from __future__ import annotations

import subprocess
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import typer

from deviate.cli._common import (
    _handle_missing_dot_dir,
    _handle_transition_error,
    console,
)
from deviate.core._shared import git_env as _git_env
from deviate.core.commit import commit_artifact
from deviate.core.issues import claim_issue
from deviate.core.validation import validate_gherkin_syntax
from deviate.core.worktree import create_worktree, detect_worktree
from deviate.state.config import SessionState, TransitionViolationError
from deviate.state.ledger import (
    IssueRecord,
    TaskRecord,
    append_task_record,
    resolve_issue_record,
    select_next_unblocked_issue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_and_transition(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    try:
        session = session.transition_to(phase)
    except TransitionViolationError as e:
        _handle_transition_error(phase, e)
    return session, session_path


def _load_session(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    if session.current_phase != phase:
        console.print(
            f"[red]PHASE_MISMATCH[/] session is in '{session.current_phase}', "
            f"expected '{phase}'"
        )
        raise typer.Exit(code=1)
    return session, session_path


def _save_session(session: SessionState, session_path: Path, phase: str) -> None:
    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def _resolve_specs_root() -> Path:
    return Path("specs")


def _resolve_bucket_dir(source_file: str) -> str:
    return PurePosixPath(source_file).parent.parent.name


def _find_spec_md(issue_id: str) -> Path | None:
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        return None
    bucket = _resolve_bucket_dir(record.source_file)
    spec_path = _resolve_specs_root() / bucket / "spec.md"
    if spec_path.exists():
        return spec_path
    return None


def _resolve_and_validate_issue(issue_id: str, phase: str) -> IssueRecord:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
        raise typer.Exit(code=1)
    return record


# ---------------------------------------------------------------------------
# Specify — legacy positional-argument API
# ---------------------------------------------------------------------------


def _specify_legacy(issue_id: str) -> None:
    record = _resolve_and_validate_issue(issue_id, "SPECIFY")
    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path)
    issue_slug = PurePosixPath(record.source_file).stem
    spec_dir = _resolve_specs_root() / issue_slug
    if spec_dir.exists():
        console.print(f"[yellow]SKIP[/] specs/{issue_slug}/ already exists")
    else:
        spec_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]CREATE[/] specs/{issue_slug}/")
    spec_md = spec_dir / "spec.md"
    if not spec_md.exists():
        spec_md.write_text("")
        console.print(f"[green]CREATE[/] specs/{issue_slug}/spec.md")
    try:
        session = session.transition_to("SPECIFY")
    except TransitionViolationError as e:
        _handle_transition_error("SPECIFY", e)
    session.active_issue_id = issue_id
    session.save(session_path)
    console.print("[green]SPECIFY[/] session advanced to SPECIFY phase")


# ---------------------------------------------------------------------------
# Specify — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


def _specify_pre(issue_id: str | None = None, force: bool = False) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("SPECIFY")
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    ledger_path = _resolve_specs_root() / "issues.jsonl"

    if issue_id is None:
        issue = select_next_unblocked_issue(ledger_path)
        if issue is None:
            console.print(
                "[red]NO_UNBLOCKED_BACKLOG[/] no unblocked BACKLOG issues found"
            )
            raise typer.Exit(code=1)
        resolved_id: str = issue.issue_id
        console.print(f"[green]SELECTED[/] {resolved_id} — {issue.title}")
    else:
        issue = resolve_issue_record(issue_id, ledger_path)
        if issue is None:
            console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
            raise typer.Exit(code=1)
        resolved_id = issue_id

    bucket_slug = _resolve_bucket_dir(issue.source_file)
    branch = f"feat/{resolved_id}"
    worktree_path = Path.cwd().parent / resolved_id

    try:
        create_worktree(branch, worktree_path, repo=Path.cwd())
        console.print(f"[green]WORKTREE[/] created at {worktree_path}")
    except RuntimeError as e:
        if not force:
            console.print(f"[red]WORKTREE_ERROR[/] {e}")
            raise typer.Exit(code=1)

    claimed = claim_issue(resolved_id, ledger_path)
    if claimed:
        console.print(f"[green]CLAIMED[/] {resolved_id} → SPECIFIED")
    else:
        console.print(f"[yellow]CLAIM_SKIP[/] {resolved_id} already claimed")

    spec_target = str(_resolve_specs_root() / bucket_slug / "spec.md")

    try:
        session = session.transition_to("SPECIFY")
    except TransitionViolationError as e:
        _handle_transition_error("SPECIFY", e)
    session.active_issue_id = resolved_id
    session.save(session_path)
    console.print(
        f"[green]SPECIFY_PRE[/] session advanced to SPECIFY with {resolved_id}"
    )
    console.print(
        '{"phase": "SPECIFY", '
        f'"issue_id": "{resolved_id}", '
        f'"branch": "{branch}", '
        f'"spec_target": "{spec_target}"'
        "}"
    )


def _specify_post(force: bool = False) -> None:
    session, session_path = _load_session("SPECIFY")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    spec_path = _find_spec_md(issue_id)
    if spec_path is None:
        console.print("[red]SPEC_NOT_FOUND[/] could not find spec.md for issue")
        raise typer.Exit(code=1)
    content = spec_path.read_text(encoding="utf-8")
    errors = validate_gherkin_syntax(content)
    if errors:
        if force:
            for err in errors:
                console.print(f"[yellow]WARNING[/] {err}")
        else:
            for err in errors:
                console.print(f"[red]GHERKIN_ERROR[/] {err}")
            raise typer.Exit(code=1)
    try:
        sha = commit_artifact(
            spec_path, f"SPECIFY: spec.md for {issue_id}", repo=Path.cwd()
        )
        console.print(f"[green]COMMITTED[/] spec.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]COMMIT_FAILED[/] {e}")
        raise typer.Exit(code=1)
    try:
        session = session.transition_to("TASKS")
    except TransitionViolationError as e:
        _handle_transition_error("SPECIFY", e)
    _save_session(session, session_path, "TASKS")


# ---------------------------------------------------------------------------
# Tasks — legacy positional-argument API
# ---------------------------------------------------------------------------


def _tasks_legacy(issue_id: str) -> None:
    record = _resolve_and_validate_issue(issue_id, "TASKS")
    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path)
    issue_slug = PurePosixPath(record.source_file).stem
    tasks_jsonl = _resolve_specs_root() / issue_slug / "tasks.jsonl"
    if tasks_jsonl.exists():
        console.print(f"[yellow]SKIP[/] tasks already provisioned for {issue_slug}")
        raise typer.Exit(code=0)
    try:
        session = session.transition_to("TASKS")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    session.active_issue_id = issue_id
    session.save(session_path)

    task = TaskRecord(
        id=str(uuid_mod.uuid4()),
        issue_id=issue_id,
        description=f"Implement {record.title}",
        status="PENDING",
        execution_mode="TDD",
    )
    if not append_task_record(task, tasks_jsonl):
        console.print(f"[red]ERROR[/] Failed to append task record {task.id}")
        raise typer.Exit(code=1)

    try:
        session = session.transition_to("IDLE")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    session.save(session_path)
    console.print(f"[green]TASKS[/] 1 task(s) provisioned for {issue_slug}")


