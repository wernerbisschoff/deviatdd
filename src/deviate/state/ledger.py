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

    security_profile: SecurityProfile | None = None
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
    flow_refs: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def _validate_flow_id(value: str) -> str:
    # Canonical source: src/deviate/cli/adhoc.py:19. Import lazily to avoid the
    # cli.adhoc -> state.ledger module initialization cycle.
    from deviate.cli.adhoc import _FLOW_REF_PATTERN

    if _FLOW_REF_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Invalid flow ID format: {value}")
    return value


_LINKED_FLOW_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "FLOW_REFERENCED_BY_ISSUE",
        "FLOW_INCLUDED_IN_RELEASE",
        "FLOW_IMPLEMENTATION_EVIDENCE_ADDED",
        "FLOW_CONFIRMED_IMPLEMENTED",
    }
)


class FlowRecord(BaseModel):
    flow_id: str
    name: str
    actor: str
    domain: str
    source: str
    status: Literal["Active", "Deprecated"] = "Active"
    first_discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {"extra": "forbid"}

    _flow_id_is_canonical = field_validator("flow_id")(_validate_flow_id)


class FlowEvent(BaseModel):
    flow_id: str
    event_type: Literal[
        "FLOW_DISCOVERED",
        "FLOW_DOCUMENTED",
        "FLOW_IMPLEMENTATION_EVIDENCE_ADDED",
        "FLOW_CONFIRMED_IMPLEMENTED",
        "FLOW_REFERENCED_BY_ISSUE",
        "FLOW_INCLUDED_IN_RELEASE",
        "FLOW_DEPRECATED",
    ]
    event_issue_id: str | None = None
    event_release_version: str | None = None
    evidence_path: str | None = None
    timestamp: datetime

    model_config = {"extra": "forbid"}

    _flow_id_is_canonical = field_validator("flow_id")(_validate_flow_id)

    @model_validator(mode="after")
    def _linked_event_has_reference(self) -> "FlowEvent":
        references = (
            self.event_issue_id,
            self.event_release_version,
            self.evidence_path,
        )
        if self.event_type in _LINKED_FLOW_EVENT_TYPES and not any(references):
            raise ValueError(f"{self.event_type} requires a reference field")
        return self


class FlowCoverage(BaseModel):
    flow_id: str
    discovered_status: Literal["DISCOVERED", "UNDISCOVERED"]
    doc_status: Literal["DOCUMENTED", "UNDOCUMENTED"]
    impl_status: Literal[
        "CONFIRMED_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "UNCONFIRMED"
    ]
    drift_flag: Literal[
        "PROMPT_ONLY_NO_CODE",
        "DOC_ARTIFACT_ONLY",
        "DOCUMENTED_BUT_NOT_IMPLEMENTED",
        "IMPLEMENTED_BUT_UNDOCUMENTED",
        "ORPHANED_FLOW",
        "STALE_DRIFT",
        "OK",
    ]
    last_referenced_by_issue_id: str | None = None
    last_referenced_by_release_version: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


FlowImplementationStatus = Literal[
    "CONFIRMED_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "UNCONFIRMED"
]
FlowDriftFlag = Literal[
    "PROMPT_ONLY_NO_CODE",
    "DOC_ARTIFACT_ONLY",
    "DOCUMENTED_BUT_NOT_IMPLEMENTED",
    "IMPLEMENTED_BUT_UNDOCUMENTED",
    "ORPHANED_FLOW",
    "STALE_DRIFT",
    "OK",
]


_FLOW_EVENT_KEY_FIELDS = [
    "flow_id",
    "event_type",
    "event_issue_id",
    "event_release_version",
    "evidence_path",
]


def append_flow_record(record: FlowRecord, ledger_path: Path) -> bool:
    """Append a ``FlowRecord`` identity row to the flows ledger.

    Idempotency is checked on the ``flow_id`` key so that re-seeding the
    canonical flow index does not produce duplicate identity rows. Mirrors
    the ``append_issue_record`` pattern at ``src/deviate/state/ledger.py:242``.
    """
    return _append_record(
        record_json=record.model_dump_json(),
        record_id=record.flow_id,
        id_field="flow_id",
        ledger_path=ledger_path,
    )


