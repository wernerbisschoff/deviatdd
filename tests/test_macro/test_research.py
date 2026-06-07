from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestResearchCommand:
    def test_research_help(self):
        result = runner.invoke(cli, ["research", "--help"])
        assert result.exit_code == 0, result.output
        assert "research" in result.output.lower()

    def test_research_transitions_from_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore results\n")

            result = runner.invoke(cli, ["research", "001-deviate-cli-python"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "RESEARCH"

    def test_research_rejects_if_not_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["research", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output

    def test_research_missing_explore_artifact(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["research", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output
            assert "explore.md" in result.output
