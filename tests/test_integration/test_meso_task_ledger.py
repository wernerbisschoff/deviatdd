from __future__ import annotations

import json
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord, TaskRecord

from tests.conftest import _git_env

runner = CliRunner()

MESO_ISSUE_ID = "ISS-100"
MESO_BUCKET = "test-epic"


class TestMesoTaskLedger:
    def test_full_tasks_cycle(self, meso_workspace: Path) -> None:
        result = runner.invoke(cli, ["tasks", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        spec_dir = Path("specs") / MESO_BUCKET
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
        result = runner.invoke(cli, ["tasks", MESO_ISSUE_ID])
        assert result.exit_code == 0, result.output

        spec_dir = Path("specs") / MESO_BUCKET
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

    def test_specify_nonexistent_issue_fails(self, meso_workspace: Path) -> None:
        result = runner.invoke(cli, ["specify", "NONEXISTENT"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_NOT_FOUND" in result.output

    def test_empty_issues_ledger(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("")

            result = runner.invoke(cli, ["specify", "ISS-200"])
            assert result.exit_code == 1, result.output
            assert "ISSUE_NOT_FOUND" in result.output

    def test_malformed_jsonl_in_ledger(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            valid = IssueRecord(
                issue_id="ISS-300",
                type="feature",
                title="Valid Issue in Malformed Ledger",
                status="SHARDED",
                source_file="specs/test-epic/issues/valid-issue-malformed.md",
                timestamp=datetime.now(timezone.utc),
            )
            ledger = Path("specs") / "issues.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                "not valid json\n"
                "also not valid\n" + valid.model_dump_json() + "\n" + "trash\n"
            )

            import subprocess

            subprocess.run(
                ["git", "add", "."],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "setup ledger"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["specify", "ISS-300", "--dry-run"])
            assert result.exit_code == 0, result.output
            assert "DRY_RUN" in result.output

    def test_missing_dotdir_graceful(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["specify", "any-id"])
            assert result.exit_code == 1, result.output
            assert "ISSUE_NOT_FOUND" in result.output
