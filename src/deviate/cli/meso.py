from __future__ import annotations

import uuid
from pathlib import Path

import typer

from deviate.cli._common import (
    _handle_missing_dot_dir,
    _handle_transition_error,
    console,
)
from deviate.state.config import SessionState, TransitionViolationError
from deviate.state.ledger import (
    IssueRecord,
    TaskRecord,
    append_task_record,
    resolve_issue_record,
)


def _resolve_and_validate_issue(issue_id: str, phase: str) -> IssueRecord:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)

    ledger_path = Path("specs") / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
        raise typer.Exit(code=1)

    return record


def tasks(
    issue_id: str = typer.Argument(..., help="Issue ID to decompose into tasks"),
) -> None:
    record = _resolve_and_validate_issue(issue_id, "TASKS")

    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path)

    issue_slug = record.issue_slug
    tasks_jsonl = Path("specs") / issue_slug / "tasks.jsonl"

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
        id=str(uuid.uuid4()),
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


def specify(
    issue_id: str = typer.Argument(..., help="Issue ID to specify"),
) -> None:
    record = _resolve_and_validate_issue(issue_id, "SPECIFY")

    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path)

    issue_slug = record.issue_slug
    spec_dir = Path("specs") / issue_slug
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
