from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from deviate.state.ledger import CriterionLink, TaskRecord


_TASK_LINE_PATTERN = re.compile(r"^\s*-\s+(?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.+)")
_MODE_PATTERN = re.compile(r"\*\*Mode\*\*:\s*(\S+)")
_CRITERIA_LINE_PATTERN = re.compile(r"\*\*Acceptance Criteria\*\*:\s*(.+)")
_LINK_PATTERN = re.compile(r"^(AC-PLAN-\d{3})\s*\(([^)]*)\)$")


def generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[TaskRecord]:
    content = tasks_md.read_text(encoding="utf-8")
    records: list[TaskRecord] = []
    current_id: str | None = None
    current_desc: str | None = None
    current_mode: str = "TDD"
    current_criteria: list[str] = []

    for line in content.splitlines():
        task_match = _TASK_LINE_PATTERN.match(line)
        if task_match:
            if current_id:
                records.append(
                    _build_task_record(
                        current_id,
                        issue_id,
                        current_desc,
                        current_mode,
                        current_criteria,
                    )
                )
            current_id = task_match.group(1)
            current_desc = task_match.group(2).strip()
            current_mode = "TDD"
            current_criteria = []
        elif current_id:
            mode_match = _MODE_PATTERN.search(line)
            if mode_match:
                current_mode = mode_match.group(1)
            criteria_match = _CRITERIA_LINE_PATTERN.search(line)
            if criteria_match:
                current_criteria = [
                    entry.strip()
                    for entry in re.split(
                        r",\s*(?=AC-PLAN-\d{3}\s*\()", criteria_match.group(1)
                    )
                    if entry.strip()
                ]

    if current_id:
        records.append(
            _build_task_record(
                current_id,
                issue_id,
                current_desc,
                current_mode,
                current_criteria,
            )
        )

    return records


def _build_task_record(
    task_id: str,
    issue_id: str,
    description: str | None,
    execution_mode: str,
    criteria_entries: list[str] | None = None,
) -> TaskRecord:
    links: list[CriterionLink] | None = None
    if criteria_entries:
        links = []
        for entry in criteria_entries:
            match = _LINK_PATTERN.match(entry)
            if match is None:
                raise ValueError(
                    f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
                )
            criterion_id, inner = match.group(1), match.group(2)
            parts = [p.strip() for p in inner.split(",")] if inner else []
            verification_mode = parts[0] if parts else ""
            test_ref = parts[1] if len(parts) > 1 and parts[1] else None
            links.append(
                CriterionLink(
                    criterion_id=criterion_id,
                    verification_mode=verification_mode,
                    test_ref=test_ref,
                )
            )
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description or "",
        status="PENDING",
        execution_mode=execution_mode,
        acceptance_criteria=links,
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
