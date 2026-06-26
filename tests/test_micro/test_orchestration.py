from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _mock_invoke_agent(*args, **kwargs):
    """Mock _invoke_agent to return a valid manifest for testing."""
    return HandoverManifest(
        phase=kwargs.get("phase", "RED"),
        status="SUCCESS",
        task_id=kwargs.get("task_id", "TSK-000-00"),
    ), ""


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "Test TDD task",
    status: str = "PENDING",
    execution_mode: str = "TDD",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description,
        status=status,
        execution_mode=execution_mode,
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


class TestMicroOrchestration:
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_single_task_full_cycle(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="Full cycle orchestration task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" in result.output
            assert "GREEN" in result.output
            assert "COMPLETED" in result.output

            session_data = json.loads(
                (dot_dir / "session.json").read_text(encoding="utf-8")
            )
            assert session_data.get("current_phase") == "IDLE", (
                f"Expected session to be IDLE after full cycle, got {session_data}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_session_tracks_active_phase(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-02",
                issue_id="ISS-001-004",
                description="Session tracking task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            runner.invoke(cli, ["run", "TSK-004-01"])

            session_data = json.loads(
                (dot_dir / "session.json").read_text(encoding="utf-8")
            )
            assert session_data.get("last_command") == "run TSK-004-01", (
                f"Expected last_command to be set, got {session_data}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_no_judge_flag(self, mock_agent, mock_verify, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-03",
                issue_id="ISS-001-004",
                description="No judge flag task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "--no-judge", "TSK-004-03"])

            assert result.exit_code == 0, (
                f"Expected --no-judge flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "JUDGE" not in result.output, (
                f"JUDGE phase should be skipped with --no-judge: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_no_refactor_flag(self, mock_agent, mock_verify, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-04",
                issue_id="ISS-001-004",
                description="No refactor flag task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "--no-refactor", "TSK-004-04"])

            assert result.exit_code == 0, (
                f"Expected --no-refactor flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "REFACTOR" not in result.output, (
                f"REFACTOR phase should be skipped with --no-refactor: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_agent_flag(self, mock_agent, mock_verify, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-05",
                issue_id="ISS-001-004",
                description="Agent flag task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "--agent", "droid", "TSK-004-05"])

            assert result.exit_code == 0, (
                f"Expected --agent flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to complete with --agent: {result.output}"
            )

    def test_yellow_not_in_phase_map(self):
        from deviate.cli.micro import _PHASE_MAP

        assert "YELLOW" not in _PHASE_MAP, (
            "YELLOW must not be in _PHASE_MAP — "
            "it should be invoked from the cycle loop body, not the map"
        )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_ledger_updates_on_each_phase(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-06",
                issue_id="ISS-001-004",
                description="Ledger tracking task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            runner.invoke(cli, ["run", "TSK-004-06"])

            ledger_lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
            statuses = [json.loads(line).get("status") for line in ledger_lines if line]

            assert "PENDING" in statuses, (
                f"Expected PENDING in ledger statuses: {statuses}"
            )
            assert "JUDGE" in statuses, f"Expected JUDGE in ledger statuses: {statuses}"
            assert "RED" in statuses, (
                "RED status is now written directly by _run_red_phase"
            )
            assert "GREEN" in statuses, (
                "GREEN status is now written directly by _run_green_phase"
            )
            assert "COMPLETED" in statuses, (
                "COMPLETED status is now written directly by _run_refactor_phase"
            )

    def _mock_yellow_approved_manifest(*args, **kwargs):
        phase = kwargs.get("phase", "RED")
        tid = kwargs.get("task_id", "TSK-005-04")
        if phase == "GREEN":
            return HandoverManifest(
                phase="GREEN",
                status="SUCCESS",
                task_id=tid,
                yellow_trigger=True,
            ), ""
        if phase == "YELLOW":
            return HandoverManifest(
                phase="YELLOW",
                status="SUCCESS",
                task_id=tid,
            ), ""
        return HandoverManifest(phase=phase, status="SUCCESS", task_id=tid), ""

    def _mock_yellow_rejected_manifest(*args, **kwargs):
        phase = kwargs.get("phase", "RED")
        tid = kwargs.get("task_id", "TSK-005-04")
        if phase == "GREEN":
            return HandoverManifest(
                phase="GREEN",
                status="SUCCESS",
                task_id=tid,
                yellow_trigger=True,
            ), ""
        if phase == "YELLOW":
            return HandoverManifest(
                phase="YELLOW",
                status="SUCCESS",
                verdict="REJECTED",
                task_id=tid,
                rationale="Amendments rejected — test changes invalid",
            ), ""
        return HandoverManifest(phase=phase, status="SUCCESS", task_id=tid), ""

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch(
        "deviate.cli.micro._invoke_agent",
        side_effect=_mock_yellow_approved_manifest,
    )
    def test_tdd_cycle_yellow_approved_continues_to_judge(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-04",
                issue_id="ISS-002-005",
                description="YELLOW approved continues to JUDGE",
                status="PENDING",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-04"])

            assert "YELLOW" in result.output, (
                f"Expected YELLOW phase in output: {result.output}"
            )
            assert "JUDGE" in result.output, (
                f"Expected JUDGE phase after YELLOW: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch(
        "deviate.cli.micro._invoke_agent",
        side_effect=_mock_yellow_rejected_manifest,
    )
    def test_tdd_cycle_yellow_rejected_re_runs_green(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-04",
                issue_id="ISS-002-005",
                description="YELLOW rejected re-runs GREEN",
                status="PENDING",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-04"])

            assert "YELLOW" in result.output, (
                f"Expected YELLOW phase in output: {result.output}"
            )
            assert "YELLOW_REJECTED" in result.output, (
                f"Expected YELLOW_REJECTED in output: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_all_processes_all_pending(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task_a = _make_task_record(
                task_id="TSK-004-07",
                issue_id="ISS-001-004",
                description="First --all task",
                status="PENDING",
            )
            task_b = _make_task_record(
                task_id="TSK-004-08",
                issue_id="ISS-001-004",
                description="Second --all task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task_a, task_b)

            result = runner.invoke(cli, ["run", "--all"])

            assert result.exit_code == 0, (
                f"Expected exit 0 for --all, got {result.exit_code}: {result.output}"
            )
            assert result.output.count("COMPLETED") >= 2, (
                f"Expected both tasks to reach COMPLETED: {result.output}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_all_retry_once_then_abort(self, mock_agent, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            failing_task = _make_task_record(
                task_id="TSK-004-09",
                issue_id="ISS-001-004",
                description="Failing task for retry test",
                status="PENDING",
            )
            good_task = _make_task_record(
                task_id="TSK-004-10",
                issue_id="ISS-001-004",
                description="Good task that should not run",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, failing_task, good_task)

            result = runner.invoke(cli, ["run", "--all"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit when a task fails twice: {result.output}"
            )
            ledger_lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
            statuses = [json.loads(line).get("status") for line in ledger_lines if line]
            assert statuses.count("FAILED") >= 1, (
                f"Expected at least one FAILED status: {statuses}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_judge_rejection_triggers_green_retry(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        """JUDGE_REJECTED must not skip GREEN on TRAIN retry.

        Regression test: the _phase_already_done ledger check in
        _run_green_phase was blocking re-runs after JUDGE_REJECTED
        because the GREEN ledger entry was never removed on rejection.
        Now _run_green_phase checks session.train_feedback and runs
        regardless of the ledger when feedback is present.
        """
        call_log: list[str] = []

        def _judge_reject_once(*args, **kwargs):
            phase = kwargs.get("phase", "")
            call_log.append(phase)
            tid = kwargs.get("task_id", "TSK-004-11")
            if phase == "JUDGE":
                judge_count = sum(1 for p in call_log if p == "JUDGE")
                if judge_count == 1:
                    return HandoverManifest(
                        phase="JUDGE",
                        status="SUCCESS",
                        verdict="COMPLIANCE_VIOLATION",
                        task_id=tid,
                        rationale="Incomplete — missing required logic",
                        train_feedback="Implement the missing logic per spec",
                    ), ""
            return HandoverManifest(
                phase=phase,
                status="SUCCESS",
                task_id=tid,
            ), ""

        mock_agent.side_effect = _judge_reject_once

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-11",
                issue_id="ISS-001-004",
                description="Judge reject + train retry",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            Path("README.md").write_text("# test\n")
            subprocess.run(
                ["git", "add", "."],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: setup"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["run", "TSK-004-11"])

            assert "JUDGE_REJECTED" in result.output, (
                f"Expected JUDGE_REJECTED: {result.output}"
            )
            assert "TRAIN" in result.output, f"Expected TRAIN retry: {result.output}"
            assert "GREEN →" in result.output.split("TRAIN")[-1], (
                "GREEN must re-run during TRAIN retry after rejection"
            )
            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_judge_rejection_with_empty_feedback_reroutes_to_green(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        """JUDGE_REJECTED with empty rationale/train_feedback must still reroute to GREEN.

        Regression: when the judge returned ``COMPLIANCE_VIOLATION`` with empty
        rationale AND empty train_feedback, the reroute condition
        ``if session.train_feedback or green_tests_failed`` evaluated False
        (empty string is falsy), so the loop exited and REFACTOR ran on a
        rejected implementation. The fix is to key the reroute on
        ``session.judge_rejected`` (always set on COMPLIANCE_VIOLATION),
        independent of feedback text content.
        """
        call_log: list[str] = []

        def _judge_reject_with_empty_feedback(*args, **kwargs):
            phase = kwargs.get("phase", "")
            call_log.append(phase)
            tid = kwargs.get("task_id", "TSK-004-12")
            if phase == "JUDGE":
                judge_count = sum(1 for p in call_log if p == "JUDGE")
                if judge_count == 1:
                    return HandoverManifest(
                        phase="JUDGE",
                        status="SUCCESS",
                        verdict="COMPLIANCE_VIOLATION",
                        task_id=tid,
                        rationale=None,
                        train_feedback=None,
                    ), ""
            return HandoverManifest(
                phase=phase,
                status="SUCCESS",
                task_id=tid,
            ), ""

        mock_agent.side_effect = _judge_reject_with_empty_feedback

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-12",
                issue_id="ISS-001-004",
                description="Judge reject with empty feedback must reroute",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            Path("README.md").write_text("# test\n")
            subprocess.run(
                ["git", "add", "."],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: setup"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["run", "TSK-004-12"])

            assert "JUDGE_REJECTED" in result.output, (
                f"Expected JUDGE_REJECTED: {result.output}"
            )
            assert "TRAIN" in result.output, (
                f"Expected TRAIN retry despite empty feedback: {result.output}"
            )
            assert "GREEN →" in result.output.split("TRAIN")[-1], (
                "GREEN must re-run on empty-feedback rejection"
            )
            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )


class TestYellowHandoffContract:
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_tdd_cycle_inlines_yellow_gate(
        self, mock_invoke, mock_verify, tmp_git_repo: Path
    ):
        def _mock_green_yellow_trigger(*args, **kwargs):
            phase = kwargs.get("phase", "RED")
            tid = kwargs.get("task_id", "TSK-005-04")
            if phase == "GREEN":
                return HandoverManifest(
                    phase="GREEN",
                    status="SUCCESS",
                    task_id=tid,
                    yellow_trigger=True,
                ), ""
            return HandoverManifest(phase=phase, status="SUCCESS", task_id=tid), ""

        mock_invoke.side_effect = _mock_green_yellow_trigger

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-04",
                issue_id="ISS-002-005",
                description="YELLOW inline gate test",
                status="PENDING",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-04"])

            assert "YELLOW" in result.output, (
                f"Expected YELLOW between GREEN and JUDGE: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_run_yellow_phase_helper_returns_decision(
        self, mock_invoke, mock_verify, tmp_git_repo: Path
    ):
        from deviate.cli.micro import _run_yellow_phase
        from rich.console import Console

        mock_invoke.return_value = (
            HandoverManifest(
                phase="YELLOW",
                status="SUCCESS",
                task_id="TSK-005-04",
            ),
            "",
        )

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="GREEN")
            session_path = dot_dir / "session.json"
            session.save(session_path)

            task = {
                "id": "TSK-005-04",
                "issue_id": "ISS-002-005",
                "description": "Test YELLOW phase helper return",
            }
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            ledger_path.parent.mkdir(parents=True)

            c = Console()

            result = _run_yellow_phase(
                task, ledger_path, session, session_path, c, agent="opencode"
            )

            assert isinstance(result, tuple), (
                f"_run_yellow_phase should return a tuple, got {type(result)}"
            )
            assert len(result) == 2, (
                f"Expected 2-element tuple, got {len(result)} elements"
            )
            assert isinstance(result[0], SessionState), (
                f"First element should be SessionState, got {type(result[0])}"
            )
            assert result[1] in (
                "approved",
                "rejected",
            ), f"Second element should be 'approved' or 'rejected', got '{result[1]}'"

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._run_test_cmd")
    def test_green_phase_test_failure_captures_train_feedback(
        self, mock_run_test, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="FAILED test_green_fail\n1 failed",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-99",
                issue_id="ISS-001-004",
                description="Test failure capture",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            Path("README.md").write_text("# repo\n")
            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: init"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["run", "TSK-004-99"])

            assert result.exit_code == 0, (
                f"Expected zero exit when GREEN recovers from test failure, "
                f"got exit {result.exit_code}: {result.output}"
            )
