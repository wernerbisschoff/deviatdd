from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


def _create_mock_workspace(tmp_path: Path) -> None:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    spec_dir = tmp_path / "specs" / "001-deviate-cli-python"
    spec_dir.mkdir(parents=True)
    (spec_dir / "explore.md").write_text("# Explore\n")
    (spec_dir / "research.md").write_text("# Research\n")
    (spec_dir / "prd.md").write_text("# PRD\n")


class TestMacroFullCycle:
    def test_full_idle_to_shard_cycle(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            _create_mock_workspace(tmp_path)

            result_explore = runner.invoke(cli, ["explore", "001-deviate-cli-python"])
            assert result_explore.exit_code == 0, result_explore.output

            result_research = runner.invoke(
                cli, ["research", "001-deviate-cli-python"]
            )
            assert result_research.exit_code == 0, result_research.output

            result_prd = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result_prd.exit_code == 0, result_prd.output

            result_shard = runner.invoke(cli, ["shard", "001-deviate-cli-python"])
            assert result_shard.exit_code == 0, result_shard.output

            loaded = SessionState.load(Path(".deviate") / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"expected IDLE, got {loaded.current_phase}"
            )

            ledger_path = Path("specs") / "issues.jsonl"
            assert ledger_path.exists(), "issues.jsonl should exist"
            lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1, f"expected 1 record, got {len(lines)}"
            record = json.loads(lines[0])
            assert record["status"] == "SHARDED"
            assert record["issue_slug"] == "001-deviate-cli-python"

    def test_cycle_resets_for_second_run(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            _create_mock_workspace(tmp_path)

            runner.invoke(cli, ["explore", "001-deviate-cli-python"])
            runner.invoke(cli, ["research", "001-deviate-cli-python"])
            runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            runner.invoke(cli, ["shard", "001-deviate-cli-python"])

            loaded = SessionState.load(Path(".deviate") / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"expected IDLE after first cycle, got {loaded.current_phase}"
            )

            result = runner.invoke(cli, ["explore", "001-deviate-cli-python"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(Path(".deviate") / "session.json")
            assert loaded.current_phase == "EXPLORE", (
                f"expected EXPLORE, got {loaded.current_phase}"
            )

    def test_cycle_breaks_on_missing_artifact(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            spec_dir = Path("specs") / "001-deviate-cli-python"
            spec_dir.mkdir(parents=True)
            (spec_dir / "explore.md").write_text("# Explore\n")

            result_explore = runner.invoke(cli, ["explore", "001-deviate-cli-python"])
            assert result_explore.exit_code == 0, result_explore.output

            result_research = runner.invoke(
                cli, ["research", "001-deviate-cli-python"]
            )
            assert result_research.exit_code == 0, result_research.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "RESEARCH"

            result_prd = runner.invoke(cli, ["prd", "001-deviate-cli-python"])
            assert result_prd.exit_code != 0
            assert "PRD_HALTED" in result_prd.output
            assert "research.md" in result_prd.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "RESEARCH", (
                f"expected RESEARCH (not advanced), got {loaded.current_phase}"
            )
