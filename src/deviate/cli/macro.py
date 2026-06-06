from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from deviate.state.config import SessionState, TransitionViolationError

macro_cli = typer.Typer()
console = Console()

_EXPLORE_MD = "explore.md"
_RESEARCH_MD = "research.md"
_PRD_MD = "prd.md"


def _validate_artifacts(required: list[Path]) -> list[Path]:
    return [p for p in required if not p.exists()]


def _handle_missing_dot_dir(phase: str) -> None:
    console.print(
        f"[red]{phase}_HALTED: .deviate/ not found, run 'deviate init' first[/]"
    )
    raise typer.Exit(code=1)


def _handle_transition_error(phase: str, error: TransitionViolationError) -> None:
    console.print(f"[red]{phase}_HALTED: {error}[/]")
    raise typer.Exit(code=1)


def _handle_missing_artifacts(phase: str, missing: list[Path]) -> None:
    paths = "\n  - ".join(str(p) for p in missing)
    console.print(f"[red]{phase}_HALTED: missing upstream artifacts\n  - {paths}[/]")
    raise typer.Exit(code=1)


def explore(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("EXPLORE")

    session = _load_session(dot_dir)
    try:
        session = session.transition_to("EXPLORE")
    except TransitionViolationError as e:
        _handle_transition_error("EXPLORE", e)

    session.save(dot_dir / "session.json")
    console.print("[green]EXPLORE[/] session advanced to EXPLORE phase")


def research(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("RESEARCH")

    session = _load_session(dot_dir)
    try:
        session = session.transition_to("RESEARCH")
    except TransitionViolationError as e:
        _handle_transition_error("RESEARCH", e)

    spec_dir = Path("specs") / epic_slug
    missing = _validate_artifacts([spec_dir / _EXPLORE_MD])
    if missing:
        _handle_missing_artifacts("RESEARCH", missing)

    session.save(dot_dir / "session.json")
    console.print("[green]RESEARCH[/] session advanced to RESEARCH phase")


def prd(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("PRD")

    session = _load_session(dot_dir)
    try:
        session = session.transition_to("PRD")
    except TransitionViolationError as e:
        _handle_transition_error("PRD", e)

    spec_dir = Path("specs") / epic_slug
    missing = _validate_artifacts([spec_dir / _EXPLORE_MD, spec_dir / _RESEARCH_MD])
    if missing:
        _handle_missing_artifacts("PRD", missing)

    session.save(dot_dir / "session.json")
    console.print("[green]PRD[/] session advanced to PRD phase")


def shard(
    epic_slug: str = typer.Argument(..., help="Epic slug for the feature scope"),
) -> None:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir("SHARD")

    session = _load_session(dot_dir)
    try:
        session = session.transition_to("SHARD")
    except TransitionViolationError as e:
        _handle_transition_error("SHARD", e)

    spec_dir = Path("specs") / epic_slug
    missing = _validate_artifacts([spec_dir / _PRD_MD])
    if missing:
        _handle_missing_artifacts("SHARD", missing)

    session.save(dot_dir / "session.json")
    console.print("[green]SHARD[/] session advanced to SHARD phase")


def _load_session(dot_dir: Path) -> SessionState:
    session_path = dot_dir / "session.json"
    return SessionState.load(session_path)