def append_flow_event(event: FlowEvent, ledger_path: Path) -> bool:
    """Append a ``FlowEvent`` row to the flows ledger.

    Idempotency is enforced on the
    ``(flow_id, event_type, event_issue_id, event_release_version, evidence_path)``
    compound key — when two events share all five fields the earlier
    timestamp is preserved and no new row is written. Mirrors
    ``_append_with_compound_key`` at ``src/deviate/state/ledger.py:116``.
    """
    return _append_with_compound_key(
        record_json=event.model_dump_json(),
        key_fields=_FLOW_EVENT_KEY_FIELDS,
        ledger_path=ledger_path,
    )


def _parse_flows_index(flows_index: Path) -> list[FlowRecord]:
    """Parse the canonical ``flows/index.md`` table into identity rows.

    The index table is the canonical source of truth for flow identity
    (per ``specs/_product/flows/index.md:5-8``). Each row carrying a
    ``FLOW-`` prefix is converted to a ``FlowRecord``. Malformed rows
    are skipped silently — the index is human-authored and may be
    sparsely populated.
    """
    if not flows_index.exists():
        return []
    records: list[FlowRecord] = []
    for raw_line in flows_index.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "Flow ID" in line or "---" in line:
            continue
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        if len(cells) < 6 or not cells[0].startswith("FLOW-"):
            continue
        try:
            records.append(
                FlowRecord(
                    flow_id=cells[0],
                    name=cells[1],
                    actor=cells[2],
                    domain=cells[3],
                    status=cells[4]
                    if cells[4] in {"Active", "Deprecated"}
                    else "Active",
                    source=cells[5].strip("`"),
                )
            )
        except PydanticValidationError:
            continue
    return records


def _iter_flow_ledger_rows(
    ledger_path: Path,
) -> tuple[list[FlowRecord], list[FlowEvent]]:
    """Read the flows ledger and split rows into identity + event buckets.

    Rows are discriminated by the presence of an ``event_type`` field:
    ``FlowEvent`` rows carry it, ``FlowRecord`` rows do not. Malformed
    rows are skipped via the lenient ``_read_ledger`` parser.
    """
    identity_rows: list[FlowRecord] = []
    event_rows: list[FlowEvent] = []
    for data in _read_ledger(ledger_path):
        if "event_type" in data:
            try:
                event_rows.append(FlowEvent.model_validate(data))
            except PydanticValidationError:
                continue
        else:
            try:
                identity_rows.append(FlowRecord.model_validate(data))
            except PydanticValidationError:
                continue
    return identity_rows, event_rows


def _derive_impl_status(events: list[FlowEvent]) -> FlowImplementationStatus:
    has_confirmed = any(e.event_type == "FLOW_CONFIRMED_IMPLEMENTED" for e in events)
    if has_confirmed:
        return "CONFIRMED_IMPLEMENTED"
    has_evidence = any(
        e.event_type == "FLOW_IMPLEMENTATION_EVIDENCE_ADDED" for e in events
    )
    if has_evidence:
        return "PARTIALLY_IMPLEMENTED"
    return "UNCONFIRMED"


def _derive_drift_flag(
    *,
    discovered: bool,
    documented: bool,
    impl_status: FlowImplementationStatus,
    referenced_by_issue: bool,
    referenced_by_release: bool,
) -> FlowDriftFlag:
    if (
        referenced_by_issue
        and not discovered
        and not documented
        and impl_status == "UNCONFIRMED"
    ):
        return "PROMPT_ONLY_NO_CODE"
    state = (discovered, documented, impl_status)
    drift_by_state: dict[tuple[bool, bool, FlowImplementationStatus], FlowDriftFlag] = {
        (False, False, "UNCONFIRMED"): "DOC_ARTIFACT_ONLY",
        (True, False, "UNCONFIRMED"): "PROMPT_ONLY_NO_CODE",
        (True, True, "UNCONFIRMED"): "DOCUMENTED_BUT_NOT_IMPLEMENTED",
        (False, True, "UNCONFIRMED"): "DOCUMENTED_BUT_NOT_IMPLEMENTED",
        (False, False, "PARTIALLY_IMPLEMENTED"): "IMPLEMENTED_BUT_UNDOCUMENTED",
        (False, False, "CONFIRMED_IMPLEMENTED"): "IMPLEMENTED_BUT_UNDOCUMENTED",
        (True, False, "PARTIALLY_IMPLEMENTED"): "IMPLEMENTED_BUT_UNDOCUMENTED",
        (True, False, "CONFIRMED_IMPLEMENTED"): "IMPLEMENTED_BUT_UNDOCUMENTED",
    }
    if state in drift_by_state:
        return drift_by_state[state]
    if (
        impl_status == "CONFIRMED_IMPLEMENTED"
        and documented
        and not referenced_by_release
    ):
        return "STALE_DRIFT"
    return "OK"


