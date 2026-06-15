from __future__ import annotations

from pathlib import Path


def _resolve_specs_root(specs_root: Path | None = None) -> Path:
    return specs_root or Path("specs")


def _discover_all(specs_root: Path | None = None) -> list[str]:
    root = _resolve_specs_root(specs_root)
    if not root.exists():
        return []
    return sorted(
        d.name
        for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "explore.md").exists()
    )


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
    if not root.exists():
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
