from __future__ import annotations

import json
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
    status: Literal["PENDING", "RED", "GREEN", "REFACTOR", "COMPLETED"] = "PENDING"
    execution_mode: Literal["TDD", "DIRECT", "E2E"] = "TDD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def _validate_uuid4(cls, v: str) -> str:
        try:
            uuid.UUID(v, version=4)
        except ValueError:
            raise ValueError(f"Invalid UUID4: {v}")
        return v


def append_task_record(record: TaskRecord, ledger_path: Path) -> bool:
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
                    if data.get("id") == record.id:
                        return False
                except json.JSONDecodeError:
                    continue
            f.write(record.model_dump_json() + "\n")
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return True


def resolve_issue_record(issue_id: str, ledger_path: Path) -> IssueRecord | None:
    records = _read_ledger(ledger_path)
    for data in reversed(records):
        if data.get("issue_id") == issue_id:
            return IssueRecord.model_validate(data)
    return None


def append_issue_record(record: IssueRecord, ledger_path: Path) -> bool:
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
                    if data.get("issue_id") == record.issue_id:
                        return False
                except json.JSONDecodeError:
                    continue
            f.write(record.model_dump_json() + "\n")
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return True
