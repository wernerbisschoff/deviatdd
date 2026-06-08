from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from deviate.state.ledger import IssueRecord, resolve_issue_record


def _resolve_ledger(path: Path | None = None) -> Path:
    return path or Path("specs/issues.jsonl")


def resolve_issue(issue_id: str, ledger_path: Path | None = None) -> IssueRecord | None:
    return resolve_issue_record(issue_id, _resolve_ledger(ledger_path))


def claim_issue(issue_id: str, ledger_path: Path | None = None) -> bool:
    ledger_path = _resolve_ledger(ledger_path)
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
    ledger_path = _resolve_ledger(ledger_path)
    record = resolve_issue(issue_id, ledger_path)
    if record is None:
        return ""
    return record.model_dump_json(indent=2)


def is_issue_completed(issue_id: str, ledger_path: Path | None = None) -> bool:
    record = resolve_issue(issue_id, _resolve_ledger(ledger_path))
    if record is None:
        return False
    return record.status == "COMPLETED"
