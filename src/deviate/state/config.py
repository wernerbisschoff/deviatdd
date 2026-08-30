from __future__ import annotations

import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from deviate.core.profile import canonicalize_profile

CODEX_DEFAULT_MODEL = "gpt-5.6-luna"
CODEX_DEFAULT_REASONING_EFFORT = "high"
ReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh"]


class AgentConfig(BaseModel):
    # Agent backend: "opencode", "claude", "droid", "pi", "omp", or "codex"
    backend: Literal["opencode", "claude", "droid", "pi", "omp", "codex"] = "pi"
    # Agent-process and test-command deadlines resolve from the single
    # consolidated DeviateConfig.timeout_seconds via resolve_agent_deadline().
    # Opt-in RPC mode for Pi — spawns `pi --mode rpc --no-session` instead of `pi -p`
    pi_rpc: bool = Field(
        default=False,
        description="Opt-in RPC mode for Pi (spawns pi --mode rpc --no-session instead of pi -p)",
    )

    # Transport mode: "rpc" (JSON-RPC over stdio) or "cli" (legacy subprocess)
    # Defaults to "rpc" for Pi and OMP, "cli" for other backends
    transport: Literal["rpc", "cli"] = Field(default="cli")
    # Optional RPC URI override (e.g., "stdio://pi --mode rpc --no-session")
    rpc_uri: Optional[str] = Field(default=None)
    # Codex-only: forwarded as ``codex exec -c model_reasoning_effort=<value>``.
    # Official values are minimal|low|medium|high|xhigh. Other backends ignore it.
    reasoning_effort: Optional[ReasoningEffort] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _normalize_transport(cls, data: dict[str, object]) -> dict[str, object]:
        """Normalize transport field: set default based on backend if not specified.

        If `transport` is not set and `pi_rpc` is True, upgrade to RPC mode.
        """
        if isinstance(data, dict):
            # Migrate legacy pi_rpc flag
            pi_rpc = data.get("pi_rpc")
            if pi_rpc is True:
                data["transport"] = "rpc"
            # Set default transport based on backend if not specified
            if "transport" not in data:
                backend = data.get("backend", "pi")
                if backend in ("pi", "omp"):
                    data["transport"] = "rpc"
                else:
                    data["transport"] = "cli"
        return data

    @field_validator("reasoning_effort", mode="before")
    @classmethod
    def _empty_reasoning_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Transport resolution helpers for C5 backend substitution
# ---------------------------------------------------------------------------


def resolve_transport(models: dict[str, object]) -> Literal["rpc", "cli"]:
    """Resolve the transport mode from a [models] dict.

    Returns "rpc" by default (the default for Pi and OMP backends).
    """
    raw = models.get("transport")
    if isinstance(raw, str) and raw in frozenset({"rpc", "cli"}):
        return raw  # type: ignore[return-value]
    if raw is not None:
        raise ValueError(f"transport must be one of ('rpc', 'cli'), got {raw!r}")
    # Default is "rpc" when not specified
    return "rpc"


def resolve_legacy_cli_fallback(models: dict[str, object]) -> bool:
    """Resolve the legacy_cli_fallback flag from a [models] dict.

    Returns True by default (preserves existing subprocess path for non-RPC backends).
    """
    raw = models.get("legacy_cli_fallback")
    if isinstance(raw, bool):
        return raw
    # Default is True when not specified
    return True


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
    # Micro-run default when ``deviate micro run --profile`` is omitted.
    # Must be a real execution profile — never the unused string "default".
    profile: Literal["full", "fast"] = "full"
    # Default 1800s accommodates legitimate long-running test commands
    # (e.g. Rust workspace `cargo test` first builds); the orchestrator
    # still enforces a hard deadline via SIGTERM/SIGKILL on the process
    # group, so this is a ceiling, not a sleep.
    timeout_seconds: int = Field(default=1800, gt=0)
    # Agent export mode: "local" (project .claude/) or "global" (~/.claude/)
    agent_export_mode: Literal["local", "global"] = "local"
    # Agent backend config (opencode, claude, droid, pi, omp, or codex)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    # Per-phase model overrides, e.g. default = "opencode/deepseek-v4-flash"
    models: dict[str, str] = Field(default_factory=dict)
    # Enable the libref CLI for offline documentation lookups
    use_libref: bool = False
    # Git branch used as trunk for worktrees, PR base, and review diffs
    base_branch: str = Field(default="main", min_length=1)
    # Push the claim branch as a distributed lock (opt-in)
    claim_remote: bool = Field(default=False)

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


def resolve_reasoning_effort(root: Path) -> str | None:
    """Return ``[agent].reasoning_effort`` from `.deviate/config.toml`.

    Returns ``None`` when the file, table, or key is absent, or when the
    value is not a non-empty string. Callers construct
    :class:`AgentConfig` which validates the official Codex set
    (``minimal|low|medium|high|xhigh``).
    """
    data = _load_deviate_config_toml(root)
    if not isinstance(data, dict):
        return None
    agent = data.get("agent", {})
    if not isinstance(agent, dict):
        return None
    raw = agent.get("reasoning_effort")
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


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


def _resolve_toml_bool(root: Path, key: str, default: bool) -> bool:
    """Return a top-level bool from `.deviate/config.toml`.

    Returns *default* when the file is absent, the key is absent, or the
    value is not a bool.
    """
    data = _load_deviate_config_toml(root)
    if data is None:
        return default
    value = data.get(key, default)
    return value if isinstance(value, bool) else default


