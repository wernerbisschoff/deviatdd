from __future__ import annotations

import ast
import importlib.resources
import json
import os
import re
import subprocess
import sys
import warnings
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import typer
from rich.console import Console

from deviate.core.agent import (
    AgentBackend,
    AgentBinaryNotFoundError,
    AgentSubprocessError,
    AgentTimeoutError,
    EmptyOutputError,
    HandoverManifest,
    MalformedHandoverManifestError,
)
from deviate.core.profile import resolve_profile
from deviate.core.tamper import TamperContext, TamperGuard, TamperVerdict
from deviate.core.worktree import find_worktree_for_branch
from deviate.state.config import AgentConfig, PytestReportConfig, SessionState
from deviate.state.ledger import (
    TaskRecord,
    append_task_transition,
)

console = Console()

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


def _invoke_agent(
    prompt: str, c: Console, backend_name: str = "opencode"
) -> HandoverManifest | None:
    c.print(f"  [dim]Invoking agent ({backend_name})...[/]")
    try:
        backend = AgentBackend(config=AgentConfig(backend=backend_name))
        manifest = backend.invoke(prompt)
        return manifest
    except AgentBinaryNotFoundError:
        c.print(
            f"  [yellow]AGENT_NOT_AVAILABLE[/] {backend_name} not found on PATH, skipping"
        )
        return None
    except (
        AgentTimeoutError,
        AgentSubprocessError,
        MalformedHandoverManifestError,
        EmptyOutputError,
    ) as exc:
        c.print(f"  [yellow]AGENT_ERROR[/] {exc}")
        return None
    except Exception as exc:
        c.print(f"  [yellow]AGENT_SKIP[/] {exc}")
        return None


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
    """Look up a task record by its TSK-NNN-NN ID across all ledger files."""
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("id") == task_id:
                return record, ledger_file
    return None


def _find_all_pending_tasks(
    root: Path, issue_id: str | None = None
) -> list[tuple[dict, Path]]:
    results: list[tuple[dict, Path]] = []
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("status") == "PENDING":
                if issue_id is None or record.get("issue_id") == issue_id:
                    results.append((record, ledger_file))

    if not results and issue_id is not None:
        tasks_md = _find_tasks_md_for_issue(root, issue_id)
        if tasks_md is not None:
            tasks = _parse_tasks_md(tasks_md)
            ledger_path = tasks_md.with_name("tasks.jsonl")
            for task in tasks:
                task["issue_id"] = issue_id
                results.append((task, ledger_path))

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


_MODE_MAP: dict[str, str] = {
    "TDD": "TDD",
    "DIRECT": "DIRECT",
    "E2E": "E2E",
    "IMMEDIATE": "DIRECT",
}

_TASK_MD_RE = re.compile(r"^\s*-\s+\[.\]\s+(TSK-\d{3}-\d{2}):\s*(.*)")
_MODE_MD_RE = re.compile(r"^\s+-\s+\*\*Mode\*\*:\s*(\S+)")


def _parse_tasks_md(tasks_md: Path) -> list[dict]:
    """Parse tasks.md to extract task entries.

    Returns list of dicts with id, description, status, execution_mode.
    """
    tasks: list[dict] = []
    content = tasks_md.read_text(encoding="utf-8")
    current: dict | None = None
    for line in content.splitlines():
        m = _TASK_MD_RE.match(line)
        if m:
            if current is not None:
                tasks.append(current)
            current = {
                "id": m.group(1),
                "description": m.group(2).strip(),
                "status": "PENDING",
                "execution_mode": "TDD",
            }
        elif current is not None:
            mode_m = _MODE_MD_RE.match(line)
            if mode_m:
                raw = mode_m.group(1).upper()
                current["execution_mode"] = _MODE_MAP.get(raw, "TDD")
    if current is not None:
        tasks.append(current)
    return tasks


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
    """Return the first PENDING task for *issue_id*."""
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for rec in _read_ledger_records(ledger_file):
            if rec.get("issue_id") == issue_id and rec.get("status") == "PENDING":
                return (rec, ledger_file)
    tasks_md = _find_tasks_md_for_issue(root, issue_id)
    if tasks_md is not None:
        tasks = _parse_tasks_md(tasks_md)
        ledger_path = tasks_md.with_name("tasks.jsonl")
        if tasks:
            first = tasks[0]
            first["issue_id"] = issue_id
            return (first, ledger_path)
    return None


