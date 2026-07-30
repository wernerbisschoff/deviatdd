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


def stage_and_commit(
    message: str,
    files: list[Path],
    repo: Path | None = None,
    no_verify: bool = False,
    files_to_remove: list[Path] | None = None,
) -> str | None:
    """Stage ``files`` (via ``git add``) and any ``files_to_remove`` (via
    ``git rm``), then create a single commit carrying both.

    ``files_to_remove`` is the explicit way to record a move/rename inside
    a single commit: ``git rm`` the tracked-but-deleted origin path and
    ``git add`` the new path in one shot. Each path must exist as a
    tracked file in the index — passing a never-tracked path raises
    ``CalledProcessError`` from ``git rm`` (use ``shutil.move`` followed
    by ``stage_and_commit`` only when the source WAS committed first).
    Pass ``files_to_remove=None`` (the default) for the original
    add-only behavior.
    """
    repo = repo or Path.cwd()
    files_to_remove = files_to_remove or []
    all_paths = list(files) + list(files_to_remove)

    if not _has_changes_to_stage(all_paths, repo):
        return None

    if files_to_remove:
        subprocess.run(
            ["git", "rm", "--"] + [str(f) for f in files_to_remove],
            cwd=repo,
            env=_git_env(),
            check=True,
        )

    subprocess.run(
        ["git", "add", "--"] + [str(f) for f in files],
        cwd=repo,
        env=_git_env(),
        check=True,
    )

    commit_cmd = ["git", "commit", "-m", message]
    if no_verify:
        commit_cmd.append("--no-verify")

    subprocess.run(
        commit_cmd,
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


def stage_files(files: list[Path], repo: Path | None = None) -> None:
    """Stage specific files without committing."""
    repo = repo or Path.cwd()
    if not _has_changes_to_stage(files, repo):
        return
    subprocess.run(
        ["git", "add", "--"] + [str(f) for f in files],
        cwd=repo,
        env=_git_env(),
        check=True,
    )


def commit_artifact(
    path: Path,
    message: str,
    repo: Path | None = None,
    no_verify: bool = False,
) -> str | None:
    repo = repo or Path.cwd()
    return stage_and_commit(
        message=message, files=[path], repo=repo, no_verify=no_verify
    )
