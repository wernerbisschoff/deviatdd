from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from deviate.state.ledger import (
    IssueRecord,
    _read_ledger,
    resolve_issue_record,
)


class TestIssueRecordSchemaRealignment:
    def test_issue_record_schema_realignment(self):
        record = IssueRecord(
            issue_id="ISS-001",
            type="feature",
            title="[FR-001] CLI Initialization",
            status="BACKLOG",
            source_file="specs/001/some-file.md",
            blocked_by=[],
            coordinates_with=["ISS-002"],
            timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert record.issue_id == "ISS-001"
        assert record.type == "feature"
        assert record.title == "[FR-001] CLI Initialization"
        assert record.status == "BACKLOG"
        assert record.source_file == "specs/001/some-file.md"
        assert record.blocked_by == []
        assert record.coordinates_with == ["ISS-002"]
        assert record.timestamp == datetime(2026, 6, 1, tzinfo=timezone.utc)

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                issue_id="ISS-002",
                type="feature",
                title="Test",
                status="BACKLOG",
                source_file="test.md",
                timestamp=datetime.now(timezone.utc),
                unknown_field="should_fail",
            )

    def test_rejects_missing_issue_id(self):
        with pytest.raises(ValidationError):
            IssueRecord(
                type="feature",
                title="Missing issue_id",
                status="BACKLOG",
                source_file="test.md",
                timestamp=datetime.now(timezone.utc),
            )

    def test_issue_id_is_primary_key(self):
        record = IssueRecord(
            issue_id="ISS-010",
            type="feature",
            title="PK test",
            status="BACKLOG",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        assert not hasattr(record, "id") or record.id is None
        assert record.issue_id == "ISS-010"

    def test_coordinates_with_default_empty_list(self):
        record = IssueRecord(
            issue_id="ISS-003",
            type="bug",
            title="No coords",
            status="BACKLOG",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        assert record.coordinates_with == []

    def test_blocked_by_default_empty_list(self):
        record = IssueRecord(
            issue_id="ISS-004",
            type="bug",
            title="No blockers",
            status="BACKLOG",
            source_file="test.md",
            timestamp=datetime.now(timezone.utc),
        )
        assert record.blocked_by == []


class TestMalformedJsonlRecovery:
    def test_malformed_jsonl_skip_with_warning(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        valid_line = json.dumps(
            {
                "issue_id": "ISS-001",
                "type": "feature",
                "title": "Valid",
                "status": "BACKLOG",
                "source_file": "test.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        ledger_path.write_text(
            f"{valid_line}\n{{broken-json}}\n{valid_line}\n",
            encoding="utf-8",
        )

        with pytest.warns(UserWarning, match=r"line 2"):
            records = _read_ledger(ledger_path)
        assert len(records) == 2

    def test_malformed_jsonl_includes_line_number(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            '{"valid": true}\nbad-data\n{"valid": false}\n',
            encoding="utf-8",
        )

        with pytest.warns(UserWarning) as warning_records:
            _read_ledger(ledger_path)
        assert len(warning_records) == 1
        assert "line 2" in str(warning_records[0].message)

    def test_malformed_jsonl_emits_warning_per_line(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            "bad\nworse\nstill-bad\n",
            encoding="utf-8",
        )

        with pytest.warns(UserWarning) as warning_records:
            records = _read_ledger(ledger_path)
        assert len(records) == 0
        assert len(warning_records) == 3

    def test_malformed_with_missing_issue_id_skipped(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "type": "feature",
                    "title": "Missing issue_id",
                    "status": "BACKLOG",
                    "source_file": "test.md",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        records = _read_ledger(ledger_path)
        assert len(records) == 1


class TestResolveIssueRecordByIssueId:
    def test_resolve_by_issue_id(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-001",
                    "type": "feature",
                    "title": "Test",
                    "status": "BACKLOG",
                    "source_file": "test.md",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = resolve_issue_record("ISS-001", ledger_path)
        assert result is not None
        assert result.issue_id == "ISS-001"

    def test_resolve_by_issue_id_not_found(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-001",
                    "type": "feature",
                    "title": "Test",
                    "status": "BACKLOG",
                    "source_file": "test.md",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = resolve_issue_record("ISS-999", ledger_path)
        assert result is None

    def test_resolve_respects_latest_record(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-001",
                    "type": "feature",
                    "title": "Original",
                    "status": "BACKLOG",
                    "source_file": "test.md",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
            + "\n"
            + json.dumps(
                {
                    "issue_id": "ISS-001",
                    "type": "feature",
                    "title": "Updated",
                    "status": "COMPLETED",
                    "source_file": "test.md",
                    "timestamp": "2026-01-02T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = resolve_issue_record("ISS-001", ledger_path)
        assert result is not None
        assert result.title == "Updated"
        assert result.status == "COMPLETED"

    def test_old_id_field_does_not_match(self, tmp_path: Path):
        ledger_path = tmp_path / "issues.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "id": "some-old-style-id",
                    "title": "Old style",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = resolve_issue_record("some-old-style-id", ledger_path)
        assert result is None