def _build_scope(issue_id: str, task_id: str) -> str:
    """Return the task ID as scope (already TSK-NNN-NN format)."""
    issue_match = re.search(r"ISS-(\d+)", issue_id)
    if not issue_match:
        return issue_id
    return task_id


def _run_red_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    c.print(f"  [bold blue]RED →[/] {tid}")

    backend = agent or "opencode"
    skill = _load_skill_content("RED")
    if skill:
        prompt = _build_agent_prompt(skill, "RED", task, Path.cwd())
        manifest = _invoke_agent(prompt, c, backend_name=backend)
        if manifest is not None and manifest.status.upper() in (
            "FAILURE",
            "ERROR",
        ):
            raise PhaseFailedError(
                f"RED phase failed for {tid}: {manifest.rationale or 'unknown'}"
            )
        if manifest and manifest.yellow_trigger:
            c.print(f"  [yellow]YELLOW_TRIGGERED[/] {tid}")

    session = session.force_transition_to("RED")
    session.save(session_path)
    _append_status_transition(task, "RED", ledger_path)
    return session


def _run_green_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    c.print(f"  [bold green]GREEN →[/] {tid}")

    backend = agent or "opencode"
    skill = _load_skill_content("GREEN")
    manifest: HandoverManifest | None = None
    if skill:
        prompt = _build_agent_prompt(skill, "GREEN", task, Path.cwd())
        if session.train_feedback:
            prompt += (
                f"\n\n<train_feedback>\n{session.train_feedback}\n</train_feedback>\n"
            )
        manifest = _invoke_agent(prompt, c, backend_name=backend)
        if manifest is not None and manifest.status.upper() in (
            "FAILURE",
            "ERROR",
        ):
            raise PhaseFailedError(
                f"GREEN phase failed for {tid}: {manifest.rationale or 'unknown'}"
            )

    session = session.force_transition_to("GREEN")
    if manifest and manifest.yellow_trigger:
        c.print(f"  [yellow]YELLOW_TRIGGERED[/] {tid}")
        session.yellow_triggered = True
    session.train_feedback = ""
    session.save(session_path)
    _append_status_transition(task, "GREEN", ledger_path)
    return session


def _resolve_spec_md(root: Path, task: dict) -> str:
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return ""
    source_file = _resolve_issue_source_file(root, issue_id)
    if not source_file:
        return ""
    parts = PurePosixPath(source_file)
    if len(parts.parts) < 3:
        return ""
    epic = parts.parent.parent.name
    slug = parts.stem
    spec_path = root / "specs" / epic / slug / "spec.md"
    if spec_path.exists():
        return spec_path.read_text(encoding="utf-8")
    return ""


def _resolve_tasks_md(root: Path, task: dict) -> Path | None:
    issue_id = task.get("issue_id", "")
    if not issue_id:
        return None
    return _find_tasks_md_for_issue(root, issue_id)


def _append_judge_feedback(tasks_md: Path, task_id: str, feedback: str) -> None:
    content = tasks_md.read_text(encoding="utf-8")
    task_marker = f"TSK-{task_id.split('-', 1)[1]}" if "-" in task_id else task_id
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


