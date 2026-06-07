from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from deviate.state.config import SessionState, TransitionViolationError
from deviate.state.ledger import resolve_issue_record

console = Console()


def _handle_missing_dot_dir() -> None:
    console.print(
        "[red]SPECIFY_HALTED: .deviate/ not found, run 'deviate init' first[/]"
    )
    raise typer.Exit(code=1)


def _handle_transition_error(error: TransitionViolationError) -> None:
    console.print(f"[red]SPECIFY_HALTED: {error}[/]")
    raise typer.Exit(code=1)


def specify(
    issue_id: str = typer.Argument(..., help="Issue ID to specify"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir()

    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    ledger_path = Path("specs") / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
        raise typer.Exit(code=1)

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
        _handle_transition_error(e)

    session.active_issue_id = issue_id
    session.save(session_path)
    console.print("[green]SPECIFY[/] session advanced to SPECIFY phase")
