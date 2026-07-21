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


class TestDiscoverAllWarnsLegacy:
    """A numbered epic dir missing `explore.md` is the legacy
    `001-*`/`002-*`/`003-*` shape that pre-dates the explore.md move.
    `_discover_all` keeps returning it but must surface the asymmetry
    via `warnings.warn` so operators can spot it.
    """

    def test_warns_on_numbered_dir_without_explore(self, tmp_path: Path):
        import pytest

        from deviate.core.epic import _discover_all

        specs_root = tmp_path / "specs"
        legacy = specs_root / "001-legacy"
        legacy.mkdir(parents=True)
        # No explore.md inside the numbered bucket — legacy shape.
        (legacy / "design.md").touch()

        fresh = specs_root / "002-fresh"
        fresh.mkdir(parents=True)
        (fresh / "explore.md").touch()  # new shape: explore.md inside

        with pytest.warns(UserWarning, match="001-legacy"):
            discovered = _discover_all(specs_root=specs_root)

        assert "001-legacy" in discovered
        assert "002-fresh" in discovered
