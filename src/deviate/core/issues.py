from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from deviate.state.ledger import IssueRecord, _read_ledger, resolve_issue_record


def resolve_issue(issue_id: str, ledger_path: Path | None = None) -> IssueRecord | None:
    ledger_path = ledger_path or Path("specs/issues.jsonl")
    return resolve_issue_record(issue_id, ledger_path)


def claim_issue(issue_id: str, ledger_path: Path | None = None) -> bool:
    ledger_path = ledger_path or Path("specs/issues.jsonl")
    record = resolve_issue(issue_id, ledger_path)
    if record is None:
        return False
    claimed = record.model_copy(
        update={
            "status": "SPECIFIED",
            "timestamp": datetime.now(timezone.utc),
        }
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(claimed.model_dump_json() + "\n")
    return True


def read_issue_body(issue_id: str, ledger_path: Path | None = None) -> str:
    ledger_path = ledger_path or Path("specs/issues.jsonl")
    records = _read_ledger(ledger_path)
    for data in reversed(records):
        if data.get("issue_id") == issue_id:
            return json.dumps(data, indent=2)
    return ""


def is_issue_completed(issue_id: str, ledger_path: Path | None = None) -> bool:
    ledger_path = ledger_path or Path("specs/issues.jsonl")
    record = resolve_issue(issue_id, ledger_path)
    if record is None:
        return False
    return record.status == "COMPLETED"
