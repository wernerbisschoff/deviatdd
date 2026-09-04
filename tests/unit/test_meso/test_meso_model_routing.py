from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console


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
    def test_invoke_diagnostics_require_verbose(
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
        contract = {"issue_id": "ISS-001-001"}

        normal_buf = StringIO()
        verbose_buf = StringIO()
        with patch(
            "deviate.cli.meso.console",
            Console(file=normal_buf, force_terminal=False),
        ):
            _invoke_agent_phase("PLAN", contract)
        with patch(
            "deviate.cli.meso.console",
            Console(file=verbose_buf, force_terminal=False),
        ):
            _invoke_agent_phase("PLAN", contract, verbose=True)

        assert "INVOKE_AGENT" not in normal_buf.getvalue()
        assert "INVOKE_AGENT" in verbose_buf.getvalue()

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


class TestMesoInvokeAgentPhaseBackendAliasResolution:
    """Regression: user-facing backend aliases (``factory``) are normalised
    to canonical backends (``droid``) before
    :class:`~deviate.state.config.AgentConfig` is constructed.

    ``omp`` is a canonical backend (not an alias), so it reaches
    ``AgentConfig`` unchanged — the test for it lives in
    :class:`TestOmpBackendRegistration` (it asserts the canonical
    ``omp -p`` command, not just the Literal).

    Without this resolution, ``AgentConfig(backend="factory")`` would
    fail Pydantic Literal validation (the Factory IDE is a user-facing
    alias, not a dispatch backend) and the ``deviate`` meso pipeline
    would abort before the agent is invoked. The canonical home for
    the resolution is
    :func:`deviate.core.agent.resolve_agent_to_backend`.
    """

    @patch("deviate.cli.meso.Path.cwd")
    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_codex_reasoning_effort_reaches_agent_config(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        mock_cwd: MagicMock,
        tmp_path: Path,
    ) -> None:
        """``[agent].reasoning_effort`` is forwarded on the Codex meso path."""
        with patch("deviate.cli.meso.AgentBackend") as MockBackend:
            mock_inst = MagicMock()
            mock_inst.invoke.return_value = MagicMock(status="PASS")
            MockBackend.return_value = mock_inst
            from deviate.cli.meso import _invoke_agent_phase

            mock_cwd.return_value = tmp_path
            mock_build.return_value = "test prompt"

            dot = tmp_path / ".deviate"
            dot.mkdir(parents=True)
            (dot / "config.toml").write_text(
                '[agent]\nbackend = "codex"\nreasoning_effort = "high"\n',
                encoding="utf-8",
            )

            _invoke_agent_phase(
                "PLAN",
                {
                    "issue_id": "ISS-001-001",
                    "issue_title": "Test",
                    "epic_slug": "test-epic",
                },
            )

        _, call_kwargs = MockBackend.call_args
        cfg = call_kwargs["config"]
        assert cfg.backend == "codex"
        assert cfg.reasoning_effort == "high"
