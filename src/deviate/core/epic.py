from __future__ import annotations

import re
import subprocess
import warnings
from pathlib import Path

from deviate.core._shared import git_env as _git_env

_FEAT_EPIC_PREFIX = re.compile(r"^(?:origin/)?feat/(\d+)-")


def _resolve_specs_root(specs_root: Path | None = None) -> Path:
    return specs_root or Path("specs")


def _discover_all(specs_root: Path | None = None) -> list[str]:
    root = _resolve_specs_root(specs_root)
    if not root.exists():
        return []
    result = sorted(
        d.name
        for d in root.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and (
            (
                d / "explore.md"
            ).exists()  # Any dir holding explore.md (legacy slug dir or post-research numbered bucket)
            or _extract_prefix_num(d.name)
            > 0  # New format: specs/NNN-slug/ (numbered bucket)
        )
    )
    # Surface the asymmetry: a numbered dir without explore.md is a
    # broken or pre-move state. The `prd pre` halt is the hard gate;
    # this warn is informational so operators can spot it.
    for name in result:
        if _extract_prefix_num(name) > 0 and not (root / name / "explore.md").exists():
            warnings.warn(
                f"epic dir {name} is numbered but missing explore.md; "
                f"this is a broken or pre-move state",
                stacklevel=2,
            )
    return result


def discover_epic(specs_root: Path | None = None) -> str:
    slug_dirs = _discover_all(specs_root)
    return slug_dirs[0] if slug_dirs else ""


def discover_latest_epic(specs_root: Path | None = None) -> str:
    slug_dirs = _discover_all(specs_root)
    if not slug_dirs:
        return ""
    return max(slug_dirs, key=lambda s: _extract_prefix_num(s))


def _extract_prefix_num(slug: str) -> int:
    try:
        return int(slug.split("-")[0])
    except (ValueError, IndexError):
        return 0


def _list_remote_feat_refs(repo_path: Path | None = None) -> list[str]:
    """Return already-fetched origin feat ref short names (no network)."""
    try:
        result = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/remotes/origin/feat/",
            ],
            cwd=repo_path or Path.cwd(),
            env=_git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _find_next_epic_num(root: Path, repo_path: Path | None = None) -> int:
    local_nums = [
        num
        for d in (root.iterdir() if root.is_dir() else ())
        if d.is_dir() and (num := _extract_prefix_num(d.name)) > 0
    ]
    remote_nums = [
        int(match.group(1))
        for ref in _list_remote_feat_refs(repo_path)
        if (match := _FEAT_EPIC_PREFIX.match(ref))
    ]
    return max([*local_nums, *remote_nums], default=0) + 1


def allocate_feature_bucket(
    slug: str,
    specs_root: Path | None = None,
    repo_path: Path | None = None,
) -> Path:
    root = _resolve_specs_root(specs_root)

    if _extract_prefix_num(slug) > 0:
        bucket = root / slug
        bucket.mkdir(parents=True, exist_ok=True)
        return bucket

    next_num = _find_next_epic_num(root, repo_path=repo_path)
    numbered_slug = f"{next_num:03d}-{slug}"
    bucket = root / numbered_slug
    bucket.mkdir(parents=True, exist_ok=True)
    return bucket


def resolve_active_feature(specs_root: Path | None = None) -> str:
    return discover_latest_epic(specs_root)
