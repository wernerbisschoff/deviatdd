"""RED: compile-error output counts as a failing RED (ISS-ADH-041).
TSK-041-01 covers AC-PLAN-001..003; TSK-041-02 covers AC-PLAN-004.
TSK-041-03 (AC-PLAN-005) pins the no-failing-test COMPLETE evidence
guards: empty evidence quotes, docs-only diffs, and COMPLETE routes
whose declared regression paths miss the diff are rejected.

AC-PLAN-001: non-zero result with compile-error markers commits RED / GREEN.
AC-PLAN-002: exit 0 / exit 5 / exit 127 still route to adjudication.
AC-PLAN-003: mixed compile-error plus passing output counts as failing.
AC-PLAN-005: no-failing-test COMPLETE keeps evidence guardrails.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

import deviate.cli.micro as micro
from deviate.cli.micro import (
    PhaseFailedError,
    _adjudicate_red_no_failing_test,
    _append_status_transition,
    _execute_task_with_retry,
    _run_red_phase,
    _run_tdd_cycle,
)

from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition
from deviate.ui.monitor import OrchestrationMonitor


def _proc(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _classifier():
    fn = getattr(micro, "_is_compile_error", None)
    assert fn is not None, (
        "_is_compile_error missing on deviate.cli.micro (RED: implement it)"
    )
    return fn


@pytest.mark.behavioral
def test_python_collection_traceback_is_compile_error():
    out = "ERROR tests/test_x.py - ModuleNotFoundError: No module named 'foo'\nTraceback (most recent call last):\n"
    assert _classifier()(_proc(2, stdout=out)) is True


@pytest.mark.behavioral
def test_exunit_markers_are_compile_errors():
    assert (
        _classifier()(_proc(1, stdout="** (CompileError) Compilation failed")) is True
    )
    assert _classifier()(_proc(1, stderr="error: undefined function foo/0")) is True


@pytest.mark.behavioral
def test_exit_zero_with_markers_still_adjudicates():
    assert _classifier()(_proc(0, stdout="1 passed, Compilation failed")) is False


@pytest.mark.behavioral
def test_exit_five_and_127_are_not_compile_errors():
    assert _classifier()(_proc(5, stdout="no tests ran")) is False
    assert _classifier()(_proc(127, stderr="No test command configured")) is False


@pytest.mark.behavioral
def test_empty_stdout_with_stderr_markers_counts():
    assert (
        _classifier()(_proc(2, stderr="ModuleNotFoundError: No module named 'x'"))
        is True
    )


def _drive_red(root: Path, result: subprocess.CompletedProcess):
    task = {
        "id": "TSK-041-01",
        "issue_id": "ISS-ADH-041",
        "description": "compile error RED",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    session = SessionState(current_phase="IDLE")
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    ledger_path = root / "specs" / "adhoc" / "tasks.jsonl"
    manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id=task["id"])
    with (
        chdir(root),
        patch.object(micro, "_phase_already_done", return_value=False),
        patch.object(micro, "_log_run"),
        patch.object(micro, "_make_agent_output_callback", return_value=None),
        patch.object(micro, "resolve_model_for_phase", return_value=None),
        patch.object(micro, "_invoke_agent", return_value=(manifest, "")),
        patch.object(micro, "_run_test_cmd", return_value=result),
        patch.object(micro, "_run_format_cmd", return_value=_proc(0)),
        patch.object(micro, "append_task_transition"),
        patch.object(micro, "_commit_phase", return_value=True),
        patch.object(micro, "_verify_clean_worktree"),
        patch.object(
            micro, "_adjudicate_red_no_failing_test", return_value=session
        ) as adjudicate,
    ):
        _run_red_phase(task, ledger_path, session, session_path, Console(quiet=True))
    return adjudicate


@pytest.mark.behavioral
def test_red_phase_routes_compile_error_to_green(tmp_git_repo: Path):
    out = "ERROR tests/test_x.py - ModuleNotFoundError: No module named 'foo'"
    adjudicate = _drive_red(tmp_git_repo, _proc(2, stdout=out))
    adjudicate.assert_not_called()


@pytest.mark.behavioral
def test_red_phase_routes_exit_zero_to_adjudication(tmp_git_repo: Path):
    adjudicate = _drive_red(tmp_git_repo, _proc(0, stdout="1 passed"))
    adjudicate.assert_called_once()


@pytest.mark.behavioral
def test_red_phase_routes_mixed_output_to_green(tmp_git_repo: Path):
    out = "1 passed\nERROR tests/test_y.py - ModuleNotFoundError: No module named 'bar'"
    adjudicate = _drive_red(tmp_git_repo, _proc(2, stdout=out))
    adjudicate.assert_not_called()


def _seed_exhaustion_workspace(root: Path) -> tuple[dict, Path, Path]:
    ledger_dir = root / "specs" / "adhoc" / "041-red-compile-error-no-failing-test"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "tasks.jsonl"
    task = {
        "id": "TSK-041-02",
        "issue_id": "ISS-ADH-041",
        "description": "Record FAILED row at TRAIN exhaustion",
        "execution_mode": "TDD",
    }
    append_task_transition(TaskRecord(**task), ledger_path)
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(active_issue_id="ISS-ADH-041").save(session_path)
    return task, ledger_path, session_path


def _install_always_revert_red(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    call_log: list[str] = []

    def _guard() -> None:
        if len(call_log) > 24:
            raise AssertionError(f"TDD loop did not stop: {call_log!r}")

    def _red(*args: object, **kwargs: object) -> SessionState:
        call_log.append("RED")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        if not current.red_commit_sha:
            current.red_commit_sha = "standing-red-sha"
        current.current_phase = "RED"
        current.save(session_path_arg)
        return current

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        current.current_phase = "GREEN"
        current.failure_kind = "test_defect"
        current.train_feedback = "standing feedback"
        current.save(session_path_arg)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        current.judge_rejected = True
        current.pending_judge_action = "revert_red"
        current.failure_kind = "test_defect"
        current.train_feedback = "standing feedback"
        current.save(session_path_arg)
        return current

    def _finish(*args: object, **kwargs: object) -> SessionState:
        call_log.append("REFACTOR")
        session_arg = args[2]
        assert isinstance(session_arg, SessionState)
        return session_arg

    monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
    monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
    monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
    monkeypatch.setattr("deviate.cli.micro._finish_tdd_cycle", _finish)
    return call_log


@pytest.mark.behavioral
def test_train_exhaustion_records_failed_row(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_git_repo
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="1 failed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *a, **kw: None
    )
    task, ledger_path, _session_path = _seed_exhaustion_workspace(root)
    call_log = _install_always_revert_red(monkeypatch)
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False, width=200)
    with pytest.raises(PhaseFailedError) as excinfo:
        _run_tdd_cycle(task, ledger_path, c)
    assert "TRAIN_EXHAUSTED" in str(excinfo.value)
    assert call_log.count("RED") == 3
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed = [
        r for r in rows if r.get("id") == "TSK-041-02" and r.get("status") == "FAILED"
    ]
    assert len(failed) == 1, f"AC-PLAN-004: exactly one FAILED row; got {rows!r}"
    assert "TRAIN_EXHAUSTED" in json.dumps(failed[0]), (
        f"AC-PLAN-004: FAILED row carries TRAIN_EXHAUSTED reason; got {failed[0]!r}"
    )


@pytest.mark.behavioral
def test_train_exhaustion_marks_clean_error(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_git_repo
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="1 failed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *a, **kw: None
    )
    task, ledger_path, _session_path = _seed_exhaustion_workspace(root)
    _install_always_revert_red(monkeypatch)
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=False, width=200)
    with pytest.raises(PhaseFailedError) as excinfo:
        _run_tdd_cycle(task, ledger_path, c)
    assert "TRAIN_EXHAUSTED" in buf.getvalue()
    assert getattr(excinfo.value, "train_exhausted", False) is True, (
        "AC-PLAN-004: exhaustion error carries the clean-failure mark so the retry wrapper honors it"
    )


@pytest.mark.behavioral
def test_retry_wrapper_does_not_rerun_exhausted_task(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_git_repo
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="1 failed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *a, **kw: None
    )
    task, ledger_path, _session_path = _seed_exhaustion_workspace(root)
    call_log = _install_always_revert_red(monkeypatch)
    monitor = OrchestrationMonitor(
        Console(file=io.StringIO(), force_terminal=False, width=200)
    )
    with monitor:
        dispatched = {"count": 0}
        real_dispatch = micro._dispatch_task

        def _counting_dispatch(*args: object, **kwargs: object) -> None:
            dispatched["count"] += 1
            return real_dispatch(*args, **kwargs)

        monkeypatch.setattr("deviate.cli.micro._dispatch_task", _counting_dispatch)
        ok = _execute_task_with_retry(
            task,
            ledger_path,
            Console(file=io.StringIO(), force_terminal=False, width=200),
            monitor,
            root,
        )
    assert ok is False
    assert dispatched["count"] == 1, (
        f"AC-PLAN-004: retry wrapper must not rerun; got {dispatched['count']}"
    )
    assert call_log.count("RED") == 3
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed = [
        r for r in rows if r.get("id") == "TSK-041-02" and r.get("status") == "FAILED"
    ]
    assert len(failed) == 1, f"AC-PLAN-004: no duplicate FAILED rows; got {rows!r}"


# ---------------------------------------------------------------------------
# TSK-041-03 / AC-PLAN-005: pin the no-failing-test COMPLETE evidence guards.
# A COMPLETE with empty evidence quotes is rejected; a COMPLETE whose only
# evidence path is a docs file is rejected; a COMPLETE whose declared
# regression paths miss the diff is rejected.
# ---------------------------------------------------------------------------


def _041_task() -> dict:
    return {
        "id": "TSK-041-03",
        "issue_id": "ISS-ADH-041",
        "description": "Pin no-failing-test COMPLETE evidence guards",
        "status": "JUDGE",
        "execution_mode": "TDD",
        "acceptance_criteria": [
            {"criterion_id": "AC-PLAN-005", "verification_mode": "automated"}
        ],
    }


def _041_session(**overrides: object) -> SessionState:
    kwargs: dict = {"current_phase": "JUDGE"}
    kwargs.update(overrides)
    session = SessionState(**kwargs)
    return session


def _041_save(session: SessionState, repo: Path) -> Path:
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    return session_path


@pytest.mark.behavioral
def test_complete_with_empty_evidence_quotes_is_rejected(tmp_git_repo: Path):
    """AC-PLAN-005: COMPLETE with empty evidence quotes is rejected."""
    session = _041_session(
        last_judge_verdict="COMPLIANCE_PASS",
        pending_judge_action="skip_refactor",
        validated_evidence=[
            {
                "ac": "AC-PLAN-005",
                "test_path": "",
                "test_quote": "",
                "impl_path": "",
                "impl_quote": "",
            }
        ],
    )
    _041_save(session, tmp_git_repo)
    ledger_path = tmp_git_repo / "specs" / "adhoc" / "tasks.jsonl"
    with chdir(tmp_git_repo), pytest.raises(PhaseFailedError) as exc:
        _append_status_transition(_041_task(), "COMPLETED", ledger_path)
    assert "COMPLETED_EVIDENCE_MISSING" in str(exc.value)


@pytest.mark.behavioral
def test_complete_with_docs_only_diff_is_rejected(tmp_git_repo: Path):
    """AC-PLAN-005: COMPLETE naming only a docs evidence path is rejected."""
    docs = tmp_git_repo / "docs" / "plan.md"
    docs.parent.mkdir(parents=True, exist_ok=True)
    docs.write_text("AC-PLAN-005 guardrail\n", encoding="utf-8")
    session = _041_session(
        last_judge_verdict="COMPLIANCE_PASS",
        pending_judge_action="skip_refactor",
        validated_evidence=[
            {
                "ac": "AC-PLAN-005",
                "test_path": "docs/plan.md",
                "test_quote": "AC-PLAN-005 guardrail",
                "impl_path": "",
                "impl_quote": "",
            }
        ],
    )
    _041_save(session, tmp_git_repo)
    ledger_path = tmp_git_repo / "specs" / "adhoc" / "tasks.jsonl"
    with chdir(tmp_git_repo), pytest.raises(PhaseFailedError) as exc:
        _append_status_transition(_041_task(), "COMPLETED", ledger_path)
    assert "COMPLETED_EVIDENCE_MISSING" in str(exc.value)


@pytest.mark.behavioral
def test_complete_missing_declared_regression_path_in_diff_is_rejected(
    tmp_git_repo: Path,
):
    """AC-PLAN-005: COMPLETE whose declared paths miss the diff is rejected."""
    manifest = HandoverManifest(
        phase="RED",
        status="SUCCESS",
        task_id="TSK-041-03",
        files=["tests/unit/test_micro/test_missing_pin.py"],
        test_file="tests/unit/test_micro/test_missing_pin.py",
    )
    session = SessionState(
        current_phase="RED",
        failure_kind="no_failing_test",
        train_feedback="standing feedback",
        pending_judge_action="skip_refactor",
    )
    session_path = _041_save(session, tmp_git_repo)
    ledger_path = tmp_git_repo / "specs" / "adhoc" / "tasks.jsonl"
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_phase_already_done", return_value=False),
        patch.object(micro, "_log_run"),
        patch.object(micro, "_make_agent_output_callback", return_value=None),
        patch.object(micro, "resolve_model_for_phase", return_value=None),
        patch.object(micro, "_run_format_cmd", return_value=_proc(0)),
        patch.object(micro, "_commit_phase", return_value=True),
        patch.object(micro, "_verify_clean_worktree"),
        patch.object(micro, "_run_judge_phase", return_value=session),
    ):
        with pytest.raises(PhaseFailedError):
            _adjudicate_red_no_failing_test(
                _041_task(),
                ledger_path,
                session,
                session_path,
                Console(quiet=True),
                manifest=manifest,
                test_result=_proc(0, stdout="1 passed"),
                red_baseline=[],
            )
