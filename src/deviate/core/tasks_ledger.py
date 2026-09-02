from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from deviate.state.ledger import CriterionLink, TaskRecord


_TASK_LINE_PATTERN = re.compile(r"^\s*-\s+(?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.+)")
_MODE_PATTERN = re.compile(r"\*\*Mode\*\*:\s*(\S+)")
_TYPE_PATTERN = re.compile(r"\*\*Type\*\*:\s*(\S+)")
_STRATEGY_PATTERN = re.compile(r"\*\*Test Strategy\*\*:\s*`?(\S+)`?")
_CRITERIA_LINE_PATTERN = re.compile(r"^\s*-\s*\*\*Acceptance Criteria\*\*:\s*(.+)")
_LINK_PATTERN = re.compile(r"^(AC-PLAN-\d{3})\s*\(([^)]*)\)$")
_CRITERIA_ENTRY_SPLIT: re.Pattern[str] = re.compile(r",\s*(?=AC-PLAN-\d{3}\s*\()")

TEST_STRATEGIES = frozenset({"unit", "integration", "e2e"})


def parse_test_strategy(value: str | None) -> str | None:
    """Return ``unit``, ``integration``, or ``e2e``; drop retired runner values.

    ``Sociable_Unit`` / ``Solitary_Unit`` are not verification buckets.
    """
    if not value or not isinstance(value, str):
        return None
    normalized = value.strip().strip("`").strip("*").rstrip(".").lower()
    if normalized in TEST_STRATEGIES:
        return normalized
    return None


# Hard type→mode lock. Verification_Batch is not a Red-Green-Refactor cycle
# (api.md / architecture.md: EXECUTE / IMMEDIATE). Other types keep the
# planner-declared Mode so adhoc/plan can still pick TDD vs IMMEDIATE.
IMMEDIATE_TASK_TYPES = frozenset({"Verification_Batch"})


def resolve_execution_mode(
    task_type: str | None,
    declared_mode: str = "TDD",
) -> str:
    """Return the execution mode for a task type.

    ``Verification_Batch`` is always ``IMMEDIATE``. Every other type (or a
    missing type) keeps *declared_mode*.
    """
    if task_type in IMMEDIATE_TASK_TYPES:
        return "IMMEDIATE"
    return declared_mode


@dataclass
class _TaskBlock:
    task_id: str
    description: str
    execution_mode: str = "TDD"
    task_type: str | None = None
    test_strategy: str | None = None
    criteria_entries: list[str] = field(default_factory=list)


def generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[TaskRecord]:
    content = tasks_md.read_text(encoding="utf-8")
    blocks: list[_TaskBlock] = []
    current: _TaskBlock | None = None

    for line in content.splitlines():
        task_match = _TASK_LINE_PATTERN.match(line)
        if task_match:
            if current is not None:
                blocks.append(current)
            current = _TaskBlock(
                task_id=task_match.group(1),
                description=task_match.group(2).strip(),
            )
        elif current is not None:
            type_match = _TYPE_PATTERN.search(line)
            if type_match:
                current.task_type = type_match.group(1)
            mode_match = _MODE_PATTERN.search(line)
            if mode_match:
                current.execution_mode = mode_match.group(1)
            strategy_match = _STRATEGY_PATTERN.search(line)
            if strategy_match:
                current.test_strategy = parse_test_strategy(strategy_match.group(1))
            criteria_match = _CRITERIA_LINE_PATTERN.search(line)
            if criteria_match:
                current.criteria_entries = _parse_criteria_entries(
                    criteria_match.group(1)
                )
    if current is not None:
        blocks.append(current)

    return [
        _build_task_record(
            task_id=block.task_id,
            issue_id=issue_id,
            description=block.description,
            execution_mode=resolve_execution_mode(
                block.task_type, block.execution_mode
            ),
            test_strategy=block.test_strategy,
            criteria_entries=block.criteria_entries,
        )
        for block in blocks
    ]


def _parse_criteria_entries(text: str) -> list[str]:
    return [
        entry.strip() for entry in _CRITERIA_ENTRY_SPLIT.split(text) if entry.strip()
    ]


def _build_task_record(
    task_id: str,
    issue_id: str,
    description: str | None,
    execution_mode: str,
    criteria_entries: list[str] | None = None,
    test_strategy: str | None = None,
) -> TaskRecord:
    links: list[CriterionLink] | None = None
    if criteria_entries:
        links = [_parse_criterion_link(task_id, entry) for entry in criteria_entries]
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description or "",
        status="PENDING",
        execution_mode=execution_mode,
        test_strategy=test_strategy,  # type: ignore[arg-type]
        acceptance_criteria=links,
    )


def _parse_criterion_link(task_id: str, entry: str) -> CriterionLink:
    match = _LINK_PATTERN.match(entry)
    if match is None:
        raise ValueError(
            f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
        )
    inner = match.group(2)
    if not inner or not inner.strip():
        raise ValueError(
            f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
        )
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) > 2 or not parts[0]:
        raise ValueError(
            f"Malformed acceptance criteria entry for task {task_id}: {entry}"
        )
    verification_mode = parts[0]
    test_ref = parts[1] if len(parts) > 1 and parts[1] else None
    return CriterionLink(
        criterion_id=match.group(1),
        verification_mode=verification_mode,
        test_ref=test_ref,
    )


def validate_tasks_jsonl(records: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, record in enumerate(records):
        try:
            TaskRecord.model_validate(record)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(part) for part in err["loc"])
                errors.append(f"Record {i}: {loc}: {err['msg']}")
    return errors
