from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
)

try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


class IssueRecord(BaseModel):
    issue_id: str
    type: str
    title: str = Field(min_length=1)
    status: Literal["DRAFT", "BACKLOG", "SPECIFIED", "SHARDED", "COMPLETED"] = "DRAFT"
    source_file: str
    blocked_by: list[str] = []
    coordinates_with: list[str] = []
    timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flow_refs: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def _read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                warnings.warn(
                    f"Skipping malformed JSONL line {line_no} in {path}",
                    stacklevel=2,
                )
                continue
    return records


class TaskRecord(BaseModel):
    id: str
    issue_id: str
    description: str = Field(min_length=1)
    status: Literal[
        "PENDING",
        "RED",
        "GREEN",
        "JUDGE",
        "REFACTOR",
        "COMPLETED",
        "FAILED",
    ] = "PENDING"
    execution_mode: Literal["TDD", "DIRECT", "EXECUTE", "E2E", "IMMEDIATE"] = "TDD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def _validate_task_id(cls, v: str) -> str:
        if not re.match(r"^TSK-\d{3}-\d{2}$", v):
            raise ValueError(f"Invalid task ID format: {v}")
        return v


def _append_record(
    record_json: str,
    record_id: str,
    id_field: str,
    ledger_path: Path,
) -> bool:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a+", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get(id_field) == record_id:
                        return False
                except json.JSONDecodeError:
                    continue
            f.write(record_json + "\n")
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return True


