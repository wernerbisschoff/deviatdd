from __future__ import annotations

import subprocess
from pathlib import Path

from tests.conftest import _git_env

from deviate.core.commit import commit_artifact, stage_and_commit


class TestStageAndCommit:
    def test_stage_and_commit_creates_commit(self, tmp_git_repo: Path):
        file_path = tmp_git_repo / "test_file.txt"
        file_path.write_text("hello")
        sha = stage_and_commit(
            message="feat: add test file",
            files=[file_path],
            repo=tmp_git_repo,
        )
        assert sha is not None
        assert isinstance(sha, str)
        assert len(sha) == 40

        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat: add test file" in result.stdout

    def test_stage_and_commit_multiple_files(self, tmp_git_repo: Path):
        a = tmp_git_repo / "a.txt"
        b = tmp_git_repo / "b.txt"
        a.write_text("a")
        b.write_text("b")
        sha = stage_and_commit(
            message="feat: add two files",
            files=[a, b],
            repo=tmp_git_repo,
        )
        assert sha is not None
        assert len(sha) == 40

    def test_stage_and_commit_returns_none_when_nothing_to_stage(
        self, tmp_git_repo: Path
    ):
        file_path = tmp_git_repo / "committed_already.txt"
        file_path.write_text("content")
        stage_and_commit(
            message="feat: initial commit",
            files=[file_path],
            repo=tmp_git_repo,
        )

        before_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        sha = stage_and_commit(
            message="feat: should not commit",
            files=[file_path],
            repo=tmp_git_repo,
        )
        assert sha is None, (
            f"expected None when nothing to stage, got {sha!r} — "
            "this would mislead callers into printing a fake COMMITTED message"
        )

        after_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert before_sha == after_sha, "no new commit should have been created"

    def test_commit_artifact_returns_none_when_no_changes(self, tmp_git_repo: Path):
        artifact = tmp_git_repo / "artifact.md"
        artifact.write_text("# Artifact")
        commit_artifact(path=artifact, message="docs: initial", repo=tmp_git_repo)

        sha = commit_artifact(
            path=artifact, message="docs: should not commit", repo=tmp_git_repo
        )
        assert sha is None


class TestCommitArtifact:
    def test_commit_artifact_creates_commit(self, tmp_git_repo: Path):
        artifact = tmp_git_repo / "artifact.md"
        artifact.write_text("# Artifact")
        sha = commit_artifact(
            path=artifact,
            message="docs: add artifact",
            repo=tmp_git_repo,
        )
        assert sha is not None
        assert isinstance(sha, str)
        assert len(sha) == 40

    def test_commit_artifact_visible_in_log(self, tmp_git_repo: Path):
        artifact = tmp_git_repo / "artifact.md"
        artifact.write_text("# Artifact")
        commit_artifact(
            path=artifact,
            message="docs: add artifact",
            repo=tmp_git_repo,
        )
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "docs: add artifact" in result.stdout
