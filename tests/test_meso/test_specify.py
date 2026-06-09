from __future__ import annotations

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


class TestSpecifyPreSubcommand:
    def test_specify_pre_dry_run_emits_contract(self, tmp_git_repo: Path):
        issue_id = "ISS-001"
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            source_file = "specs/test-epic/issues/001-test-issue.md"
            (tmp_git_repo / "specs/test-epic/issues").mkdir(parents=True, exist_ok=True)
            (tmp_git_repo / source_file).write_text("Issue body content")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(
                issue_id,
                issue_slug="001-test-issue",
                status="BACKLOG",
            )
            _write_ledger(ledger, record)

            result = runner.invoke(
                cli, ["specify", "pre", "--issue", issue_id, "--dry-run"]
            )
            assert result.exit_code == 0, result.output

            # Should NOT have created a worktree
            assert not (tmp_git_repo / ".worktrees").exists()

            # Session should be advanced
            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "SPECIFY"
            assert loaded.active_issue_id == issue_id

            # JSON contract should be in output
            assert '"status": "DRY_RUN"' in result.output
            assert f'"issue_id": "{issue_id}"' in result.output
            assert '"epic_slug": "test-epic"' in result.output
            assert '"issue_slug": "001-test-issue"' in result.output
            assert '"branch_name": "feat/test-epic/001-test-issue"' in result.output
            assert (
                '"spec_target": "specs/test-epic/001-test-issue/spec.md"'
                in result.output
            )

    def test_specify_pre_with_explicit_issue_creates_worktree(self, tmp_git_repo: Path):
        issue_id = "ISS-002"
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            source_file = "specs/test-epic/issues/002-another-issue.md"
            (tmp_git_repo / "specs/test-epic/issues").mkdir(parents=True, exist_ok=True)
            (tmp_git_repo / source_file).write_text("Body with FR-001 reference")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(
                issue_id,
                issue_slug="002-another-issue",
                status="BACKLOG",
            )
            _write_ledger(ledger, record)

            result = runner.invoke(
                cli,
                [
                    "specify",
                    "pre",
                    "--issue",
                    issue_id,
                    "--force",
                ],
            )
            assert result.exit_code == 0, result.output

            # Worktree should be created at .worktrees/feat/test-epic/002-another-issue
            wt_path = (
                tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "002-another-issue"
            )
            assert wt_path.exists(), f"Expected worktree at {wt_path}"
            assert (wt_path / ".git").exists() or (wt_path / ".git").is_file()

            # Session advanced
            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "SPECIFY"
            assert loaded.active_issue_id == issue_id

            # Contract emitted
            assert '"status": "READY"' in result.output
            assert f'"issue_id": "{issue_id}"' in result.output

    def test_specify_pre_rejects_completed_issue(self, tmp_git_repo: Path):
        issue_id = "ISS-003"
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            source_file = "specs/test-epic/issues/003-done.md"
            (tmp_git_repo / "specs/test-epic/issues").mkdir(parents=True, exist_ok=True)
            (tmp_git_repo / source_file).write_text("Done")

            ledger = Path("specs") / "issues.jsonl"
            record = _make_issue_record(
                issue_id,
                issue_slug="003-done",
                status="COMPLETED",
            )
            _write_ledger(ledger, record)

            result = runner.invoke(
                cli, ["specify", "pre", "--issue", issue_id, "--dry-run"]
            )
            assert result.exit_code != 0
            assert "COMPLETED" in result.output

    def test_specify_pre_auto_selects_unblocked(self, tmp_git_repo: Path):
        blocked_id = "ISS-004"
        unblocked_id = "ISS-005"
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            (tmp_git_repo / "specs/test-epic/issues").mkdir(parents=True, exist_ok=True)

            ledger = Path("specs") / "issues.jsonl"
            blocked = _make_issue_record(
                blocked_id,
                issue_slug="004-blocked",
                status="BACKLOG",
            )
            blocked.blocked_by = ["ISS-999"]
            _write_ledger(ledger, blocked)
            unblocked = _make_issue_record(
                unblocked_id,
                issue_slug="005-unblocked",
                status="BACKLOG",
            )
            _write_ledger(ledger, unblocked)

            result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
            assert result.exit_code == 0, result.output
            assert unblocked_id in result.output

    def test_specify_pre_no_unblocked_issues(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            ledger = Path("specs") / "issues.jsonl"
            _write_ledger(ledger)

            result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
            assert result.exit_code != 0
            assert "NO_UNBLOCKED_BACKLOG" in result.output
