import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from deviate.state.ledger import IssueRecord, append_issue_record


class TestIssueRecord:
    def test_issue_record_creation(self):
        record = IssueRecord(
            id=str(uuid4()),
            title="Test Issue",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-001",
            created_at=datetime.now(timezone.utc),
        )
        assert record.id is not None
        assert record.title == "Test Issue"
        assert record.status == "SHARDED"
        assert record.epic_slug == "epic-001"
        assert record.issue_slug == "iss-001"
        assert record.created_at.tzinfo is not None

    def test_issue_record_default_status(self):
        record = IssueRecord(
            id=str(uuid4()),
            title="Default Status",
            epic_slug="epic-001",
            issue_slug="iss-default",
        )
        assert record.status == "DRAFT"

    def test_issue_record_invalid_status(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                id=str(uuid4()),
                title="Bad Status",
                status="INVALID",
                epic_slug="epic-001",
                issue_slug="iss-002",
                created_at=datetime.now(timezone.utc),
            )

    def test_issue_record_missing_id(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                title="No ID",
                status="SHARDED",
                epic_slug="epic-001",
                issue_slug="iss-003",
                created_at=datetime.now(timezone.utc),
            )

    def test_issue_record_serialization(self):
        record = IssueRecord(
            id=str(uuid4()),
            title="Round Trip",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-004",
            created_at=datetime.now(timezone.utc),
        )
        data = json.loads(record.model_dump_json())
        restored = IssueRecord.model_validate(data)
        assert restored == record


class TestAppendIssueRecord:
    def test_append_new_record(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        record = IssueRecord(
            id=str(uuid4()),
            title="New Issue",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-005",
            created_at=datetime.now(timezone.utc),
        )
        result = append_issue_record(record, ledger_path)
        assert result is True
        assert ledger_path.exists()
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["issue_slug"] == "iss-005"

    def test_idempotent_skip_existing_slug(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        record = IssueRecord(
            id=str(uuid4()),
            title="First",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-same",
            created_at=datetime.now(timezone.utc),
        )
        result1 = append_issue_record(record, ledger_path)
        assert result1 is True

        record2 = IssueRecord(
            id=str(uuid4()),
            title="Second",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-same",
            created_at=datetime.now(timezone.utc),
        )
        result2 = append_issue_record(record2, ledger_path)
        assert result2 is False

        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_ledger_file_created_when_missing(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        assert not ledger_path.exists()

        record = IssueRecord(
            id=str(uuid4()),
            title="Creates File",
            status="SHARDED",
            epic_slug="epic-001",
            issue_slug="iss-creator",
            created_at=datetime.now(timezone.utc),
        )
        result = append_issue_record(record, ledger_path)
        assert result is True
        assert ledger_path.exists()
        assert ledger_path.stat().st_size > 0
