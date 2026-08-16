from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from deviate.state.ledger import CriterionLink, TaskRecord


_TASK_LINE_PATTERN = re.compile(r"^\s*-\s+(?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.+)")
_MODE_PATTERN = re.compile(r"\*\*Mode\*\*:\s*(\S+)")
_CRITERIA_LINE_PATTERN = re.compile(r"\*\*Acceptance Criteria\*\*:\s*(.+)")
_LINK_PATTERN = re.compile(r"^(AC-PLAN-\d{3})\s*\(([^)]*)\)$")
_CRITERIA_ENTRY_SPLIT: re.Pattern[str] = re.compile(r",\s*(?=AC-PLAN-\d{3}\s*\()")


@dataclass
class _TaskBlock:
    task_id: str
    description: str
    execution_mode: str = "TDD"
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
            mode_match = _MODE_PATTERN.search(line)
            if mode_match:
                current.execution_mode = mode_match.group(1)
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
            execution_mode=block.execution_mode,
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
        acceptance_criteria=links,
    )


def _parse_criterion_link(task_id: str, entry: str) -> CriterionLink:
    match = _LINK_PATTERN.match(entry)
    if match is None:
        raise ValueError(
            f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
        )
    inner = match.group(2)
    parts = [p.strip() for p in inner.split(",")] if inner else []
    verification_mode = parts[0] if parts else ""
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
