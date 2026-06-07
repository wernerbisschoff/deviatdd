import os
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


@contextmanager
def chdir(path: Path):
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


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
