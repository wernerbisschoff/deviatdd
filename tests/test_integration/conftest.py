from __future__ import annotations

from contextlib import chdir
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
        id="550e8400-e29b-41d4-a716-446655440100",
        title="Test Meso Issue",
        status="SHARDED",
        epic_slug="test-epic",
        issue_slug="test-meso-issue",
    )
    ledger = tmp_path / "specs" / "issues.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(issue.model_dump_json() + "\n")

    with chdir(tmp_path):
        yield tmp_path
