from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
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

_TRANSITION_MAP: dict[str, tuple[str, ...]] = {
    "IDLE": ("EXPLORE", "SPECIFY"),
    "EXPLORE": ("RESEARCH",),
    "RESEARCH": ("PRD",),
    "PRD": ("SHARD",),
    "SHARD": ("IDLE",),
    "SPECIFY": ("TASKS",),
    "TASKS": ("IDLE",),
}


def _find_source_for(target: str) -> str | None:
    for source, targets in _TRANSITION_MAP.items():
        if target in targets:
            return source
    return None


class TransitionViolationError(Exception):
    pass


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

    def transition_to(self, phase: str) -> SessionState:
        expected_next: tuple[str, ...] | None = _TRANSITION_MAP.get(self.current_phase)
        if expected_next is None or phase not in expected_next:
            expected_current = _find_source_for(phase)
            raise TransitionViolationError(
                f"cannot transition from '{self.current_phase}' to '{phase}': "
                f"expected '{expected_current}' -> '{phase}', "
                f"current '{self.current_phase}' -> '{expected_next}'"
            )
        return SessionState(
            current_phase=phase,
            active_issue_id=self.active_issue_id,
            last_command=self.last_command,
            timestamp=datetime.now(timezone.utc),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SessionState:
        if not path.exists():
            return cls()
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls.model_validate(data)
