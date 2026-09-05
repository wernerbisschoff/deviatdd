from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

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


class TestPiPrintModeOnly:
    """ISS-ADH-048 / AC-PLAN-001: ``pi -p`` is the only Pi transport.

    The RPC branch (``PI_RPC_COMMAND``, ``_invoke_rpc_blocking``, ``use_rpc``)
    is removed. Every Pi invoke spawns print mode. A legacy ``pi_rpc=True``
    flag is ignored at this layer and still spawns ``pi -p``.
    """

    @pytest.mark.behavioral
    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_invoke_spawns_print_mode(self, mock_popen: MagicMock) -> None:
        """AC-PLAN-001: default Pi invoke spawns ``pi -p`` without RPC flags."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"phase: RED\nstatus: OK\n", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        backend = AgentBackend(config=AgentConfig(backend="pi"))
        backend.invoke("test prompt")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pi", f"Expected first argv 'pi', got {cmd[0]!r}"
        assert cmd[1] == "-p", f"Expected print-mode '-p', got {cmd}"
        assert "--mode" not in cmd, f"Print mode must not contain --mode (got {cmd})"
        assert "rpc" not in cmd, f"Print mode must not contain rpc (got {cmd})"
        assert "--no-session" not in cmd, (
            f"Print mode must not contain --no-session (got {cmd})"
        )

    @pytest.mark.behavioral
    def test_legacy_pi_rpc_flag_rejected(self) -> None:
        """AC-PLAN-002: legacy ``pi_rpc=True`` fails validation (print mode only)."""
        with pytest.raises(ValidationError):
            AgentConfig(backend="pi", pi_rpc=True)  # type: ignore[call-arg]

    @pytest.mark.behavioral
    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_print_lean_spawn_flags(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """AC-PLAN-001: print-mode argv keeps the lean tool policy after ``pi -p``."""
        skill_path = tmp_path / _DEVIATDD_SKILL_REL
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# deviatdd\n", encoding="utf-8")

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"phase: RED\nstatus: OK\n", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        AgentBackend(config=AgentConfig(backend="pi")).invoke(
            "test prompt", cwd=str(tmp_path)
        )

        cmd = mock_popen.call_args[0][0]
        assert cmd[:2] == ["pi", "-p"], f"Print prefix must stay pi -p (got {cmd})"
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

    @pytest.mark.behavioral
    def test_no_pi_rpc_command_symbol(self) -> None:
        """AC-PLAN-001: ``PI_RPC_COMMAND`` no longer exists on the agent module."""
        import deviate.core.agent as agent_mod

        assert not hasattr(agent_mod, "PI_RPC_COMMAND"), (
            "PI_RPC_COMMAND must be removed; pi -p is the only Pi transport"
        )

    @pytest.mark.behavioral
    def test_no_invoke_rpc_blocking(self) -> None:
        """AC-PLAN-001: ``AgentBackend._invoke_rpc_blocking`` is removed."""
        assert not hasattr(AgentBackend, "_invoke_rpc_blocking"), (
            "_invoke_rpc_blocking must be removed; Pi always calls _invoke_streaming"
        )

    @pytest.mark.behavioral
    def test_agent_source_has_zero_rpc_tokens(self) -> None:
        """AC-PLAN-001: no RPC dispatch token remains in ``src/deviate/core/agent.py``."""
        src = Path("src/deviate/core/agent.py").read_text(encoding="utf-8")
        for token in ("PI_RPC_COMMAND", "_invoke_rpc_blocking", "use_rpc"):
            assert token not in src, (
                f"RPC token {token!r} must be removed from agent.py"
            )

    @pytest.mark.behavioral
    @patch("deviate.core.agent.subprocess.Popen")
    def test_claude_invoke_omits_pi_lean_tool_flags(
        self, mock_popen: MagicMock
    ) -> None:
        """Preservation: non-Pi backends keep their argv and skip Pi lean flags."""
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

    @pytest.mark.behavioral
    @patch("deviate.core.agent.subprocess.Popen")
    def test_pi_missing_binary_still_raises(self, mock_popen: MagicMock) -> None:
        """Preservation: a missing ``pi`` binary uses the existing spawn error path."""
        from deviate.core.agent import AgentBinaryNotFoundError

        mock_popen.side_effect = FileNotFoundError("pi")
        with pytest.raises(AgentBinaryNotFoundError):
            AgentBackend(config=AgentConfig(backend="pi")).invoke("test prompt")


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
