from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from deviate.core.agent import BACKEND_COMMANDS, AgentBackend
from deviate.state.config import AgentConfig, DeviateConfig


class TestAgentConfigModel:
    def test_agent_config_defaults(self):
        config = AgentConfig()
        assert config.backend == "pi"
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
        assert deviate.agent.backend == "pi"
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
        assert manifest.rationale is None

    def test_handover_manifest_minimal_fields(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(phase="RED", status="TEST_WRITTEN_FAILING")
        assert manifest.test_file is None
        assert manifest.rationale is None

    def test_handover_manifest_allows_extra_fields(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(phase="RED", status="FAIL", unknown_field="x")
        assert manifest.phase == "RED"
        assert manifest.status == "FAIL"

    def test_handover_manifest_files_defaults_to_none(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(phase="GREEN", status="PASS")
        assert manifest.files is None

    def test_handover_manifest_files_round_trips(self):
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest(
            phase="GREEN",
            status="PASS",
            task_id="TSK-006-09",
            files=["src/watcher.py", "src/main.py"],
        )
        assert manifest.files == ["src/watcher.py", "src/main.py"]
        dumped = manifest.model_dump()
        assert dumped["files"] == ["src/watcher.py", "src/main.py"]
        reloaded = HandoverManifest.model_validate(dumped)
        assert reloaded.files == ["src/watcher.py", "src/main.py"]


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

    def test_agent_uses_pi_command_default(self):
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
        assert "pi -p" in cmd_str

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

    def test_agent_caps_oversized_prompt_preserving_head_and_tail(self):
        yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
        mock_proc.returncode = 0
        prompt = "HEAD_SENTINEL\n" + ("x" * 100_000) + "\nTAIL_SENTINEL"

        with patch("subprocess.Popen", return_value=mock_proc):
            AgentBackend().invoke(prompt)

        dispatched = mock_proc.communicate.call_args.kwargs["input"].decode("utf-8")
        assert len(dispatched) <= 80_000
        assert dispatched.startswith("HEAD_SENTINEL\n")
        assert dispatched.endswith("\nTAIL_SENTINEL")
        assert "PROMPT_TRUNCATED" in dispatched


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

    def test_streaming_agent_detects_stdout_stall(self):
        from deviate.core.agent import AgentTimeoutError

        release = threading.Event()

        class BlockingPipe:
            def __iter__(self):
                return self

            def __next__(self):
                release.wait()
                raise StopIteration

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = BlockingPipe()
        mock_proc.stderr = iter(())
        mock_proc.kill.side_effect = release.set
        ticks = iter((0.0, 0.0, 0.051))

        with (
            patch("deviate.core.agent.STREAM_STALL_TIMEOUT_SECONDS", 0.05),
            patch(
                "deviate.core.agent.time.monotonic",
                side_effect=lambda: next(ticks, 0.051),
            ),
            pytest.raises(AgentTimeoutError, match="STALL_DETECTED"),
        ):
            AgentBackend()._invoke_streaming(
                mock_proc,
                ["pi", "-p"],
                "prompt",
                timeout_secs=10,
                backend_name="pi",
                output_callback=lambda _line: None,
            )

    def test_streaming_agent_output_completes_without_stall(self):
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = iter((b"phase: RED\n", b"status: PASS\n"))
        mock_proc.stderr = iter(())
        mock_proc.returncode = 0

        with patch("deviate.core.agent.STREAM_STALL_TIMEOUT_SECONDS", 0.05):
            stdout, _stderr = AgentBackend()._invoke_streaming(
                mock_proc,
                ["pi", "-p"],
                "prompt",
                timeout_secs=10,
                backend_name="pi",
                output_callback=lambda _line: None,
            )

        assert stdout == "phase: RED\nstatus: PASS"

    @pytest.mark.parametrize(
        ("yaml_body", "expected_hint"),
        [
            (
                'phase: "JUDGE"\nstatus: "PASS"\ndetail: "embedder == \\"mini\\""\n',
                "Avoid backslash-escaped quotes",
            ),
            (
                'phase: "JUDGE"\nstatus: "PASS"\ndetail: "unterminated\n',
                "Unbalanced double quotes",
            ),
            (
                'phase: "JUDGE"\nstatus: "PASS"\ndetail: |\nunindented detail\n',
                "Indent block scalar content",
            ),
        ],
    )
    def test_yaml_error_hint_identifies_malformed_scalar(
        self, yaml_body: str, expected_hint: str
    ):
        output = f"```yaml\n{yaml_body}```"

        hint = AgentBackend._yaml_error_hint(output)

        assert expected_hint in hint

    def test_agent_retries_malformed_manifest_with_error_context(self):
        malformed = MagicMock(spec=subprocess.Popen)
        malformed.communicate.return_value = (b"```yaml\nphase: [\n```", b"")
        malformed.returncode = 0
        valid = MagicMock(spec=subprocess.Popen)
        valid.communicate.return_value = (b"phase: JUDGE\nstatus: PASS\n", b"")
        valid.returncode = 0

        with patch("subprocess.Popen", side_effect=(malformed, valid)) as mock_popen:
            manifest = AgentBackend().invoke("ORIGINAL_PROMPT")

        assert manifest.status == "PASS"
        assert mock_popen.call_count == 2
        retry_prompt = valid.communicate.call_args.kwargs["input"].decode("utf-8")
        assert "Failed to parse YAML handover manifest" in retry_prompt
        assert "strict YAML" in retry_prompt
        assert "ORIGINAL_PROMPT" in retry_prompt

    def test_agent_does_not_manifest_retry_subprocess_failure(self):
        from deviate.core.agent import AgentSubprocessError

        failed = MagicMock(spec=subprocess.Popen)
        failed.communicate.return_value = (b"", b"backend crashed")
        failed.returncode = 2

        with (
            patch("subprocess.Popen", return_value=failed) as mock_popen,
            pytest.raises(AgentSubprocessError, match="backend crashed"),
        ):
            AgentBackend().invoke("ORIGINAL_PROMPT")

        assert mock_popen.call_count == 1

    def test_missing_phase_and_status_recover_as_unknown(self):
        manifest = AgentBackend.parse_output(
            "task_id: TSK-001-01\nrationale: implementation interrupted\n",
            "pi",
        )

        assert manifest.phase == "UNKNOWN"
        assert manifest.status == "UNKNOWN"
        assert any("phase" in error for error in manifest.parse_errors)
        assert any("status" in error for error in manifest.parse_errors)
        assert manifest.is_success is False

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

    def test_prose_with_word_prefix_does_not_match_mapping_fallback(self):
        # Regression: a `word:` line in prose (e.g. a JUDGE verdict with a
        # verification matrix and a `Status:` line but no fenced YAML block)
        # must NOT be accepted as a manifest via the `_YAML_MAPPING_START_RE`
        # fallback. Previously the fallback grabbed prose to EOF and
        # `safe_load` returned a `str`, surfacing the misleading "manifest
        # is not a mapping (got str)" error.
        from deviate.core.agent import AgentBackend, MalformedHandoverManifestError

        prose_output = (
            "## Final Verdict\n"
            "**COMPLIANCE_PASS** — TSK-009-05 GREEN is compliant.\n"
            "| Spec item | Where in implementation | Verified by |\n"
            "|-----------|------------------------|-------------|\n"
            "| FR-016    | initialize_response     | unit test  |\n"
            "Status: complete\n"
        )
        with pytest.raises(MalformedHandoverManifestError) as exc_info:
            AgentBackend.parse_output(prose_output, "omp")
        msg = str(exc_info.value).lower()
        # Operator-grep invariant: the message must NOT claim YAML was found.
        assert "got str" not in msg
        assert "not a mapping" not in msg
        # The hint should explicitly say no YAML was detected.
        assert "no yaml" in msg or "no fenced" in msg

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
        agent_result_calls = [
            call
            for call in mock_log_run.call_args_list
            if call.args and call.args[0] == "AGENT_RESULT"
        ]
        assert agent_result_calls
        assert "pi_session_stats" not in agent_result_calls[0].kwargs


class TestAgentToBackendResolution:
    """Canonical home of ``AGENT_TO_BACKEND`` and ``resolve_agent_to_backend``
    is :mod:`deviate.core.agent` — both must remain importable from there
    and the resolution contract must hold for every supported alias.

    ``factory`` is the only true alias (Factory Droid IDE → ``droid``
    binary); every other entry (``opencode``, ``claude``, ``droid``,
    ``pi``, ``omp``) is canonical and resolves to itself.
    """

    def test_resolve_factory_to_droid(self) -> None:
        from deviate.core.agent import resolve_agent_to_backend

        assert resolve_agent_to_backend("factory") == "droid"

    def test_resolve_canonical_passthrough(self) -> None:
        from deviate.core.agent import resolve_agent_to_backend

        for canonical in ("opencode", "claude", "droid", "pi", "omp"):
            assert resolve_agent_to_backend(canonical) == canonical

    def test_resolve_omp_is_identity_not_alias(self) -> None:
        """``omp`` is its own backend, not an alias for ``pi``.

        Oh-My-Pi wraps Pi internally but is invoked as a distinct CLI
        binary (``omp -p``); aliasing it to ``pi`` would route
        ``deviate`` through the wrong process.
        """
        from deviate.core.agent import resolve_agent_to_backend

        assert resolve_agent_to_backend("omp") == "omp"

    def test_resolve_unknown_passthrough_for_validation_error(self) -> None:
        """Unknown names pass through so ``AgentConfig`` raises a clear
        Literal validation error (instead of silently mapping to ``opencode``)."""
        from deviate.core.agent import resolve_agent_to_backend

        assert resolve_agent_to_backend("aider") == "aider"

    def test_agent_to_backend_table_includes_omp_identity(self) -> None:
        """``AGENT_TO_BACKEND['omp'] == 'omp'`` (canonical, not aliased)."""
        from deviate.core.agent import AGENT_TO_BACKEND

        assert AGENT_TO_BACKEND["omp"] == "omp"

    def test_cli_re_export_is_same_object_as_core(self) -> None:
        """``deviate.cli.AGENT_TO_BACKEND`` is the SAME dict object as
        ``deviate.core.agent.AGENT_TO_BACKEND`` (no shadow copy)."""
        from deviate.cli import AGENT_TO_BACKEND as cli_table
        from deviate.core.agent import AGENT_TO_BACKEND as core_table

        assert cli_table is core_table

    def test_cli_private_resolver_delegates_to_core(self) -> None:
        """``deviate.cli._resolve_agent_to_backend`` is the public
        :func:`deviate.core.agent.resolve_agent_to_backend` function —
        keeping the existing private import path working."""
        from deviate.cli import _resolve_agent_to_backend as cli_resolve
        from deviate.core.agent import resolve_agent_to_backend as core_resolve

        assert cli_resolve is core_resolve


class TestOmpBackendRegistration:
    """``omp`` is a first-class dispatch backend (not an alias for ``pi``).

    The dispatch layer must accept ``omp`` as a valid ``BackendName``,
    resolve it to its own ``BACKEND_COMMANDS`` entry (``omp -p``), and
    pass it through the Pydantic ``AgentConfig.backend`` Literal. The
    ``MODEL_FLAGS`` entry supports ``--model <id>`` like the other
    subprocess-driven backends.
    """

    def test_omp_is_valid_backend_literal(self) -> None:
        from deviate.state.config import AgentConfig

        cfg = AgentConfig(backend="omp")
        assert cfg.backend == "omp"

    def test_omp_in_backend_commands_runs_omp_binary(self) -> None:
        """``BACKEND_COMMANDS['omp']`` must spawn ``omp -p``, not ``pi -p``."""
        from deviate.core.agent import BACKEND_COMMANDS

        assert BACKEND_COMMANDS["omp"] == "omp -p"

    def test_omp_supports_model_flag(self) -> None:
        """``MODEL_FLAGS['omp']`` accepts ``--model`` (subprocess-driven
        backend, like ``pi``)."""
        from deviate.core.agent import MODEL_FLAGS

        assert MODEL_FLAGS["omp"] == ["--model"]

    @patch("deviate.core.agent.subprocess.Popen")
    def test_omp_dispatch_spawns_omp_command(self, mock_popen: MagicMock) -> None:
        """``AgentBackend.invoke(backend='omp')`` spawns ``omp -p`` (NOT
        ``pi -p``). This is the contract that distinguishes ``omp`` as a
        distinct backend from an alias to ``pi``.
        """
        from deviate.core.agent import AgentBackend
        from deviate.state.config import AgentConfig

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"phase: RED\nstatus: TEST_WRITTEN_FAILING\ntask_id: T\n",
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend(config=AgentConfig(backend="omp"))
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "omp", (
            f"Expected first argv 'omp' for backend=omp, got {cmd[0]!r}"
        )
        assert "-p" in cmd, f"Expected '-p' in cmd, got {cmd}"
        assert "pi" not in cmd, f"omp backend must NOT invoke pi binary, got {cmd}"

    def test_omp_passes_through_resolve_agent_to_backend(self) -> None:
        """``_resolve_agent_config`` returns ``omp`` unchanged (identity,
        since ``omp`` is canonical, not an alias)."""
        from deviate.cli.micro import _resolve_agent_config

        assert _resolve_agent_config(Path.cwd(), "omp") == "omp"
