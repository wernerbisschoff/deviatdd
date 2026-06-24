from __future__ import annotations

import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import _git_env

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord

runner = CliRunner()


def _setup_meso_workspace(
    tmp_git_repo: Path,
    issue_id: str = "ISS-100",
    issue_status: str = "BACKLOG",
) -> None:
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    spec_root = tmp_git_repo / "specs"
    spec_root.mkdir(parents=True)
    (spec_root / "constitution.md").write_text("# Constitution\n")

    epic_dir = spec_root / "test-epic"
    epic_dir.mkdir(parents=True)
    issue_body_dir = epic_dir / "issues"
    issue_body_dir.mkdir(parents=True)
    (issue_body_dir / "iss-100.md").write_text("# Test Issue\n\nFR-001: do the thing\n")
    (epic_dir / "prd.md").write_text("# PRD\n\nFR-001: do the thing\n")

    ledger = spec_root / "issues.jsonl"
    record = IssueRecord(
        issue_id=issue_id,
        type="feature",
        title="Test Meso Issue",
        status=issue_status,
        source_file="specs/test-epic/issues/iss-100.md",
        timestamp=datetime.now(timezone.utc),
    )
    ledger.write_text(record.model_dump_json() + "\n")

    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "setup meso workspace"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )


class TestMesoIntegration:
    def test_meso_integration_full_pipeline(self, tmp_git_repo: Path) -> None:
        _setup_meso_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["meso", "run", "--dry-run", "--verbose"])
            assert result.exit_code == 0, result.output
            assert "DRY_RUN" in result.output

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"

    def test_meso_integration_no_unblocked_issues(self, tmp_git_repo: Path) -> None:
        _setup_meso_workspace(
            tmp_git_repo, issue_id="ISS-100", issue_status="COMPLETED"
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["meso", "run", "--verbose"])
            assert result.exit_code != 0
            assert "NO_CLAIMABLE_ISSUES" in result.output
