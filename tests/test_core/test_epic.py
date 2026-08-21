from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core.epic import allocate_feature_bucket, discover_epic
from tests.conftest import _git_env


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


def _seed_origin_feat_ref(repo: Path, feat_suffix: str) -> None:
    """Point an already-fetched origin feat ref at HEAD (no network)."""
    subprocess.run(
        [
            "git",
            "update-ref",
            f"refs/remotes/origin/feat/{feat_suffix}",
            "HEAD",
        ],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )


def _bucket_num(bucket: Path) -> int:
    return int(bucket.name.split("-")[0])


class TestAllocateFeatureBucketRemoteAware:
    """AC-PLAN-002: next epic bucket counts remote feat/<NNN>-* prefixes."""

    def test_unnumbered_slug_allocates_above_remote_feat_005(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_origin_feat_ref(tmp_git_repo, "005-acceptance-gates")
        specs_root = tmp_git_repo / "specs"
        specs_root.mkdir()
        assert not any(specs_root.glob("005-*"))

        bucket = allocate_feature_bucket(
            "remote-aware-slug",
            specs_root=specs_root,
            repo_path=tmp_git_repo,
        )

        assert _bucket_num(bucket) > 5
        assert bucket.parent == specs_root
        assert bucket.is_dir()

    def test_numbered_slug_stays_idempotent_when_remote_feat_exists(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_origin_feat_ref(tmp_git_repo, "005-acceptance-gates")
        specs_root = tmp_git_repo / "specs"
        specs_root.mkdir()

        first = allocate_feature_bucket(
            "005-acceptance-gates",
            specs_root=specs_root,
            repo_path=tmp_git_repo,
        )
        second = allocate_feature_bucket(
            "005-acceptance-gates",
            specs_root=specs_root,
            repo_path=tmp_git_repo,
        )

        assert first == second
        assert first.name == "005-acceptance-gates"
        assert first.is_dir()
        assert list(specs_root.iterdir()) == [first]

    def test_local_only_feat_branch_does_not_reserve_epic_number(
        self, tmp_git_repo: Path
    ) -> None:
        subprocess.run(
            ["git", "branch", "feat/005-local-only"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        specs_root = tmp_git_repo / "specs"
        specs_root.mkdir()

        bucket = allocate_feature_bucket(
            "from-local-only",
            specs_root=specs_root,
            repo_path=tmp_git_repo,
        )

        assert _bucket_num(bucket) == 1
        assert bucket.name.endswith("-from-local-only")

    def test_nested_feat_issue_ref_counts_epic_prefix_not_issue_ordinal(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_origin_feat_ref(tmp_git_repo, "005-acceptance-gates/003-issue")
        specs_root = tmp_git_repo / "specs"
        specs_root.mkdir()

        bucket = allocate_feature_bucket(
            "nested-prefix",
            specs_root=specs_root,
            repo_path=tmp_git_repo,
        )

        assert _bucket_num(bucket) > 5
