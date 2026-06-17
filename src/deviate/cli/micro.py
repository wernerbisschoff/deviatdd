from __future__ import annotations

import ast
import importlib.resources
import json
import os
import re
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import typer
import yaml
from rich.console import Console

from deviate.core.agent import (
    BACKEND_COMMANDS,
    AgentBackend,
    AgentBinaryNotFoundError,
    AgentSubprocessError,
    AgentTimeoutError,
    EmptyOutputError,
    HandoverManifest,
    MalformedHandoverManifestError,
)
from deviate.core.cache_discipline import CacheDiscipline, CacheStore
from deviate.core.profile import resolve_profile
from deviate.core.tamper import TamperContext, TamperGuard, TamperVerdict
from deviate.core.worktree import find_worktree_for_branch
from deviate.prompts.assembly import assemble_prompt
from deviate.state.config import (
    AgentConfig,
    PytestReportConfig,
    SessionState,
    resolve_model_for_phase,
)
from deviate.ui.monitor import OrchestrationMonitor


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


def _log(msg: str) -> None:
    if _verbose:
        console.print(f"[dim]{msg}[/]")


def _save_agent_log(phase: str, task_id: str, label: str, content: str) -> None:
    log_dir = Path.cwd() / ".deviate"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "prompts.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"=== {timestamp} | {phase} | {task_id} | {label} ===\n")
        f.write(content)
        f.write("\n\n")


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
yellow_app = typer.Typer(no_args_is_help=True)
judge_app = typer.Typer(no_args_is_help=True)
refactor_app = typer.Typer(no_args_is_help=True)
execute_app = typer.Typer(no_args_is_help=True)
e2e_app = typer.Typer(no_args_is_help=True)
hotfix_app = typer.Typer(no_args_is_help=True)

_LEDGER_GLOB = "specs/**/tasks.jsonl"

_SKILL_NAMES: dict[str, str | None] = {
    "RED": "deviate-red",
    "GREEN": "deviate-green",
    "YELLOW": "deviate-yellow",
    "JUDGE": "deviate-judge",
    "REFACTOR": "deviate-refactor",
    "EXECUTE": "deviate-execute",
}


def _load_skill_content(phase_name: str) -> str | None:
    skill_name = _SKILL_NAMES.get(phase_name.upper())
    if not skill_name:
        return None
    try:
        path = importlib.resources.files("deviate.prompts.skills").joinpath(
            skill_name, "SKILL.md"
        )
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        fallback = Path("src/deviate/prompts/skills") / skill_name / "SKILL.md"
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
            sys.stdout.flush()
            return

        c.print(stripped[:600], style="dim", markup=False)

    return handler


def _invoke_agent(
    prompt: str,
    c: Console,
    backend_name: str = "opencode",
    task_id: str = "",
    phase: str = "",
    output_callback: Callable[[str], None] | None = None,
    model: str | None = None,
) -> tuple[HandoverManifest | None, str]:
    c.print(f"  [dim]Invoking agent ({backend_name})...[/]")
    _save_agent_log(phase, task_id, "prompt", prompt)
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
        _save_agent_log(phase, task_id, "manifest", manifest.model_dump_json())
        if raw_lines:
            _save_agent_log(phase, task_id, "raw_output", "\n".join(raw_lines))
        return manifest, ""
    except AgentBinaryNotFoundError:
        c.print(
            f"  [yellow]AGENT_NOT_AVAILABLE[/] {backend_name} not found on PATH, skipping"
        )
        return None, ""
    except AgentTimeoutError as exc:
        partial_output = exc.partial_stdout or ""
        if exc.partial_stderr:
            _save_agent_log(phase, task_id, "timeout_stderr", exc.partial_stderr)
        if partial_output:
            _save_agent_log(phase, task_id, "timeout_stdout", partial_output)
        c.print(f"  [yellow]AGENT_ERROR[/] {exc}")
        return None, partial_output
    except (
        AgentSubprocessError,
        MalformedHandoverManifestError,
        EmptyOutputError,
    ) as exc:
        c.print(f"  [yellow]AGENT_ERROR[/] {exc}")
        return None, ""
    except Exception as exc:
        c.print(f"  [yellow]AGENT_SKIP[/] {exc}")
        return None, ""


