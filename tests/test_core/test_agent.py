from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from deviate.core.agent import BACKEND_COMMANDS, AgentBackend
from deviate.state.config import AgentConfig, DeviateConfig


class TestAgentConfigModel:
    def test_agent_config_defaults(self):
        config = AgentConfig()
        assert config.backend == "opencode"
        assert config.timeout == 600

    def test_agent_config_custom_values(self):
        config = AgentConfig(backend="claude", timeout=300)
        assert config.backend == "claude"
        assert config.timeout == 300

    def test_agent_config_droid_backend(self):
        config = AgentConfig(backend="droid", timeout=120)
        assert config.backend == "droid"
        assert config.timeout == 120

    def test_agent_config_rejects_invalid_backend(self):
        with pytest.raises(ValidationError):
            AgentConfig(backend="invalid-backend")

    def test_agent_config_rejects_zero_timeout(self):
        with pytest.raises(ValidationError):
            AgentConfig(timeout=0)

    def test_agent_config_rejects_negative_timeout(self):
        with pytest.raises(ValidationError):
            AgentConfig(timeout=-1)

    def test_agent_config_in_deviate_config(self):
        deviate = DeviateConfig(agent=AgentConfig(backend="claude", timeout=300))
        assert deviate.agent.backend == "claude"
        assert deviate.agent.timeout == 300

    def test_agent_config_in_deviate_config_default(self):
        deviate = DeviateConfig()
        assert deviate.agent.backend == "opencode"
        assert deviate.agent.timeout == 600

    def test_agent_config_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            AgentConfig(backend="opencode", timeout=600, unknown_field="x")


