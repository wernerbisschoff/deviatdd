from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifyDeprecatedStubs:
    def test_specify_emits_deprecation(self):
        """'deviate specify' should print deprecation notice and exit 0"""
        result = runner.invoke(cli, ["specify", "ISS-001-001"])
        assert result.exit_code == 0, result.output
        assert "DEPRECATED" in result.output
        assert "deviate shard" in result.output

    def test_specify_pre_emits_deprecation(self, tmp_path: Path):
        """'deviate specify pre' should print deprecation notice"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "DEPRECATED" in result.output

    def test_specify_post_emits_deprecation(self):
        """'deviate specify post' should print deprecation notice"""
        result = runner.invoke(cli, ["specify", "post"])
        assert result.exit_code == 0, result.output
        assert "DEPRECATED" in result.output
