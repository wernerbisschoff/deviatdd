from __future__ import annotations

from pathlib import Path


from deviate.core.worktree import (
    DEFAULT_WORKTREE_ROOT_NAME,
    LEGACY_WORKTREE_ROOT_NAME,
    create_worktree,
    detect_worktree,
    expected_branch_from_worktree_path,
    find_worktree_for_branch,
    resolve_start_point,
    resolve_worktree_root,
    validate_worktree,
    worktree_gitignore_entries,
)


class TestResolveWorktreeRoot:
    def test_fresh_repo_uses_wt(self, tmp_path: Path):
        assert resolve_worktree_root(tmp_path) == tmp_path / DEFAULT_WORKTREE_ROOT_NAME

    def test_legacy_only_stays_sticky(self, tmp_path: Path):
        (tmp_path / LEGACY_WORKTREE_ROOT_NAME).mkdir()
        assert resolve_worktree_root(tmp_path) == tmp_path / LEGACY_WORKTREE_ROOT_NAME

    def test_wt_only_uses_wt(self, tmp_path: Path):
        (tmp_path / DEFAULT_WORKTREE_ROOT_NAME).mkdir()
        assert resolve_worktree_root(tmp_path) == tmp_path / DEFAULT_WORKTREE_ROOT_NAME

    def test_both_exist_prefers_wt_for_new_trees(self, tmp_path: Path):
        (tmp_path / DEFAULT_WORKTREE_ROOT_NAME).mkdir()
        (tmp_path / LEGACY_WORKTREE_ROOT_NAME).mkdir()
        assert resolve_worktree_root(tmp_path) == tmp_path / DEFAULT_WORKTREE_ROOT_NAME

    def test_does_not_rename_legacy_dir(self, tmp_path: Path):
        legacy = tmp_path / LEGACY_WORKTREE_ROOT_NAME
        legacy.mkdir()
        resolve_worktree_root(tmp_path)
        assert legacy.is_dir()
        assert not (tmp_path / DEFAULT_WORKTREE_ROOT_NAME).exists()


class TestExpectedBranchFromWorktreePath:
    def test_wt_root_returns_full_branch(self):
        path = Path("/repo") / DEFAULT_WORKTREE_ROOT_NAME / "feat" / "epic" / "iss-001"
        assert expected_branch_from_worktree_path(path) == "feat/epic/iss-001"

    def test_legacy_root_returns_full_branch(self):
        path = Path("/repo") / LEGACY_WORKTREE_ROOT_NAME / "feat" / "epic" / "iss-001"
        assert expected_branch_from_worktree_path(path) == "feat/epic/iss-001"

    def test_keeps_full_branch_including_suffix(self):
        path = (
            Path("/repo")
            / DEFAULT_WORKTREE_ROOT_NAME
            / "feat"
            / "epic"
            / "iss-001-retry"
        )
        assert expected_branch_from_worktree_path(path) == "feat/epic/iss-001-retry"

    def test_legacy_root_with_wt_in_branch_name(self):
        path = Path("/repo") / LEGACY_WORKTREE_ROOT_NAME / "wt" / "feature"
        assert expected_branch_from_worktree_path(path) == "wt/feature"

    def test_not_under_legal_root_returns_none(self):
        assert expected_branch_from_worktree_path(Path("/repo/src/foo")) is None

    def test_root_dirname_alone_returns_none(self):
        assert (
            expected_branch_from_worktree_path(
                Path("/repo") / DEFAULT_WORKTREE_ROOT_NAME
            )
            is None
        )


class TestWorktreeGitignoreEntries:
    def test_includes_both_legal_roots(self):
        entries = worktree_gitignore_entries()
        assert f"{DEFAULT_WORKTREE_ROOT_NAME}/" in entries
        assert f"{LEGACY_WORKTREE_ROOT_NAME}/" in entries


class TestFindWorktreeForBranch:
    def test_returns_none_for_nonexistent_branch(self, tmp_git_repo: Path):
        assert find_worktree_for_branch("no-such-branch", repo=tmp_git_repo) is None

    def test_returns_path_for_existing_branch(self, tmp_git_repo: Path):
        wt_path = tmp_git_repo / "worktrees" / "feat-test"
        create_worktree(branch="feat-test", path=wt_path, repo=tmp_git_repo)
        found = find_worktree_for_branch("feat-test", repo=tmp_git_repo)
        assert found is not None
        assert found.resolve() == wt_path.resolve()


