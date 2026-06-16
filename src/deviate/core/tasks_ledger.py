from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from deviate.state.ledger import TaskRecord


_TASK_LINE_PATTERN = re.compile(r"^- (TSK-\d{3}-\d{2}): (.+)")
_MODE_PATTERN = re.compile(r"\*\*Mode\*\*:\s*(\S+)")


def generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[TaskRecord]:
    content = tasks_md.read_text(encoding="utf-8")
    records: list[TaskRecord] = []
    current_id: str | None = None
    current_desc: str | None = None
    current_mode: str = "TDD"

    for line in content.splitlines():
        task_match = _TASK_LINE_PATTERN.match(line)
        if task_match:
            if current_id:
                records.append(
                    _build_task_record(current_id, issue_id, current_desc, current_mode)
                )
            current_id = task_match.group(1)
            current_desc = task_match.group(2).strip()
            current_mode = "TDD"
        elif current_id:
            mode_match = _MODE_PATTERN.search(line)
            if mode_match:
                current_mode = mode_match.group(1)

    if current_id:
        records.append(
            _build_task_record(current_id, issue_id, current_desc, current_mode)
        )

    return records


def _build_task_record(
    task_id: str,
    issue_id: str,
    description: str | None,
    execution_mode: str,
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description or "",
        status="PENDING",
        execution_mode=execution_mode,
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
