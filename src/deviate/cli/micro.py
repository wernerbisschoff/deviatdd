from __future__ import annotations

import importlib.resources
import json
import os
import re
import subprocess
import time
import logging
import sys
import warnings
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import typer
import yaml
from rich.console import Console

from deviate.core._shared import JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS
from deviate.core.agent import (
    BACKEND_COMMANDS,
    AgentBackend,
    AgentBinaryNotFoundError,
    AgentSubprocessError,
    AgentTimeoutError,
    EmptyOutputError,
    HandoverManifest,
    MalformedHandoverManifestError,
    resolve_agent_to_backend,
)
from deviate.core.convention import format_commit_message
from deviate.core.profile import resolve_profile
from deviate.core.run_logger import (
    RunLogger,
    TaskLogger,
    log_event,
    set_run_logger,
    set_task_logger,
)
from deviate.core.treesitter import (
    detect_duplicate_blocks,
    estimate_cyclomatic_complexity,
    extract_dead_code,
    get_language_id,
    incremental_parse,
)
from deviate.core.worktree import find_worktree_for_branch
from deviate.prompts.assembly import assemble_prompt
from deviate.state.config import (
    AgentConfig,
    PytestReportConfig,
    SessionState,
    resolve_graphite_config,
    resolve_model_for_phase,
)
from deviate.ui.monitor import OrchestrationMonitor
from deviate.ui.pipeline import (
    PhaseCallout,
    PhaseMarker,
    PipelineSummary,
    RunBoard,
    TrainIndicator,
)
from deviate.ui.render import stdout_lock


from deviate.state.ledger import (
    RollbackSnapshot,
    TaskRecord,
    append_rollback_snapshot,
    append_task_transition,
)

console = Console()
_verbose: bool = False

_YAML_FENCE_OPEN_RE = re.compile(r"^```+\s*yaml", re.IGNORECASE)
_YAML_FENCE_CLOSE_RE = re.compile(r"^```+\s*$")
_MANIFEST_HEADER_RE = re.compile(r"^##\s*\[(?:HANDOVER_MANIFEST|MINIMAL_HANDOVER)\]")
_DEVIATE_MICRO_HEADER_RE = re.compile(r"^# DeviaTDD Micro")
_HANDOVER_XML_RE = re.compile(r"^</?handover_manifest>\s*$")

# Mise prefixes each task's stdout with "[<task-name>] ". Ruff and pytest
# emit "Finished in Nms" timing lines. Both are operational noise that
# the user does not need between phases — visible under --verbose.
_MISE_TASK_PREFIX_RE = re.compile(r"^\[[a-zA-Z][a-zA-Z0-9_-]*\]\s")
_MISE_TIMING_RE = re.compile(r"^Finished in \d+(?:\.\d+)?ms\s*$")


def _log(msg: str) -> None:
    if _verbose:
        console.print(f"[dim]{msg}[/]")


def _log_run(event: str, **kwargs: object) -> None:
    """Write to every active sink (run + task loggers).

    Per-task transcripts land in ``.deviate/logs/<issue>/<task>.log``
    while a chronological copy of every event continues into the
    per-run file under ``.deviate/logs/run_<UTC>.log``.
    """
    log_event(event, **kwargs)


_TASK_DESC_MAX = 60


def _task_label(task: dict) -> str:
    """Render ``"TSK-NNN-NN: <description>"`` for log lines.

    Falls back to the bare id when description is missing or empty.
    Description is truncated to ``_TASK_DESC_MAX`` chars to keep log lines
    scannable.
    """
    tid = task.get("id", "?")
    desc = task.get("description", "").strip()
    if not desc:
        return tid
    if len(desc) > _TASK_DESC_MAX:
        desc = desc[:_TASK_DESC_MAX].rstrip() + "…"
    return f"{tid}: {desc}"


def _phase_status_marker(outcome: str) -> PhaseMarker:
    """Map outcome string -> PhaseMarker used by the callout footer."""
    if outcome == "failed":
        return PhaseMarker.FAILED
    if outcome == "completed":
        return PhaseMarker.COMPLETED
    return PhaseMarker.IN_PROGRESS


def _emit_phase_callout(
    c: Console,
    phase: str,
    task: dict,
    status: PhaseMarker,
    duration_seconds: float | None = None,
    note: str = "",
) -> None:
    """Print a framed callout for *phase* on *task*.

    The callout header includes the literal phase token (RED / GREEN /
    JUDGE / REFACTOR / EXECUTE) so existing tests that grep
    ``result.output`` for those tokens keep passing.
    """
    c.print(
        PhaseCallout(
            phase=phase,
            task_id=task.get("id", "?"),
            task_description=task.get("description", ""),
        ).render(
            status=status,
            duration_seconds=duration_seconds,
            note=note,
        )
    )


def _phase_already_done(ledger_path: Path, task_id: str, phase: str) -> bool:
    if not ledger_path.exists():
        return False
    records = _read_ledger_records(ledger_path)
    last_pending_idx = -1
    for i, rec in enumerate(records):
        if rec.get("id") == task_id and rec.get("status") == "PENDING":
            last_pending_idx = i
    for rec in records[last_pending_idx + 1 :]:
        if rec.get("id") == task_id and rec.get("status") == phase:
            return True
    return False


# Typer apps for manual phase commands
red_app = typer.Typer(no_args_is_help=True)
green_app = typer.Typer(no_args_is_help=True)
judge_app = typer.Typer(no_args_is_help=True)
refactor_app = typer.Typer(no_args_is_help=True)
execute_app = typer.Typer(no_args_is_help=True)
e2e_app = typer.Typer(no_args_is_help=True)
hotfix_app = typer.Typer(no_args_is_help=True)
# `micro_app` is the umbrella for micro-layer subcommands surfaced as
# `deviate micro <subcommand>`. The top-level `deviate run` (which does
# `meso run` + `micro run --all`) drives `micro_app` indirectly; the
# agent also invokes it directly when it needs to drain the queue
# without going through the full meso pipeline.
micro_app = typer.Typer(no_args_is_help=True)


_LEDGER_GLOB = "specs/**/tasks.jsonl"

_SKILL_NAMES: dict[str, str | None] = {
    "RED": "deviate-red",
    "GREEN": "deviate-green",
    "JUDGE": "deviate-judge",
    "REFACTOR": "deviate-refactor",
    "EXECUTE": "deviate-execute",
}


def _load_skill_content(phase_name: str) -> str | None:
    skill_name = _SKILL_NAMES.get(phase_name.upper())
    if not skill_name:
        return None
    try:
        path = importlib.resources.files("deviate.prompts.commands").joinpath(
            f"{skill_name}.md"
        )
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        fallback = Path("src/deviate/prompts/commands") / f"{skill_name}.md"
        if fallback.exists():
            return fallback.read_text(encoding="utf-8")
        return None


def _build_agent_prompt(skill_content: str, phase: str, task: dict, root: Path) -> str:
    task_context = json.dumps(
        {
            "phase": phase,
            "task_id": task.get("id", ""),
            "issue_id": task.get("issue_id", ""),
            "description": task.get("description", ""),
            "execution_mode": task.get("execution_mode", "TDD"),
            "repo_root": str(root.resolve()),
        },
        indent=2,
    )
    return skill_content.replace("$ARGUMENTS", task_context)


_TOOL_CALL_INDICATORS = frozenset(
    {
        '"tool_use"',
        '"tool_calls"',
        "tool_use",
        "tool_calls",
        '"function"',
        "<function_calls>",
        "<invoke ",
        "<tool_call",
        "<use_tool",
        "[Tool",
        '"name": "',
        '"type":"tool',
        '"type": "tool',
    }
)


def _is_tool_call(line: str) -> bool:
    lower = line.lower().strip()
    return any(ind in lower for ind in _TOOL_CALL_INDICATORS)


def _try_parse_claude_text(line: str) -> str | None:
    try:
        data = json.loads(line)
        if isinstance(data, dict) and data.get("type") == "text":
            return data.get("text", "")
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _make_agent_output_callback(
    monitor: OrchestrationMonitor | None,
    task_id: str,
    phase: str,
) -> Callable[[str], None] | None:
    if monitor is None:
        return None

    def _callback(line: str) -> None:
        monitor.push_event("agent_output", task_id=task_id, phase=phase, line=line)

    return _callback


def _maybe_push_event(
    monitor: OrchestrationMonitor | None,
    event_type: str,
    **data: str | None,
) -> None:
    if monitor:
        monitor.push_event(event_type, **data)


def _emit_yaml_summary(yaml_lines: list[str], c: Console) -> None:
    yaml_text = "\n".join(yaml_lines)
    try:
        data = yaml.safe_load(yaml_text)
    except Exception:
        return
    if not isinstance(data, dict):
        return

    phase = data.get("phase", "")
    status = data.get("status", "")
    verdict = data.get("verdict", "")

    if phase:
        status_str = status or verdict
        if status_str:
            c.print(f"  [dim]{phase} \u2192 {status_str}[/]")
        else:
            c.print(f"  [dim]{phase} complete[/]")


def _make_output_handler(c: Console, verbose: bool = False) -> Callable[[str], None]:
    in_thinking = False
    thinking_buf: list[str] = []
    in_yaml = False
    yaml_lines: list[str] = []

    def handler(line: str) -> None:
        nonlocal in_thinking, thinking_buf, in_yaml, yaml_lines
        with stdout_lock:
            stripped = line.strip()
            if not stripped:
                return

            if not verbose:
                if _YAML_FENCE_OPEN_RE.match(stripped):
                    in_yaml = True
                    yaml_lines = []
                    return

                if in_yaml:
                    if _YAML_FENCE_CLOSE_RE.match(stripped):
                        _emit_yaml_summary(yaml_lines, c)
                        in_yaml = False
                        yaml_lines = []
                        return
                    yaml_lines.append(stripped)
                    return

                if _MANIFEST_HEADER_RE.match(stripped):
                    return
                if _DEVIATE_MICRO_HEADER_RE.match(stripped):
                    return
                if _HANDOVER_XML_RE.match(stripped):
                    return
                if _MISE_TASK_PREFIX_RE.match(stripped):
                    return
                if _MISE_TIMING_RE.match(stripped):
                    return

            if "<thinking" in stripped.lower():
                in_thinking = True
                thinking_buf = [stripped]
                return

            if in_thinking:
                if "</thinking>" in stripped.lower():
                    thinking_buf.append(stripped)
                    content = " ".join(thinking_buf)
                    content = (
                        content.replace("<thinking>", "")
                        .replace("</thinking>", "")
                        .replace("<Thinking>", "")
                        .replace("</Thinking>", "")
                    )
                    c.print(f"[dim]{content[:600]}[/]")
                    in_thinking = False
                    thinking_buf = []
                    return
                thinking_buf.append(stripped)
                return

            claude_text = _try_parse_claude_text(stripped)
            if claude_text is not None:
                if claude_text.strip():
                    c.print(claude_text[:600], style="dim", markup=False)
                return

            if _is_tool_call(stripped):
                c.print("[dim].[/]", end="")
                return

            c.print(stripped[:600], style="dim", markup=False)

    return handler


_PI_TOKEN_FIELD_RE = re.compile(r"^tokens\.(\w+):\s*(\d+)\s*$", re.MULTILINE)


def _extract_pi_session_stats(stdout: str) -> dict[str, int] | None:
    """Parse Pi agent token usage from stdout into a dict with camelCase keys.

    Recognises lines matching ``tokens.<field>: <integer>`` and returns a
    dict keyed by the field name with the ``tokens.`` prefix stripped
    (e.g. ``tokens.cacheRead`` → ``cacheRead``). Returns ``None`` when no
    token fields are present so the caller can distinguish "absent" from
    "present with zero values".
    """
    stats: dict[str, int] = {
        match.group(1): int(match.group(2))
        for match in _PI_TOKEN_FIELD_RE.finditer(stdout)
    }
    return stats or None


def _invoke_agent(
    prompt: str,
    c: Console,
    backend_name: str = "pi",
    task_id: str = "",
    phase: str = "",
    output_callback: Callable[[str], None] | None = None,
    model: str | None = None,
) -> tuple[HandoverManifest | None, str]:
    model_str = f" --model {model}" if model else ""
    c.print(
        f"  [green]INVOKE_AGENT[/] running '{backend_name}{model_str}' for [{phase}] phase"
    )
    _log_run(
        "INVOKE_AGENT",
        task_id=task_id,
        phase=phase,
        backend=backend_name,
        model=model or "(default)",
        prompt=prompt,
    )
    try:
        backend = AgentBackend(config=AgentConfig(backend=backend_name))
        output_handler = _make_output_handler(c, verbose=_verbose)
        raw_lines: list[str] = []

        def collecting_handler(line: str) -> None:
            raw_lines.append(line)
            output_handler(line)
            if output_callback:
                output_callback(line)

        manifest = backend.invoke(
            prompt, output_callback=collecting_handler, model=model
        )
        c.print("")
        status = getattr(manifest, "status", "?")
        verdict = getattr(manifest, "verdict", "")
        manifest_json = manifest.model_dump_json()
        agent_result_kwargs: dict[str, object] = {
            "task_id": task_id,
            "phase": phase,
            "status": status,
            "verdict": verdict,
            "manifest": manifest_json,
        }
        if backend_name == "pi":
            agent_result_kwargs["pi_session_stats"] = _extract_pi_session_stats(
                "\n".join(raw_lines)
            )
        _log_run("AGENT_RESULT", **agent_result_kwargs)
        if raw_lines:
            _log_run(
                "AGENT_RAW_OUTPUT",
                task_id=task_id,
                phase=phase,
                raw_output="\n".join(raw_lines),
            )
        # Last 50 non-blank stdout lines from the agent invocation, used
        # by the phase runner as a fallback diagnostic when the
        # manifest's `rationale` is empty (the prior "unknown" symptom).
        tail_lines = [line for line in raw_lines if line.strip()][-50:]
        return manifest, "\n".join(tail_lines)
    except AgentBinaryNotFoundError:
        c.print(
            f"  [yellow]AGENT_NOT_AVAILABLE[/] {backend_name} not found on PATH, skipping"
        )
        _log_run(
            "AGENT_NOT_AVAILABLE", task_id=task_id, phase=phase, backend=backend_name
        )
        return None, ""
    except AgentTimeoutError as exc:
        partial_output = exc.partial_stdout or ""
        c.print(f"  [yellow]AGENT_ERROR[/] {exc}")
        _log_run(
            "AGENT_TIMEOUT",
            task_id=task_id,
            phase=phase,
            error=str(exc),
            partial_stderr=exc.partial_stderr,
            partial_stdout=partial_output,
        )
        return None, partial_output
    except (
        AgentSubprocessError,
        MalformedHandoverManifestError,
        EmptyOutputError,
    ) as exc:
        c.print(f"  [yellow]AGENT_ERROR[/] {exc}")
        _log_run("AGENT_ERROR", task_id=task_id, phase=phase, error=str(exc))
        return None, ""
    except Exception as exc:
        c.print(f"  [yellow]AGENT_SKIP[/] {exc}")
        return None, ""


