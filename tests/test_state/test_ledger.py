import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from deviate.state.ledger import (
    IssueRecord,
    TaskRecord,
    append_issue_record,
    append_task_record,
    resolve_issue_record,
)


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


class TestTaskRecord:
    def test_task_record_creation(self):
        record = TaskRecord(
            id=str(uuid4()),
            issue_id="iss-001",
            description="Implement task record model",
        )
        assert record.id is not None
        assert record.issue_id == "iss-001"
        assert record.description == "Implement task record model"
        assert record.status == "PENDING"
        assert record.execution_mode == "TDD"
        assert record.created_at.tzinfo is not None

    def test_task_record_explicit_status_and_mode(self):
        record = TaskRecord(
            id=str(uuid4()),
            issue_id="iss-002",
            description="Explicit fields",
            status="RED",
            execution_mode="DIRECT",
        )
        assert record.status == "RED"
        assert record.execution_mode == "DIRECT"

    def test_task_record_invalid_status(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id=str(uuid4()),
                issue_id="iss-003",
                description="Bad status",
                status="INVALID",
            )

    def test_task_record_invalid_execution_mode(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id=str(uuid4()),
                issue_id="iss-004",
                description="Bad execution mode",
                execution_mode="INVALID",
            )

    def test_task_record_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id=str(uuid4()),
                issue_id="iss-005",
                description="Extra field",
                extra_field="should_fail",
            )

    def test_task_record_uuid4_validation(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id="not-a-uuid",
                issue_id="iss-006",
                description="Invalid UUID",
            )

    def test_task_record_empty_description(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id=str(uuid4()),
                issue_id="iss-007",
                description="",
            )

    def test_task_record_serialization(self):
        record = TaskRecord(
            id=str(uuid4()),
            issue_id="iss-008",
            description="Round trip",
            status="REFACTOR",
            execution_mode="E2E",
        )
        data = json.loads(record.model_dump_json())
        restored = TaskRecord.model_validate(data)
        assert restored == record


class TestAppendTaskRecord:
    def test_append_task_record_new(self, tmp_path: Path):
        ledger_path = tmp_path / "tasks.jsonl"
        record = TaskRecord(
            id=str(uuid4()),
            issue_id="iss-010",
            description="First task",
        )
        result = append_task_record(record, ledger_path)
        assert result is True
        assert ledger_path.exists()
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["id"] == record.id

    def test_append_task_record_idempotent_skip(self, tmp_path: Path):
        ledger_path = tmp_path / "tasks.jsonl"
        task_id = str(uuid4())
        record = TaskRecord(
            id=task_id,
            issue_id="iss-011",
            description="First",
        )
        result1 = append_task_record(record, ledger_path)
        assert result1 is True

        record2 = TaskRecord(
            id=task_id,
            issue_id="iss-012",
            description="Duplicate id",
        )
        result2 = append_task_record(record2, ledger_path)
        assert result2 is False

        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_task_ledger_directory_creation(self, tmp_path: Path):
        ledger_path = tmp_path / "subdir" / "tasks.jsonl"
        assert not ledger_path.parent.exists()

        record = TaskRecord(
            id=str(uuid4()),
            issue_id="iss-013",
            description="Creates dirs",
        )
        result = append_task_record(record, ledger_path)
        assert result is True
        assert ledger_path.parent.exists()
        assert ledger_path.exists()
        assert ledger_path.stat().st_size > 0


class TestResolveIssueRecord:
    def test_read_issue_record_by_id(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        issue_id = str(uuid4())
        record = IssueRecord(
            id=issue_id,
            title="Test",
            epic_slug="epic-001",
            issue_slug="iss-resolve",
        )
        append_issue_record(record, ledger_path)

        result = resolve_issue_record(issue_id, ledger_path)
        assert result is not None
        assert result.id == issue_id
        assert result.title == "Test"

    def test_read_issue_record_not_found(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        result = resolve_issue_record("nonexistent-id", ledger_path)
        assert result is None