class TestCreateWorktree:
    def test_create_worktree_returns_path(self, tmp_git_repo: Path):
        worktree_path = tmp_git_repo / "worktrees" / "test-feature"
        result = create_worktree(
            branch="test-feature",
            path=worktree_path,
            repo=tmp_git_repo,
        )
        assert result == worktree_path
        assert result.exists()
        assert (result / ".git").exists() or (result / ".git").is_file()

    def test_create_worktree_existing_worktree_returns_existing(
        self, tmp_git_repo: Path
    ):
        wt_path = tmp_git_repo / "worktrees" / "existing-branch"
        first = create_worktree(
            branch="existing-branch",
            path=wt_path,
            repo=tmp_git_repo,
        )
        second = create_worktree(
            branch="existing-branch",
            path=wt_path,
            repo=tmp_git_repo,
        )
        assert first == second

    def test_create_worktree_uses_start_point(self, tmp_git_repo: Path):
        import subprocess

        from deviate.core._shared import git_env as _git_env

        subprocess.run(
            ["git", "checkout", "-b", "wb-dev"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        (tmp_git_repo / "trunk.txt").write_text("from-trunk\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "trunk.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "trunk marker"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        wt_path = tmp_git_repo / "worktrees" / "from-trunk"
        create_worktree(
            branch="from-trunk",
            path=wt_path,
            repo=tmp_git_repo,
            start_point="wb-dev",
        )
        assert (wt_path / "trunk.txt").read_text(encoding="utf-8") == "from-trunk\n"

    def test_resolve_start_point_falls_back_to_head(self, tmp_git_repo: Path):
        assert resolve_start_point("does-not-exist", repo=tmp_git_repo) == "HEAD"

    def test_resolve_start_point_prefers_local_base_over_stale_origin(
        self, tmp_git_repo: Path
    ):
        """Local trunk wins when origin/<base> is an ancestor (local-only issues).

        Meso discovers issues from the local ledger, so the worktree base must
        come from the local trunk even when origin/<base> exists but is behind.
        """
        import subprocess

        from deviate.core._shared import git_env as _git_env

        (tmp_git_repo / "local.txt").write_text("local-only\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "local.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "local trunk ahead"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        # Point origin/main at the parent commit so it lacks local.txt.
        parent = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/main", parent],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        assert resolve_start_point("main", repo=tmp_git_repo) == "main"


class TestDetectWorktree:
    def test_detect_worktree_no_worktrees(self, tmp_git_repo: Path):
        result = detect_worktree(repo=tmp_git_repo)
        assert isinstance(result, dict)
        assert len(result) >= 1

    def test_detect_worktree_after_creation(self, tmp_git_repo: Path):
        worktree_path = tmp_git_repo / "worktrees" / "detect-feature"
        create_worktree(
            branch="detect-feature",
            path=worktree_path,
            repo=tmp_git_repo,
        )
        result = detect_worktree(repo=tmp_git_repo)
        assert any("detect-feature" in str(v) for v in result.values())


class TestValidateWorktree:
    def test_validate_existing_worktree(self, tmp_git_repo: Path):
        worktree_path = tmp_git_repo / "worktrees" / "validate-feature"
        create_worktree(
            branch="validate-feature",
            path=worktree_path,
            repo=tmp_git_repo,
        )
        assert validate_worktree(worktree_path) is True

    def test_validate_nonexistent_path(self, tmp_path: Path):
        assert validate_worktree(tmp_path / "nonexistent") is False


class TestVerifyWorktreeBranch:
    """``_verify_worktree_branch`` accepts both legal roots and compares HEAD."""

    def _checkout_worktree(self, tmp_git_repo: Path, root_name: str) -> Path:
        import subprocess

        from tests.conftest import _git_env

        branch = "feat/epic/iss-001"
        path = tmp_git_repo / root_name / "feat" / "epic" / "iss-001"
        create_worktree(branch=branch, path=path, repo=tmp_git_repo)
        head = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head == branch
        return path

    def test_accepts_wt_path_matching_head(self, tmp_git_repo: Path):
        from deviate.cli.micro import _verify_worktree_branch

        path = self._checkout_worktree(tmp_git_repo, DEFAULT_WORKTREE_ROOT_NAME)
        _verify_worktree_branch(path)

    def test_accepts_legacy_path_matching_head(self, tmp_git_repo: Path):
        from deviate.cli.micro import _verify_worktree_branch

        path = self._checkout_worktree(tmp_git_repo, LEGACY_WORKTREE_ROOT_NAME)
        _verify_worktree_branch(path)

    def test_rejects_head_mismatch_under_wt(self, tmp_git_repo: Path):
        import subprocess

        import pytest
        import typer

        from deviate.cli.micro import _verify_worktree_branch
        from tests.conftest import _git_env

        path = self._checkout_worktree(tmp_git_repo, DEFAULT_WORKTREE_ROOT_NAME)
        subprocess.run(
            ["git", "checkout", "-b", "other-branch"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        with pytest.raises(typer.Exit) as exc_info:
            _verify_worktree_branch(path)
        assert exc_info.value.exit_code == 78

    def test_skips_path_not_under_legal_root(self, tmp_git_repo: Path):
        from deviate.cli.micro import _verify_worktree_branch

        _verify_worktree_branch(tmp_git_repo)