def _latest_issue_reference(flow_id: str, issues_ledger: Path) -> str | None:
    """Return the most recent ``IssueRecord.flow_refs`` mention of *flow_id*.

    The reverse index is derived by replaying ``specs/issues.jsonl``;
    ``flow_refs: [FLOW-XX]`` rows in the issue ledger drive the
    ``last_referenced_by_issue_id`` field on the coverage row.
    """
    latest_issue_id: str | None = None
    latest_timestamp = datetime.min.replace(tzinfo=timezone.utc)
    for data in _read_ledger(issues_ledger):
        flow_refs = data.get("flow_refs") or []
        if flow_id not in flow_refs:
            continue
        issue_id = data.get("issue_id")
        if not issue_id:
            continue
        timestamp = _parse_timestamp(data.get("created_at") or data.get("timestamp"))
        if timestamp >= latest_timestamp:
            latest_timestamp = timestamp
            latest_issue_id = issue_id
    return latest_issue_id


def _group_flow_events(events: list[FlowEvent]) -> dict[str, list[FlowEvent]]:
    grouped: dict[str, list[FlowEvent]] = {}
    for event in events:
        grouped.setdefault(event.flow_id, []).append(event)
    return grouped


def _last_release_reference(events: list[FlowEvent]) -> str | None:
    return next(
        (
            event.event_release_version
            for event in reversed(events)
            if event.event_type == "FLOW_INCLUDED_IN_RELEASE"
            and event.event_release_version
        ),
        None,
    )


def _implementation_evidence_paths(events: list[FlowEvent]) -> list[str]:
    return [
        event.evidence_path
        for event in events
        if event.event_type == "FLOW_IMPLEMENTATION_EVIDENCE_ADDED"
        and event.evidence_path
    ]


def load_flow_coverage(
    ledger_path: Path, flows_index: Path, issues_ledger: Path
) -> list[FlowCoverage]:
    """Derive ``FlowCoverage`` rows for every flow in the canonical index.

    The canonical flow set is ``specs/_product/flows/index.md`` (per the
    spec: *derivation is canonical-set-driven*). The flows ledger layers
    on top with event-sourced state (``FLOW_DISCOVERED``,
    ``FLOW_DOCUMENTED``, ``FLOW_CONFIRMED_IMPLEMENTED``, etc.) and the
    issues ledger is reverse-indexed to populate
    ``last_referenced_by_issue_id``. Rows are returned in index order.
    """
    canonical = _parse_flows_index(flows_index)
    canonical_index_ids = {r.flow_id for r in canonical}
    identity_rows, event_rows = _iter_flow_ledger_rows(ledger_path)
    events_by_flow = _group_flow_events(event_rows)
    for identity in identity_rows:
        # Identity rows in the ledger are the fallback when the index
        # is empty — the canonical set drives the iteration but each
        # row in the ledger represents a real flow. Ledger-only rows
        # (absent from the canonical index) are emitted as
        # ORPHANED_FLOW per the spec edge case "Flow present in
        # flows.jsonl but absent from index.md".
        if identity.flow_id not in canonical_index_ids:
            canonical.append(identity)
    coverage: list[FlowCoverage] = []
    for identity in canonical:
        events = events_by_flow.get(identity.flow_id, [])
        discovered = any(e.event_type == "FLOW_DISCOVERED" for e in events)
        documented = any(e.event_type == "FLOW_DOCUMENTED" for e in events)
        impl_status = _derive_impl_status(events)
        last_issue = _latest_issue_reference(identity.flow_id, issues_ledger)
        last_release = _last_release_reference(events)
        evidence_paths = _implementation_evidence_paths(events)
        in_canonical_index = identity.flow_id in canonical_index_ids
        if not in_canonical_index:
            drift_flag: FlowDriftFlag = "ORPHANED_FLOW"
        else:
            drift_flag = _derive_drift_flag(
                discovered=discovered,
                documented=documented,
                impl_status=impl_status,
                referenced_by_issue=last_issue is not None,
                referenced_by_release=last_release is not None,
            )
        coverage.append(
            FlowCoverage(
                flow_id=identity.flow_id,
                discovered_status="DISCOVERED" if discovered else "UNDISCOVERED",
                doc_status="DOCUMENTED" if documented else "UNDOCUMENTED",
                impl_status=impl_status,
                drift_flag=drift_flag,
                last_referenced_by_issue_id=last_issue,
                last_referenced_by_release_version=last_release,
                evidence_paths=evidence_paths,
            )
        )
    return coverage


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


