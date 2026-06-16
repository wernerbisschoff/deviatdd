from __future__ import annotations

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifyPre:
    def test_specify_pre_emits_deprecation(self):
        """'deviate specify pre' now emits deprecation notice"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "DEPRECATED" in result.output
