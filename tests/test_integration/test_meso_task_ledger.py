from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord, TaskRecord

runner = CliRunner()

MESO_ISSUE_ID = "550e8400-e29b-41d4-a716-446655440100"
MESO_ISSUE_SLUG = "test-meso-issue"


class TestMesoTaskLedger:
    def test_full_specify_tasks_cycle(self, meso_workspace: Path) -> None:
        result = runner.invoke(cli, ["specify", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        spec_dir = Path("specs") / MESO_ISSUE_SLUG
        assert spec_dir.is_dir(), f"spec dir {spec_dir} not created"
        spec_md = spec_dir / "spec.md"
        assert spec_md.is_file(), f"spec.md not created at {spec_md}"

        result = runner.invoke(cli, ["tasks", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        tasks_jsonl = spec_dir / "tasks.jsonl"
        assert tasks_jsonl.is_file(), f"tasks.jsonl not created at {tasks_jsonl}"

        lines = tasks_jsonl.read_text().strip().splitlines()
        assert len(lines) >= 1, "Expected at least one task record"

        for line in lines:
            data = json.loads(line)
            record = TaskRecord.model_validate(data)
            assert record.issue_id == MESO_ISSUE_ID

        loaded = SessionState.load(Path(".deviate") / "session.json")
        assert loaded.current_phase == "IDLE", (
            f"Expected IDLE, got {loaded.current_phase}"
        )

    def test_tasks_idempotency_full_cycle(self, meso_workspace: Path) -> None:
        result = runner.invoke(cli, ["specify", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        result = runner.invoke(cli, ["tasks", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        spec_dir = Path("specs") / MESO_ISSUE_SLUG
        tasks_jsonl = spec_dir / "tasks.jsonl"
        pre_lines = len(tasks_jsonl.read_text().strip().splitlines())
        pre_content = tasks_jsonl.read_text()

        result = runner.invoke(cli, ["tasks", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output
        assert "already provisioned" in result.output.lower()

        post_lines = len(tasks_jsonl.read_text().strip().splitlines())
        assert post_lines == pre_lines, (
            f"Line count changed: {pre_lines} -> {post_lines}"
        )

        post_content = tasks_jsonl.read_text()
        assert post_content == pre_content, "File content changed on re-run"

    def test_invalid_issue_id_rejected(self, meso_workspace: Path) -> None:
        result = runner.invoke(cli, ["specify", "NONEXISTENT"])
        assert result.exit_code != 0
        assert "INVALID_ISSUE_ID" in result.output

    def test_empty_issues_ledger(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("")

            result = runner.invoke(
                cli, ["specify", "550e8400-e29b-41d4-a716-446655440200"]
            )
            assert result.exit_code != 0
            assert "INVALID_ISSUE_ID" in result.output

    def test_malformed_jsonl_in_ledger(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            valid = IssueRecord(
                id="550e8400-e29b-41d4-a716-446655440300",
                title="Valid Issue in Malformed Ledger",
                status="SHARDED",
                epic_slug="test-epic",
                issue_slug="valid-issue-malformed",
            )
            ledger = Path("specs") / "issues.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                "not valid json\n"
                "also not valid\n"
                + valid.model_dump_json()
                + "\n"
                + "trash\n"
            )

            result = runner.invoke(
                cli, ["specify", "550e8400-e29b-41d4-a716-446655440300"]
            )
            assert result.exit_code == 0, result.output

            spec_dir = Path("specs") / "valid-issue-malformed"
            assert spec_dir.is_dir(), (
                f"Expected {spec_dir} despite malformed lines"
            )

    def test_missing_dotdir_graceful(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["specify", "any-id"])
            assert result.exit_code != 0
            assert "HALTED" in result.output
