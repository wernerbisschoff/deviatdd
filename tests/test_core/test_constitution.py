from __future__ import annotations

from pathlib import Path

import pytest

from deviate.core.constitution import (
    extract_commands,
    resolve_constitution,
    validate_constitution,
)


class TestResolveConstitution:
    def test_resolve_constitution_finds_file(self, tmp_path: Path):
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        constitution_path = specs_dir / "constitution.md"
        constitution_path.write_text("# Constitution")
        result = resolve_constitution(repo_root=tmp_path)
        assert result == constitution_path

    def test_resolve_constitution_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="constitution.md"):
            resolve_constitution(repo_root=tmp_path)


class TestValidateConstitution:
    def test_validate_valid_constitution(self, tmp_path: Path):
        path = tmp_path / "constitution.md"
        path.write_text(
            "## [TESTING_PROTOCOLS]\nTEST_COMMAND: pytest\nLINT_COMMAND: ruff check .\n"
        )
        assert validate_constitution(path) is True

    def test_validate_empty_constitution(self, tmp_path: Path):
        path = tmp_path / "constitution.md"
        path.write_text("")
        assert validate_constitution(path) is False

    def test_validate_missing_file(self):
        assert validate_constitution(Path("/nonexistent/constitution.md")) is False


class TestExtractCommands:
    def test_extract_test_command(self, tmp_path: Path):
        path = tmp_path / "constitution.md"
        path.write_text(
            "## [3_TESTING_PROTOCOLS]\n"
            "\n"
            "### [3_1_FRAMEWORK]\n"
            "- `TEST_COMMAND`: pytest tests/ -v\n"
            "- `LINT_COMMAND`: ruff check .\n"
        )
        commands = extract_commands(path)
        assert "test_command" in commands
        assert "lint_command" in commands

    def test_extract_commands_empty_section(self, tmp_path: Path):
        path = tmp_path / "constitution.md"
        path.write_text("## [3_TESTING_PROTOCOLS]\n")
        commands = extract_commands(path)
        assert commands == {}