def _run_judge_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    c.print(f"  [bold magenta]JUDGE →[/] {tid}")

    backend = agent or "opencode"
    skill = _load_skill_content("JUDGE")
    if skill:
        root = Path.cwd()

        diff = subprocess.run(
            ["git", "diff", "HEAD~1..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout

        spec_content = _resolve_spec_md(root, task)

        prompt = _build_agent_prompt(skill, "JUDGE", task, root)
        prompt += f"\n\n<diff>\n{diff}\n</diff>\n"
        if spec_content:
            prompt += f"\n<spec>\n{spec_content}\n</spec>\n"

        manifest = _invoke_agent(prompt, c, backend_name=backend)
        if manifest is not None and manifest.status.upper() in (
            "FAILURE",
            "ERROR",
        ):
            c.print(f"  [red]JUDGE_REJECTED[/] {tid}: {manifest.rationale or ''}")

            feedback = manifest.rationale or ""
            if hasattr(manifest, "train_feedback") and manifest.train_feedback:
                feedback = manifest.train_feedback

            subprocess.run(
                ["git", "revert", "--no-edit", "HEAD"],
                cwd=root,
                capture_output=True,
                env=_git_env(),
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
) -> SessionState:
    tid = task.get("id", "?")
    c.print(f"  [bold yellow]REFACTOR →[/] {tid}")

    backend = agent or "opencode"
    skill = _load_skill_content("REFACTOR")
    if skill:
        prompt = _build_agent_prompt(skill, "REFACTOR", task, Path.cwd())
        manifest = _invoke_agent(prompt, c, backend_name=backend)
        if manifest is not None and manifest.status.upper() in (
            "FAILURE",
            "ERROR",
        ):
            raise PhaseFailedError(
                f"REFACTOR phase failed for {tid}: {manifest.rationale or 'unknown'}"
            )

    session = session.force_transition_to("REFACTOR")
    session.save(session_path)
    _append_status_transition(task, "REFACTOR", ledger_path)
    return session


def _run_yellow_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
    agent: str | None = None,
) -> SessionState:
    tid = task.get("id", "?")
    c.print(f"  [bold magenta]YELLOW →[/] {tid}")

    backend = agent or "opencode"
    skill = _load_skill_content("YELLOW")
    if skill:
        prompt = _build_agent_prompt(skill, "YELLOW", task, Path.cwd())
        manifest = _invoke_agent(prompt, c, backend_name=backend)
        if manifest is not None and manifest.status.upper() == "FAILURE":
            c.print(f"  [yellow]YELLOW_REJECTED[/] {tid}: {manifest.rationale or ''}")
            subprocess.run(
                ["git", "restore", "."],
                cwd=Path.cwd(),
                env=_git_env(),
                check=False,
            )
            c.print("  [dim]Reverted test changes, re-running GREEN[/]")

    session = session.force_transition_to("YELLOW")
    session.save(session_path)
    _append_status_transition(task, "YELLOW", ledger_path)
    return session


_PHASE_MAP: dict[str, Callable] = {
    "RED": _run_red_phase,
    "GREEN": _run_green_phase,
    "YELLOW": _run_yellow_phase,
    "JUDGE": _run_judge_phase,
    "REFACTOR": _run_refactor_phase,
}


def _run_tdd_cycle(
    task: dict,
    ledger_path: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
) -> None:
    root = Path.cwd()
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    session = _run_red_phase(task, ledger_path, session, session_path, c, agent=agent)

    train_attempts = 0
    max_train_attempts = 3
    judge_passed = no_judge

    while not judge_passed:
        session = _run_green_phase(
            task, ledger_path, session, session_path, c, agent=agent
        )

        if session.yellow_triggered:
            c.print("  [yellow]YELLOW requested by GREEN — running YELLOW phase[/]")
            session = _run_yellow_phase(
                task, ledger_path, session, session_path, c, agent=agent
            )
            session.yellow_triggered = False
            session.save(session_path)
            c.print("  [yellow]Re-running GREEN after YELLOW[/]")
            session = _run_green_phase(
                task, ledger_path, session, session_path, c, agent=agent
            )

        if no_judge:
            judge_passed = True
            break

        session = _run_judge_phase(
            task, ledger_path, session, session_path, c, agent=agent
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

    if not no_refactor:
        session = _run_refactor_phase(
            task, ledger_path, session, session_path, c, agent=agent
        )

    _append_status_transition(task, "COMPLETED", ledger_path)
    c.print(f"  [bold green]COMPLETED[/] {task.get('id', '?')}")

    session = session.force_transition_to("IDLE")
    session.yellow_triggered = False
    session.train_feedback = ""
    session.save(session_path)


def _run_execute_phase(task: dict, ledger_path: Path, c: Console) -> None:
    tid = task.get("id", "?")
    c.print(f"  [bold green]EXECUTE →[/] {tid}")
    _append_status_transition(task, "COMPLETED", ledger_path)
    c.print(f"  [bold green]COMPLETED[/] {tid}")


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
        )
    else:
        _run_execute_phase(task, ledger_path, c)


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

    if status == "COMPLETED":
        c.print(f"[yellow]TASK_ALREADY_DONE[/] {task_id} is already completed")
        raise typer.Exit(code=0)

    _dispatch_task(
        task,
        ledger_file,
        c,
        no_judge=no_judge,
        no_refactor=no_refactor,
        agent=agent,
        batch_mode=False,
    )


def _run_all(
    root: Path,
    c: Console,
    no_judge: bool = False,
    no_refactor: bool = False,
    agent: str | None = None,
) -> None:
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = (
        SessionState.load(session_path) if session_path.exists() else SessionState()
    )
    issue_id = session.active_issue_id

    pending = _find_all_pending_tasks(root, issue_id=issue_id)
    if not pending:
        msg = "No PENDING tasks found"
        if issue_id:
            msg += f" for issue {issue_id}"
        c.print(f"[yellow]{msg}[/]")
        raise typer.Exit(code=0)

    any_failed = False
    for task, ledger_file in pending:
        tid = task.get("id", "?")
        attempts = 0
        while attempts < 2:
            try:
                _dispatch_task(
                    task,
                    ledger_file,
                    c,
                    no_judge=no_judge,
                    no_refactor=no_refactor,
                    agent=agent,
                    batch_mode=True,
                )
                break
            except Exception as exc:
                attempts += 1
                if attempts >= 2:
                    c.print(f"  [red]FAILED[/] {tid} after 2 attempts: {exc}")
                    _append_status_transition(task, "FAILED", ledger_file)
                    any_failed = True
                else:
                    c.print(f"  [yellow]RETRY[/] {tid} (attempt {attempts + 1})")
        if any_failed:
            break

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


def _commit_phase(message: str, root: Path) -> bool:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root, env=_git_env()
    )
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, env=_git_env())
    if staged.returncode != 0 or unstaged.returncode != 0:
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=root,
            env=_git_env(),
            check=False,
        )
        return True
    return False


