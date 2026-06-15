from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn

import typer

from deviate.core.constitution import (
    extract_commands,
    validate_constitution,
    validate_sections,
)
from deviate.core.commit import commit_artifact

constitution_app = typer.Typer(no_args_is_help=True)


def _fail_with(reason: str) -> NoReturn:
    print(json.dumps({"status": "FAILURE", "reason": reason}))
    raise typer.Exit(code=1)


@constitution_app.command()
def pre() -> None:
    """Validate constitution and extract commands."""
    repo_root = Path.cwd()
    const_path = repo_root / "specs" / "constitution.md"

    if not const_path.exists():
        _fail_with(f"constitution.md not found at {const_path}")

    if not validate_constitution(const_path):
        _fail_with("constitution validation failed")

    missing = validate_sections(const_path, ["## TESTING_PROTOCOLS"])
    if missing:
        _fail_with(f"Missing required section: {missing[0]}")

    commands = extract_commands(const_path)
    print(json.dumps(commands))


@constitution_app.command()
def post(
    manifest: str = typer.Argument(..., help="Path to manifest JSON"),
) -> None:
    """Validate constitution sections and commit."""
    manifest_path = Path(manifest)

    if not manifest_path.exists():
        _fail_with(f"manifest not found at {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text())
    sections = manifest_data.get("sections", [])
    const_rel_path = manifest_data.get("constitution_path", "specs/constitution.md")

    const_path = Path.cwd() / const_rel_path

    missing = validate_sections(const_path, sections)
    if missing:
        _fail_with(f"Missing sections: {', '.join(missing)}")

    commit_artifact(path=const_path, message="Update constitution")
    print(json.dumps({"status": "SUCCESS"}))