class TestHandoverManifestModel:
    def test_handover_manifest_parsed_from_yaml(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(
            phase="RED",
            status="TEST_WRITTEN_FAILING",
            test_file="tests/test_core/test_agent.py",
            verification_command="pytest tests/test_core/test_agent.py -v",
        )
        assert manifest.phase == "RED"
        assert manifest.status == "TEST_WRITTEN_FAILING"
        assert manifest.test_file == "tests/test_core/test_agent.py"
        assert (
            manifest.verification_command == "pytest tests/test_core/test_agent.py -v"
        )
        assert manifest.yellow_trigger is None

    def test_handover_manifest_yellow_trigger(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(
            phase="GREEN",
            status="YELLOW_TRIGGERED",
            yellow_trigger=True,
            test_changes={"file": "test_x.py", "diff": "..."},
            rationale="Need to adjust assertion",
        )
        assert manifest.yellow_trigger is True
        assert manifest.test_changes == {"file": "test_x.py", "diff": "..."}
        assert manifest.rationale == "Need to adjust assertion"

    def test_handover_manifest_minimal_fields(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(phase="RED", status="TEST_WRITTEN_FAILING")
        assert manifest.test_file is None
        assert manifest.verification_command is None
        assert manifest.yellow_trigger is None

    def test_handover_manifest_allows_extra_fields(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(phase="RED", status="FAIL", unknown_field="x")
        assert manifest.phase == "RED"
        assert manifest.status == "FAIL"


class TestAgentBackendInvocation:
    def test_agent_successful_invocation(self):
        from deviate.core.agent import AgentBackend

        yaml_output = (
            "phase: RED\n"
            "status: TEST_WRITTEN_FAILING\n"
            "test_file: tests/test_core/test_agent.py\n"
            "verification_command: pytest tests/test_core/test_agent.py -v\n"
        )
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            backend = AgentBackend()
            manifest = backend.invoke("test prompt")

        assert manifest.phase == "RED"
        assert manifest.status == "TEST_WRITTEN_FAILING"
        assert manifest.test_file == "tests/test_core/test_agent.py"

    def test_agent_backend_parses_yellow_handover(self):
        from deviate.core.agent import AgentBackend

        yaml_output = (
            "phase: GREEN\n"
            "status: YELLOW_TRIGGERED\n"
            "yellow_trigger: true\n"
            "test_changes:\n"
            "  file: test_agent.py\n"
            '  diff: "@@ -1,5 +1,6 @@"\n'
            "rationale: Need to widen assertion scope\n"
        )
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            backend = AgentBackend()
            manifest = backend.invoke("test prompt")

        assert manifest.yellow_trigger is True
        assert manifest.phase == "GREEN"
        assert manifest.rationale == "Need to widen assertion scope"

    def test_agent_uses_opencode_command_default(self):
        from deviate.core.agent import AgentBackend

        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            backend = AgentBackend()
            backend.invoke("test prompt")

        args, kwargs = mock_popen.call_args
        cmd_str = " ".join(args[0]) if isinstance(args[0], list) else str(args[0])
        assert "opencode run" in cmd_str

    def test_agent_backend_pipe_heredoc_stdin(self):
        from deviate.core.agent import AgentBackend

        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            backend = AgentBackend()
            backend.invoke("test prompt")

        _, kwargs = mock_popen.call_args
        assert "stdin" in kwargs

    def test_agent_backend_respects_config_backend(self):
        from deviate.core.agent import AgentBackend

        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with (
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch(
                "deviate.core.agent.BACKEND_COMMANDS",
                {"claude": "claude -p"},
            ),
        ):
            config = AgentConfig(backend="claude", timeout=300)
            backend = AgentBackend(config=config)
            backend.invoke("test prompt")

        args, _ = mock_popen.call_args
        cmd_str = " ".join(args[0]) if isinstance(args[0], list) else str(args[0])
        assert "claude" in cmd_str


class TestStubAgentBackend:
    def test_stub_backend_registered_in_commands(self):
        assert "stub" in BACKEND_COMMANDS
        assert BACKEND_COMMANDS["stub"] == "stub"

    def test_stub_backend_returns_valid_manifest(self):
        from deviate.core.agent import StubAgentBackend

        backend = StubAgentBackend()
        manifest = backend.invoke("test prompt")

        assert manifest.phase == "RED"
        assert manifest.status == "success"
        assert manifest.task_id is None

    def test_stub_backend_no_subprocess(self):
        from deviate.core.agent import StubAgentBackend

        with patch("subprocess.Popen") as mock_popen:
            backend = StubAgentBackend()
            backend.invoke("test prompt")

        mock_popen.assert_not_called()

    def test_stub_backend_fires_output_callback(self):
        from deviate.core.agent import StubAgentBackend

        callback_calls: list[str] = []

        def callback(text: str) -> None:
            callback_calls.append(text)

        backend = StubAgentBackend()
        backend.invoke("test prompt", output_callback=callback)

        assert len(callback_calls) == 1
        assert "test prompt" in callback_calls[0]

    def test_stub_backend_accepts_timeout(self):
        from deviate.core.agent import StubAgentBackend

        backend = StubAgentBackend()
        manifest = backend.invoke("test prompt", timeout=999)

        assert manifest.phase == "RED"
        assert manifest.status == "success"

    def test_stub_backend_manifest_is_handover_manifest_type(self):
        from deviate.core.agent import HandoverManifest, StubAgentBackend

        backend = StubAgentBackend()
        manifest = backend.invoke("test prompt")

        assert isinstance(manifest, HandoverManifest)

    def test_stub_backend_invoke_signature_matches_agent_backend(self):
        import inspect
        from deviate.core.agent import AgentBackend, StubAgentBackend

        ab_sig = inspect.signature(AgentBackend.invoke)
        sb_sig = inspect.signature(StubAgentBackend.invoke)

        assert ab_sig.parameters.keys() == sb_sig.parameters.keys()


class TestAgentBackendErrors:
    def test_agent_timeout_retry(self):
        from deviate.core.agent import AgentBackend, AgentTimeoutError

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="opencode run", timeout=10, output=b""
        )

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep", return_value=None) as mock_sleep,
        ):
            backend = AgentBackend()
            with pytest.raises(AgentTimeoutError):
                backend.invoke("test prompt", timeout=10)

        assert mock_sleep.called
        sleep_args = mock_sleep.call_args[0]
        assert sleep_args[0] == 30

    def test_agent_timeout_retry_twice_then_raises(self):
        from deviate.core.agent import AgentBackend, AgentTimeoutError

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="opencode run", timeout=10, output=b""
        )

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("time.sleep", return_value=None),
        ):
            backend = AgentBackend()
            with pytest.raises(AgentTimeoutError) as exc_info:
                backend.invoke("test prompt", timeout=10)

        assert (
            "timed out" in str(exc_info.value).lower()
            or "timeout" in str(exc_info.value).lower()
        )

    def test_agent_malformed_yaml(self):
        from deviate.core.agent import AgentBackend, MalformedHandoverManifestError

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (b"not: valid: yaml: [\nbroken", b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            backend = AgentBackend()
            with pytest.raises(MalformedHandoverManifestError) as exc_info:
                backend.invoke("test prompt")

        assert (
            "yaml" in str(exc_info.value).lower()
            or "malformed" in str(exc_info.value).lower()
        )

    def test_agent_nonzero_exit(self):
        from deviate.core.agent import AgentBackend, AgentSubprocessError

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (b"", b"command not found")
        mock_proc.returncode = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            backend = AgentBackend()
            with pytest.raises(AgentSubprocessError) as exc_info:
                backend.invoke("test prompt")

        assert "command not found" in str(exc_info.value)

    def test_agent_empty_output(self):
        from deviate.core.agent import AgentBackend, EmptyOutputError

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            backend = AgentBackend()
            with pytest.raises(EmptyOutputError):
                backend.invoke("test prompt")

    def test_agent_binary_not_found(self):
        from deviate.core.agent import AgentBackend, AgentBinaryNotFoundError

        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            backend = AgentBackend()
            with pytest.raises(AgentBinaryNotFoundError):
                backend.invoke("test prompt")

    def test_agent_timeout_error_is_exception(self):
        from deviate.core.agent import AgentTimeoutError

        assert issubclass(AgentTimeoutError, Exception)

    def test_agent_subprocess_error_captures_exit_code(self):
        from deviate.core.agent import (
            AgentSubprocessError,
            MalformedHandoverManifestError,
            AgentBinaryNotFoundError,
            EmptyOutputError,
        )

        assert issubclass(AgentSubprocessError, Exception)
        assert issubclass(MalformedHandoverManifestError, Exception)
        assert issubclass(AgentBinaryNotFoundError, Exception)
        assert issubclass(EmptyOutputError, Exception)


class TestAgentModelRouting:
    """AC-ADHOC-005-01 through AC-ADHOC-005-05: model parameter injection."""

    def test_agent_command_with_model(self):
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            backend = AgentBackend()
            backend.invoke("test prompt", model="opencode/deepseek-v4-flash")

        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--model" in cmd, f"Expected --model in command, got {cmd}"
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "opencode/deepseek-v4-flash"

    def test_agent_command_without_model(self):
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            backend = AgentBackend()
            backend.invoke("test prompt")

        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--model" not in cmd, f"Expected no --model in command, got {cmd}"

    def test_agent_command_droid_backend(self):
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with (
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch(
                "deviate.core.agent.BACKEND_COMMANDS",
                {"droid": "droid exec"},
            ),
        ):
            config = AgentConfig(backend="droid")
            backend = AgentBackend(config=config)
            backend.invoke("test prompt", model="deepseek-v4-pro")

        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--model" in cmd, f"Expected --model in droid command, got {cmd}"
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "deepseek-v4-pro"

    def test_agent_command_claude_backend(self):
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with (
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch(
                "deviate.core.agent.BACKEND_COMMANDS",
                {"claude": "claude -p"},
            ),
        ):
            config = AgentConfig(backend="claude")
            backend = AgentBackend(config=config)
            backend.invoke("test prompt", model="opencode/deepseek-v4-flash")

        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--model" not in cmd, (
            f"Expected no --model for claude backend, got {cmd}"
        )
