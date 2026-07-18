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
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_single_task_full_cycle(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            result = runner.invoke(cli, ["micro", "run", "TSK-004-01"])

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

            runner.invoke(cli, ["micro", "run", "TSK-004-01"])

            session_data = json.loads(
                (dot_dir / "session.json").read_text(encoding="utf-8")
            )
            assert session_data.get("last_command") == "micro run TSK-004-01", (
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

            result = runner.invoke(cli, ["micro", "run", "--no-judge", "TSK-004-03"])

            assert result.exit_code == 0, (
                f"Expected --no-judge flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "JUDGE" not in result.output, (
                f"JUDGE phase should be skipped with --no-judge: {result.output}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_no_refactor_flag(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            result = runner.invoke(cli, ["micro", "run", "--no-refactor", "TSK-004-04"])

            assert result.exit_code == 0, (
                f"Expected --no-refactor flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "REFACTOR" not in result.output, (
                f"REFACTOR phase should be skipped with --no-refactor: {result.output}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_agent_flag(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            result = runner.invoke(
                cli, ["micro", "run", "--agent", "droid", "TSK-004-05"]
            )

            assert result.exit_code == 0, (
                f"Expected --agent flag to be accepted, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to complete with --agent: {result.output}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_ledger_updates_on_each_phase(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            runner.invoke(cli, ["micro", "run", "TSK-004-06"])

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

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_all_processes_all_pending(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            result = runner.invoke(cli, ["micro", "run", "--all"])

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

            result = runner.invoke(cli, ["micro", "run", "--all"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit when a task fails twice: {result.output}"
            )
            ledger_lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
            statuses = [json.loads(line).get("status") for line in ledger_lines if line]
            assert statuses.count("FAILED") >= 1, (
                f"Expected at least one FAILED status: {statuses}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_judge_rejection_triggers_green_retry(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        """JUDGE_REJECTED must not skip GREEN on TRAIN retry.

        Regression test: the _phase_already_done ledger check in
        _run_green_phase was blocking re-runs after JUDGE_REJECTED
        because the GREEN ledger entry was never removed on rejection.
        Now _run_green_phase checks session.train_feedback and runs
        regardless of the ledger when feedback is present.
        """
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
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

            result = runner.invoke(cli, ["micro", "run", "TSK-004-11"])

            assert "JUDGE_REJECTED" in result.output, (
                f"Expected JUDGE_REJECTED: {result.output}"
            )
            assert "TRAIN" in result.output, f"Expected TRAIN retry: {result.output}"
            assert "TSK-004-11" in result.output.split("TRAIN")[-1], (
                "GREEN must re-run during TRAIN retry after rejection"
            )
            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_judge_rejection_with_empty_feedback_aborts(
        self, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        """JUDGE_REJECTED with no feedback at all must abort, not silently reroute.

        Contract tightened: when the judge returns COMPLIANCE_VIOLATION with
        empty rationale AND empty train_feedback AND no summary AND no
        violations, the run aborts with ``JUDGE_AGENT_NO_FEEDBACK``. The
        older contract fell back to a generic ``re-verify spec compliance``
        message and reran GREEN — which looped until TRAIN_EXHAUSTED with
        no actionable signal. Loud abort gives the operator a chance to
        fix the agent, the SKILL.md, or the spec before the next attempt.
        """
        call_log: list[str] = []

        def _judge_emit_with_no_feedback(*args, **kwargs):
            phase = kwargs.get("phase", "")
            call_log.append(phase)
            tid = kwargs.get("task_id", "TSK-004-12")
            if phase == "JUDGE":
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

        mock_agent.side_effect = _judge_emit_with_no_feedback

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-12",
                issue_id="ISS-001-004",
                description="Judge reject with no feedback aborts",
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

            result = runner.invoke(cli, ["micro", "run", "TSK-004-12"])

            assert "JUDGE_AGENT_NO_FEEDBACK" in result.output, (
                f"Expected JUDGE_AGENT_NO_FEEDBACK: {result.output}"
            )
            assert "JUDGE_REJECTED" not in result.output, (
                f"Did not expect JUDGE_REJECTED with empty feedback: {result.output}"
            )
            assert result.exit_code != 0, (
                f"Expected non-zero exit on empty-feedback rejection, got {result.exit_code}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_green_phase_escalates_to_hitl_on_contract_drift(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        """GREEN manifest carrying ``contract_drift``+``hitl_options`` is
        a structured escalation — must halt the chain via HITL_PENDING,
        not waste stall budget on a retry that produces the same verdict.

        Regression test for the runner bug where a single GREEN manifest
        with ``status: ERROR`` + ``contract_drift`` was retried twice,
        each time burning 900 s of stall budget before a duplicate
        PhaseFailedError. The runner must short-circuit on first
        detection and surface the agent's hitl_options to the operator.
        """
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        def _escalate_once(*args, **kwargs):
            phase = kwargs.get("phase", "")
            tid = kwargs.get("task_id", "TSK-004-13")
            if phase == "GREEN":
                return (
                    HandoverManifest.model_construct(
                        phase="GREEN",
                        status="ERROR",
                        task_id=tid,
                        reason="contract_drift",
                        summary=(
                            "spec:64 forbids the gloss index CLI surface, "
                            "but spec:22 mandates exercising it"
                        ),
                        contract_drift={
                            "symptom": "spec contradiction at spec:22/64",
                            "side_a": "spec:22 (Hard Inclusion: test calls gloss index)",
                            "side_b": "spec:64 (Defensive Exclusion: no CLI)",
                        },
                        hitl_options={
                            "recommended": "trim_red_test",
                            "trim_red_test": {
                                "patch": "drop the subprocess `gloss index` step",
                                "trade_off": "defers CLI to ISS-011",
                            },
                        },
                        escalates_to="orchestrator (decide RED retry vs HITL amendment)",
                    ),
                    "",
                )
            return (
                HandoverManifest(
                    phase=phase,
                    status="SUCCESS",
                    task_id=tid,
                ),
                "",
            )

        mock_agent.side_effect = _escalate_once

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-13",
                issue_id="ISS-001-004",
                description="Hitl escalation on green",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-13"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit on HITL escalation, "
                f"got {result.exit_code}: {result.output}"
            )
            assert "HITL_REQUIRED" in result.output, (
                f"Expected HITL_REQUIRED banner: {result.output}"
            )
            assert "TRAIN_EXHAUSTED" not in result.output, (
                f"HITL must short-circuit; TRAIN_EXHAUSTED is the wrong path: "
                f"{result.output}"
            )
            # RED runs once (success) + GREEN runs once (escalation) = 2 agent
            # calls. The HITL branch must NOT trigger a retry, so we
            # must NOT see TSK-004-13 invoked more than twice.
            assert mock_agent.call_count == 2, (
                f"HITL escalation must skip retry; expected RED+GREEN only "
                f"(2 calls), got {mock_agent.call_count}"
            )

            statuses = _read_statuses(ledger_path)
            assert "HITL_PENDING" in statuses, (
                f"Expected HITL_PENDING in ledger: {statuses}"
            )
            assert "FAILED" not in statuses, (
                f"HITL is distinct from FAILED — the new state machine must "
                f"not collapse them: {statuses}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_micro_green_phase_mechanical_failure_does_not_escalate_to_hitl(
        self, mock_agent, mock_verify, mock_run_test, tmp_git_repo: Path
    ):
        """GREEN receiving a RED test that cannot be satisfied via the
        library/API surface declared in scope emits ``status: FAILURE`` +
        a concrete mechanical ``rationale:`` — NOT ``error_kind:
        contract_drift`` and NOT a structured escalation (the runner's
        narrow ``_is_hitl_escalation`` check stays defensive, GREEN
        doesn't opine on drift/HITL routing).

        Pins the layer separation: GREEN says "I can't make this test
        pass within my mechanical scope" — JUDGE owns scope review and
        surfaces slice-scope conflicts to the operator. A GREEN that
        fabricates a structured escalation dict bypasses the layer and
        routes through the wrong branch.
        """
        mechanical_rationale = (
            "RED test at tests/embedder_swap_test.rs:307-379 invokes "
            "`gloss index .` as a subprocess; CLI dispatch at "
            "src/cli/mod.rs:651 routes Commands::Index(_) to "
            "not_implemented('index'). Library API `Index::update_file` "
            "is reachable from outside the CLI but cannot satisfy this "
            "test as written."
        )

        def _fail_green_mechanically(*args, **kwargs):
            phase = kwargs.get("phase", "")
            tid = kwargs.get("task_id", "TSK-004-15")
            if phase == "GREEN":
                return (
                    HandoverManifest.model_construct(
                        phase="GREEN",
                        status="FAILURE",
                        task_id=tid,
                        rationale=mechanical_rationale,
                        # Even if the agent loosely tags the kind (as the
                        # TSK-013-01 agent did), the runner must NOT
                        # promote this to a HITL escalation — the
                        # narrow check looks for structured dict keys
                        # only.
                        error_kind="contract_drift",
                    ),
                    "",
                )
            return (
                HandoverManifest(phase=phase, status="SUCCESS", task_id=tid),
                "",
            )

        mock_agent.side_effect = _fail_green_mechanically

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-15",
                issue_id="ISS-001-004",
                description="Green mechanical failure stays GREEN",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-15"])

            # Task fails (not escalates) — exit non-zero, no HITL banner.
            assert "HITL_REQUIRED" not in result.output, (
                f"Mechanical FAILURE must NOT escalate to HITL: {result.output}"
            )
            assert result.exit_code != 0, (
                f"Expected non-zero exit on mechanical FAILURE, "
                f"got {result.exit_code}: {result.output}"
            )

            # The mechanical rationale must surface verbatim in the
            # raised PhaseFailedError — proves the runner used
            # manifest.rationale, not the "unknown" fallback. The
            # exception is the canonical surface for non-banner failures
            # in ``micro run <task_id>`` mode (no _execute_task_with_retry
            # wrapper that would re-print to stdout).
            from deviate.cli.micro import HitlEscalationError, PhaseFailedError

            assert isinstance(result.exception, PhaseFailedError), (
                f"Expected PhaseFailedError, got "
                f"{type(result.exception).__name__}: {result.exception}"
            )
            assert not isinstance(result.exception, HitlEscalationError), (
                f"Mechanical FAILURE must NOT escalate to "
                f"HitlEscalationError — that bypasses layer discipline: "
                f"{result.exception}"
            )
            exc_msg = str(result.exception)
            assert "tests/embedder_swap_test.rs:307-379" in exc_msg, (
                f"Expected mechanical rationale (test path) in exception: {exc_msg}"
            )
            assert "not_implemented" in exc_msg, (
                f"Expected concrete CLI-dispatch detail in exception: {exc_msg}"
            )
            assert "unknown" not in exc_msg.split("agent_output_tail")[0], (
                f"Rationale fallback 'unknown' must NOT appear before "
                f"agent_output_tail — the runner should use the "
                f"manifest's mechanical rationale: {exc_msg}"
            )
            statuses = _read_statuses(ledger_path)
            # Single-task `micro run <task_id>` mode does not write
            # ``FAILED`` to the ledger (that's `_execute_task_with_retry`'s
            # job in `--all` mode); the canonical failure surface is the
            # raised exception, asserted above. What we MUST verify in
            # either path is that the runner did NOT write HITL_PENDING.
            assert "HITL_PENDING" not in statuses, (
                f"Mechanical FAILURE must NOT write HITL_PENDING — "
                f"layer discipline: {statuses}"
            )

    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_micro_green_train_feedback_still_retries_then_exhausts(
        self,
        mock_agent,
        mock_verify,
        mock_commit,
        mock_run_format,
        mock_run_test,
        tmp_git_repo: Path,
    ):
        """Regression guard: when GREEN's ``_run_test_cmd`` returns non-zero
        (training failure), the existing TRAIN retry loop must still run —
        NOT be redirected to the HITL branch. The new branch only fires on
        ``status: ERROR`` with ``contract_drift`` / ``hitl_options`` /
        ``escalates_to`` populated; bare test-failure train_feedback is
        out of scope.
        """
        # Drive GREEN's `test_result.returncode != 0` branch on first
        # invocation, then succeed afterwards so the cycle can settle.
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-14",
                issue_id="ISS-001-004",
                description="Train feedback still drives train_exhausted",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-14"])

            assert "HITL_REQUIRED" not in result.output, (
                f"Bare train_feedback must NOT escalate to HITL: {result.output}"
            )
            assert "TRAIN" in result.output, (
                f"Expected TRAIN retry on bare train_feedback path: {result.output}"
            )
            assert result.exit_code != 0, (
                f"Expected non-zero exit after retry exhaustion: {result.output}"
            )


def _read_statuses(ledger_path: Path) -> list[str]:
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line).get("status") for line in lines if line]


def test_green_auto_prompt_has_no_drift_instruction_language() -> None:
    """Pin the GREEN prompt's layer-discipline content.

    Sibling to ``test_micro_green_phase_mechanical_failure_does_not_escalate_to_hitl``
    which pins the *runner*'s narrow ``_is_hitl_escalation``. This test pins the
    *prompt* so a future edit cannot re-add "Halt and report API signature
    conflict" or similar GREEN drift-judgment instructions without CI failure.
    Together: runner-narrowness + prompt-content = two-axis pin on layer
    separation (GREEN does not opine on drift/HITL routing).
    """
    from importlib import resources

    green_prompt = (
        resources.files("deviate.prompts.auto").joinpath("green.md").read_text(
            encoding="utf-8"
        )
    )

    forbidden_phrases = (
        # Original Mandate 3 (replaced by mechanical scope-boundary language).
        "Contract Drift Detection",
        # Original edge_case row (removed; now mechanical FAILURE).
        "Contract drift detected",
        # Original action language (replaced with mechanical FAILURE guidance).
        "Halt and report API signature conflict",
        # Original action language in the edge_case_handling table.
        "halt and report",
        # Mandate 3 rename target — pin that the new mandate is "Scope Boundary",
        # not "Drift Detection" or any drift-themed title.
        "drift detection",
    )
    for phrase in forbidden_phrases:
        assert phrase not in green_prompt, (
            f"GREEN auto prompt must NOT contain {phrase!r} — GREEN does not "
            f"opine on drift/HITL routing; that is JUDGE's job. See "
            f"specs/DeviaTDD-api.md § GREEN Phase Layer Discipline."
        )

    # Positive pin: the new mechanical scope-boundary language must be present
    # so a future edit that just deletes the forbidden phrases (instead of
    # replacing them with the mechanical alternative) also fails.
    assert "Scope Boundary" in green_prompt, (
        "GREEN prompt must contain the 'Scope Boundary' mandate that replaced "
        "the drift-detection language. If you removed the drift language, "
        "you must add the mechanical scope-boundary replacement in the same edit."
    )
    assert "status: FAILURE" in green_prompt, (
        "GREEN prompt must instruct the agent to emit 'status: FAILURE' for "
        "RED tests that cannot be satisfied within mechanical scope."
    )


class TestYellowHandoffContract:
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

            result = runner.invoke(cli, ["micro", "run", "TSK-004-99"])

            assert result.exit_code == 0, (
                f"Expected zero exit when GREEN recovers from test failure, "
                f"got exit {result.exit_code}: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._run_test_cmd")
    def test_green_clean_worktree_failure_preserves_commit(
        self, mock_run_test, mock_agent, mock_verify, tmp_git_repo: Path
    ):
        """When _verify_clean_worktree raises during GREEN, the GREEN commit
        must NOT be destroyed.  The old code did ``git reset --hard`` to the
        RED SHA which wiped the GREEN commit entirely.  The new code tries
        to commit residual files instead."""
        from deviate.cli.micro import PhaseFailedError

        def _verify_side_effect(root, phase, tid):
            if phase == "GREEN":
                raise PhaseFailedError(
                    f"{phase} phase agent for {tid} did not commit all files"
                )

        mock_verify.side_effect = _verify_side_effect
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-88",
                issue_id="ISS-001-004",
                description="Preserve GREEN commit on worktree failure",
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

            # JUDGE will reject (mock agent produces no real code), but the
            # GREEN commit must survive — the old code destroyed it.
            runner.invoke(cli, ["micro", "run", "TSK-004-88"])

            # GREEN commit must still be in history — not destroyed by reset
            log = subprocess.run(
                ["git", "log", "--oneline", "--all"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
            ).stdout
            assert "GREEN phase" in log, f"GREEN commit was destroyed! Git log:\n{log}"
