from __future__ import annotations

from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

import pytest

from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")
    spec_dir = tmp_path / "specs" / "001-deviate-cli-python"
    spec_dir.mkdir(parents=True)
    with chdir(tmp_path):
        yield tmp_path


@pytest.fixture
def meso_workspace(tmp_path: Path) -> Path:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    issue = IssueRecord(
        issue_id="ISS-100",
        type="feature",
        title="Test Meso Issue",
        status="SHARDED",
        source_file="specs/test-epic/issues/test-meso-issue.md",  # stem = test-meso-issue
        timestamp=datetime.now(timezone.utc),
    )
    ledger = tmp_path / "specs" / "issues.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(issue.model_dump_json() + "\n")

    with chdir(tmp_path):
        yield tmp_path
