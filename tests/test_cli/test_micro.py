from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from deviate.cli.__init__ import cli
from deviate.cli.micro import _run_judge_phase, PhaseFailedError
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState, resolve_model_for_phase
from deviate.state.ledger import TaskRecord, append_task_transition
from deviate.ui.monitor import OrchestrationMonitor
from tests.conftest import _git_env


runner = CliRunner()


E2E_ISSUE_ID = "ISS-E2E-001"
E2E_EPIC = "adhoc"
E2E_SLUG = "e2e-pipeline"


def _setup_issue_ledger(
    root: Path, issue_id: str, epic: str, slug: str, tasks: list[dict]
) -> None:
    issues_dir = root / "specs"
    issues_dir.mkdir(exist_ok=True)
    (issues_dir / "issues.jsonl").write_text(
        json.dumps(
            {"issue_id": issue_id, "source_file": f"specs/{epic}/{slug}/spec.md"}
        )
        + "\n",
        encoding="utf-8",
    )
    feature_dir = issues_dir / epic / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    with open(feature_dir / "tasks.jsonl", "w") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")
    tasks_md = ["# Tasks\n", "\n"]
    for task in tasks:
        tasks_md.append(f"- {task['id']}: {task['description']}\n")
    (feature_dir / "tasks.md").write_text("".join(tasks_md), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec", encoding="utf-8")


def _setup_session(root: Path, issue_id: str) -> None:
    dot_dir = root / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    session = SessionState(active_issue_id=issue_id)
    session.save(dot_dir / "session.json")


class TestResolveAgentConfigBackendAlias:
    """Regression: ``_resolve_agent_config`` normalises user-facing backend
    aliases (``factory``) to canonical backends (``droid``) before the
    value reaches the dispatch layer. ``omp`` is canonical and passes
    through unchanged.

    Before the fix, ``--agent omp`` (or ``backend = "omp"`` in
    ``.deviate/config.toml``) was returned to ``_invoke_agent`` raw with
    ``backend="omp"`` tripping Pydantic Literal validation — aborting
    the ``deviate run`` pipeline before any agent invocation. ``omp``
    is now widened into the ``AgentConfig.backend`` Literal as a
    first-class backend. The canonical home for the resolution is
    :func:`deviate.core.agent.resolve_agent_to_backend`.
    """

    def test_cli_arg_omp_passes_through_as_canonical(self, tmp_path: Path) -> None:
        """`--agent omp` from the CLI must return ``omp`` (canonical,
        not aliased to ``pi``)."""
        from deviate.cli.micro import _resolve_agent_config

        assert _resolve_agent_config(tmp_path, "omp") == "omp"

    def test_cli_arg_factory_resolves_to_droid(self, tmp_path: Path) -> None:
        """`--agent factory` from the CLI must return ``droid``."""
        from deviate.cli.micro import _resolve_agent_config

        assert _resolve_agent_config(tmp_path, "factory") == "droid"

    def test_cli_arg_canonical_passes_through(self, tmp_path: Path) -> None:
        """Canonical backend names pass through unchanged."""
        from deviate.cli.micro import _resolve_agent_config

        for canonical in ("opencode", "claude", "droid", "pi", "omp"):
            assert _resolve_agent_config(tmp_path, canonical) == canonical

    def test_config_toml_omp_passes_through_as_canonical(self, tmp_path: Path) -> None:
        """``backend = "omp"`` in ``.deviate/config.toml`` must return ``omp``."""
        from deviate.cli.micro import _resolve_agent_config

        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('[agent]\nbackend = "omp"\n')

        assert _resolve_agent_config(tmp_path, None) == "omp"

    def test_config_toml_factory_resolves_to_droid(self, tmp_path: Path) -> None:
        """``backend = "factory"`` in config.toml must return ``droid``."""
        from deviate.cli.micro import _resolve_agent_config

        dot = tmp_path / ".deviate"
        dot.mkdir()
        (dot / "config.toml").write_text('[agent]\nbackend = "factory"\n')

        assert _resolve_agent_config(tmp_path, None) == "droid"

    def test_config_toml_canonical_passes_through(self, tmp_path: Path) -> None:
        """Canonical backends in config.toml pass through unchanged."""
        from deviate.cli.micro import _resolve_agent_config

        dot = tmp_path / ".deviate"
        dot.mkdir()

        for canonical in ("opencode", "claude", "droid", "pi", "omp"):
            (dot / "config.toml").write_text(f'[agent]\nbackend = "{canonical}"\n')
            assert _resolve_agent_config(tmp_path, None) == canonical

    def test_no_config_returns_none(self, tmp_path: Path) -> None:
        """No config file and no CLI arg → None (dispatch falls back to default)."""
        from deviate.cli.micro import _resolve_agent_config

        assert _resolve_agent_config(tmp_path, None) is None


class TestPytestReportConfig:
    def test_default_values(self):
        from deviate.state.config import PytestReportConfig

        config = PytestReportConfig()
        assert config.json_report is False

    def test_extra_fields_forbidden(self):
        from pydantic import ValidationError
        from deviate.state.config import PytestReportConfig

        with pytest.raises(ValidationError):
            PytestReportConfig(json_report=True, unknown_field="value")


class TestRunPytestJsonReport:
    @patch("deviate.cli.micro._is_pytest_json_report_available", return_value=True)
    @patch("deviate.cli.micro.subprocess.run")
    def test_report_enabled_appends_json_report_flag(self, mock_run, mock_available):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = PytestReportConfig(json_report=True)
        _run_pytest(root=Path("."), report_config=config)
        args = mock_run.call_args[0][0]
        assert "--json-report" in args

    @patch("deviate.cli.micro.subprocess.run")
    def test_report_disabled_no_json_report_flag(self, mock_run):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = PytestReportConfig(json_report=False)
        _run_pytest(root=Path("."), report_config=config)
        args = mock_run.call_args[0][0]
        assert "--json-report" not in args

    @patch("deviate.cli.micro.subprocess.run")
    def test_fallback_when_plugin_missing(self, mock_run):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="AssertionError: assert False", stderr=""
        )
        config = PytestReportConfig(json_report=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _run_pytest(root=Path("."), report_config=config)
        plugin_warnings = [
            x for x in w if "pytest-json-report" in str(x.message).lower()
        ]
        assert len(plugin_warnings) > 0


ISSUE_ID = "ISS-TEST-MON"
EPIC = "adhoc"
SLUG = "monitor-int"


class TestRunAllMonitorIntegration:
    """OrchestrationMonitor wiring in `deviate run --all`."""

    @pytest.fixture
    def env(self, tmp_git_repo: Path) -> Path:
        tasks = [
            {
                "id": "TSK-001-01",
                "issue_id": ISSUE_ID,
                "description": "Test task 1",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
        ]
        _setup_issue_ledger(tmp_git_repo, ISSUE_ID, EPIC, SLUG, tasks)
        _setup_session(tmp_git_repo, ISSUE_ID)
        return tmp_git_repo

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_creates_monitor_in_run_all(
        self,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env)
        mock_invoke_agent.return_value = (
            HandoverManifest(phase="RED", status="SUCCESS"),
            "",
        )
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_monitor = MagicMock(spec=OrchestrationMonitor)
        with patch("deviate.cli.micro.OrchestrationMonitor", return_value=mock_monitor):
            result = runner.invoke(cli, ["micro", "run", "--all"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_monitor.__enter__.assert_called_once()
        assert mock_monitor.push_event.called
        mock_monitor.__exit__.assert_called_once()

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_json_flag_toggles_monitor_mode(
        self,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env)
        mock_invoke_agent.return_value = (
            HandoverManifest(phase="RED", status="SUCCESS"),
            "",
        )
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = runner.invoke(cli, ["micro", "run", "--all", "--json"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert '"event":' in result.output

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_non_tty_uses_text_output(
        self,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env)
        mock_invoke_agent.return_value = (
            HandoverManifest(phase="RED", status="SUCCESS"),
            "",
        )
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = runner.invoke(cli, ["micro", "run", "--all"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "TSK-001-01" in result.output
        assert '"event":' not in result.output

    @patch("deviate.cli.micro._invoke_agent")
    def test_interrupt_during_run_all(
        self, mock_invoke_agent: MagicMock, env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(env)
        mock_invoke_agent.side_effect = KeyboardInterrupt()
        mock_monitor = MagicMock(spec=OrchestrationMonitor)
        with patch("deviate.cli.micro.OrchestrationMonitor", return_value=mock_monitor):
            result = runner.invoke(cli, ["micro", "run", "--all"])
        assert mock_monitor.signal_keyboard_interrupt.called
        assert result.exit_code == 130


def _build_e2e_tasks() -> list[dict]:
    return [
        {
            "id": "TSK-001-01",
            "issue_id": E2E_ISSUE_ID,
            "description": "Implement monitor core state machine",
            "status": "PENDING",
            "execution_mode": "TDD",
        },
        {
            "id": "TSK-001-02",
            "issue_id": E2E_ISSUE_ID,
            "description": "Implement render functions with buffer",
            "status": "PENDING",
            "execution_mode": "TDD",
        },
        {
            "id": "TSK-001-03",
            "issue_id": E2E_ISSUE_ID,
            "description": "Wire monitor into deviate run",
            "status": "PENDING",
            "execution_mode": "TDD",
        },
    ]


class TestRunAllMonitorE2E:
    @pytest.fixture
    def env3(self, tmp_git_repo: Path) -> Path:
        _setup_issue_ledger(
            tmp_git_repo, E2E_ISSUE_ID, E2E_EPIC, E2E_SLUG, _build_e2e_tasks()
        )
        _setup_session(tmp_git_repo, E2E_ISSUE_ID)
        return tmp_git_repo

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_run_all_with_live_display_agent_output(
        self,
        mock_load_skill: MagicMock,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env3: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env3)
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_load_skill.return_value = "# Dummy skill content"

        def invoke_side_effect(
            prompt: str,
            c: object,
            backend_name: str = "opencode",
            task_id: str = "",
            phase: str = "",
            output_callback: object = None,
            **kwargs: object,
        ) -> tuple[HandoverManifest | None, str]:
            if output_callback is not None:
                output_callback(f"[{phase}] Starting {task_id}...")
                output_callback(f"[{phase}] Running tests for {task_id}...")
                output_callback(f"[{phase}] All done for {task_id}!")
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["micro", "run", "--all", "--json", "--verbose"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        all_lines = [line for line in result.output.splitlines() if line.strip()]
        events = [json.loads(line) for line in all_lines if line.startswith("{")]
        assert len(events) > 0, f"No JSONL events found in output: {all_lines[:5]}"
        event_types = [e["event"] for e in events]

        assert "task_started" in event_types, "Missing task_started events"
        assert "phase_change" in event_types, "Missing phase_change events"
        assert "agent_output" in event_types, "Missing agent_output events"
        assert "task_completed" in event_types, "Missing task_completed events"

        completed_ids = [
            e.get("id", e.get("task_id", ""))
            for e in events
            if e["event"] == "task_completed"
        ]
        assert len(completed_ids) == 3, (
            f"Expected 3 completed tasks, got {len(completed_ids)}"
        )

        assert "Traceback" not in result.output

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_agent_output_lines_in_fifo_order(
        self,
        mock_load_skill: MagicMock,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env3: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env3)
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_load_skill.return_value = "# Dummy skill content"

        emitted_lines: list[str] = []

        def invoke_side_effect(
            prompt: str,
            c: object,
            backend_name: str = "opencode",
            task_id: str = "",
            phase: str = "",
            output_callback: object = None,
            **kwargs: object,
        ) -> tuple[HandoverManifest | None, str]:
            if output_callback is not None:
                line_a = f"Line {len(emitted_lines) + 1}: {task_id} {phase} step 1"
                line_b = f"Line {len(emitted_lines) + 1}: {task_id} {phase} step 2"
                emitted_lines.append(line_a)
                emitted_lines.append(line_b)
                output_callback(line_a)
                output_callback(line_b)
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["micro", "run", "--all", "--json", "--verbose"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        all_lines = [line for line in result.output.splitlines() if line.strip()]
        events = [json.loads(line) for line in all_lines if line.startswith("{")]
        agent_output_events = [e for e in events if e["event"] == "agent_output"]

        assert len(agent_output_events) == len(emitted_lines), (
            f"Expected {len(emitted_lines)} agent_output events, "
            f"got {len(agent_output_events)}"
        )

        for emitted, event in zip(emitted_lines, agent_output_events):
            assert event.get("line") == emitted, (
                f"FIFO order violation: expected {emitted!r}, got {event.get('line')!r}"
            )

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_json_default_omits_agent_output_events(
        self,
        mock_load_skill: MagicMock,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env3: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env3)
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_load_skill.return_value = "# Dummy skill content"

        def invoke_side_effect(
            prompt: str,
            c: object,
            backend_name: str = "opencode",
            task_id: str = "",
            phase: str = "",
            output_callback: object = None,
            **kwargs: object,
        ) -> tuple[HandoverManifest | None, str]:
            if output_callback is not None:
                output_callback(f"[{phase}] {task_id} stdout line")
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["micro", "run", "--all", "--json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        all_lines = [line for line in result.output.splitlines() if line.strip()]
        events = [json.loads(line) for line in all_lines if line.startswith("{")]
        event_types = [e["event"] for e in events]

        assert "task_started" in event_types
        assert "phase_change" in event_types
        assert "task_completed" in event_types
        assert "agent_output" not in event_types, (
            "Default --json should not stream agent_output; use --verbose for full stream"
        )

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_failing_task_continues_remaining(
        self,
        mock_load_skill: MagicMock,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env3: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env3)
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_load_skill.return_value = "# Dummy skill content"

        def invoke_side_effect(
            prompt: str,
            c: object,
            backend_name: str = "opencode",
            task_id: str = "",
            phase: str = "",
            output_callback: object = None,
            **kwargs: object,
        ) -> tuple[HandoverManifest | None, str]:
            if task_id == "TSK-001-02" and phase == "RED":
                return (
                    HandoverManifest(
                        phase="RED",
                        status="FAILURE",
                        rationale="Agent returned non-zero exit code 1",
                    ),
                    "",
                )
            if output_callback is not None:
                output_callback(f"[{phase}] {task_id} running...")
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["micro", "run", "--all", "--json"])

        assert result.exit_code == 1, (
            f"Expected exit code 1 on failure, got {result.exit_code}"
        )

        all_lines = [line for line in result.output.splitlines() if line.strip()]
        events = [json.loads(line) for line in all_lines if line.startswith("{")]
        event_types = [e["event"] for e in events]

        assert "task_failed" in event_types, (
            "Expected task_failed event for failing task"
        )
        failed_events = [e for e in events if e["event"] == "task_failed"]
        assert len(failed_events) >= 1
        failed_event = failed_events[0]
        failed_id = failed_event.get("id", failed_event.get("task_id", ""))
        assert failed_id == "TSK-001-02", (
            f"Expected TSK-001-02 to fail, got {failed_id}"
        )

        assert "pipeline_halted" in event_types, (
            "Expected pipeline_halted event when task failure halts pipeline"
        )

        task_started_events = [e for e in events if e["event"] == "task_started"]
        started_ids = [e.get("id", e.get("task_id", "")) for e in task_started_events]
        assert "TSK-001-03" not in started_ids, (
            "Pipeline should halt after failure — TSK-001-03 should not start"
        )
        assert result.exit_code != 0, "Expected non-zero exit code when pipeline halts"


class TestJudgeTrainRollback:
    """US-004-ROLLBACK / US-010-HITL: JUDGE train rollback with git revert and RED boundary."""

    def _setup_judge_env(self, root: Path) -> tuple[dict, Path, Path, Path]:
        """Setup session, ledger, and task state for judge phase tests."""
        dot_dir = root / ".deviate"
        dot_dir.mkdir(exist_ok=True)
        session = SessionState(active_issue_id="ISS-002-005")
        session_path = dot_dir / "session.json"
        session.save(session_path)

        ledger_dir = (
            root / "specs" / "002-deviatdd-gap-analysis" / "005-micro-layer-integrity"
        )
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "tasks.jsonl"
        task = {
            "id": "TSK-005-05",
            "issue_id": "ISS-002-005",
            "description": "Test train rollback",
            "execution_mode": "TDD",
        }
        record = TaskRecord(**task)
        append_task_transition(record, ledger_path)

        return task, ledger_path, session_path, dot_dir

    def _setup_git_repo_with_green_commits(self, root: Path) -> tuple[str, list[str]]:
        """Create git history: [initial] → RED → GREEN1 → GREEN2.

        Returns (red_sha, green_shas).
        """
        red_file = root / "feature.py"
        red_file.write_text("def feature(): pass")
        subprocess.run(
            ["git", "add", "."],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        green1_file = root / "feature_test.py"
        green1_file.write_text("def test_feature(): pass")
        subprocess.run(
            ["git", "add", "."],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        green1_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        green2_file = root / "refactor.py"
        green2_file.write_text("def refactored(): pass")
        subprocess.run(
            ["git", "add", "."],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): GREEN refactor"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        green2_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        return red_sha, [green1_sha, green2_sha]

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_rollback_resets_to_red_sha(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_git_repo
        monkeypatch.chdir(root)

        red_sha, green_shas = self._setup_git_repo_with_green_commits(root)
        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)

        mock_skill.return_value = "# JUDGE skill content"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="Compliance violation",
            ),
            "",
        )

        from rich.console import Console

        c = Console()

        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        session_after = SessionState.load(session_path)
        assert session_after.current_phase == "GREEN", (
            f"Expected GREEN phase after rollback, got {session_after.current_phase}"
        )
        assert session_after.train_feedback == "Compliance violation"

        # Rollback resets to red_sha — ALL green commits are discarded,
        # not just the last one.  Only RED and initial commits survive.
        assert not (root / "refactor.py").exists(), (
            "GREEN2 commit's file must be discarded after rollback to red_sha"
        )
        assert not (root / "feature_test.py").exists(), (
            "GREEN1 commit's file must be discarded after rollback to red_sha"
        )
        assert (root / "feature.py").exists(), (
            "RED-introduced file must be preserved after rollback"
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        assert red_sha[:7] in log_after, (
            "RED commit must remain in git history after rollback"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_feedback_preserved_across_rejection_rounds(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Round 2 rollback must NOT destroy Round 1's judge feedback commit."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → seed tasks.md (meso) → RED → GREEN
        #
        # tasks.md is committed BEFORE the RED phase so the JUDGE
        # ``git reset --hard <red_sha>`` rollback preserves it (matching
        # production where the meso layer writes tasks.md via
        # ``commit_artifact`` ahead of the micro RED phase).
        (root / "specs").mkdir(exist_ok=True)
        (root / "specs" / "constitution.md").write_text("# constitution\n")
        tasks_dir = (
            root / "specs" / "002-deviatdd-gap-analysis" / "005-micro-layer-integrity"
        )
        tasks_dir.mkdir(parents=True, exist_ok=True)
        tasks_md = tasks_dir / "tasks.md"
        tasks_md.write_text("- [ ] TSK-005-05: The task\n")
        issues_path = root / "specs" / "issues.jsonl"
        issues_path.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-002-005",
                    "source_file": "specs/002-deviatdd-gap-analysis/005-micro-layer-integrity/005-micro-layer-integrity.md",
                }
            )
            + "\n"
        )
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore(tasks): seed tasks.md (meso layer)"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        # Now RED (failing test) — the RED boundary the JUDGE rollback targets.
        red_file = root / "feature.py"
        red_file.write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        # GREEN (passing implementation) — the JUDGE rollback target.
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        # Session + ledger (lives in .deviate, gitignored, fine to leave untracked).
        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)
        from rich.console import Console

        c = Console()

        # --- Round 1: judge rejects with next_action=revert_to_red (explicit) ---
        mock_skill.return_value = "# JUDGE skill"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="Missing error handling",
                next_action="revert_to_red",
            ),
            "",
        )

        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # Verify: rollback killed GREEN, feedback committed, boundary advanced
        s1 = SessionState.load(session_path)
        assert s1.current_phase == "GREEN"
        assert s1.train_feedback == "Missing error handling"
        assert s1.red_commit_sha != red_sha, (
            "red_commit_sha must advance past the feedback commit"
        )
        rev_list_count = subprocess.run(
            ["git", "rev-list", "--count", f"{red_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert int(rev_list_count) > 0, (
            f"expected feedback commit past red_sha; rev-list counted {rev_list_count}"
        )
        fb1_sha = s1.red_commit_sha
        assert "Missing error handling" in tasks_md.read_text(), (
            "Round 1 feedback must appear in tasks.md"
        )
        green2_file = root / "impl2.py"
        green2_file.write_text("def impl2(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN retry"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="Still wrong",
                next_action="revert_to_red",
            ),
            "",
        )

        session2 = SessionState.load(session_path)
        session2.red_commit_sha = fb1_sha
        _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session2,
            session_path=session_path,
            c=c,
        )

        # Verify: Round 1 feedback survives Round 2 rollback
        s2 = SessionState.load(session_path)
        assert s2.current_phase == "GREEN"
        tasks_content = tasks_md.read_text()
        assert "Missing error handling" in tasks_content, (
            "Round 1 judge feedback must survive Round 2 rollback"
        )
        assert "Still wrong" in tasks_content, (
            "Round 2 judge feedback must be present in tasks.md"
        )
        # RED file still exists
        assert (root / "feature.py").exists(), (
            "RED-introduced file must survive both rollbacks"
        )
        # Round 2 GREEN killed
        assert not (root / "impl2.py").exists(), (
            "Round 2 GREEN file must be discarded after rollback"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_rejection_advances_red_boundary_across_cycles(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rejection must advance ``red_commit_sha`` past the feedback
        commit AND the next cycle must not repeatedly reset to the original
        RED SHA.

        Regression for b54e585 (``fix(judge): 4-way rollback routing via
        HandoverManifest.next_action``): prior to the fix, the boundary
        advance was gated on ``tasks.md`` existing. The no-task-board case
        left the runner pinned at the original RED baseline — every
        GREEN attempt re-ran the same failing test and the loop was
        un-stuckable. The fix decouples the commit from the tasks.md write
        so the boundary advances on every rejection regardless.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → RED → GREEN.  No ``tasks.md`` is written so the
        # runner takes the no-task-board path that the buggy code skipped.
        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        mock_skill.return_value = "# JUDGE skill"

        from rich.console import Console

        c = Console()

        # --- Round 1: rejection with feedback (no tasks.md) -------------
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="missing error path",
                next_action="revert_to_red",
            ),
            "",
        )

        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result1 = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # Contract 1: red_commit_sha advanced past the feedback commit —
        # NOT pinned to the original RED SHA.  This is the exact assertion
        # the b54e585 fix enables.
        assert result1.red_commit_sha != red_sha, (
            f"red_commit_sha must advance past the feedback commit; "
            f"got {result1.red_commit_sha[:7]}, original {red_sha[:7]}"
        )
        fb1_sha = result1.red_commit_sha

        # Contract 2: phase transitions to GREEN so the next cycle can
        # retry the GREEN phase from the advanced boundary.
        assert result1.current_phase == "GREEN", (
            f"rejection must transition to GREEN for retry; got {result1.current_phase}"
        )

        # Sanity: a feedback commit really did land past red_sha.
        rev_list_count = subprocess.run(
            ["git", "rev-list", "--count", f"{red_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert int(rev_list_count) > 0, (
            f"feedback commit must exist past red_sha; rev-list count={rev_list_count}"
        )

        # Contract 3: the advanced boundary persists on disk — the next
        # TDD cycle sees the NEW red_commit_sha, not the original.
        reloaded = SessionState.load(session_path)
        assert reloaded.red_commit_sha == fb1_sha, (
            f"session must persist the advanced red_commit_sha; "
            f"disk has {reloaded.red_commit_sha[:7]}, expected {fb1_sha[:7]}"
        )

        # --- Round 2: another rejection cycle ----------------------------
        # Land a fresh GREEN retry commit so the rollback has something
        # to discard.
        (root / "impl2.py").write_text("def impl2(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN retry"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="still wrong",
                next_action="revert_to_red",
            ),
            "",
        )

        # Reload from disk — the next cycle does NOT inherit any
        # in-memory state.  This is what catches a runner that advances
        # the boundary in memory but forgets to persist it.
        session2 = SessionState.load(session_path)
        result2 = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session2,
            session_path=session_path,
            c=c,
        )

        # Contract 4: the SECOND rejection did NOT reset the boundary to
        # the original RED SHA — the runner kept advancing on every
        # rejection rather than re-running the same baseline forever.
        assert result2.red_commit_sha != red_sha, (
            f"second rejection must not reset red_commit_sha to the original "
            f"RED SHA {red_sha[:7]}; got {result2.red_commit_sha[:7]}"
        )
        # And the boundary advanced AGAIN past the first feedback commit —
        # the runner is not stuck at the first-feedback SHA either.
        assert result2.red_commit_sha != fb1_sha, (
            f"second rejection must advance red_commit_sha again, not stay "
            f"pinned at the first feedback commit {fb1_sha[:7]}; "
            f"got {result2.red_commit_sha[:7]}"
        )
        assert result2.current_phase == "GREEN", (
            f"second rejection must transition to GREEN; got {result2.current_phase}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_feedback_commit_failure_raises_phase_failed_error(
        self,
        mock_skill: MagicMock,
        mock_log: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failing ``git commit`` during the judge feedback must surface
        ``PhaseFailedError`` with the git stderr and emit
        ``FEEDBACK_COMMIT_FAILED`` — never silently leave the runner stuck.

        Regression: defends the ``commit_result.returncode != 0`` branch
        introduced when the feedback commit was decoupled from the tasks.md
        write. Without the branch, a hook-denied or otherwise failing commit
        would silently leave ``red_commit_sha`` at the rejected baseline —
        every subsequent GREEN attempt would re-run the same failing test
        forever because the boundary never advanced past the rejection.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        red_sha, _ = self._setup_git_repo_with_green_commits(root)
        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)

        mock_skill.return_value = "# JUDGE skill content"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="missing error path",
                next_action="revert_to_red",
            ),
            "",
        )

        fake_stderr = (
            "fatal: refusing to create feedback commit (pre-commit hook denied)"
        )

        # Capture the real subprocess.run BEFORE entering the patch context so
        # the side_effect can pass non-commit git invocations through to the
        # real git binary while still intercepting the feedback commit.
        real_run = subprocess.run

        def _fail_commit(argv, *args, **kwargs):
            if (
                isinstance(argv, (list, tuple))
                and len(argv) >= 2
                and argv[0] == "git"
                and argv[1] == "commit"
            ):
                return subprocess.CompletedProcess(
                    args=list(argv),
                    returncode=1,
                    stdout="",
                    stderr=fake_stderr,
                )
            return real_run(argv, *args, **kwargs)

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha

        with patch("deviate.cli.micro.subprocess.run", side_effect=_fail_commit):
            with pytest.raises(PhaseFailedError) as excinfo:
                _run_judge_phase(
                    task=task,
                    ledger_path=ledger_path,
                    session=session,
                    session_path=session_path,
                    c=c,
                )

        # Contract 1: the git stderr must surface in the exception message so
        # the operator can diagnose the underlying git-level cause rather
        # than seeing a generic "feedback commit failed".
        assert fake_stderr in str(excinfo.value), (
            f"PhaseFailedError message must include git stderr; got: {excinfo.value}"
        )

        # Contract 2: the FEEDBACK_COMMIT_FAILED event must be emitted so the
        # per-task transcript captures the failure for post-mortem triage.
        log_event_names = [call.args[0] for call in mock_log.call_args_list]
        assert "FEEDBACK_COMMIT_FAILED" in log_event_names, (
            f"_log_run must be called with FEEDBACK_COMMIT_FAILED; got {log_event_names}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_rollback_preserves_red(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_git_repo
        monkeypatch.chdir(root)

        red_sha, _ = self._setup_git_repo_with_green_commits(root)
        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)

        mock_skill.return_value = "# JUDGE skill content"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="FAILURE",
                rationale="Violation",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        assert red_sha[:7] in log_after, (
            "RED commit SHA must still appear in git log after rollback"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_no_violation_proceeds(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_git_repo
        monkeypatch.chdir(root)

        self._setup_git_repo_with_green_commits(root)
        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)

        mock_skill.return_value = "# JUDGE skill content"
        mock_invoke.return_value = (
            HandoverManifest(phase="JUDGE", status="SUCCESS"),
            "",
        )

        log_before = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        assert result.current_phase == "JUDGE", (
            f"Expected JUDGE phase on clean pass, got {result.current_phase}"
        )

        log_after = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout
        assert log_before == log_after, (
            "git log must be unchanged when no violation detected"
        )

    # ----- Four-scenario action routing (JUDGE.next_action drives rollback) -----

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_revert_before_resets_past_red(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """next_action=revert_before resets past RED so the task retries from scratch."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → RED → GREEN
        red_file = root / "feature.py"
        red_file.write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        mock_skill.return_value = "# JUDGE skill"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="Implementation drifted from spec",
                next_action="revert_before",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # Both RED and GREEN must be discarded — running this task again from RED.
        assert not (root / "feature.py").exists(), (
            "revert_before must discard RED's introduced file"
        )
        assert not (root / "impl.py").exists(), (
            "revert_before must discard GREEN's introduced file"
        )
        # red_commit_sha must be cleared so the cycle restarts cleanly.
        assert result.red_commit_sha == "", (
            f"red_commit_sha must be cleared after revert_before; got {result.red_commit_sha!r}"
        )
        assert result.current_phase == "RED", (
            f"after revert_before the phase must transition to RED; got {result.current_phase}"
        )
        assert result.train_feedback, (
            "REDRestart must carry the judge feedback into RED's next attempt"
        )
        # HEAD should sit at the initial empty commit (parent of red_sha).
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        red_parent_sha = subprocess.run(
            ["git", "rev-parse", f"{red_sha}^"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert head_sha == red_parent_sha, (
            f"HEAD must equal red_sha^ ({red_parent_sha}); got {head_sha}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_revert_to_red_advances_red_commit_sha(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """next_action=revert_to_red: discard GREEN, advance red_commit_sha to feedback commit."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → RED → GREEN
        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        # tasks.md so feedback persistence + advance path runs
        # tasks.md tracked BEFORE RED so JUDGE rollback preserves it.
        tasks_dir = (
            root / "specs" / "002-deviatdd-gap-analysis" / "005-micro-layer-integrity"
        )
        tasks_dir.mkdir(parents=True, exist_ok=True)
        (tasks_dir / "tasks.md").write_text("- [ ] TSK-005-05: The task\n")
        issues_path = root / "specs" / "issues.jsonl"
        issues_path.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-002-005",
                    "source_file": (
                        "specs/002-deviatdd-gap-analysis/005-micro-layer-integrity"
                        "/005-micro-layer-integrity.md"
                    ),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "specs" / "constitution.md").write_text("# constitution\n")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore(tasks): seed tasks.md (meso layer)"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        mock_skill.return_value = "# JUDGE skill"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="missing error path",
                next_action="revert_to_red",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # GREEN killed, RED kept.
        assert (root / "feature.py").exists(), "RED file preserved"
        assert not (root / "impl.py").exists(), "GREEN file discarded"
        # Feedback commit exists past RED.
        rev_list_count = subprocess.run(
            ["git", "rev-list", "--count", f"{red_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert int(rev_list_count) > 0, (
            f"feedback commit must exist past red_sha; got count {rev_list_count}"
        )
        # red_commit_sha advanced to the feedback commit.
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert result.red_commit_sha == head_sha, (
            f"red_commit_sha must equal HEAD ({head_sha}); got {result.red_commit_sha}"
        )
        assert result.current_phase == "GREEN", (
            f"revert_to_red transitions to GREEN; got {result.current_phase}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_continue_refactor_skips_rollback_and_preserves_green(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """next_action=continue_refactor: GREEN already good, route straight to REFACTOR."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → RED → GREEN
        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        pre_judge_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        mock_skill.return_value = "# JUDGE skill"
        # Verdict is a passing one — judge accepts GREEN, but the refactor phase
        # should still be entered.
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_PASS",
                rationale="looks clean; refactor opportunity exists",
                next_action="continue_refactor",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # GREEN must not have been rolled back.
        assert (root / "impl.py").exists(), (
            "continue_refactor must preserve GREEN's file"
        )
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert head_after == pre_judge_head, (
            f"continue_refactor must not move HEAD; before {pre_judge_head}, after {head_after}"
        )
        assert not result.judge_rejected, (
            "continue_refactor is not a rejection; judge_rejected must stay False"
        )
        assert result.pending_judge_action == "continue_refactor", (
            f"pending_judge_action must record the routing; got {result.pending_judge_action!r}"
        )
        # Session phase must announce intent to continue (REFACTOR); the runner hands
        # control to _finish_tdd_cycle which reads pending_judge_action next.
        assert result.current_phase in ("REFACTOR", "JUDGE"), (
            f"continue_refactor must transition to REFACTOR (or leave JUDGE for the "
            f"caller); got {result.current_phase}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_skip_refactor_marks_task_completed(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """next_action=skip_refactor: JUDGE passes; runner marks the task COMPLETED."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial → RED → GREEN
        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        mock_skill.return_value = "# JUDGE skill"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_PASS",
                next_action="skip_refactor",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # GREEN preserved, no rolling rollback, task marked COMPLETED in ledger.
        assert (root / "impl.py").exists(), "skip_refactor must preserve GREEN"
        assert result.pending_judge_action == "skip_refactor", (
            f"pending_judge_action must record skip_refactor; got {result.pending_judge_action!r}"
        )
        assert not result.judge_rejected, "skip_refactor is not a rejection"
        # session phase signals completion; runner + _finish_tdd_cycle read it.
        assert result.current_phase in ("IDLE", "COMPLETED"), (
            f"skip_refactor must move the phase to IDLE (or COMPLETED); got {result.current_phase}"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_judge_default_action_on_violation_is_revert_to_red(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing next_action on violation defaults to revert_to_red (backward compat)."""
        root = tmp_git_repo
        monkeypatch.chdir(root)

        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        (root / "impl.py").write_text("def impl(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(TSK-005-05): GREEN phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        task, ledger_path, session_path, _ = self._setup_judge_env(root)
        # Manifest omits next_action entirely — runner must default.
        mock_skill.return_value = "# JUDGE skill"
        mock_invoke.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                rationale="missing",
            ),
            "",
        )

        from rich.console import Console

        c = Console()
        session = SessionState.load(session_path)
        session.red_commit_sha = red_sha
        result = _run_judge_phase(
            task=task,
            ledger_path=ledger_path,
            session=session,
            session_path=session_path,
            c=c,
        )

        # Same outcome as explicit revert_to_red.
        assert (root / "feature.py").exists(), "RED preserved under default action"
        assert not (root / "impl.py").exists(), "GREEN discarded under default action"
        assert result.current_phase == "GREEN", (
            f"default action must transition to GREEN; got {result.current_phase}"
        )
        assert result.red_commit_sha != red_sha, (
            "default action must advance red_commit_sha past the feedback commit"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_pre_red_sha_uses_red_parent_subject_match(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_resolve_pre_red_sha returns red_commit_sha^ when its subject matches
        the RED-phase convention (``test(<scope>): RED phase``).
        """
        from deviate.cli.micro import _resolve_pre_red_sha

        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Git: initial (subject="initial") → RED (subject="test(TSK-005-05): RED phase")
        red_file = root / "feature.py"
        red_file.write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-005-05): RED phase"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        resolved = _resolve_pre_red_sha(root, red_sha)
        expected_parent = subprocess.run(
            ["git", "rev-parse", f"{red_sha}^"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert resolved == expected_parent, (
            f"expected parent {expected_parent}; got {resolved}"
        )

    def test_pre_red_sha_logs_warning_when_subject_does_not_match(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When red_commit_sha^'s subject isn't a RED-phase convention, log a warning
        and fall back to the safe default.
        """
        from deviate.cli.micro import _resolve_pre_red_sha

        root = tmp_git_repo
        monkeypatch.chdir(root)

        # Build a custom commit whose parent is NOT a RED-phase subject.
        (root / "feature.py").write_text("def feature(): pass")
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: arbitrary commit (not RED)"],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        arbitrary_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        import logging

        with caplog.at_level(logging.WARNING):
            result = _resolve_pre_red_sha(root, arbitrary_sha)
        # Result is still the parent SHA — failure here is non-fatal. The warning
        # is the operator-visible signal.
        expected_parent = subprocess.run(
            ["git", "rev-parse", f"{arbitrary_sha}^"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert result == expected_parent
        assert any(
            "PRE_RED_AMBIGUOUS" in rec.message or "ambiguous" in rec.message.lower()
            for rec in caplog.records
        ), "warning log must fire when the parent subject isn't a RED-phase convention"

    @patch("deviate.cli.micro.subprocess.run")
    def test_commit_judge_feedback_and_advance_raises_phase_failed_on_git_commit_failure(
        self,
        mock_subprocess: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``_commit_judge_feedback_and_advance`` must surface a real
        ``PhaseFailedError`` when the underlying ``git commit`` fails
        (nonzero returncode with stderr) — silently returning the
        session would leave the runner pinned at the original RED
        baseline and every subsequent rejection cycle would re-run the
        same failing GREEN attempt forever.
        """
        from rich.console import Console
        from deviate.cli.micro import _commit_judge_feedback_and_advance

        root = tmp_git_repo
        monkeypatch.chdir(root)

        task, ledger_path, session_path, dot_dir = self._setup_judge_env(root)

        # ``_commit_judge_feedback_and_advance`` issues a ``git commit``
        # whose message is first passed through ``format_commit_message``.
        # That helper calls ``git log`` via ``deviate.core.convention`` —
        # because Python's ``subprocess`` is a shared module, patching
        # ``deviate.cli.micro.subprocess.run`` also intercepts the
        # convention-module ``git log`` call.  We need three responses:
        #   1) ``git add -A``              — succeeds, no inspection.
        #   2) ``git log … --pretty=…``    — succeeds (emoji probe), no
        #      inspection — we only assert on the commit step's contract.
        #   3) ``git commit -m …``         — fails with the captured
        #      stderr so the PhaseFailedError contract is exercised.
        # A function-based ``side_effect`` makes each call self-routing
        # instead of relying on call order, which is robust to future
        # additions of helper subprocess probes in the commit path.
        commit_stderr = "fatal: unable to auto-detect email address"

        def _fake_subprocess_run(cmd, *args, **kwargs):
            if cmd[:2] == ["git", "commit"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=128,
                    stdout="",
                    stderr=commit_stderr,
                )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        mock_subprocess.side_effect = _fake_subprocess_run

        c = Console()
        session = SessionState.load(session_path)
        original_red_sha = session.red_commit_sha

        with pytest.raises(PhaseFailedError) as excinfo:
            _commit_judge_feedback_and_advance(
                root=root,
                task=task,
                feedback="missing error path",
                feedback_source="test_judge_unit",
                c=c,
                session=session,
                session_path=session_path,
            )

        # Contract: stderr surfaces in the exception so operators can
        # diagnose the underlying git failure from the PhaseFailedError
        # message alone. The task id is also carried in the message
        # because every log line under it is correlated by tid.
        assert commit_stderr in str(excinfo.value), (
            "PhaseFailedError message must include the failing git "
            f"stderr; got {excinfo.value!r}"
        )
        assert task["id"] in str(excinfo.value), (
            f"PhaseFailedError message must identify the task; got {excinfo.value!r}"
        )

        # Boundary must NOT advance when the commit failed — the runner
        # is now surfaced with a PhaseFailedError and the caller decides
        # the next move. The pre-call red_commit_sha is preserved.
        reloaded = SessionState.load(session_path)
        assert reloaded.red_commit_sha == original_red_sha, (
            "red_commit_sha must NOT advance when the feedback commit "
            f"failed; was {original_red_sha!r}, now {reloaded.red_commit_sha!r}"
        )

        # The commit step must have actually been reached — not, e.g.,
        # bailed before invoking git at all. A future refactor that
        # short-circuits the commit (and stops raising) would still
        # leave this assertion red.
        commit_calls = [
            call_args
            for call_args in mock_subprocess.call_args_list
            if call_args.args and call_args.args[0][:2] == ["git", "commit"]
        ]
        assert len(commit_calls) == 1, (
            "expected exactly one ``git commit`` invocation; "
            f"got {[ca.args[0][:2] for ca in mock_subprocess.call_args_list]}"
        )


class TestFindTaskRecord:
    """_find_task_record returns the latest (last) matching record."""

    def test_find_task_record_returns_latest_status(self, tmp_path: Path):
        from deviate.cli.micro import _find_task_record

        records = [
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "test",
                "status": "PENDING",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "test",
                "status": "RED",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "test",
                "status": "GREEN",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "test",
                "status": "JUDGE",
            },
        ]
        ledger_path = tmp_path / "specs" / "005-micro-layer" / "tasks.jsonl"
        ledger_path.parent.mkdir(parents=True)
        for r in records:
            ledger_path.open("a").write(json.dumps(r) + "\n")

        result = _find_task_record(tmp_path, "TSK-005-07")
        assert result is not None, "Expected to find the task record"
        task, ledger_file = result
        assert task["status"] == "JUDGE", (
            f"Expected latest status JUDGE, got {task['status']}"
        )
        assert ledger_file == ledger_path

    def test_find_task_record_multiple_entries_returns_last(self, tmp_path: Path):
        from deviate.cli.micro import _find_task_record

        ledger_path = tmp_path / "specs" / "adhoc" / "tasks.jsonl"
        ledger_path.parent.mkdir(parents=True)
        for r in [
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "PENDING",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "RED",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "GREEN",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "JUDGE",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "COMPLETED",
            },
        ]:
            ledger_path.open("a").write(json.dumps(r) + "\n")

        result = _find_task_record(tmp_path, "TSK-005-07")
        assert result is not None
        task, ledger_file = result
        assert task["status"] == "COMPLETED", (
            f"Expected COMPLETED as last record, got {task['status']}"
        )


ISSUE_005 = "ISS-ADH-005"
SLUG_005 = "005-per-phase-model-configuration"


class TestPhaseModelRouting:
    """AC-ADHOC-005-08: each TDD phase uses its configured model."""

    @pytest.fixture
    def env(self, tmp_git_repo: Path) -> Path:
        tasks = [
            {
                "id": "TSK-005-01",
                "issue_id": ISSUE_005,
                "description": "Add ModelPhaseMap model",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
        ]
        _setup_issue_ledger(tmp_git_repo, ISSUE_005, "adhoc", SLUG_005, tasks)
        _setup_session(tmp_git_repo, ISSUE_005)

        dot_dir = tmp_git_repo / ".deviate"
        config_path = dot_dir / "config.toml"
        config_path.write_text(
            '[models]\ndefault = "fast/model"\njudge = "premium/model"\n'
        )
        return tmp_git_repo

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_phase_routes_model(
        self,
        mock_load_skill: MagicMock,
        mock_invoke_agent: MagicMock,
        mock_verify: MagicMock,
        mock_run_test: MagicMock,
        mock_run_format: MagicMock,
        env: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(env)
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_load_skill.return_value = "# Dummy skill content"

        call_log: list[dict] = []

        def invoke_side_effect(
            prompt: str,
            c: object,
            backend_name: str = "opencode",
            task_id: str = "",
            phase: str = "",
            output_callback: object = None,
            model: str | None = None,
        ) -> tuple[HandoverManifest | None, str]:
            call_log.append(
                {
                    "phase": phase,
                    "model": model,
                    "backend": backend_name,
                    "task_id": task_id,
                }
            )
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["micro", "run", "--all", "--json"])

        assert result.exit_code == 0

        red_calls = [c for c in call_log if c["phase"] == "RED"]
        assert len(red_calls) > 0
        assert red_calls[0]["model"] == "fast/model", (
            f"RED should use default model, got {red_calls[0]['model']}"
        )

        judge_calls = [c for c in call_log if c["phase"] == "JUDGE"]
        assert len(judge_calls) > 0
        assert judge_calls[0]["model"] == "premium/model", (
            f"JUDGE should use premium/model, got {judge_calls[0]['model']}"
        )


class TestPhaseModelUnitResolution:
    """Per-phase model resolution via resolve_model_for_phase (unit level).

    AC-ADHOC-005-08: TDD cycle uses phase-specific models with default
    fallback. These tests verify the resolution function directly,
    independent of CLI integration.
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

    def test_phase_not_in_dict_falls_back_to_default(
        self, config_default_only: Path
    ) -> None:
        """Phase not in models dict and default exists -> uses default."""
        assert resolve_model_for_phase("PLAN", config_default_only) == "fast/model"

    def test_explore_phase_gets_default(self, config_with_models: Path) -> None:
        """EXPLORE phase not in dict -> uses default."""
        assert resolve_model_for_phase("EXPLORE", config_with_models) == "fast/model"


class TestModelPassedToInvokeAgent:
    """Verify the resolved model is passed to _invoke_agent.

    Unlike TestTddCycleIntegration which only checks resolve_model_for_phase
    is called, these tests verify the returned model value flows through
    to the _invoke_agent call.
    """

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._find_test_files")
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._commit_phase")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_red_invoke_agent_receives_model(
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
        mock_resolve.return_value = "red/specific-model"
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
        _, invoke_kwargs = mock_agent.call_args
        assert invoke_kwargs.get("model") == "red/specific-model", (
            f"Expected model='red/specific-model' in _invoke_agent call, "
            f"got {invoke_kwargs.get('model')}"
        )

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_invoke_agent_receives_model(
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
        mock_resolve.return_value = "judge/specific-model"
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
        _, invoke_kwargs = mock_agent.call_args
        assert invoke_kwargs.get("model") == "judge/specific-model", (
            f"Expected model='judge/specific-model' in _invoke_agent call, "
            f"got {invoke_kwargs.get('model')}"
        )


class TestTddCycleIntegration:
    """Verify each TDD phase runner calls resolve_model_for_phase.

    Uses patch to trace calls to resolve_model_for_phase from each
    phase runner, confirming the correct phase constant is passed.
    """

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
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
    @patch("deviate.cli.micro._log_run")
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
            HandoverManifest(
                phase="GREEN", status="PASS", task_id="TSK-005-03", files=["src/x.py"]
            ),
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
    @patch("deviate.cli.micro._log_run")
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
    @patch("deviate.cli.micro._log_run")
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


class TestCommitPhaseConventionFormatting:
    """Verify _commit_phase applies format_commit_message before git commit."""

    def test_commit_phase_prepends_emoji_when_repo_uses_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """When the repo has emoji commits, _commit_phase formats the message."""
        from deviate.cli.micro import _commit_phase

        # Seed git history with an emoji commit so detect_uses_emojis returns True
        seed = tmp_git_repo / "seed.txt"
        seed.write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "seed.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        # Create a new file so _commit_phase has something to commit
        new_file = tmp_git_repo / "impl.py"
        new_file.write_text("x = 1\n", encoding="utf-8")

        result = _commit_phase("feat(T001): add implementation", tmp_git_repo)

        assert result is True
        log = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert log.stdout == "✨ feat(T001): add implementation"

    def test_commit_phase_leaves_plain_message_when_no_emoji_convention(
        self, tmp_git_repo: Path
    ) -> None:
        """When the repo has no emoji commits, _commit_phase passes message as-is."""
        from deviate.cli.micro import _commit_phase

        new_file = tmp_git_repo / "impl.py"
        new_file.write_text("x = 1\n", encoding="utf-8")

        result = _commit_phase("feat(T001): add implementation", tmp_git_repo)

        assert result is True
        log = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert log.stdout == "feat(T001): add implementation"

    def test_commit_phase_red_phase_test_uses_siren_emoji(
        self, tmp_git_repo: Path
    ) -> None:
        """RED-phase `test:` commit routed through _commit_phase uses 🚨."""
        from deviate.cli.micro import _commit_phase

        seed = tmp_git_repo / "seed.txt"
        seed.write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "seed.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        new_file = tmp_git_repo / "red_test.py"
        new_file.write_text("x = 1\n", encoding="utf-8")

        result = _commit_phase(
            "test(T001): RED phase - failing test",
            tmp_git_repo,
            no_verify=True,
            phase="red",
        )

        assert result is True
        log = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert log.stdout == "🚨 test(T001): RED phase - failing test"


class TestSummarizeTimeoutContextFallback:
    """Regression: when the agent binary is missing, _summarize_timeout_context
    must return the friendly fallback message instead of letting FileNotFoundError
    propagate (which would crash the GREEN retry path)."""

    def test_missing_binary_returns_fallback_message(self) -> None:
        from deviate.cli import micro as micro_mod
        from deviate.core import agent as agent_mod

        # Register a fake backend pointing at a nonexistent binary, then
        # invoke _summarize_timeout_context with it. The function should
        # catch FileNotFoundError and return the partial-output fallback.
        fake_key = "__missing_for_test__"
        agent_mod.BACKEND_COMMANDS[fake_key] = "/nonexistent/binary -p"
        try:
            result = micro_mod._summarize_timeout_context(
                "agent emitted partial output before crashing",
                backend_name=fake_key,
            )
        finally:
            agent_mod.BACKEND_COMMANDS.pop(fake_key, None)

        assert "Partial output" in result, f"expected fallback message, got: {result!r}"
        assert "agent emitted partial output" in result, (
            "fallback should include the partial output content"
        )


class TestExecutePhaseJudgeRouting:
    """EXECUTE phase's inner JUDGE branch mirrors the four-action
    routing with ``pre_execute_sha`` as the rollback anchor (EXECUTE
    has no RED boundary). Two scenarios are pinned: the explicit
    ``revert_before`` (which collapses to ``revert_to_red`` because
    there's nothing pre-RED to revert to) and the default
    ``revert_to_red`` path. Both must roll back to ``pre_execute_sha``
    and land a feedback commit past it.

    Implements the (3) "Continue to Refactor (for cases where green
    was already implemented, **or for execute**)" arm of the user's
    ask.
    """

    @staticmethod
    def _setup_execute_env(root: Path) -> tuple[dict, Path, Path]:
        """Seed a tracked issue.md so ``_resolve_spec_md`` returns
        content and forces the inner JUDGE pass to run. EXECUTE's
        JUDGE works off the issue spec, not ``tasks.md``, so
        ``tasks.md`` is intentionally NOT seeded here — the feedback
        path will report ``TASKS_MD_SKIP`` but the git feedback commit
        + boundary advance both fire regardless, matching the
        regression-fix semantics.
        """
        issue_dir = root / "specs" / "002-deviatdd-gap-analysis" / "006-execute-routing"
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "006-execute-routing.md").write_text(
            "# EXECUTE routing regression\n\n## Acceptance\n"
        )
        (root / "specs" / "issues.jsonl").write_text(
            json.dumps(
                {
                    "issue_id": "ISS-002-006",
                    "source_file": (
                        "specs/002-deviatdd-gap-analysis/006-execute-routing"
                        "/006-execute-routing.md"
                    ),
                }
            )
            + "\n"
        )
        subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore(spec): seed issue spec for EXECUTE test"],
            cwd=root,
            env=_git_env(),
            check=True,
        )

        dot_dir = root / ".deviate"
        dot_dir.mkdir(exist_ok=True)
        session_path = dot_dir / "session.json"
        SessionState(active_issue_id="ISS-002-006").save(session_path)

        tasks_md = issue_dir / "tasks.jsonl"
        task = {
            "id": "TSK-006-01",
            "issue_id": "ISS-002-006",
            "description": "EXECUTE judge rollback routing",
            "execution_mode": "DIRECT",
        }
        return task, tasks_md, session_path

    @staticmethod
    def _build_invoke_side_effect(next_action_value: str, judge_rationale: str):
        """Build a ``mock_invoke.side_effect`` that returns success on
        EXECUTE phase calls and rejects (then raises) on JUDGE phase
        calls. Second JUDGE rejection raises ``PhaseFailedError`` to
        halt the test after the first rollback without burning the
        full 3-attempt budget.
        """
        reject_count = {"n": 0}

        def _side_effect(*args: object, **kwargs: object):
            if kwargs.get("phase") == "JUDGE":
                reject_count["n"] += 1
                if reject_count["n"] >= 2:
                    raise PhaseFailedError("stop test after first rollback")
                return (
                    HandoverManifest(
                        phase="JUDGE",
                        status="SUCCESS",
                        verdict="COMPLIANCE_VIOLATION",
                        rationale=judge_rationale,
                        next_action=next_action_value,
                    ),
                    "",
                )
            return (
                HandoverManifest(
                    phase="EXECUTE",
                    status="SUCCESS",
                    files=["impl.py"],
                ),
                "",
            )

        return _side_effect

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_execute_judge_revert_before_rolls_back_to_pre_execute_sha(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``next_action=revert_before`` on EXECUTE JUDGE: roll back to
        ``pre_execute_sha``, land a feedback commit past it, retry
        EXECUTE. Both EXECUTE rollback actions share the same anchor
        (EXECUTE has no RED boundary) — pinning the explicit
        ``revert_before`` case guards against accidental divergence.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)

        task, tasks_md, session_path = self._setup_execute_env(root)
        pre_execute_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        mock_invoke.side_effect = self._build_invoke_side_effect(
            next_action_value="revert_before",
            judge_rationale="Spec drift",
        )
        mock_skill.return_value = "# JUDGE skill"

        from rich.console import Console
        from deviate.cli.micro import _run_execute_phase

        c = Console()
        try:
            _run_execute_phase(
                task=task,
                ledger_path=tasks_md,
                c=c,
            )
        except PhaseFailedError:
            pass

        rev_list_count = subprocess.run(
            ["git", "rev-list", "--count", f"{pre_execute_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert int(rev_list_count) > 0, (
            f"feedback commit must exist past pre_execute_sha after "
            f"revert_before rejection; rev-list counted {rev_list_count}"
        )
        session_after = SessionState.load(session_path)
        assert session_after.red_commit_sha != pre_execute_sha, (
            "session.red_commit_sha must advance past pre_execute_sha "
            f"after a rollback; was still {pre_execute_sha[:7]}"
        )
        assert session_after.red_commit_sha, (
            "session.red_commit_sha must be non-empty after rollback"
        )

    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._load_skill_content")
    def test_execute_judge_revert_to_red_advances_boundary_and_retries(
        self,
        mock_skill: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``next_action=revert_to_red`` on EXECUTE JUDGE: same anchor
        as ``revert_before``, advance the boundary, retry.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)

        task, tasks_md, session_path = self._setup_execute_env(root)
        pre_execute_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()

        mock_invoke.side_effect = self._build_invoke_side_effect(
            next_action_value="revert_to_red",
            judge_rationale="Implementation drifted from spec",
        )
        mock_skill.return_value = "# JUDGE skill"

        from rich.console import Console
        from deviate.cli.micro import _run_execute_phase

        c = Console()
        try:
            _run_execute_phase(
                task=task,
                ledger_path=tasks_md,
                c=c,
            )
        except PhaseFailedError:
            pass

        rev_list_count = subprocess.run(
            ["git", "rev-list", "--count", f"{pre_execute_sha}..HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        ).stdout.strip()
        assert int(rev_list_count) > 0, (
            f"feedback commit must exist past pre_execute_sha; "
            f"rev-list counted {rev_list_count}"
        )
        session_after = SessionState.load(session_path)
        assert session_after.red_commit_sha != pre_execute_sha, (
            "session.red_commit_sha must advance past pre_execute_sha "
            "after revert_to_red rejection"
        )


class TestExecuteTaskRetryJudgeFeedbackCommitBound:
    """Regression: a failed JUDGE feedback commit must not spin the outer
    ``_execute_task_with_retry`` indefinitely.

    Inside both ``_run_tdd_cycle`` and ``_run_execute_phase``, the inner
    JUDGE rejection path commits the judge feedback via
    ``_commit_judge_feedback_and_advance``. When the ``git commit`` of
    that feedback fails (returncode != 0), that helper raises
    ``PhaseFailedError("JUDGE feedback commit failed for <tid>: ...")``
    which bubbles out of the cycle into the outer retry wrapper.

    Before this regression was pinned, a naive rewrite of the outer
    loop (e.g. ``while not done: try: dispatch(...)`` with no counter)
    would let a persistent ``FEEDBACK_COMMIT_FAILED`` retrigger the
    inner cycle forever, exhausting the git reflog and stalling the
    pipeline. The wrapper bounds the retries at exactly two
    ``_dispatch_task`` invocations and surfaces terminal failure via a
    FAILED ledger transition and a ``task_failed`` monitor event.
    """

    @staticmethod
    def _setup_retry_env(root: Path) -> tuple[dict, Path]:
        """Seed a session, a tasks.jsonl ledger, and a single PENDING
        task. The ledger pre-seed lets us verify the FAILED transition
        appends *after* an existing PENDING record."""
        dot_dir = root / ".deviate"
        dot_dir.mkdir(exist_ok=True)
        SessionState(active_issue_id="ISS-RET-007").save(dot_dir / "session.json")
        ledger_dir = root / "specs" / "retry-bound" / "007-cycle"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "tasks.jsonl"
        task = {
            "id": "TSK-007-01",
            "issue_id": "ISS-RET-007",
            "description": "Outer retry bound on JUDGE feedback commit failure",
            "execution_mode": "TDD",
            "status": "PENDING",
        }
        record = TaskRecord(**task)
        append_task_transition(record, ledger_path)
        return task, ledger_path

    @staticmethod
    def _read_task_statuses(ledger_path: Path, task_id: str) -> list[str]:
        """Return the ordered status history for ``task_id`` from the
        ledger, newest first. Mirrors the read pattern used by the
        rest of the test suite."""
        lines = [
            line
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        records = [json.loads(line) for line in lines]
        history = [r["status"] for r in records if r.get("id") == task_id]
        return history

    def test_judge_feedback_commit_failure_bounds_dispatch_and_returns_false(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The outer retry wrapper must terminate after exactly two
        ``_dispatch_task`` invocations when the inner cycle raises
        ``PhaseFailedError`` for a JUDGE feedback commit failure,
        return False, append a FAILED transition, and emit a single
        ``task_failed`` event on the monitor. Any unbound loop shape
        (call_count >= 3) is the regression symptom this test pins."""
        from rich.console import Console
        from deviate.cli.micro import _execute_task_with_retry

        root = tmp_git_repo
        monkeypatch.chdir(root)

        task, ledger_path = self._setup_retry_env(root)
        monitor = OrchestrationMonitor(Console())

        # Inner cycle raises PhaseFailedError exactly as
        # _commit_judge_feedback_and_advance does when `git commit`
        # of the docs(<tid>): judge feedback commit fails.
        def _raise_judge_feedback_commit_failure(
            *args: object, **kwargs: object
        ) -> None:
            raise PhaseFailedError(
                "JUDGE feedback commit failed for TSK-007-01: "
                "hook declined pre-commit check"
            )

        with patch(
            "deviate.cli.micro._dispatch_task",
            side_effect=_raise_judge_feedback_commit_failure,
        ) as mock_dispatch:
            result = _execute_task_with_retry(
                task=task,
                ledger_file=ledger_path,
                c=Console(),
                monitor=monitor,
                root=root,
            )

        assert result is False, (
            "_execute_task_with_retry must return False after the "
            f"second PhaseFailedError; got {result!r}"
        )
        assert mock_dispatch.call_count == 2, (
            "outer retry must bound _dispatch_task invocations at "
            "exactly 2 attempts; "
            f"got {mock_dispatch.call_count}. An unbounded retry loop "
            "would let a persistent JUDGE feedback commit failure "
            "spin the inner cycle indefinitely."
        )

        status_history = self._read_task_statuses(ledger_path, "TSK-007-01")
        assert status_history, (
            "ledger must retain the pre-seeded PENDING record plus "
            "the terminal FAILED transition appended by the wrapper"
        )
        assert status_history[-1] == "FAILED", (
            "FAILED transition must be appended as the final recorded "
            f"status after the bounded retries; got history "
            f"{status_history!r}"
        )
        assert "PENDING" in status_history, (
            "FAILED transition must append after the pre-existing "
            f"PENDING record; got {status_history!r}"
        )

        from deviate.ui.monitor import MarkdownStatus

        assert monitor.failed_count == 1, (
            "monitor must record exactly one failed task after "
            f"retry exhaustion; got failed_count={monitor.failed_count}"
        )
        tracked = monitor._tasks["TSK-007-01"]
        assert tracked.marker is MarkdownStatus.FAILED, (
            "monitor marker must transition to FAILED on the "
            f"task_failed event; got marker={tracked.marker!r}"
        )
        assert tracked.error_reason and (
            "JUDGE feedback commit failed" in tracked.error_reason
        ), (
            "monitor error_reason must surface the JUDGE feedback "
            f"commit failure message; got {tracked.error_reason!r}"
        )
