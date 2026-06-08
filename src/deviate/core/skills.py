from __future__ import annotations

import shutil
from pathlib import Path


def _resolve_skills_root(skills_root: Path | None = None) -> Path:
    return skills_root or Path("src/deviate/prompts/skills")


def discover_skills(skills_root: Path | None = None) -> list[str]:
    root = _resolve_skills_root(skills_root)
    if not root.exists():
        return []
    return sorted(
        d.name for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    )


def resolve_skill(name: str, skills_root: Path | None = None) -> Path:
    root = _resolve_skills_root(skills_root)
    skill_path = root / name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{name}' not found at {skill_path}")
    return skill_path


def install_skill(name: str, target_dir: Path, skills_root: Path | None = None) -> bool:
    skill_path = resolve_skill(name, skills_root)
    target_path = target_dir / name / "SKILL.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.read_text(
        encoding="utf-8"
    ) == skill_path.read_text(encoding="utf-8"):
        return False
    shutil.copy2(skill_path, target_path)
    return True
