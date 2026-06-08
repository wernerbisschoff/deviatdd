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


class TestSpecifyCommand:
    def test_specify_valid_issue(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440000"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["specify", issue_id])
            assert result.exit_code == 0, result.output

            spec_dir = Path("specs") / BUCKET
            assert spec_dir.is_dir(), f"Expected directory {spec_dir} to be created"

    def test_specify_invalid_issue_id(self, tmp_path: Path):
        valid_id = "550e8400-e29b-41d4-a716-446655440001"
        missing_id = "550e8400-e29b-41d4-a716-446655440002"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(valid_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["specify", missing_id])
            assert result.exit_code != 0, "Expected non-zero exit for invalid issue ID"
            assert "INVALID_ISSUE_ID" in result.output

    def test_specify_issue_regardless_of_status(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440003"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id, status="DRAFT")
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["specify", issue_id])
            assert result.exit_code == 0, result.output

            spec_dir = Path("specs") / BUCKET
            assert spec_dir.is_dir(), f"Expected directory {spec_dir} for DRAFT issue"

    def test_specify_creates_spec_md_placeholder(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440004"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["specify", issue_id])
            assert result.exit_code == 0, result.output

            spec_md = Path("specs") / BUCKET / "spec.md"
            assert spec_md.is_file(), f"Expected {spec_md} placeholder to exist"

    def test_specify_sets_session_to_specify(self, tmp_path: Path):
        issue_id = "550e8400-e29b-41d4-a716-446655440005"

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(issue_id)
            _write_ledger(ledger, record)

            result = runner.invoke(cli, ["specify", issue_id])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "SPECIFY", (
                f"Expected SPECIFY, got {loaded.current_phase}"
            )
            assert loaded.active_issue_id == issue_id, (
                f"Expected active_issue_id={issue_id}, got {loaded.active_issue_id}"
            )
