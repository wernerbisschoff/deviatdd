from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core._shared import git_env as _git_env


def _has_changes_to_stage(files: list[Path], repo: Path) -> bool:
    """Check if any of the given files have unstaged changes or are untracked."""
    for f in files:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", str(f)],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git status failed for {f}: {result.stderr.strip()}")
        if result.stdout.strip():
            return True
    return False


def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()

    if not _has_changes_to_stage(files, repo):
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    subprocess.run(
        ["git", "add", "--"] + [str(f) for f in files],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit_artifact(path: Path, message: str, repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    return stage_and_commit(message=message, files=[path], repo=repo)
