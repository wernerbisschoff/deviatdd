import warnings
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import _resolve_placeholder, cli
from deviate.cli.__init__ import resolve_graphite_config

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

    def test_init_detects_context(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/context"
                result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_context = true" in content

    def test_init_missing_context(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_context = false" in content

    def test_init_context_governance_block(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/context"
                result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output

            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            claude_content = claude_path.read_text()
            assert "## Offline Context Documentation System" in claude_content
            assert "context query" in claude_content
            assert "context list" in claude_content
            assert "context add" in claude_content

            agents_path = workdir / "AGENTS.md"
            assert agents_path.exists()
            agents_content = agents_path.read_text()
            assert "## Offline Context Documentation System" in agents_content

    def test_resolve_graphite_config_true(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text("graphite = true\n", encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is True

    def test_resolve_graphite_config_false(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text("graphite = false\n", encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is False

    def test_resolve_graphite_config_key_absent(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text('profile = "default"\n', encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is False

    def test_resolve_graphite_config_no_config(self, tmp_path: Path) -> None:
        assert resolve_graphite_config(tmp_path) is False


class TestInitGraphiteFlag:
    """RED phase tests for TSK-007-02: --graphite flag on deviate init."""

    def test_init_with_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-01: --graphite flag writes graphite = true in config.toml.

        FAILS because the --graphite flag doesn't exist on the init command yet.
        """
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--graphite"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            assert config_path.exists()
            content = config_path.read_text()
            assert "graphite = true" in content

    def test_init_without_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-02: Default init either omits graphite or sets false."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            assert config_path.exists()
            content = config_path.read_text()
            if "graphite" in content:
                assert "graphite = false" in content

    def test_init_graphite_governance_section(self, tmp_path: Path):
        """AC-ADHOC-007-03: Graphite section appears in governance seeds when enabled.

        FAILS because the --graphite flag doesn't exist on the init command yet,
        and _apply_governance doesn't accept a graphite parameter.
        """
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--graphite"])
            assert result.exit_code == 0, result.output
            for fname in ["CLAUDE.md", "AGENTS.md"]:
                fpath = workdir / fname
                assert fpath.exists()
                content = fpath.read_text()
                assert "## Graphite Stacked Changes Workflow" in content

    def test_init_graphite_governance_absent_when_disabled(self, tmp_path: Path):
        """AC-ADHOC-007-04: No Graphite section when graphite disabled."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            for fname in ["CLAUDE.md", "AGENTS.md"]:
                fpath = workdir / fname
                assert fpath.exists()
                content = fpath.read_text()
                assert "## Graphite Stacked Changes Workflow" not in content

    def test_scaffold_dotfiles_with_graphite_true(self, tmp_path: Path):
        """_scaffold_dotfiles(graphite=True) writes graphite = true.

        FAILS because _scaffold_dotfiles doesn't accept a graphite kwarg yet.
        """
        from deviate.cli import _scaffold_dotfiles

        _scaffold_dotfiles(tmp_path, "local", graphite=True)
        config_path = tmp_path / ".deviate" / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        assert "graphite = true" in content

    def test_scaffold_dotfiles_with_graphite_false(self, tmp_path: Path):
        """_scaffold_dotfiles(graphite=False) omits graphite or sets false."""
        from deviate.cli import _scaffold_dotfiles

        _scaffold_dotfiles(tmp_path, "local", graphite=False)
        config_path = tmp_path / ".deviate" / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        if "graphite" in content:
            assert "graphite = false" in content

    def test_apply_governance_with_graphite(self, tmp_path: Path):
        """_apply_governance(graphite=True) emits Graphite section.

        FAILS because _apply_governance doesn't accept a graphite kwarg yet.
        """
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" in content
            assert "gt create -am" in content
            assert "gt submit --stack" in content

    def test_apply_governance_without_graphite(self, tmp_path: Path):
        """_apply_governance(graphite=False) omits Graphite section."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=False)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" not in content

    def test_init_graphite_governance_section_present(self, tmp_path: Path):
        """AC-ADHOC-007-03: Graphite section present via _apply_governance."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" in content

    def test_init_graphite_governance_section_absent(self, tmp_path: Path):
        """AC-ADHOC-007-04: Graphite section absent via _apply_governance."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=False)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" not in content

    def test_init_graphite_governance_idempotent(self, tmp_path: Path):
        """Re-running _apply_governance updates existing Graphite section."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        claude_path = tmp_path / "CLAUDE.md"
        original = claude_path.read_text()
        assert "## Graphite Stacked Changes Workflow" in original

        outdated_section = "\n\n## Graphite Stacked Changes Workflow\n\nOutdated content\n\n## Unrelated\nKept\n"
        claude_path.write_text(outdated_section, encoding="utf-8")

        _apply_governance(tmp_path, graphite=True)
        updated = claude_path.read_text()
        assert "Outdated content" not in updated
        assert "gt create -am" in updated
        assert "gt submit --stack" in updated
        assert "## Unrelated" in updated
        assert "Kept" in updated
