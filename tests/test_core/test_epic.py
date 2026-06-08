from __future__ import annotations

from pathlib import Path

from deviate.core.epic import discover_epic


class TestDiscoverEpic:
    def test_discover_epic_returns_slug(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        slug_dir = specs_root / "001-my-feature"
        slug_dir.mkdir(parents=True)
        (slug_dir / "explore.md").touch()
        result = discover_epic(specs_root=specs_root)
        assert result == "001-my-feature"