# ---------------------------------------------------------------------------
# Tasks — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


def _tasks_pre() -> None:
    session, session_path = _load_session("SPECIFY")
    wts = detect_worktree(repo=Path.cwd())
    console.print(f"[green]WORKTREES[/] {len(wts)} worktree(s) detected")
    spec_mds = list(_resolve_specs_root().rglob("spec.md"))
    if not spec_mds:
        console.print("[red]SPEC_NOT_FOUND[/] no spec.md found under specs/")
        raise typer.Exit(code=1)
    spec_path = spec_mds[0]
    console.print(f"[green]SPEC_DISCOVERED[/] {spec_path}")
    _save_session(session, session_path, "SPECIFY")


def _tasks_post(force: bool = False) -> None:
    session, session_path = _load_session("TASKS")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    bucket = _resolve_bucket_dir(record.source_file)
    tasks_md = _resolve_specs_root() / bucket / "tasks.md"
    if not tasks_md.exists():
        console.print(f"[red]TASKS_NOT_FOUND[/] {tasks_md}")
        raise typer.Exit(code=1)
    content = tasks_md.read_text(encoding="utf-8").strip()
    if not content and not force:
        console.print("[red]TASKS_EMPTY[/] tasks.md is empty")
        raise typer.Exit(code=1)
    try:
        sha = commit_artifact(
            tasks_md, f"TASKS: tasks.md for {issue_id}", repo=Path.cwd()
        )
        console.print(f"[green]COMMITTED[/] tasks.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]COMMIT_FAILED[/] {e}")
        raise typer.Exit(code=1)
    try:
        session = session.transition_to("IDLE")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    _save_session(session, session_path, "IDLE")


