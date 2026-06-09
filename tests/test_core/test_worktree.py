from __future__ import annotations

from pathlib import Path


from deviate.core.worktree import (
    create_worktree,
    detect_worktree,
    find_worktree_for_branch,
    validate_worktree,
)


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
