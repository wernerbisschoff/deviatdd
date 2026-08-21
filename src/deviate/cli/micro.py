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
from typing import NoReturn
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
from deviate.core.issues import resolve_issue_artifact_path
from deviate.core.profile import resolve_profile
from deviate.core.run_logger import (
    RunLogger,
    TaskLogger,
    log_event,
    set_run_logger,
    set_task_logger,
)
from deviate.core.worktree import find_worktree_for_branch
from deviate.prompts.assembly import assemble_prompt
from deviate.state.config import (
    AgentConfig,
    PytestReportConfig,
    SessionState,
    _load_deviate_config_toml,
    resolve_graphite_config,
    resolve_phase_model,
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

from deviate.cli._safe_commands import (
    is_safe_test_command,
    run_safe_command,
)
from deviate.state.ledger import (
    RollbackSnapshot,
    TaskRecord,
    append_rollback_snapshot,
    append_task_transition,
)

console = Console()
_verbose: bool = False

_cli_model_override: str | None = None


def resolve_model_for_phase(
    phase: str, root: Path, *, backend: str | None = None
) -> str | None:
    """Resolve model for *phase* with CLI override priority.

    Priority (highest first):
        1. Phase-specific config key (e.g. ``[models].red``)
        2. CLI ``--model`` flag (``_cli_model_override``)
        3. Default config key (``[models].default``)
        4. ``None`` — backend uses its native default

    JUDGE phase is excluded from CLI override to preserve model tiering
    (V4 Pro for JUDGE). Phase-specific and default config still apply.

    *backend* is accepted for backward compatibility with prior callers
    but is no longer consulted: model resolution is config-only so the
    same ``[models]`` block applies regardless of which agent CLI is
    spawned. Operators select models at the agent layer via their own
    env vars (e.g. ``PI_MODEL``) instead of having deviate forward one.

    Exposed as a module-level symbol so micro-layer tests can
    ``unittest.mock.patch`` it to bypass config + CLI resolution for
    hermetic unit tests.
    """
    data = _load_deviate_config_toml(root)
    models: dict[str, str] = {}
    if data:
        m = data.get("models", {})
        if isinstance(m, dict):
            models = {k.lower(): str(v) for k, v in m.items() if v}
    if phase.lower() in models:
        return models[phase.lower()]
    allowed = frozenset({"RED", "GREEN", "REFACTOR", "EXECUTE"})
    if _cli_model_override and phase.upper() in allowed:
        return _cli_model_override
    return resolve_phase_model(phase, models)


_YAML_FENCE_OPEN_RE = re.compile(r"^```+\s*yaml", re.IGNORECASE)
_YAML_FENCE_CLOSE_RE = re.compile(r"^```+\s*$")
_MANIFEST_HEADER_RE = re.compile(r"^##\s*\[(?:HANDOVER_MANIFEST|MINIMAL_HANDOVER)\]")
_DEVIATE_MICRO_HEADER_RE = re.compile(r"^# DeviaTDD Micro")
_HANDOVER_XML_RE = re.compile(r"^</?handover_manifest>\s*$")
_AGENT_PHASE_STATUS_RE = re.compile(
    r"^Status:\s+(?:GREEN_STATE_ACHIEVED|TEST_WRITTEN_FAILING|TASK_COMPLETE)"
    r"(?:\s+\([^)]*\))?\s*$",
    re.IGNORECASE,
)

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


# Per-agent slash command that invokes the deviatdd skill. ``deviate setup``
# provisions the skill at every platform's project-local skills directory
# (``.claude/skills/deviatdd/``, ``.pi/skills/deviatdd/``, ``.omp/skills/deviatdd/``,
# etc.). Sending the literal slash command as the prompt makes the agent
# resolve and execute the skill on the operator's behalf — no manual TUI
# invocation needed. Claude Code names the slash command after the skill
# itself; Pi / OMP use the ``/skills:`` prefix that matches their slash-
# command parser. The runner stays agent-agnostic by consulting this map.
_DEVIATDD_SLASH_COMMAND: dict[str, str] = {
    "claude": "/deviatdd",
    "pi": "/skills:deviatdd",
    "omp": "/skills:deviatdd",
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
                if _AGENT_PHASE_STATUS_RE.match(stripped):
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
    stall_timeout: int | None = None,
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
            prompt,
            output_callback=collecting_handler,
            model=model,
            stall_timeout=stall_timeout,
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
    """Git subprocess env: strip inherited ``GIT_*`` overrides and pin the
    locale so CLI output parsing stays stable regardless of the operator's
    system locale (e.g. the "nothing to commit" detection in
    ``_commit_phase_with_recovery`` relies on git's untranslated message)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["LC_ALL"] = "C"
    return env


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
    """Look up the latest (current) record by its TSK-NNN-NN ID.

    A task ID is namespaced per issue (every issue reuses the same
    ``TSK-NNN-NN`` numbering). When several issues carry the same id,
    prefer the record that belongs to this worktree's branch issue so an
    explicit ``deviate micro run <tid>`` targets the active slice rather than
    a same-numbered task from an unrelated ledger.
    """
    branch_issue_id = _resolve_issue_id_from_branch(root) or ""
    preferred = None
    for rec, ledger_file in _collect_latest_task_records(root):
        if rec.get("id") == task_id:
            if rec.get("issue_id") == branch_issue_id:
                return rec, ledger_file
            if preferred is None:
                preferred = (rec, ledger_file)
    return preferred


_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "REFACTOR"}


def _collect_latest_task_records(root: Path) -> list[tuple[dict, Path]]:
    """Return the latest record per (issue_id, task ID) across all ledger files.

    Because the ledger is append-only (chronological within each file,
    files sorted lexicographically), the last seen record for each task
    within one issue represents its current status.

    Task IDs are namespaced per issue (every issue reuses the same
    ``TSK-NNN-NN`` numbering), so the dedup key must include the issue id.
    Keying by task ID alone lets a later-sorted ledger from an unrelated
    issue shadow this issue's records (e.g. ``specs/adhoc/*`` sorting after
    ``specs/005-*``).
    """
    latest: dict[tuple[str, str], dict] = {}
    ledger_of: dict[tuple[str, str], Path] = {}
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for rec in _read_ledger_records(ledger_file):
            tid = rec.get("id")
            issue_id = rec.get("issue_id", "")
            if tid:
                key = (issue_id, tid)
                latest[key] = rec
                ledger_of[key] = ledger_file
    return [(latest[key], ledger_of[key]) for key in latest]


_BRANCH_SLUG_RE = re.compile(r"^feat/([^/]+)/([^/]+(?:/[^/]+)*)$")
_TASK_LINE_RE = re.compile(r"^\s*-\s+(?:\[(x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.*)")
_MODE_LINE_RE = re.compile(r"^\s*-\s+\*\*Mode\*\*:\s*(\S+)")
_TASK_BULLET_HEAD_RE = re.compile(r"^- (?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):")
_JUDGE_FEEDBACK_BULLET_RE = re.compile(r"^  - \*\*Judge Feedback\*\*:\s*(.*)")

# GH-53: DIRECT EXECUTE phases run deterministic long pipelines (clean-checkout
# ``mise run check``, cargo release builds) that can emit nothing for >15 min.
# The interactive 900s stall budget would kill a healthy run, so the EXECUTE
# agent invocation gets a one-hour stall allowance; the hard ``timeout`` still
# bounds the overall run.
EXECUTE_STALL_TIMEOUT_SECONDS = 3600


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
    tasks_md = resolve_issue_artifact_path(root, source_file, "tasks.md")
    if tasks_md is not None and tasks_md.exists():
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


def _git_branch(root: Path) -> str:
    """Return the current branch name, or "" when not a git repo."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def _resolve_issue_id_from_branch(root: Path) -> str | None:
    """Derive issue_id from the current git branch via issues.jsonl."""
    branch = _git_branch(root)
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

    issue_id = session.active_issue_id
    branch_issue_id = _resolve_issue_id_from_branch(root)
    if issue_id and branch_issue_id and branch_issue_id != issue_id:
        # Stale-session guard (GH-54): a freshly claimed worktree can carry
        # the *previous* issue's id in session.json while its branch points
        # at the new issue. When the session issue has no tasks board in
        # this checkout, the branch is authoritative — re-key so the scan
        # does not silently emit NO_PENDING_TASKS for a queue that exists.
        if _find_tasks_md_for_issue(root, issue_id) is None:
            _log(
                f"stale session issue {issue_id}: no tasks board in this "
                f"checkout; re-keying to branch issue {branch_issue_id}"
            )
            issue_id = branch_issue_id
    elif not issue_id:
        # Session has no active issue (fresh checkout / no session.json).
        # Fall back to the branch slug so the scan stays scoped to the
        # issue the feature branch belongs to. Without this, an unscoped
        # scan returns the first unchecked task in any tasks.md repo-wide
        # (e.g. a stale slice task from an unrelated issue).
        issue_id = branch_issue_id or issue_id

    pending = _find_all_pending_tasks(root, issue_id=issue_id)
    if not pending:
        console.print("[yellow]NO_PENDING_TASKS[/]")
        # Empty queue is a graceful no-op, not an error. The trainer's
        # empty-queue contract (deviatdd skill table) documents exit 0.
        raise typer.Exit(code=0)
    return pending[0]


def _start_phase_from_status(status: str) -> str | None:
    """Return the phase where a task's run resumes, from its latest JSONL status.

    The tracked ``specs/**/tasks.jsonl`` is authoritative for
    RED/GREEN/REFACTOR progress; ``session.json`` is an untracked cache that
    a ``git reset`` does not roll back. ``None`` means start the full RED
    cycle. Terminal statuses also fall through to ``None`` — their internal
    ``_phase_already_done`` guards skip re-work."""
    return {
        "RED": "GREEN",
        "GREEN": "JUDGE",
        "JUDGE": "JUDGE",
    }.get(status)


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


def _build_auto_prompt(
    phase: str,
    task: dict,
    root: Path,
    *,
    train_feedback: str = "",
) -> str:
    """Build a prompt from auto templates with context injected.

    ``train_feedback`` fills the ``{train_feedback}`` placeholder.
    Escalate paths pass a short note from ``_inject_escalate_note``;
    GREEN-train paths pass the standing GREEN dump. Empty on first RED.
    """
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
        "train_feedback": train_feedback,
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


_NO_FAILING_TEST_FORWARD_ROUTES = frozenset(
    {"continue_refactor", "proceed_to_refactor_no_diff", "skip_refactor"}
)


def _worktree_status_paths(root: Path) -> list[str]:
    """Return ``git status --porcelain`` lines for *root*."""
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    return proc.stdout.splitlines()


def _restore_worktree_to_baseline(root: Path, baseline: list[str]) -> None:
    """Discard worktree changes that appeared after *baseline* was captured.

    Used by the RED no-failing-test adjudication to remove the files the RED
    agent produced (an uncommitted passing test) without touching anything
    that was already present when the phase started."""
    baseline_set = set(baseline)
    for line in _worktree_status_paths(root):
        if line in baseline_set:
            continue
        entry = line[3:].strip().strip('"').rstrip("/")
        if not entry:
            continue
        if line.startswith("??"):
            subprocess.run(
                ["git", "clean", "-fd", "--", entry],
                cwd=root,
                capture_output=True,
                text=True,
                env=_git_env(),
            )
        else:
            subprocess.run(
                ["git", "restore", "--", entry],
                cwd=root,
                capture_output=True,
                text=True,
                env=_git_env(),
            )


def _is_no_tests_collected(proc: subprocess.CompletedProcess) -> bool:
    """Return whether a pytest-style exit 5 means 'no test ran'."""
    if proc.returncode != 5:
        return False
    output = f"{proc.stdout or ''} {proc.stderr or ''}".lower()
    return "no tests" in output


def _is_no_test_command(proc: subprocess.CompletedProcess) -> bool:
    """Return whether the test command could not be resolved.

    ``_run_test_cmd`` returns ``returncode == 127`` with a fixed
    diagnostic when no command configures and no project is detected,
    so the RED phase can route that to the same JUDGE adjudication as
    a pytest ``exit 5`` (``_is_no_tests_collected``)."""
    if proc.returncode != 127:
        return False
    return "no test command" in f"{proc.stderr or ''}".lower()


def _run_red_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
    *,
    bypass_phase_done: bool = False,
    no_judge: bool = False,
) -> SessionState:
    tid = task.get("id", "?")
    if not bypass_phase_done and _phase_already_done(
        ledger_path, task.get("id", ""), "RED"
    ):
        c.print(f"  [dim]RED already done for {_task_label(task)}, skipping[/]")
        return session
    # A rollback boundary belongs to the active task.  Clear any boundary
    # retained by a completed prior task before the RED agent can fail; this
    # phase records its own boundary only after the RED commit lands.
    session.red_commit_sha = ""
    session.save(session_path)
    _log_run("PHASE_START", task_id=tid, phase="RED")
    _emit_phase_callout(c, "RED", task, PhaseMarker.IN_PROGRESS)
    if _verbose:
        c.print(f"  [bold blue]RED →[/] {_task_label(task)}")

    backend = agent or "pi"
    root = Path.cwd()
    red_baseline = _worktree_status_paths(root)
    prompt = _build_auto_prompt(
        "red", task, root, train_feedback=session.train_feedback
    )
    agent_output_callback = _make_agent_output_callback(monitor, tid, "RED")
    red_model = resolve_model_for_phase("RED", root, backend=backend)
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

    test_result = _run_test_cmd(root)
    if (
        test_result.returncode == 0
        or _is_no_tests_collected(test_result)
        or _is_no_test_command(test_result)
    ):
        return _adjudicate_red_no_failing_test(
            task,
            ledger_path,
            session,
            session_path,
            c,
            agent=agent,
            monitor=monitor,
            manifest=manifest,
            test_result=test_result,
            red_baseline=red_baseline,
            no_judge=no_judge,
        )

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


