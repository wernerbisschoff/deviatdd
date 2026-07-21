from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


def scaffold_artifacts(workspace: Path, *names: str) -> None:
    spec_dir = workspace / "specs" / "001-deviate-cli-python"
    for name in names:
        (spec_dir / name).write_text(f"# {name}\n")
    # `deviate research pre` now reads `specs/explore/<slug>.md` and moves
    # it into the epic dir, so tests that simulate a full macro cycle
    # must place `explore.md` at the staging location too (the previous
    # legacy format was `specs/<slug>/explore.md` inside the epic dir).
    if "explore.md" in names:
        staging = workspace / "specs" / "explore" / "001-deviate-cli-python.md"
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_text("# explore.md\n")


class TestMacroFullCycle:
    def test_full_idle_to_shard_cycle(self, mock_workspace: Path) -> None:
        scaffold_artifacts(
            mock_workspace, "explore.md", "design.md", "data-model.md", "prd.md"
        )
        (mock_workspace / "specs" / "constitution.md").write_text("# Constitution\n")

        result_explore = runner.invoke(
            cli,
            ["explore", "pre", "Test problem", "--slug", "001-deviate-cli-python"],
        )
        assert result_explore.exit_code == 0, result_explore.output

        result_research = runner.invoke(
            cli, ["research", "pre", "--slug", "001-deviate-cli-python"]
        )
        assert result_research.exit_code == 0, result_research.output

        result_prd = runner.invoke(cli, ["prd", "pre"])
        assert result_prd.exit_code == 0, result_prd.output

        manifest = mock_workspace / "specs" / "001-deviate-cli-python" / "manifest.json"
        issues = [
            {
                "issue_id": "ISS-001-001",
                "type": "feature",
                "title": "Issue 1",
                "source_file": "specs/001-deviate-cli-python/issues/issue-1.md",
            }
        ]
        manifest.write_text(json.dumps({"issues": issues}), encoding="utf-8")

        result_shard_pre = runner.invoke(cli, ["shard", "pre"])
        assert result_shard_pre.exit_code == 0, result_shard_pre.output

        result_shard_post = runner.invoke(cli, ["shard", "post", str(manifest)])
        assert result_shard_post.exit_code == 0, result_shard_post.output

        loaded = SessionState.load(mock_workspace / ".deviate" / "session.json")
        assert loaded.current_phase == "IDLE", (
            f"expected IDLE, got {loaded.current_phase}"
        )

        ledger_path = mock_workspace / "specs" / "issues.jsonl"
        assert ledger_path.exists(), "issues.jsonl should exist"
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        backlog_lines = [
            ln for ln in lines if json.loads(ln).get("status") == "BACKLOG"
        ]
        assert len(backlog_lines) >= 1, (
            f"expected at least 1 BACKLOG record, got {len(backlog_lines)}"
        )

    def test_cycle_resets_for_second_run(self, mock_workspace: Path) -> None:
        scaffold_artifacts(
            mock_workspace, "explore.md", "design.md", "data-model.md", "prd.md"
        )
        (mock_workspace / "specs" / "constitution.md").write_text("# Constitution\n")

        runner.invoke(
            cli,
            ["explore", "pre", "Test", "--slug", "001-deviate-cli-python"],
        )
        runner.invoke(cli, ["research", "pre", "--slug", "001-deviate-cli-python"])
        runner.invoke(cli, ["prd", "pre"])
        runner.invoke(cli, ["shard", "pre"])

        manifest = mock_workspace / "specs" / "001-deviate-cli-python" / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "issues": [
                        {
                            "issue_id": "ISS-001-001",
                            "type": "feature",
                            "title": "Test",
                            "source_file": "specs/001-deviate-cli-python/issues/001-test.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        runner.invoke(cli, ["shard", "post", str(manifest)])

        loaded = SessionState.load(mock_workspace / ".deviate" / "session.json")
        assert loaded.current_phase == "IDLE", (
            f"expected IDLE after first cycle, got {loaded.current_phase}"
        )

        result = runner.invoke(
            cli,
            ["explore", "pre", "Second run", "--slug", "001-deviate-cli-python"],
        )
        assert result.exit_code == 0, result.output

        loaded = SessionState.load(mock_workspace / ".deviate" / "session.json")
        assert loaded.current_phase == "EXPLORE", (
            f"expected EXPLORE, got {loaded.current_phase}"
        )

    def test_cycle_breaks_on_missing_artifact(self, mock_workspace: Path) -> None:
        scaffold_artifacts(mock_workspace, "explore.md")
        (mock_workspace / "specs" / "constitution.md").write_text("# Constitution\n")

        result_explore = runner.invoke(
            cli,
            ["explore", "pre", "Test", "--slug", "001-deviate-cli-python"],
        )
        assert result_explore.exit_code == 0, result_explore.output

        result_research = runner.invoke(
            cli, ["research", "pre", "--slug", "001-deviate-cli-python"]
        )
        assert result_research.exit_code == 0, result_research.output

        loaded = SessionState.load(mock_workspace / ".deviate" / "session.json")
        assert loaded.current_phase == "RESEARCH"

        result_prd = runner.invoke(cli, ["prd", "pre"])
        assert result_prd.exit_code != 0
        assert "PRD_HALTED" in result_prd.output

        loaded = SessionState.load(mock_workspace / ".deviate" / "session.json")
        assert loaded.current_phase == "RESEARCH", (
            f"expected RESEARCH (not advanced), got {loaded.current_phase}"
        )
