from __future__ import annotations

import json

import typer

constitution_app = typer.Typer(no_args_is_help=True)


@constitution_app.command()
def pre() -> None:
    """Validate constitution and extract commands."""
    print(json.dumps({"status": "NOT_IMPLEMENTED"}))


@constitution_app.command()
def post(
    manifest: str = typer.Argument(..., help="Path to manifest JSON"),
) -> None:
    """Validate constitution sections and commit."""
    print(json.dumps({"status": "NOT_IMPLEMENTED"}))