def resolve_agent_deadline(root: Path) -> int:
    """Return the agent wall-clock deadline for *root*.

    Reads ``timeout_seconds`` from ``.deviate/config.toml``; falls back
    to ``DeviateConfig.timeout_seconds`` (the single consolidation site,
    AC-PLAN-005) when the file or key is absent or the value is not a
    positive int.
    """
    data = _load_deviate_config_toml(root)
    if isinstance(data, dict):
        config_value = data.get("timeout_seconds")
        if isinstance(config_value, int) and config_value > 0:
            return config_value
    return DeviateConfig().timeout_seconds


def resolve_claim_remote(root: Path) -> bool:
    """Resolve whether claim should push a lock branch to the remote.

    Returns False when the config file is absent, the key is absent, or the
    value is not a bool. Existing ``claim_remote = true`` configs still push.
    """
    return _resolve_toml_bool(root, "claim_remote", False)


def resolve_execution_profile(root: Path) -> str:
    """Return the micro-run profile from ``.deviate/config.toml``.

    Missing, empty, ``"default"``, or any value outside
    ``full`` / ``fast`` coerces to ``full``.
    Legacy ``"secure"`` is kept as an internal alias (JUDGE on, REFACTOR off).
    """
    data = _load_deviate_config_toml(root)
    if data is None:
        return "full"
    value = data.get("profile", "full")
    if isinstance(value, str):
        name = canonicalize_profile(value.strip())
        if name in {"full", "fast", "secure"}:
            return name
    return "full"


def _remote_default_branch(root: Path) -> str | None:
    """Return ``origin/HEAD``'s branch name, or ``None`` if it is unset.

    Uses ``git symbolic-ref --quiet --short refs/remotes/origin/HEAD``
    (the remote default), not the current branch's ``@{upstream}``.
    """
    from deviate.core._shared import git_env

    try:
        result = subprocess.run(
            [
                "git",
                "symbolic-ref",
                "--quiet",
                "--short",
                "refs/remotes/origin/HEAD",
            ],
            cwd=root,
            env=git_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    if name.startswith("origin/"):
        name = name.removeprefix("origin/")
    return name or None


def resolve_base_branch(root: Path) -> str:
    """Return the trunk branch for worktrees, PRs, and review diffs.

    Order: hand-set ``base_branch`` in ``.deviate/config.toml``, then
    ``origin/HEAD``, then ``main``.
    """
    data = _load_deviate_config_toml(root)
    if isinstance(data, dict):
        value = data.get("base_branch")
        if isinstance(value, str) and value.strip():
            return value.strip()
    remote = _remote_default_branch(root)
    if remote:
        return remote
    return "main"


def resolve_agent_export_mode(root: Path) -> Literal["local", "global"]:
    """Return the prompt/skill install mode, defaulting to ``local``."""
    data = _load_deviate_config_toml(root)
    if data is None:
        return "local"
    value = data.get("agent_export_mode", "local")
    if value in ("local", "global"):
        return value
    return "local"


class PytestReportConfig(BaseModel):
    json_report: bool = False

    model_config = {"extra": "forbid"}


class ProfileConfig(BaseModel):
    default: Literal["full", "fast"] = "full"

    model_config = {"extra": "forbid"}

    def to_toml_string(self) -> str:
        return 'default = "{}"\n'.format(self.default)


class SessionState(BaseModel):
    current_phase: str = "IDLE"
    active_issue_id: Optional[str] = None
    last_command: str = ""
    train_feedback: str = ""
    green_attempts: int = 0
    red_attempts: int = 0
    failure_kind: Literal["", "mechanical", "test_defect", "no_failing_test"] = ""
    judge_rejected: bool = False
    pending_judge_action: str = ""
    red_commit_sha: str = ""
    pending_judge_feedback: Optional[dict[str, str]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Verdict of the most recent JUDGE phase. Used for diagnostics and for
    # no_failing_test / mechanical forward-route handling. A COMPLIANCE_PASS
    # after GREEN TEST_FAILURE does not complete the slice — the runner
    # remaps that pass to TRAIN with the test dump. Empty = no judge has
    # weighed in yet.
    last_judge_verdict: str = ""
    # Path of the ``specs/explore/<slug>.md`` source file that
    # ``deviate research pre`` moved into the numbered epic dir. Populated
    # by ``research_pre`` so ``research_post`` can ``git rm`` it inside
    # the same atomic commit that adds the moved ``explore.md`` into the
    # epic dir. The default ``""`` keeps pre-fix ``.deviate/session.json``
    # files compatible — ``research_post`` skips the deletion when this
    # field is empty (the manual-escape-hatch path where research_pre
    # never ran).
    research_explore_source: str = ""
    # Transient carrier for runner-validated JUDGE citations until the
    # COMPLETED ledger row is written. Not the proof store (GH-84).
    validated_evidence: list[dict] = Field(default_factory=list)

    @field_validator("current_phase")
    @classmethod
    def _validate_phase(cls, v: str) -> str:
        if v not in _VALID_PHASES:
            valid = ", ".join(sorted(_VALID_PHASES))
            raise ValueError(f"Invalid phase '{v}'. Must be one of: {valid}")
        return v

    def _copy_with_phase(self, phase: str) -> SessionState:
        data = self.model_dump()
        data["current_phase"] = phase
        data["timestamp"] = datetime.now(timezone.utc)
        return type(self).model_validate(data)

    def transition_to(self, phase: str) -> SessionState:
        return self._copy_with_phase(phase)

    def force_transition_to(self, phase: str) -> SessionState:
        return self._copy_with_phase(phase)

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
