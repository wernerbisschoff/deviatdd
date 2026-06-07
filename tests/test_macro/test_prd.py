from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestPrdCommand:
    def test_prd_help(self):
        result = runner.invoke(cli, ["prd", "--help"])
        assert result.exit_code == 0, result.output
        assert "prd" in result.output.lower()

    def test_prd_transitions_from_research(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")
            (spec_dir / "research.md").write_text("# Research\n")

            result = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "PRD"

    def test_prd_rejects_if_not_research(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output

    def test_prd_missing_explore_and_research(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output
            assert "explore.md" in result.output
            assert "research.md" in result.output

    def test_prd_missing_research_only(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")

            result = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output
            assert "research.md" in result.output
