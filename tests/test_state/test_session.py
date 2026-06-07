from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from deviate.state.config import SessionState


class TestValidTransitions:
    def test_valid_explore_from_idle(self):
        session = SessionState(current_phase="IDLE")
        result = session.transition_to("EXPLORE")
        assert result.current_phase == "EXPLORE"
        assert result.timestamp is not None

    def test_valid_research_from_explore(self):
        session = SessionState(current_phase="EXPLORE")
        result = session.transition_to("RESEARCH")
        assert result.current_phase == "RESEARCH"

    def test_valid_prd_from_research(self):
        session = SessionState(current_phase="RESEARCH")
        result = session.transition_to("PRD")
        assert result.current_phase == "PRD"

    def test_valid_shard_from_prd(self):
        session = SessionState(current_phase="PRD")
        result = session.transition_to("SHARD")
        assert result.current_phase == "SHARD"

    def test_shard_resets_to_idle(self):
        session = SessionState(current_phase="SHARD")
        result = session.transition_to("IDLE")
        assert result.current_phase == "IDLE"


class TestTransitionViolations:
    def test_transition_violation_skip_phase(self):
        from deviate.state.config import TransitionViolationError

        session = SessionState(current_phase="IDLE")
        with pytest.raises(TransitionViolationError) as exc_info:
            session.transition_to("PRD")
        msg = str(exc_info.value)
        assert "EXPLORE" in msg
        assert "IDLE" in msg

    def test_transition_violation_duplicate(self):
        from deviate.state.config import TransitionViolationError

        session = SessionState(current_phase="EXPLORE")
        with pytest.raises(TransitionViolationError) as exc_info:
            session.transition_to("EXPLORE")
        msg = str(exc_info.value)
        assert "IDLE" in msg
        assert "EXPLORE" in msg

    def test_transition_violation_backwards(self):
        from deviate.state.config import TransitionViolationError

        session = SessionState(current_phase="PRD")
        with pytest.raises(TransitionViolationError) as exc_info:
            session.transition_to("RESEARCH")
        msg = str(exc_info.value)
        assert "SHARD" in msg
        assert "PRD" in msg


class TestSessionPersistence:
    def test_session_persistence(self, tmp_path: Path):
        session_path = tmp_path / ".deviate" / "session.json"
        original = SessionState(
            current_phase="EXPLORE",
            active_issue_id="iss-001",
            last_command="explore",
        )
        original.save(session_path)

        assert session_path.exists()
        loaded = SessionState.load(session_path)
        assert loaded.current_phase == original.current_phase
        assert loaded.active_issue_id == original.active_issue_id
        assert loaded.last_command == original.last_command

    def test_session_persistence_missing_dir(self, tmp_path: Path):
        session_path = tmp_path / "nonexistent" / "session.json"
        session = SessionState(current_phase="IDLE")
        session.save(session_path)

        assert session_path.exists()
        loaded = SessionState.load(session_path)
        assert loaded.current_phase == "IDLE"

    def test_session_persistence_all_fields(self, tmp_path: Path):
        session_path = tmp_path / "session.json"
        expected_timestamp = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        original = SessionState(
            current_phase="RESEARCH",
            active_issue_id="iss-002",
            last_command="research",
            timestamp=expected_timestamp,
        )
        original.save(session_path)

        raw = json.loads(session_path.read_text(encoding="utf-8"))
        assert raw["current_phase"] == "RESEARCH"
        assert raw["active_issue_id"] == "iss-002"
        assert raw["last_command"] == "research"
        assert "timestamp" in raw

    def test_session_load_missing_file_returns_default(self, tmp_path: Path):
        session_path = tmp_path / ".deviate" / "session.json"
        assert not session_path.exists()

        loaded = SessionState.load(session_path)
        assert loaded.current_phase == "IDLE"
        assert loaded.active_issue_id is None

    def test_session_load_corrupted_file_raises_error(self, tmp_path: Path):
        session_path = tmp_path / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text("not valid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            SessionState.load(session_path)

    def test_transition_returns_new_instance(self):
        session = SessionState(current_phase="IDLE")
        result = session.transition_to("EXPLORE")
        assert result is not session
        assert session.current_phase == "IDLE"

    def test_transition_updates_timestamp(self):
        session = SessionState(current_phase="IDLE")
        before = session.timestamp
        result = session.transition_to("EXPLORE")
        assert result.timestamp >= before
