from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from deviate.core.constitution import resolve_constitution, validate_constitution
from deviate.state.config import TransitionViolationError

console = Console()


def _halt(phase: str, message: str) -> None:
    console.print(f"[red]{phase}_HALTED: {message}[/]")
    raise typer.Exit(code=1)


def _handle_missing_dot_dir(phase: str) -> None:
    _halt(phase, ".deviate/ not found, run 'deviate init' first")


def _handle_transition_error(phase: str, error: TransitionViolationError) -> None:
    _halt(phase, str(error))


def _validate_constitution(phase: str = "CONSTITUTION") -> Path:
    try:
        const_path = resolve_constitution(Path.cwd())
        if not validate_constitution(const_path):
            _halt(phase, "constitution validation failed")
        return const_path
    except FileNotFoundError:
        _halt(phase, "constitution.md not found")


def _load_manifest(path: Path, phase: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        _halt(phase, f"invalid manifest at {path} — {e}")
