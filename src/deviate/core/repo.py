from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core._shared import git_env as _git_env


def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()
    for parent in [start_at] + list(start_at.parents):
        if (parent / ".git").exists():
            return parent
    raise ValueError(f"not a git repository: {start_at}")


def gather_git_state(repo: Path | None = None) -> dict:
    repo = repo or Path.cwd()
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    staged = []
    unstaged = []
    untracked = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if line.startswith("??"):
            untracked.append(line[3:])
        else:
            x = line[0]
            y = line[1]
            filename = line[3:]
            if x != " ":
                staged.append(filename)
            if y != " ":
                unstaged.append(filename)
    return {
        "staged_files": staged,
        "unstaged_files": unstaged,
        "untracked_files": untracked,
    }
