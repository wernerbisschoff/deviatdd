from __future__ import annotations

from pathlib import Path

import pytest

from deviate.core.constitution import (
    extract_commands,
    resolve_constitution,
    validate_constitution,
    validate_placeholders,
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


class TestValidatePlaceholders:
    REQUIRED = frozenset(
        {
            "PROJECT_NAME",
            "REPO_ROOT",
            "TARGET_BACKEND_FRAMEWORK",
            "TARGET_PACKAGE_MANAGER",
            "TARGET_TEST_RUNNER",
            "TARGET_COVERAGE_MINIMUM",
        }
    )

    def _make_seed(self, tmp_path: Path, variables: set[str]) -> Path:
        path = tmp_path / "constitution_seed.md"
        lines = ["# Test Seed\n"]
        for var in sorted(variables):
            lines.append(f"${{{var}}}\n")
        path.write_text("".join(lines))
        return path

    def test_validate_placeholders_all_present(self, tmp_path: Path):
        path = self._make_seed(tmp_path, self.REQUIRED)
        result = validate_placeholders(path)
        assert result.all_present is True
        assert sorted(result.variables) == sorted(self.REQUIRED)
        assert result.missing == []

    def test_validate_placeholders_missing_variable(self, tmp_path: Path):
        present = self.REQUIRED - {"TARGET_COVERAGE_MINIMUM"}
        path = self._make_seed(tmp_path, present)
        result = validate_placeholders(path)
        assert result.all_present is False
        assert result.missing == ["TARGET_COVERAGE_MINIMUM"]

    def test_validate_placeholders_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            validate_placeholders(Path("/nonexistent/seed.md"))

    def test_validate_placeholders_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty_seed.md"
        path.write_text("")
        result = validate_placeholders(path)
        assert result.all_present is False
        assert sorted(result.missing) == sorted(self.REQUIRED)

    def test_validate_placeholders_extra_variables_ignored(self, tmp_path: Path):
        extras = self.REQUIRED | {"EXTRA_VAR", "ANOTHER_EXTRA"}
        path = self._make_seed(tmp_path, extras)
        result = validate_placeholders(path)
        assert result.all_present is True
        assert "EXTRA_VAR" not in result.variables
        assert result.missing == []