# ---------------------------------------------------------------------------
# PR — new pre/run subcommand behavior
# ---------------------------------------------------------------------------


def _pr_pre() -> None:
    session, session_path = _load_session("TASKS")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    console.print(f"[green]ISSUE[/] {issue_id}: {record.title}")
    _save_session(session, session_path, "TASKS")


def _pr_run(
    body_file: Path,
    merge: bool = False,
    auto_merge: bool = False,
) -> None:
    session, session_path = _load_session("TASKS")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    if not body_file.exists():
        console.print(f"[red]BODY_FILE_NOT_FOUND[/] {body_file}")
        raise typer.Exit(code=1)
    title = f"[{issue_id}] {record.title}"
    cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]
    if merge:
        cmd.append("--merge")
    if auto_merge:
        cmd.append("--auto-merge")
    result = subprocess.run(cmd, capture_output=True, text=True, env=_git_env())
    if result.returncode != 0:
        console.print(f"[red]PR_CREATE_FAILED[/] {result.stderr.strip()}")
        raise typer.Exit(code=1)
    pr_url = result.stdout.strip()
    console.print(f"[green]PR_CREATED[/] {pr_url}")

    completed = record.model_copy(
        update={
            "status": "COMPLETED",
            "timestamp": datetime.now(timezone.utc),
        }
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(completed.model_dump_json() + "\n")
    console.print(f"[green]COMPLETED[/] {issue_id} → COMPLETED")
    _save_session(session, session_path, "TASKS")


# ---------------------------------------------------------------------------
# CLI command entry points
# ---------------------------------------------------------------------------


def specify(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(False, "--force", help="Force operation"),
    issue: str | None = typer.Option(
        None, "--issue", help="Issue ID for pre subcommand"
    ),
) -> None:
    """Specify phase: pre (select issue, create worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _specify_pre(issue_id=issue, force=force)
    elif issue_id == "post":
        _specify_post(force=force)
    else:
        _specify_legacy(issue_id)


def tasks(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(False, "--force", help="Force operation"),
) -> None:
    """Tasks phase: pre (detect worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _tasks_pre()
    elif issue_id == "post":
        _tasks_post(force=force)
    else:
        _tasks_legacy(issue_id)


def pr(
    action: str = typer.Argument(..., help="Action: pre (validate) or run (create PR)"),
    body_file: Path | None = typer.Option(
        None, "--body-file", help="Path to PR body file"
    ),
    merge: bool = typer.Option(False, "--merge", help="Merge after PR creation"),
    auto_merge: bool = typer.Option(False, "--auto-merge", help="Enable auto-merge"),
) -> None:
    """PR phase: pre (validate) or run (create PR)"""
    if action == "pre":
        _pr_pre()
    elif action == "run":
        if body_file is None:
            console.print("[red]MISSING_BODY_FILE[/] --body-file is required for 'run'")
            raise typer.Exit(code=1)
        _pr_run(body_file, merge=merge, auto_merge=auto_merge)
    else:
        console.print(f"[red]UNKNOWN_ACTION[/] '{action}'. Use 'pre' or 'run'")
        raise typer.Exit(code=1)
