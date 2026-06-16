import json

import pytest
from pydantic import ValidationError

from deviate.state.config import (
    DeviateConfig,
    ProfileConfig,
    SessionState,
)


class TestDeviateConfig:
    def test_default_values(self):
        config = DeviateConfig()
        assert config.profile == "default"
        assert config.llm_backend == "droid"
        assert config.timeout_seconds == 300
        assert config.agent_export_mode == "local"

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
            profile="test",
            llm_backend="claude",
            timeout_seconds=60,
            agent_export_mode="global",
        )
        data = json.loads(config.model_dump_json())
        restored = DeviateConfig.model_validate(data)
        assert restored == config


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
