"""Keep JUDGE task and local-environment repairs across implementation rollback."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from deviate.core._shared import git_env

_SUBJECT = "chore(JUDGE): repair task and environment"
_PATTERNS = (
    "specs/**/tasks.md",
    "tasks.md",
    "mise.toml",
    ".mise.toml",
    "mise/tasks/**/*",
    ".mise/tasks/**/*",
    "mise/*.toml",
    ".mise/*.toml",
    "scripts/setup*",
    "scripts/doctor*",
    "scripts/reset*",
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        env=git_env(),
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"JUDGE_REPAIR_FAILED: git {args[0]} failed; work preserved: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def snapshot_repairs(root: Path) -> dict[str, str]:
    result = {}
    for pattern in _PATTERNS:
        for path in root.glob(pattern):
            if (
                not path.is_file()
                or path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())
            ):
                continue
            relative = path.relative_to(root).as_posix()
            if any(part.startswith(".env") for part in path.parts) or path.suffix in {
                ".key",
                ".pem",
                ".crt",
            }:
                continue
            result[relative] = (
                f"{path.stat().st_mode}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
            )
    return result


def commit_repairs(root: Path, before: dict[str, str]) -> bool:
    after = snapshot_repairs(root)
    paths = sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )
    if not paths or not _git(
        root, "status", "--porcelain", "--untracked-files=all", "--", *paths
    ):
        return False
    _git(root, "add", "--", *paths)
    _git(root, "commit", "--only", "-m", _SUBJECT, "--", *paths)
    return True


def repair_commits(root: Path, boundary: str) -> list[str]:
    return _git(
        root,
        "log",
        "--reverse",
        "--format=%H",
        "--fixed-strings",
        f"--grep={_SUBJECT}",
        f"{boundary}..HEAD",
    ).splitlines()


def replay_repairs(root: Path, commits: list[str]) -> None:
    for commit in commits:
        _git(root, "cherry-pick", commit)