class FlowConfirmationResult(BaseModel):
    """Outcome of :func:`_confirm_implemented_flows`.

    ``flow_ids`` is the set of refs that were confirmed (already recorded
    or written on this call).  ``appended_count`` distinguishes new
    writes from idempotent no-ops, so callers can emit
    ``[green]CONFIRMED[/]`` vs ``[yellow]LEDGER_IDEMPOTENT[/]`` banners
    without re-parsing the ledger.  ``skipped_refs`` is the list of
    flow tokens the helper intentionally did not write: orphans (no
    matching ``FlowRecord``) and malformed tokens.
    """

    flow_ids: list[str] = Field(default_factory=list)
    appended_count: int = 0
    skipped_refs: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def _confirm_implemented_flows(
    *,
    issue_id: str,
    issues_ledger: Path,
    flows_ledger: Path,
) -> FlowConfirmationResult:
    """Append ``FLOW_CONFIRMED_IMPLEMENTED`` events for an issue's flow refs.

    Pure ledger operation: reads the issue's ``flow_refs`` from
    *issues_ledger*, validates each token against the canonical flow ID
    regex, and writes one ``FlowEvent`` per ref to *flows_ledger* via
    :func:`append_flow_event`. The compound key
    ``(flow_id, event_type, event_issue_id, evidence_path=None)`` is
    the dedup boundary — re-invoking this helper for the same issue
    produces zero new rows but still reports the flow IDs as confirmed.

    Orphan policy (depends on flows ledger state):
      * flows ledger missing or has no identity rows (unseeded):
        every syntactically valid ref is confirmed; ``skipped_refs``
        remains empty. Confirmation events persist; they will be
        un-represented in ``load_flow_coverage`` until a matching
        ``FlowRecord`` or index row exists, but they are not
        surfaced as orphans.
      * flows ledger seeded with identity rows: refs without a
        matching ``FlowRecord`` are reported in ``skipped_refs``.
        The merge CLI surfaces these as
        ``ORPHANED_FLOW_REF_SKIPPED`` for the operator; coverage
        itself derives rows from the canonical set, so event-only
        orphans are not classified as ``ORPHANED_FLOW`` here.
      * unknown issue id: returns an empty result, no ledger
        writes.
      * malformed token (anything that does not match
        ``FLOW-\\d{2,}``): appended to ``skipped_refs``.

    Malformed tokens (anything that does not match ``FLOW-\\d{2,}``)
    are also reported in ``skipped_refs``; they are a bug in the
    upstream issue record and coverage will never classify them.
    """
    result = FlowConfirmationResult()
    record = resolve_issue_record(issue_id, issues_ledger)
    if record is None:
        return result
    flow_refs = list(record.flow_refs or [])
    if not flow_refs:
        return result

    timestamp = datetime.now(timezone.utc)
    for ref in flow_refs:
        if not ref or not re.match(r"^FLOW-\d{2,}$", ref):
            if ref:
                result.skipped_refs.append(ref)
            continue
        # Always confirm syntactically valid refs — orphan diagnostics
        # are a coverage concern.  ``load_flow_coverage`` iterates the
        # canonical set (index/identity rows) and only emits
        # ``ORPHANED_FLOW`` for identity rows that are absent from
        # the index; it does not classify event-only refs as
        # orphans, so we do not skip here either.  Skipping at
        # merge time would also create stale data: the user has
        # shipped the work, but the ledger would carry no
        # confirmation event until the index is manually seeded.
        appended = append_flow_event(
            FlowEvent(
                flow_id=ref,
                event_type="FLOW_CONFIRMED_IMPLEMENTED",
                event_issue_id=issue_id,
                event_release_version=None,
                evidence_path=None,
                timestamp=timestamp,
            ),
            flows_ledger,
        )
        result.flow_ids.append(ref)
        if appended:
            result.appended_count += 1
    return result