def _append_with_compound_key(
    record_json: str,
    key_fields: list[str],
    ledger_path: Path,
) -> bool:
    """Append a record only if no existing entry matches all *key_fields* values."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record_data = json.loads(record_json)
    with ledger_path.open("a+", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if all(data.get(k) == record_data.get(k) for k in key_fields):
                        return False
                except json.JSONDecodeError:
                    continue
            f.write(record_json + "\n")
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return True


def append_issue_transition(record: IssueRecord, ledger_path: Path) -> bool:
    """Append a status-transition entry for an issue.

    Idempotency is checked on the ``(issue_id, status)`` compound key so that
    multiple transitions for the same issue (e.g. BACKLOG → CLAIMED →
    COMPLETED) are all recorded, but re-running the same transition is safe.
    """
    return _append_with_compound_key(
        record_json=record.model_dump_json(),
        key_fields=["issue_id", "status"],
        ledger_path=ledger_path,
    )


def append_task_record(record: TaskRecord, ledger_path: Path) -> bool:
    return _append_record(
        record_json=record.model_dump_json(),
        record_id=record.id,
        id_field="id",
        ledger_path=ledger_path,
    )


def append_task_transition(record: TaskRecord, ledger_path: Path) -> bool:
    """Append a status-transition entry for a task.

    Idempotency is checked on the ``(id, status)`` compound key so that
    multiple transitions for the same task (e.g. PENDING → RED → GREEN)
    are all recorded, but re-running the same transition is safe.
    """
    return _append_with_compound_key(
        record_json=record.model_dump_json(),
        key_fields=["id", "status"],
        ledger_path=ledger_path,
    )


def resolve_issue_record(issue_id: str, ledger_path: Path) -> IssueRecord | None:
    records = _read_ledger(ledger_path)
    for data in reversed(records):
        if data.get("issue_id") == issue_id:
            try:
                return IssueRecord.model_validate(data)
            except PydanticValidationError:
                continue
    return None


def append_issue_record(record: IssueRecord, ledger_path: Path) -> bool:
    return _append_record(
        record_json=record.model_dump_json(),
        record_id=record.issue_id,
        id_field="issue_id",
        ledger_path=ledger_path,
    )


class LedgerFilter(BaseModel):
    entity_type: Literal["issue", "task"]
    status_filter: str | None = None
    limit: int = Field(default=20, gt=0)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["created_at", "timestamp", "status"] = "created_at"
    sort_desc: bool = True
    model_config = {"extra": "forbid"}


def _read_ledger_strict(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                raise ValueError(f"Malformed JSONL line {line_no} in {path}")
    return records


def filter_tasks(ledger_path: Path, filter_obj: LedgerFilter) -> list[TaskRecord]:
    records = _read_ledger_strict(ledger_path)
    seen: set[str] = set()
    deduped: list[dict] = []
    for rec in records:
        task_id = rec.get("id")
        if task_id and task_id in seen:
            continue
        if task_id:
            seen.add(task_id)
        deduped.append(rec)
    if filter_obj.status_filter:
        deduped = [r for r in deduped if r.get("status") == filter_obj.status_filter]
    sort_key = filter_obj.sort_by
    deduped.sort(
        key=lambda r: r.get(sort_key, "") or "",
        reverse=filter_obj.sort_desc,
    )
    start = filter_obj.offset
    end = start + filter_obj.limit
    result = deduped[start:end]
    tasks: list[TaskRecord] = []
    for r in result:
        try:
            tasks.append(TaskRecord.model_validate(r))
        except PydanticValidationError as e:
            warnings.warn(f"Skipping invalid task record: {e}")
            continue
    return tasks


class RollbackSnapshot(BaseModel):
    phase: str
    branch: str
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    red_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str
    restored: bool = False
    model_config = {"extra": "forbid"}


ROLLBACK_LEDGER_NAME = "rollback.jsonl"


def append_rollback_snapshot(snapshot: RollbackSnapshot, deviate_dir: Path) -> bool:
    """Persist a RollbackSnapshot to .deviate/rollback.jsonl.

    Idempotency is checked on the (phase, commit_sha) compound key so that
    re-running the same rollback does not create duplicate entries.
    """
    ledger_path = deviate_dir / ROLLBACK_LEDGER_NAME
    return _append_with_compound_key(
        record_json=snapshot.model_dump_json(),
        key_fields=["phase", "commit_sha"],
        ledger_path=ledger_path,
    )


class AdhocRecord(BaseModel):
    issue_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    execution_mode: Literal["TDD", "DIRECT", "EXECUTE", "E2E", "IMMEDIATE"] = "DIRECT"
    status: Literal["PENDING", "COMPLETED"] = "PENDING"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flow_refs: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def _parse_timestamp(value: object) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Returns ``datetime.min`` (UTC) for unparseable or missing values so that
    malformed entries sort to the bottom rather than crashing the comparator.
    """
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _get_unblocked_backlog_features(ledger_path: Path) -> list[IssueRecord]:
    records = _read_ledger(ledger_path)
    if not records:
        return []

    status_map: dict[str, str] = {}
    for data in records:
        issue_id = data.get("issue_id")
        status = data.get("status")
        if issue_id and status:
            status_map[issue_id] = status

    typed: list[dict] = [r for r in records if r.get("type") is not None]
    issue_map: dict[str, dict] = {}
    for f in typed:
        issue_map[f["issue_id"]] = f

    candidates: list[IssueRecord] = []
    for issue_id, record in issue_map.items():
        latest_status = status_map.get(issue_id, "BACKLOG")
        if latest_status != "BACKLOG":
            continue
        blocked_by = record.get("blocked_by", [])
        is_unblocked = True
        for dep_id in blocked_by:
            dep_status = status_map.get(dep_id, "UNKNOWN")
            if dep_status != "COMPLETED":
                is_unblocked = False
                break
        if is_unblocked:
            candidates.append(IssueRecord.model_validate(record))

    candidates.sort(key=lambda r: r.created_at or r.timestamp)
    return candidates


def select_next_unblocked_issue(ledger_path: Path) -> IssueRecord | None:
    candidates = _get_unblocked_backlog_features(ledger_path)
    return candidates[0] if candidates else None


def select_unblocked_candidates(ledger_path: Path) -> list[IssueRecord]:
    """Return all unblocked BACKLOG issue records, sorted oldest-first.

    Multi-candidate version of ``select_next_unblocked_issue`` used by the
    try-claim loop in the specify pre command.
    """
    return _get_unblocked_backlog_features(ledger_path)