_YELLOW_DECISION_REJECTED = "rejected"
_YELLOW_DECISION_APPROVED = "approved"


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
    backend_name: str = "opencode",
) -> str:
    """Call the agent backend to summarize timeout partial output."""
    truncated = partial_output[-5000:] if len(partial_output) > 5000 else partial_output
    prompt = _TIMEOUT_SUMMARY_PROMPT.format(partial_text=truncated)
    backend_cmd = BACKEND_COMMANDS.get(backend_name, "opencode run")
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
            "Check prompts.log for partial output.]"
        )
    except FileNotFoundError:
        return (
            f"[Previous GREEN attempt timed out. Partial output (last {len(truncated)} chars):\n"
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
        c.print(f"  [dim]RED already done for {tid}, skipping[/]")
        return session
    c.print(f"  [bold blue]RED →[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()
    prompt = _build_auto_prompt("red", task, root)
    agent_output_callback = _make_agent_output_callback(monitor, tid, "RED")
    red_model = _resolve_model_for_phase("RED", root)
    manifest, _ = _invoke_agent(
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
        raise PhaseFailedError(
            f"RED phase failed for {tid}: {manifest.rationale or 'unknown'}"
        )
    if manifest.yellow_trigger:
        c.print(f"  [yellow]YELLOW_TRIGGERED[/] {tid}")

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

    _commit_phase(f"test({scope}): RED phase - failing test", root, no_verify=True)

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
            c.print(f"  [dim]GREEN already done for {tid}, skipping[/]")
            return session
        c.print(
            f"  [dim]GREEN already done for {tid}"
            f" but train_feedback present — re-running[/]"
        )
    c.print(f"  [bold green]GREEN →[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()
    prompt = _build_auto_prompt("green", task, root)
    if session.train_feedback:
        prompt += f"\n\n<train_feedback>\n{session.train_feedback}\n</train_feedback>\n"
    agent_output_callback = _make_agent_output_callback(monitor, tid, "GREEN")
    green_model = _resolve_model_for_phase("GREEN", root)
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
        raise PhaseFailedError(
            f"GREEN phase failed for {tid}: {manifest.rationale or 'unknown'}"
        )

    session = session.force_transition_to("GREEN")
    if manifest and manifest.yellow_trigger:
        c.print(f"  [yellow]YELLOW_TRIGGERED[/] {tid}")
        session.yellow_triggered = True
    session.train_feedback = ""
    session.save(session_path)

    issue_id = task.get("issue_id", "")
    scope = _build_scope(issue_id, tid)

    _run_test_cmd(root)
    _run_format_cmd(root)

    try:
        record = TaskRecord.model_validate(task)
        record.status = "GREEN"
        append_task_transition(record, ledger_path)
    except Exception as e:
        raise PhaseFailedError(f"GREEN phase ledger update failed for {tid}: {e}")

    _commit_phase(f"feat({scope}): GREEN phase - implementation", root)

    try:
        _verify_clean_worktree(root, "GREEN", tid)
    except PhaseFailedError as e:
        c.print(f"  [red]CLEAN_WORKTREE_FAILED[/] {e}")
        subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            cwd=Path.cwd(),
            capture_output=True,
            env=_git_env(),
        )
        session = session.force_transition_to("RED")
        session.train_feedback = str(e)
        session.yellow_triggered = False
        session.save(session_path)
        return session
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


def _append_judge_feedback(tasks_md: Path, task_id: str, feedback: str) -> None:
    content = tasks_md.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines: list[str] = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and task_id in line and line.strip().startswith("-"):
            indent = "  "
            for fb_line in feedback.strip().splitlines():
                new_lines.append(f"{indent}- **Judge Feedback**: {fb_line}")
                indent = "    "
            inserted = True
    if inserted:
        tasks_md.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _resolve_red_boundary_sha(root: Path) -> str:
    session_path = root / ".deviate" / "session.json"
    if session_path.exists():
        session = SessionState.load(session_path)
        if session.red_commit_sha:
            return session.red_commit_sha
    _log("No RED commit SHA in session — falling back to root commit scan")
    root_sha = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    has_content = subprocess.run(
        ["git", "ls-tree", "-r", root_sha],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    if has_content:
        return root_sha
    children = (
        subprocess.run(
            ["git", "rev-list", "--reverse", f"{root_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        .stdout.strip()
        .splitlines()
    )
    return children[0] if children else root_sha


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

    # Hard reset to RED boundary — discards GREEN's unverified implementation
    subprocess.run(
        ["git", "reset", "--hard", red_sha],
        cwd=root,
        capture_output=True,
        env=_git_env(),
    )
    return red_sha


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
    c.print(f"  [bold magenta]JUDGE →[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()

    diff = subprocess.run(
        ["git", "diff", "HEAD~1..HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout

    prompt = _build_auto_prompt("judge", task, root)
    prompt += f"\n\n<diff>\n{diff}\n</diff>\n"

    agent_output_callback = _make_agent_output_callback(monitor, tid, "JUDGE")
    judge_model = _resolve_model_for_phase("JUDGE", root)
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
    if verdict.upper() == "COMPLIANCE_VIOLATION":
        c.print(f"  [red]JUDGE_REJECTED[/] {tid}: {manifest.rationale or ''}")

        feedback = manifest.rationale or ""
        if hasattr(manifest, "train_feedback") and manifest.train_feedback:
            feedback = manifest.train_feedback

        try:
            _execute_rollback(root, feedback)
        except Exception as e:
            c.print(
                f"  [yellow]ROLLBACK_FAILED[/] {e} — proceeding with train feedback"
            )

        tasks_md = _resolve_tasks_md(root, task)
        if tasks_md is not None:
            _append_judge_feedback(tasks_md, tid, feedback)
            subprocess.run(
                ["git", "add", "-A"],
                cwd=root,
                capture_output=True,
                env=_git_env(),
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"docs({tid}): add judge feedback for GREEN retry",
                ],
                cwd=root,
                capture_output=True,
                env=_git_env(),
            )

        session = session.force_transition_to("GREEN")
        session.train_feedback = feedback
        session.yellow_triggered = False
        session.save(session_path)
        return session

    session = session.force_transition_to("JUDGE")
    session.train_feedback = ""
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
        c.print(f"  [dim]Already completed for {tid}, skipping[/]")
        return session
    c.print(f"  [bold green]REFACTOR →[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()
    prompt = _build_auto_prompt("refactor", task, root)
    agent_output_callback = _make_agent_output_callback(monitor, tid, "REFACTOR")
    refactor_model = _resolve_model_for_phase("REFACTOR", root)
    manifest, _ = _invoke_agent(
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
        raise PhaseFailedError(
            f"REFACTOR phase failed for {tid}: {manifest.rationale or 'unknown'}"
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

    _commit_phase(f"refactor({scope}): REFACTOR phase - cleanup", root)

    session = session.force_transition_to("IDLE")
    session.yellow_triggered = False
    session.save(session_path)
    _verify_clean_worktree(root, "REFACTOR", tid)
    c.print(f"  [bold green]COMPLETED[/] {tid}")
    return session


def _run_yellow_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
    monitor: OrchestrationMonitor | None = None,
) -> tuple[SessionState, str]:
    tid = task.get("id", "?")
    c.print(f"  [bold magenta]YELLOW →[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()
    prompt = _build_auto_prompt("yellow", task, root)
    agent_output_callback = _make_agent_output_callback(monitor, tid, "YELLOW")
    yellow_model = _resolve_model_for_phase("YELLOW", root)
    manifest, _ = _invoke_agent(
        prompt,
        c,
        backend_name=backend,
        task_id=tid,
        phase="YELLOW",
        output_callback=agent_output_callback,
        model=yellow_model,
    )
    if manifest is None:
        raise PhaseFailedError(
            f"YELLOW phase agent error for {tid}: agent returned no manifest"
        )
    verdict = getattr(manifest, "verdict", "")
    if verdict.upper() == "REJECTED":
        c.print(f"  [yellow]YELLOW_REJECTED[/] {tid}: {manifest.rationale or ''}")
        subprocess.run(
            ["git", "restore", "."],
            cwd=Path.cwd(),
            env=_git_env(),
            check=False,
        )
        c.print("  [dim]Reverted test changes, re-running GREEN[/]")
        _append_status_transition(task, "YELLOW_REJECTED", ledger_path)
        return session, _YELLOW_DECISION_REJECTED

    session = session.force_transition_to("YELLOW")
    session.yellow_triggered = False
    session.save(session_path)
    _append_status_transition(task, "YELLOW_APPROVED", ledger_path)
    return session, _YELLOW_DECISION_APPROVED


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
    if not no_refactor:
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
    else:
        _append_status_transition(task, "COMPLETED", ledger_path)
        c.print(f"  [bold green]COMPLETED[/] {tid}")
        session = session.force_transition_to("IDLE")
        session.yellow_triggered = False
        session.train_feedback = ""
        session.save(session_path)
    return session


def _capture_cache_store(root: Path, task: dict, agent: str | None) -> CacheStore:
    model = agent or "opencode"
    test_files: dict[str, str] = {}
    tests_dir = root / "tests"
    if tests_dir.exists():
        for tf in sorted(tests_dir.rglob("test_*.py")):
            try:
                test_files[str(tf.relative_to(root))] = tf.read_text(encoding="utf-8")
            except Exception:
                pass
    return CacheStore(
        model=model,
        tool_definitions=[],
        system_prompt="",
        test_files=test_files,
    )


def _validate_cache_store(
    phase: str,
    root: Path,
    task: dict,
    agent: str | None,
    previous: CacheStore | None,
) -> CacheStore:
    current = _capture_cache_store(root, task, agent)
    CacheDiscipline.validate(phase=phase, current=current, previous=previous)
    return current


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
        c.print(f"  [dim]Already completed for {tid}, skipping[/]")
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
        cache_store = _capture_cache_store(root, task, agent)
        session = _finish_tdd_cycle(
            task, ledger_path, session, session_path, c, no_refactor, agent=agent
        )
        return

    if start_phase == "YELLOW":
        cache_store = _capture_cache_store(root, task, agent)
        _maybe_push_event(
            monitor,
            "phase_change",
            task_id=tid,
            phase="YELLOW",
            description=task_desc,
        )
        session, _ = _run_yellow_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )
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
        cache_store = _capture_cache_store(root, task, agent)
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
        return

    _maybe_push_event(
        monitor, "phase_change", task_id=tid, phase="RED", description=task_desc
    )
    session = _run_red_phase(
        task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
    )
    cache_store = _capture_cache_store(root, task, agent)

    train_attempts = 0
    max_train_attempts = 3
    judge_passed = no_judge

    while not judge_passed:
        cache_store = _capture_cache_store(root, task, agent)
        _maybe_push_event(
            monitor, "phase_change", task_id=tid, phase="GREEN", description=task_desc
        )
        session = _run_green_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )

        if session.yellow_triggered:
            cache_store = _capture_cache_store(root, task, agent)
            _maybe_push_event(
                monitor,
                "phase_change",
                task_id=tid,
                phase="YELLOW",
                description=task_desc,
            )
            session, decision = _run_yellow_phase(
                task,
                ledger_path,
                session,
                session_path,
                c,
                agent=agent,
                monitor=monitor,
            )
            if decision == _YELLOW_DECISION_REJECTED:
                c.print("  [yellow]Re-running GREEN after YELLOW[/]")
                cache_store = _capture_cache_store(root, task, agent)
                _maybe_push_event(
                    monitor,
                    "phase_change",
                    task_id=tid,
                    phase="GREEN",
                    description=task_desc,
                )
                session = _run_green_phase(
                    task,
                    ledger_path,
                    session,
                    session_path,
                    c,
                    agent=agent,
                    monitor=monitor,
                )

        if session.train_feedback:
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
                f"  [yellow]TRAIN ({train_attempts}/{max_train_attempts})"
                f" — GREEN phase post-cleanup failed, retrying with feedback[/]"
            )
            continue

        if no_judge:
            judge_passed = True
            break

        cache_store = _capture_cache_store(root, task, agent)
        _maybe_push_event(
            monitor, "phase_change", task_id=tid, phase="JUDGE", description=task_desc
        )
        session = _run_judge_phase(
            task, ledger_path, session, session_path, c, agent=agent, monitor=monitor
        )

        if session.train_feedback:
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
            c.print(
                f"  [yellow]TRAIN ({train_attempts}/{max_train_attempts})"
                f" — re-running GREEN with judge feedback[/]"
            )
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
    c.print(f"  [bold green]EXECUTE \u2192[/] {tid}")

    backend = agent or "opencode"
    root = Path.cwd()

    spec_content = _resolve_spec_md(root, task)
    has_spec = bool(spec_content)
    train_feedback = ""
    max_judge_attempts = 3
    execute_model = _resolve_model_for_phase("EXECUTE", root)

    for attempt in range(max_judge_attempts):
        prompt = _build_auto_prompt("execute", task, root)
        if train_feedback:
            prompt += f"\n\n<train_feedback>\n{train_feedback}\n</train_feedback>\n"

        agent_output_callback = _make_agent_output_callback(monitor, tid, "EXECUTE")
        manifest, _ = _invoke_agent(
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
            raise PhaseFailedError(
                f"EXECUTE phase failed for {tid}: {manifest.rationale or 'unknown'}"
            )

        issue_id = task.get("issue_id", "")
        scope = _build_scope(issue_id, tid)
        _commit_phase(f"feat({scope}): EXECUTE phase - {tid}", root)

        _verify_clean_worktree(root, "EXECUTE", tid)

        if not has_spec:
            break

        diff = subprocess.run(
            ["git", "diff", "HEAD~1..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        if not diff.strip():
            c.print(f"  [dim]JUDGE_SKIP \u2014 no diff in commit for {tid}[/]")
            break

        c.print(f"  [bold magenta]JUDGE \u2192[/] {tid} (spec compliance)")
        judge_prompt = _build_auto_prompt("judge", task, root)
        judge_prompt += f"\n\n<diff>\n{diff}\n</diff>\n"

        judge_manifest, _ = _invoke_agent(
            judge_prompt,
            c,
            backend_name=backend,
            task_id=tid,
            phase="JUDGE",
        )

        if judge_manifest is None:
            raise PhaseFailedError(
                f"JUDGE phase agent error for {tid}: agent returned no manifest"
            )

        verdict = getattr(judge_manifest, "verdict", "")
        if verdict.upper() == "COMPLIANCE_VIOLATION":
            feedback = judge_manifest.rationale or ""
            tf = getattr(judge_manifest, "train_feedback", None)
            if tf:
                feedback = tf

            c.print(f"  [red]JUDGE_REJECTED[/] {tid}: {feedback[:200]}")

            try:
                _execute_rollback(root, feedback)
            except Exception as e:
                c.print(f"  [yellow]ROLLBACK_FAILED[/] {e} — proceeding with retry")

            if attempt < max_judge_attempts - 1:
                train_feedback = feedback
                c.print(
                    f"  [yellow]RETRY EXECUTE ({attempt + 2}/{max_judge_attempts})[/]"
                )
                continue
            raise PhaseFailedError(
                f"EXECUTE phase failed for {tid} "
                f"after {max_judge_attempts} JUDGE attempts: {feedback}"
            )

        break

    c.print(f"  [bold green]COMPLETED[/] {tid}")
    try:
        record = TaskRecord.model_validate(task)
        record.status = "COMPLETED"
        append_task_transition(record, ledger_path)
    except Exception as e:
        c.print(f"  [yellow]LEDGER_UPDATE_FAILED[/] {e}")


class PhaseFailedError(Exception):
    pass


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
    c.print(f"[cyan]Processing {task.get('id', '?')} ({mode})[/]")

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
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
) -> bool:
    tid = task.get("id", "?")
    monitor.push_event(
        "task_started", task_id=tid, description=task.get("description", "")
    )
    for attempt in range(2):
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
            monitor.push_event(
                "task_completed",
                task_id=tid,
                phase=monitor.get_task_phase(tid),
                status="completed",
            )
            return True
        except Exception as exc:
            if attempt == 1:
                c.print(f"  [red]FAILED[/] {tid} after 2 attempts: {exc}")
                monitor.push_event("task_failed", task_id=tid, error_reason=str(exc))
                _append_status_transition(task, "FAILED", ledger_file)
                return False
            c.print(f"  [yellow]RETRY[/] {tid} (attempt {attempt + 2})")


def _run_all(
    root: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
    json_mode: bool = False,
) -> None:
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

    monitor = OrchestrationMonitor(c, json_mode=json_mode, total_tasks=len(pending))

    any_failed = False
    try:
        with monitor:
            for task, ledger_file in pending:
                if not _execute_task_with_retry(
                    task,
                    ledger_file,
                    c,
                    monitor,
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
    except KeyboardInterrupt:
        monitor.signal_keyboard_interrupt()
        raise typer.Exit(code=130)

    total = len(pending)
    pipeline_status = (
        "interrupted"
        if monitor.interrupted
        else ("halted" if any_failed else "completed")
    )
    monitor.push_event(
        "pipeline_complete",
        total=total,
        failed=monitor.failed_count,
        status=pipeline_status,
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


def _commit_phase(message: str, root: Path, no_verify: bool = False) -> bool:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root, env=_git_env()
    )
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, env=_git_env())
    if staged.returncode != 0 or unstaged.returncode != 0:
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)
        cmd = ["git", "commit", "-m", message]
        if no_verify:
            cmd.append("--no-verify")
        result = subprocess.run(
            cmd,
            cwd=root,
            env=_git_env(),
        )
        if result.returncode != 0:
            console.print("[red]COMMIT_FAILED[/]")
            return False
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
        log_dir = root / ".deviate"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "prompts.log"
        timestamp = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"=== {timestamp} | {phase} | {tid} | POST_CMD_FAILURE ===\n")
            f.write(f"{len(files)} uncommitted file(s):\n")
            for line in files:
                f.write(f"  {line}\n")
            f.write("\n")
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

    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": "mise run test",
        "lint_command": "mise run lint",
        "spec_dir": spec_dir,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


def _run_test_cmd(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["mise", "run", "test"],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _run_format_cmd(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["mise", "run", "format"],
        cwd=root,
        capture_output=True,
        text=True,
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
    _commit_phase(f"test({scope}): RED phase - failing test", root, no_verify=True)

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

    tamper_verdict = TamperGuard.evaluate(
        context=TamperContext.GREEN_IMPLEMENTATION, repo_path=root
    )

    if tamper_verdict == TamperVerdict.TAMPER_DETECTED:
        console.print("[yellow]TAMPER_DETECTED[/]")
        console.print("[yellow]YELLOW_TRIGGERED[/]")
        # Transition to YELLOW and append YELLOW to ledger,
        # bypassing the normal GREEN commit flow.
        try:
            record = TaskRecord.model_validate(red_task[0])
            record.status = "YELLOW"
            append_task_transition(record, red_task[1])
        except Exception as e:
            console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
            raise typer.Exit(code=1)
        session = session.force_transition_to("YELLOW")
        session.save(session_path)
        raise typer.Exit(code=0)

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


@yellow_app.command(name="pre")
def yellow_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    _resolve_task_context(task, root)

    if not _load_skill_content("YELLOW"):
        console.print("[yellow]SKILL_NOT_FOUND[/] deviate-yellow")

    changed = _detect_phase_changes(root)
    test_files = [str(f) for f in _find_test_files(root)]

    contract = {
        "proposed_changes": changed,
        "rationale": "YELLOW phase - review proposed test amendments",
        "test_files": test_files,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@yellow_app.command(name="post")
def yellow_post(
    approved: bool = typer.Option(False, "--approved", help="Approve amendments"),
    rejected: bool = typer.Option(False, "--rejected", help="Reject amendments"),
) -> None:
    if approved and rejected:
        console.print(
            "[red]MUTUALLY_EXCLUSIVE[/] --approved and --rejected cannot both be set"
        )
        raise typer.Exit(code=1)

    root = Path.cwd()

    if not _load_skill_content("YELLOW"):
        console.print("[yellow]SKILL_NOT_FOUND[/] deviate-yellow")

    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    changed = _detect_phase_changes(root)

    if not changed:
        console.print("NO_CHANGES_PROPOSED")
        raise typer.Exit(code=0)

    # Find latest YELLOW or GREEN task across all ledger files
    latest_task: tuple[dict, Path] | None = None
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for rec in _read_ledger_records(ledger_file):
            if rec.get("status") in ("GREEN", "YELLOW"):
                latest_task = (rec, ledger_file)

    if approved:
        _commit_phase("feat: YELLOW phase - approved amendments", root)
        if latest_task is not None:
            _append_status_transition(latest_task[0], "YELLOW_APPROVED", latest_task[1])
        session = session.force_transition_to("JUDGE")
        session.save(session_path)
        console.print("[green]YELLOW_POST_OK[/]")

    if rejected:
        subprocess.run(["git", "restore", "."], cwd=root, env=_git_env(), check=False)
        if latest_task is not None:
            _append_status_transition(latest_task[0], "YELLOW_REJECTED", latest_task[1])
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        console.print("[yellow]YELLOW_REVERTED[/]")

    raise typer.Exit(code=0)


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


def _classify_expression_returns(value: ast.expr, expected: str) -> list[str]:
    """Walk return expressions and flag obvious constant/literal mismatches.

    Only flags literal constants and collection literals whose type doesn't
    match the annotation.  Complex expressions (calls, attributes, names)
    are assumed correct — the checker cannot statically resolve them.
    """
    issues: list[str] = []

    scalar_types = {"str": str, "int": int, "float": (int, float), "bool": bool}
    collection_nodes = {
        "list": ast.List,
        "dict": ast.Dict,
        "tuple": ast.Tuple,
        "set": ast.Set,
    }

    if isinstance(value, ast.Constant):
        if expected in scalar_types:
            if not isinstance(value.value, scalar_types[expected]):
                issues.append(
                    f"expected {expected}, got literal {type(value.value).__name__}"
                )
        elif expected in collection_nodes:
            issues.append(f"expected {expected}, got literal constant")

    elif isinstance(value, ast.JoinedStr):
        if expected != "str":
            issues.append(f"expected {expected}, got f-string (str)")

    else:
        for type_name, node_class in collection_nodes.items():
            if isinstance(value, node_class) and expected != type_name:
                issues.append(f"expected {expected}, got {type_name} literal")

    return issues


def _check_return_type_mismatch(filepath: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.returns is None:
            continue

        return_annotation: str | None = None
        if isinstance(node.returns, ast.Name):
            return_annotation = node.returns.id
        elif isinstance(node.returns, ast.Constant) and isinstance(
            node.returns.value, str
        ):
            return_annotation = node.returns.value

        if return_annotation is None:
            continue

        # Only validate known builtin types
        known = {"str", "int", "float", "bool", "list", "dict", "tuple", "set"}
        if return_annotation not in known:
            continue

        for child in ast.walk(node):
            if not isinstance(child, ast.Return) or child.value is None:
                continue
            issues.extend(_classify_expression_returns(child.value, return_annotation))
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
    session.yellow_triggered = False
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
        session.yellow_triggered = False
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
    """Resolve agent backend from CLI arg or config.toml fallback."""
    if agent is not None:
        return agent
    config_path = root / ".deviate" / "config.toml"
    if not config_path.exists():
        return None
    try:
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("agent", {}).get("backend") or None
    except Exception:
        return None


def _resolve_model_for_phase(phase: str, root: Path) -> str | None:
    return resolve_model_for_phase(phase, root)


def _validate_profile(value: str) -> str:
    """Typer callback: validate profile via resolve_profile, emit Typer error."""
    try:
        resolve_profile(value)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    return value


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
    """Run dispatcher: route task by execution_mode to TDD cycle or execute phase.

    When called without arguments, picks the next PENDING task for the active issue.
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
        cmd_parts = ["run"]
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
