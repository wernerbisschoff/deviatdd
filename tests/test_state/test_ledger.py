import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from deviate.state.ledger import (
    AdhocRecord,
    IssueRecord,
    TaskRecord,
    append_issue_record,
    append_task_record,
    resolve_issue_record,
)


class TestIssueRecord:
    def test_issue_record_creation(self):
        record = IssueRecord(
            issue_id="ISS-001-001",
            type="feature",
            title="Test Issue",
            status="SHARDED",
            source_file="specs/epic-001/issues/iss-001.md",
            timestamp=datetime.now(timezone.utc),
        )
        assert record.issue_id == "ISS-001-001"
        assert record.type == "feature"
        assert record.title == "Test Issue"
        assert record.status == "SHARDED"
        assert record.source_file == "specs/epic-001/issues/iss-001.md"
        assert record.timestamp is not None

    def test_issue_record_default_status(self):
        record = IssueRecord(
            issue_id="ISS-001-002",
            type="feature",
            title="Default Status",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        assert record.status == "DRAFT"

    def test_issue_record_invalid_status(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                issue_id="ISS-001-003",
                type="feature",
                title="Bad Status",
                status="INVALID",
                source_file="test.md",
                timestamp=datetime.now(timezone.utc),
            )

    def test_issue_record_missing_issue_id(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                type="feature",
                title="No ID",
                status="SHARDED",
                source_file="test.md",
                timestamp=datetime.now(timezone.utc),
            )

    def test_issue_record_serialization(self):
        record = IssueRecord(
            issue_id="ISS-001-004",
            type="feature",
            title="Round Trip",
            status="SHARDED",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        data = json.loads(record.model_dump_json())
        restored = IssueRecord.model_validate(data)
        assert restored == record


class TestAppendIssueRecord:
    def test_append_new_record(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        record = IssueRecord(
            issue_id="ISS-001-005",
            type="feature",
            title="New Issue",
            status="SHARDED",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        result = append_issue_record(record, ledger_path)
        assert result is True
        assert ledger_path.exists()
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["issue_id"] == "ISS-001-005"

    def test_idempotent_skip_existing_issue_id(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        record = IssueRecord(
            issue_id="ISS-SAME",
            type="feature",
            title="First",
            status="SHARDED",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        result1 = append_issue_record(record, ledger_path)
        assert result1 is True

        record2 = IssueRecord(
            issue_id="ISS-SAME",
            type="feature",
            title="Second",
            status="SHARDED",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        result2 = append_issue_record(record2, ledger_path)
        assert result2 is False

        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_ledger_file_created_when_missing(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        assert not ledger_path.exists()

        record = IssueRecord(
            issue_id="ISS-CREATOR",
            type="feature",
            title="Creates File",
            status="SHARDED",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        result = append_issue_record(record, ledger_path)
        assert result is True
        assert ledger_path.exists()
        assert ledger_path.stat().st_size > 0


class TestTaskRecord:
    def test_task_record_creation(self):
        record = TaskRecord(
            id="TSK-001-01",
            issue_id="iss-001",
            description="Implement task record model",
        )
        assert record.id == "TSK-001-01"
        assert record.issue_id == "iss-001"
        assert record.description == "Implement task record model"
        assert record.status == "PENDING"
        assert record.execution_mode == "TDD"
        assert record.created_at.tzinfo is not None

    def test_task_record_explicit_status_and_mode(self):
        record = TaskRecord(
            id="TSK-001-02",
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
                id="TSK-001-03",
                issue_id="iss-003",
                description="Bad status",
                status="INVALID",
            )

    def test_task_record_invalid_execution_mode(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id="TSK-001-04",
                issue_id="iss-004",
                description="Bad execution mode",
                execution_mode="INVALID",
            )

    def test_task_record_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id="TSK-001-05",
                issue_id="iss-005",
                description="Extra field",
                extra_field="should_fail",
            )

    def test_task_record_invalid_id_format(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id="not-a-tsk",
                issue_id="iss-006",
                description="Invalid ID format",
            )

    def test_task_record_empty_description(self):
        with pytest.raises(ValidationError):
            TaskRecord(
                id="TSK-001-06",
                issue_id="iss-007",
                description="",
            )

    def test_task_record_serialization(self):
        record = TaskRecord(
            id="TSK-001-07",
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
            id="TSK-001-08",
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
        task_id = "TSK-001-09"
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
            id="TSK-001-10",
            issue_id="iss-013",
            description="Creates dirs",
        )
        result = append_task_record(record, ledger_path)
        assert result is True
        assert ledger_path.parent.exists()
        assert ledger_path.exists()
        assert ledger_path.stat().st_size > 0


class TestResolveIssueRecord:
    def test_read_issue_record_by_issue_id(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        record = IssueRecord(
            issue_id="ISS-RESOLVE",
            type="feature",
            title="Test",
            status="DRAFT",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        append_issue_record(record, ledger_path)

        result = resolve_issue_record("ISS-RESOLVE", ledger_path)
        assert result is not None
        assert result.issue_id == "ISS-RESOLVE"
        assert result.title == "Test"

    def test_read_issue_record_not_found(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        result = resolve_issue_record("nonexistent-id", ledger_path)
        assert result is None


class TestAdhocRecord:
    def test_adhoc_record_schema(self):
        record = AdhocRecord(
            issue_id="adhoc-001",
            description="Fix typo in README",
        )
        assert record.issue_id == "adhoc-001"
        assert record.description == "Fix typo in README"
        assert record.execution_mode == "DIRECT"
        assert record.status == "PENDING"
        assert record.timestamp is not None

    def test_adhoc_record_explicit_execution_mode(self):
        record = AdhocRecord(
            issue_id="adhoc-002",
            description="Build auth system",
            execution_mode="TDD",
        )
        assert record.execution_mode == "TDD"

    def test_adhoc_record_explicit_status(self):
        record = AdhocRecord(
            issue_id="adhoc-003",
            description="Completed record",
            status="COMPLETED",
        )
        assert record.status == "COMPLETED"

    def test_adhoc_record_invalid_status(self):
        with pytest.raises(ValidationError):
            AdhocRecord(
                issue_id="adhoc-004",
                description="Invalid status",
                status="INVALID",
            )

    def test_adhoc_record_invalid_execution_mode(self):
        with pytest.raises(ValidationError):
            AdhocRecord(
                issue_id="adhoc-005",
                description="Invalid mode",
                execution_mode="INVALID",
            )

    def test_adhoc_record_empty_description(self):
        with pytest.raises(ValidationError):
            AdhocRecord(
                issue_id="adhoc-006",
                description="",
            )

    def test_adhoc_record_empty_issue_id(self):
        with pytest.raises(ValidationError):
            AdhocRecord(
                issue_id="",
                description="Empty issue ID",
            )

    def test_adhoc_record_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            AdhocRecord(
                issue_id="adhoc-007",
                description="Extra field",
                extra_field="should_fail",
            )

    def test_adhoc_record_serialization_roundtrip(self):
        import json

        record = AdhocRecord(
            issue_id="adhoc-008",
            description="Round trip test",
        )
        data = json.loads(record.model_dump_json())
        restored = AdhocRecord.model_validate(data)
        assert restored == record
