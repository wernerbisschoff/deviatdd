from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core._shared import git_env as _git_env


def find_worktree_for_branch(branch: str, repo: Path | None = None) -> Path | None:
    """Return the worktree path for an existing branch, or None."""
    repo = repo or Path.cwd()
    result = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].strip("[]") == branch:
            return Path(parts[0])
    return None


def detect_remote(repo: Path | None = None) -> str:
    """Return the default git remote name, preferring ``origin``."""
    repo = repo or Path.cwd()
    result = subprocess.run(
        ["git", "remote"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    remotes = result.stdout.strip().splitlines()
    if not remotes:
        msg = "no git remotes configured"
        raise RuntimeError(msg)
    return "origin" if "origin" in remotes else remotes[0]


def branch_exists_on_remote(
    branch: str, repo: Path | None = None, remote: str | None = None
) -> bool:
    """Check if a branch exists on the remote (auto-detected by default).

    Returns ``False`` if the remote is unreachable (network error) —
    the caller's ``detect_remote`` already validated the remote exists.
    """
    repo = repo or Path.cwd()
    remote = remote or detect_remote(repo)
    result = subprocess.run(
        ["git", "ls-remote", "--heads", remote, branch],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def create_worktree(branch: str, path: Path, repo: Path | None = None) -> Path:
    repo = repo or Path.cwd()
    existing = find_worktree_for_branch(branch, repo)
    if existing is not None:
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    branch_exists = bool(result.stdout.strip())
    if not branch_exists:
        subprocess.run(
            ["git", "branch", branch, "HEAD"],
            cwd=repo,
            env=_git_env(),
            check=True,
        )
    subprocess.run(
        ["git", "worktree", "add", str(path), branch],
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


def remove_worktree(branch: str, path: Path, repo: Path | None = None) -> None:
    """Remove a worktree and its local branch (best-effort, no-op on failure)."""
    repo = repo or Path.cwd()
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        pass
    try:
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        pass


def validate_worktree(path: Path) -> bool:
    if not path.exists():
        return False
    return (path / ".git").exists()
