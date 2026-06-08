from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
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
