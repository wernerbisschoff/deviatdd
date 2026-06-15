from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestConstitutionPre:
    """RED phase tests for TSK-004-02: Constitution CLI — constitution pre."""

    def test_constitution_pre_emits_commands(self, tmp_path: Path) -> None:
        """AC-005-01 (US-001-01): Valid constitution extracts commands."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        constitution_path = specs_dir / "constitution.md"
        constitution_path.write_text(
            "# Constitution\n"
            "\n"
            "## TESTING_PROTOCOLS\n"
            "\n"
            "- TEST_COMMAND: `mise run test`\n"
            "- LINT_COMMAND: `mise run lint`\n"
            "- TYPE_CHECK_COMMAND: `mise run check-types`\n"
            "\n"
            "## Other Section\n"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["constitution", "pre"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert "test_command" in data
        assert "lint_command" in data
        assert "type_check_command" in data

    def test_constitution_pre_missing_file(self, tmp_path: Path) -> None:
        """AC-005-01 (US-001-02): Missing constitution file returns FAILURE."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["constitution", "pre"])
        assert result.exit_code != 0, result.output
        data = json.loads(result.stdout)
        assert data["status"] == "FAILURE"
        assert "reason" in data

    def test_constitution_pre_missing_section(self, tmp_path: Path) -> None:
        """AC-005-02 (US-001-03): Missing TESTING_PROTOCOLS returns FAILURE."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        constitution_path = specs_dir / "constitution.md"
        constitution_path.write_text(
            "# Constitution\n\n## Some Other Section\n\nContent here.\n"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["constitution", "pre"])
        assert result.exit_code != 0, result.output
        data = json.loads(result.stdout)
        assert data["status"] == "FAILURE"
        assert "TESTING_PROTOCOLS" in data["reason"]


class TestConstitutionPost:
    """RED phase tests for TSK-004-02: Constitution CLI — constitution post."""

    def _make_constitution(self, tmp_path: Path) -> Path:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        constitution_path = specs_dir / "constitution.md"
        constitution_path.write_text(
            "# Constitution\n"
            "\n"
            "## TESTING_PROTOCOLS\n"
            "\n"
            "- TEST_COMMAND: `mise run test`\n"
        )
        return constitution_path

    def _make_manifest(self, tmp_path: Path, sections: list[str]) -> Path:
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {"sections": sections, "constitution_path": "specs/constitution.md"}
            )
        )
        return manifest_path

    @patch("deviate.cli.constitution.commit_artifact")
    def test_constitution_post_valid_manifest(
        self, mock_commit, tmp_path: Path
    ) -> None:
        """AC-005-03 (US-002-01): Valid manifest commits changes."""
        self._make_constitution(tmp_path)
        manifest_path = self._make_manifest(tmp_path, ["## TESTING_PROTOCOLS"])

        with chdir(tmp_path):
            result = runner.invoke(cli, ["constitution", "post", str(manifest_path)])

        assert result.exit_code == 0, result.output
        mock_commit.assert_called_once()

    def test_constitution_post_invalid_sections(self, tmp_path: Path) -> None:
        """AC-005-04 (US-002-02): Invalid manifest with missing sections fails."""
        self._make_constitution(tmp_path)
        manifest_path = self._make_manifest(tmp_path, ["## NONEXISTENT_SECTION"])

        with chdir(tmp_path):
            result = runner.invoke(cli, ["constitution", "post", str(manifest_path)])

        assert result.exit_code != 0, result.output
