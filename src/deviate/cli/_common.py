from __future__ import annotations

import typer
from rich.console import Console

from deviate.state.config import TransitionViolationError

console = Console()


def _handle_missing_dot_dir(phase: str) -> None:
    console.print(
        f"[red]{phase}_HALTED: .deviate/ not found, run 'deviate init' first[/]"
    )
    raise typer.Exit(code=1)


def _handle_transition_error(phase: str, error: TransitionViolationError) -> None:
    console.print(f"[red]{phase}_HALTED: {error}[/]")
    raise typer.Exit(code=1)
