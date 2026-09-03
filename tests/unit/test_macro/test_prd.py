from contextlib import chdir
import json
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

    def test_prd_pre_transitions_from_research(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")
            (spec_dir / "design.md").write_text("# Design\n")
            (spec_dir / "data-model.md").write_text("# Data Model\n")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "PRD"

    def test_prd_pre_rejects_if_not_research(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output

    def test_prd_pre_missing_all_artifacts(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output

    def test_prd_pre_missing_design_and_data_model(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code != 0
            assert "PRD_HALTED" in result.output

    def test_prd_pre_json_emits_contract(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")
            (spec_dir / "design.md").write_text("# Design\n")
            (spec_dir / "data-model.md").write_text("# Data Model\n")

            result = runner.invoke(cli, ["prd", "pre", "--json"])
            assert result.exit_code == 0, result.output

            contract = json.loads(result.output.strip())
            assert contract["phase"] == "PRD"
            assert contract["epic_slug"] == "001-deviate-cli-python"
            assert contract["design_path"].endswith("design.md")
            assert contract["data_model_path"].endswith("data-model.md")
            assert contract["explore_md_path"].endswith("explore.md")
            assert contract["plan_target"].endswith("manifest_prd.json")


class TestPrdPreExploreContract:
    """Verify `deviate prd pre` halts on missing explore.md and exposes
    the moved explore.md path in the contract payload.
    """

    def test_prd_pre_halts_when_explore_md_missing(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            # design.md and data-model.md present, but explore.md is
            # missing — pre must halt with a clear message rather than
            # silently letting the contract through.
            (spec_dir / "design.md").write_text("# Design\n")
            (spec_dir / "data-model.md").write_text("# Data Model\n")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code != 0, result.output
            assert "PRD_HALTED" in result.output
            assert "explore.md" in result.output

    def test_prd_pre_contract_exposes_explore_md_path(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            explore = spec_dir / "explore.md"
            explore.write_text("# Explore\n")
            (spec_dir / "design.md").write_text("# Design\n")
            (spec_dir / "data-model.md").write_text("# Data Model\n")

            result = runner.invoke(cli, ["prd", "pre", "--json"])
            assert result.exit_code == 0, result.output

            start = result.output.index("{")
            end = result.output.rindex("}") + 1
            contract = json.loads(result.output[start:end])
            assert contract["phase"] == "PRD"
            assert contract["explore_md_path"] == str(explore)
