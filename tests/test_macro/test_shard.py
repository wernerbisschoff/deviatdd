from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestCodebaseStructureInjection:
    """SHARD pre injects codebase structure appendix into the contract."""

    @patch("deviate.cli.macro._emit_contract")
    def test_appendix_in_contract(self, mock_emit, tmp_git_repo: Path) -> None:
        """AC-ADHOC-008-05: Contract dict includes codebase_structure_appendix with file signatures."""
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")
            (spec_dir / "prd.md").write_text("# PRD\n")

            src_dir = Path("src") / "example_lib"
            src_dir.mkdir(parents=True)
            (src_dir / "greeter.py").write_text(
                "def greet(name: str) -> str:\n"
                '    return f"Hello, {name}!"\n'
                "\n"
                "class Greeter:\n"
                "    def hello(self) -> str:\n"
                '        return "hi"\n'
            )

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code == 0, result.output

            assert mock_emit.called
            _args, kwargs = mock_emit.call_args
            assert "codebase_structure_appendix" in kwargs
            appendix = kwargs["codebase_structure_appendix"]
            assert "## Codebase Structure" in appendix
            assert "greet" in appendix
            assert "Greeter" in appendix


class TestShardCommand:
    def test_shard_help(self):
        result = runner.invoke(cli, ["shard", "--help"])
        assert result.exit_code == 0, result.output
        assert "shard" in result.output.lower()

    def test_shard_pre_transitions_from_prd(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")
            (spec_dir / "prd.md").write_text("# PRD\n")

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "SHARD"

    def test_shard_pre_rejects_if_not_prd(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code != 0
            assert "SHARD_HALTED" in result.output

    def test_shard_pre_missing_prd_artifact(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code != 0
            assert "SHARD_HALTED" in result.output
