from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


_VALID_PHASES = frozenset(
    {
        "IDLE",
        "EXPLORE",
        "RESEARCH",
        "PRD",
        "SHARD",
        "SPECIFY",
        "TASKS",
        "RED",
        "GREEN",
        "REFACTOR",
        "E2E",
    }
)


class DeviateConfig(BaseModel):
    profile: str = "default"
    llm_backend: str = "droid"
    timeout_seconds: int = Field(default=300, gt=0)
    agent_export_mode: Literal["local", "global"] = "local"

    model_config = {"extra": "forbid"}


class SessionState(BaseModel):
    current_phase: str = "IDLE"
    active_issue_id: Optional[str] = None
    last_command: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("current_phase")
    @classmethod
    def _validate_phase(cls, v: str) -> str:
        if v not in _VALID_PHASES:
            valid = ", ".join(sorted(_VALID_PHASES))
            raise ValueError(f"Invalid phase '{v}'. Must be one of: {valid}")
        return v
