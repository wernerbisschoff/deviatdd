from __future__ import annotations

import warnings
from pathlib import Path


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


def _find_next_epic_num(root: Path) -> int:
    if not root.is_dir():
        return 1
    nums = [
        _extract_prefix_num(d.name)
        for d in root.iterdir()
        if d.is_dir() and _extract_prefix_num(d.name) > 0
    ]
    return max(nums, default=0) + 1


def allocate_feature_bucket(slug: str, specs_root: Path | None = None) -> Path:
    root = _resolve_specs_root(specs_root)

    if _extract_prefix_num(slug) > 0:
        bucket = root / slug
        bucket.mkdir(parents=True, exist_ok=True)
        return bucket

    next_num = _find_next_epic_num(root)
    numbered_slug = f"{next_num:03d}-{slug}"
    bucket = root / numbered_slug
    bucket.mkdir(parents=True, exist_ok=True)
    return bucket


def resolve_active_feature(specs_root: Path | None = None) -> str:
    return discover_latest_epic(specs_root)
