from __future__ import annotations

from pathlib import Path


def _resolve_specs_root(specs_root: Path | None = None) -> Path:
    return specs_root or Path("specs")


def discover_epic(specs_root: Path | None = None) -> str:
    root = _resolve_specs_root(specs_root)
    if not root.exists():
        return ""
    slug_dirs = sorted(
        d.name
        for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "explore.md").exists()
    )
    return slug_dirs[0] if slug_dirs else ""


def allocate_feature_bucket(slug: str, specs_root: Path | None = None) -> Path:
    root = _resolve_specs_root(specs_root)
    bucket = root / slug
    bucket.mkdir(parents=True, exist_ok=True)
    return bucket


def resolve_active_feature(specs_root: Path | None = None) -> str:
    return discover_epic(specs_root)
