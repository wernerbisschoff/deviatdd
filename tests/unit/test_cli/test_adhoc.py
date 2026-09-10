from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.complexity import ClassificationResult
from deviate.core.explore_routing import ATTACH_EXISTING_EPIC
from deviate.state.config import SessionState

from tests.explore_artifact import render_explore_md

runner = CliRunner()


class TestAdhocPre:
    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_low_complexity(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Fix typo"])

        assert result.exit_code == 0
        assert "DIRECT" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_medium_complexity(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Add form validation"])

        assert result.exit_code == 0
        assert "DIRECT" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_high_complexity_rejected(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="HIGH", execution_mode="TDD"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["adhoc", "pre", "Build auth system with OAuth, JWT, RBAC"]
            )

        assert result.exit_code != 0
        assert "COMPLEXITY_GATE_REJECTION" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_high_complexity_skip_gates(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="HIGH", execution_mode="TDD"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "adhoc",
                    "pre",
                    "--skip-gates",
                    "Build auth system with OAuth, JWT, RBAC",
                ],
            )

        assert result.exit_code == 0


class TestAdhocPreAttachRouting:
    def _seed_attach(
        self,
        tmp_path: Path,
        *,
        hitl_override: str = "none",
        session_only: bool = False,
    ) -> None:
        specs = tmp_path / "specs"
        specs.mkdir(parents=True)
        if not session_only:
            (specs / "explore").mkdir(parents=True)
            (specs / "explore" / "follow-on.md").write_text(
                render_explore_md(
                    next_action="attach_existing_epic `006-existing-epic`",
                    attach_epic="006-existing-epic",
                    hitl_override=hitl_override,
                ),
                encoding="utf-8",
            )
        epic = specs / "006-existing-epic"
        epic.mkdir(parents=True)
        (epic / "prd.md").write_text("# epic prd\n")
        (epic / "issues").mkdir(exist_ok=True)
        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        SessionState(
            current_phase="EXPLORE",
            explore_next_action=ATTACH_EXISTING_EPIC if session_only else "",
            attach_epic_slug="006-existing-epic" if session_only else "",
        ).save(dot / "session.json")

    def test_pre_emits_attach_contract_and_skips_shared_prd(
        self, tmp_path: Path
    ) -> None:
        self._seed_attach(tmp_path)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Follow-on config work"])

        assert result.exit_code == 0, result.output
        start = result.stdout.index("{")
        end = result.stdout.rindex("}") + 1
        contract = json.loads(result.stdout[start:end])
        assert contract["attach_existing_epic"] is True
        assert contract["allocate_bucket"] is False
        assert contract["shared_prd"] is False
        assert contract["epic_slug"] == "006-existing-epic"
        assert contract["issue_dir"].endswith("specs/006-existing-epic/issues")
        assert contract["prd_path"].endswith("specs/006-existing-epic/prd.md")

    def test_pre_reads_session_when_explore_md_absent(self, tmp_path: Path) -> None:
        self._seed_attach(tmp_path, session_only=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Follow-on from session"])

        assert result.exit_code == 0, result.output
        assert "006-existing-epic" in result.stdout
        assert '"attach_existing_epic": true' in result.stdout

    def test_pre_high_complexity_still_attaches(self, tmp_path: Path) -> None:
        self._seed_attach(tmp_path)
        with (
            chdir(tmp_path),
            patch("deviate.cli.adhoc.ComplexityGate.classify") as mock_classify,
        ):
            mock_classify.return_value = ClassificationResult(
                level="HIGH", execution_mode="TDD"
            )
            result = runner.invoke(
                cli, ["adhoc", "pre", "Build auth system with OAuth"]
            )

        assert result.exit_code == 0, result.output
        assert "COMPLEXITY_GATE_REJECTION" not in result.stdout
        assert "attach_existing_epic" in result.stdout

    def test_pre_halts_when_hitl_pending(self, tmp_path: Path) -> None:
        self._seed_attach(tmp_path, hitl_override="pending")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Follow-on config work"])

        assert result.exit_code != 0
        assert "HITL_PENDING_ROUTING" in result.stdout


class TestAdhocPost:
    def test_post_completes_record(self, tmp_path: Path) -> None:
        manifest_id = "adhoc-test-001"
        record = {
            "issue_id": manifest_id,
            "description": "Fix typo in README",
            "execution_mode": "DIRECT",
            "status": "PENDING",
        }
        adhoc_dir = tmp_path / "specs"
        adhoc_dir.mkdir(parents=True, exist_ok=True)
        adhoc_file = adhoc_dir / "adhoc.jsonl"
        adhoc_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "post", manifest_id])

        assert result.exit_code == 0
        assert "COMPLETED" in result.stdout

    def test_post_rejects_gherkin_leak_in_issue(self, tmp_path: Path) -> None:
        manifest_id = "adhoc-test-002"
        specs = tmp_path / "specs"
        issue = specs / "adhoc" / "issues" / "002-demo.md"
        issue.parent.mkdir(parents=True)
        issue.write_text(
            "## Acceptance Outline\n- **AO-002**: Demo succeeds.\n"
            "- **Given** configured\n- **When** run\n- **Then** success\n"
        )
        (specs / "adhoc.jsonl").write_text(
            json.dumps(
                {
                    "issue_id": manifest_id,
                    "description": "Demo",
                    "execution_mode": "DIRECT",
                    "status": "PENDING",
                    "source_file": "specs/adhoc/issues/002-demo.md",
                }
            )
            + "\n"
        )

        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "post", manifest_id])

        assert result.exit_code == 1, result.output
        assert "GHERKIN_LEAK_DETECTED" in result.output

    def test_post_missing_manifest(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "post", "nonexistent-id"])

        assert result.exit_code != 0
        assert "MANIFEST_NOT_FOUND" in result.stdout
