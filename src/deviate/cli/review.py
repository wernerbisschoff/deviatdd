from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env

review_app = typer.Typer(no_args_is_help=True)


@review_app.command()
def pre(
    base: str = typer.Option(
        "main", "--base", help="Base branch for merge-base computation"
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Target branch for self-contained review"
    ),
) -> None:
    """Gather git state and governance context for review."""
    repo = Path.cwd()

    target = branch or "HEAD"
    branch_name = branch or _get_current_branch(repo)

    diff = _compute_diff(repo, base=base, target_branch=target)
    constitution_path = _resolve_constitution_path(repo)
    prd_path, prd_warning = _resolve_prd(branch_name, repo)
    report_exists = _check_existing_reports(repo)

    contract = {
        "status": "READY",
        "diff": diff,
        "constitution_path": constitution_path,
        "constitution_warning": constitution_path is None,
        "prd_path": prd_path,
        "prd_warning": prd_warning,
        "base_branch": base,
        "report_exists": report_exists,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(contract, indent=2))


def _get_current_branch(repo: Path) -> str | None:
    """Get current git branch name."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


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


def _compute_diff(repo: Path, base: str = "main", target_branch: str = "HEAD") -> str:
    """Compute unified diff against merge-base with given base branch."""
    merge_base = _compute_merge_base(base, target_branch, repo)
    if not merge_base:
        return ""
    return _gather_diff(merge_base, target_branch, repo)


def _resolve_constitution_path(repo: Path) -> str | None:
    """Resolve specs/constitution.md path if it exists."""
    path = repo / "specs" / "constitution.md"
    if path.exists():
        return str(path.resolve())
    return None


def _resolve_prd(branch_name: str | None, repo: Path) -> tuple[str | None, bool]:
    """Resolve PRD path with epic priority over adhoc fallback."""
    epic_slug = None
    if branch_name:
        parts = branch_name.split("/")
        if len(parts) > 1:
            epic_slug = parts[1]

    if epic_slug:
        epic_prd = repo / "specs" / epic_slug / "prd.md"
        if epic_prd.exists():
            return str(epic_prd.resolve()), False

    adhoc_prd = repo / "specs" / "adhoc" / "prd.md"
    if adhoc_prd.exists():
        return str(adhoc_prd.resolve()), False

    return None, True


def _reports_dir(repo: Path) -> Path:
    """Resolve the .deviate/review/reports/ directory path."""
    return repo / ".deviate" / "review" / "reports"


def _check_existing_reports(repo: Path) -> bool:
    """Check if review reports already exist under .deviate/review/reports/."""
    reports_dir = _reports_dir(repo)
    if not reports_dir.is_dir():
        return False
    return any(reports_dir.iterdir())


@review_app.command()
def post(
    content: str | None = typer.Argument(
        None, help="Report markdown content. If not provided, reads from stdin."
    ),
) -> None:
    """Persist review report and mark review complete."""
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()

    if not content:
        console.print("[yellow]SKIP[/] no report content provided")
        raise typer.Exit(code=0)

    repo = Path.cwd()
    reports_dir = _reports_dir(repo)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_file = reports_dir / f"review-report-{timestamp}.md"
    report_file.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/] report written to {report_file}")
