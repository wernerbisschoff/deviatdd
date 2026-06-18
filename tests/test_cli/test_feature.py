from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from tests.conftest import _git_env

runner = CliRunner()


def _mock_subprocess_run(args, *a, **kw):
    if kw.get("check"):
        return subprocess.CompletedProcess(args, returncode=0)
    return subprocess.CompletedProcess(args, returncode=1)


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


class TestFeatureCreateWithGraphite:
    def test_feature_create_with_graphite_enabled(self, tmp_git_repo: Path) -> None:
        dot_dir = tmp_git_repo / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text("graphite = true\n", encoding="utf-8")

        with patch(
            "deviate.cli.feature.subprocess.run", side_effect=_mock_subprocess_run
        ) as mock_run:
            with chdir(tmp_git_repo):
                result = runner.invoke(cli, ["feature", "create", "test feature"])

        assert result.exit_code == 0, f"stdout: {result.stdout}"

        gt_calls = [
            call_args
            for call_args in mock_run.call_args_list
            if call_args.args[0][0] == "gt"
        ]
        assert len(gt_calls) > 0, (
            "Expected `gt` subprocess call when graphite is enabled, "
            f"but got: {[ca.args[0] for ca in mock_run.call_args_list]}"
        )
        assert gt_calls[0].args[0] == [
            "gt",
            "create",
            "-am",
            "feat/test-feature",
        ]

    def test_feature_create_with_graphite_disabled(self, tmp_git_repo: Path) -> None:
        with patch(
            "deviate.cli.feature.subprocess.run", side_effect=_mock_subprocess_run
        ) as mock_run:
            with chdir(tmp_git_repo):
                result = runner.invoke(cli, ["feature", "create", "test feature"])

        assert result.exit_code == 0, f"stdout: {result.stdout}"

        gt_calls = [
            call_args
            for call_args in mock_run.call_args_list
            if call_args.args[0][0] == "gt"
        ]
        assert len(gt_calls) == 0, (
            "Expected NO `gt` subprocess calls when graphite is disabled, "
            f"but got: {[ca.args[0] for ca in mock_run.call_args_list]}"
        )

        git_branch_calls = [
            call_args
            for call_args in mock_run.call_args_list
            if call_args.args[0][:2] == ["git", "branch"]
        ]
        assert len(git_branch_calls) > 0, (
            "Expected `git branch` call when graphite is disabled, "
            f"but got: {[ca.args[0] for ca in mock_run.call_args_list]}"
        )
