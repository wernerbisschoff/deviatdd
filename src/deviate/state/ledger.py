from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TextIO

from pydantic import (
    BaseModel,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
    model_validator,
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

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_flow_refs(cls, data: Any) -> Any:
        """Ignore historical ``flow_refs`` on append-only ledger rows."""
        if isinstance(data, dict) and "flow_refs" in data:
            data = dict(data)
            data.pop("flow_refs", None)
        return data


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


class SecurityProfile(BaseModel):
    """Optional per-task security profile body.

    Single-field model: ``body`` holds the verbatim markdown body of the
    ``## Security Profile`` section from ``plan.md``. The JUDGE prompt reads
    this as supplementary context when populating the ``security_checks``
    field on the verdict manifest.

    The field is intentionally prose-only — structured fields
    (``risk_surfaces`` / ``negative_tests`` / ``green_constraints``) are a
    follow-up concern. The model follows the ledger family pattern
    (``model_config = {"extra": "forbid"}``) so unknown fields are rejected
    at validation time.
    """

    body: str | None = None

    model_config = {"extra": "forbid"}


_CRITERION_ID_PATTERN: re.Pattern[str] = re.compile(r"^AC-PLAN-\d{3}$")


class CriterionLink(BaseModel):
    """Traceability link from a task row to an AC-PLAN-NNN criterion.

    ``criterion_id`` names a scenario in the owning slice's validated plan
    contract (``AC-PLAN-\\d{3}``). ``verification_mode`` selects how the
    criterion is verified; an ``automated`` link must carry a non-empty
    ``test_ref``. The model follows the ledger family pattern
    (``model_config = {"extra": "forbid"}``) so unknown fields are rejected.
    """

    criterion_id: str
    verification_mode: Literal["automated", "manual", "deferred"]
    test_ref: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("criterion_id")
    @classmethod
    def _validate_criterion_id(cls, v: str) -> str:
        if _CRITERION_ID_PATTERN.match(v) is None:
            raise ValueError(
                f"criterion_id must match {_CRITERION_ID_PATTERN.pattern}: {v}"
            )
        return v

    @model_validator(mode="after")
    def _automated_link_requires_test_ref(self) -> "CriterionLink":
        if self.verification_mode == "automated" and not self.test_ref:
            raise ValueError("test_ref is required for an automated link")
        return self


class TaskEvidenceItem(BaseModel):
    """Per-AC citation copied from a validated JUDGE handover onto COMPLETED."""

    ac: str
    test_path: str = ""
    test_quote: str = ""
    impl_path: str = ""
    impl_quote: str = ""

    model_config = {"extra": "ignore"}


class TaskEvidenceBundle(BaseModel):
    """COMPLETED-row proof: citations plus runner commit provenance (GH-84)."""

    items: list[TaskEvidenceItem] = Field(default_factory=list)
    red: str = ""
    green: str = ""
    head: str = ""

    model_config = {"extra": "ignore"}


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
    test_strategy: Literal["unit", "integration", "e2e"] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    security_profile: SecurityProfile | None = None
    acceptance_criteria: list[CriterionLink] | None = None
    evidence: TaskEvidenceBundle | None = None
    judge_action: Literal["revert_red", "revert_green"] | None = None
    judge_feedback: str | None = None
    head_sha: str | None = None
    reset_to: str | None = None
    recovery_ref: str | None = None
    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def _validate_task_id(cls, v: str) -> str:
        if not re.match(r"^TSK-\d{3}-\d{2}$", v):
            raise ValueError(f"Invalid task ID format: {v}")
        return v

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, TaskEvidenceBundle):
            return v
        if isinstance(v, list):
            return {"items": v}
        return v


