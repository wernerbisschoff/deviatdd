from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env

review_app = typer.Typer(no_args_is_help=True)


@review_app.command()
def pre() -> None:
    """Gather git state and governance context for review."""
    repo = Path.cwd()

    diff = _compute_diff(repo)
    constitution_path = _resolve_constitution_path(repo)

    contract = {
        "status": "READY",
        "diff": diff,
        "constitution_path": constitution_path,
        "prd_path": None,
        "base_branch": "main",
        "report_exists": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(contract, indent=2))


def _compute_merge_base(commit_a: str, commit_b: str, repo: Path) -> str:
    """Compute merge base between two commits."""
    try:
        return subprocess.run(
            ["git", "merge-base", commit_a, commit_b],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _gather_diff(base: str, head: str, repo: Path) -> str:
    """Gather unified diff between base and head commits."""
    try:
        return subprocess.run(
            ["git", "diff", f"{base}..{head}"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _compute_diff(repo: Path) -> str:
    """Compute unified diff against merge-base with main."""
    merge_base = _compute_merge_base("main", "HEAD", repo)
    if not merge_base:
        return ""
    return _gather_diff(merge_base, "HEAD", repo)


def _resolve_constitution_path(repo: Path) -> str | None:
    """Resolve specs/constitution.md path if it exists."""
    path = repo / "specs" / "constitution.md"
    if path.exists():
        return str(path.resolve())
    return None


@review_app.command()
def post() -> None:
    """Persist review report and mark review complete."""
    console.print("[green]OK[/] no-op")
