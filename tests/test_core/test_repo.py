from __future__ import annotations

from pathlib import Path

import pytest

from deviate.core.repo import find_repo_root, gather_git_state


class TestFindRepoRoot:
    def test_find_repo_root_from_subdir(self, tmp_git_repo: Path):
        subdir = tmp_git_repo / "subdir"
        subdir.mkdir()
        result = find_repo_root(start_at=subdir)
        assert result == tmp_git_repo

    def test_find_repo_root_from_root(self, tmp_git_repo: Path):
        result = find_repo_root(start_at=tmp_git_repo)
        assert result == tmp_git_repo

    def test_raises_when_not_in_repo(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not a git repository"):
            find_repo_root(start_at=tmp_path)


class TestGatherGitState:
    def test_gather_git_state_clean(self, tmp_git_repo: Path):
        state = gather_git_state(repo=tmp_git_repo)
        assert state["staged_files"] == []
        assert state["unstaged_files"] == []
        assert state["untracked_files"] == []

    def test_gather_git_state_with_untracked(self, tmp_git_repo: Path):
        (tmp_git_repo / "new_file.txt").write_text("hello")
        state = gather_git_state(repo=tmp_git_repo)
        assert "new_file.txt" in state["untracked_files"]
