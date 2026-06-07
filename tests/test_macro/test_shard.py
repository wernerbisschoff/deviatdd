from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestShardCommand:
    def test_shard_help(self):
        result = runner.invoke(cli, ["shard", "--help"])
        assert result.exit_code == 0, result.output
        assert "shard" in result.output.lower()

    def test_shard_transitions_from_prd(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "prd.md").write_text("# PRD\n")

            result = runner.invoke(cli, ["shard", "001-deviate-cli-python"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "IDLE"

    def test_shard_rejects_if_not_prd(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["shard", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "SHARD_HALTED" in result.output

    def test_shard_missing_prd_artifact(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["shard", "001-deviate-cli-python"])
            assert result.exit_code != 0
            assert "SHARD_HALTED" in result.output
            assert "prd.md" in result.output
