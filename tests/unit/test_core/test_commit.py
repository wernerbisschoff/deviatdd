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

    def test_stage_and_commit_with_files_to_remove_records_rename(
        self, tmp_git_repo: Path
    ) -> None:
        """``stage_and_commit(files_to_remove=[old])`` records the
        add+delete as a single commit. Git's rename detection usually
        surfaces this as an ``R100`` line; the contract is that the
        old path is gone from the index and the new path is present.
        """
        old = tmp_git_repo / "old.txt"
        old.write_text("hello\n")
        new = tmp_git_repo / "new.txt"
        new.write_text("hello\n")

        subprocess.run(
            ["git", "add", "old.txt"], cwd=tmp_git_repo, env=_git_env(), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "seed old.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        sha = stage_and_commit(
            message="chore: rename old.txt to new.txt",
            files=[new],
            files_to_remove=[old],
            repo=tmp_git_repo,
        )
        assert sha is not None

        show = subprocess.run(
            ["git", "show", "--name-status", "--format=", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        # Git may render this as ``R100 old.txt new.txt`` OR
        # ``A  new.txt`` + ``D  old.txt`` — both are correct.
        assert "new.txt" in show
        assert "old.txt" in show

    def test_stage_and_commit_files_to_remove_skips_when_nothing_changes(
        self, tmp_git_repo: Path
    ) -> None:
        """If both ``files`` and ``files_to_remove`` resolve to no
        index changes, ``stage_and_commit`` returns ``None`` and no
        commit is created.
        """
        tracked = tmp_git_repo / "stable.txt"
        tracked.write_text("stable\n")
        subprocess.run(
            ["git", "add", "stable.txt"], cwd=tmp_git_repo, env=_git_env(), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "seed stable.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        sha = stage_and_commit(
            message="noop",
            files=[tracked],
            files_to_remove=[tracked],
            repo=tmp_git_repo,
        )
        assert sha is None, f"expected None when nothing changes, got {sha!r}"

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
