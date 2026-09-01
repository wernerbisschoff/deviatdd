from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestExploreCommand:
    def test_explore_help(self):
        result = runner.invoke(cli, ["explore", "--help"])
        assert result.exit_code == 0, result.output
        assert "explore" in result.output.lower()

    def test_explore_pre_transitions_from_idle(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["explore", "pre", "test problem", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"
            assert (Path("specs") / "explore").is_dir()

    def test_explore_pre_accepts_greenfield_and_transitions_from_any_phase(
        self, tmp_path: Path
    ) -> None:
        """Greenfield explore (no ``specs/constitution.md``) proceeds.

        explore pre no longer halts on a missing constitution — it derives
        ``is_greenfield=true`` from constitution absence. The orchestrator
        does NOT enforce phase transitions via ``_load_and_transition``;
        a non-IDLE starting phase is silently overwritten (see
        ``SessionState.transition_to``). The ``is_greenfield`` flag is the
        greenfield-detection signal downstream phases rely on.
        """
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")
            # No constitution file — greenfield.

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output
            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"

    def test_explore_pre_missing_session_file_defaults_idle(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            assert not (dot_dir / "session.json").exists()
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"

    def test_explore_pre_missing_dotdeviate_dir_error(self, tmp_path: Path):
        with chdir(tmp_path):
            assert not Path(".deviate").exists()

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code != 0
            assert "EXPLORE_HALTED" in result.output
