import warnings
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import _resolve_placeholder, cli

runner = CliRunner()


class TestResolvePlaceholder:
    """RED phase tests for TSK-001-04: Extended Placeholder Resolution (2→6 Variables)."""

    def test_resolve_placeholder_complete(self, tmp_path: Path):
        """AC-010-01: Complete pyproject.toml resolves all 6 placeholders."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "my-project"
dependencies = [
    "fastapi>=0.100.0",
    "pydantic>=2.0.0",
]

[tool.uv]
dev-dependencies = ["pytest>=7.0"]

[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
""")
        result = _resolve_placeholder(repo_root=tmp_path)
        assert result["PROJECT_NAME"] == "my-project"
        assert result["REPO_ROOT"] == str(tmp_path.resolve())
        assert result["TARGET_BACKEND_FRAMEWORK"] == "fastapi"
        assert result["TARGET_PACKAGE_MANAGER"] == "uv"
        assert result["TARGET_TEST_RUNNER"] == "pytest"
        assert result["TARGET_COVERAGE_MINIMUM"] == "80"

    def test_resolve_placeholder_missing_pyproject(self, tmp_path: Path):
        """AC-010-02: No pyproject.toml — all non-REPO_ROOT vars UNKNOWN."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _resolve_placeholder(repo_root=tmp_path)

        assert result["PROJECT_NAME"] == "UNKNOWN"
        assert result["REPO_ROOT"] == str(tmp_path.resolve())
        assert result["TARGET_BACKEND_FRAMEWORK"] == "UNKNOWN"
        assert result["TARGET_PACKAGE_MANAGER"] == "UNKNOWN"
        assert result["TARGET_TEST_RUNNER"] == "UNKNOWN"
        assert result["TARGET_COVERAGE_MINIMUM"] == "80"

        unresolvable = [
            "PROJECT_NAME",
            "TARGET_BACKEND_FRAMEWORK",
            "TARGET_PACKAGE_MANAGER",
            "TARGET_TEST_RUNNER",
        ]
        warning_texts = [str(x.message) for x in w]
        for var in unresolvable:
            assert any(var in msg for msg in warning_texts), (
                f"Missing warning for {var}"
            )

    def test_resolve_placeholder_partial(self, tmp_path: Path):
        """Partial pyproject.toml with only [project] name — best-effort resolution."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "partial-project"
""")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _resolve_placeholder(repo_root=tmp_path)

        assert result["PROJECT_NAME"] == "partial-project"
        assert result["REPO_ROOT"] == str(tmp_path.resolve())
        assert result["TARGET_BACKEND_FRAMEWORK"] == "UNKNOWN"
        assert result["TARGET_PACKAGE_MANAGER"] == "UNKNOWN"
        assert result["TARGET_TEST_RUNNER"] == "UNKNOWN"
        assert result["TARGET_COVERAGE_MINIMUM"] == "80"

        warning_texts = [str(x.message) for x in w]
        for var in [
            "TARGET_BACKEND_FRAMEWORK",
            "TARGET_PACKAGE_MANAGER",
            "TARGET_TEST_RUNNER",
        ]:
            assert any(var in msg for msg in warning_texts), (
                f"Missing warning for {var}"
            )


class TestInitCommand:
    def test_init_creates_dotfile_structure(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            assert (workdir / ".deviate" / "config.toml").exists()
            assert (workdir / ".deviate" / "session.json").exists()

    def test_init_creates_constitution(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--generate-constitution"])
            assert result.exit_code == 0, result.output
            constitution_path = workdir / "specs" / "constitution.md"
            assert constitution_path.exists()
            content = constitution_path.read_text()
            assert "${PROJECT_NAME}" not in content
            assert "${REPO_ROOT}" not in content

    def test_init_appends_governance_to_nonexistent_file(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            content = claude_path.read_text()
            assert "## DeviaTDD Orchestration Rules" in content

    def test_init_overwrites_governance_block_when_exists(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# My Project\n\n"
                "## DeviaTDD Orchestration Rules\n"
                "Old content\n\n"
                "## Other Section\n"
                "Preserved content\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old content" not in content
            assert "Preserved content" in content
            assert "## DeviaTDD Orchestration Rules" in content
            assert "## Other Section" in content

    def test_init_skip_existing_dotfiles(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dotfile_dir = workdir / ".deviate"
            dotfile_dir.mkdir()
            config_path = dotfile_dir / "config.toml"
            original_content = 'profile = "custom"\n'
            config_path.write_text(original_content)

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            assert config_path.read_text() == original_content
            assert "skip" in result.output.lower() or "already" in result.output.lower()

    def test_init_recover_partial_scaffold(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dotfile_dir = workdir / ".deviate"
            dotfile_dir.mkdir()
            config_path = dotfile_dir / "config.toml"
            config_path.write_text('profile = "default"\n')
            session_path = dotfile_dir / "session.json"

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            assert session_path.exists()