def _adjudicate_red_no_failing_test(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    *,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
    manifest: HandoverManifest,
    test_result: subprocess.CompletedProcess,
    red_baseline: list[str],
    no_judge: bool = False,
) -> SessionState:
    """Adjudicate a RED phase that produced no failing test.

    The test command either exited 0 (all tests passed) or collected no
    tests, so there is nothing for GREEN to implement. The decision goes to
    JUDGE directly — a vacuous GREEN would only burn the TRAIN budget:
    JUDGE either rules the behavior already exists (``skip_refactor`` — the
    task is COMPLETED without landing the agent's passing test) or rules
    the test wrong (``revert_before`` — the agent's work is discarded and
    RED re-authors a genuinely failing test)."""
    tid = task.get("id", "?")
    root = Path.cwd()
    rationale = (manifest.rationale or "").strip()
    declared = manifest.failure_kind
    if test_result.returncode == 0:
        symptom = "the test command exited 0 (all tests passed)"
    else:
        symptom = "the test command collected no tests"
    feedback = rationale or (
        f"RED phase: {symptom}. The authored test is uncommitted in the "
        "working tree. Decide whether the required behavior already exists "
        "(adjudicate the task COMPLETED) or the test is wrong (re-author a "
        "genuinely failing test in RED)."
    )
    session.train_feedback = feedback
    session.failure_kind = "no_failing_test"
    session.save(session_path)

    c.print(
        f"  [yellow]RED_NO_FAILING_TEST[/] {tid} \u2014 "
        "routing to JUDGE for adjudication"
    )
    _log_run(
        "RED_NO_FAILING_TEST",
        task_id=tid,
        returncode=test_result.returncode,
        declared_kind=declared or "",
        rationale_preview=feedback.replace("\n", " ")[:200],
        reroute="JUDGE",
    )

    if no_judge:
        raise PhaseFailedError(
            f"RED phase produced no failing test for {tid} and --no-judge "
            "disables the adjudication — RED must author a failing test. "
            "Re-run without --no-judge, or route the task through "
            "/deviate-execute if no test is expected."
        )

    session = _run_judge_phase(
        task,
        ledger_path,
        session,
        session_path,
        c,
        agent=agent,
        monitor=monitor,
        red_baseline=red_baseline,
    )
    action = session.pending_judge_action

    if action == "revert_before":
        _log_run(
            "PHASE_DECISION",
            task_id=tid,
            phase="JUDGE",
            decision="rejected",
            reroute="RED",
            action=action,
            reason="no_failing_test_test_defect",
        )
        return session

    # A bare COMPLIANCE_PASS verdict (legacy judge path) also signals that
    # the required behavior already exists.
    if not action and session.last_judge_verdict == "COMPLIANCE_PASS":
        action = "skip_refactor"
        session.pending_judge_action = "skip_refactor"

    if action in _NO_FAILING_TEST_FORWARD_ROUTES:
        _restore_worktree_to_baseline(root, red_baseline)
        if action != "skip_refactor":
            session.pending_judge_action = "skip_refactor"
        c.print(
            f"  [green]COMPLETED (adjudicated)[/] {tid} \u2014 "
            "behavior already exists, no implementation needed"
        )
        _log_run(
            "RED_ADJUDICATED_COMPLETE",
            task_id=tid,
            action=action,
            rationale_preview=feedback.replace("\n", " ")[:200],
        )
        session.train_feedback = ""
        session.failure_kind = ""
        session.judge_rejected = False
        session.save(session_path)
        return session

    # JUDGE returned no actionable verdict — strict RED contract applies.
    _restore_worktree_to_baseline(root, red_baseline)
    raise PhaseFailedError(
        f"RED phase produced no failing test for {tid} and JUDGE returned no "
        f"routing decision (action={action!r}). The RED agent must author a "
        "failing test; declare `failure_kind: test_defect` in the RED "
        "manifest if the test cannot target the required behavior."
    )


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
    green_already_done = _phase_already_done(ledger_path, task.get("id", ""), "GREEN")
    is_feedback_retry = green_already_done and bool(session.train_feedback)
    if green_already_done:
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
    if session.judge_rejected and session.pending_judge_action == "revert_to_red":
        prompt += (
            "\n\n<rollback_context>\n"
            "JUDGE rollback discarded the prior GREEN implementation, including "
            "uncommitted and untracked files. Treat this as a clean-slate GREEN "
            "attempt: verify every referenced artifact exists on disk and recreate "
            "anything missing before reporting success.\n"
            "</rollback_context>\n"
        )
    if session.train_feedback:
        prompt += f"\n\n<train_feedback>\n{session.train_feedback}\n</train_feedback>\n"
    else:
        persisted = _read_judge_feedback_from_tasks_md(root, task)
        if persisted:
            prompt += f"\n\n<persisted_judge_feedback>\n{persisted}\n</persisted_judge_feedback>\n"
    agent_output_callback = _make_agent_output_callback(monitor, tid, "GREEN")
    green_model = resolve_model_for_phase("GREEN", root, backend=backend)
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

    committed = _commit_phase(
        f"feat({scope}): GREEN phase - implementation",
        root,
        no_verify=True,
        phase="green",
    )
    if is_feedback_retry and not committed:
        raise PhaseFailedError(
            f"GREEN_STATE_DRIFT {tid}: ledger already records GREEN and JUDGE "
            "requested changes, but the retry produced no implementation commit. "
            "Verify the existing implementation and reconcile the task ledger."
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
    """Combine macro intent with the authoritative meso acceptance contract."""
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return ""
    source_file = _resolve_issue_source_file(root, issue_id)
    if not source_file:
        return ""
    issue_path = root / source_file
    if not issue_path.exists():
        return ""
    plan_path = resolve_issue_artifact_path(root, source_file, "plan.md")
    if not plan_path.is_file():
        return issue_path.read_text(encoding="utf-8")
    return (
        "<macro_issue_intent>\n"
        f"{issue_path.read_text(encoding='utf-8')}\n"
        "</macro_issue_intent>\n\n"
        '<authoritative_acceptance_contract source="plan.md">\n'
        f"{plan_path.read_text(encoding='utf-8')}\n"
        "</authoritative_acceptance_contract>"
    )


def _resolve_tasks_md(root: Path, task: dict) -> Path | None:
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return None
    return _find_tasks_md_for_issue(root, issue_id)


_MAX_JUDGE_FEEDBACK = 3


def _append_judge_feedback(tasks_md: Path, task_id: str, feedback: str) -> int | None:
    """Store bounded, deduplicated feedback rounds under one task."""
    lines = tasks_md.read_text(encoding="utf-8").splitlines()
    target_index = next(
        (
            i
            for i, line in enumerate(lines)
            if task_id in line and line.startswith("- ")
        ),
        None,
    )
    if target_index is None:
        return None
    end = next(
        (
            i
            for i in range(target_index + 1, len(lines))
            if _TASK_BULLET_HEAD_RE.match(lines[i])
        ),
        len(lines),
    )
    history = [
        match.group(1).rstrip()
        for line in lines[target_index + 1 : end]
        if (match := _JUDGE_FEEDBACK_BULLET_RE.match(line))
    ]
    candidate = feedback.strip() or ""
    history = [item for item in history if item != candidate]
    history.append(candidate)
    history = history[-_MAX_JUDGE_FEEDBACK:]
    retained = [
        line
        for line in lines[target_index + 1 : end]
        if not _JUDGE_FEEDBACK_BULLET_RE.match(line)
    ]
    replacement = [f"  - **Judge Feedback**: {item}" for item in history]
    updated = lines[: target_index + 1] + retained + replacement + lines[end:]
    tasks_md.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return len(candidate.splitlines()) or 1
    return len(replacement)


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


# Defensive regex matching RED-phase task-id characters used by
# `_recovery_branch_for`. Git ref components disallow a few shell-hostile
# characters (``:``, spaces, ``~``, ``^``, ``?``, ``*``, ``[``, ASCII
# controls); the sanitiser maps anything outside `[A-Za-z0-9_./-]` to ``-``
# so a hostile task id can't escape the `tmp/deviate-agent-work/` prefix.
_RECOVERY_REF_SAFE_RE = re.compile(r"[^A-Za-z0-9_./-]")
_RECOVERY_REF_PREFIX = "tmp/deviate-agent-work"


def _recovery_branch_for(task_id: str, attempt: int) -> str:
    """Return the per-task, per-attempt recovery ref name.

    Format: ``tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>``.

    Each discarded commit lands on its own ref so a parent SIGTERM between
    ``git reset`` and ``git clean`` cannot overwrite an earlier attempt's
    recovery handle. The sanitiser collapses any character outside
    ``[A-Za-z0-9_./-]`` to ``-`` so unusual task ids (slashes, colons,
    whitespace) still produce a valid git ref. A missing task id falls
    back to ``"unknown"`` rather than producing an empty path segment.
    """
    raw = (task_id or "").strip() or "unknown"
    sanitized = _RECOVERY_REF_SAFE_RE.sub("-", raw)
    return f"{_RECOVERY_REF_PREFIX}/{sanitized}/attempt-{int(attempt)}"


def _execute_rollback(
    root: Path,
    *,
    boundary_sha: str,
    reason: str,
    phase: str = "JUDGE",
    task_id: str,
    attempt: int,
) -> str:
    """Reset HEAD and clean untracked state back to ``boundary_sha``.

    F3 (commit-before-judge rollback safety): the agent's pre-reset HEAD
    is captured on a per-task, per-attempt recovery ref
    (``tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>``) BEFORE
    any destructive reset so a parent SIGTERM landing between ``git
    reset`` and ``git clean`` doesn't strand the agent's commit. Older
    snapshots stay reachable at their distinct refs — a single global
    ref would let the most recent rollback overwrite earlier attempts
    that the operator may still need to inspect.

    ``boundary_sha`` is REQUIRED and must be explicitly supplied by the
    caller. There is no implicit fallback to ``SessionState.red_commit_sha``
    or ``HEAD~1`` — both have masked real boundary-loss bugs (a completed
    task's stale boundary leaking into the next RED attempt; a partially
    committed GREEN losing commit content when ``HEAD~1`` resolves to the
    wrong parent). Empty / whitespace ``boundary_sha`` raises
    ``PhaseFailedError`` BEFORE ``git reset`` runs so the runner never
    wipes work without an explicit anchor.

    ``task_id`` and ``attempt`` thread the recovery ref identity: the
    caller chooses what counts as a distinct attempt (typically one
    increment per rollback fired inside a single JUDGE-phase call), and
    the function computes ``tmp/deviate-agent-work/<task>/attempt-N``
    deterministically.
    """
    if not boundary_sha or not boundary_sha.strip():
        raise PhaseFailedError(
            f"ROLLBACK_BOUNDARY_MISSING: refusing to roll back without an "
            f"explicit boundary_sha (phase={phase}, task_id={task_id!r}, "
            f"attempt={attempt}). The runner no longer falls back to "
            f"SessionState.red_commit_sha or HEAD~1."
        )
    boundary_sha = boundary_sha.strip()
    recovery_branch = _recovery_branch_for(task_id, attempt)

    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()

    # Capture the agent's work on a per-task, per-attempt side branch
    # BEFORE the destructive reset so the commit survives a parent SIGTERM
    # landing between ``git reset`` and ``git clean``. Earlier attempts
    # keep their distinct refs (attempt-0, attempt-1, ...) so a second
    # rollback cannot silently clobber the first.
    if commit_sha != boundary_sha:
        _preserve_agent_work(
            root,
            commit_sha=commit_sha,
            branch=branch,
            red_sha=boundary_sha,
            reason=reason,
            recovery_branch=recovery_branch,
        )

    snapshot = RollbackSnapshot(
        phase=phase,
        branch=branch,
        commit_sha=commit_sha,
        red_sha=boundary_sha,
        reason=reason[:500],
    )
    append_rollback_snapshot(snapshot, root / ".deviate")
    subprocess.run(
        ["git", "checkout", "--quiet", "--", ".deviate/"],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )

    # Reset to boundary_sha — discards ALL commits made during GREEN
    # (agent commit, orchestrator commit, residual commit) preserving only
    # the boundary and any previous judge feedback commits.
    #
    # If GREEN never committed (tests failed, early return),
    # HEAD == boundary_sha and the reset is a no-op on history.
    subprocess.run(
        ["git", "reset", "--hard", boundary_sha],
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
    return boundary_sha


def _preserve_agent_work(
    root: Path,
    *,
    commit_sha: str,
    branch: str,
    red_sha: str,
    reason: str,
    recovery_branch: str,
) -> None:
    """Snapshot the agent's commit on a per-attempt recovery branch.

    Force-updates ``recovery_branch`` (a ref of the form
    ``tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>``) to point
    at ``commit_sha`` so a parent SIGTERM between ``git reset`` and
    ``git clean`` doesn't strand the agent's work. Branch refs are
    cheap (a few bytes each) and live outside the worktree's normal
    branch refs so they never collide with operator-facing branches.

    The recovery ref identity MUST be threaded by the caller (typically
    via ``_recovery_branch_for(task_id, attempt)``) so each rollback
    stores its discarded commit at a distinct ref. A single global ref
    overwrites earlier attempts; per-attempt refs preserve them.

    Failure modes:
    - Branch creation fails (no git, detached HEAD, etc.): logged via
      ``_log_run``, rollback proceeds. The agent's work is lost in that
      case — same as before this fix — but the runner does not crash.
    """
    try:
        subprocess.run(
            [
                "git",
                "branch",
                "-f",
                recovery_branch,
                commit_sha,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=False,
        )
        _log_run(
            "AGENT_WORK_PRESERVED",
            commit_sha=commit_sha,
            branch=branch,
            red_sha=red_sha,
            recovery_branch=recovery_branch,
            reason=reason[:200],
        )
    except Exception as e:
        # ``subprocess.run`` with check=False won't raise on non-zero
        # exit; this guards against the rare case where git is missing
        # or the worktree is in an unexpected state.
        _log_run(
            "AGENT_WORK_PRESERVE_FAILED",
            error=str(e),
            commit_sha=commit_sha,
            recovery_branch=recovery_branch,
        )


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


def _coerce_feedback_text(value: object) -> str:
    """Return ``value`` as a readable feedback string, tolerating non-str.

    The judge agent may emit ``train_feedback`` (or ``rationale``/
    ``summary``) as a YAML mapping or list instead of a plain string.
    A mapping is flattened to its string sub-values; a list is line-
    joined; anything else is ``str()``. This keeps the feedback-cascade
    and ``JUDGE_REFACTOR_NOTE`` paths from crashing on a dict-valued
    field.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [_coerce_feedback_text(v) for v in value.values() if v is not None]
        return "\n".join(p for p in parts if p) if parts else str(value)
    if isinstance(value, (list, tuple)):
        return "\n".join(_coerce_feedback_text(v) for v in value)
    return str(value)


# ---- Judge next_action routing ---------------------------------------------
#
# JUDGE decides, via HandoverManifest.next_action, how the runner should
# route the task on compliance outcome. Five values:
#
#   revert_before              — discard this task's GREEN *and* its RED; restart
#                                from pre-RED so RED can re-author the failing test.
#                                Used when the test itself is wrong.
#   revert_to_red              — discard GREEN, keep RED, advance red_commit_sha
#                                past the feedback commit so a second rollback
#                                preserves the new GREEN attempt's history. (Default
#                                on COMPLIANCE_VIOLATION when next_action is omitted
#                                — preserves the prior behavior that this module is
#                                fixing regression on.)
#   continue_refactor          — GREEN already correct; skip JUDGEs verdict-loop
#                                and route directly to REFACTOR. Distinct from
#                                `proceed_to_refactor_no_diff` below: signals a
#                                *substantive* refactor pass (GREEN produced a
#                                non-empty diff that REFACTOR will polish).
#   skip_refactor              — GREEN already correct and refactor not wanted;
#                                mark the task COMPLETED and move on.
#   proceed_to_refactor_no_diff — A forward (COMPLIANCE_PASS) route parallel to
#                                `continue_refactor`, but for the case where
#                                GREEN had nothing to do (e.g. a RED-only
#                                deliverable slice, or a mechanical GREEN FAILURE
#                                the judge ruled in-scope but unsatisfiable). The
#                                diff is empty — REFACTOR still runs because its
#                                commit + ledger transition are the only path to
#                                mark the task COMPLETED. Forces entry into
#                                REFACTOR regardless of the `--no-refactor` CLI
#                                flag, exactly like `continue_refactor`.
#
# The runner honors the manifest verbatim. There is no interactive prompt:
# operators can override externally via a CLI flag (future work), not via
# a runtime question.
_JUDGE_ACTIONS = frozenset(
    {
        "revert_before",
        "revert_to_red",
        "continue_refactor",
        "skip_refactor",
        "proceed_to_refactor_no_diff",
    }
)
_MAX_GREEN_ATTEMPTS = 3
_MAX_RED_ATTEMPTS = 3


def _coerce_judge_action(
    manifest: HandoverManifest,
    verdict: str,
    *,
    failure_kind: str = "",
) -> str | None:
    """Return the manifest's ``next_action`` if valid; default to
    ``revert_to_red`` on violation when the field is absent; ``None`` on
    pass when the field is absent.

    Runner-level override: when ``failure_kind`` is ``test_defect`` or
    ``no_failing_test`` and the verdict is a violation, force
    ``revert_before`` regardless of what ``next_action`` the JUDGE manifest
    declared (or omitted). The RED test itself is wrong; the agent must
    re-author it before any further GREEN attempt. PASS verdicts preserve
    the agent's outcome.
    """
    if (
        failure_kind in {"test_defect", "no_failing_test"}
        and verdict.upper() == "COMPLIANCE_VIOLATION"
    ):
        return "revert_before"
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
    train_feedback_fb = _coerce_feedback_text(
        getattr(manifest, "train_feedback", None)
        or (manifest.model_extra or {}).get("train_feedback", "")
    )
    rationale_fb = _coerce_feedback_text(
        getattr(manifest, "rationale", None)
        or (manifest.model_extra or {}).get("rationale", "")
    )
    summary_fb = _coerce_feedback_text(
        getattr(manifest, "summary", None)
        or (manifest.model_extra or {}).get("summary", "")
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
    """Persist JUDGE feedback and advance the committed RED boundary."""
    tid = task.get("id", "?")
    session.pending_judge_feedback = {
        "task_id": str(tid),
        "feedback": feedback,
        "feedback_source": feedback_source,
    }
    session.save(session_path)
    feedback_preview = feedback.replace("\n", " ")[:200]

    tasks_md = _resolve_tasks_md(root, task)
    if tasks_md is not None:
        added_lines = _append_judge_feedback(tasks_md, tid, feedback)
        if added_lines is None:
            c.print(
                f"  [yellow]TASKS_MD_NO_MATCH[/] {tid}: "
                f"no task line in {tasks_md} matches this id — "
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
                f"  [cyan]TASKS_MD_FEEDBACK[/] {tid} → {tasks_md}: "
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
            ["git", "commit", "-m", judge_msg, "--no-verify", "--allow-empty"],
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
    session.pending_judge_feedback = None
    session.save(session_path)
    return session


def _resume_pending_judge_feedback(
    root: Path,
    task: dict,
    c: Console,
    session: SessionState,
    session_path: Path,
) -> SessionState:
    pending = session.pending_judge_feedback
    if not pending or pending.get("task_id") != task.get("id"):
        return session

    session = _commit_judge_feedback_and_advance(
        root,
        task,
        pending["feedback"],
        pending["feedback_source"],
        c,
        session,
        session_path,
    )
    session.pending_judge_action = "revert_to_red"
    session.train_feedback = pending["feedback"]
    session.judge_rejected = True
    session = session.force_transition_to("GREEN")
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
    red_baseline: list[str] | None = None,
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
        committed_diff = subprocess.run(
            ["git", "diff", f"{diff_base}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
    elif red_baseline is not None:
        # RED-adjudication path: no RED commit exists, so there is no
        # committed diff — the uncommitted RED test carries the change
        # (surfaced via the dirty_parts scan below).
        committed_diff = ""
    else:
        diff_base = "HEAD~1"
        committed_diff = subprocess.run(
            ["git", "diff", f"{diff_base}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout
    dirty_parts: list[str] = []
    if status.strip():
        worktree_diff = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        dirty_parts.append(worktree_diff)
        for status_line in status.splitlines():
            if status_line.startswith("?? "):
                path = status_line[3:]
                untracked_diff = subprocess.run(
                    ["git", "diff", "--no-index", "/dev/null", path],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    env=_git_env(),
                ).stdout
                dirty_parts.append(untracked_diff)
    diff = "\n".join(part for part in [committed_diff, *dirty_parts] if part)

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

    elif session.failure_kind == "no_failing_test":
        prompt += (
            "\n\n<failure_kind>no_failing_test</failure_kind>\n\n"
            "RED phase completed but produced NO failing test: the test "
            "command exited 0 (all tests passed) or collected no tests. The "
            "authored test is uncommitted in the working tree and may be a "
            "stub; no implementation exists yet. Decide between two "
            "outcomes:\n"
            "  - The required behavior ALREADY EXISTS and the task needs no "
            "implementation: `verdict: COMPLIANCE_PASS` + "
            "`next_action: skip_refactor` (mark the task COMPLETED; no "
            "REFACTOR pass is wanted — no implementation was written).\n"
            "  - The test is wrong, tautological, or cannot target the "
            "required behavior: `verdict: COMPLIANCE_VIOLATION` + "
            "`next_action: revert_before` (discard the test and re-author a "
            "genuinely failing test in RED).\n"
            "Populate `train_feedback` or `rationale` with the reason, so "
            "the next RED attempt (or the COMPLETED record) carries it.\n"
        )
    agent_output_callback = _make_agent_output_callback(monitor, tid, "JUDGE")
    judge_model = resolve_model_for_phase("JUDGE", root, backend=backend)
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
    action = _coerce_judge_action(manifest, verdict, failure_kind=session.failure_kind)
    session.last_judge_verdict = getattr(manifest, "verdict", "").upper()

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

        # Rollback to the anchor that the action names. Both branches MUST
        # pass an explicit `boundary_sha` — the runner no longer falls back
        # to ``SessionState.red_commit_sha`` or ``HEAD~1``. ``task_id`` and
        # ``attempt`` thread the per-attempt recovery ref
        # (``tmp/deviate-agent-work/<task>/attempt-<N>``) so each discarded
        # commit lands on its own ref instead of clobbering one global ref.
        # ``rollback_attempts`` increments before each preserved reset so
        # multiple rollbacks inside a single JUDGE-phase call produce
        # distinct refs.
        rollback_attempts = 0
        try:
            if action == "revert_before":
                pre_red = (
                    _resolve_pre_red_sha(root, session.red_commit_sha)
                    if session.red_commit_sha
                    else ""
                )
                if pre_red:
                    # F3 (rollback safety): capture the agent's work BEFORE
                    # the destructive reset so a parent SIGTERM landing
                    # between ``git reset`` and ``git clean`` doesn't
                    # strand the agent's commit. Same recovery-ref
                    # identity rules as ``_execute_rollback`` apply.
                    branch = subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        env=_git_env(),
                    ).stdout.strip()
                    head_sha = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        env=_git_env(),
                    ).stdout.strip()
                    rollback_attempts += 1
                    if head_sha != pre_red:
                        _preserve_agent_work(
                            root,
                            commit_sha=head_sha,
                            branch=branch,
                            red_sha=pre_red,
                            reason=feedback,
                            recovery_branch=_recovery_branch_for(
                                tid, rollback_attempts
                            ),
                        )
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
                elif session.red_commit_sha:
                    # No pre-RED anchor, but ``session.red_commit_sha`` is
                    # known — fall back to that explicit boundary so the
                    # runner is never stuck and never guesses.
                    rollback_attempts += 1
                    _execute_rollback(
                        root,
                        boundary_sha=session.red_commit_sha,
                        reason=feedback,
                        phase="JUDGE",
                        task_id=tid,
                        attempt=rollback_attempts,
                    )
                elif red_baseline is not None:
                    # RED-adjudication path: no RED commit exists to roll
                    # back. Discard only the files this RED attempt produced
                    # so the next RED re-author starts from the phase
                    # baseline.
                    _restore_worktree_to_baseline(root, red_baseline)
                else:
                    # No pre-RED anchor AND no RED boundary in session.
                    # The runner no longer falls back to ``HEAD~1``; raise
                    # so the operator can see why rollback was refused
                    # instead of silently losing commits.
                    raise PhaseFailedError(
                        f"ROLLBACK_BOUNDARY_MISSING: revert_before for {tid} "
                        f"has no pre-RED anchor (session.red_commit_sha is "
                        f"empty) and no explicit boundary_sha was supplied. "
                        f"Refusing to fall back to HEAD~1."
                    )
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
            # ``boundary_sha`` is the active RED commit, threaded from
            # ``session.red_commit_sha`` — never inferred from session
            # state inside ``_execute_rollback`` itself.
            if not session.red_commit_sha:
                raise PhaseFailedError(
                    f"ROLLBACK_BOUNDARY_MISSING: revert_to_red for {tid} "
                    f"has no session.red_commit_sha to roll back to. "
                    f"Refusing to fall back to HEAD~1."
                )
            rollback_attempts += 1
            _execute_rollback(
                root,
                boundary_sha=session.red_commit_sha,
                reason=feedback,
                phase="JUDGE",
                task_id=tid,
                attempt=rollback_attempts,
            )
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
    #   action=None                       → legacy behavior: phase = JUDGE,
    #                                       hand to _finish_tdd_cycle (which
    #                                       decides refactor)
    #   action=continue_refactor          → pending_judge_action=continue_refactor;
    #                                       _finish_tdd_cycle enters REFACTOR
    #                                       regardless of no_refactor.
    #   action=skip_refactor              → phase = IDLE, mark COMPLETED, move on.
    #   action=proceed_to_refactor_no_diff → pending_judge_action=proceed_to_refactor_no_diff;
    #                                       _finish_tdd_cycle enters REFACTOR
    #                                       regardless of no_refactor. Used when
    #                                       GREEN had nothing to do (e.g. a
    #                                       RED-only deliverable slice that
    #                                       produced an empty diff). Same hand-off
    #                                       shape as `continue_refactor`, but with
    #                                       a distinct action so the runner and
    #                                       logs can distinguish a substantive
    #                                       refactor pass from a no-op green
    #                                       sign-off.
    refactor_note = _coerce_feedback_text(
        getattr(manifest, "train_feedback", None)
        or (manifest.model_extra or {}).get("train_feedback", "")
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

    if action == "proceed_to_refactor_no_diff":
        # Used when GREEN had nothing to do (e.g. a RED-only deliverable
        # slice that produced an empty diff). Same hand-off shape as
        # `continue_refactor`: enter REFACTOR and let `_finish_tdd_cycle`
        # mark the task COMPLETED after REFACTOR's no-op commit. Distinct
        # pending_judge_action so the runner + logs differentiate a
        # substantive refactor pass from a no-op green sign-off.
        session.pending_judge_action = "proceed_to_refactor_no_diff"
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
    refactor_model = resolve_model_for_phase("REFACTOR", root, backend=backend)
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
    #   continue_refactor             → enter REFACTOR regardless of no_refactor.
    #   proceed_to_refactor_no_diff   → enter REFACTOR regardless of no_refactor
    #                                  (used when GREEN had nothing to do;
    #                                  REFACTOR's no-op commit + COMPLETED
    #                                  transition is the only way to terminate
    #                                  a slice whose git diff is empty).
    #   skip_refactor                 → mark COMPLETED and stop, regardless
    #                                  of no_refactor (the CLI flag says
    #                                  nothing about future tasks; the judge
    #                                  verdict does).
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
        return _idle_after_tdd(session, session_path)

    if (
        pending == "continue_refactor"
        or pending == "proceed_to_refactor_no_diff"
        or not no_refactor
    ):
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
        _reset_tdd_retry_budget(session)
        session.save(session_path)
        return session

    # no_refactor (CLI flag) with no JUDGE override.
    try:
        _append_status_transition(task, "COMPLETED", ledger_path)
    except Exception as e:
        c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")
    c.print(f"  [bold green]COMPLETED[/] {_task_label(task)}")
    return _idle_after_tdd(session, session_path)


def _reset_tdd_retry_budget(session: SessionState) -> None:
    """Clear GREEN-train and RED-escalate counters for the next task."""
    session.green_attempts = 0
    session.red_attempts = 0


def _clear_judge_retry_gate(session: SessionState) -> None:
    """Consume the one-shot JUDGE action so the next cycle cannot re-escalate."""
    session.pending_judge_action = ""
    session.judge_rejected = False


def _idle_after_tdd(
    session: SessionState,
    session_path: Path,
) -> SessionState:
    """Park the session at IDLE with a fresh TDD retry budget."""
    session.pending_judge_action = ""
    session = session.force_transition_to("IDLE")
    session.train_feedback = ""
    session.judge_rejected = False
    _reset_tdd_retry_budget(session)
    session.save(session_path)
    return session


def _raise_train_exhausted(
    session: SessionState,
    session_path: Path,
    c: Console,
    *,
    task_id: str,
) -> NoReturn:
    """Print TRAIN_EXHAUSTED, zero counters, and hand off to the operator."""
    message = f"TRAIN_EXHAUSTED: {task_id} reached {_MAX_RED_ATTEMPTS} RED escalates"
    c.print(f"  [red]TRAIN_EXHAUSTED[/] {message}")
    _reset_tdd_retry_budget(session)
    _clear_judge_retry_gate(session)
    session.save(session_path)
    raise PhaseFailedError(message)


def _account_red_escalate(
    session: SessionState,
    session_path: Path,
    c: Console,
    *,
    task_id: str,
) -> None:
    """Reset GREEN trains, count one RED escalate, and stop at the cap."""
    session.green_attempts = 0
    session.red_attempts += 1
    session.save(session_path)
    if session.red_attempts >= _MAX_RED_ATTEMPTS:
        _raise_train_exhausted(session, session_path, c, task_id=task_id)


def _rollback_pre_red_if_resolvable(
    root: Path,
    session: SessionState,
    *,
    task_id: str,
    attempt: int,
    reason: str,
) -> None:
    """Reset to the pre-RED SHA when git can resolve a full 40-char SHA."""
    red_sha = session.red_commit_sha
    if not red_sha or not re.fullmatch(r"[a-f0-9]{40}", red_sha):
        return
    pre_red = _resolve_pre_red_sha(root, red_sha)
    if not pre_red or not re.fullmatch(r"[a-f0-9]{40}", pre_red):
        return
    _execute_rollback(
        root,
        boundary_sha=pre_red,
        reason=reason,
        phase="GREEN",
        task_id=task_id,
        attempt=attempt,
    )


def _short_escalate_note(*, reason: str, failure_kind: str = "") -> str:
    """Build a one-line retry-RED note from the escalate reason token."""
    cause = " ".join(reason.replace("_", " ").split()) or (
        "the previous cycle was rejected"
    )
    kind = " ".join(failure_kind.split())
    suffix = f" (failure_kind={kind})" if kind else ""
    return f"previous cycle failed because {cause}{suffix}."


def _inject_escalate_note(
    session: SessionState,
    session_path: Path,
    *,
    reason: str,
) -> None:
    """Replace GREEN ``train_feedback`` with a short note and persist it."""
    session.train_feedback = _short_escalate_note(
        reason=reason,
        failure_kind=session.failure_kind,
    )
    session.save(session_path)


def _escalate_to_new_red(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    *,
    agent: str | None,
    monitor: OrchestrationMonitor | None,
    no_judge: bool,
    root: Path,
    reason: str,
) -> SessionState:
    """Escalate to a fresh RED. Stop after three escalates.

    Counters persist first. Then GREEN ``train_feedback`` is replaced
    with a short note so retry RED does not receive the GREEN dump.
    """
    tid = task.get("id", "?")
    task_desc = task.get("description", "")
    _account_red_escalate(session, session_path, c, task_id=tid)
    _inject_escalate_note(session, session_path, reason=reason)
    _rollback_pre_red_if_resolvable(
        root,
        session,
        task_id=tid,
        attempt=session.red_attempts,
        reason=reason,
    )
    _maybe_push_event(
        monitor,
        "phase_change",
        task_id=tid,
        phase="RED",
        description=task_desc,
    )
    session = _run_red_phase(
        task,
        ledger_path,
        session,
        session_path,
        c,
        agent=agent,
        monitor=monitor,
        bypass_phase_done=True,
        no_judge=no_judge,
    )
    _clear_judge_retry_gate(session)
    session.save(session_path)
    _log_run(
        "PHASE_DECISION",
        task_id=tid,
        phase="CYCLE",
        decision="escalate_to_red",
        reason=reason,
        red_attempts=session.red_attempts,
    )
    return session


def _emit_green_train(c: Console, *, attempt: int, reason: str) -> None:
    c.print(
        TrainIndicator.render(
            attempt=attempt,
            maximum=_MAX_GREEN_ATTEMPTS,
            phase="GREEN",
        )
    )
    c.print(f"  [yellow]TRAIN ({attempt}/{_MAX_GREEN_ATTEMPTS}) \u2014 {reason}[/]")


def _train_green_or_escalate(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    *,
    agent: str | None,
    monitor: OrchestrationMonitor | None,
    no_judge: bool,
    root: Path,
) -> tuple[SessionState, bool]:
    """Count one GREEN train. Escalate when ``green_attempts`` reaches 3.

    Returns ``(session, True)`` after a new RED dispatch, or
    ``(session, False)`` when GREEN should retry the standing RED contract.
    """
    session.green_attempts += 1
    session.save(session_path)
    if session.green_attempts < _MAX_GREEN_ATTEMPTS:
        return session, False
    session = _escalate_to_new_red(
        task,
        ledger_path,
        session,
        session_path,
        c,
        agent=agent,
        monitor=monitor,
        no_judge=no_judge,
        root=root,
        reason="green_budget_exhausted",
    )
    return session, True


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

    # `no_judge` only skips the JUDGE phase — GREEN must still run. The
    # in-loop `if no_judge: judge_passed = True; break` below is the exit
    # path; initializing to `no_judge` here would skip the GREEN loop
    # entirely and mark the task COMPLETED with its test never implemented.
    judge_passed = False
    if start_phase != "GREEN":
        _maybe_push_event(
            monitor, "phase_change", task_id=tid, phase="RED", description=task_desc
        )
        session = _run_red_phase(
            task,
            ledger_path,
            session,
            session_path,
            c,
            agent=agent,
            monitor=monitor,
            no_judge=no_judge,
        )

    while not judge_passed:
        # RED's no-failing-test adjudication (RED → JUDGE direct route) may
        # have already returned a verdict — honor it before GREEN runs,
        # since a vacuous GREEN has nothing to implement. Forward verdicts
        # break out to _finish_tdd_cycle; revert_before escalates to a new RED.
        if session.pending_judge_action == "revert_before":
            session = _escalate_to_new_red(
                task,
                ledger_path,
                session,
                session_path,
                c,
                agent=agent,
                monitor=monitor,
                no_judge=no_judge,
                root=root,
                reason="no_failing_test_adjudicated",
            )
            continue
        if session.pending_judge_action in _NO_FAILING_TEST_FORWARD_ROUTES:
            judge_passed = True
            break
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
                session, escalated = _train_green_or_escalate(
                    task,
                    ledger_path,
                    session,
                    session_path,
                    c,
                    agent=agent,
                    monitor=monitor,
                    no_judge=no_judge,
                    root=root,
                )
                if escalated:
                    continue
                _emit_green_train(
                    c,
                    attempt=session.green_attempts,
                    reason=("GREEN phase post-cleanup failed, retrying with feedback"),
                )
                _log_run(
                    "PHASE_DECISION",
                    task_id=tid,
                    phase="GREEN",
                    decision="reroute_to_green",
                    reason="post_cleanup_failed",
                    attempt=session.green_attempts,
                    max_red_attempts=_MAX_RED_ATTEMPTS,
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
        # Forward-route exit: JUDGE picked continue_refactor /
        # proceed_to_refactor_no_diff / skip_refactor. The runner must leave
        # the TRAIN retry loop without re-running GREEN — the forward-route
        # verdict is the cycle's exit signal (clears train_feedback, sets
        # pending_judge_action, and JUDGE has already cleaned up state).
        if session.pending_judge_action in {
            "continue_refactor",
            "proceed_to_refactor_no_diff",
            "skip_refactor",
        }:
            judge_passed = True
            break
        # Honor coerced ``revert_before``. ``revert_to_red`` still trains
        # GREEN and keeps dump ``train_feedback``.
        if session.pending_judge_action == "revert_before":
            session = _escalate_to_new_red(
                task,
                ledger_path,
                session,
                session_path,
                c,
                agent=agent,
                monitor=monitor,
                no_judge=no_judge,
                root=root,
                reason="test_defect",
            )
            continue
        # Decision gate. An explicit COMPLIANCE_PASS verdict adjudicates any
        # residual suite failures as acceptable, so the pre-JUDGE GREEN-stall
        # snapshot must not force a spurious TRAIN retry (which would loop a
        # correct slice into TRAIN_EXHAUSTED). An unadjudicated (EMPTY) judge
        # verdict leaves the pre-JUDGE snapshot authoritative: a genuinely
        # failing GREEN suite still retrains to exhaustion.
        judge_passed_explicitly = bool(
            session.last_judge_verdict == "COMPLIANCE_PASS"
            and not session.judge_rejected
        )
        still_failing = bool(green_tests_failed and not judge_passed_explicitly)
        if session.judge_rejected or session.train_feedback or still_failing:
            session, escalated = _train_green_or_escalate(
                task,
                ledger_path,
                session,
                session_path,
                c,
                agent=agent,
                monitor=monitor,
                no_judge=no_judge,
                root=root,
            )
            if escalated:
                continue
            if not session.train_feedback:
                session.train_feedback = (
                    "GREEN implementation tests failed. "
                    "The implementation must be corrected to pass the test suite."
                )
            session = session.force_transition_to("GREEN")
            session.save(session_path)
            if (
                session.pending_judge_action == "revert_to_red"
                or session.judge_rejected
            ):
                train_reason = "re-running GREEN with judge feedback"
            else:
                train_reason = (
                    "tests still failing, re-running GREEN with test feedback"
                )
            _emit_green_train(
                c,
                attempt=session.green_attempts,
                reason=train_reason,
            )
            session.judge_rejected = False
            session.save(session_path)
            _log_run(
                "PHASE_DECISION",
                task_id=tid,
                phase="JUDGE",
                decision="reroute_to_green",
                attempt=session.green_attempts,
                max_red_attempts=_MAX_RED_ATTEMPTS,
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
    execute_model = resolve_model_for_phase("EXECUTE", root, backend=backend)

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
            stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS,
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
        # Stage the agent's deliverable before committing. The recovery
        # helper (unlike _commit_phase) does not stage, so without this the
        # EXECUTE commit fails with "nothing staged" and untracked files
        # (new schemas, migrations) are dropped from the recovery ref.
        # The worktree at this point holds only this task's changes
        # (enforced by _verify_clean_worktree below), so a full add is exact.
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)

        _commit_phase_with_recovery(
            f"feat({scope}): EXECUTE phase - {tid}",
            root,
            task_id=tid,
            attempt=attempt,
            phase="EXECUTE",
        )

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

        judge_model = resolve_model_for_phase("JUDGE", root, backend=backend)
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
                # EXECUTE has no RED boundary — ``pre_execute_sha`` (captured
                # before the first EXECUTE attempt) is the only safe anchor,
                # threaded explicitly so ``_execute_rollback`` cannot infer
                # it from session state or ``HEAD~1``. ``attempt`` is the
                # JUDGE-attempt counter so each discarded commit lands on
                # ``tmp/deviate-agent-work/<tid>/attempt-<N>``.
                _execute_rollback(
                    root,
                    boundary_sha=pre_execute_sha,
                    reason=feedback,
                    phase="EXECUTE",
                    task_id=tid,
                    attempt=attempt,
                )
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
    model: str | None = None,
) -> None:
    global _cli_model_override
    if model is not None:
        _cli_model_override = model
    task, ledger_file = _resolve_task_context(task_id, root)
    status = task.get("status", "PENDING")

    session_path = root / ".deviate" / "session.json"
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

    # RED/GREEN/REFACTOR progress is read from the tracked tasks.jsonl, not
    # from session.json (a git reset reverts the JSONL but not the untracked
    # session cache). pending_judge_feedback is honored only when the JSONL
    # still records the implementation the judge rejected.
    if session.pending_judge_feedback and status in ("RED", "GREEN"):
        session = _resume_pending_judge_feedback(root, task, c, session, session_path)
        start_phase = "GREEN"
    else:
        start_phase = _start_phase_from_status(status)

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
    session_path = root / ".deviate" / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    start_phase: str | None = None
    # Honor pending_judge_feedback only when the tracked tasks.jsonl still
    # records the implementation the judge rejected (RED or GREEN). A git
    # reset that reverts the JSONL to PENDING invalidates stale feedback.
    status = task.get("status", "PENDING")
    if (
        session.pending_judge_feedback
        and session.pending_judge_feedback.get("task_id") == tid
        and status in ("RED", "GREEN")
    ):
        session = _resume_pending_judge_feedback(root, task, c, session, session_path)
        start_phase = "GREEN"
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
                    start_phase=start_phase,
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


def _resolve_pending_feedback_task(
    root: Path, session: SessionState, issue_id: str | None
) -> tuple[dict, Path] | None:
    pending = session.pending_judge_feedback
    if not pending:
        return None
    result = _find_task_record(root, pending.get("task_id", ""))
    if result is None:
        return None
    task, ledger_path = result
    if issue_id is not None and task.get("issue_id") != issue_id:
        return None
    return task, ledger_path


def _run_all(
    root: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
    json_mode: bool = False,
    model: str | None = None,
) -> None:
    global _cli_model_override
    if model is not None:
        _cli_model_override = model
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

    recovery = _resolve_pending_feedback_task(root, session, issue_id)
    pending = _find_all_pending_tasks(root, issue_id=issue_id)
    if recovery is not None and all(
        task.get("id") != recovery[0].get("id") for task, _ in pending
    ):
        pending.insert(0, recovery)
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


# ---------------------------------------------------------------------------
# Commit-failure recovery
#
# The round-1 rollback fix preserves discarded agent work on a per-task,
# per-attempt ref under the ``tmp/deviate-agent-work/<task>/attempt-<N>``
# namespace (see ``_execute_rollback`` / ``_preserve_agent_work`` above).
# This namespace is for *successful* discards of a judged attempt.
#
# This block defines a SECOND, parallel namespace
# (``refs/deviate/recovery/<task>/attempt-<N>``) for the orthogonal case
# where ``git commit`` itself never lands. The two namespaces are
# intentionally distinct so a future reader can tell rollback-snapshot
# evidence from commit-hook-block evidence at a glance. They must not be
# unified: rollback evidence is anchored to a real git commit that the
# runner already produced; commit-failure recovery is anchored to the
# tree the hook rejected, captured at the moment of failure.
# ---------------------------------------------------------------------------

_RECOVERY_NS_PREFIX = "refs/deviate/recovery"
_RECOVERY_NS_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")
_RECOVERY_ID_MAX_LEN = 64


class _SanitizeError(ValueError):
    """Raised when a task id cannot be safely namespaced for the recovery refs.

    Translates to ``CommitFailedError(reason=<sanitize_reason>, recovery_ref=None)``
    at the outer caller so the banner preserves the distinction between
    "operator passed a hostile task id" and "git plumbing failed".
    """

    def __init__(self, reason: str, raw: str) -> None:
        super().__init__(f"{reason}: {raw!r}")
        self.reason = reason
        self.raw = raw


def _sanitize_recovery_id(task_id: str) -> str:
    """Return a git-ref-safe task id for the recovery namespace.

    Allow-list: ``[A-Za-z0-9_-]``. Length cap: 64 characters. Rejects
    empty / whitespace, leading ``.``, any literal ``..``, and ids that
    exceed the cap. The strict allow-list prevents ref injection (e.g.
    ``../../../HEAD``) and keeps every produced ref inside the
    ``refs/deviate/recovery/`` namespace.

    Raises ``_SanitizeError``; the outer helper translates that to a
    ``CommitFailedError`` with a sanitize-specific reason so the banner
    does not collapse into ``commit_failed_plumbing``.
    """
    raw = (task_id or "").strip()
    if not raw:
        raise _SanitizeError("sanitize_empty_task_id", task_id or "")
    if raw.startswith("."):
        raise _SanitizeError("sanitize_leading_dot", raw)
    if ".." in raw:
        raise _SanitizeError("sanitize_double_dot", raw)
    if len(raw) > _RECOVERY_ID_MAX_LEN:
        raise _SanitizeError("sanitize_too_long", raw)
    return _RECOVERY_NS_SAFE_RE.sub("-", raw)


def _next_recovery_attempt(task_id: str, *, root: Path) -> int:
    """Return the next available attempt number for the recovery namespace.

    Enumerates ``refs/deviate/recovery/<sanitized>/attempt-*`` and returns
    ``max(N) + 1`` (default 1 if none exist). This makes recovery refs
    collision-safe: two distinct failures for the same task produce
    ``attempt-1`` and ``attempt-2`` instead of silently overwriting.

    Reservation of the integer is part of the helper contract: the
    caller threads the same integer into BOTH the commit message and
    the recovery ref name so they cannot disagree.
    """
    sanitized = _sanitize_recovery_id(task_id)
    listing = subprocess.run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname)",
            f"{_RECOVERY_NS_PREFIX}/{sanitized}/",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    refs = [line.strip() for line in listing.stdout.splitlines() if line.strip()]
    max_n = 0
    for ref in refs:
        suffix = ref.rsplit("/attempt-", 1)[-1]
        try:
            n = int(suffix)
        except ValueError:
            continue
        if n > max_n:
            max_n = n
    return max_n + 1


def _recovery_ref(task_id: str, attempt: int) -> str:
    """Return the namespaced recovery ref for ``task_id`` and ``attempt``."""
    sanitized = _sanitize_recovery_id(task_id)
    return f"{_RECOVERY_NS_PREFIX}/{sanitized}/attempt-{int(attempt)}"


class CommitFailedError(PhaseFailedError):
    """Raised when ``git commit`` fails for the EXECUTE phase.

    Carries a recovery ref pointing at a real commit whose tree is
    exactly the tree the ``git commit`` attempted to record. Operators
    restore the rejected work with::

        git cherry-pick refs/deviate/recovery/<task>/attempt-<N>

    The recovery ref is created via plumbing only (``git write-tree``,
    ``git commit-tree``, ``git update-ref``); the operator's index and
    working tree are NOT mutated. If plumbing itself fails, the
    ``recovery_ref`` is ``None`` and ``output`` carries the plumbing
    stderr so the operator sees the underlying cause instead of a
    misleading hook-blocked banner.

    ``terminal=True`` marks the failure as terminal for the current run
    (so the dispatcher can render the recovery banner and not silently
    retry atop the rejected staged tree), but the underlying
    ``PhaseFailedError`` shape means the existing call sites that
    already catch ``PhaseFailedError`` continue to match without code
    changes.
    """

    terminal: bool = True

    def __init__(
        self,
        *,
        recovery_ref: str | None,
        output: str,
        reason: str,
        terminal: bool = True,
    ) -> None:
        self.recovery_ref = recovery_ref
        self.output = output
        self.reason = reason
        self.terminal = terminal
        super().__init__(f"COMMIT_FAILED: {reason}")


def _commit_phase_with_recovery(
    message: str,
    root: Path,
    *,
    task_id: str,
    attempt: int,
    phase: str | None = "EXECUTE",
) -> bool:
    """Like ``_commit_phase`` but raises ``CommitFailedError`` on failure.

    The existing ``_commit_phase`` helper silently swallows ``git commit``
    failures and returns ``False``; that contract is correct for the 10
    routine ``no_verify=True`` RED/GREEN/REFACTOR sites because their
    commits are bypassed by hooks and effectively cannot fail for hook
    reasons. The single EXECUTE call site at ``micro.py:2857`` is the
    only one that intentionally lets the project's hook gate the commit,
    so it gets a stricter contract:

    * Run ``git commit`` with combined ``stdout+stderr`` captured.
    * On non-zero, build a recovery commit from the existing staged
      index via ``git write-tree`` / ``git commit-tree -p HEAD`` /
      ``git update-ref`` (no ``git add``, no ``git reset``, no
      ``git clean``, no ``git stash``).
    * Assert the recovery commit's tree equals the ``write-tree``
      output, catching merge-driver / intent-to-add / submodule
      mismatches that would otherwise produce a cherry-pick that
      differs from the rejected tree.
    * On any plumbing failure, raise ``CommitFailedError(recovery_ref=None, ...)``
      with the plumbing stderr in ``output`` so the operator sees the
      underlying cause.
    * Always print the recovery banner and raise — the dispatcher will
      mark the task FAILED with reason ``commit_failed`` and stop the run.

    Returns ``True`` when ``git commit`` exits zero, or when the
    worktree was already clean (``nothing to commit``) — a legitimate
    no-op EXECUTE outcome treated as success.
    """
    formatted = format_commit_message(message, root, phase=phase)
    cmd = ["git", "commit", "-m", formatted]
    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=False,
    )
    if result.returncode == 0:
        console.print(f"  [green]Committed[/] [dim]{formatted}[/]")
        return True
    combined_output = (result.stdout or "") + (result.stderr or "")

    # A clean worktree is a legitimate EXECUTE outcome: the agent made
    # no changes (e.g. the deliverable already exists in the repo), so
    # ``git commit`` exits 1 with "nothing to commit". Git only emits
    # that message AFTER the hook chain passes, so this cannot mask a
    # hook-blocked commit. Treat it as a successful no-op (mirroring
    # ``_commit_phase``'s clean-tree contract) instead of fabricating a
    # recovery ref for an empty tree; the caller's no-diff branch
    # (JUDGE_SKIP) then completes the task as designed.
    if result.returncode == 1 and "nothing to commit" in combined_output:
        _log_run(
            "COMMIT_NOOP",
            task_id=task_id,
            attempt=attempt,
            reason="clean_worktree",
            output_trimmed=combined_output.strip()[:200],
        )
        console.print(
            f"  [dim]Nothing to commit for {task_id} — EXECUTE produced "
            "no changes (no-op)[/]"
        )
        return True
    plumbing_output = ""
    tree_sha = ""
    recovery_ref: str | None = None
    recovery_sha = ""

    # Reservation: compute the recovery attempt number ONCE, BEFORE the
    # plumbing try/except, so the commit message and the ref name use
    # the same integer. Sanitization failures surface here as
    # ``_SanitizeError``; a dedicated handler (below) translates them to
    # ``CommitFailedError(reason=sanitize_*, recovery_ref=None)`` instead
    # of letting them be swallowed by the generic plumbing fallback.
    try:
        next_attempt = _next_recovery_attempt(task_id, root=root)
        recovery_ref = _recovery_ref(task_id, next_attempt)
    except _SanitizeError as exc:
        _log_run(
            "COMMIT_FAILED_SANITIZE",
            task_id=task_id,
            attempt=attempt,
            recovery_ref=None,
            reason=exc.reason,
            raw=exc.raw[:200],
        )
        console.print(f"  [red]COMMIT_FAILED[/] {task_id} (sanitize: {exc.reason})")
        raise CommitFailedError(
            recovery_ref=None,
            output=combined_output,
            reason=exc.reason,
            terminal=True,
        ) from exc

    try:
        write_tree = subprocess.run(
            ["git", "write-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=False,
        )
        if write_tree.returncode != 0:
            plumbing_output = write_tree.stderr or write_tree.stdout or ""
            raise RuntimeError("write-tree failed")
        tree_sha = write_tree.stdout.strip()

        commit_tree = subprocess.run(
            [
                "git",
                "commit-tree",
                tree_sha,
                "-p",
                "HEAD",
                "-m",
                f"Recovery: {task_id} attempt-{int(next_attempt)} blocked by git commit failure",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=False,
        )
        if commit_tree.returncode != 0:
            plumbing_output = commit_tree.stderr or commit_tree.stdout or ""
            raise RuntimeError("commit-tree failed")
        recovery_sha = commit_tree.stdout.strip()

        roundtrip = subprocess.run(
            ["git", "rev-parse", f"{recovery_sha}^{{tree}}"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=False,
        )
        if roundtrip.returncode != 0:
            plumbing_output = roundtrip.stderr or roundtrip.stdout or ""
            raise RuntimeError("rev-parse tree failed")
        roundtrip_tree = roundtrip.stdout.strip()
        if roundtrip_tree != tree_sha:
            plumbing_output = (
                f"tree roundtrip mismatch: write-tree={tree_sha} "
                f"recovery^{{tree}}={roundtrip_tree}"
            )
            raise RuntimeError("tree roundtrip mismatch")

        update = subprocess.run(
            ["git", "update-ref", recovery_ref, recovery_sha],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=False,
        )
        if update.returncode != 0:
            plumbing_output = update.stderr or update.stdout or ""
            raise RuntimeError("update-ref failed")
    except Exception as plumbing_exc:
        _log_run(
            "COMMIT_FAILED_PLUMBING",
            task_id=task_id,
            attempt=attempt,
            recovery_ref=recovery_ref,
            reason=str(plumbing_exc),
            plumbing_output=plumbing_output[:500],
        )
        console.print(
            f"  [red]COMMIT_FAILED[/] {task_id} attempt-{attempt} "
            f"(plumbing fallback: {plumbing_exc})"
        )
        raise CommitFailedError(
            recovery_ref=None,
            output=(combined_output + "\n" + plumbing_output).strip(),
            reason="commit_failed_plumbing",
            terminal=True,
        ) from plumbing_exc

    _log_run(
        "COMMIT_FAILED",
        task_id=task_id,
        attempt=next_attempt,
        recovery_ref=recovery_ref,
        tree_sha=tree_sha,
        recovery_sha=recovery_sha,
        output_trimmed=combined_output.strip()[:500],
    )
    console.print(f"  [red]COMMIT_FAILED[/] {task_id} attempt-{next_attempt}")
    console.print("    git commit output (combined stdout+stderr):")
    for line in combined_output.strip().splitlines() or ["(no output captured)"]:
        console.print(f"      {line}")
    console.print(f"    recovery_ref: {recovery_ref}")
    console.print(
        "    Two recovery options:\n"
        "      1. Fix the failure in the target repo, then re-run `git commit`\n"
        "         (the worktree is already in the state the commit failed at).\n"
        "      2. After you have explicitly restored or removed the current\n"
        "         changes yourself, restore the rejected work with:\n"
        f"           git cherry-pick {recovery_ref}"
    )
    raise CommitFailedError(
        recovery_ref=recovery_ref,
        output=combined_output,
        reason="commit_failed",
        terminal=True,
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


def _issue_tasks_complete(root: Path, issue_id: str) -> bool:
    """True when every record for *issue_id*'s own tasks.jsonl is terminal.

    Scoped to the resolved issue's ledger, not the repo-wide glob, so an
    unrelated issue's incomplete tasks cannot block this issue's E2E run.
    """
    source_file = _resolve_issue_source_file(root, issue_id)
    if not source_file:
        return False
    ledger_path = resolve_issue_artifact_path(root, source_file, "tasks.jsonl")
    for record in _read_ledger_records(ledger_path):
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
    """Return the Verification value from the ledger or ``tasks.md``.

    A safety filter (:func:`is_safe_test_command`) is applied as
    defence in depth: any task verification that fails the parser is
    silently dropped so a poisoned record cannot smuggle an executable
    string through the task ledger. The final execution layer
    (:func:`run_safe_command`) repeats the same check and produces a
    deterministic failed ``CompletedProcess`` if a malicious value
    somehow slipped past this filter.
    """
    raw = _resolve_task_verification_value(root, task)
    if raw and is_safe_test_command(raw):
        return _normalise_test_command(raw)
    return ""


def _resolve_task_verification_value(root: Path, task: dict | None) -> str:
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
    raw = _normalise_test_command(
        commands.get("test_command") or commands.get("python_test_command")
    )
    # Constitution is repository-controlled metadata; route it through
    # the same policy as the ledger and tasks.md so a poisoned
    # constitution cannot escape via this source.
    if raw and is_safe_test_command(raw):
        return raw
    return ""


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


def _resolve_test_timeout_seconds(root: Path) -> int:
    """Resolve the test-command deadline for *root*.

    Resolution order (highest first):
        1. ``DEVIATE_TEST_TIMEOUT_SECONDS`` environment variable
           (ad-hoc CI override; takes a positive integer in seconds).
        2. ``DeviateConfig.timeout_seconds`` from the worktree's
           ``.deviate/config.toml`` (default 1800s).
        3. The Pydantic default ``1800`` when no config is present.

    An unparseable env var falls back to the config value; a config
    value that violates ``gt=0`` (only ``0`` is reachable through the
    loader today) also falls back to 300. Both fallback rules keep
    the timeout binding active even when the user mistypes the
    override — a silent disable would resurrect the GREEN-hang bug.
    """
    env_override = os.environ.get("DEVIATE_TEST_TIMEOUT_SECONDS", "").strip()
    if env_override:
        try:
            override = int(env_override)
            if override > 0:
                return override
        except ValueError:
            pass
    data = _load_deviate_config_toml(root)
    if isinstance(data, dict):
        config_value = data.get("timeout_seconds")
        if isinstance(config_value, int) and config_value > 0:
            return config_value
    return 1800


def _execute_test_command(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Execute a single candidate test command through the safe-command gate.

    The previous implementation invoked ``sh -c`` for every value, which
    allowed arbitrary shell execution from any untrusted repository
    source (constitution / tasks.md / ledger). The new implementation
    routes the command through :func:`run_safe_command`, which parses
    it via :mod:`shlex` against an executable allowlist and rejects
    shell metacharacters and unsupported binaries before the process
    is spawned.

    The deadline is resolved from :func:`_resolve_test_timeout_seconds`
    and forwarded to ``run_safe_command`` so a hung test command (for
    example ``cargo test`` spawning ``gloss serve`` parked on stdin
    EOF) cannot wedge the orchestrator. The deadline also opts into
    process-group isolation so SIGTERM/SIGKILL reach every descendant.
    """
    timeout = _resolve_test_timeout_seconds(cwd)
    return run_safe_command(command, cwd, timeout=timeout)


def _mise_test_invocation_failed(proc: subprocess.CompletedProcess) -> bool:
    """Return whether mise itself could not resolve the ``test`` task."""
    stderr = (proc.stderr or "").lower()
    return proc.returncode != 0 and any(
        marker in stderr
        for marker in ("unknown command", "unknown task", "task not found")
    )


def _run_test_cmd(root: Path, task: dict | None = None) -> subprocess.CompletedProcess:
    """Run configured tests through the safe-command gate.

    The candidate list is built by :func:`_test_command_candidates`,
    which already drops values that fail :func:`is_safe_test_command`
    for the task-ledger and constitution sources. Each remaining
    candidate is then executed by :func:`_execute_test_command`, which
    uses :func:`run_safe_command` — the single structured-argv
    trust boundary. No shell is ever spawned for repository-provided
    test commands.
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
    if not _test_command_candidates(root):
        console.print(
            "[red]TEST_NOT_FOUND[/] No test command configured and no test project detected"
        )
        raise typer.Exit(code=1)

    proc = _run_test_cmd(root)

    if proc.returncode == 0:
        console.print(
            "[red]RedMustPassError:[/] Test passed, expected a failing test "
            "(no new failing test was produced). Fix the test so it fails "
            "against the current implementation. If the required behavior "
            "already exists, declare `failure_kind: already_satisfied` in "
            "the RED handover manifest so `deviate micro run` adjudicates "
            "the task as COMPLETED."
        )
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
    if not _test_command_candidates(root):
        console.print(
            "[red]TEST_NOT_FOUND[/] No test command configured and no test project detected"
        )
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


def _check_return_type_mismatch(filepath: str) -> list[str]:
    """Check Python return type annotations against literal return values.

    Python-only check using stdlib ``ast``. Returns a list of human-readable
    issue strings for any function whose annotated return type is a known
    builtin (``str``, ``int``, ``float``, ``bool``, ``list``, ``dict``,
    ``tuple``, ``set``) whose body returns a literal of an incompatible type.
    Non-``.py`` paths return ``[]`` (the orchestrator only ever calls this on
    ``.py`` files; the language gate is defensive).
    """
    issues: list[str] = []
    if not filepath.endswith(".py"):
        return issues

    import ast

    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (OSError, SyntaxError):
        return issues

    scalar_types = {"str", "int", "float", "bool"}
    collection_types = {"list", "dict", "tuple", "set"}
    all_known = scalar_types | collection_types

    def _return_type_name(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        if func.returns is None:
            return None
        ann = func.returns
        if isinstance(ann, ast.Name):
            return ann.id
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            return ann.value
        return None

    def _literal_category(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant):
            val = node.value
            if isinstance(val, bool):
                return "bool"
            if isinstance(val, (int, float)):
                return type(val).__name__
            if isinstance(val, str):
                return "str"
            if isinstance(val, (list, tuple)):
                return "list" if isinstance(val, list) else "tuple"
            if isinstance(val, dict):
                return "dict"
            if isinstance(val, set):
                return "set"
            return None
        if isinstance(node, ast.List):
            return "list"
        if isinstance(node, ast.Tuple):
            return "tuple"
        if isinstance(node, ast.Dict):
            return "dict"
        if isinstance(node, ast.Set):
            return "set"
        return None

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ret_type = _return_type_name(node)
        if ret_type is None or ret_type not in all_known:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Return):
                continue
            if sub.value is None:
                continue
            got = _literal_category(sub.value)
            if got is None:
                continue
            if got != ret_type:
                ret_name = f"{node.name} (line {node.lineno})"
                issues.append(f"{ret_name}: expected {ret_type}, got literal {got}")
    return issues


@refactor_app.command(name="post")
def refactor_post() -> None:
    root = Path.cwd()
    if not _test_command_candidates(root):
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

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    issue_id = session.active_issue_id
    if not issue_id:
        issue_id = _resolve_issue_id_from_branch(root) or issue_id

    # Scope the completeness check to the branch's own issue so an unrelated
    # issue's incomplete tasks cannot block this E2E run. When no issue is
    # resolvable (plain dir, non-feature branch) fall back to the repo-wide
    # check for backward compatibility.
    if issue_id:
        all_complete = _issue_tasks_complete(root, issue_id)
    else:
        all_complete = _all_tasks_complete(root)

    if not all_complete:
        console.print("[red]INCOMPLETE_TASKS[/] Some tasks not completed")
        raise typer.Exit(code=1)

    test_paths = [str(p) for p in _find_test_files(root)]
    contract: dict[str, object] = {"test_paths": test_paths}
    if issue_id:
        source_file = _resolve_issue_source_file(root, issue_id)
        tasks_file = ""
        spec_dir = ""
        if source_file:
            tasks_file = str(
                resolve_issue_artifact_path(root, source_file, "tasks.jsonl")
            )
            spec_file = resolve_issue_artifact_path(root, source_file, "spec.md")
            if spec_file is not None:
                spec_dir = str(spec_file.parent)
        contract["issue_id"] = issue_id
        contract["tasks_file"] = tasks_file
        contract["spec_dir"] = spec_dir
        contract["git_branch"] = _git_branch(root)
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


def _run_auto_agent(root: Path, agent: str | None, model: str | None) -> None:
    """Spawn the agent with the deviatdd skill slash command as the prompt.

    Looks up the canonical slash command for the resolved backend in
    :data:`_DEVIATDD_SLASH_COMMAND` and invokes the agent with it. The
    agent then runs the skill, which internally calls ``deviate micro run``
    per task until the queue drains. Falls back to a warning + exit-1
    when the configured backend has no known slash command (e.g.
    ``opencode`` / ``droid`` / ``stub``); operators on those backends
    must invoke the agent manually.
    """
    backend_name = _resolve_agent_config(root, agent)
    slash_cmd = _DEVIATDD_SLASH_COMMAND.get(backend_name or "")
    if slash_cmd is None:
        console.print(
            f"[red]AUTO_NO_SLASH_COMMAND[/] backend '{backend_name}' has no "
            f"deviatdd slash command. Invoke the agent manually with the "
            f"skill installed by `deviate setup`."
        )
        raise typer.Exit(code=1)
    console.print(
        f"[green]AUTO_AGENT[/] spawning '{backend_name}' with "
        f"slash command [bold]{slash_cmd}[/]"
    )
    # Phase model doesn't apply — the slash-command prompt goes to the
    # agent's own default model unless the operator passed --model.
    # Re-use ``_invoke_agent`` so error handling, manifest parsing, and
    # timeout semantics stay identical to the phase-driven path.
    _invoke_agent(
        slash_cmd,
        console,
        backend_name=backend_name,
        task_id="AUTO",
        phase="AUTO",
        model=model,
    )


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
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override default model for RED/GREEN/REFACTOR/EXECUTE phases",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help=(
            "Spawn the agent with the deviatdd skill invoked (slash command), "
            "instead of running an internal micro phase. Skips the normal "
            "RED/GREEN/JUDGE/REFACTOR orchestration. The agent runs the "
            "skill, which itself drives `deviate micro run` per task until "
            "the queue drains."
        ),
    ),
) -> None:
    """Use `deviate micro run --all` to drain the queue."""
    global _verbose, _cli_model_override
    _verbose = verbose
    _cli_model_override = model

    root = _resolve_workspace_root()
    session_path = root / ".deviate" / "session.json"
    agent = _resolve_agent_config(root, agent)

    # Note: HITL Gate 2 (plan/tasks approval) has been removed. Micro runs
    # as soon as it is invoked; session.json is still loaded for last_command
    # bookkeeping but is no longer a precondition.
    if session_path.exists():
        session = SessionState.load(session_path)
        cmd_parts = ["micro", "run"]
        if task_id:
            cmd_parts.append(task_id)
        if all_tasks:
            cmd_parts.append("--all")
        session.last_command = " ".join(cmd_parts)
        session.save(session_path)
        cmd_parts = ["micro", "run"]
        if task_id:
            cmd_parts.append(task_id)
        if all_tasks:
            cmd_parts.append("--all")
        session.last_command = " ".join(cmd_parts)
        session.save(session_path)

    if auto:
        # ``--auto`` short-circuits the normal RED/GREEN/JUDGE/REFACTOR
        # orchestration: instead of running one task phase locally, spawn
        # the configured agent with the deviatdd skill slash command as the
        # prompt. The agent then drives ``deviate micro run`` itself, per
        # the skill's per-task stepping loop, until the queue drains. The
        # runner here is the entry point — not a phase driver.
        _run_auto_agent(root, agent=agent, model=model)
        raise typer.Exit(code=0)

    if dry_run:
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
                task, path = _resolve_task_context(task_id, root)
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
                model=model,
            )
            raise typer.Exit(code=0)

        _run_single(
            task_id,
            root,
            console,
            no_judge=skip_judge,
            no_refactor=skip_refactor,
            agent=agent,
            model=model,
        )
    finally:
        run_logger.close()
        set_run_logger(None)
