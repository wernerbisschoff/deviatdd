from __future__ import annotations

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentConfig(BaseModel):
    # Agent backend: "opencode", "claude", "droid", or "pi"
    backend: Literal["opencode", "claude", "droid", "pi"] = "opencode"
    # Agent invocation timeout in seconds (must be > 0)
    timeout: int = Field(default=600, gt=0)
    # Opt-in RPC mode for Pi — spawns `pi --mode rpc --no-session` instead of `pi -p`
    pi_rpc: bool = Field(
        default=False,
        description="Opt-in RPC mode for Pi (spawns pi --mode rpc --no-session instead of pi -p)",
    )

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
    # Profile name — defines preset config groups (default, full, fast, secure)
    profile: str = "default"
    # CLI inactivity timeout in seconds (must be > 0)
    timeout_seconds: int = Field(default=300, gt=0)
    # Agent export mode: "local" (project .claude/) or "global" (~/.claude/)
    agent_export_mode: Literal["local", "global"] = "local"
    # Agent backend config (opencode, claude, or droid)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    # Per-phase model overrides, e.g. default = "opencode/deepseek-v4-flash"
    models: dict[str, str] = Field(default_factory=dict)
    # Enable the libref CLI for offline documentation lookups
    use_libref: bool = False
    # Enable Graphite CLI integration for stacked changes
    graphite: bool = Field(default=False)

    model_config = {"extra": "forbid"}


def _load_deviate_config_toml(root: Path) -> dict | None:
    """Load the `.deviate/config.toml` file, returning a dict or None."""
    config_path = root / ".deviate" / "config.toml"
    if not config_path.exists():
        return None
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def resolve_phase_model(phase: str, models: dict[str, str]) -> str | None:
    """Resolve the model ID for *phase* from a `[models]` dict.

    Resolution order (case-insensitive):
        1. Phase-specific key (e.g. ``judge``, ``plan``, ``red``)
        2. ``default`` key
        3. ``None`` — backend falls back to its native default
    """
    if not models:
        return None
    phase_lower = phase.lower()
    lookup = {k.lower(): val for k, val in models.items() if val}
    if phase_lower in lookup:
        return lookup[phase_lower]
    if "default" in lookup:
        return lookup["default"]
    return None


def resolve_model_for_phase(phase: str, root: Path) -> str | None:
    """Load `[models]` from `.deviate/config.toml` and resolve *phase*.

    Backed by :func:`resolve_phase_model`. ``opencode`` and ``droid``
    backends accept ``--model <id>``; the ``claude`` backend ignores the
    resolved value silently.
    """
    data = _load_deviate_config_toml(root)
    if data is None:
        return None
    models = data.get("models", {})
    if not isinstance(models, dict):
        return None
    return resolve_phase_model(phase, {k: str(v) for k, v in models.items()})


def resolve_graphite_config(root: Path) -> bool:
    """Check whether the Graphite integration is enabled in `.deviate/config.toml`."""
    data = _load_deviate_config_toml(root)
    if data is None:
        return False
    value = data.get("graphite", False)
    return value if isinstance(value, bool) else False


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
    train_feedback: str = ""
    judge_rejected: bool = False
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
            red_commit_sha=self.red_commit_sha,
            timestamp=datetime.now(timezone.utc),
        )

    def force_transition_to(self, phase: str) -> SessionState:
        return SessionState(
            current_phase=phase,
            active_issue_id=self.active_issue_id,
            last_command=self.last_command,
            red_commit_sha=self.red_commit_sha,
            train_feedback=self.train_feedback,
            judge_rejected=self.judge_rejected,
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
