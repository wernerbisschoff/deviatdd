from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deviate.core.agent import AgentBackend, AgentConfig, AgentSubprocessError

_CODING_TOOLS = ("read", "bash", "edit", "write")
_DEVIATDD_SKILL_REL = Path(".pi") / "skills" / "deviatdd" / "SKILL.md"


def _has_long_or_short(cmd: list[str], long_flag: str, short_flag: str) -> bool:
    return long_flag in cmd or short_flag in cmd


def _flag_value(cmd: list[str], flag: str) -> str | None:
    for index, token in enumerate(cmd):
        if token == flag and index + 1 < len(cmd):
            return cmd[index + 1]
        prefix = f"{flag}="
        if token.startswith(prefix):
            return token[len(prefix) :]
    return None


def _tools_allowlist(cmd: list[str]) -> set[str]:
    raw = _flag_value(cmd, "--tools")
    if raw is None:
        raw = _flag_value(cmd, "-t")
    if raw is None:
        return set()
    return {part for part in raw.split(",") if part}


def _assert_pi_lean_coding_tools(cmd: list[str]) -> None:
    allowlist = _tools_allowlist(cmd)
    missing = [tool for tool in _CODING_TOOLS if tool not in allowlist]
    assert not missing, (
        f"Pi --tools must list {_CODING_TOOLS}, missing {missing} in {cmd}"
    )
    assert "--no-tools" not in cmd, f"Default Pi spawn must omit --no-tools (got {cmd})"
    assert "--no-builtin-tools" not in cmd, (
        f"Default Pi spawn must omit --no-builtin-tools (got {cmd})"
    )


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
    def test_pi_rpc_lean_spawn_flags(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """AC-PLAN-001 / AC-PLAN-002: RPC argv keeps AC-009-10 then lean flags."""
        skill_path = tmp_path / _DEVIATDD_SKILL_REL
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# deviatdd\n", encoding="utf-8")

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
        backend.invoke("test prompt", cwd=str(tmp_path))

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pi", f"Expected first argv 'pi', got {cmd[0]!r}"
        assert cmd[1:4] == ["--mode", "rpc", "--no-session"], (
            f"RPC prefix must stay pi --mode rpc --no-session (got {cmd})"
        )
        assert "-p" not in cmd, f"RPC argv must omit print-mode -p (got {cmd})"
        assert not _has_long_or_short(cmd, "--no-extensions", "-ne"), (
            f"Pi spawn must load extension providers, got {cmd}"
        )
        assert _has_long_or_short(cmd, "--no-skills", "-ns"), (
            f"Lean Pi spawn requires --no-skills or -ns (got {cmd})"
        )
        _assert_pi_lean_coding_tools(cmd)
        skill_arg = _flag_value(cmd, "--skill")
        assert skill_arg is not None, (
            f"Expected --skill when skill file exists (got {cmd})"
        )
        assert Path(skill_arg) == skill_path or skill_arg.endswith(
            str(_DEVIATDD_SKILL_REL)
        ), f"--skill must point at {_DEVIATDD_SKILL_REL} (got {skill_arg!r})"

    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_rpc_lean_tools_remain_when_skill_missing(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """AC-PLAN-002: missing skill file still lists the four coding tools on RPC."""
        yaml_output = "phase: RED\nstatus: OK\n"
        jsonl_output = (
            json.dumps({"type": "agent_end", "message": {"content": yaml_output}})
            + "\n"
        ).encode("utf-8")
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (jsonl_output, b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)
        backend.invoke("test prompt", cwd=str(tmp_path))

        cmd = mock_popen.call_args[0][0]
        assert "--mode" in cmd and "rpc" in cmd and "--no-session" in cmd
        _assert_pi_lean_coding_tools(cmd)
        assert _flag_value(cmd, "--skill") is None, (
            f"Missing skill file must not add --skill (got {cmd})"
        )

    @patch("deviate.core.agent.subprocess.Popen")
    def test_claude_invoke_omits_pi_lean_tool_flags(
        self, mock_popen: MagicMock
    ) -> None:
        """AC-PLAN-002: non-Pi backends keep their argv and skip Pi lean flags."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"phase: RED\nstatus: PASS\n", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend(config=AgentConfig(backend="claude"))
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert cmd[:4] == ["claude", "-p", "--permission-mode", "auto"], (
            f"Claude argv must stay unchanged (got {cmd})"
        )
        assert "--no-extensions" not in cmd and "-ne" not in cmd
        assert "--no-skills" not in cmd and "-ns" not in cmd
        assert "--tools" not in cmd and "-t" not in cmd
        assert "--skill" not in cmd

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

    @patch("deviate.core.agent.subprocess.Popen")
    def test_invoke_rpc_aborts_on_unsupported_tool_schema(
        self, mock_popen: MagicMock
    ) -> None:
        """AC-PLAN-003: RPC blocking abort on first schema-rejection line."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"",
            b"unsupported_tool_schema tool_count_limit\n",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        config = AgentConfig(backend="pi", pi_rpc=True)
        backend = AgentBackend(config=config)
        with (
            patch("time.sleep", return_value=None) as mock_sleep,
            pytest.raises(
                AgentSubprocessError,
                match="unsupported_tool_schema|tool_count_limit",
            ),
        ):
            backend.invoke("test prompt")

        mock_proc.kill.assert_called()
        assert mock_popen.call_count == 1, (
            "schema rejection must not start EmptyOutputError manifest retry"
        )
        for call in mock_sleep.call_args_list:
            if call.args and call.args[0] == 30:
                pytest.fail("schema rejection must skip the 30s timeout retry")


class TestPiLeanSharedSkill:
    """TSK-047-03 / AC-PLAN-002 (US-047-01): Pi lean flags prefer shared skill."""

    _SHARED_REL = Path(".agents") / "skills" / "deviatdd" / "SKILL.md"

    def _write(self, root: Path, rel: Path) -> Path:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# deviatdd\n", encoding="utf-8")
        return target

    @pytest.mark.behavioral
    def test_shared_skill_preferred(self, tmp_path: Path) -> None:
        """AC-PLAN-002: both copies present resolves the shared path."""
        self._write(tmp_path, self._SHARED_REL)
        self._write(tmp_path, _DEVIATDD_SKILL_REL)
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(str(tmp_path))
        assert flags[flags.index("--skill") + 1].endswith(str(self._SHARED_REL))

    @pytest.mark.behavioral
    def test_shared_skill_only(self, tmp_path: Path) -> None:
        """AC-PLAN-002: shared copy alone injects the shared path."""
        self._write(tmp_path, self._SHARED_REL)
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(str(tmp_path))
        assert flags[flags.index("--skill") + 1].endswith(str(self._SHARED_REL))

    @pytest.mark.behavioral
    def test_legacy_fallback(self, tmp_path: Path) -> None:
        """AC-PLAN-002: single-Pi layout keeps the legacy path."""
        self._write(tmp_path, _DEVIATDD_SKILL_REL)
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(str(tmp_path))
        assert flags[flags.index("--skill") + 1].endswith(str(_DEVIATDD_SKILL_REL))

    @pytest.mark.behavioral
    def test_no_skill_flag_when_missing(self, tmp_path: Path) -> None:
        """AC-PLAN-002: neither copy emits no --skill flag."""
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(str(tmp_path))
        assert "--skill" not in flags

    @pytest.mark.behavioral
    def test_lean_flag_sequence_preserved(self, tmp_path: Path) -> None:
        """AC-PLAN-002: --tools plus --no-skills sequence stays intact."""
        self._write(tmp_path, self._SHARED_REL)
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(str(tmp_path))
        assert flags[:3] == ["--tools", ",".join(_CODING_TOOLS), "--no-skills"]

    @pytest.mark.behavioral
    def test_cwd_none_defaults_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-PLAN-002: cwd=None resolves the shared copy under cwd."""
        self._write(tmp_path, self._SHARED_REL)
        monkeypatch.chdir(tmp_path)
        from deviate.core.agent import _pi_lean_flags as lean

        flags = lean(None)
        assert flags[flags.index("--skill") + 1].endswith(str(self._SHARED_REL))
