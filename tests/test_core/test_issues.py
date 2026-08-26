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

    def test_claim_issue_separates_when_last_line_lacks_newline(self, tmp_path: Path):
        """GH-117: claim must not concatenate SPECIFIED onto a newline-less BACKLOG."""
        ledger = tmp_path / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "issue_id": "ISS-ADH-030",
            "type": "feature",
            "title": "Claim without trailing newline",
            "status": "BACKLOG",
            "source_file": "specs/adhoc/issues/030-config-rework.md",
            "blocked_by": [],
            "coordinates_with": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ledger.write_text(json.dumps(record), encoding="utf-8")
        assert not ledger.read_bytes().endswith(b"\n")

        result = claim_issue("ISS-ADH-030", ledger_path=ledger)
        assert result is True

        raw = ledger.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        lines = raw.splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["status"] == "BACKLOG"
        assert json.loads(lines[1])["status"] == "SPECIFIED"
        assert json.loads(lines[0])["issue_id"] == "ISS-ADH-030"
        assert json.loads(lines[1])["issue_id"] == "ISS-ADH-030"
