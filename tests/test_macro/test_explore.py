import json
import subprocess
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

    def test_explore_post_renders_flow_coverage_table(self, tmp_path: Path):
        with chdir(tmp_path):
            subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test"],
                cwd=tmp_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmp_path,
                capture_output=True,
            )
            (tmp_path / "README.md").write_text("# test")
            subprocess.run(
                ["git", "add", "README.md"], cwd=tmp_path, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True
            )

            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            explore_dir = Path("specs/explore")
            explore_dir.mkdir(parents=True)
            (explore_dir / "test-slug.md").write_text(
                "# Explore: test-slug\n"
                "\n"
                "## Problem Definition\n"
                "Test problem\n"
                "\n"
                "## Discovery Audit Results\n"
                "None\n"
                "\n"
                "## Constitution Quotes\n"
                "None\n"
                "\n"
                "## Architectural Baselines\n"
                "None\n"
                "\n"
                "## Ecosystem Research\n"
                "None\n"
                "\n"
                "## File Registry\n"
                "None\n"
                "\n"
                "## Status Summary\n"
                "None\n"
            )

            flows_dir = Path("specs/_product/flows")
            flows_dir.mkdir(parents=True)
            (flows_dir / "index.md").write_text(
                "# DeviaTDD Product Flow Index\n"
                "\n"
                "| Flow ID | Name | Actor | Domain | Status | Source |\n"
                "|---------|------|-------|--------|--------|--------|\n"
                "| FLOW-01 | Flows | Developer | Software Engineering | Active"
                " | specs/_product/flows/flows-product.md |\n"
                "| FLOW-02 | Architecture | Developer | Software Engineering | Active"
                " | specs/_product/flows/flows-product.md |\n"
                "| FLOW-03 | Release | Developer | Software Engineering | Active"
                " | specs/_product/flows/flows-product.md |\n"
                "| FLOW-04 | Live-Stream Agent Progress via RPC | Developer"
                " | Agent Integration | Active"
                " | specs/_product/flows/flows-streaming.md |\n"
            )

            from deviate.state.ledger import seed_flow_ledger

            flows_ledger = Path("specs/_product") / "flows.jsonl"
            seed_flow_ledger(
                Path("specs/_product") / "flows" / "index.md",
                flows_ledger,
            )

            result = runner.invoke(cli, ["explore", "post", "--slug", "test-slug"])
            assert result.exit_code == 0, result.output
            assert "FLOW-04" in result.output
            assert "DOCUMENTED_BUT_NOT_IMPLEMENTED" in result.output

            content = flows_ledger.read_text().strip()
            lines = [ln for ln in content.split("\n") if ln.strip()]
            records = [json.loads(ln) for ln in lines]
            flow_records = [
                r for r in records if "flow_id" in r and "event_type" not in r
            ]
            assert len(flow_records) >= 4

    def test_explore_post_never_writes_referenced_by_events(self, tmp_path: Path):
        with chdir(tmp_path):
            subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test"],
                cwd=tmp_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmp_path,
                capture_output=True,
            )
            (tmp_path / "README.md").write_text("# test")
            subprocess.run(
                ["git", "add", "README.md"], cwd=tmp_path, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True
            )

            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            explore_dir = Path("specs/explore")
            explore_dir.mkdir(parents=True)
            explore_text = (
                "# Explore: test-slug\n\n"
                + "## Problem Definition\nTest problem\n\n"
                + "## Discovery Audit Results\nNone\n\n"
                + "## Constitution Quotes\nNone\n\n"
                + "## Architectural Baselines\nNone\n\n"
                + "## Ecosystem Research\nNone\n\n"
                + "## File Registry\nNone\n\n"
                + "## Status Summary\nNone\n"
            )
            (explore_dir / "test-slug.md").write_text(explore_text)

            flows_dir = Path("specs/_product/flows")
            flows_dir.mkdir(parents=True)
            (flows_dir / "index.md").write_text(
                "# DeviaTDD Product Flow Index\n\n"
                + "| Flow ID | Name | Actor | Domain | Status | Source |\n"
                + "|---------|------|-------|--------|--------|--------|\n"
                + "| FLOW-01 | Flows | Developer | Software Engineering | Active | specs/_product/flows/flows-product.md |\n"
                + "| FLOW-04 | Live-Stream Agent Progress via RPC | Developer | Agent Integration | Active | specs/_product/flows/flows-streaming.md |\n"
            )

            (Path("specs") / "issues.jsonl").write_text(
                json.dumps(
                    {
                        "issue_id": "ISS-TEST-001",
                        "flow_refs": ["FLOW-01", "FLOW-04", "FLOW-99"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                )
                + "\n",
            )

            result = runner.invoke(cli, ["explore", "post", "--slug", "test-slug"])
            assert result.exit_code == 0, result.output

            flows_jsonl = Path("specs/_product") / "flows.jsonl"
            if flows_jsonl.exists():
                content = flows_jsonl.read_text().strip()
                lines = [ln for ln in content.split("\n") if ln.strip()]
                records = [json.loads(ln) for ln in lines]
                referenced_by = [
                    r
                    for r in records
                    if r.get("event_type") == "FLOW_REFERENCED_BY_ISSUE"
                ]
                assert referenced_by == [], (
                    "explore post must never write a FLOW_REFERENCED_BY_ISSUE ",
                    "event into flows.jsonl",
                )

    def test_explore_post_does_not_seed_flow_identity_or_documented_events(
        self, tmp_git_repo: Path
    ) -> None:
        with chdir(tmp_git_repo):
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            explore_dir = Path("specs/explore")
            explore_dir.mkdir(parents=True)
            (explore_dir / "test-slug.md").write_text(
                "# Explore: test-slug\n\n"
                "## Problem Definition\nTest\n\n"
                "## Discovery Audit Results\nNone\n\n"
                "## Constitution Quotes\nNone\n\n"
                "## Architectural Baselines\nNone\n\n"
                "## Ecosystem Research\nNone\n\n"
                "## File Registry\nNone\n\n"
                "## Status Summary\nNone\n"
            )

            flows_dir = Path("specs/_product/flows")
            flows_dir.mkdir(parents=True)
            (flows_dir / "index.md").write_text(
                "| Flow ID | Name | Actor | Domain | Status | Source |\n"
                "|---------|------|-------|--------|--------|--------|\n"
                "| FLOW-04 | Live-Stream Agent Progress via RPC | Developer"
                " | Agent Integration | Active"
                " | specs/_product/flows/flows-streaming.md |\n"
            )

            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["explore", "post", "--slug", "test-slug"])
            assert result.exit_code == 0, result.output
            flows_jsonl = Path("specs/_product") / "flows.jsonl"
            assert not flows_jsonl.exists(), (
                "explore post must not create flows.jsonl; "
                "creation belongs to `deviate flows sync`"
            )
