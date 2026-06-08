from __future__ import annotations

from pathlib import Path


def discover_epic(specs_root: Path | None = None) -> str:
    raise NotImplementedError


def allocate_feature_bucket(slug: str, specs_root: Path | None = None) -> Path:
    raise NotImplementedError


def resolve_active_feature(specs_root: Path | None = None) -> str:
    raise NotImplementedError
