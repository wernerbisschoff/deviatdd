from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from deviate.cli.__init__ import cli
from deviate.cli.micro import _run_judge_phase
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
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
            result = runner.invoke(cli, ["run", "--all"])
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
        result = runner.invoke(cli, ["run", "--all", "--json"])
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
        result = runner.invoke(cli, ["run", "--all"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Processing" in result.output
        assert '"event":' not in result.output

    @patch("deviate.cli.micro._invoke_agent")
    def test_interrupt_during_run_all(
        self, mock_invoke_agent: MagicMock, env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(env)
        mock_invoke_agent.side_effect = KeyboardInterrupt()
        mock_monitor = MagicMock(spec=OrchestrationMonitor)
        with patch("deviate.cli.micro.OrchestrationMonitor", return_value=mock_monitor):
            result = runner.invoke(cli, ["run", "--all"])
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
        ) -> tuple[HandoverManifest | None, str]:
            if output_callback is not None:
                output_callback(f"[{phase}] Starting {task_id}...")
                output_callback(f"[{phase}] Running tests for {task_id}...")
                output_callback(f"[{phase}] All done for {task_id}!")
            return (HandoverManifest(phase=phase, status="SUCCESS"), "")

        mock_invoke_agent.side_effect = invoke_side_effect

        result = runner.invoke(cli, ["run", "--all", "--json"])

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

        result = runner.invoke(cli, ["run", "--all", "--json"])

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

        result = runner.invoke(cli, ["run", "--all", "--json"])

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
    def test_judge_train_rollback_all_commits_since_red(
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

        assert not (root / "feature_test.py").exists(), (
            "GREEN-introduced file must be discarded after hard reset"
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
                "status": "YELLOW",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "first",
                "status": "YELLOW_APPROVED",
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
