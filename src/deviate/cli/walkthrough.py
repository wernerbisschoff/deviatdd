from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.core._shared import git_env as _git_env

logger = logging.getLogger(__name__)

walkthrough_app = typer.Typer(no_args_is_help=True)


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


def _get_changed_files(repo: Path, base: str, target: str = "HEAD") -> list[str]:
    """Get list of changed files between merge-base and target."""
    try:
        merge_base = _compute_merge_base(base, target, repo)
        if not merge_base:
            return []
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{merge_base}..{target}"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _get_branch_commits(repo: Path, base: str) -> list[str]:
    """Get commit messages from merge-base to HEAD (exclusive)."""
    try:
        merge_base = _compute_merge_base(base, "HEAD", repo)
        if not merge_base:
            return []
        result = subprocess.run(
            ["git", "log", f"{merge_base}..HEAD", "--format=%s"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


@walkthrough_app.command()
def pre(
    base: str = typer.Option(
        "main", "--base", help="Base branch for merge-base computation"
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Target branch for self-contained walkthrough"
    ),
) -> None:
    """Gather git state and governance context for walkthrough."""
    repo = Path.cwd()

    target = branch or "HEAD"
    branch_name = branch or _get_current_branch(repo)

    diff = _compute_diff(repo, base, target)
    constitution_path = _resolve_constitution_path(repo)
    prd_path, prd_warning = _resolve_prd(branch_name, repo)
    commit_messages = _get_branch_commits(repo, base)
    changed_files = _get_changed_files(repo, base, target)

    contract: dict[str, object] = {
        "status": "READY",
        "diff": diff,
        "constitution_path": constitution_path,
        "constitution_warning": constitution_path is None,
        "prd_path": prd_path,
        "prd_warning": prd_warning,
        "base_branch": base,
        "commit_messages": commit_messages,
        "changed_files_count": len(changed_files),
        "changed_files": changed_files,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(contract, indent=2))


@walkthrough_app.command()
def post(
    status: str = typer.Argument(
        ..., help="Status after walkthrough: CLEAN or FLAGGED"
    ),
) -> None:
    """Record walkthrough outcome (placeholder — future summary persistence)."""
    contract: dict[str, object] = {
        "status": status,
        "phase": "walkthrough",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Walkthrough is a human-guided process — outcome recorded for audit trail",
    }
    print(json.dumps(contract, indent=2))