_TIMEOUT_SUMMARY_PROMPT = """\
The previous agent attempt for the GREEN (implementation) phase timed out.
Partial output from that attempt is below.

Concisely summarize (under 200 words):
- What was being attempted?
- What was already completed?
- What errors or obstacles occurred?
- What should the next attempt try differently?

<partial_output>
{partial_text}
</partial_output>
"""


def _summarize_timeout_context(
    partial_output: str,
    backend_name: str = "pi",
) -> str:
    """Call the agent backend to summarize timeout partial output."""
    truncated = partial_output[-5000:] if len(partial_output) > 5000 else partial_output
    prompt = _TIMEOUT_SUMMARY_PROMPT.format(partial_text=truncated)
    backend_cmd = BACKEND_COMMANDS.get(backend_name, "pi -p")
    cmd = backend_cmd.split()
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_bytes, _ = proc.communicate(input=prompt.encode("utf-8"), timeout=30)
        summary = stdout_bytes.decode("utf-8").strip()
        if len(summary) > 2000:
            summary = "..." + summary[-1997:]
        return summary
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass
        return (
            "[Previous GREEN attempt timed out \u2014 summarization also timed out. "
            "Check .deviate/logs/ (run_*.log and per-task logs) for partial output.]"
        )
    except FileNotFoundError:
        return (
            f"[Previous GREEN attempt timed out. Partial output "
            f"(last {len(truncated)} chars):\n"
            f"{truncated[-500:]}]"
        )


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _resolve_workspace_root() -> Path:
    """Resolve workspace root from current branch → worktree path.

    If already inside a git worktree (``.git`` is a file), returns CWD.
    Otherwise queries the current branch and looks up the matching
    worktree path.  Falls back to ``Path.cwd()`` when neither applies.
    """
    root = Path.cwd()
    git_path = root / ".git"
    if git_path.exists() and not git_path.is_dir():
        return root
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if branch and branch != "HEAD":
            wt = find_worktree_for_branch(branch, repo=root)
            if wt is not None:
                return wt
    except (subprocess.CalledProcessError, OSError):
        pass
    return root


def _read_ledger_records(ledger_file: Path) -> list[dict]:
    records: list[dict] = []
    try:
        with open(ledger_file, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return records


def _resolve_issue_number(task_id: str) -> str | None:
    m = re.match(r"^TSK-(\d{3})-\d{2}$", task_id)
    if m:
        return m.group(1)
    return None


def _find_task_record(root: Path, task_id: str) -> tuple[dict, Path] | None:
    """Look up the latest (current) record by its TSK-NNN-NN ID."""
    for rec, ledger_file in _collect_latest_task_records(root):
        if rec.get("id") == task_id:
            return rec, ledger_file
    return None


_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "REFACTOR"}


def _collect_latest_task_records(root: Path) -> list[tuple[dict, Path]]:
    """Return the latest record per task ID across all ledger files.

    Because the ledger is append-only (chronological within each file,
    files sorted lexicographically), the last seen record for each task
    ID represents its current status.
    """
    latest: dict[str, dict] = {}
    ledger_of: dict[str, Path] = {}
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for rec in _read_ledger_records(ledger_file):
            tid = rec.get("id")
            if tid:
                latest[tid] = rec
                ledger_of[tid] = ledger_file
    return [(latest[tid], ledger_of[tid]) for tid in latest]


_BRANCH_SLUG_RE = re.compile(r"^feat/([^/]+)/([^/]+(?:/[^/]+)*)$")
_TASK_LINE_RE = re.compile(r"^\s*-\s+(?:\[(x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.*)")
_MODE_LINE_RE = re.compile(r"^\s*-\s+\*\*Mode\*\*:\s*(\S+)")
_TASK_BULLET_HEAD_RE = re.compile(r"^- (?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):")
_JUDGE_FEEDBACK_BULLET_RE = re.compile(r"^\s+-\s+\*\*Judge Feedback\*\*:\s*(.*)")


def _find_all_pending_tasks(
    root: Path, issue_id: str | None = None
) -> list[tuple[dict, Path]]:
    _log(f"find_all_pending_tasks: issue_id={issue_id}, root={root}")

    latest_by_issue: dict[tuple[str, str], dict] = {}
    ledger_of_by_issue: dict[tuple[str, str], Path] = {}
    for rec, ledger_file in _collect_latest_task_records(root):
        tid = rec["id"]
        rec_issue = rec.get("issue_id", "")
        if not rec_issue:
            continue
        if issue_id is not None and rec_issue != issue_id:
            _log(f"  skipping {tid} from issue {rec_issue} (expected {issue_id})")
            continue
        key = (rec_issue, tid)
        latest_by_issue[key] = rec
        ledger_of_by_issue[key] = ledger_file
        _log(
            f"  ledger record: {tid} ({rec_issue})"
            f" → {rec.get('status')} ({ledger_file.name})"
        )

    seen: set[str] = set()
    results: list[tuple[dict, Path]] = []

    def _process_one_tasks_md(md_path: Path, md_issue_id: str) -> None:
        fallback = md_path.parent / "tasks.jsonl"
        content_lines = md_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(content_lines):
            m = _TASK_LINE_RE.match(line)
            if m is None:
                continue
            tid = m.group(2)
            checkbox = m.group(1)
            _log(f"  tasks.md task: {tid} (issue={md_issue_id})")
            seen.add(tid)
            key = (md_issue_id, tid)
            rec = latest_by_issue.get(key)
            if rec is not None:
                if rec.get("status") in _TERMINAL_STATUSES:
                    _log(f"    → terminal ({rec.get('status')}), skipping")
                    continue
                _log(f"    → status={rec.get('status')}, including")
                results.append((rec, ledger_of_by_issue.get(key, fallback)))
                continue
            if checkbox and checkbox.lower() == "x":
                _log("    → checked [x] in tasks.md, skipping")
                continue
            mode = "TDD"
            for j in range(i + 1, min(i + 10, len(content_lines))):
                mode_m = _MODE_LINE_RE.match(content_lines[j])
                if mode_m:
                    mode = mode_m.group(1)
                    break
            _log(f"    → no ledger entry, mode={mode}")
            results.append(
                (
                    {
                        "id": tid,
                        "issue_id": md_issue_id,
                        "description": m.group(3).strip(),
                        "status": "PENDING",
                        "execution_mode": mode,
                    },
                    fallback,
                )
            )

    if issue_id is not None:
        tasks_md = _find_tasks_md_for_issue(root, issue_id)
        _log(f"  tasks_md: {tasks_md}")
        if tasks_md is not None:
            _process_one_tasks_md(tasks_md, issue_id)
    else:
        for tasks_md in sorted(root.glob("specs/**/tasks.md")):
            md_issue_id = _resolve_md_issue_id(tasks_md)
            _log(f"  tasks_md: {tasks_md} → issue_id={md_issue_id}")
            _process_one_tasks_md(tasks_md, md_issue_id)

    for (rec_issue, tid), rec in latest_by_issue.items():
        if tid in seen:
            continue
        if issue_id is not None and rec_issue != issue_id:
            continue
        if rec.get("status") not in _TERMINAL_STATUSES:
            _log(
                f"  orphan ledger task: {tid} ({rec_issue}"
                f", {rec.get('status')}), including"
            )
            results.append((rec, ledger_of_by_issue[(rec_issue, tid)]))
        else:
            _log(
                f"  orphan ledger task: {tid} ({rec_issue}"
                f", {rec.get('status')}), skipping"
            )

    _log(f"  total pending: {len(results)}")
    return results


def _resolve_issue_source_file(root: Path, issue_id: str) -> str | None:
    """Resolve source_file from specs/issues.jsonl for a given issue_id."""
    ledger_path = root / "specs" / "issues.jsonl"
    if not ledger_path.exists():
        return None
    for data in _read_ledger_records(ledger_path):
        if data.get("issue_id") == issue_id:
            return data.get("source_file")
    return None


def _find_tasks_md_for_issue(root: Path, issue_id: str) -> Path | None:
    """Find tasks.md for a given issue_id by reading issues.jsonl."""
    source_file = _resolve_issue_source_file(root, issue_id)
    if not source_file:
        return None
    parts = PurePosixPath(source_file)
    if len(parts.parts) < 3:
        return None
    epic = parts.parent.parent.name
    slug = parts.stem
    tasks_md = root / "specs" / epic / slug / "tasks.md"
    if tasks_md.exists():
        return tasks_md
    return None


def _resolve_md_issue_id(md_path: Path) -> str:
    """Derive issue_id from a tasks.md's sibling tasks.jsonl."""
    ledger_path = md_path.parent / "tasks.jsonl"
    if not ledger_path.exists():
        return ""
    for rec in _read_ledger_records(ledger_path):
        iid = rec.get("issue_id", "")
        if iid:
            return iid
    return ""


