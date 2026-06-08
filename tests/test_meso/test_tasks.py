from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord

runner = CliRunner()


def _make_issue_record(
    issue_id: str,
    issue_slug: str = "test-issue",
    status: str = "SHARDED",
) -> IssueRecord:
    return IssueRecord(
        issue_id=issue_id,
        type="feature",
        title="Test Issue",
        status=status,
        source_file=f"specs/test-epic/issues/{issue_slug}.md",
        timestamp=datetime.now(timezone.utc),
    )


def _write_ledger(ledger_path: Path, *records: IssueRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


BUCKET = "test-epic"


class TestTasksCommand:
    def test_tasks_appends_pending_records(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440010"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["tasks", issue_id])
            assert result.exit_code == 0, result.output

            tasks_path = Path("specs") / BUCKET / "tasks.jsonl"
            assert tasks_path.is_file(), f"Expected {tasks_path} to exist"
            lines = tasks_path.read_text().strip().splitlines()
            assert len(lines) >= 1, "Expected at least one task record"

    def test_tasks_invalid_issue_id(self, tmp_path: Path):
        valid_id = "550e8400-e29b-41d4-a716-446655440011"
        missing_id = "550e8400-e29b-41d4-a716-446655440099"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(valid_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["tasks", missing_id])
            assert result.exit_code != 0, "Expected non-zero exit for invalid issue ID"
            assert "INVALID_ISSUE_ID" in result.output

    def test_tasks_idempotent_skip_existing(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440012"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            tasks_jsonl = Path("specs") / BUCKET / "tasks.jsonl"
            tasks_jsonl.parent.mkdir(parents=True)
            tasks_jsonl.write_text(
                '{"id":"existing-id","issue_id":"550e8400-e29b-41d4-a716-446655440012","description":"Existing task","status":"PENDING","execution_mode":"TDD","created_at":"2026-06-07T00:00:00Z"}\n'
            )

            pre_content = tasks_jsonl.read_text()

            result = runner.invoke(cli, ["tasks", issue_id])
            assert result.exit_code == 0, result.output
            assert "already provisioned" in result.output.lower()

            post_content = tasks_jsonl.read_text()
            assert post_content == pre_content, (
                "File content should remain unchanged on idempotent re-run"
            )

    def test_tasks_idempotent_skip_no_new_file(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440013"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            tasks_jsonl = Path("specs") / BUCKET / "tasks.jsonl"
            tasks_jsonl.parent.mkdir(parents=True)
            tasks_jsonl.write_text("existing,unchanged\n")

            pre_lines = len(tasks_jsonl.read_text().splitlines())

            result = runner.invoke(cli, ["tasks", issue_id])
            assert result.exit_code == 0, result.output

            post_lines = len(tasks_jsonl.read_text().splitlines())
            assert post_lines == pre_lines, (
                f"Line count changed: {pre_lines} → {post_lines}"
            )

    def test_tasks_sets_session_transition(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440014"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["tasks", issue_id])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"Expected IDLE, got {loaded.current_phase}"
            )
