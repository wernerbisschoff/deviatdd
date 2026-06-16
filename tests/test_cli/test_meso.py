from __future__ import annotations

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifyPre:
    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' requires --issue flag"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output
