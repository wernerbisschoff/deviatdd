import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from deviate.state.config import (
    AgentConfig,
    DeviateConfig,
    LogConfig,
    ProfileConfig,
    SessionState,
    resolve_agent_export_mode,
    resolve_agent_reasons,
    resolve_base_branch,
    resolve_claim_remote,
    resolve_execution_profile,
    resolve_phase_model,
    resolve_reasoning_effort,
)
from tests.conftest import _git_env


def _set_origin_head(repo: Path, branch: str) -> None:
    """Point ``refs/remotes/origin/HEAD`` at ``origin/<branch>``."""
    subprocess.run(
        [
            "git",
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            f"refs/remotes/origin/{branch}",
        ],
        cwd=repo,
        env=_git_env(),
        check=True,
    )


class TestDeviateConfig:
    def test_default_values(self):
        config = DeviateConfig()
        assert config.profile == "full"
        assert config.timeout_seconds == 1800
        assert config.agent_export_mode == "local"
        assert config.base_branch == "main"
        assert config.log.agent_reasons is False
        assert LogConfig().agent_reasons is False

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            DeviateConfig(unknown_field="value")

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValidationError):
            DeviateConfig(timeout_seconds=0)
        with pytest.raises(ValidationError):
            DeviateConfig(timeout_seconds=-1)

    def test_agent_export_mode_validation(self):
        with pytest.raises(ValidationError):
            DeviateConfig(agent_export_mode="invalid")

    def test_json_round_trip(self):
        config = DeviateConfig(
            profile="fast",
            timeout_seconds=60,
            agent_export_mode="global",
        )
        data = json.loads(config.model_dump_json())
        restored = DeviateConfig.model_validate(data)
        assert restored == config

    def test_model_config_defaults(self):
        config = DeviateConfig()
        assert config.models == {}

    def test_model_config_round_trip(self):
        config = DeviateConfig(
            models={"default": "fast/model", "judge": "premium/model"}
        )
        data = json.loads(config.model_dump_json())
        restored = DeviateConfig.model_validate(data)
        assert restored.models == {"default": "fast/model", "judge": "premium/model"}

    def test_model_config_phase_lookup(self):
        models = {"RED": "fast/model", "JUDGE": "premium/model"}
        assert resolve_phase_model("RED", models) == "fast/model"
        assert resolve_phase_model("PLAN", models) is None

    def test_model_config_default_fallback(self):
        models = {"default": "fast/model", "judge": "premium/model"}
        assert resolve_phase_model("RED", models) == "fast/model"

    def test_model_config_phase_overrides_default(self):
        models = {"default": "fast/model", "judge": "premium/model"}
        assert resolve_phase_model("judge", models) == "premium/model"

    def test_use_libref_default(self):
        config = DeviateConfig()
        assert config.use_libref is False

    def test_use_libref_round_trip(self):
        config = DeviateConfig(use_libref=True)
        data = json.loads(config.model_dump_json())
        restored = DeviateConfig.model_validate(data)
        assert restored.use_libref is True

    def test_config_base_branch_round_trip(self):
        config = DeviateConfig(base_branch="wb-dev")
        data = json.loads(config.model_dump_json())
        restored = DeviateConfig.model_validate(data)
        assert restored.base_branch == "wb-dev"

    def test_config_base_branch_empty_rejected(self):
        with pytest.raises(ValidationError):
            DeviateConfig(base_branch="")

    def test_resolve_base_branch_from_toml(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text(
            'base_branch = "wb-dev"\n', encoding="utf-8"
        )
        assert resolve_base_branch(tmp_path) == "wb-dev"

    def test_resolve_base_branch_config_trunk_wins(self, tmp_git_repo: Path) -> None:
        _set_origin_head(tmp_git_repo, "develop")
        dot_dir = tmp_git_repo / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text(
            'base_branch = "trunk"\n', encoding="utf-8"
        )
        assert resolve_base_branch(tmp_git_repo) == "trunk"

    def test_resolve_base_branch_from_origin_head_develop(
        self, tmp_git_repo: Path
    ) -> None:
        _set_origin_head(tmp_git_repo, "develop")
        assert resolve_base_branch(tmp_git_repo) == "develop"

    def test_resolve_base_branch_from_origin_head_master(
        self, tmp_git_repo: Path
    ) -> None:
        _set_origin_head(tmp_git_repo, "master")
        assert resolve_base_branch(tmp_git_repo) == "master"

    def test_resolve_base_branch_missing_origin_head_is_main(
        self, tmp_git_repo: Path
    ) -> None:
        assert resolve_base_branch(tmp_git_repo) == "main"

    def test_resolve_base_branch_default(self, tmp_path: Path) -> None:
        assert resolve_base_branch(tmp_path) == "main"

    def test_resolve_agent_export_mode_from_toml(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text(
            'agent_export_mode = "global"\n', encoding="utf-8"
        )
        assert resolve_agent_export_mode(tmp_path) == "global"

    def test_resolve_agent_export_mode_default(self, tmp_path: Path) -> None:
        assert resolve_agent_export_mode(tmp_path) == "local"

    def test_config_claim_remote_field_default(self) -> None:
        config = DeviateConfig()
        assert config.claim_remote is False

    def test_config_claim_remote_round_trip(self) -> None:
        true_config = DeviateConfig(claim_remote=True)
        dumped_true = true_config.model_dump()
        assert "claim_remote" in dumped_true
        assert dumped_true["claim_remote"] is True
        restored_true = DeviateConfig.model_validate(
            json.loads(true_config.model_dump_json())
        )
        assert restored_true.claim_remote is True

        false_config = DeviateConfig(claim_remote=False)
        dumped_false = false_config.model_dump()
        assert "claim_remote" in dumped_false
        assert dumped_false["claim_remote"] is False
        restored_false = DeviateConfig.model_validate(
            json.loads(false_config.model_dump_json())
        )
        assert restored_false.claim_remote is False

    def test_resolve_claim_remote_true(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text("claim_remote = true\n", encoding="utf-8")
        assert resolve_claim_remote(tmp_path) is True

    def test_resolve_claim_remote_false(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text("claim_remote = false\n", encoding="utf-8")
        assert resolve_claim_remote(tmp_path) is False

    def test_resolve_claim_remote_key_absent(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text('profile = "default"\n', encoding="utf-8")
        assert resolve_claim_remote(tmp_path) is False

    def test_resolve_claim_remote_no_file(self, tmp_path: Path) -> None:
        assert resolve_claim_remote(tmp_path) is False

    def test_resolve_claim_remote_non_bool(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text(
            'claim_remote = "false"\n', encoding="utf-8"
        )
        assert resolve_claim_remote(tmp_path) is False

    def test_resolve_agent_reasons_default_false(self, tmp_path: Path) -> None:
        assert resolve_agent_reasons(tmp_path) is False
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text('profile = "full"\n', encoding="utf-8")
        assert resolve_agent_reasons(tmp_path) is False

    def test_resolve_agent_reasons_true(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        (dot_dir / "config.toml").write_text(
            "[log]\nagent_reasons = true\n", encoding="utf-8"
        )
        assert resolve_agent_reasons(tmp_path) is True

    def test_profile_rejects_default_string(self):
        with pytest.raises(ValidationError):
            DeviateConfig(profile="default")

    def test_resolve_execution_profile_coerces_default(self, tmp_path: Path) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('profile = "default"\n', encoding="utf-8")
        assert resolve_execution_profile(tmp_path) == "full"

    def test_resolve_execution_profile_reads_fast(self, tmp_path: Path) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('profile = "fast"\n', encoding="utf-8")
        assert resolve_execution_profile(tmp_path) == "fast"

    def test_resolve_execution_profile_keeps_legacy_secure(
        self, tmp_path: Path
    ) -> None:
        from deviate.core.profile import resolve_profile

        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('profile = "secure"\n', encoding="utf-8")
        assert resolve_execution_profile(tmp_path) == "secure"
        assert resolve_profile(resolve_execution_profile(tmp_path)) == (False, True)

    def test_resolve_execution_profile_unknown_judge_coerces_to_full(
        self, tmp_path: Path
    ) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('profile = "judge"\n', encoding="utf-8")
        assert resolve_execution_profile(tmp_path) == "full"

    def test_resolve_execution_profile_missing_file(self, tmp_path: Path) -> None:
        assert resolve_execution_profile(tmp_path) == "full"


class TestConsolidatedTimeout:
    """AC-PLAN-005 / AC-PLAN-006 (ISS-ADH-030): the schema exposes exactly
    one timeout field and rejects a stale ``graphite`` key.
    """

    def test_consolidated_timeout_field(self):
        """One timeout field: ``DeviateConfig.timeout_seconds``. ``AgentConfig``
        no longer owns a ``timeout`` field (GH-87 field removal)."""
        config = DeviateConfig()
        assert config.timeout_seconds == 1800
        assert "timeout" not in AgentConfig.model_fields, (
            "AC-PLAN-005: AgentConfig must not expose a second timeout field"
        )
        assert not hasattr(DeviateConfig(agent=AgentConfig()).agent, "timeout"), (
            "AC-PLAN-005: AgentConfig must not expose a ``timeout`` attribute"
        )

    def test_parse_stale_graphite_key_rejected(self):
        """AC-PLAN-006: a literal ``graphite`` key is rejected by ``extra = "forbid"``."""
        with pytest.raises(ValidationError):
            DeviateConfig(graphite=True)
        with pytest.raises(ValidationError):
            DeviateConfig.model_validate({"graphite": True})


class TestProfileConfig:
    def test_default_values(self):
        config = ProfileConfig()
        assert config.default == "full"

    def test_forbids_extra_fields(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileConfig(default="full", unknown_field="value")

    def test_toml_roundtrip(self):
        import tomllib

        config = ProfileConfig(default="fast")
        toml_str = config.to_toml_string()
        parsed = tomllib.loads(toml_str)
        restored = ProfileConfig.model_validate(parsed)
        assert restored == config

    def test_rejects_invalid_profile(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProfileConfig(default="invalid")


class TestSessionState:
    def test_default_values(self):
        session = SessionState()
        assert session.current_phase == "IDLE"
        assert session.active_issue_id is None
        assert session.last_command == ""
        assert session.timestamp is not None
        assert session.green_attempts == 0
        assert session.red_attempts == 0

    def test_valid_phases_accepted(self):
        for phase in [
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
            "REFACTOR",
            "E2E",
        ]:
            session = SessionState(current_phase=phase)
            assert session.current_phase == phase

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValidationError) as exc:
            SessionState(current_phase="INVALID")
        assert "Invalid phase" in str(exc.value)

    def test_none_active_issue_id_serialization(self):
        session = SessionState()
        data = json.loads(session.model_dump_json())
        assert data["active_issue_id"] is None

    def test_json_round_trip(self):
        session = SessionState(
            current_phase="GREEN",
            active_issue_id="ISS-042",
            last_command="pytest tests/",
        )
        data = json.loads(session.model_dump_json())
        restored = SessionState.model_validate(data)
        assert restored == session

    def test_pending_judge_feedback_round_trip(self):
        session = SessionState(
            current_phase="JUDGE",
            active_issue_id="ISS-002",
            pending_judge_feedback={
                "task_id": "TSK-002-05",
                "feedback": "Create the missing Credo check.",
                "feedback_source": "train_feedback",
            },
        )

        restored = SessionState.model_validate_json(session.model_dump_json())

        assert restored.pending_judge_feedback == session.pending_judge_feedback

    def test_transition_idle_to_specify_is_allowed(self):
        session = SessionState(current_phase="IDLE")
        result = session.transition_to("SPECIFY")
        assert result.current_phase == "SPECIFY"

    def test_transition_specify_to_tasks(self):
        session = SessionState(current_phase="SPECIFY")
        result = session.transition_to("TASKS")
        assert result.current_phase == "TASKS"

    def test_transition_specify_to_plan(self):
        session = SessionState(current_phase="SPECIFY")
        result = session.transition_to("PLAN")
        assert result.current_phase == "PLAN"

    def test_transition_plan_to_tasks(self):
        session = SessionState(current_phase="PLAN")
        result = session.transition_to("TASKS")
        assert result.current_phase == "TASKS"

    def test_transition_tasks_to_idle(self):
        session = SessionState(current_phase="TASKS")
        result = session.transition_to("IDLE")
        assert result.current_phase == "IDLE"

    def test_transition_shard_to_specify(self):
        session = SessionState(current_phase="SHARD")
        result = session.transition_to("SPECIFY")
        assert result.current_phase == "SPECIFY"

    def test_transition_idle_to_explore_still_works(self):
        session = SessionState(current_phase="IDLE")
        result = session.transition_to("EXPLORE")
        assert result.current_phase == "EXPLORE"

    def test_transition_specify_to_shard_is_allowed(self):
        session = SessionState(current_phase="SPECIFY")
        result = session.transition_to("SHARD")
        assert result.current_phase == "SHARD"

    def test_json_round_trip_persists_retry_counters(self, tmp_path: Path) -> None:
        session_path = tmp_path / ".deviate" / "session.json"
        original = SessionState(green_attempts=2, red_attempts=1)
        original.save(session_path)

        loaded = SessionState.load(session_path)
        assert loaded.green_attempts == 2
        assert loaded.red_attempts == 1

    def test_missing_counter_keys_load_as_zero(self, tmp_path: Path) -> None:
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True)
        session_path.write_text(
            json.dumps(
                {
                    "current_phase": "GREEN",
                    "active_issue_id": "ISS-ADH-017",
                }
            ),
            encoding="utf-8",
        )

        loaded = SessionState.load(session_path)
        assert loaded.green_attempts == 0
        assert loaded.red_attempts == 0
        assert loaded.green_attempts is not None
        assert loaded.red_attempts is not None

    def test_transition_to_copies_retry_counters(self) -> None:
        session = SessionState(
            current_phase="GREEN",
            green_attempts=2,
            red_attempts=1,
        )
        result = session.transition_to("JUDGE")
        assert result.green_attempts == 2
        assert result.red_attempts == 1
        assert result.current_phase == "JUDGE"

    def test_force_transition_to_copies_retry_counters(self) -> None:
        session = SessionState(
            current_phase="GREEN",
            green_attempts=3,
            red_attempts=2,
        )
        result = session.force_transition_to("JUDGE")
        assert result.green_attempts == 3
        assert result.red_attempts == 2
        assert result.current_phase == "JUDGE"

    def test_missing_session_file_loads_zero_counters(self, tmp_path: Path) -> None:
        loaded = SessionState.load(tmp_path / ".deviate" / "session.json")
        assert loaded.green_attempts == 0
        assert loaded.red_attempts == 0


class TestResolveReasoningEffort:
    def test_missing_config_returns_none(self, tmp_path: Path) -> None:
        assert resolve_reasoning_effort(tmp_path) is None

    def test_reads_agent_reasoning_effort(self, tmp_path: Path) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text(
            '[agent]\nbackend = "codex"\nreasoning_effort = "high"\n',
            encoding="utf-8",
        )
        assert resolve_reasoning_effort(tmp_path) == "high"

    def test_empty_reasoning_effort_returns_none(self, tmp_path: Path) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text(
            '[agent]\nbackend = "codex"\nreasoning_effort = ""\n',
            encoding="utf-8",
        )
        assert resolve_reasoning_effort(tmp_path) is None
