"""Tests for the SecurityProfile Pydantic model and TaskRecord field.

These tests pin the structural contract:
- SecurityProfile is a single-field model (body: str | None) with extra="forbid"
- TaskRecord carries an optional security_profile field, defaulting to None
- Existing tasks.jsonl records (no security_profile field) parse cleanly
- Round-tripping a populated security_profile preserves the body
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from deviate.state.ledger import SecurityProfile, TaskRecord


class TestSecurityProfile:
    def test_security_profile_default_construction(self):
        """Empty SecurityProfile() yields body=None."""
        profile = SecurityProfile()
        assert profile.body is None

    def test_security_profile_round_trip_with_body(self):
        """Construct with body, serialize, deserialize, verify equality."""
        original = SecurityProfile(
            body="## Security Profile\n\nRisk surfaces: auth, secrets\n"
        )
        serialized = original.model_dump_json()
        restored = SecurityProfile.model_validate_json(serialized)
        assert restored.body == original.body
        assert restored == original

    def test_security_profile_follows_ledger_extra_forbid_contract(self):
        """SecurityProfile rejects unknown fields, matching sibling models."""
        with pytest.raises(ValidationError):
            SecurityProfile.model_validate({"body": "valid", "unknown_field": "value"})

    def test_task_record_parses_legacy_row_without_security_profile(self):
        """A pre-PR-1 task record JSON dict (no security_profile field) parses."""
        legacy_dict = {
            "id": "TSK-001-01",
            "issue_id": "ISS-001",
            "description": "Legacy task without security profile",
            "status": "PENDING",
            "execution_mode": "TDD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        record = TaskRecord.model_validate(legacy_dict)
        assert record.id == "TSK-001-01"
        assert record.security_profile is None

    def test_task_record_round_trips_with_security_profile(self):
        """Construct TaskRecord with security_profile, round-trip the JSON."""
        record = TaskRecord(
            id="TSK-001-02",
            issue_id="ISS-001",
            description="Task with security profile",
            security_profile=SecurityProfile(body="Risk surfaces: deserialization"),
        )
        serialized = record.model_dump_json()
        restored = TaskRecord.model_validate_json(serialized)
        assert restored.security_profile is not None
        assert restored.security_profile.body == "Risk surfaces: deserialization"
