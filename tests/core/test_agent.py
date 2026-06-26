from __future__ import annotations

import json
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
        assert cmd[2] == "--permission-mode"
        assert cmd[3] == "auto"
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


class TestPiRpcMode:
    """TSK-009-03: RPC mode opt-in via ``agent.pi_rpc = true``.

    AC-009-10: When ``agent.pi_rpc = true``, the subprocess spawns
    ``["pi", "--mode", "rpc", "--no-session"]`` instead of ``["pi", "-p"]``.
    The prompt is sent as JSONL over stdin. JSONL events on stdout
    (``agent_start``, ``message_update``, ``agent_end``) are parsed line-by-line.
    The handover manifest is extracted from the ``agent_end`` event's
    ``message.content`` payload.
    """

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_mode_opt_in(self, mock_popen: MagicMock) -> None:
        """AC-009-10: ``pi_rpc=True`` spawns ``["pi", "--mode", "rpc", "--no-session"]``."""
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        jsonl_output = (
            json.dumps({"type": "agent_start"})
            + "\n"
            + json.dumps({"type": "agent_end", "message": {"content": yaml_output}})
            + "\n"
        ).encode("utf-8")

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (jsonl_output, b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pi", f"Expected first argv 'pi', got {cmd[0]!r}"
        assert "--mode" in cmd, f"RPC mode requires --mode flag (got {cmd})"
        assert "rpc" in cmd, f"RPC mode requires 'rpc' value (got {cmd})"
        assert "--no-session" in cmd, f"RPC mode requires --no-session flag (got {cmd})"
        assert "-p" not in cmd, (
            f"Print-mode flag must not appear in RPC mode command (got {cmd})"
        )

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_mode_sends_jsonl_prompt_over_stdin(
        self, mock_popen: MagicMock
    ) -> None:
        """AC-009-10: RPC mode sends prompt as JSONL ``{"type":"prompt","content":...}``."""
        jsonl_output = (
            json.dumps({"type": "agent_start"})
            + "\n"
            + json.dumps(
                {
                    "type": "agent_end",
                    "message": {"content": "phase: RED\nstatus: OK\n"},
                }
            )
            + "\n"
        ).encode("utf-8")

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (jsonl_output, b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)
        backend.invoke("hello world")

        call_args = mock_proc.communicate.call_args
        stdin_bytes = (
            call_args.kwargs.get("input")
            if call_args.kwargs
            else (call_args[1].get("input") if len(call_args) > 1 else None)
        )
        assert stdin_bytes is not None, "Expected prompt piped via stdin"
        stdin_text = stdin_bytes.decode("utf-8")

        first_line = stdin_text.split("\n", 1)[0]
        parsed = json.loads(first_line)
        assert parsed["type"] == "prompt", (
            f"RPC prompt frame must have type='prompt' (got {parsed!r})"
        )
        assert parsed["content"] == "hello world", (
            f"RPC prompt content must equal user prompt (got {parsed!r})"
        )

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_mode_extracts_manifest_from_agent_end(
        self, mock_popen: MagicMock
    ) -> None:
        """AC-009-10: Manifest is extracted from ``agent_end.message.content``."""
        agent_start = json.dumps({"type": "agent_start"})
        message_update = json.dumps({"type": "message_update", "delta": "thinking..."})
        agent_end = json.dumps(
            {
                "type": "agent_end",
                "message": {
                    "content": (
                        "phase: RED\n"
                        "status: TEST_WRITTEN_FAILING\n"
                        "task_id: TSK-009-03\n"
                    ),
                },
            }
        )
        jsonl_output = (
            agent_start + "\n" + message_update + "\n" + agent_end + "\n"
        ).encode("utf-8")

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (jsonl_output, b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)
        manifest = backend.invoke("test prompt")

        assert manifest.phase == "RED"
        assert manifest.status == "TEST_WRITTEN_FAILING"
        assert manifest.task_id == "TSK-009-03"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_mode_skips_malformed_jsonl_lines(
        self, mock_popen: MagicMock
    ) -> None:
        """Edge case: malformed JSONL line is skipped, valid ``agent_end`` still parsed."""
        agent_start = json.dumps({"type": "agent_start"})
        bad_line = "{this is not json"
        agent_end = json.dumps(
            {
                "type": "agent_end",
                "message": {"content": "phase: GREEN\nstatus: OK\n"},
            }
        )
        jsonl_output = (agent_start + "\n" + bad_line + "\n" + agent_end + "\n").encode(
            "utf-8"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (jsonl_output, b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)

        manifest = backend.invoke("test prompt")

        assert manifest.phase == "GREEN"
        assert manifest.status == "OK"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_mode_default_off_uses_print_mode(
        self, mock_popen: MagicMock
    ) -> None:
        """Regression: ``pi_rpc=False`` (default) keeps print-mode ``pi -p`` command."""
        yaml_output = "phase: RED\nstatus: OK\n"
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi")
        backend = AgentBackend(config=config)
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pi"
        assert cmd[1] == "-p"
        assert "--mode" not in cmd, (
            f"Print mode must not contain --mode flag (got {cmd})"
        )
