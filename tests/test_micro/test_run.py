from __future__ import annotations

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


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-007",
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


class TestRunCommand:
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_dispatches_tdd_task_to_rgr(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-007",
                description="Implement TDD task",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-004-01"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to reach COMPLETED state: {result.output}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_dispatches_immediate_task_to_execute(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-02",
                issue_id="ISS-001-007",
                description="Implement immediate task",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-004-02"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" not in result.output
            assert "COMPLETED" in result.output, (
                f"Expected immediate task to reach COMPLETED: {result.output}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_all_iterates_mixed_modes(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            tdd_task = _make_task_record(
                task_id="TSK-004-03",
                issue_id="ISS-001-007",
                description="TDD task",
                status="PENDING",
                execution_mode="TDD",
            )
            imm_task = _make_task_record(
                task_id="TSK-004-04",
                issue_id="ISS-001-007",
                description="Immediate task",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, tdd_task, imm_task)

            result = runner.invoke(cli, ["run", "--all"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert result.output.count("COMPLETED") >= 2, (
                f"Expected all tasks to reach COMPLETED: {result.output}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_accepts_legacy_TNNN_format(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-05",
                issue_id="ISS-001-001",
                description="Legacy format task",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "001-initial" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-004-05"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected TSK-004-05 task to reach COMPLETED: {result.output}"
            )

    def test_run_unknown_task_id_exits_not_found(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["run", "TSK-999-99"])
            assert result.exit_code != 0, (
                f"Expected non-zero exit for unknown task, got {result.output}"
            )
            assert "TASK_NOT_FOUND" in result.output or "NOT_FOUND" in result.output

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_with_profile_fast(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Profile flag test",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-001-03", "--profile", "fast"])
            assert result.exit_code == 0, (
                f"Expected exit code 0 with --profile fast, got {result.exit_code}: {result.output}"
            )
            assert "JUDGE" not in result.output, (
                f"Expected JUDGE skipped with --profile fast: {result.output}"
            )
            assert "REFACTOR" not in result.output, (
                f"Expected REFACTOR skipped with --profile fast: {result.output}"
            )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_with_flag_overrides(self, mock_agent, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Profile flag overrides",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)

            result = runner.invoke(
                cli,
                ["run", "TSK-001-03", "--profile", "fast", "--no-judge"],
            )
            assert result.exit_code == 0, (
                f"Expected exit code 0 with override, got {result.exit_code}: {result.output}"
            )

    def test_run_with_profile_invalid(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Invalid profile",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-001-03", "--profile", "invalid"])
            assert result.exit_code != 0, (
                f"Expected non-zero exit for invalid profile, got {result.exit_code}: {result.output}"
            )
            assert "Invalid value" in result.output, (
                f"Expected 'Invalid value' in output: {result.output}"
            )

    def test_run_skips_already_completed_task(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-06",
                issue_id="ISS-001-007",
                description="Already done",
                status="COMPLETED",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-004-06"])
            assert result.exit_code == 0, result.output
            assert "TASK_ALREADY_DONE" in result.output, (
                f"Expected TASK_ALREADY_DONE warning: {result.output}"
            )


class TestSessionResume:
    """Session-phase resume: _run_single dispatches from session.current_phase."""

    _RESUME_MANIFEST = HandoverManifest(
        phase="JUDGE", status="SUCCESS", task_id="TSK-005-07"
    )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_run_resumes_from_judge(self, mock_agent, mock_verify, tmp_git_repo: Path):
        mock_agent.return_value = (self._RESUME_MANIFEST, "")
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="JUDGE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Resume from JUDGE",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-07"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" not in result.output, (
                f"Session resume from JUDGE must skip RED phase: {result.output}"
            )
            assert "JUDGE" in result.output, (
                f"Expected JUDGE phase in output: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_run_resumes_from_yellow(self, mock_agent, mock_verify, tmp_git_repo: Path):
        mock_agent.return_value = (self._RESUME_MANIFEST, "")
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="YELLOW")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Resume from YELLOW",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-07"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" not in result.output, (
                f"Session resume from YELLOW must skip RED phase: {result.output}"
            )
            assert "YELLOW" in result.output, (
                f"Expected YELLOW phase in output: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_task_already_done_triggers_for_yellow_latest(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        mock_agent.return_value = (self._RESUME_MANIFEST, "")
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Already done with YELLOW",
                status="YELLOW",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-07"])
            assert result.exit_code == 0, result.output
            assert "TASK_ALREADY_DONE" in result.output, (
                f"Expected TASK_ALREADY_DONE for YELLOW-latest task: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_task_already_done_triggers_for_judge_latest(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        mock_agent.return_value = (self._RESUME_MANIFEST, "")
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Already done with JUDGE",
                status="JUDGE",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["run", "TSK-005-07"])
            assert result.exit_code == 0, result.output
            assert "TASK_ALREADY_DONE" in result.output, (
                f"Expected TASK_ALREADY_DONE for JUDGE-latest task: {result.output}"
            )
