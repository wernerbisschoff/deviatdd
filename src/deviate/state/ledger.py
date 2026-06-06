from __future__ import annotations

import json
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IssueRecord(BaseModel):
    id: str
    title: str = Field(min_length=1)
    status: Literal["SHARDED"]
    epic_slug: str
    issue_slug: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id")
    @classmethod
    def _validate_uuid4(cls, v: str) -> str:
        try:
            uuid.UUID(v, version=4)
        except ValueError:
            raise ValueError(f"Invalid UUID4: {v}")
        return v


def _read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                warnings.warn(f"Skipping malformed JSONL line in {path}", stacklevel=2)
                continue
    return records


def append_issue_record(record: IssueRecord, ledger_path: Path) -> bool:
    records = _read_ledger(ledger_path)
    existing_slugs = {r.get("issue_slug") for r in records if "issue_slug" in r}
    if record.issue_slug in existing_slugs:
        return False
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")
    return True
