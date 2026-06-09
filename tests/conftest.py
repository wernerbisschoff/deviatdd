from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "runner@test.local"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/repo.git"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    return tmp_path
