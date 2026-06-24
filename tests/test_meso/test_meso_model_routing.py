from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestMesoInvokeAgentPhaseModelResolution:
    """Verify meso.py _invoke_agent_phase resolves model per-phase.

    AC-ADHOC-005-04: Droid backend uses model flag.
    AC-ADHOC-005-08: TDD cycle uses phase-specific models.
    """

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_invoke_agent_calls_resolve_model(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.meso import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\ndefault = "fast/model"\n')

        _invoke_agent_phase("PLAN", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "fast/model"

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_invoke_agent_model_none_when_no_config(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.meso import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }

        _invoke_agent_phase("PLAN", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") is None

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_invoke_agent_respects_phase_override(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.meso import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\ndefault = "fast/model"\nplan = "premium/model"\n')

        _invoke_agent_phase("PLAN", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "premium/model"

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_invoke_agent_phase_is_passed(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The phase constant is passed to resolve_model_for_phase."""
        from deviate.cli.meso import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\nTASKS = "custom/model"\n')

        _invoke_agent_phase("TASKS", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") == "custom/model"

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_invoke_agent_uses_droid_backend_from_config(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        """AC-ADHOC-005-06: Meso respects agent backend from config.toml."""
        from deviate.cli.meso import _invoke_agent_phase

        mock_cwd.return_value = tmp_path
        mock_build.return_value = "test prompt"
        mock_invoke.return_value = MagicMock(status="PASS")

        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }

        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[agent]\nbackend = "droid"\n')

        _invoke_agent_phase("PLAN", contract)

        mock_invoke.assert_called_once()
        _, kwargs = mock_invoke.call_args
        assert kwargs.get("model") is None
