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
from deviate.state.ledger import IssueRecord, append_issue_record


def _validate_artifacts(required: list[Path]) -> list[Path]:
    return [p for p in required if not p.exists()]


def _handle_missing_artifacts(phase: str, missing: list[Path]) -> None:
    paths = "\n  - ".join(str(p) for p in missing)
    console.print(f"[red]{phase}_HALTED: missing upstream artifacts\n  - {paths}[/]")
    raise typer.Exit(code=1)


def _run_command(phase: str, epic_slug: str, artifact_names: list[str]) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)

    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    try:
        session = session.transition_to(phase)
    except TransitionViolationError as e:
        _handle_transition_error(phase, e)

    if artifact_names:
        spec_dir = Path("specs") / epic_slug
        missing = _validate_artifacts([spec_dir / name for name in artifact_names])
        if missing:
            _handle_missing_artifacts(phase, missing)

    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def explore(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    _run_command("EXPLORE", epic_slug, [])


def research(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    _run_command("RESEARCH", epic_slug, ["explore.md"])


def prd(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    _run_command("PRD", epic_slug, ["explore.md", "research.md"])


def shard(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("SHARD")

    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    try:
        session = session.transition_to("SHARD")
    except TransitionViolationError as e:
        _handle_transition_error("SHARD", e)

    spec_dir = Path("specs") / epic_slug
    missing = _validate_artifacts([spec_dir / "prd.md"])
    if missing:
        _handle_missing_artifacts("SHARD", missing)

    ledger_path = Path("specs") / "issues.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = IssueRecord(
        id=str(uuid.uuid4()),
        title=f"Shard output for {epic_slug}",
        status="SHARDED",
        epic_slug=epic_slug,
        issue_slug=epic_slug,
    )
    appended = append_issue_record(record, ledger_path)
    if appended:
        console.print(f"[green]LEDGER_APPENDED[/] {record.issue_slug}")
    else:
        console.print(
            f"[yellow]LEDGER_IDEMPOTENT[/] record for "
            f"{record.issue_slug} already exists"
        )

    session = session.transition_to("IDLE")
    session.save(session_path)
    console.print("[green]SHARD[/] session reset to IDLE")