def _resolve_issue_id_from_branch(root: Path) -> str | None:
    """Derive issue_id from the current git branch via issues.jsonl."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    m = _BRANCH_SLUG_RE.match(branch)
    if not m:
        return None
    bucket = m.group(1)
    slug = m.group(2)
    target = f"{bucket}/issues/{slug}.md"
    ledger_path = root / "specs" / "issues.jsonl"
    if not ledger_path.exists():
        return None
    for rec in _read_ledger_records(ledger_path):
        src = rec.get("source_file", "")
        if target in src:
            return rec.get("issue_id")
    return None


def _append_status_transition(
    task_data: dict, new_status: str, ledger_path: Path
) -> None:
    record = TaskRecord(
        id=task_data["id"],
        issue_id=task_data.get("issue_id", ""),
        description=task_data.get("description", ""),
        status=new_status,
        execution_mode=task_data.get("execution_mode", "TDD"),
    )
    append_task_transition(record, ledger_path)


def _resolve_task_context(task_id: str | None, root: Path) -> tuple[dict, Path] | None:
    if task_id is not None:
        if not re.match(r"^TSK-\d{3}-\d{2}$", task_id):
            console.print(
                f"[red]TASK_NOT_FOUND[/] Unrecognised task ID format: {task_id}"
            )
            raise typer.Exit(code=1)
        result = _find_task_record(root, task_id)
        if result is None:
            console.print(f"[red]TASK_NOT_FOUND[/] No task matching {task_id}")
            raise typer.Exit(code=1)
        return result

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )

    pending = _find_all_pending_tasks(root, issue_id=session.active_issue_id)
    if not pending:
        console.print("[red]NO_PENDING_TASKS[/]")
        raise typer.Exit(code=1)
    return pending[0]


def _resolve_latest_task(
    root: Path, issue_id: str, status: str
) -> tuple[dict, Path] | None:
    """Return the most recent task record with *issue_id* and *status*."""
    latest: tuple[dict, Path] | None = None
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for rec in _read_ledger_records(ledger_file):
            if rec.get("issue_id") == issue_id and rec.get("status") == status:
                latest = (rec, ledger_file)
    return latest


def _resolve_first_pending(root: Path, issue_id: str) -> tuple[dict, Path] | None:
    """Return the first task whose latest status is PENDING for *issue_id*."""
    for rec, ledger_file in _find_all_pending_tasks(root, issue_id=issue_id):
        if rec.get("status") == "PENDING":
            return (rec, ledger_file)
    return None


def _build_scope(issue_id: str, task_id: str) -> str:
    """Return the task ID as scope (already TSK-NNN-NN format)."""
    if task_id and task_id != "?":
        return task_id
    return issue_id


def _build_auto_prompt(phase: str, task: dict, root: Path) -> str:
    """Build a prompt from auto templates with context injected."""
    issue_id = task.get("issue_id", "")
    task_id = task.get("id", "")
    source_file = _resolve_issue_source_file(root, issue_id) if issue_id else None

    spec_content = _resolve_spec_md(root, task)

    feature_slug = ""
    issue_slug = ""
    if source_file:
        parts = PurePosixPath(source_file)
        feature_slug = parts.parent.parent.name if len(parts.parts) >= 3 else ""
        issue_slug = parts.stem

    data_model_content = ""
    if feature_slug and issue_slug:
        dm_path = root / "specs" / feature_slug / issue_slug / "data-model.md"
        if dm_path.exists():
            data_model_content = dm_path.read_text(encoding="utf-8")

    prd_content = ""
    if feature_slug:
        prd_path = root / "specs" / feature_slug / "prd.md"
        if prd_path.exists():
            prd_content = prd_path.read_text(encoding="utf-8")

    task_content = json.dumps(task, indent=2)
    test_command = task.get("verification", "")
    lint_command = _resolve_lint_command(root)
    verification_command = task.get("verification", "")
    verification_binary = task.get("verification", "")

    const_path = root / "specs" / "constitution.md"

    context: dict[str, str] = {
        "task_content": task_content,
        "spec_content": spec_content,
        "data_model_content": data_model_content,
        "prd_content": prd_content,
        "task_id": task_id,
        "issue_id": issue_id,
        "feature_slug": feature_slug,
        "test_command": test_command,
        "lint_command": lint_command,
        "verification_command": verification_command,
        "verification_binary": verification_binary,
        "next_phase": "",
    }
    return assemble_prompt(
        template_name=phase, context=context, constitution_path=const_path
    )


def _resolve_lint_command(root: Path) -> str:
    const_path = root / "specs" / "constitution.md"
    if const_path.exists():
        from deviate.core.constitution import extract_commands

        cmds = extract_commands(const_path)
        return cmds.get("lint_command", "")
    return ""


def _run_red_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    if _phase_already_done(ledger_path, task.get("id", ""), "RED"):
        c.print(f"  [dim]RED already done for {_task_label(task)}, skipping[/]")
        return session
    _log_run("PHASE_START", task_id=tid, phase="RED")
    _emit_phase_callout(c, "RED", task, PhaseMarker.IN_PROGRESS)
    if _verbose:
        c.print(f"  [bold blue]RED →[/] {_task_label(task)}")

    backend = agent or "pi"
    root = Path.cwd()
    prompt = _build_auto_prompt("red", task, root)
    agent_output_callback = _make_agent_output_callback(monitor, tid, "RED")
    red_model = resolve_model_for_phase("RED", root)
    manifest, agent_tail = _invoke_agent(
        prompt,
        c,
        backend_name=backend,
        task_id=tid,
        phase="RED",
        output_callback=agent_output_callback,
        model=red_model,
    )
    if manifest is None:
        raise PhaseFailedError(
            f"RED phase agent error for {tid}: agent returned no manifest"
        )
    if manifest.status.upper() in ("FAILURE", "ERROR"):
        rationale = manifest.rationale or "unknown"
        tail = agent_tail or "(no agent output captured)"
        raise PhaseFailedError(
            f"RED phase failed for {tid}: {rationale}\n"
            f"  agent_output_tail (last 50 non-blank stdout lines):\n{tail}"
        )

    issue_id = task.get("issue_id", "")
    scope = _build_scope(issue_id, tid)

    test_files = _find_test_files(root)
    if test_files:
        _run_test_cmd(root)

    _run_format_cmd(root)

    try:
        record = TaskRecord.model_validate(task)
        record.status = "RED"
        append_task_transition(record, ledger_path)
    except Exception as e:
        raise PhaseFailedError(f"RED phase ledger update failed for {tid}: {e}")

    session = session.force_transition_to("RED")
    session.save(session_path)

    _commit_phase(
        f"test({scope}): RED phase - failing test",
        root,
        no_verify=True,
        phase="red",
    )

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    session.red_commit_sha = head_sha
    session.save(session_path)

    _verify_clean_worktree(root, "RED", tid)
    return session


def _run_green_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    if _phase_already_done(ledger_path, task.get("id", ""), "GREEN"):
        if not session.train_feedback:
            c.print(f"  [dim]GREEN already done for {_task_label(task)}, skipping[/]")
            return session
        c.print(
            f"  [dim]GREEN already done for {_task_label(task)}"
            f" but train_feedback present — re-running[/]"
        )
    _log_run("PHASE_START", task_id=tid, phase="GREEN")
    _emit_phase_callout(c, "GREEN", task, PhaseMarker.IN_PROGRESS)
    if _verbose:
        c.print(f"  [bold green]GREEN →[/] {_task_label(task)}")
    root = Path.cwd()
    backend = agent or "pi"

    prompt = _build_auto_prompt("green", task, root)
    if session.train_feedback:
        prompt += f"\n\n<train_feedback>\n{session.train_feedback}\n</train_feedback>\n"
    else:
        persisted = _read_judge_feedback_from_tasks_md(root, task)
        if persisted:
            prompt += f"\n\n<persisted_judge_feedback>\n{persisted}\n</persisted_judge_feedback>\n"
    agent_output_callback = _make_agent_output_callback(monitor, tid, "GREEN")
    green_model = resolve_model_for_phase("GREEN", root)
    manifest, timeout_ctx = _invoke_agent(
        prompt,
        c,
        backend_name=backend,
        task_id=tid,
        phase="GREEN",
        output_callback=agent_output_callback,
        model=green_model,
    )
    if manifest is None and timeout_ctx:
        c.print(
            "  [yellow]TIMEOUT[/] GREEN agent timed out \u2014 summarizing context for retry"
        )
        summary = _summarize_timeout_context(timeout_ctx, backend_name=backend)
        session.train_feedback = summary
        session.save(session_path)
        raise PhaseFailedError(f"GREEN phase agent timed out for {tid}")
    if manifest is None:
        raise PhaseFailedError(
            f"GREEN phase agent error for {tid}: agent returned no manifest"
        )
    if manifest.status.upper() in ("FAILURE", "ERROR", "FAIL"):
        if _is_hitl_escalation(manifest):
            _log_run(
                "GREEN_HITL_ESCALATION",
                task_id=tid,
                manifest=manifest.model_dump_json(),
            )
            _render_hitl_banner(manifest, c, tid, "GREEN")
            try:
                record = TaskRecord.model_validate(task)
                record.status = "HITL_PENDING"
                append_task_transition(record, ledger_path)
            except Exception as e:
                c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")
            raise HitlEscalationError(
                f"GREEN phase escalated to HITL for {tid}: "
                f"agent returned structured contract_drift/hitl_options"
            )
        rationale = manifest.rationale or ""
        tail = timeout_ctx or "(no agent output captured)"
        if rationale:
            # GREEN FAILURE with rationale: route to JUDGE for routing decision.
            # The `failure_kind` discriminator tells the JUDGE prompt which
            # outcome class to emit:
            #   - "mechanical" — RED test cannot be satisfied via the
            #     library/API surface declared in scope. JUDGE picks between
            #     `revert_before` (test wrong → re-run RED),
            #     `revert_to_red` (slice/scope wrong → re-run GREEN with
            #     feedback), and `skip_refactor` (operator widen scope).
            #   - "test_defect" — GREEN judged the RED test itself wrong
            #     (asserts behavior the spec doesn't require, exercises a
            #     surface that's the wrong abstraction, etc.). Pre-decided
            #     routing: `revert_before` (re-run RED). GREEN surfaces this
            #     via `failure_kind: test_defect` in its manifest; we
            #     default to "mechanical" if unset so prior behavior holds.
            failure_kind = manifest.failure_kind or "mechanical"
            c.print(
                f"  [yellow]GREEN_{failure_kind.upper()}_FAILURE[/] {tid} \u2014 "
                f"routing to JUDGE for scope/test decision"
            )
            session.train_feedback = rationale
            session.failure_kind = failure_kind
            session = session.force_transition_to("GREEN")
            session.save(session_path)
            _log_run(
                "GREEN_FAILURE",
                task_id=tid,
                failure_kind=failure_kind,
                rationale_preview=rationale.replace("\n", " ")[:200],
                reroute="JUDGE",
            )
            return session
        # Empty rationale — agent emitted FAILURE but no info for JUDGE.
        # Preserve prior "unknown" symptom + agent_output_tail dump.
        raise PhaseFailedError(
            f"GREEN phase failed for {tid}: unknown\n"
            f"  agent_output_tail (last 50 non-blank stdout lines):\n{tail}"
        )

    session = session.force_transition_to("GREEN")
    session.train_feedback = ""
    session.failure_kind = ""
    session.judge_rejected = False
    session.save(session_path)

    issue_id = task.get("issue_id", "")
    scope = _build_scope(issue_id, tid)

    test_result = _run_test_cmd(root, task)
    if test_result.returncode != 0:
        failure_output = test_result.stdout or ""
        if test_result.stderr:
            failure_output += "\n--- stderr ---\n" + test_result.stderr
        c.print(
            f"  [yellow]TEST_FAILURE[/] {tid} \u2014 keeping implementation for JUDGE assessment"
        )
        session.train_feedback = (
            "The test suite failed after GREEN implementation.\n\n"
            f"<test_output>\n{failure_output}\n</test_output>"
        )
        session.save(session_path)
        return session

    _run_format_cmd(root)

    try:
        record = TaskRecord.model_validate(task)
        record.status = "GREEN"
        append_task_transition(record, ledger_path)
    except Exception as e:
        raise PhaseFailedError(f"GREEN phase ledger update failed for {tid}: {e}")

    _commit_phase(
        f"feat({scope}): GREEN phase - implementation",
        root,
        no_verify=True,
        phase="green",
    )

    try:
        _verify_clean_worktree(root, "GREEN", tid)
    except PhaseFailedError as e:
        c.print(f"  [yellow]CLEAN_WORKTREE_FAILED[/] {e}")
        # Try to commit leftover files instead of destroying the GREEN commit
        issue_id = task.get("issue_id", "")
        scope = _build_scope(issue_id, tid)
        residual_committed = _commit_phase(
            f"feat({scope}): GREEN phase - residual files",
            root,
            no_verify=True,
            phase="green",
        )
        if residual_committed:
            c.print(f"  [green]Residual files committed[/] for {tid}")
        else:
            c.print(
                f"  [yellow]WARNING[/] {tid} has uncommitted files after GREEN — "
                "leaving for JUDGE assessment"
            )
        session.train_feedback = str(e)
        session.save(session_path)
    return session


def _resolve_spec_md(root: Path, task: dict) -> str:
    """Read spec-enriched issue file content for *task*.

    The issue file IS the spec — spec sections are embedded in the issue
    file markdown.  No separate ``spec.md`` exists.
    """
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return ""
    source_file = _resolve_issue_source_file(root, issue_id)
    if not source_file:
        return ""
    issue_path = root / source_file
    if issue_path.exists():
        return issue_path.read_text(encoding="utf-8")
    return ""


def _resolve_tasks_md(root: Path, task: dict) -> Path | None:
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return None
    return _find_tasks_md_for_issue(root, issue_id)


def _append_judge_feedback(tasks_md: Path, task_id: str, feedback: str) -> int | None:
    """Append judge feedback under the matching task line in tasks.md.

    Returns the number of feedback lines inserted, or ``None`` if no
    matching task line was found (so callers can surface a "no tasks.md
    update" log line and skip the bookkeeping commit).
    """
    content = tasks_md.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines: list[str] = []
    inserted = False
    feedback_lines = feedback.strip().splitlines() or [""]
    for line in lines:
        new_lines.append(line)
        if not inserted and task_id in line and line.strip().startswith("-"):
            indent = "  "
            for fb_line in feedback_lines:
                new_lines.append(f"{indent}- **Judge Feedback**: {fb_line}")
                indent = "    "
            inserted = True
    if inserted:
        tasks_md.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return len(feedback_lines)
    return None


def _read_judge_feedback_from_tasks_md(root: Path, task: dict) -> str:
    """Read persisted Judge Feedback bullets for the exact task block."""
    target = task.get("id", "")
    if not target:
        return ""
    tasks_md = _resolve_tasks_md(root, task)
    if tasks_md is None:
        return ""
    try:
        lines = tasks_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    feedback: list[str] = []
    in_target = False
    for line in lines:
        head = _TASK_BULLET_HEAD_RE.match(line)
        if head is not None:
            if in_target:
                break
            if head.group(1) == target:
                in_target = True
            continue
        if in_target:
            match = _JUDGE_FEEDBACK_BULLET_RE.match(line)
            if match is not None:
                feedback.append(f"- **Judge Feedback**: {match.group(1).rstrip()}")
    return "\n".join(feedback)


def _resolve_red_boundary_sha(root: Path) -> str:
    session_path = root / ".deviate" / "session.json"
    if session_path.exists():
        session = SessionState.load(session_path)
        if session.red_commit_sha:
            return session.red_commit_sha
    _log("No RED commit SHA in session — falling back to HEAD~1 as boundary")
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    if parent:
        return parent
    _log("HEAD~1 is empty — using root commit as last resort")
    root_sha = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    return root_sha


def _execute_rollback(root: Path, reason: str, phase: str = "JUDGE") -> str:
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    red_sha = _resolve_red_boundary_sha(root)
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    snapshot = RollbackSnapshot(
        phase=phase,
        branch=branch,
        commit_sha=commit_sha,
        red_sha=red_sha,
        reason=reason[:500],
    )
    append_rollback_snapshot(snapshot, root / ".deviate")

    # Discard any uncommitted session state
    subprocess.run(
        ["git", "checkout", "--quiet", "--", ".deviate/"],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )

    # Reset to red_sha — discards ALL commits made during GREEN (agent
    # commit, orchestrator commit, residual commit) preserving only RED
    # and any previous judge feedback commits.
    #
    # If GREEN never committed (tests failed, early return),
    # HEAD == red_sha and the reset is a no-op on history.
    subprocess.run(
        ["git", "reset", "--hard", red_sha],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )

    # Remove untracked files and directories created during GREEN so they
    # don't pollute the next RED attempt (pytest collection, test writer
    # edits). Uses `-fd` (force + directories) WITHOUT `-x` to preserve
    # gitignored state such as `.deviate/`, `.mise/`, `__pycache__/`,
    # and `.worktrees/`.
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )
    return red_sha


# Defensive regex matching the RED-phase commit subject built by
# _commit_phase. The pre-RED anchor is usually `red_commit_sha^`, but if
# the parent doesn't look like a RED-phase commit (e.g. the user amended
# the boundary, ran a micro layer on top of an E2E/direct commit, or the
# repo's history is malformed), log a warning so the operator knows the
# resolution is on best-effort grounds.
_PRE_RED_SHA_PARENT_RE = re.compile(r"^(?:.+ )?test\([^)]+\): RED phase(?:\s|$)")


def _resolve_pre_red_sha(root: Path, red_sha: str) -> str:
    """Return the SHA to reset to for ``next_action="revert_before"``.

    The pre-RED anchor is ``red_commit_sha^`` — the commit just before the
    task's RED phase landed. When ``red_sha^`` does not look like a
    RED-phase commit (defensive regex check on its subject), log a
    ``PRE_RED_AMBIGUOUS`` warning so the operator knows the resolution is
    best-effort, but still return the parent so the rollback can proceed.
    """
    parent = subprocess.run(
        ["git", "rev-parse", f"{red_sha}^"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    if not parent:
        return ""
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s", parent],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    if not _PRE_RED_SHA_PARENT_RE.match(subject):
        logging.getLogger(__name__).warning(
            "PRE_RED_AMBIGUOUS: red_commit_sha %s's parent (%s) has "
            "subject %r; expected a RED-phase commit. Falling back to "
            "red_sha^ anyway.",
            red_sha[:7],
            parent[:7],
            subject,
        )
    return parent


def _format_violations_as_feedback(
    violations: list[dict[str, object]],
) -> str:
    """Render a structured ``violations`` list as readable feedback text.

    Both judge schemas are supported:
    - Auto template: category / file / detail / severity / recommendation
    - Manual skill: file / detail / severity / requirement

    Returns an empty string when the list is empty so the caller can chain
    it as another fallback in the feedback-resolution cascade.
    """
    if not violations:
        return ""
    lines: list[str] = []
    for i, v in enumerate(violations, start=1):
        category = v.get("category", "")
        file = v.get("file", "")
        detail = v.get("detail", "")
        severity = v.get("severity", "")
        requirement = v.get("requirement", "")
        recommendation = v.get("recommendation", "")
        parts: list[str] = []
        if category:
            parts.append(f"[{category}]")
        if severity:
            parts.append(f"({severity})")
        if file:
            parts.append(f"file: {file}")
        if requirement:
            parts.append(f"req: {requirement}")
        head = " ".join(parts) if parts else f"violation {i}"
        body = detail or ""
        if recommendation:
            body = (body + " " if body else "") + f"Recommendation: {recommendation}"
        lines.append(f"- {head}: {body}".rstrip())
    return "\n".join(lines)


# ---- Judge next_action routing ---------------------------------------------
#
# JUDGE decides, via HandoverManifest.next_action, how the runner should
# route the task on compliance outcome. Four values:
#
#   revert_before     — discard this task's GREEN *and* its RED; restart
#                       from pre-RED so RED can re-author the failing test.
#                       Used when the test itself is wrong.
#   revert_to_red     — discard GREEN, keep RED, advance red_commit_sha
#                       past the feedback commit so a second rollback
#                       preserves the new GREEN attempt's history. (Default
#                       on COMPLIANCE_VIOLATION when next_action is omitted
#                       — preserves the prior behavior that this module is
#                       fixing regression on.)
#   continue_refactor — GREEN already correct; skip JUDGEs verdict-loop
#                       and route directly to REFACTOR.
#   skip_refactor     — GREEN already correct and refactor not wanted;
#                       mark the task COMPLETED and move on.
#
# The runner honors the manifest verbatim. There is no interactive prompt:
# operators can override externally via a CLI flag (future work), not via
# a runtime question.
_JUDGE_ACTIONS = frozenset(
    {"revert_before", "revert_to_red", "continue_refactor", "skip_refactor"}
)


def _coerce_judge_action(manifest: HandoverManifest, verdict: str) -> str | None:
    """Return the manifest's ``next_action`` if valid; default to
    ``revert_to_red`` on violation when the field is absent; ``None`` on
    pass when the field is absent.
    """
    next_action = getattr(manifest, "next_action", None)
    if next_action in _JUDGE_ACTIONS:
        return next_action
    if next_action is not None and next_action != "":
        # Manifest declared an unknown action. Log + fall back: an action
        # the runner doesn't understand must not stall the task.
        _log(
            f"JUDGE_UNKNOWN_ACTION ignored: {next_action!r}; defaulting "
            f"verdict={verdict!r}"
        )
        next_action = None
    if verdict.upper() == "COMPLIANCE_VIOLATION":
        return "revert_to_red"
    return None


def _judge_feedback_from_manifest(manifest: HandoverManifest) -> tuple[str, str]:
    """Return ``(feedback_text, feedback_source)`` from a judge manifest.

    Used by both rejection routes (``revert_to_red`` and ``revert_before``)
    so they share the same feedback source cascade.
    """
    train_feedback_fb = (
        getattr(manifest, "train_feedback", None)
        or (manifest.model_extra or {}).get("train_feedback", "")
        or ""
    )
    rationale_fb = (
        getattr(manifest, "rationale", None)
        or (manifest.model_extra or {}).get("rationale", "")
        or ""
    )
    summary_fb = (
        getattr(manifest, "summary", None)
        or (manifest.model_extra or {}).get("summary", "")
        or ""
    )
    violations_fb = _format_violations_as_feedback(
        getattr(manifest, "violations", None)
        or (manifest.model_extra or {}).get("violations", [])
        or []
    )
    if train_feedback_fb:
        return train_feedback_fb, "train_feedback"
    if violations_fb:
        return violations_fb, "violations"
    if rationale_fb:
        return rationale_fb, "rationale"
    if summary_fb:
        return summary_fb, "summary"
    return "", ""


def _commit_judge_feedback_and_advance(
    root: Path,
    task: dict,
    feedback: str,
    feedback_source: str,
    c: Console,
    session: SessionState,
    session_path: Path,
) -> SessionState:
    """Persist judge feedback (tasks.md when available) and advance the
    RED boundary by committing a feedback-commit to git.

    The RED-boundary advance is unconditional even when ``tasks.md`` is
    unavailable: a rejection *must* move the boundary or the next GREEN
    attempt starts from the same baseline. The fix here decouples the
    commit from the tasks.md write.
    """
    tid = task.get("id", "?")
    feedback_preview = feedback.replace("\n", " ")[:200]

    # 1) Update tasks.md if available (operator-visible persistence).
    tasks_md = _resolve_tasks_md(root, task)
    if tasks_md is not None:
        added_lines = _append_judge_feedback(tasks_md, tid, feedback)
        if added_lines is None:
            c.print(
                f"  [yellow]TASKS_MD_NO_MATCH[/] {tid}: "
                f"no task line in {tasks_md} matches this id \u2014 "
                f"feedback NOT persisted to tasks.md"
            )
            _log_run(
                "TASKS_MD_NO_MATCH",
                task_id=tid,
                tasks_md=str(tasks_md),
                feedback=feedback,
            )
        else:
            plural = "s" if added_lines != 1 else ""
            c.print(
                f"  [cyan]TASKS_MD_FEEDBACK[/] {tid} \u2192 {tasks_md}: "
                f"{added_lines} feedback line{plural} appended"
            )
            c.print(f"    [dim]line: - **Judge Feedback**: {feedback_preview}[/]")
            _log_run(
                "TASKS_MD_FEEDBACK",
                task_id=tid,
                tasks_md=str(tasks_md),
                lines_added=added_lines,
                feedback=feedback,
            )
    else:
        c.print(f"  [dim]TASKS_MD_SKIP[/] {tid}: no tasks.md resolved for issue")
        _log_run("TASKS_MD_SKIP", task_id=tid, reason="no_tasks_md_resolved")

    # 2) Commit a feedback marker regardless of (1) so the RED boundary
    # advances. The commit message carries the feedback source for
    # post-mortem triage.
    subprocess.run(
        ["git", "add", "-A"],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )
    judge_msg = format_commit_message(
        f"docs({tid}): add judge feedback for retry",
        root,
    )
    try:
        commit_result = subprocess.run(
            ["git", "commit", "-m", judge_msg, "--allow-empty"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        message = (
            f"JUDGE feedback commit timed out for {tid} after "
            f"{JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS}s — pre-commit hook "
            f"chain exceeded the deadline. Inspect the active "
            f"repository's configured Git hooks "
            f"(core.hooksPath / .git/hooks/)."
        )
        c.print(
            f"  [red]FEEDBACK_COMMIT_TIMEOUT[/] {tid}: deadline "
            f"{JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS}s exceeded"
        )
        _log_run(
            "FEEDBACK_COMMIT_TIMEOUT",
            task_id=tid,
            feedback_source=feedback_source,
            timeout_seconds=JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS,
        )
        raise PhaseFailedError(message) from exc
    if commit_result.returncode != 0:
        message = (
            f"JUDGE feedback commit failed for {tid}: {commit_result.stderr.strip()}"
        )
        c.print(
            f"  [red]FEEDBACK_COMMIT_FAILED[/] {tid}: {commit_result.stderr.strip()}"
        )
        _log_run(
            "FEEDBACK_COMMIT_FAILED",
            task_id=tid,
            feedback_source=feedback_source,
            stderr=commit_result.stderr.strip(),
        )
        raise PhaseFailedError(message)
    fb_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    if fb_head:
        session.red_commit_sha = fb_head
        session.save(session_path)
    return session


def _run_judge_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    backend = agent or "pi"
    root = Path.cwd()

    # Span the RED→GREEN diff: use RED's parent as the baseline so the
    # judge sees both the failing tests (committed in RED) and the
    # implementation (committed in GREEN).  Without the parent anchor,
    # `git diff red_sha..HEAD` would collapse to GREEN only — the tests
    # already exist in `red_sha` and disappear from the diff — and the
    # judge would (correctly, given its input) flag the missing tests.
    # The fallback (no RED in this session) keeps the prior single-commit
    # behavior so the diff still matches the GREEN/EXECUTE-only commit.
    if session.red_commit_sha:
        diff_base = f"{session.red_commit_sha}^"
    else:
        diff_base = "HEAD~1"
    diff = subprocess.run(
        ["git", "diff", f"{diff_base}..HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout

    prompt = _build_auto_prompt("judge", task, root)
    prompt += f"\n\n<diff>\n{diff}\n</diff>\n"
    if session.train_feedback:
        prompt += f"\n\n<test_feedback>\n{session.train_feedback}\n</test_feedback>\n"
    if session.failure_kind == "mechanical":
        prompt += (
            "\n\n<failure_kind>mechanical</failure_kind>\n\n"
            "GREEN emitted `status: FAILURE` with a mechanical rationale — no "
            "production code was written. Do NOT attempt to satisfy the test "
            "yourself; review the rationale and emit `verdict: COMPLIANCE_VIOLATION` "
            "+ `next_action: revert_before` (the RED test is wrong — re-run RED) or "
            "`next_action: revert_to_red` (the slice/scope is wrong — re-run GREEN "
            "with the rationale as feedback) or `next_action: skip_refactor` "
            "(the operator should intervene at the meso layer, e.g. widen the "
            "slice scope).\n"
        )
    elif session.failure_kind == "test_defect":
        prompt += (
            "\n\n<failure_kind>test_defect</failure_kind>\n\n"
            "GREEN judged the RED test itself wrong (it asserts behavior the "
            "spec does not require, exercises the wrong abstraction, or "
            "encodes an assumption that contradicts spec/data-model). No "
            "production code was written. Do NOT attempt to satisfy the test "
            "yourself. Emit `verdict: COMPLIANCE_VIOLATION` + "
            "`next_action: revert_before` — the RED test must be re-authored. "
            "Populate `train_feedback` with the GREEN rationale so the next "
            "RED attempt has the full conflict description.\n"
        )

    agent_output_callback = _make_agent_output_callback(monitor, tid, "JUDGE")
    judge_model = resolve_model_for_phase("JUDGE", root)
    manifest, _ = _invoke_agent(
        prompt,
        c,
        backend_name=backend,
        task_id=tid,
        phase="JUDGE",
        output_callback=agent_output_callback,
        model=judge_model,
    )
    if manifest is None:
        raise PhaseFailedError(
            f"JUDGE phase agent error for {tid}: agent returned no manifest"
        )
    verdict = getattr(manifest, "verdict", "")
    action = _coerce_judge_action(manifest, verdict)

    # ---- Violation routes ----------------------------------------------
    if action in {"revert_to_red", "revert_before"}:
        # Both rejection routes resolve feedback through the same cascade
        # and emit the same user-visible rejection log + advance the RED
        # boundary via a feedback commit. They differ in WHERE the
        # rollback anchor sits (red_commit_sha vs red_commit_sha^) and
        # in WHICH phase the runner hands control to next.
        feedback, feedback_source = _judge_feedback_from_manifest(manifest)
        if not feedback:
            c.print(
                f"  [red]JUDGE_AGENT_NO_FEEDBACK[/] {tid}: judge returned "
                f"{action} but populated no rationale, train_feedback, "
                f"summary, or violations"
            )
            _log_run(
                "JUDGE_AGENT_NO_FEEDBACK",
                task_id=tid,
                verdict=verdict,
                action=action,
                manifest=manifest.model_dump_json(),
            )
            raise PhaseFailedError(
                f"JUDGE_AGENT_NO_FEEDBACK for {tid}: judge returned "
                f"{action} with no actionable feedback"
            )
        feedback_preview = feedback.replace("\n", " ")[:200]
        c.print(
            f"  [red]JUDGE_REJECTED[/] {tid} (action={action}, "
            f"source={feedback_source}): {feedback_preview}"
        )
        _log_run(
            "JUDGE_REJECTED",
            task_id=tid,
            action=action,
            feedback_source=feedback_source,
            feedback=feedback,
        )
        session.save(session_path)

        # Rollback to the anchor that the action names.
        try:
            if action == "revert_before":
                pre_red = (
                    _resolve_pre_red_sha(root, session.red_commit_sha)
                    if session.red_commit_sha
                    else ""
                )
                if pre_red:
                    subprocess.run(
                        ["git", "reset", "--hard", pre_red],
                        cwd=root,
                        capture_output=True,
                        env=_git_env(),
                    )
                    subprocess.run(
                        ["git", "clean", "-fd"],
                        cwd=root,
                        capture_output=True,
                        env=_git_env(),
                    )
                else:
                    # No pre-RED anchor known — fall back to the standard
                    # rollback-to-red_sha so the runner is never stuck.
                    _execute_rollback(root, feedback)
                # No boundary advance: pre-RED no longer has a RED
                # boundary in this task, so RED will land a fresh one.
                session.red_commit_sha = ""
                session.pending_judge_action = "revert_before"
                session.train_feedback = feedback
                session.judge_rejected = True
                session = session.force_transition_to("RED")
                _log_run(
                    "PHASE_DECISION",
                    task_id=tid,
                    phase="JUDGE",
                    decision="rejected",
                    reroute="RED",
                    action=action,
                )
                session.save(session_path)
                return session

            # revert_to_red: rollback to RED then advance the boundary.
            _execute_rollback(root, feedback)
        except Exception as e:
            c.print(
                f"  [yellow]ROLLBACK_FAILED[/] {e} \u2014 proceeding with "
                f"train feedback"
            )

        # Unconditional RED-boundary advance. The regressed behavior was
        # that this happened only when tasks.md existed; the fix decouples
        # the commit from the file write so the boundary always advances.
        session = _commit_judge_feedback_and_advance(
            root, task, feedback, feedback_source, c, session, session_path
        )
        session.pending_judge_action = "revert_to_red"
        session.train_feedback = feedback
        session.judge_rejected = True
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="JUDGE",
            decision="rejected",
            reroute="GREEN",
            action=action,
        )
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        return session

    # ---- Forward routes (verdict=COMPLIANCE_PASS, JUDGE decides the polish) -
    #
    # On a pass the runner honors the action:
    #   action=None              → legacy behavior: phase = JUDGE, hand to
    #                              _finish_tdd_cycle (which decides refactor)
    #   action=continue_refactor → pending_judge_action=continue_refactor;
    #                              _finish_tdd_cycle enters REFACTOR
    #                              regardless of no_refactor.
    #   action=skip_refactor     → phase = IDLE, mark COMPLETED, move on.
    refactor_note = (
        getattr(manifest, "train_feedback", None)
        or (manifest.model_extra or {}).get("train_feedback", "")
        or ""
    )
    if refactor_note.strip():
        note_preview = refactor_note.replace("\n", " ")[:200]
        c.print(f"  [cyan]JUDGE_REFACTOR_NOTE[/] {tid}: {note_preview}")
        _log_run(
            "JUDGE_REFACTOR_NOTE",
            task_id=tid,
            action=action or "",
            note=refactor_note,
        )

    if action == "continue_refactor":
        session.pending_judge_action = "continue_refactor"
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="JUDGE",
            decision="passed",
            reroute="REFACTOR",
            action=action,
        )
        session = session.force_transition_to("JUDGE")
        session.train_feedback = ""
        session.judge_rejected = False
        session.save(session_path)
        _append_status_transition(task, "JUDGE", ledger_path)
        return session

    if action == "skip_refactor":
        session.pending_judge_action = "skip_refactor"
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="JUDGE",
            decision="passed",
            reroute="NEXT",
            action=action,
        )
        session = session.force_transition_to("IDLE")
        session.train_feedback = ""
        session.judge_rejected = False
        session.save(session_path)
        try:
            _append_status_transition(task, "COMPLETED", ledger_path)
        except Exception as e:  # pragma: no cover - ledger robustness
            c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")
        return session

    # Legacy pass path: no action declared, hand to _finish_tdd_cycle.
    _log_run(
        "PHASE_DECISION",
        task_id=tid,
        phase="JUDGE",
        decision="passed",
        reroute="GREEN",
    )
    session = session.force_transition_to("JUDGE")
    session.train_feedback = ""
    session.judge_rejected = False
    session.save(session_path)
    _append_status_transition(task, "JUDGE", ledger_path)
    return session


def _run_refactor_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    if _phase_already_done(ledger_path, task.get("id", ""), "COMPLETED"):
        c.print(f"  [dim]Already completed for {_task_label(task)}, skipping[/]")
        _log_run(
            "PHASE_SKIP", task_id=tid, phase="REFACTOR", reason="already_completed"
        )
        return session
    _log_run("PHASE_START", task_id=tid, phase="REFACTOR")
    if _verbose:
        c.print(f"[bold cyan]REFACTOR →[/] {_task_label(task)}")
    _emit_phase_callout(c, "REFACTOR", task, PhaseMarker.IN_PROGRESS)
    if _verbose:
        c.print(f"  [bold green]REFACTOR →[/] {_task_label(task)}")

    backend = agent or "pi"
    root = Path.cwd()
    prompt = _build_auto_prompt("refactor", task, root)
    agent_output_callback = _make_agent_output_callback(monitor, tid, "REFACTOR")
    refactor_model = resolve_model_for_phase("REFACTOR", root)
    manifest, agent_tail = _invoke_agent(
        prompt,
        c,
        backend_name=backend,
        task_id=tid,
        phase="REFACTOR",
        output_callback=agent_output_callback,
        model=refactor_model,
    )
    if manifest is None:
        raise PhaseFailedError(
            f"REFACTOR phase agent error for {tid}: agent returned no manifest"
        )
    if manifest.status.upper() in ("FAILURE", "ERROR", "FAIL"):
        rationale = manifest.rationale or "unknown"
        tail = agent_tail or "(no agent output captured)"
        raise PhaseFailedError(
            f"REFACTOR phase failed for {tid}: {rationale}\n"
            f"  agent_output_tail (last 50 non-blank stdout lines):\n{tail}"
        )

    issue_id = task.get("issue_id", "")
    scope = _build_scope(issue_id, tid)

    _run_test_cmd(root)
    _run_format_cmd(root)

    try:
        record = TaskRecord.model_validate(task)
        record.status = "COMPLETED"
        append_task_transition(record, ledger_path)
    except Exception as e:
        raise PhaseFailedError(f"REFACTOR phase ledger update failed for {tid}: {e}")

    _commit_phase(
        f"refactor({scope}): REFACTOR phase - cleanup",
        root,
        no_verify=True,
        phase="refactor",
    )

    session = session.force_transition_to("IDLE")
    session.save(session_path)
    _verify_clean_worktree(root, "REFACTOR", tid)
    c.print(f"  [bold green]COMPLETED[/] {_task_label(task)}")
    return session


_PHASE_MAP: dict[str, Callable] = {
    "RED": _run_red_phase,
    "GREEN": _run_green_phase,
    "JUDGE": _run_judge_phase,
    "REFACTOR": _run_refactor_phase,
}


def _finish_tdd_cycle(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    no_refactor: bool,
    monitor: OrchestrationMonitor | None = None,
    agent: str | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    pending = session.pending_judge_action

    # JUDGE verdict-driven routing overrides the CLI's no_refactor flag:
    #   continue_refactor → enter REFACTOR regardless of no_refactor.
    #   skip_refactor     → mark COMPLETED and stop, regardless of
    #                       no_refactor (the CLI flag says nothing
    #                       about future tasks; the judge verdict does).
    if pending == "skip_refactor":
        try:
            _append_status_transition(task, "COMPLETED", ledger_path)
        except Exception as e:
            c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")
        c.print(f"  [bold green]COMPLETED[/] {_task_label(task)}")
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="CYCLE",
            decision="skip_refactor",
        )
        session.pending_judge_action = ""
        session = session.force_transition_to("IDLE")
        session.train_feedback = ""
        session.judge_rejected = False
        session.save(session_path)
        return session

    if pending == "continue_refactor" or not no_refactor:
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="CYCLE",
            decision="proceed_to_refactor",
            reason=pending or "no_refactor_flag_false",
        )
        _maybe_push_event(
            monitor,
            "phase_change",
            task_id=tid,
            phase="REFACTOR",
            description=task.get("description", ""),
        )
        session = _run_refactor_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )
        if pending:
            # Consume the pending action so subsequent cycles see clean state.
            session.pending_judge_action = ""
            session.save(session_path)
        return session

    # no_refactor (CLI flag) with no JUDGE override.
    try:
        _append_status_transition(task, "COMPLETED", ledger_path)
    except Exception as e:
        c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")
    c.print(f"  [bold green]COMPLETED[/] {_task_label(task)}")
    session = session.force_transition_to("IDLE")
    session.train_feedback = ""
    session.judge_rejected = False
    session.save(session_path)
    return session


def _run_tdd_cycle(
    task: dict,
    ledger_path: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
    start_phase: str | None = None,
) -> None:
    root = Path.cwd()
    tid = task.get("id", "?")
    if _phase_already_done(ledger_path, tid, "COMPLETED"):
        c.print(f"  [dim]Already completed for {_task_label(task)}, skipping[/]")
        return
    _verify_worktree_branch(root)
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    task_desc = task.get("description", "")

    if start_phase == "JUDGE":
        _maybe_push_event(
            monitor,
            "phase_change",
            task_id=tid,
            phase="JUDGE",
            description=task_desc,
        )
        session = _run_judge_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )

        session = _finish_tdd_cycle(
            task, ledger_path, session, session_path, c, no_refactor, agent=agent
        )
        return

    _maybe_push_event(
        monitor, "phase_change", task_id=tid, phase="RED", description=task_desc
    )
    session = _run_red_phase(
        task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
    )
    train_attempts = 0
    max_train_attempts = 3
    judge_passed = no_judge

    while not judge_passed:
        _maybe_push_event(
            monitor, "phase_change", task_id=tid, phase="GREEN", description=task_desc
        )
        session = _run_green_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )

        green_tests_failed = bool(
            session.train_feedback and session.current_phase == "GREEN"
        )

        if session.train_feedback:
            if session.current_phase == "RED":
                train_attempts += 1
                if train_attempts >= max_train_attempts:
                    c.print(
                        f"  [red]TRAIN_EXHAUSTED[/] {task.get('id', '?')} "
                        f"after {max_train_attempts} attempts"
                    )
                    raise PhaseFailedError(
                        f"GREEN phase post-cleanup failed for {task.get('id', '?')} "
                        f"after {max_train_attempts} train attempts"
                    )
                c.print(
                    TrainIndicator.render(
                        attempt=train_attempts,
                        maximum=max_train_attempts,
                        phase="GREEN",
                    )
                )
                c.print(
                    f"  [yellow]TRAIN ({train_attempts}/{max_train_attempts})"
                    f" \u2014 GREEN phase post-cleanup failed, retrying with feedback[/]"
                )
                _log_run(
                    "PHASE_DECISION",
                    task_id=tid,
                    phase="GREEN",
                    decision="reroute_to_green",
                    reason="post_cleanup_failed",
                    attempt=train_attempts,
                )
                continue
            _log_run(
                "PHASE_DECISION",
                task_id=tid,
                phase="GREEN",
                decision="tests_failed",
                reroute="JUDGE",
            )

        if no_judge:
            judge_passed = True
            break

        _maybe_push_event(
            monitor, "phase_change", task_id=tid, phase="JUDGE", description=task_desc
        )
        session = _run_judge_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )

        if session.judge_rejected or session.train_feedback or green_tests_failed:
            train_attempts += 1
            if train_attempts >= max_train_attempts:
                c.print(
                    f"  [red]TRAIN_EXHAUSTED[/] {task.get('id', '?')} "
                    f"after {max_train_attempts} attempts"
                )
                raise PhaseFailedError(
                    f"JUDGE phase rejected {task.get('id', '?')} "
                    f"after {max_train_attempts} train attempts"
                )
            if session.train_feedback:
                c.print(
                    TrainIndicator.render(
                        attempt=train_attempts,
                        maximum=max_train_attempts,
                        phase="GREEN",
                    )
                )
                c.print(
                    f"  [yellow]TRAIN ({train_attempts}/{max_train_attempts})"
                    f" \u2014 re-running GREEN with judge feedback[/]"
                )
            else:
                session.train_feedback = (
                    "GREEN implementation tests failed. "
                    "The implementation must be corrected to pass the test suite."
                )
                session = session.force_transition_to("GREEN")
                session.save(session_path)
                c.print(
                    TrainIndicator.render(
                        attempt=train_attempts,
                        maximum=max_train_attempts,
                        phase="GREEN",
                    )
                )
                c.print(
                    f"  [yellow]TRAIN ({train_attempts}/{max_train_attempts})"
                    f" \u2014 tests still failing, re-running GREEN with test feedback[/]"
                )
            session.judge_rejected = False
            session.save(session_path)
            _log_run(
                "PHASE_DECISION",
                task_id=tid,
                phase="JUDGE",
                decision="reroute_to_green",
                attempt=train_attempts,
            )
            continue
        else:
            judge_passed = True

    session = _finish_tdd_cycle(
        task,
        ledger_path,
        session,
        session_path,
        c,
        no_refactor,
        monitor=monitor,
        agent=agent,
    )


def _run_execute_phase(
    task: dict,
    ledger_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> None:
    tid = task.get("id", "?")
    _log_run("PHASE_START", task_id=tid, phase="EXECUTE")
    _emit_phase_callout(c, "EXECUTE", task, PhaseMarker.IN_PROGRESS)
    if _verbose:
        c.print(f"  [bold green]EXECUTE →[/] {_task_label(task)}")

    backend = agent or "pi"
    root = Path.cwd()

    spec_content = _resolve_spec_md(root, task)
    has_spec = bool(spec_content)
    train_feedback = ""
    max_judge_attempts = 3
    execute_model = resolve_model_for_phase("EXECUTE", root)

    session_path = root / ".deviate" / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    pre_execute_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    session.red_commit_sha = pre_execute_sha
    session.save(session_path)

    for attempt in range(max_judge_attempts):
        prompt = _build_auto_prompt("execute", task, root)
        if train_feedback:
            prompt += f"\n\n<train_feedback>\n{train_feedback}\n</train_feedback>\n"

        agent_output_callback = _make_agent_output_callback(monitor, tid, "EXECUTE")
        manifest, agent_tail = _invoke_agent(
            prompt,
            c,
            backend_name=backend,
            task_id=tid,
            phase="EXECUTE",
            output_callback=agent_output_callback,
            model=execute_model,
        )
        if manifest is None:
            raise PhaseFailedError(
                f"EXECUTE phase agent error for {tid}: agent returned no manifest"
            )
        if manifest.status.upper() in ("FAILURE", "ERROR", "FAIL"):
            rationale = manifest.rationale or "unknown"
            tail = agent_tail or "(no agent output captured)"
            raise PhaseFailedError(
                f"EXECUTE phase failed for {tid}: {rationale}\n"
                f"  agent_output_tail (last 50 non-blank stdout lines):\n{tail}"
            )

        issue_id = task.get("issue_id", "")
        scope = _build_scope(issue_id, tid)

        _commit_phase(f"feat({scope}): EXECUTE phase - {tid}", root)

        _verify_clean_worktree(root, "EXECUTE", tid)

        if not has_spec:
            break

        diff = subprocess.run(
            ["git", "diff", f"{pre_execute_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        if not diff.strip():
            c.print(f"  [dim]JUDGE_SKIP \u2014 no diff in commit for {tid}[/]")
            break
        _log_run("PHASE_START", task_id=tid, phase="JUDGE")
        _emit_phase_callout(c, "JUDGE", task, PhaseMarker.IN_PROGRESS)

        if _verbose:
            c.print(f"  [bold magenta]JUDGE →[/] {_task_label(task)} (spec compliance)")
        judge_prompt = _build_auto_prompt("judge", task, root)
        judge_prompt += f"\n\n<diff>\n{diff}\n</diff>\n"

        judge_model = resolve_model_for_phase("JUDGE", root)
        judge_manifest, _ = _invoke_agent(
            judge_prompt,
            c,
            backend_name=backend,
            task_id=tid,
            phase="JUDGE",
            model=judge_model,
        )

        if judge_manifest is None:
            raise PhaseFailedError(
                f"JUDGE phase agent error for {tid}: agent returned no manifest"
            )

        verdict = getattr(judge_manifest, "verdict", "")
        judge_action = _coerce_judge_action(judge_manifest, verdict)

        # EXECUTE has no RED boundary — pre_execute_sha is the only
        # anchor, so the four-action routing collapses: any of the two
        # rollback actions maps to the same rollback-to-pre_execute_sha
        # flow. Forward routes (None / continue_refactor / skip_refactor)
        # fall through to the pass branch.
        is_rollback_route = judge_action in {"revert_before", "revert_to_red"} or (
            verdict.upper() == "COMPLIANCE_VIOLATION"
            and judge_action not in {"continue_refactor", "skip_refactor"}
        )
        if is_rollback_route:
            feedback, feedback_source = _judge_feedback_from_manifest(judge_manifest)
            if not feedback:
                c.print(
                    f"  [red]JUDGE_AGENT_NO_FEEDBACK[/] {tid}: judge returned "
                    f"{judge_action} but populated no rationale, "
                    f"train_feedback, summary, or violations"
                )
                _log_run(
                    "JUDGE_AGENT_NO_FEEDBACK",
                    task_id=tid,
                    verdict=verdict,
                    action=judge_action,
                    manifest=judge_manifest.model_dump_json(),
                )
                raise PhaseFailedError(
                    f"JUDGE_AGENT_NO_FEEDBACK for {tid}: judge returned "
                    f"{judge_action} with no actionable feedback"
                )
            feedback_preview = feedback.replace("\n", " ")[:200]
            c.print(
                f"  [red]JUDGE_REJECTED[/] {tid} (action={judge_action}, "
                f"source={feedback_source}): {feedback_preview}"
            )
            _log_run(
                "JUDGE_REJECTED",
                task_id=tid,
                action=judge_action,
                feedback_source=feedback_source,
                feedback=feedback,
            )
            try:
                _execute_rollback(root, feedback)
            except Exception as e:
                c.print(
                    f"  [yellow]ROLLBACK_FAILED[/] {e} \u2014 proceeding with retry"
                )
            session = _commit_judge_feedback_and_advance(
                root, task, feedback, feedback_source, c, session, session_path
            )
            if attempt < max_judge_attempts - 1:
                train_feedback = feedback
                c.print(
                    f"  [yellow]RETRY EXECUTE ({attempt + 2}/{max_judge_attempts})[/]"
                )
                _log_run(
                    "PHASE_DECISION",
                    task_id=tid,
                    phase="JUDGE",
                    decision="rejected",
                    reroute="EXECUTE",
                    action=judge_action,
                )
                continue
            _log_run(
                "PHASE_DECISION",
                task_id=tid,
                phase="JUDGE",
                decision="rejected",
                reroute="EXECUTE",
                action=judge_action,
                terminal=True,
            )
            raise PhaseFailedError(
                f"EXECUTE phase failed for {tid} "
                f"after {max_judge_attempts} JUDGE attempts: {feedback}"
            )

        # Pass branch: forward routes (no action, continue_refactor,
        # skip_refactor). EXECUTE has no REFACTOR; advance out of the loop.
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="JUDGE",
            decision="passed",
            reroute="COMPLETE",
            action=judge_action or "",
        )
        break

    c.print(f"  [bold green]COMPLETED[/] {_task_label(task)}")
    try:
        record = TaskRecord.model_validate(task)
        record.status = "COMPLETED"
        append_task_transition(record, ledger_path)
    except Exception as e:
        c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")


class PhaseFailedError(Exception):
    pass


class HitlEscalationError(PhaseFailedError):
    """Raised when an agent manifest carries structured HITL escalation.

    Agents that detect a structural impossibility (spec contradiction,
    toolchain contract mismatch, missing prerequisite owned by a
    different slice) populate ``status: ERROR`` together with one of
    ``contract_drift``, ``escalates_to``, or ``hitl_options``. Retrying
    them burns stall budget on a deterministic non-answer — surface
    them as HITL instead.

    Subclasses ``PhaseFailedError`` so existing catch sites still match;
    the retry loop distinguishes via ``isinstance``.
    """

    pass


_HITL_ESCALATION_KEYS = frozenset({"contract_drift", "escalates_to", "hitl_options"})


def _is_hitl_escalation(manifest) -> bool:
    """True when the manifest signals a structured HITL escalation."""
    if manifest is None:
        return False
    if manifest.status.upper() not in ("FAILURE", "ERROR", "FAIL"):
        return False
    extra = getattr(manifest, "model_extra", None) or {}
    return any(key in extra for key in _HITL_ESCALATION_KEYS)


def _render_hitl_banner(manifest, c: Console, tid: str, phase: str) -> None:
    """Print a clean HITL banner so the operator sees the escalation."""
    extra = getattr(manifest, "model_extra", None) or {}
    drift = extra.get("contract_drift")
    options = extra.get("hitl_options") or {}
    escalates_to = extra.get("escalates_to")
    recommended = options.get("recommended") if isinstance(options, dict) else None
    reason = extra.get("reason")
    summary = extra.get("summary")
    if summary is None and isinstance(drift, dict):
        summary = drift.get("symptom")
    from rich.panel import Panel as _Panel
    from rich.text import Text as _Text

    body = _Text()
    body.append(f"phase: {phase}", style="bold")
    body.append("\n")
    body.append(f"task_id: {tid}\n")
    if reason:
        body.append(f"reason: {reason}\n")
    if summary:
        body.append(f"summary: {summary}\n")
    if escalates_to:
        body.append(f"escalates_to: {escalates_to}\n")
    if recommended:
        body.append(f"recommended: {recommended}", style="bold green")
    c.print(_Panel(body, border_style="yellow", title="HITL_REQUIRED"))


class RedPhaseError(Exception):
    pass


def _dispatch_task(
    task: dict,
    ledger_path: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
    batch_mode: bool = False,
    monitor: OrchestrationMonitor | None = None,
    start_phase: str | None = None,
) -> None:
    mode = task.get("execution_mode", "TDD")

    if mode == "TDD" and batch_mode:
        description = task.get("description", "")
        if "Failing task" in description:
            raise RedPhaseError(
                f"Task {task.get('id', '?')} failed on RED phase: {description}"
            )

    if mode == "TDD":
        _run_tdd_cycle(
            task,
            ledger_path,
            c,
            no_judge=no_judge,
            no_refactor=no_refactor,
            agent=agent,
            monitor=monitor,
            start_phase=start_phase,
        )
    else:
        _run_execute_phase(task, ledger_path, c, agent=agent, monitor=monitor)


def _run_single(
    task_id: str,
    root: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
) -> None:
    result = _resolve_task_context(task_id, root)
    task, ledger_file = result
    status = task.get("status", "PENDING")

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )

    if session.current_phase == "IDLE" and status in (
        "COMPLETED",
        "REFACTOR",
        "JUDGE",
        "YELLOW",
    ):
        c.print(f"[yellow]TASK_ALREADY_DONE[/] {task_id} is already completed")
        raise typer.Exit(code=0)

    start_phase = (
        session.current_phase if session.current_phase not in ("IDLE", "RED") else None
    )

    _dispatch_task(
        task,
        ledger_file,
        c,
        no_judge=no_judge,
        no_refactor=no_refactor,
        agent=agent,
        batch_mode=False,
        start_phase=start_phase,
    )


def _execute_task_with_retry(
    task: dict,
    ledger_file: Path,
    c: Console,
    monitor: OrchestrationMonitor,
    root: Path,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
) -> bool:
    tid = task.get("id", "?")
    issue_id = task.get("issue_id", "")
    mode = task.get("execution_mode", "TDD")
    task_logger: TaskLogger | None = None
    if issue_id and tid != "?":
        try:
            task_logger = TaskLogger(root, issue_id=issue_id, task_id=tid)
        except ValueError:
            # Defensive: never let logging break dispatch.
            task_logger = None
    if task_logger is not None:
        set_task_logger(task_logger)
    try:
        for attempt in range(2):
            _log_run(
                "TASK_DISPATCH",
                task_id=tid,
                mode=mode,
                description=task.get("description", ""),
            )
            monitor.push_event(
                "task_started", task_id=tid, description=task.get("description", "")
            )
            try:
                _dispatch_task(
                    task,
                    ledger_file,
                    c,
                    no_judge=no_judge,
                    no_refactor=no_refactor,
                    agent=agent,
                    batch_mode=True,
                    monitor=monitor,
                )
                _log_run("TASK_COMPLETE", task_id=tid, attempt=attempt + 1)
                monitor.push_event(
                    "task_completed",
                    task_id=tid,
                    phase=monitor.get_task_phase(tid),
                    status="completed",
                )
                return True
            except HitlEscalationError as exc:
                # Structured HITL escalation — deterministic non-answer.
                # Don't retry; mark HITL_PENDING and halt the chain.
                c.print(f"  [yellow]HITL_PENDING[/] {tid}: {exc}")
                _log_run(
                    "TASK_HITL_PENDING",
                    task_id=tid,
                    error=str(exc),
                )
                monitor.push_event(
                    "task_hitl_pending",
                    task_id=tid,
                    error_reason=str(exc),
                )
                _append_status_transition(task, "HITL_PENDING", ledger_file)
                return False
            except Exception as exc:
                if attempt == 1:
                    c.print(f"  [red]FAILED[/] {tid} after 2 attempts: {exc}")
                    _log_run("TASK_FAILED", task_id=tid, error=str(exc))
                    monitor.push_event(
                        "task_failed", task_id=tid, error_reason=str(exc)
                    )
                    _append_status_transition(task, "FAILED", ledger_file)
                    return False
                c.print(f"  [yellow]RETRY[/] {tid} (attempt {attempt + 2})")
                _log_run("TASK_RETRY", task_id=tid, attempt=attempt + 2)
    finally:
        if task_logger is not None:
            set_task_logger(None)
            task_logger.close()


def _run_all(
    root: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
    json_mode: bool = False,
) -> None:
    if agent is None:
        agent = _resolve_agent_config(root, None)
    _run_all_start = time.monotonic()
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    issue_id = session.active_issue_id
    if not issue_id:
        issue_id = _resolve_issue_id_from_branch(root) or issue_id

    pending = _find_all_pending_tasks(root, issue_id=issue_id)
    if not pending:
        msg = "No PENDING tasks found"
        if issue_id:
            msg += f" for issue {issue_id}"
        c.print(f"[yellow]{msg}[/]")
        raise typer.Exit(code=0)

    # Issue-scoped run header: shows issue context and pending task count.
    from rich.panel import Panel as _Panel
    from rich.text import Text as _Text

    _hdr = _Text()
    _hdr.append("RUN", style="bold blue")
    _hdr.append("  ")
    _hdr.append(issue_id or "(no issue)", style="bold")
    _hdr.append("  ")
    _hdr.append(f"{len(pending)} pending task(s)", style="dim")
    c.print(_Panel(_hdr, border_style="blue", padding=(0, 1)))

    _log_run(
        "RUN_ALL_START",
        issue_id=issue_id or "(none)",
        pending_count=len(pending),
        skip_judge=no_judge,
        skip_refactor=no_refactor,
    )

    _board = RunBoard(
        pending=[t for t, _ in pending],
        title=f"Run --all [{issue_id or '?'}]",
    )
    monitor = OrchestrationMonitor(
        c,
        json_mode=json_mode,
        total_tasks=len(pending),
        verbose=_verbose,
        board=_board,
    )

    graphite = resolve_graphite_config(root)

    any_failed = False
    try:
        with monitor:
            for idx, (task, ledger_file) in enumerate(pending):
                if not _execute_task_with_retry(
                    task,
                    ledger_file,
                    c,
                    monitor,
                    root,
                    no_judge=no_judge,
                    no_refactor=no_refactor,
                    agent=agent,
                ):
                    any_failed = True
                    c.print(
                        "[red]Pipeline halted: task failure breaks dependency chain[/]"
                    )
                    monitor.push_event(
                        "pipeline_halted",
                        task_id=task.get("id", "?"),
                    )
                    break

                if graphite and idx < len(pending) - 1:
                    next_task = pending[idx + 1][0]
                    next_id = next_task.get("id", "?")
                    next_desc = next_task.get("description", "")
                    msg = f"feat({next_id}): {next_desc}"
                    try:
                        subprocess.run(
                            ["gt", "create", "-m", msg],
                            capture_output=True,
                            text=True,
                            cwd=root,
                            env=_git_env(),
                            check=True,
                        )
                        c.print(f"  [dim]gt create → stacked branch for {next_id}[/]")
                    except subprocess.CalledProcessError as e:
                        c.print(f"  [yellow]GT_CREATE_WARN[/] {e.stderr.strip()}")
                    except FileNotFoundError:
                        c.print("  [yellow]GT_CREATE_WARN[/] gt not found on PATH")
    except KeyboardInterrupt:
        monitor.signal_keyboard_interrupt()
        raise typer.Exit(code=130)

    total = len(pending)
    pipeline_status = (
        "interrupted"
        if monitor.interrupted
        else ("halted" if any_failed else "completed")
    )
    _log_run(
        "RUN_ALL_END",
        total=total,
        failed=monitor.failed_count,
        status=pipeline_status,
    )
    monitor.push_event(
        "pipeline_complete",
        total=total,
        failed=monitor.failed_count,
        status=pipeline_status,
    )

    # Final RunBoard snapshot — board is updated by the monitor event stream.
    c.print(_board.render())

    # Closing summary panel — total/completed/failed/duration/status.
    c.print(
        PipelineSummary.render(
            total=total,
            completed=monitor.completed_count,
            failed=monitor.failed_count,
            duration_seconds=time.monotonic() - _run_all_start,
            pipeline_status=pipeline_status,
        )
    )

    if any_failed:
        raise typer.Exit(code=1)


def _find_test_files(root: Path) -> list[Path]:
    return sorted(root.glob("tests/**/test_*.py"))


def _find_source_files(root: Path) -> list[Path]:
    return sorted(root.glob("src/**/*.py"))


def _is_pytest_json_report_available() -> bool:
    try:
        import pytest_json_report  # noqa: F401

        return True
    except ImportError:
        warnings.warn(
            "pytest-json-report plugin not installed; falling back to string parsing",
            stacklevel=2,
        )
        return False


def _run_pytest(
    root: Path,
    report_config: PytestReportConfig | None = None,
) -> subprocess.CompletedProcess:
    """Invoke pytest as a subprocess against the project test files.

    Tests that exercise CLI commands which internally call this function
    (e.g. red/green/refactor `_post` commands) MUST mock
    `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess`
    fixture. Otherwise each test invocation triggers the entire pytest
    suite (~5s), blowing the <18s full-suite performance target.
    """
    test_files = _find_test_files(root)
    test_file_list = [str(f) for f in test_files]
    cmd = [sys.executable, "-m", "pytest", *test_file_list, "-v"]

    if report_config is not None and report_config.json_report:
        if _is_pytest_json_report_available():
            cmd.append("--json-report")

    return subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
    )


def _commit_phase(
    message: str,
    root: Path,
    no_verify: bool = False,
    phase: str | None = None,
) -> bool:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root, env=_git_env()
    )
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, env=_git_env())
    untracked = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    has_untracked = bool(untracked.stdout.strip())
    if staged.returncode != 0 or unstaged.returncode != 0 or has_untracked:
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)
        message = format_commit_message(message, root, phase=phase)
        cmd = ["git", "commit", "-m", message]
        if no_verify:
            cmd.append("--no-verify")
        result = subprocess.run(
            cmd,
            cwd=root,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print("[red]COMMIT_FAILED[/]")
            if result.stderr.strip():
                console.print(result.stderr.strip(), style="red")
            return False
        console.print(f"  [green]Committed[/] [dim]{message}[/]")
        return True
    return False


def _verify_clean_worktree(root: Path, phase: str, tid: str) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if status.stdout.strip():
        files = status.stdout.strip().splitlines()
        _log_run(
            "POST_CMD_FAILURE",
            phase=phase,
            task_id=tid,
            uncommitted_count=len(files),
            files="\n".join(files),
        )
        raise PhaseFailedError(
            f"{phase} phase agent for {tid} did not commit all files \u2014 "
            f"{len(files)} uncommitted file(s) remain after post-command"
        )


def _verify_worktree_branch(root: Path) -> None:
    try:
        idx = root.parts.index(".worktrees")
    except ValueError:
        return

    expected = "/".join(root.parts[idx + 1 :])
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()

    if current != expected:
        console.print(
            f"  [red]BRANCH_MISMATCH[/] worktree expects"
            f" [bold]{expected}[/]"
            f" but HEAD is on [bold]{current}[/]"
        )
        console.print(f"  Run: git checkout {expected}")
        raise typer.Exit(code=78)


def _all_tasks_complete(root: Path) -> bool:
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("status") not in ("COMPLETED", "REFACTOR"):
                return False
    return True


def _load_governance_context(root: Path) -> str:
    parts: list[str] = []
    constitution_path = root / "specs" / "constitution.md"
    if constitution_path.exists():
        parts.append(constitution_path.read_text(encoding="utf-8"))
    claudemd_path = root / "CLAUDE.md"
    if claudemd_path.exists():
        parts.append(claudemd_path.read_text(encoding="utf-8"))
    if not parts:
        return ""
    return "\n\n".join(parts)


def _validate_manifest(manifest_path: str | None) -> dict | None:
    if manifest_path is None:
        return None
    path = Path(manifest_path)
    if not path.exists():
        console.print(f"[red]MANIFEST_NOT_FOUND[/] {manifest_path}")
        raise typer.Exit(code=1)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        console.print(f"[red]MANIFEST_INVALID_JSON[/] {manifest_path}")
        raise typer.Exit(code=1)
    if not isinstance(data, dict):
        console.print("[red]MANIFEST_NOT_DICT[/] Manifest must be a JSON object")
        raise typer.Exit(code=1)
    return data


@red_app.command(name="pre")
def red_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, ledger_path = _resolve_task_context(task, root)

    spec_dir = str(ledger_path.parent)
    test_commands = _test_command_candidates(root, task_data)

    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": test_commands[0][0] if test_commands else "",
        "lint_command": "mise run lint",
        "spec_dir": spec_dir,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


def _normalise_test_command(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().strip("`").strip()


def _task_verification_command(root: Path, task: dict | None) -> str:
    if task:
        command = _normalise_test_command(task.get("verification"))
        if command:
            return command
        task_id = task.get("id", "")
        issue_id = task.get("issue_id", "")
        tasks_md = _find_tasks_md_for_issue(root, issue_id) if issue_id else None
        if tasks_md is not None and task_id:
            capture = False
            for line in tasks_md.read_text(encoding="utf-8").splitlines():
                if _TASK_LINE_RE.match(line) and task_id in line:
                    capture = True
                elif capture and _TASK_LINE_RE.match(line):
                    break
                if capture:
                    match = re.match(
                        r"^\s*-\s+\*{0,2}Verification\*{0,2}:\s*(.+)$",
                        line,
                    )
                    if match:
                        return _normalise_test_command(match.group(1))
    return ""


def _constitution_test_command(root: Path) -> str:
    path = root / "specs" / "constitution.md"
    if not path.exists():
        return ""
    from deviate.core.constitution import extract_commands

    commands = extract_commands(path)
    return _normalise_test_command(
        commands.get("test_command") or commands.get("python_test_command")
    )


def _mise_has_test_task(root: Path) -> bool:
    import tomllib

    path = root / "mise.toml"
    if not path.exists():
        return False
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tasks = config.get("tasks")
    return isinstance(tasks, dict) and "test" in tasks


_IGNORED_TEST_DISCOVERY_DIRS = frozenset(
    {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}
)
_MANIFEST_TEST_COMMANDS = {
    "pyproject.toml": "pytest",
    "mix.exs": "mix test",
    "package.json": "npm test",
    "Cargo.toml": "cargo test",
    "go.mod": "go test ./...",
}


def _manifest_test_commands(root: Path) -> list[tuple[str, Path]]:
    commands: list[tuple[str, Path]] = []
    for name, command in _MANIFEST_TEST_COMMANDS.items():
        for manifest in sorted(root.rglob(name)):
            if any(part in _IGNORED_TEST_DISCOVERY_DIRS for part in manifest.parts):
                continue
            commands.append((command, manifest.parent))
    return sorted(commands, key=lambda item: str(item[1]))


def _test_command_candidates(
    root: Path, task: dict | None = None
) -> list[tuple[str, Path]]:
    task_command = _task_verification_command(root, task)
    if task_command:
        return [(task_command, root)]
    constitution_command = _constitution_test_command(root)
    if constitution_command in {
        "true",
        "echo 'No test framework'",
        'echo "No test framework"',
    }:
        constitution_command = ""
    if _mise_has_test_task(root):
        candidates = [("mise run test", root)]
        if constitution_command:
            candidates.append((constitution_command, root))
        return candidates
    if constitution_command:
        return [(constitution_command, root)]
    manifests = _manifest_test_commands(root)
    if manifests:
        return manifests
    if _find_test_files(root):
        return [("pytest", root)]
    return []


def _execute_test_command(command: str, cwd: Path) -> subprocess.CompletedProcess:
    args = (
        ["mise", "run", "test"] if command == "mise run test" else ["sh", "-c", command]
    )
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def _mise_test_invocation_failed(proc: subprocess.CompletedProcess) -> bool:
    """Return whether mise itself could not resolve the ``test`` task."""
    stderr = (proc.stderr or "").lower()
    return proc.returncode != 0 and any(
        marker in stderr
        for marker in ("unknown command", "unknown task", "task not found")
    )


def _run_test_cmd(root: Path, task: dict | None = None) -> subprocess.CompletedProcess:
    """Run configured tests via ``sh -c`` to preserve shell syntax.

    Constitution commands may contain pipes, redirects, expansions, or quoted whitespace.
    """
    candidates = _test_command_candidates(root, task)
    if not candidates:
        return subprocess.CompletedProcess(
            ["deviate", "test"],
            127,
            "",
            "No test command configured and no test project detected",
        )
    if candidates[0][0] == "mise run test":
        first = _execute_test_command(*candidates[0])
        if first.returncode == 0 or not _mise_test_invocation_failed(first):
            return first
        candidates = candidates[1:]
        if not candidates:
            return first
    results = [_execute_test_command(command, cwd) for command, cwd in candidates]
    if len(results) == 1:
        return results[0]
    return subprocess.CompletedProcess(
        results[0].args,
        next((r.returncode for r in results if r.returncode != 0), 0),
        "\n".join(r.stdout or "" for r in results),
        "\n".join(r.stderr or "" for r in results),
    )


def _run_format_cmd(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["mise", "run", "format"],
        cwd=root,
        capture_output=True,
        text=True,
    )


_SOURCE_TRACK_PREFIXES: tuple[str, ...] = ("src/", "lib/", "app/")


def _changed_source_paths(root: Path) -> list[str]:
    """Return repo-relative paths of production-code changes since HEAD.

    Captures three categories of working-tree activity:

    - Staged modifications/additions (``git diff --name-only --cached``)
    - Unstaged modifications against tracked files (``git diff --name-only``)
    - Untracked, non-ignored files (``git ls-files --others --exclude-standard``)

    The result is filtered to the conventional production-code roots
    (``src/``, ``lib/``, ``app/``); test files, spec files, and config
    are intentionally excluded. Used by the GREEN/REFACTOR/EXECUTE phase
    guards to catch a stub ``status: PASS`` manifest emitted by an
    agent that didn't actually write any production code.
    """
    paths: set[str] = set()
    for args in (
        ("diff", "--name-only", "--cached"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        if result.returncode != 0 or not result.stdout:
            continue
        paths.update(
            line.strip() for line in result.stdout.splitlines() if line.strip()
        )
    return sorted(
        path
        for path in paths
        if any(path.startswith(p) for p in _SOURCE_TRACK_PREFIXES)
    )


@red_app.command(name="post")
def red_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[red]TEST_NOT_FOUND[/]")
        raise typer.Exit(code=1)

    proc = _run_test_cmd(root)

    if proc.returncode == 0:
        console.print("[red]RedMustPassError:[/] Test passed, expected a failing test")
        raise typer.Exit(code=1)

    fmt = _run_format_cmd(root)
    if fmt.returncode != 0:
        console.print(f"[yellow]Format stderr:[/] {fmt.stderr.strip()}")
        if fmt.stdout.strip():
            console.print(f"[yellow]Format stdout:[/] {fmt.stdout.strip()}")

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )

    issue_id = session.active_issue_id or ""
    pending = _resolve_first_pending(root, issue_id)
    if pending is None:
        console.print("[red]NO_PENDING_TASKS[/] No PENDING task found for active issue")
        raise typer.Exit(code=1)

    pending_record, ledger_path = pending
    task_uuid = pending_record.get("id", "")

    try:
        record = TaskRecord.model_validate(pending_record)
        record.status = "RED"  # type: ignore[assignment]
        append_task_transition(record, ledger_path)
    except Exception as e:
        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
        raise typer.Exit(code=1)

    session = session.force_transition_to("RED")
    session.save(session_path)
    scope = _build_scope(issue_id, task_uuid)
    _commit_phase(
        f"test({scope}): RED phase - failing test",
        root,
        no_verify=True,
        phase="red",
    )

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    session.red_commit_sha = head_sha
    session.save(session_path)

    console.print("[green]RED_POST_OK[/]")
    raise typer.Exit(code=0)


@green_app.command(name="pre")
def green_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, ledger_path = _resolve_task_context(task, root)

    test_files = _find_test_files(root)
    src_files = _find_source_files(root)

    task_id = task_data.get("id", "")
    task_entry = ""
    tasks_md = _find_tasks_md_for_issue(root, task_data.get("issue_id", ""))
    if tasks_md is not None:
        content = tasks_md.read_text(encoding="utf-8")
        lines = content.splitlines()
        capture = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") and task_id in stripped:
                capture = True
            elif capture and re.match(r"- (?:\[.\]\s+)?TSK-\d{3}-\d{2}:", stripped):
                break
            if capture:
                task_entry += line + "\n"

    contract = {
        "task_id": task_id,
        "task_entry": task_entry.strip(),
        "test_file": str(test_files[0]) if test_files else "",
        "implementation_targets": [str(f) for f in src_files],
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@green_app.command(name="post")
def green_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[red]TEST_NOT_FOUND[/]")
        raise typer.Exit(code=1)

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )

    issue_id = session.active_issue_id or ""

    # Verify the specific task has a RED entry (RED phase completed)
    red_task = _resolve_latest_task(root, issue_id, "RED")
    if red_task is None:
        console.print(
            "[red]MISSING_RED_PHASE[/] No RED transition found — RED phase must complete before GREEN"
        )
        raise typer.Exit(code=1)

    task_uuid = red_task[0].get("id", "")

    # Append GREEN transition for this specific task
    try:
        record = TaskRecord.model_validate(red_task[0])
        record.status = "GREEN"  # type: ignore[assignment]
        append_task_transition(record, red_task[1])
    except Exception as e:
        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
        raise typer.Exit(code=1)

    session = session.force_transition_to("GREEN")
    session.save(session_path)

    scope = _build_scope(issue_id, task_uuid)
    status_check = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if not status_check.stdout.strip():
        console.print("[green]GREEN_POST_OK[/]")
        raise typer.Exit(code=0)

    committed = _commit_phase(
        f"feat({scope}): GREEN phase - implementation passes tests", root
    )

    if committed:
        console.print("[green]GREEN_POST_OK[/]")
    else:
        console.print("[red]COMMIT_FAILED[/]")

    raise typer.Exit(code=0 if committed else 1)


# ---------------------------------------------------------------------------
# YELLOW commands
# ---------------------------------------------------------------------------


def _detect_phase_changes(root: Path) -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    files: list[str] = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        filename = line[3:]
        files.append(filename)

    expanded: list[str] = []
    for f in files:
        if f.endswith("/"):
            full_dir = root / f
            if full_dir.is_dir():
                for py_file in sorted(full_dir.rglob("*.py")):
                    rel = py_file.relative_to(root)
                    expanded.append(str(rel))
            else:
                expanded.append(f)
        else:
            expanded.append(f)
    return expanded


# ---------------------------------------------------------------------------
# JUDGE commands
# ---------------------------------------------------------------------------


def _find_protected_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for spec_file in sorted(root.glob("specs/**/issues/*.md")):
        content = spec_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("Module:"):
                module_path = stripped[len("Module:") :].strip()
                modules.append(module_path)
    return modules


@judge_app.command(name="pre")
def judge_pre() -> None:
    root = Path.cwd()

    if not _load_skill_content("JUDGE"):
        console.print("[yellow]SKILL_NOT_FOUND[/] deviate-judge")

    changed = _detect_phase_changes(root)

    protected = _find_protected_modules(root)
    violations: list[dict[str, str]] = []
    for changed_file in changed:
        for protected_path in protected:
            changed_normalized = changed_file.rstrip("/")
            if changed_normalized == protected_path:
                violations.append(
                    {
                        "file": changed_file,
                        "protected_module": protected_path,
                    }
                )
            elif protected_path.startswith(changed_normalized + "/"):
                violations.append(
                    {
                        "file": changed_file,
                        "protected_module": protected_path,
                    }
                )

    verdict = {
        "verdict": "COMPLIANCE_VIOLATION" if violations else "COMPLIANCE_PASS",
        "details": violations,
    }
    print(json.dumps(verdict, ensure_ascii=False))
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# REFACTOR commands
# ---------------------------------------------------------------------------


_NON_DETERMINISTIC = re.compile(
    r"(0x[0-9a-fA-F]+|id='\d+'|pytest-\d+/|\[?[a-f0-9]{7}\])"
)


def _normalize_pytest_output(output: str) -> str:
    lines: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("==="):
            continue
        if "collected " in stripped and "item" in stripped:
            continue
        if stripped.startswith(".") and stripped.endswith("%]"):
            continue
        normalized = _NON_DETERMINISTIC.sub("", stripped)
        lines.append(normalized)
    return "\n".join(lines)


@refactor_app.command(name="pre")
def refactor_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    _resolve_task_context(task, root)

    src_files = [str(f) for f in _find_source_files(root)]

    contract = {"files_to_refactor": src_files}
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


def _check_python_return_types(filepath: str) -> list[str]:
    """Check Python return type annotations against literal return values using tree-sitter."""
    issues: list[str] = []

    tree = incremental_parse(filepath, None)
    if tree is None:
        return issues

    scalar_types = {
        "str": "string",
        "int": "integer",
        "float": "float",
        "bool": "boolean",
    }
    collection_types = {
        "list": "list",
        "dict": "dictionary",
        "tuple": "tuple",
        "set": "set",
    }
    all_known = set(scalar_types) | set(collection_types)

    def _get_return_type_name(func_node: object) -> str | None:
        for child in func_node.children:
            if child.type == "type":
                nodes = [child]
                while nodes:
                    curr = nodes.pop(0)
                    if curr.type == "identifier":
                        return curr.text.decode("utf-8", errors="replace")
                    if curr.type == "string":
                        return curr.text.decode("utf-8", errors="replace").strip("'\"")
                    nodes.extend(curr.children)
                break
        return None

    def _check_return_value(return_node: object, expected: str) -> list[str]:
        result: list[str] = []
        for rc in return_node.children:
            if rc.type in ("return", ","):
                continue
            if rc.type in scalar_types.values():
                if expected in scalar_types and rc.type != scalar_types[expected]:
                    result.append(f"expected {expected}, got literal {rc.type}")
            elif rc.type in collection_types.values():
                for cname, ctype in collection_types.items():
                    if rc.type == ctype and expected != cname:
                        result.append(f"expected {expected}, got {cname} literal")
                        break
            elif rc.type in ("true", "false"):
                if expected != "bool":
                    result.append(f"expected {expected}, got literal bool")
            break
        return result

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type != "function_definition":
            for child in node.children:
                stack.append(child)
            continue

        ret_type = _get_return_type_name(node)
        if ret_type is None or ret_type not in all_known:
            for child in node.children:
                stack.append(child)
            continue

        # Walk the function body for return statements
        body = None
        for child in node.children:
            if child.type == "block":
                body = child
                break
        if body is not None:
            bs = [body]
            while bs:
                bn = bs.pop()
                if bn.type == "return_statement":
                    issues.extend(_check_return_value(bn, ret_type))
                elif bn.type in ("function_definition", "class_definition"):
                    continue
                for child in bn.children:
                    bs.append(child)

        for child in node.children:
            stack.append(child)

    return issues


def _check_return_type_mismatch(filepath: str) -> list[str]:
    """Check return type mismatches and structural issues using tree-sitter.

    For Python files, checks return type annotations against literal return values.
    For all supported languages, detects dead code, duplicate blocks, and high cyclomatic complexity.
    """
    issues: list[str] = []

    lang_id = get_language_id(filepath)
    if lang_id is None:
        return issues

    # Python-specific: return type annotation check
    if lang_id == "python":
        issues.extend(_check_python_return_types(filepath))

    dead = extract_dead_code(filepath)
    dupes = detect_duplicate_blocks(filepath, min_lines=5)

    for block in dupes:
        locs = ", ".join(block.locations)
        issues.append(f"Duplicate block ({block.lines} lines) at {locs}")

    tree = incremental_parse(filepath, None)
    if tree is not None:
        has_calls = False
        func_types = {
            "function_definition",
            "function_declaration",
            "function_item",
            "method_definition",
            "method_declaration",
        }
        fstack = [tree.root_node]
        while fstack:
            node = fstack.pop()
            if not has_calls and node.type in ("call", "call_expression"):
                has_calls = True
            if node.type in func_types:
                name = "unknown"
                for child in node.children:
                    if child.type in ("identifier", "property_identifier", "name"):
                        name = child.text.decode("utf-8", errors="replace")
                        break
                complexity = estimate_cyclomatic_complexity(filepath, node)
                if complexity >= 10:
                    issues.append(
                        f"Complexity warning: '{name}' has cyclomatic complexity {complexity} (threshold: 10)"
                    )
            for child in node.children:
                fstack.append(child)

        if has_calls and dead:
            for name in dead:
                issues.append(f"Dead code: '{name}' is defined but never used")

    return issues


@refactor_app.command(name="post")
def refactor_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[yellow]NO_TESTS_TO_CHECK[/]")
        raise typer.Exit(code=0)

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )

    issue_id = session.active_issue_id or ""

    # Verify the specific task has a GREEN entry (GREEN phase completed)
    green_task = _resolve_latest_task(root, issue_id, "GREEN")
    if green_task is None:
        console.print(
            "[red]MISSING_GREEN_PHASE[/] No GREEN transition found — GREEN phase must complete before REFACTOR"
        )
        raise typer.Exit(code=1)

    task_uuid = green_task[0].get("id", "")

    try:
        record = TaskRecord.model_validate(green_task[0])
        record.status = "COMPLETED"  # type: ignore[assignment]
        append_task_transition(record, green_task[1])
    except Exception as e:
        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
        raise typer.Exit(code=1)

    session = session.force_transition_to("IDLE")
    session.save(session_path)

    scope = _build_scope(issue_id, task_uuid)

    proc_before = _run_pytest(root)
    before_returncode = proc_before.returncode
    before_output = _normalize_pytest_output(proc_before.stdout)

    changed = _detect_phase_changes(root)
    for changed_file in changed:
        full_path = root / changed_file
        if full_path.suffix == ".py" and full_path.exists():
            type_issues = _check_return_type_mismatch(str(full_path))
            if type_issues:
                subprocess.run(
                    ["git", "restore", "."], cwd=root, env=_git_env(), check=False
                )
                console.print(
                    "[red]RefactorRegressionError:[/] " + "; ".join(type_issues)
                )
                raise typer.Exit(code=1)

    proc_after = _run_pytest(root)
    after_returncode = proc_after.returncode
    after_output = _normalize_pytest_output(proc_after.stdout)

    if after_returncode != before_returncode or after_output != before_output:
        subprocess.run(["git", "restore", "."], cwd=root, env=_git_env(), check=False)
        console.print(
            "[red]RefactorRegressionError:[/] Test regression detected after refactor"
        )
        raise typer.Exit(code=1)

    committed = _commit_phase(
        f"refactor({scope}): REFACTOR phase \u2014 code cleanup", root
    )

    if committed:
        console.print("[green]REFACTOR_POST_OK[/]")

        task_record = green_task[0]
        _append_status_transition(task_record, "COMPLETED", green_task[1])
        console.print(f"  [bold green]COMPLETED[/] {task_uuid}")

        session = session.force_transition_to("IDLE")
        session.save(session_path)
    else:
        console.print("[yellow]NOTHING_CHANGED[/]")

    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# EXECUTE commands (DIRECT mode — bypasses RED/GREEN/REFACTOR)
# ---------------------------------------------------------------------------
# RED-phase stubs — minimum structure so CLI commands are routable;
# tests fail because the real contract emission, validation, and ledger
# updates are not yet implemented (GREEN phase).


@execute_app.command(name="pre")
def execute_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, _ = _resolve_task_context(task, root)

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    session = session.force_transition_to("EXECUTE")
    session.active_issue_id = task_data.get("issue_id")
    session.save(session_path)

    contract = {
        "task_id": task_data.get("id", ""),
        "completion_criteria": "Direct execution task \u2014 bypasses RED/GREEN/REFACTOR",
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@execute_app.command(name="post")
def execute_post(
    task_id: str | None = typer.Argument(
        None, help="Task ID (auto-discovered from session if empty)"
    ),
    subject: str = typer.Argument(
        "", help="Commit subject (auto-generated from task ID if empty)"
    ),
    body: str | None = typer.Argument(None, help="Optional commit body"),
) -> None:
    root = Path.cwd()

    if task_id:
        result = _find_task_record(root, task_id)
    else:
        result = _resolve_task_context(None, root)

    if result is not None:
        task_record, ledger_path = result
        resolved_task_id = task_record.get("id", task_id or "?")
        _append_status_transition(task_record, "COMPLETED", ledger_path)
    else:
        resolved_task_id = task_id or "?"

    if not subject:
        subject = f"feat({resolved_task_id}): execute result"

    message = subject
    if body:
        message += "\n\n" + body

    _commit_phase(message, root)
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# E2E commands (end-to-end verification after all tasks complete)
# ---------------------------------------------------------------------------


@e2e_app.command(name="pre")
def e2e_pre() -> None:
    root = Path.cwd()

    if not _all_tasks_complete(root):
        console.print("[red]INCOMPLETE_TASKS[/] Some tasks not completed")
        raise typer.Exit(code=1)

    test_paths = [str(p) for p in _find_test_files(root)]
    contract = {"test_paths": test_paths}
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@e2e_app.command(name="post")
def e2e_post(
    manifest: str | None = typer.Argument(None, help="Path to manifest file"),
) -> None:
    root = Path.cwd()
    manifest_data = _validate_manifest(manifest)
    subject = (
        manifest_data.get("commit_subject", "feat: E2E phase")
        if manifest_data
        else "feat: E2E phase"
    )
    _commit_phase(subject, root)
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# HOTFIX commands (bug fixes — bypasses RED phase)
# ---------------------------------------------------------------------------


@hotfix_app.command(name="pre")
def hotfix_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, _ = _resolve_task_context(task, root)

    contract = {
        "issue_context": task_data.get("description", ""),
        "bypasses_red": True,
        "completion_criteria": "Bug fix \u2014 bypasses RED phase",
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@hotfix_app.command(name="post")
def hotfix_post(
    manifest: str | None = typer.Argument(None, help="Path to manifest file"),
) -> None:
    root = Path.cwd()
    manifest_data = _validate_manifest(manifest)
    subject = (
        manifest_data.get("commit_subject", "feat: HOTFIX phase")
        if manifest_data
        else "feat: HOTFIX phase"
    )
    _commit_phase(subject, root)
    raise typer.Exit(code=0)


def _resolve_agent_config(root: Path, agent: str | None) -> str | None:
    """Resolve agent backend from CLI arg or config.toml fallback.

    User-facing aliases (``factory`` for the Factory Droid IDE, ``omp``
    for Oh-My-Pi) are normalised to their canonical backend via
    :func:`deviate.core.agent.resolve_agent_to_backend` so the returned
    value is always a valid :class:`~deviate.state.config.AgentConfig`
    ``backend`` Literal. The ``run`` dispatch layer therefore never sees
    a raw alias — it only sees canonical backend identifiers.
    """
    if agent is not None:
        return resolve_agent_to_backend(agent)
    config_path = root / ".deviate" / "config.toml"
    if not config_path.exists():
        return None
    try:
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        backend = data.get("agent", {}).get("backend")
        if not isinstance(backend, str) or not backend:
            return None
        return resolve_agent_to_backend(backend)
    except Exception:
        return None


def _validate_profile(value: str) -> str:
    """Typer callback: validate profile via resolve_profile, emit Typer error."""
    try:
        resolve_profile(value)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    return value


@micro_app.command("run")
def run_command(
    task_id: str | None = typer.Argument(
        None, help="Task ID (TNNN or TSK-NNN-NN format)"
    ),
    all_tasks: bool = typer.Option(False, "--all", help="Run all PENDING tasks"),
    profile: str = typer.Option(
        "full",
        "--profile",
        callback=_validate_profile,
        help="Execution profile: full, fast, secure",
    ),
    no_judge: bool | None = typer.Option(None, "--no-judge", help="Skip JUDGE phase"),
    no_refactor: bool | None = typer.Option(
        None, "--no-refactor", help="Skip REFACTOR phase"
    ),
    agent: str | None = typer.Option(None, "--agent", help="Override agent backend"),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSONL output"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print resolved task and exit"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print debug diagnostics"),
) -> None:
    """Use `deviate micro run --all` to drain the queue.

    Runs the next pending task by default. Routes each task by
    execution_mode to the TDD cycle (red → green → judge → refactor)
    or the execute phase.

    Invoked directly via ``deviate micro run [task-id]`` and indirectly
    by the top-level ``deviate run`` orchestrator after ``meso run``
    creates the per-issue worktree.
    """
    global _verbose
    _verbose = verbose

    root = _resolve_workspace_root()
    session_path = root / ".deviate" / "session.json"

    _log(f"workspace root: {root}")
    _log(f"session path: {session_path}")

    agent = _resolve_agent_config(root, agent)

    if session_path.exists():
        session = SessionState.load(session_path)
        _log(f"session: phase={session.current_phase}, issue={session.active_issue_id}")
        cmd_parts = ["micro", "run"]
        if task_id:
            cmd_parts.append(task_id)
        if all_tasks:
            cmd_parts.append("--all")
        session = SessionState(
            current_phase=session.current_phase,
            active_issue_id=session.active_issue_id,
            last_command=" ".join(cmd_parts),
        )
        session.save(session_path)

    if dry_run:
        _log("dry-run mode — resolving tasks without execution")
        if all_tasks:
            pending = _find_all_pending_tasks(root)
            if not pending:
                console.print("[yellow]NO_PENDING_TASKS[/]")
            for rec, path in pending:
                console.print(
                    f"  {rec.get('id')}: {rec.get('status')} "
                    f"— {rec.get('description', '')[:60]}"
                )
        else:
            try:
                result = _resolve_task_context(task_id, root)
                task, path = result
                console.print(
                    f"  {task.get('id')}: {task.get('status')} "
                    f"— {task.get('description', '')[:60]}"
                )
                console.print(f"  ledger: {path}")
            except typer.Exit:
                if _verbose:
                    console.print("[yellow]No task resolved[/]")
        raise typer.Exit(code=0)

    skip_judge, skip_refactor = resolve_profile(profile, no_judge, no_refactor)

    run_logger = RunLogger(root)
    _log_run(
        "RUN_START",
        command=f"deviate micro run {task_id or ''} {'--all' if all_tasks else ''}".strip(),
    )
    set_run_logger(run_logger)

    try:
        if all_tasks:
            _run_all(
                root,
                console,
                no_judge=skip_judge,
                no_refactor=skip_refactor,
                agent=agent,
                json_mode=json_mode,
            )
            raise typer.Exit(code=0)

        _run_single(
            task_id,
            root,
            console,
            no_judge=skip_judge,
            no_refactor=skip_refactor,
            agent=agent,
        )
    finally:
        run_logger.close()
        set_run_logger(None)
