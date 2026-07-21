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

    def test_research_pre_transitions_from_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            explore_dir = Path("specs") / "explore"
            explore_dir.mkdir(parents=True)
            (explore_dir / "deviate-cli-python.md").write_text("# Explore results\n")
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["research", "pre", "--slug", "deviate-cli-python"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "RESEARCH"
            # Verify numbered epic bucket was created
            epic_dirs = [
                d for d in Path("specs").iterdir() if d.is_dir() and d.name != "explore"
            ]
            assert len(epic_dirs) >= 1

    def test_research_pre_rejects_if_not_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            result = runner.invoke(
                cli, ["research", "pre", "--slug", "001-deviate-cli-python"]
            )
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output

    def test_research_pre_missing_explore_artifact(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["research", "pre", "--slug", "missing-slug"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output
            assert "explore.md" in result.output


class TestResearchExploreMove:
    """Verify `deviate research pre` moves explore.md into the numbered
    epic directory and updates the contract field accordingly.
    """

    def test_research_pre_moves_explore_into_epic_dir(self, tmp_path: Path) -> None:
        import json

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            explore_dir = Path("specs") / "explore"
            explore_dir.mkdir(parents=True)
            content = (
                "# Explore: my-feature\n\n## Problem Definition\n\n"
                "Factual context.\n## File Registry\n| Path | Type |\n"
            )
            source = explore_dir / "my-feature.md"
            source.write_text(content)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(cli, ["research", "pre", "--slug", "my-feature"])
            assert result.exit_code == 0, result.output

            # The source must no longer exist (clean cutover, no orphan).
            assert not source.exists(), (
                f"source explore.md still present at {source} after research pre"
            )

            # The numbered epic bucket was created.
            epic_dir = Path("specs") / "001-my-feature"
            assert epic_dir.is_dir(), f"expected epic dir at {epic_dir}"

            # explore.md now lives inside the epic dir, with byte-identical
            # content (no corruption from the move).
            moved = epic_dir / "explore.md"
            assert moved.exists(), f"expected explore.md at {moved}"
            assert moved.read_text(encoding="utf-8") == content

            # The contract payload points explore_md_path at the new location.
            start = result.output.index("{")
            end = result.output.rindex("}") + 1
            contract = json.loads(result.output[start:end])
            assert contract["phase"] == "RESEARCH"
            assert contract["explore_md_path"] == str(moved.resolve())
            assert contract["explore_path"] == str(moved)
            assert contract["feature_dir"] == str(epic_dir)

    def test_research_pre_halts_when_source_explore_missing(
        self, tmp_path: Path
    ) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            (Path("specs") / "explore").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            # No specs/explore/ghost.md exists; the command should halt
            # before allocating a numbered bucket.
            result = runner.invoke(cli, ["research", "pre", "--slug", "ghost"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output
            assert "explore.md" in result.output
            assert not (Path("specs") / "001-ghost").exists()