def _write_jsonl_record(f: TextIO, record_json: str) -> None:
    """Write ``record_json`` as its own JSONL line.

    If the file is non-empty and does not already end in ``\\n``, a leading
    newline is written first so the new record is not concatenated onto the
    previous line. The write always leaves a trailing newline.
    """
    f.seek(0, 2)
    if f.tell() > 0:
        f.seek(f.tell() - 1)
        if f.read(1) != "\n":
            f.write("\n")
    f.write(record_json + "\n")


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
            _write_jsonl_record(f, record_json)
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
            _write_jsonl_record(f, record_json)
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


def _task_record_json(record: TaskRecord) -> str:
    """Serialize a task row, omitting absent optional fields so earlier rows stay lean."""
    exclude = set()
    if record.evidence is None:
        exclude.add("evidence")
    if record.judge_action is None:
        exclude.add("judge_action")
    if not record.judge_feedback:
        exclude.add("judge_feedback")
    if not record.head_sha:
        exclude.add("head_sha")
    if not record.reset_to:
        exclude.add("reset_to")
    if not record.recovery_ref:
        exclude.add("recovery_ref")
    return record.model_dump_json(exclude=exclude)


def append_task_record(record: TaskRecord, ledger_path: Path) -> bool:
    return _append_record(
        record_json=_task_record_json(record),
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
        record_json=_task_record_json(record),
        key_fields=["id", "status"],
        ledger_path=ledger_path,
    )


def append_task_event(record: TaskRecord, ledger_path: Path) -> None:
    """Always append a task ledger row.

    Used for JUDGE revert records that may repeat ``PENDING`` / ``RED``
    (``append_task_transition`` is a no-op on a repeated ``(id, status)``).
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a+", encoding="utf-8") as handle:
        if HAS_FCNTL:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            _write_jsonl_record(handle, _task_record_json(record))
        finally:
            if HAS_FCNTL:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def resolve_issue_record(issue_id: str, ledger_path: Path) -> IssueRecord | None:
    """Resolve the authoritative record for *issue_id*.

    ``COMPLETED`` is a terminal status and always takes precedence over later
    non-``COMPLETED`` entries: once an issue has been recorded ``COMPLETED``,
    no subsequent ``SPECIFIED`` / ``BACKLOG`` / ``DRAFT`` transition overrides
    it — even if that transition appears later in the ledger. This guards
    against merge flows that re-append a non-terminal transition after the
    ``COMPLETED`` write, and against idempotent merges whose write order is
    non-monotonic.

    Among non-``COMPLETED`` entries, the most recent valid record by file
    position wins (the prior behaviour).

    Tolerates sparse transitions (e.g. bare ``{issue_id, status, timestamp}``
    written by external tools like squash-merge) by merging them with the
    last fully-resolved record so they are not silently dropped by Pydantic
    validation.
    """
    records = _read_ledger(ledger_path)
    fallback: IssueRecord | None = None
    base: IssueRecord | None = None

    def _resolve_base(exclude: dict) -> IssueRecord | None:
        for prev in reversed(records):
            if prev.get("issue_id") != issue_id or prev is exclude:
                continue
            try:
                return IssueRecord.model_validate(prev)
            except PydanticValidationError:
                continue
        return None

    for data in reversed(records):
        if data.get("issue_id") != issue_id:
            continue
        try:
            candidate = IssueRecord.model_validate(data)
        except PydanticValidationError:
            # Sparse transition — resolve base on first need.
            if base is None:
                base = _resolve_base(data)
            if base is None:
                continue
            merged = {**base.model_dump(), **data}
            try:
                candidate = IssueRecord.model_validate(merged)
            except PydanticValidationError:
                continue
        # COMPLETED is terminal — return immediately, regardless of file order.
        if candidate.status == "COMPLETED":
            return candidate
        # Track the latest non-COMPLETED candidate as a fallback.
        if fallback is None:
            fallback = candidate

    return fallback


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

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_flow_refs(cls, data: Any) -> Any:
        """Ignore historical ``flow_refs`` on append-only ledger rows."""
        if isinstance(data, dict) and "flow_refs" in data:
            data = dict(data)
            data.pop("flow_refs", None)
        return data


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