def _issue_timestamps_by_id(issues_ledger: Path) -> dict[str, datetime]:
    """Build a map of issue_id → most recent timestamp from the ledger.

    The issues ledger is append-only; for each issue_id we keep the
    latest timestamp seen.  Used to sort release candidates by
    ``last_referenced_by_issue_id`` without falling back to lexical
    order.
    """
    out: dict[str, datetime] = {}
    for data in _read_ledger(issues_ledger):
        issue_id = data.get("issue_id")
        if not issue_id:
            continue
        ts = _parse_timestamp(data.get("created_at") or data.get("timestamp"))
        if issue_id not in out or ts > out[issue_id]:
            out[issue_id] = ts
    return out


def select_release_candidate_flows(
    *,
    flows_ledger: Path,
    flows_index: Path,
    issues_ledger: Path,
    exclude_released: bool = True,
) -> list[FlowCoverage]:
    """Return ``FlowCoverage`` rows whose implementation is confirmed.

    The candidate set is the canonical flow set with
    ``impl_status == "CONFIRMED_IMPLEMENTED"``. When
    ``exclude_released`` is true (default), flows with any prior
    ``FLOW_INCLUDED_IN_RELEASE`` event are excluded so that a release
    does not re-list what it already shipped.  When false, every
    confirmed flow is returned regardless of release history.

    Returns an empty list when *flows_ledger* does not exist
    (first-run state — no confirmed flows possible).  Empty list is
    also returned when the canonical index is missing so the caller
    does not need a special-case branch.

    Ordering: flows whose ``last_referenced_by_issue_id`` is the most
    recent in the issues ledger come first, ties broken by ``flow_id``
    ascending.  Rows with no issue reference sort last by ``flow_id``.
    """
    if not flows_ledger.exists() or not flows_index.exists():
        return []
    coverage = load_flow_coverage(flows_ledger, flows_index, issues_ledger)
    candidates = [row for row in coverage if row.impl_status == "CONFIRMED_IMPLEMENTED"]
    if exclude_released:
        _, event_rows = _iter_flow_ledger_rows(flows_ledger)
        released = {
            ev.flow_id
            for ev in event_rows
            if ev.event_type == "FLOW_INCLUDED_IN_RELEASE"
        }
        candidates = [r for r in candidates if r.flow_id not in released]

    issue_ts = _issue_timestamps_by_id(issues_ledger)
    sentinel_min = datetime.min.replace(tzinfo=timezone.utc)

    # Deterministic ordering:
    # 1) Stable sort by flow_id ascending (canonical, human-friendly
    #    tiebreaker).
    # 2) Split into referenced / unreferenced and stable-sort the
    #    referenced bucket by issue timestamp descending so the most
    #    recent reference comes first while preserving the flow_id
    #    order from step 1.  Unreferenced rows sort last by flow_id.
    candidates.sort(key=lambda r: r.flow_id)
    referenced = [r for r in candidates if r.last_referenced_by_issue_id]
    unreferenced = [r for r in candidates if not r.last_referenced_by_issue_id]
    referenced.sort(
        key=lambda r: issue_ts.get(r.last_referenced_by_issue_id or "", sentinel_min),
        reverse=True,
    )
    return referenced + unreferenced