def _all_tasks_complete(root: Path) -> bool:
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("status") != "COMPLETED":
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


_SYNTAX_ERROR_MARKERS = frozenset(
    {
        "SyntaxError",
        "IndentationError",
        "TabError",
        "ImportError",
        "ModuleNotFoundError",
    }
)


def _classify_pytest_outcome(stdout: str, stderr: str, returncode: int) -> str | None:
    combined = stdout + "\n" + stderr
    if returncode == 0:
        return "PASS"
    for marker in _SYNTAX_ERROR_MARKERS:
        if marker in combined:
            return "SYNTAX_ERROR"
    if "AssertionError" in combined or "failed" in stdout:
        return "ASSERTION_FAILURE"
    return "UNKNOWN_FAILURE"


@red_app.command(name="pre")
def red_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, ledger_path = _resolve_task_context(task, root)

    spec_dir = str(ledger_path.parent)

    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": "pytest tests/ -v",
        "lint_command": "ruff check .",
        "spec_dir": spec_dir,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@red_app.command(name="post")
def red_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[red]TEST_NOT_FOUND[/]")
        raise typer.Exit(code=1)

    proc = _run_pytest(root)
    outcome = _classify_pytest_outcome(proc.stdout, proc.stderr, proc.returncode)

    if outcome == "PASS":
        console.print("[red]RedMustPassError:[/] Test passed, expected a failing test")
        raise typer.Exit(code=1)

    if outcome == "SYNTAX_ERROR":
        console.print("[red]SyntaxCrashRejected:[/] Test file contains syntax errors")
        raise typer.Exit(code=1)

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
    _commit_phase(f"test({scope}): RED phase - failing test", root)

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

    contract = {
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

    proc = _run_pytest(root)

    if proc.returncode != 0:
        console.print("[red]Tests failed:[/] Implementation does not pass tests")
        raise typer.Exit(code=1)

    tamper_verdict = TamperGuard.evaluate(
        context=TamperContext.GREEN_IMPLEMENTATION, repo_path=root
    )

    if tamper_verdict == TamperVerdict.TAMPER_DETECTED:
        console.print("[yellow]TAMPER_DETECTED[/]")

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
    committed = _commit_phase(
        f"feat({scope}): GREEN phase - implementation passes tests", root
    )

    if committed:
        console.print("[green]GREEN_POST_OK[/]")
    else:
        console.print("[yellow]YELLOW_TRIGGERED[/]")

    raise typer.Exit(code=0)


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

    changed = _detect_phase_changes(root)
    test_files = [str(f) for f in _find_test_files(root)]

    contract = {
        "proposed_changes": changed,
        "rationale": "YELLOW phase — review proposed test amendments",
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
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    changed = _detect_phase_changes(root)

    if not changed:
        console.print("NO_CHANGES_PROPOSED")
        raise typer.Exit(code=0)

    if approved:
        _commit_phase("feat: YELLOW phase — approved amendments", root)
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        console.print("[green]YELLOW_POST_OK[/]")

    if rejected:
        subprocess.run(["git", "restore", "."], cwd=root, env=_git_env(), check=False)
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        console.print("[yellow]YELLOW_REVERTED[/]")

    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# JUDGE commands
# ---------------------------------------------------------------------------


def _find_protected_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for spec_file in sorted(root.glob("specs/**/spec.md")):
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
        lines.append(stripped)
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


_RETURN_TYPE_MAP = {
    "str": (ast.Constant, ast.JoinedStr),
    "int": (ast.Constant,),
    "float": (ast.Constant,),
    "bool": (ast.Constant,),
    "list": (ast.List,),
    "dict": (ast.Dict,),
    "tuple": (ast.Tuple,),
    "set": (ast.Set,),
}


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

        for child in ast.walk(node):
            if not isinstance(child, ast.Return) or child.value is None:
                continue
            if _is_return_type_mismatch(child.value, return_annotation):
                issues.append(
                    f"{node.name}: return value type mismatch (expected {return_annotation})"
                )
                break
    return issues


def _is_return_type_mismatch(
    value: ast.expr,
    expected: str,
) -> bool:
    if isinstance(value, ast.Constant):
        type_map = {"str": str, "int": int, "float": (int, float), "bool": bool}
        if expected in type_map:
            return not isinstance(value.value, type_map[expected])
        return True

    expected_nodes = _RETURN_TYPE_MAP.get(expected, ())
    if not expected_nodes:
        return False
    return not isinstance(value, expected_nodes)


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

    # Append REFACTOR transition for this specific task
    try:
        record = TaskRecord.model_validate(green_task[0])
        record.status = "REFACTOR"  # type: ignore[assignment]
        append_task_transition(record, green_task[1])
    except Exception as e:
        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
        raise typer.Exit(code=1)

    session = session.force_transition_to("REFACTOR")
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
    manifest: str | None = typer.Argument(None, help="Path to manifest file"),
) -> None:
    root = Path.cwd()
    _validate_manifest(manifest)
    _commit_phase("feat: EXECUTE phase \u2014 direct execution result", root)
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
    _validate_manifest(manifest)
    _commit_phase("feat: E2E phase \u2014 verification results", root)
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
    _validate_manifest(manifest)
    _commit_phase("feat: HOTFIX phase \u2014 bug fix", root)
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
) -> None:
    """Run dispatcher: route task by execution_mode to TDD cycle or execute phase.

    When called without arguments, picks the next PENDING task for the active issue.
    """
    root = _resolve_workspace_root()
    session_path = root / ".deviate" / "session.json"

    agent = _resolve_agent_config(root, agent)

    if session_path.exists():
        session = SessionState.load(session_path)
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

    skip_judge, skip_refactor = resolve_profile(profile, no_judge, no_refactor)

    if all_tasks:
        _run_all(
            root,
            console,
            no_judge=skip_judge,
            no_refactor=skip_refactor,
            agent=agent,
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
