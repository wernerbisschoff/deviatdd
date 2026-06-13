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
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_single_task_full_cycle(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_session_tracks_active_phase(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_no_judge_flag(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_no_refactor_flag(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_agent_flag(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_ledger_updates_on_each_phase(self, mock_agent, tmp_git_repo: Path):
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
            assert "RED" in statuses, f"Expected RED in ledger statuses: {statuses}"
            assert "GREEN" in statuses, f"Expected GREEN in ledger statuses: {statuses}"
            assert "COMPLETED" in statuses, (
                f"Expected COMPLETED in ledger statuses: {statuses}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_all_processes_all_pending(self, mock_agent, tmp_git_repo: Path):
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

    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_judge_rejection_triggers_green_retry(
        self, mock_agent, tmp_git_repo: Path
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
                        status="FAILURE",
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
            assert "GREEN already done" not in result.output, (
                "GREEN must NOT be skipped during TRAIN retry after rejection:\n"
                f"{result.output}"
            )
            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
