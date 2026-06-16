from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentConfig(BaseModel):
    backend: Literal["opencode", "claude", "droid"] = "opencode"
    timeout: int = Field(default=600, gt=0)

    model_config = {"extra": "forbid"}


_VALID_PHASES = frozenset(
    {
        "IDLE",
        "EXPLORE",
        "RESEARCH",
        "PRD",
        "SHARD",
        "SPECIFY",
        "PLAN",
        "TASKS",
        "RED",
        "GREEN",
        "YELLOW",
        "JUDGE",
        "REFACTOR",
        "E2E",
        "EXECUTE",
        "HOTFIX",
    }
)

_PHASE_ARTIFACT_MAP: dict[str, tuple[str, ...]] = {
    "RESEARCH": ("explore.md",),
    "PRD": ("design.md", "data-model.md"),
    "SHARD": ("prd.md",),
    "SPECIFY": ("spec.md",),
    "PLAN": ("plan.md",),
    "TASKS": ("spec.md", "tasks.md"),
}


class TransitionViolationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Module-level utility functions (extracted from SessionState static methods)
# ---------------------------------------------------------------------------


def validate_filesystem_state(
    phase: str,
    epic_slug: str | None,
    repo_path: Path,
) -> list[str]:
    expected_artifacts = _PHASE_ARTIFACT_MAP.get(phase, ())
    missing: list[str] = []
    for artifact in expected_artifacts:
        artifact_path = (
            repo_path / "specs" / epic_slug / artifact
            if epic_slug
            else repo_path / artifact
        )
        if not artifact_path.exists():
            missing.append(artifact)
    return missing


def reconstruct_from_worktree(worktree: Path) -> SessionState:
    has_spec = (worktree / "spec.md").exists()
    has_plan = (worktree / "plan.md").exists()
    has_tasks = (worktree / "tasks.md").exists()
    if has_plan and has_tasks:
        phase = "TASKS"
    elif has_plan:
        phase = "PLAN"
    elif has_spec and has_tasks:
        phase = "TASKS"
    elif has_spec:
        phase = "SPECIFY"
    else:
        phase = "IDLE"
    return SessionState(current_phase=phase)


def normalize_task_id(ref: str) -> str:
    return ref.rstrip(":")


class DeviateConfig(BaseModel):
    profile: str = "default"
    llm_backend: str = "droid"
    timeout_seconds: int = Field(default=300, gt=0)
    agent_export_mode: Literal["local", "global"] = "local"
    agent: AgentConfig = Field(default_factory=AgentConfig)

    model_config = {"extra": "forbid"}


class PytestReportConfig(BaseModel):
    json_report: bool = False

    model_config = {"extra": "forbid"}


class ProfileConfig(BaseModel):
    default: Literal["full", "fast", "secure"] = "full"

    model_config = {"extra": "forbid"}

    def to_toml_string(self) -> str:
        return 'default = "{}"\n'.format(self.default)


class SessionState(BaseModel):
    current_phase: str = "IDLE"
    active_issue_id: Optional[str] = None
    last_command: str = ""
    yellow_triggered: bool = False
    train_feedback: str = ""
    red_commit_sha: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("current_phase")
    @classmethod
    def _validate_phase(cls, v: str) -> str:
        if v not in _VALID_PHASES:
            valid = ", ".join(sorted(_VALID_PHASES))
            raise ValueError(f"Invalid phase '{v}'. Must be one of: {valid}")
        return v

    def transition_to(self, phase: str) -> SessionState:
        return SessionState(
            current_phase=phase,
            active_issue_id=self.active_issue_id,
            last_command=self.last_command,
            yellow_triggered=self.yellow_triggered,
            red_commit_sha=self.red_commit_sha,
            timestamp=datetime.now(timezone.utc),
        )

    def force_transition_to(self, phase: str) -> SessionState:
        return SessionState(
            current_phase=phase,
            active_issue_id=self.active_issue_id,
            last_command=self.last_command,
            yellow_triggered=self.yellow_triggered,
            red_commit_sha=self.red_commit_sha,
            train_feedback=self.train_feedback,
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

    @staticmethod
    def validate_filesystem_state(
        phase: str,
        epic_slug: str | None,
        repo_path: Path,
    ) -> list[str]:
        return validate_filesystem_state(phase, epic_slug, repo_path)

    @staticmethod
    def reconstruct_from_worktree(worktree: Path) -> SessionState:
        return reconstruct_from_worktree(worktree)

    @staticmethod
    def normalize_task_id(ref: str) -> str:
        return normalize_task_id(ref)
