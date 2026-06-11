from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from deviate.core.issues import claim_issue, resolve_issue


class TestResolveIssue:
    def test_resolve_issue_returns_record(self, tmp_path: Path):
        ledger = tmp_path / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "issue_id": "ISS-001-001",
            "type": "feature",
            "title": "Test issue",
            "status": "BACKLOG",
            "source_file": "specs/001/explore.md",
            "blocked_by": [],
            "coordinates_with": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ledger.write_text(json.dumps(record) + "\n")
        result = resolve_issue("ISS-001-001", ledger_path=ledger)
        assert result is not None
        assert result.issue_id == "ISS-001-001"

    def test_resolve_issue_returns_none_when_not_found(self, tmp_path: Path):
        ledger = tmp_path / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("")
        result = resolve_issue("NONEXISTENT", ledger_path=ledger)
        assert result is None


class TestClaimIssue:
    def test_claim_issue_updates_ledger(self, tmp_path: Path):
        ledger = tmp_path / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "issue_id": "ISS-001-002",
            "type": "feature",
            "title": "Claim test",
            "status": "BACKLOG",
            "source_file": "specs/002/explore.md",
            "blocked_by": [],
            "coordinates_with": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ledger.write_text(json.dumps(record) + "\n")
        result = claim_issue("ISS-001-002", ledger_path=ledger)
        assert result is True
        lines = ledger.read_text().strip().split("\n")
        assert len(lines) >= 2
