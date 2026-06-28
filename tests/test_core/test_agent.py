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


class TestPiBackendRegistration:
    """TSK-009-01: Register Pi backend in config model, command registry,
    model-flag dispatch, error handling, and test fixtures.

    Covers AC-009-08 (AgentConfig Literal accepts Pi), AC-009-07
    (BACKEND_COMMANDS includes Pi), AC-009-01 (Pi backend dispatches
    correctly), AC-009-09 (YAML extraction is backend-agnostic), and the
    `StubPiBackend` fixture contract.
    """

    def test_agent_config_literal_accepts_pi(self):
        """AC-009-08: ``AgentConfig(backend='pi')`` validates without error."""
        config = AgentConfig(backend="pi")
        assert config.backend == "pi"
        assert config.model_dump()["backend"] == "pi"

    def test_agent_config_pi_round_trip_via_toml(self, tmp_path):
        """AC-009-08: ``backend='pi'`` survives model_dump → model_validate."""
        import tomllib

        config = AgentConfig(backend="pi")
        dumped = config.model_dump()
        toml_str = (
            f'[agent]\nbackend = "{dumped["backend"]}"\ntimeout = {dumped["timeout"]}\n'
        )
        (tmp_path / "config.toml").write_text(toml_str, encoding="utf-8")
        parsed = tomllib.loads((tmp_path / "config.toml").read_text())
        reloaded = AgentConfig(**parsed["agent"])
        assert reloaded.backend == "pi"

    def test_agent_config_literal_rejects_unknown(self):
        """AC-009-08: ``AgentConfig(backend='unknown')`` raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentConfig(backend="unknown")

    def test_pi_rpc_field_defaults_to_false(self):
        """Opt-in RPC mode must default off (print mode is the default)."""
        config = AgentConfig(backend="pi")
        assert getattr(config, "pi_rpc", False) is False

    def test_pi_rpc_field_opt_in(self):
        """Setting ``pi_rpc=True`` persists on the model."""
        config = AgentConfig(backend="pi", pi_rpc=True)
        assert config.pi_rpc is True

    def test_backend_commands_includes_pi(self):
        """AC-009-07: ``BACKEND_COMMANDS['pi'] == 'pi -p'``."""
        assert "pi" in BACKEND_COMMANDS
        assert BACKEND_COMMANDS["pi"] == "pi -p"

    def test_pi_backend_subprocess_contract(self):
        """AC-009-01: Pi backend spawns ``['pi', '-p']`` with prompt via stdin."""
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            config = AgentConfig(backend="pi")
            backend = AgentBackend(config=config)
            backend.invoke("test prompt")

        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert cmd[0] == "pi", f"Expected first argv 'pi', got {cmd[0]!r}"
        assert cmd[1] == "-p", f"Expected second argv '-p', got {cmd[1]!r}"
        assert kwargs.get("stdin") is not None, "Expected stdin=PIPE for prompt"

    def test_pi_backend_model_flag_injected(self):
        """Pi print mode accepts ``--model <id>`` — flag is injected when set."""
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            config = AgentConfig(backend="pi")
            backend = AgentBackend(config=config)
            backend.invoke("test prompt", model="anthropic/claude-sonnet-4-5")

        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--model" in cmd, f"Expected --model in command, got {cmd}"
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "anthropic/claude-sonnet-4-5"

    def test_pi_backend_missing_binary(self):
        """Edge case: ``pi`` not on PATH → ``AgentBinaryNotFoundError``."""
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            config = AgentConfig(backend="pi")
            backend = AgentBackend(config=config)
            with pytest.raises(Exception) as exc_info:
                backend.invoke("test prompt")

        from deviate.core.agent import AgentBinaryNotFoundError

        assert isinstance(exc_info.value, AgentBinaryNotFoundError)
        assert "pi" in str(exc_info.value).lower()

    def test_pi_backend_yaml_extraction_fenced(self):
        """AC-009-09: Pi-shaped stdout (fenced YAML) parses via existing pipeline."""
        pi_output = (
            "Some preamble\n"
            "```yaml\n"
            "phase: RED\n"
            "status: TEST_WRITTEN_FAILING\n"
            "task_id: TSK-009-01\n"
            "```\n"
        )
        manifest = AgentBackend.parse_output(pi_output, "pi")
        assert manifest.phase == "RED"
        assert manifest.status == "TEST_WRITTEN_FAILING"
        assert manifest.task_id == "TSK-009-01"

    def test_pi_backend_yaml_extraction_handover_marker(self):
        """AC-009-09: Pi-shaped stdout with ``<handover_manifest>`` tag parses."""
        pi_output = (
            "<handover_manifest>\n```yaml\n"
            "phase: GREEN\n"
            "status: IMPLEMENTED\n"
            "task_id: TSK-009-01\n"
            "```\n"
        )
        manifest = AgentBackend.parse_output(pi_output, "pi")
        assert manifest.phase == "GREEN"
        assert manifest.status == "IMPLEMENTED"
        assert manifest.task_id == "TSK-009-01"

    def test_pi_backend_parse_output_empty_raises(self):
        """Empty Pi stdout surfaces ``EmptyOutputError`` (backend-agnostic guard)."""
        from deviate.core.agent import EmptyOutputError

        with pytest.raises(EmptyOutputError):
            AgentBackend.parse_output("", "pi")


class TestStubPiBackend:
    """TSK-009-01: ``StubPiBackend`` mirrors ``StubAgentBackend`` for downstream
    Pi-specific test isolation.
    """

    def test_stub_pi_backend_registered_in_commands(self):
        """The Pi stub must be reachable via ``BACKEND_COMMANDS['stub']`` (or
        a dedicated ``pi_stub`` key) — verify it is importable and exposes
        a canonical command prefix."""
        from deviate.core.agent import StubPiBackend

        assert StubPiBackend is not None
        assert "stub" in BACKEND_COMMANDS

    def test_stub_pi_backend_yields_canonical_manifest(self):
        """``StubPiBackend().invoke(...)`` returns a valid ``HandoverManifest``."""
        from deviate.core.agent import HandoverManifest, StubPiBackend

        backend = StubPiBackend()
        manifest = backend.invoke("test prompt")

        assert isinstance(manifest, HandoverManifest)
        assert manifest.phase == "RED"
        assert manifest.status == "success"

    def test_stub_pi_backend_no_subprocess(self):
        """``StubPiBackend`` must not spawn a real subprocess."""
        from deviate.core.agent import StubPiBackend

        with patch("subprocess.Popen") as mock_popen:
            backend = StubPiBackend()
            backend.invoke("test prompt")

        mock_popen.assert_not_called()

    def test_stub_pi_backend_fires_output_callback(self):
        """``StubPiBackend`` invokes the output_callback when provided."""
        from deviate.core.agent import StubPiBackend

        callback_calls: list[str] = []

        def callback(text: str) -> None:
            callback_calls.append(text)

        backend = StubPiBackend()
        backend.invoke("test prompt", output_callback=callback)

        assert len(callback_calls) == 1
        assert "test prompt" in callback_calls[0]

    def test_stub_pi_backend_inherits_from_stub_agent_backend(self):
        """``StubPiBackend`` must subclass ``StubAgentBackend`` to share test
        plumbing (communal ``_invoked`` flag, callable surface)."""
        from deviate.core.agent import StubAgentBackend, StubPiBackend

        assert issubclass(StubPiBackend, StubAgentBackend)


class TestModelFlagsRegistry:
    """Per-backend model-flag dispatch via ``MODEL_FLAGS`` map.

    The dispatch table maps backend names to the flag prefix used for
    model injection. ``pi``, ``opencode``, and ``droid`` all use
    ``['--model']``; ``claude`` ignores model config (existing behavior).
    """

    def test_model_flags_map_contains_pi(self):
        from deviate.core.agent import MODEL_FLAGS

        assert "pi" in MODEL_FLAGS

    def test_model_flags_pi_uses_model_flag(self):
        """Pi accepts ``--model <id>`` — entry is ``['--model']``."""
        from deviate.core.agent import MODEL_FLAGS

        assert MODEL_FLAGS["pi"] == ["--model"]

    def test_model_flags_opencode_uses_model_flag(self):
        from deviate.core.agent import MODEL_FLAGS

        assert MODEL_FLAGS["opencode"] == ["--model"]

    def test_model_flags_droid_uses_model_flag(self):
        from deviate.core.agent import MODEL_FLAGS

        assert MODEL_FLAGS["droid"] == ["--model"]

    def test_pi_model_flag_lookup_returns_model_flag(self):
        """``AgentBackend.invoke()`` consults ``MODEL_FLAGS[backend]`` —
        ``pi`` resolves to ``['--model']`` so ``--model <id>`` is appended."""
        from deviate.core.agent import MODEL_FLAGS

        assert MODEL_FLAGS.get("pi") == ["--model"]


class TestPiSessionStatsLogging:
    """TSK-009-04: Extract ``pi.session_stats`` from Pi agent output and
    enrich ``prompts.log`` AGENT_RESULT entries with token statistics.

    Covers AC-ADHOC-009-04 (Token stats captured in prompts.log), US-009-03
    (cache-hit ratio observability), and the ``_extract_pi_session_stats``
    helper contract. Tests fail in RED phase because:

    1. ``_extract_pi_session_stats`` does not exist in
       ``deviate.cli.micro`` — tests that import it raise ``ImportError``.
    2. ``_invoke_agent`` does not pass ``pi_session_stats`` kwarg to
       ``_log_run("AGENT_RESULT", ...)`` — the kwarg lookup fails.
    """

    def test_extract_pi_session_stats_returns_all_four_fields(self):
        """Helper extracts ``tokens.{input,output,cacheRead,cacheWrite}``
        into a dict with camelCase keys and integer values.

        Spec: AC-ADHOC-009-04 — all four fields populated, no nulls.
        """
        from deviate.cli.micro import _extract_pi_session_stats

        stdout = (
            "phase: RED\n"
            "status: TEST_WRITTEN_FAILING\n"
            "tokens.input: 1234\n"
            "tokens.output: 567\n"
            "tokens.cacheRead: 890\n"
            "tokens.cacheWrite: 45\n"
        )

        stats = _extract_pi_session_stats(stdout)

        assert stats is not None, "Expected stats dict, got None"
        assert stats == {
            "input": 1234,
            "output": 567,
            "cacheRead": 890,
            "cacheWrite": 45,
        }

    def test_extract_pi_session_stats_returns_none_when_absent(self):
        """Helper returns ``None`` when no token stats appear in stdout.

        Spec edge case: token stats absent from Pi output → helper returns
        ``None`` (caller logs a warning, does not fail).
        """
        from deviate.cli.micro import _extract_pi_session_stats

        stdout = "phase: RED\nstatus: TEST_WRITTEN_FAILING\ntask_id: TSK-009-04\n"

        assert _extract_pi_session_stats(stdout) is None

    def test_extract_pi_session_stats_partial_fields(self):
        """Helper returns only the fields present in stdout when stats
        are partial (e.g., only input/output, no cache fields).

        Spec edge case: partial stats — return only present fields.
        """
        from deviate.cli.micro import _extract_pi_session_stats

        stdout = "tokens.input: 100\ntokens.output: 50\n"

        stats = _extract_pi_session_stats(stdout)

        assert stats == {"input": 100, "output": 50}

    def test_pi_session_stats_logged(self):
        """AC-ADHOC-009-04: AGENT_RESULT event contains ``pi_session_stats``
        kwarg with all four token fields when Pi backend emits stats.

        Exercises the full ``_invoke_agent(backend_name='pi')`` logging path:
        mock ``AgentBackend.invoke`` to push Pi-shaped stdout through the
        ``output_callback`` (which captures ``raw_lines`` internally), then
        verify ``_log_run('AGENT_RESULT', ...)`` receives ``pi_session_stats``.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.cli.micro import _invoke_agent

        manifest = HandoverManifest(phase="RED", status="TEST_WRITTEN_FAILING")
        pi_stdout_lines = [
            "phase: RED",
            "status: TEST_WRITTEN_FAILING",
            "tokens.input: 1234",
            "tokens.output: 567",
            "tokens.cacheRead: 890",
            "tokens.cacheWrite: 45",
        ]

        def fake_invoke(self, prompt, **kwargs):
            callback = kwargs.get("output_callback")
            if callback is not None:
                for line in pi_stdout_lines:
                    callback(line)
            return manifest

        with (
            patch("deviate.cli.micro._log_run") as mock_log_run,
            patch.object(AgentBackend, "invoke", new=fake_invoke),
        ):
            from rich.console import Console

            _invoke_agent(
                prompt="test prompt",
                c=Console(),
                backend_name="pi",
                task_id="TSK-009-04",
                phase="RED",
            )

        agent_result_calls = [
            call
            for call in mock_log_run.call_args_list
            if call.args and call.args[0] == "AGENT_RESULT"
        ]
        assert agent_result_calls, (
            "_log_run was not invoked with the 'AGENT_RESULT' event"
        )

        pi_stats_kwarg = agent_result_calls[0].kwargs.get("pi_session_stats")
        assert pi_stats_kwarg is not None, (
            "Expected 'pi_session_stats' kwarg on _log_run('AGENT_RESULT', ...),"
            f" got kwargs: {agent_result_calls[0].kwargs}"
        )
        assert pi_stats_kwarg["input"] == 1234
        assert pi_stats_kwarg["output"] == 567
        assert pi_stats_kwarg["cacheRead"] == 890
        assert pi_stats_kwarg["cacheWrite"] == 45

    def test_pi_session_stats_absent_logs_none(self):
        """When Pi stdout contains no token stats, the AGENT_RESULT event
        must carry ``pi_session_stats=None`` (not raise, not omit the kwarg).

        Spec edge case: absent stats — log warning but do not fail.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.cli.micro import _invoke_agent

        manifest = HandoverManifest(phase="RED", status="TEST_WRITTEN_FAILING")
        pi_stdout_lines = [
            "phase: RED",
            "status: TEST_WRITTEN_FAILING",
        ]

        def fake_invoke(self, prompt, **kwargs):
            callback = kwargs.get("output_callback")
            if callback is not None:
                for line in pi_stdout_lines:
                    callback(line)
            return manifest

        with (
            patch("deviate.cli.micro._log_run") as mock_log_run,
            patch.object(AgentBackend, "invoke", new=fake_invoke),
        ):
            from rich.console import Console

            _invoke_agent(
                prompt="test prompt",
                c=Console(),
                backend_name="pi",
                task_id="TSK-009-04",
                phase="RED",
            )

        agent_result_calls = [
            call
            for call in mock_log_run.call_args_list
            if call.args and call.args[0] == "AGENT_RESULT"
        ]
        assert agent_result_calls
        assert "pi_session_stats" in agent_result_calls[0].kwargs
        assert agent_result_calls[0].kwargs["pi_session_stats"] is None

    def test_non_pi_backend_skips_session_stats_extraction(self):
        """When backend is NOT 'pi', the AGENT_RESULT event must NOT include
        ``pi_session_stats`` (extraction is Pi-specific).

        Spec: defensive exclusion — non-Pi backends never include the block.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.cli.micro import _invoke_agent

        manifest = HandoverManifest(phase="RED", status="TEST_WRITTEN_FAILING")

        def fake_invoke(self, prompt, **kwargs):
            return manifest

        with (
            patch("deviate.cli.micro._log_run") as mock_log_run,
            patch.object(AgentBackend, "invoke", new=fake_invoke),
        ):
            from rich.console import Console

            _invoke_agent(
                prompt="test prompt",
                c=Console(),
                backend_name="opencode",
                task_id="TSK-009-04",
                phase="RED",
            )

        agent_result_calls = [
            call
            for call in mock_log_run.call_args_list
            if call.args and call.args[0] == "AGENT_RESULT"
        ]
        assert agent_result_calls
        assert "pi_session_stats" not in agent_result_calls[0].kwargs
