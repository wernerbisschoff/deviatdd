#!/usr/bin/env python3
"""Compute the next SemVer for an on-demand GitHub Actions release cut.

Reads the current ``version`` from ``pyproject.toml``, inspects conventional
commits since the commit that set that version (falling back to the latest
``v*`` tag, then the previous ``chore(release):`` commit), and prints the
next ``X.Y.Z`` on stdout.

Bump rules (highest wins):

- ``BREAKING CHANGE`` / ``feat!:`` / ``fix!:`` → major
- ``feat:`` → minor
- ``fix:`` → patch
- only ``chore`` / ``docs`` / ``test`` / ``ci`` / ``style`` / ``refactor``
  → patch (a manual cut still produces a new version)
- no conventional commits since the baseline → patch
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

_TYPES = ("feat", "fix", "chore", "docs", "test", "ci", "style", "refactor")
_SUBJECT_RE = re.compile(
    rf"^(?:(?P<type>{'|'.join(_TYPES)})"
    rf"(?P<scope>\([^)]*\))?(?P<breaking>!)?:"
    rf")\s",
    re.IGNORECASE,
)
_BREAKING_RE = re.compile(r"BREAKING[ -]CHANGE", re.IGNORECASE)
_PYPROJECT_VERSION_RE = re.compile(
    r'^version\s*=\s*["\']([^"\']+)["\']\s*$',
    re.MULTILINE,
)
_LOCK_VERSION_RE = re.compile(
    r'(name = "deviatdd"\nversion = ")[^"]+(")',
)
_RELEASE_SUBJECT_RE = r"^chore\(release\): version "
_RANK = {"major": 3, "minor": 2, "patch": 1}


def git_env() -> dict[str, str]:
    """Strip GIT_*/GH_* so subprocess git never inherits a parent repo."""
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_") and not k.startswith("GH_")
    }


def _git(*args: str, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=git_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def read_current_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION_RE.search(text)
    if match is None:
        raise SystemExit(f"version not found in {pyproject}")
    return match.group(1)


def bump_semver(version: str, level: str) -> str:
    try:
        major_s, minor_s, patch_s = version.split(".")
        major, minor, patch = int(major_s), int(minor_s), int(patch_s)
    except ValueError as exc:
        raise SystemExit(f"not a X.Y.Z version: {version!r}") from exc
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"unknown bump level: {level!r}")


def classify_commit(message: str) -> str | None:
    if _BREAKING_RE.search(message):
        return "major"
    subject = message.split("\n", 1)[0].strip()
    match = _SUBJECT_RE.match(subject)
    if match is None:
        return None
    if match.group("breaking"):
        return "major"
    commit_type = match.group("type").lower()
    if commit_type == "feat":
        return "minor"
    if commit_type == "fix":
        return "patch"
    if commit_type in {"chore", "docs", "test", "ci", "style", "refactor"}:
        return "patch"
    return None


def highest_bump(messages: list[str]) -> str:
    rank = 0
    for message in messages:
        level = classify_commit(message)
        if level is None:
            continue
        rank = max(rank, _RANK[level])
    if rank == 0:
        return "patch"
    for name, value in _RANK.items():
        if value == rank:
            return name
    return "patch"


def _pickaxe_version_commit(repo: Path, version: str) -> str | None:
    needle = f'version = "{version}"'
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "-S", needle, "--", "pyproject.toml"],
        cwd=repo,
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha or None


def _latest_v_tag(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "tag", "-l", "v*", "--sort=-v:refname"],
        cwd=repo,
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None


def _latest_release_commit(repo: Path) -> str | None:
    result = subprocess.run(
        [
            "git",
            "log",
            "-1",
            "--extended-regexp",
            f"--grep={_RELEASE_SUBJECT_RE}",
            "--format=%H",
        ],
        cwd=repo,
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha or None


def find_version_baseline(repo: Path, current_version: str) -> str:
    for candidate in (
        _pickaxe_version_commit(repo, current_version),
        _latest_v_tag(repo),
        _latest_release_commit(repo),
    ):
        if candidate:
            return candidate
    raise SystemExit(
        "could not determine version baseline "
        "(no pyproject version commit, v* tag, or chore(release) commit)"
    )


def commits_since(repo: Path, baseline: str) -> list[str]:
    result = _git("log", f"{baseline}..HEAD", "--format=%B%x1e", repo=repo)
    return [block.strip() for block in result.stdout.split("\x1e") if block.strip()]


def compute_next_version(repo: Path, bump: str = "auto") -> str:
    pyproject = repo / "pyproject.toml"
    current = read_current_version(pyproject)
    if bump != "auto":
        return bump_semver(current, bump)
    baseline = find_version_baseline(repo, current)
    level = highest_bump(commits_since(repo, baseline))
    return bump_semver(current, level)


def persist_version(repo: Path, version: str) -> None:
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    updated, count = _PYPROJECT_VERSION_RE.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise SystemExit(f"failed to write version in {pyproject}")
    pyproject.write_text(updated, encoding="utf-8")

    lock = repo / "uv.lock"
    if not lock.is_file():
        raise SystemExit(f"uv.lock not found at {lock}")
    lock_text = lock.read_text(encoding="utf-8")
    lock_updated, lock_count = _LOCK_VERSION_RE.subn(
        rf"\g<1>{version}\2", lock_text, count=1
    )
    if lock_count != 1:
        raise SystemExit(f'failed to write name = "deviatdd" version in {lock}')
    lock.write_text(lock_updated, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: cwd)",
    )
    parser.add_argument(
        "--bump",
        choices=("auto", "patch", "minor", "major"),
        default="auto",
        help="bump level (default: auto from conventional commits)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist the computed version to pyproject.toml and uv.lock",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the computed version and skip all writes",
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    version = compute_next_version(repo, bump=args.bump)
    print(version)
    if args.dry_run:
        print(f"dry_run: next version is {version} (no files written)", file=sys.stderr)
        return 0
    if args.write:
        persist_version(repo, version)
        print(f"wrote {version} to pyproject.toml and uv.lock", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
