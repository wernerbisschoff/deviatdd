from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core._shared import git_env as _git_env


def create_worktree(branch: str, path: Path, repo: Path | None = None) -> Path:
    repo = repo or Path.cwd()
    path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    branch_exists = bool(result.stdout.strip())
    if branch_exists:
        raise RuntimeError(f"Branch '{branch}' already exists")
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(path)],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    return path


def detect_worktree(repo: Path | None = None) -> dict[str, str]:
    repo = repo or Path.cwd()
    result = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    worktrees: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            worktrees[parts[1]] = parts[0]
    return worktrees


def validate_worktree(path: Path) -> bool:
    if not path.exists():
        return False
    return (path / ".git").exists()
