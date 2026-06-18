from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deviate.core.agent import AgentBackend, AgentConfig, AgentSubprocessError


class TestAgentCommandModel:
    """AgentBackend.invoke() constructs the correct command for each backend.

    The model parameter injects ``--model <id>`` into the subprocess command
    for opencode and droid backends, but is silently ignored for claude.
    """

    @patch("deviate.core.agent.subprocess.Popen")
    def test_command_with_model(self, mock_popen: MagicMock) -> None:
        """AC-ADHOC-005-01: Default model applies — command includes --model."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"phase: RED\nstatus: PASS\n",
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend()
        backend.invoke("test prompt", model="opencode/deepseek-v4-flash")

        cmd = mock_popen.call_args[0][0]
        assert "--model" in cmd, f"Expected --model in command, got {cmd}"
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "opencode/deepseek-v4-flash"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_command_without_model(self, mock_popen: MagicMock) -> None:
        """AC-ADHOC-005-03: No model → no --model flag."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"phase: RED\nstatus: PASS\n",
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend()
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert "--model" not in cmd, f"Unexpected --model in command: {cmd}"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_command_droid_backend(self, mock_popen: MagicMock) -> None:
        """AC-ADHOC-005-04: Droid backend uses --model flag."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"phase: RED\nstatus: PASS\n",
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend(config=AgentConfig(backend="droid"))
        backend.invoke("test prompt", model="deepseek-v4-pro")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "droid"
        assert cmd[1] == "exec"
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "deepseek-v4-pro"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_command_claude_backend(self, mock_popen: MagicMock) -> None:
        """AC-ADHOC-005-05: Claude backend ignores model config."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"phase: RED\nstatus: PASS\n",
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend(config=AgentConfig(backend="claude"))
        backend.invoke("test prompt", model="fast/model")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"
        assert "--model" not in cmd

    @patch("deviate.core.agent.subprocess.Popen")
    def test_command_with_invalid_model(self, mock_popen: MagicMock) -> None:
        """AC-ADHOC-005-06: Invalid model passes through to backend
        and surfaces as AgentSubprocessError."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"",
            b"model not found",
        )
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        backend = AgentBackend()

        with pytest.raises(AgentSubprocessError):
            backend.invoke("test prompt", model="nonexistent/model")

        cmd = mock_popen.call_args[0][0]
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "nonexistent/model"
