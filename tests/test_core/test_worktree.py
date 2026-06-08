from __future__ import annotations

from pathlib import Path

import pytest

from deviate.core.worktree import (
    create_worktree,
    detect_worktree,
    validate_worktree,
)


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

    def test_create_worktree_with_existing_branch_fails(self, tmp_git_repo: Path):
        worktree_path = tmp_git_repo / "worktrees" / "main"
        with pytest.raises(RuntimeError):
            create_worktree(
                branch="main",
                path=worktree_path,
                repo=tmp_git_repo,
            )


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
