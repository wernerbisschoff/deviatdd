from __future__ import annotations

from pathlib import Path

from deviate.core.skills import discover_skills


class TestDiscoverSkills:
    def test_discover_skills_lists_directories(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        (skills_root / "deviate-specify").mkdir(parents=True)
        (skills_root / "deviate-specify" / "SKILL.md").touch()
        (skills_root / "deviate-red").mkdir(parents=True)
        (skills_root / "deviate-red" / "SKILL.md").touch()
        result = discover_skills(skills_root=skills_root)
        assert "deviate-specify" in result
        assert "deviate-red" in result

    def test_discover_skills_skips_dirs_without_skill_md(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        (skills_root / "with-skill").mkdir(parents=True)
        (skills_root / "with-skill" / "SKILL.md").touch()
        (skills_root / "without-skill").mkdir(parents=True)
        result = discover_skills(skills_root=skills_root)
        assert "with-skill" in result
        assert "without-skill" not in result
