"""GREEN-resume JUDGE must TRAIN GREEN on ``revert_green``.

Ledger GREEN maps to ``start_phase="JUDGE"``. After a passing GREEN
(``_is_green_test_failure`` is false) a JUDGE ``next_action: revert_green``
must fall through into the GREEN train loop. It must not call
``_finish_tdd_cycle`` / ``_run_refactor_phase`` or mark COMPLETED.

Constitution §3: pytest under tests/; git isolation via tmp_git_repo +
``_git_env()``; mock ``_run_pytest`` / agent invoke.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import _finish_tdd_cycle, _run_tdd_cycle
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition
from tests.conftest import _git_env

STANDING_RED_SHA = "abc-red-contract"
TRAIN_FEEDBACK = (
    "implementation wrong: slice misses AC-PLAN-001 boundary on revert_green"
)
_ISSUE_ID = "ISS-ADH-032"
_TASK_ID = "TSK-032-01"


def _seed_workspace(
    root: Path, *, ledger_status: str = "GREEN"
) -> tuple[dict, Path, Path]:
    ledger_dir = root / "specs" / "adhoc" / "032-revert-to-red-resume"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "tasks.jsonl"
    task = {
        "id": _TASK_ID,
        "issue_id": _ISSUE_ID,
        "description": "Resume JUDGE revert_green must train GREEN",
        "execution_mode": "TDD",
    }
    append_task_transition(TaskRecord(**task), ledger_path)
    if ledger_status != "PENDING":
        append_task_transition(
            TaskRecord(**{**task, "status": ledger_status}), ledger_path
        )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    return task, ledger_path, session_path


def _mock_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="1 passed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *a, **kw: None
    )


def _completed_rows(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    rows: list[dict] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("status") == "COMPLETED":
            rows.append(data)
    return rows


def _install_judge_resume_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    first_judge_action: str = "revert_green",
    subsequent_judge_action: str = "skip_refactor",
) -> dict[str, object]:
    """Stub phases. First JUDGE applies ``first_judge_action``; later skip.

    GREEN records ``pending_judge_action`` / ``train_feedback`` at entry so
    the resume pin can see the stored train payload. After the first GREEN
    train, JUDGE forwards so the cycle can exit without hanging.
    """
    call_log: list[str] = []
    pending_at_green: list[str] = []
    feedback_at_green: list[str] = []
    rejected_at_green: list[bool] = []

    def _red(*args: object, **kwargs: object) -> SessionState:
        call_log.append("RED")
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        if not current.red_commit_sha:
            current.red_commit_sha = STANDING_RED_SHA
        current.current_phase = "RED"
        current.save(session_path_arg)
        return current

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        pending_at_green.append(current.pending_judge_action)
        feedback_at_green.append(current.train_feedback)
        rejected_at_green.append(current.judge_rejected)
        current.current_phase = "GREEN"
        current.failure_kind = ""
        # Suite is green: do not stamp the TEST_FAILURE prefix.
        current.save(session_path_arg)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        action = (
            first_judge_action
            if call_log.count("JUDGE") == 1
            else subsequent_judge_action
        )
        if action == "revert_green":
            current.judge_rejected = True
            current.pending_judge_action = "revert_green"
            current.train_feedback = TRAIN_FEEDBACK
            current.failure_kind = ""
            current.last_judge_verdict = "COMPLIANCE_VIOLATION"
            current.current_phase = "GREEN"
        else:
            current.judge_rejected = False
            current.pending_judge_action = action
            current.train_feedback = ""
            current.failure_kind = ""
            current.last_judge_verdict = "COMPLIANCE_PASS"
            current.current_phase = "JUDGE"
        current.save(session_path_arg)
        return current

    def _refactor(*args: object, **kwargs: object) -> SessionState:
        call_log.append("REFACTOR")
        session_arg = args[2] if len(args) > 2 else kwargs.get("session")
        assert isinstance(session_arg, SessionState)
        return session_arg

    monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
    monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
    monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
    monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
    return {
        "call_log": call_log,
        "pending_at_green": pending_at_green,
        "feedback_at_green": feedback_at_green,
        "rejected_at_green": rejected_at_green,
    }


class TestJudgeResumeRevertGreenTrainsGreen:
    """start_phase=JUDGE + passing suite + revert_green → TRAIN GREEN."""

    def test_start_phase_judge_revert_green_trains_green_not_refactor(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Resume at JUDGE after GREEN PASS must train GREEN, never REFACTOR.

        ``_is_green_test_failure`` is false (passing suite). Mocked JUDGE
        returns ``COMPLIANCE_VIOLATION`` + ``next_action: revert_green`` +
        train_feedback. GREEN must run with that pending action; REFACTOR
        must not.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        task, ledger_path, session_path = _seed_workspace(root, ledger_status="GREEN")
        SessionState(
            active_issue_id=_ISSUE_ID,
            current_phase="GREEN",
            red_commit_sha=STANDING_RED_SHA,
            green_attempts=0,
            red_attempts=0,
            train_feedback="",
            judge_rejected=False,
            pending_judge_action="",
            failure_kind="",
        ).save(session_path)

        traces = _install_judge_resume_stubs(monkeypatch)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        _run_tdd_cycle(task, ledger_path, console, start_phase="JUDGE")

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        pending_at_green = traces["pending_at_green"]
        assert isinstance(pending_at_green, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)

        assert "REFACTOR" not in call_log, (
            "start_phase=JUDGE + revert_green must not enter REFACTOR; "
            f"got {call_log!r}\n{buf.getvalue()}"
        )
        assert "GREEN" in call_log, (
            "start_phase=JUDGE + revert_green must train GREEN; "
            f"got {call_log!r}\n{buf.getvalue()}"
        )
        assert call_log[0] == "JUDGE", (
            "fresh JUDGE resume (no stored pending) must invoke JUDGE once; "
            f"got {call_log!r}"
        )
        assert pending_at_green[0] == "revert_green", (
            "pending_judge_action must stay revert_green until GREEN trains; "
            f"got {pending_at_green!r}"
        )
        assert feedback_at_green[0] == TRAIN_FEEDBACK, (
            "GREEN train must receive stored JUDGE train_feedback; "
            f"got {feedback_at_green!r}"
        )

    def test_finish_tdd_cycle_refuses_refactor_on_revert_green(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Defense in depth: pending revert_green never enters REFACTOR."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        task, ledger_path, session_path = _seed_workspace(root, ledger_status="GREEN")
        session = SessionState(
            active_issue_id=_ISSUE_ID,
            current_phase="GREEN",
            pending_judge_action="revert_green",
            train_feedback=TRAIN_FEEDBACK,
            judge_rejected=True,
            red_commit_sha=STANDING_RED_SHA,
            failure_kind="",
        )
        session.save(session_path)
        refactor_calls: list[str] = []

        def _refactor(*args: object, **kwargs: object) -> SessionState:
            refactor_calls.append("REFACTOR")
            return session

        monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
        console = Console(file=io.StringIO(), force_terminal=False, width=200)

        result = _finish_tdd_cycle(
            task, ledger_path, session, session_path, console, no_refactor=False
        )

        assert refactor_calls == [], (
            "_finish_tdd_cycle must not call _run_refactor_phase while "
            f"pending is revert_green; got {refactor_calls!r}"
        )
        assert result.pending_judge_action == "revert_green", (
            "_finish_tdd_cycle must leave pending revert_green in place; "
            f"got {result.pending_judge_action!r}"
        )
        assert result.current_phase != "IDLE", (
            "_finish_tdd_cycle must not park IDLE/COMPLETED on revert_green; "
            f"got {result.current_phase!r}"
        )
        assert _completed_rows(ledger_path) == [], (
            "_finish_tdd_cycle must not append COMPLETED on revert_green; "
            f"got {_completed_rows(ledger_path)!r}"
        )

    def test_finish_tdd_cycle_refuses_refactor_on_revert_red(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Defense in depth: pending revert_red never enters REFACTOR."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root, ledger_status="GREEN")
        session = SessionState(
            active_issue_id=_ISSUE_ID,
            current_phase="RED",
            pending_judge_action="revert_red",
            train_feedback=TRAIN_FEEDBACK,
            judge_rejected=True,
            red_commit_sha="",
            failure_kind="",
        )
        session.save(session_path)
        refactor_calls: list[str] = []

        def _refactor(*args: object, **kwargs: object) -> SessionState:
            refactor_calls.append("REFACTOR")
            return session

        monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
        console = Console(file=io.StringIO(), force_terminal=False, width=200)

        result = _finish_tdd_cycle(
            task, ledger_path, session, session_path, console, no_refactor=False
        )

        assert refactor_calls == [], (
            "_finish_tdd_cycle must not call _run_refactor_phase while "
            f"pending is revert_red; got {refactor_calls!r}"
        )
        assert result.pending_judge_action == "revert_red"
        assert _completed_rows(ledger_path) == []

    def test_resume_stored_revert_green_skips_judge_and_trains_green(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ledger GREEN + session already revert_green skips a second JUDGE."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        task, ledger_path, session_path = _seed_workspace(root, ledger_status="GREEN")
        SessionState(
            active_issue_id=_ISSUE_ID,
            current_phase="GREEN",
            red_commit_sha=STANDING_RED_SHA,
            pending_judge_action="revert_green",
            train_feedback=TRAIN_FEEDBACK,
            judge_rejected=True,
            failure_kind="",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_judge_resume_stubs(monkeypatch)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        _run_tdd_cycle(task, ledger_path, console, start_phase="JUDGE")

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        pending_at_green = traces["pending_at_green"]
        assert isinstance(pending_at_green, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)

        assert call_log[0] == "GREEN", (
            "stored pending revert_green + train_feedback must skip JUDGE "
            f"and train GREEN first; got {call_log!r}\n{buf.getvalue()}"
        )
        assert "REFACTOR" not in call_log, (
            f"stored revert_green resume must not enter REFACTOR; got {call_log!r}"
        )
        assert pending_at_green[0] == "revert_green"
        assert feedback_at_green[0] == TRAIN_FEEDBACK
