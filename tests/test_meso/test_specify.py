from __future__ import annotations

from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifySetup:
    def test_specify_without_issue_fails(self, tmp_git_repo: Path):
        """'deviate specify ISS-001-001' fails without ledger setup"""
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001"])
            assert result.exit_code == 1, result.output
            assert "ISSUE_NOT_FOUND" in result.output

    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' without --issue should fail"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output

    def test_specify_post_is_noop(self):
        """'deviate specify post' is a no-op with a clear message"""
        result = runner.invoke(cli, ["specify", "post"])
        assert result.exit_code == 0, result.output
        assert "SETUP_NOOP" in result.output
