from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deviate.state.config import resolve_model_for_phase


class TestPhaseModelRouting:
    """Per-phase model resolution via resolve_model_for_phase.

    AC-ADHOC-005-08: TDD cycle uses phase-specific models with default
    fallback. Each phase runner in micro.py resolves its model via
    ``resolve_model_for_phase`` — these tests verify the resolution
    returns the expected model for each standard TDD phase.
    """

    @pytest.fixture
    def config_with_models(self, tmp_path: Path) -> Path:
        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text(
            "[models]\n"
            'default = "fast/model"\n'
            'judge = "premium/model"\n'
            'plan = "premium/model"\n'
        )
        return tmp_path

    @pytest.fixture
    def config_default_only(self, tmp_path: Path) -> Path:
        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[models]\ndefault = "fast/model"\n')
        return tmp_path

    @pytest.fixture
    def config_no_models(self, tmp_path: Path) -> Path:
        dot = tmp_path / ".deviate"
        dot.mkdir(parents=True)
        cfg = dot / "config.toml"
        cfg.write_text('[agent]\nbackend = "opencode"\n')
        return tmp_path

    def test_default_model_all_phases(self, config_with_models: Path) -> None:
        """AC-ADHOC-005-01: Default model applies to all phases."""
        assert resolve_model_for_phase("RED", config_with_models) == "fast/model"
        assert resolve_model_for_phase("GREEN", config_with_models) == "fast/model"
        assert resolve_model_for_phase("REFACTOR", config_with_models) == "fast/model"
        assert resolve_model_for_phase("EXECUTE", config_with_models) == "fast/model"

    def test_judge_override(self, config_with_models: Path) -> None:
        """AC-ADHOC-005-02: Phase override takes precedence over default."""
        assert resolve_model_for_phase("JUDGE", config_with_models) == "premium/model"
        assert resolve_model_for_phase("PLAN", config_with_models) == "premium/model"

    def test_no_config_returns_none(self, tmp_path: Path) -> None:
        """AC-ADHOC-005-03: No config.toml -> no model flag."""
        assert resolve_model_for_phase("RED", tmp_path) is None

    def test_no_models_section_returns_none(self, config_no_models: Path) -> None:
        """AC-ADHOC-005-03: [models] section absent -> no model flag."""
        assert resolve_model_for_phase("RED", config_no_models) is None

    def test_tdd_cycle_model_routing(self, config_with_models: Path) -> None:
        """AC-ADHOC-005-08: TDD cycle uses phase-specific models.

        RED -> fast/model (default)
        GREEN -> fast/model (default)
        JUDGE -> premium/model (override)
        REFACTOR -> fast/model (default)
        """
        assert resolve_model_for_phase("RED", config_with_models) == "fast/model"
        assert resolve_model_for_phase("GREEN", config_with_models) == "fast/model"
        assert resolve_model_for_phase("JUDGE", config_with_models) == "premium/model"
        assert resolve_model_for_phase("REFACTOR", config_with_models) == "fast/model"

    def test_unknown_phase_falls_back_to_default(
        self, config_with_models: Path
    ) -> None:
        """Unknown phase without explicit config -> uses default."""
        assert resolve_model_for_phase("SHARD", config_with_models) == "fast/model"

    def test_phase_not_in_dict_no_default_returns_none(
        self, config_default_only: Path
    ) -> None:
        """Phase not in models dict and default exists -> uses default."""
        assert resolve_model_for_phase("PLAN", config_default_only) == "fast/model"

    def test_yellow_phase_reuses_green_model(self, config_with_models: Path) -> None:
        """YELLOW has no explicit override -> falls back to default."""
        assert resolve_model_for_phase("YELLOW", config_with_models) == "fast/model"

    def test_explore_phase_gets_default(self, config_with_models: Path) -> None:
        """EXPLORE phase not in dict -> uses default."""
        assert resolve_model_for_phase("EXPLORE", config_with_models) == "fast/model"


class TestTddCycleIntegration:
    """Verify each TDD phase runner calls resolve_model_for_phase.

    Uses patch to trace calls to resolve_model_for_phase from each
    phase runner, confirming the correct phase constant is passed.
    """

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._save_agent_log")
    @patch("deviate.cli.micro._find_test_files")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._commit_phase")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_red_phase_calls_resolve_model(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_format: MagicMock,
        mock_done: MagicMock,
        mock_verify: MagicMock,
        mock_commit: MagicMock,
        mock_test: MagicMock,
        mock_find_tests: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_red_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_done.return_value = False
        mock_find_tests.return_value = []
        mock_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = "test/model"
        mock_agent.return_value = (
            HandoverManifest(phase="RED", status="PASS"),
            "",
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123", stderr=""
        )

        task = {
            "id": "TSK-005-03",
            "issue_id": "ISS-ADH-005",
            "description": "test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_red_phase(task, ledger_path, session, session_path, Console())

        mock_resolve.assert_called_once_with("RED", cwd)

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._save_agent_log")
    @patch("deviate.cli.micro._find_test_files")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._commit_phase")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_green_phase_calls_resolve_model(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_format: MagicMock,
        mock_done: MagicMock,
        mock_verify: MagicMock,
        mock_commit: MagicMock,
        mock_test: MagicMock,
        mock_find_tests: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_green_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_done.return_value = False
        mock_find_tests.return_value = []
        mock_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = "test/model"
        mock_agent.return_value = (
            HandoverManifest(phase="GREEN", status="PASS"),
            "",
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123", stderr=""
        )

        task = {
            "id": "TSK-005-03",
            "issue_id": "ISS-ADH-005",
            "description": "test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_green_phase(task, ledger_path, session, session_path, Console())

        mock_resolve.assert_called_once_with("GREEN", cwd)

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._save_agent_log")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_phase_calls_resolve_model(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = "premium/model"
        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        task = {
            "id": "TSK-005-03",
            "issue_id": "ISS-ADH-005",
            "description": "test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        mock_resolve.assert_called_once_with("JUDGE", cwd)

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._save_agent_log")
    @patch("deviate.cli.micro._find_test_files")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._commit_phase")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_refactor_phase_calls_resolve_model(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_format: MagicMock,
        mock_done: MagicMock,
        mock_verify: MagicMock,
        mock_commit: MagicMock,
        mock_test: MagicMock,
        mock_find_tests: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_refactor_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_done.return_value = False
        mock_find_tests.return_value = []
        mock_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = "test/model"
        mock_agent.return_value = (
            HandoverManifest(phase="REFACTOR", status="PASS"),
            "",
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123", stderr=""
        )

        task = {
            "id": "TSK-005-03",
            "issue_id": "ISS-ADH-005",
            "description": "test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_refactor_phase(task, ledger_path, session, session_path, Console())

        mock_resolve.assert_called_once_with("REFACTOR", cwd)


def Console() -> MagicMock:  # noqa: N802
    return MagicMock()
