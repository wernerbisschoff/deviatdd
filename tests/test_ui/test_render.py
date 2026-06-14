from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from deviate.ui.render import (
    emit_jsonl,
    is_interactive,
)


class TestJsonlFallback:
    @patch.object(sys.stdout, "isatty", return_value=False)
    def test_render_no_tty_fallback(
        self, mock_isatty: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_jsonl("task_started", task_id="TSK-001", phase="RED")
        captured = capsys.readouterr()
        assert captured.out.strip() != ""

    @patch.object(sys.stdout, "isatty", return_value=False)
    def test_render_jsonl_event_fields(
        self, mock_isatty: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_jsonl("agent_output", task_id="T1", phase="RED", line="test line")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert "event" in parsed
        assert "task_id" in parsed
        assert "phase" in parsed
        assert "line" in parsed
        assert "timestamp" in parsed

    @patch.object(sys.stdout, "isatty", return_value=False)
    def test_render_jsonl_agent_output_event(
        self, mock_isatty: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_jsonl("agent_output", task_id="T1", phase="RED", line="Running tests...")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event"] == "agent_output"
        assert parsed["task_id"] == "T1"
        assert parsed["phase"] == "RED"
        assert parsed["line"] == "Running tests..."
        assert "timestamp" in parsed


class TestIsInteractive:
    def test_is_interactive_returns_bool(self) -> None:
        result = is_interactive()
        assert isinstance(result, bool)
