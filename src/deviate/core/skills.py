from __future__ import annotations

from pathlib import Path


def discover_skills(skills_root: Path | None = None) -> list[str]:
    raise NotImplementedError


def resolve_skill(name: str, skills_root: Path | None = None) -> Path:
    raise NotImplementedError


def install_skill(name: str, target_dir: Path, skills_root: Path | None = None) -> bool:
    raise NotImplementedError
