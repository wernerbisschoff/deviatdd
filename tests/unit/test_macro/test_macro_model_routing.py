from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestMacroInvokeAgentPhaseModelResolution:
    """Verify macro.py _invoke_agent_phase resolves model per-phase.

    AC-ADHOC-005-03: No config section -> no model flag.
    AC-ADHOC-005-08: TDD cycle uses phase-specific models with default fallback.
    """

    @patch("deviate.cli.macro.Path.cwd")
    @patch("deviate.cli.macro.AgentBackend.invoke")
    @patch("deviate.cli.macro._build_slim_prompt")
    def test_invoke_agent_calls_resolve_model(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.macro import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {"phase": "research", "target": "001-test-feature"}

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\nresearch = "research/model"\n')

        _invoke_agent_phase("research", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "research/model"

    @patch("deviate.cli.macro.Path.cwd")
    @patch("deviate.cli.macro.AgentBackend.invoke")
    @patch("deviate.cli.macro._build_slim_prompt")
    def test_invoke_agent_model_none_when_no_config(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.macro import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {"phase": "explore", "target": "001-test-feature"}

        _invoke_agent_phase("explore", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") is None

    @patch("deviate.cli.macro.Path.cwd")
    @patch("deviate.cli.macro.AgentBackend.invoke")
    @patch("deviate.cli.macro._build_slim_prompt")
    def test_invoke_agent_uses_default(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.macro import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {"phase": "shard", "target": "001-test-feature"}

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\ndefault = "default/model"\n')

        _invoke_agent_phase("shard", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "default/model"

    @patch("deviate.cli.macro.Path.cwd")
    @patch("deviate.cli.macro.AgentBackend.invoke")
    @patch("deviate.cli.macro._build_slim_prompt")
    def test_invoke_agent_phase_name_passed_to_resolve(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.macro import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {"phase": "explore", "target": "001-test-feature"}

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\nexplore = "explore/model"\n')

        _invoke_agent_phase("explore", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "explore/model"
