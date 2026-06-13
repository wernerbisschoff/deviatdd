from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from tests.conftest import _git_env

runner = CliRunner()


class TestFeatureCreate:
    def test_feature_create_scaffold(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["feature", "create", "auth overhaul"])

        assert result.exit_code == 0, f"stdout: {result.stdout}"

        assert (tmp_git_repo / "specs" / "auth-overhaul").is_dir()

        branch_out = subprocess.run(
            ["git", "branch", "--list", "feat/auth-overhaul"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        assert "feat/auth-overhaul" in branch_out.stdout

        session_path = tmp_git_repo / ".deviate" / "session.json"
        assert session_path.exists()

    def test_feature_create_existing_branch(self, tmp_git_repo: Path) -> None:
        subprocess.run(
            ["git", "checkout", "-b", "feat/auth-overhaul"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["feature", "create", "auth overhaul"])

        assert result.exit_code == 0, f"stdout: {result.stdout}"

    def test_feature_create_explicit_slug(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["feature", "create", "auth overhaul", "--slug", "user-auth"]
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}"

        assert (tmp_git_repo / "specs" / "user-auth").is_dir()

        branch_out = subprocess.run(
            ["git", "branch", "--list", "feat/user-auth"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        assert "feat/user-auth" in branch_out.stdout
