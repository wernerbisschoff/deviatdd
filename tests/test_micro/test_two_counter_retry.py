"""Two-counter TDD retry pins (ISS-ADH-017 / AC-PLAN-001..004).

GREEN trains three times against one standing RED contract on
``revert_to_red``, then escalates. Cycle 1 does not print
``TRAIN_EXHAUSTED``. ``revert_before`` escalates immediately; three
escalates print ``TRAIN_EXHAUSTED`` and stop. Counters seed from
``SessionState`` so a crash mid-train cannot zero the budget via a
local ``train_attempts = 0``. Escalate RED receives a short
``previous cycle failed because`` note, not the GREEN dump.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import (
    PhaseFailedError,
    _build_auto_prompt,
    _finish_tdd_cycle,
    _run_tdd_cycle,
)
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition

STANDING_RED_SHA = "abc-red-contract"
STANDING_FEEDBACK = (
    "implementation wrong: slice misses AC-PLAN-001 boundary on revert_to_red"
)
GREEN_DUMP_MARKER = "UNIQUE_GREEN_DUMP_MARKER_AC_PLAN_004"
GREEN_DUMP = (
    "<test_output>\n"
    "============================= test session starts =============================\n"
    "FAILED tests/test_cli/test_micro.py::test_foo - AssertionError: 1 != 2\n"
    f"{GREEN_DUMP_MARKER}\n"
    "=========================== 1 failed in 4.87s ===========================\n"
    "</test_output>\n"
    "\n"
    "Rationale: GREEN mutated specs/adhoc/017-two-counter-tdd-retry/plan.md "
    "and rewrote src/deviate/cli/micro.py::_run_tdd_cycle in full. The "
    "implementation must keep the RED contract standing. Full pytest -vv "
    "dump follows with 80 lines of traceback and captured stdout from the "
    "failing assertion.\n"
)
_MAX_PHASES = 24


def _seed_workspace(root: Path) -> tuple[dict, Path, Path]:
    ledger_dir = root / "specs" / "adhoc" / "017-two-counter-tdd-retry"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "tasks.jsonl"
    task = {
        "id": "TSK-017-02",
        "issue_id": "ISS-ADH-017",
        "description": "Train GREEN three times on revert_to_red, then escalate",
        "execution_mode": "TDD",
    }
    append_task_transition(TaskRecord(**task), ledger_path)
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    return task, ledger_path, session_path


def _mock_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="1 failed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *a, **kw: None
    )


def _install_always_revert_to_red_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pass_after_red_count: int,
) -> dict[str, object]:
    """Stub JUDGE to return ``revert_to_red`` until a new RED (escalate).

    After ``pass_after_red_count`` RED dispatches, JUDGE forwards
    ``skip_refactor`` so this task cannot hang waiting for the later
    three-escalate stop (TSK-017-03).
    """
    call_log: list[str] = []
    green_attempts_at_green: list[int] = []
    feedback_at_green: list[str] = []
    sha_at_green: list[str] = []
    counters_at_red: list[tuple[int, int]] = []

    def _guard() -> None:
        if len(call_log) > _MAX_PHASES:
            raise AssertionError(
                f"TDD loop did not terminate after {_MAX_PHASES} phases: {call_log!r}"
            )

    def _red(*args: object, **kwargs: object) -> SessionState:
        call_log.append("RED")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        counters_at_red.append((current.green_attempts, current.red_attempts))
        if not current.red_commit_sha:
            current.red_commit_sha = STANDING_RED_SHA
        current.current_phase = "RED"
        current.save(session_path_arg)
        return current

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        green_attempts_at_green.append(current.green_attempts)
        feedback_at_green.append(current.train_feedback)
        sha_at_green.append(current.red_commit_sha)
        current.current_phase = "GREEN"
        current.save(session_path_arg)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        if call_log.count("RED") >= pass_after_red_count:
            current.judge_rejected = False
            current.pending_judge_action = "skip_refactor"
            current.train_feedback = ""
            current.failure_kind = ""
        else:
            current.judge_rejected = True
            current.pending_judge_action = "revert_to_red"
            current.train_feedback = STANDING_FEEDBACK
            current.failure_kind = "mechanical"
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
    return {
        "call_log": call_log,
        "green_attempts_at_green": green_attempts_at_green,
        "feedback_at_green": feedback_at_green,
        "sha_at_green": sha_at_green,
        "counters_at_red": counters_at_red,
    }


class TestAlwaysRevertToRedTrainsThenEscalates:
    """AC-PLAN-001 / US-017-01 / FR-ADHOC-017 / AC-ADHOC-017-01."""

    def test_always_revert_to_red_trains_green_three_times_then_escalates(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Three ``revert_to_red`` trains increment ``green_attempts``.

        After 3, the runner dispatches a new RED. Cycle 1 does not print
        ``TRAIN_EXHAUSTED``. The standing RED SHA and GREEN
        ``train_feedback`` stay for those trains.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_always_revert_to_red_stubs(
            monkeypatch, pass_after_red_count=2
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-001: three revert_to_red trains must escalate to a "
                "new RED without TRAIN_EXHAUSTED on cycle 1; runner raised "
                f"{exc!r}\n{buf.getvalue()}"
            ) from exc

        output = buf.getvalue()
        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        green_attempts_at_green = traces["green_attempts_at_green"]
        assert isinstance(green_attempts_at_green, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)
        sha_at_green = traces["sha_at_green"]
        assert isinstance(sha_at_green, list)

        assert "TRAIN_EXHAUSTED" not in output, (
            "AC-PLAN-001: a JUDGE that always revert_to_red must not print "
            f"TRAIN_EXHAUSTED before the first escalate; got {output!r}"
        )
        assert call_log.count("RED") >= 2, (
            "AC-PLAN-001: after 3 revert_to_red trains the runner must "
            f"dispatch a new _run_red_phase; got {call_log!r}"
        )
        assert green_attempts_at_green[:3] == [0, 1, 2], (
            "AC-PLAN-001: first GREEN of a fresh RED does not increment; "
            "each revert_to_red then adds 1 to green_attempts before the "
            f"next GREEN. got {green_attempts_at_green!r}"
        )
        first_contract_greens = call_log[: call_log.index("RED", 1)]
        n_green_before_escalate = first_contract_greens.count("GREEN")
        assert n_green_before_escalate == 3, (
            "AC-PLAN-001: the standing RED contract trains GREEN three "
            f"times before escalate; got {call_log!r}"
        )
        assert sha_at_green[:3] == [STANDING_RED_SHA] * 3, (
            "AC-PLAN-001: revert_to_red keeps session.red_commit_sha for "
            f"trains 1-3; got {sha_at_green[:3]!r}"
        )
        assert feedback_at_green[1:3] == [STANDING_FEEDBACK, STANDING_FEEDBACK], (
            "AC-PLAN-001: revert_to_red keeps GREEN train_feedback for "
            f"trains 1-3; got {feedback_at_green!r}"
        )

    def test_counters_persist_across_session_reload(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-entry seeds from saved ``green_attempts``, not local zero.

        A crash mid-GREEN-train reloads ``.deviate/session.json``. The
        runner must not assign ``train_attempts = 0`` and give the task
        three fresh trains. Seeded ``green_attempts == 2`` plus one
        ``revert_to_red`` reaches 3 and escalates.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            current_phase="GREEN",
            green_attempts=2,
            red_attempts=0,
            red_commit_sha=STANDING_RED_SHA,
            train_feedback=STANDING_FEEDBACK,
        ).save(session_path)

        reloaded = SessionState.load(session_path)
        assert reloaded.green_attempts == 2
        assert reloaded.red_attempts == 0

        traces = _install_always_revert_to_red_stubs(
            monkeypatch, pass_after_red_count=1
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console, start_phase="GREEN")
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-001: re-entry must resume session.green_attempts=2 "
                "and escalate after one more revert_to_red, not TRAIN_EXHAUSTED "
                f"from a zeroed local train_attempts; got {exc!r}\n"
                f"{buf.getvalue()}"
            ) from exc

        output = buf.getvalue()
        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        green_attempts_at_green = traces["green_attempts_at_green"]
        assert isinstance(green_attempts_at_green, list)

        assert green_attempts_at_green[0] == 2, (
            "AC-PLAN-001: re-entry must seed from session.green_attempts=2; "
            f"got {green_attempts_at_green!r}"
        )
        assert "TRAIN_EXHAUSTED" not in output, (
            "AC-PLAN-001: loaded green_attempts=2 must not be wiped by a "
            f"local train_attempts = 0; got {output!r} log={call_log!r}"
        )
        assert call_log.count("RED") >= 1, (
            "AC-PLAN-001: one more revert_to_red on a loaded budget of 2 "
            f"must escalate to a new RED; got {call_log!r}"
        )
        greens_before_escalate = 0
        for name in call_log:
            if name == "RED":
                break
            if name == "GREEN":
                greens_before_escalate += 1
        assert greens_before_escalate == 1, (
            "AC-PLAN-001: loaded green_attempts=2 allows exactly one more "
            f"GREEN train before escalate; got {call_log!r}"
        )


def _install_always_revert_before_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """Stub JUDGE to always set ``pending_judge_action`` to ``revert_before``.

    A 24-phase guard stops the current infinite-restart loop so this
    pin fails on missing ``TRAIN_EXHAUSTED`` instead of hanging.
    """
    call_log: list[str] = []
    counters_at_red: list[tuple[int, int]] = []
    pending_at_red: list[str] = []
    pending_at_green: list[str] = []

    def _guard() -> None:
        if len(call_log) > _MAX_PHASES:
            raise AssertionError(
                f"TDD loop did not terminate after {_MAX_PHASES} phases: {call_log!r}"
            )

    def _red(*args: object, **kwargs: object) -> SessionState:
        call_log.append("RED")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        counters_at_red.append((current.green_attempts, current.red_attempts))
        pending_at_red.append(current.pending_judge_action)
        if not current.red_commit_sha:
            current.red_commit_sha = STANDING_RED_SHA
        current.current_phase = "RED"
        current.save(session_path_arg)
        return current

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        pending_at_green.append(current.pending_judge_action)
        current.current_phase = "GREEN"
        current.failure_kind = "test_defect"
        current.train_feedback = STANDING_FEEDBACK
        current.save(session_path_arg)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        current.judge_rejected = True
        current.pending_judge_action = "revert_before"
        current.failure_kind = "test_defect"
        current.train_feedback = STANDING_FEEDBACK
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
    return {
        "call_log": call_log,
        "counters_at_red": counters_at_red,
        "pending_at_red": pending_at_red,
        "pending_at_green": pending_at_green,
    }


class TestAlwaysRevertBeforeStopsAfterThreeEscalates:
    """AC-PLAN-002 / US-017-02 / US-017-03 / FR-ADHOC-017 / AC-ADHOC-017-02."""

    def test_always_revert_before_stops_after_three_escalates(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Three ``revert_before`` escalates hand off; no fourth RED.

        Each escalate increments ``red_attempts``, resets
        ``green_attempts`` to 0, and consumes ``pending_judge_action``
        once. After ``red_attempts >= 3`` the runner prints
        ``TRAIN_EXHAUSTED``, zeros both counters, and raises
        ``PhaseFailedError``.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=2,
            red_attempts=0,
        ).save(session_path)

        traces = _install_always_revert_before_stubs(monkeypatch)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        with pytest.raises(PhaseFailedError) as excinfo:
            _run_tdd_cycle(task, ledger_path, console)

        output = buf.getvalue()
        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        counters_at_red = traces["counters_at_red"]
        assert isinstance(counters_at_red, list)
        pending_at_green = traces["pending_at_green"]
        assert isinstance(pending_at_green, list)

        assert "TRAIN_EXHAUSTED" in str(excinfo.value), (
            "AC-PLAN-002: PhaseFailedError must carry TRAIN_EXHAUSTED after "
            f"three escalates; got {excinfo.value!r}\n{output}"
        )
        assert "TRAIN_EXHAUSTED" in output, (
            "AC-PLAN-002: the runner must print TRAIN_EXHAUSTED after three "
            f"escalates; got {output!r} log={call_log!r}"
        )
        assert call_log.count("RED") == 3, (
            "AC-PLAN-002: three escalates dispatch the initial RED plus two "
            "retries and must not dispatch a fourth _run_red_phase; "
            f"got {call_log!r}"
        )
        assert call_log[:9] == [
            "RED",
            "GREEN",
            "JUDGE",
            "RED",
            "GREEN",
            "JUDGE",
            "RED",
            "GREEN",
            "JUDGE",
        ], (
            "AC-PLAN-002: each revert_before is consumed once so the next "
            f"cycle is GREEN, not an extra RED; got {call_log!r}"
        )
        assert "REFACTOR" not in call_log, (
            f"AC-PLAN-002: TRAIN_EXHAUSTED returns to the operator; got {call_log!r}"
        )
        assert counters_at_red[0] == (2, 0), (
            "AC-PLAN-002: the first RED is not an escalate; seeded "
            f"green_attempts=2 must still be present; got {counters_at_red!r}"
        )
        assert counters_at_red[1:] == [(0, 1), (0, 2)], (
            "AC-PLAN-002: each revert_before resets green_attempts to 0 and "
            "adds 1 to red_attempts before the retry RED; "
            f"got {counters_at_red!r}"
        )
        assert pending_at_green[1:] == ["", ""], (
            "AC-PLAN-002: pending_judge_action is consumed once after each "
            "escalate so GREEN does not see revert_before; "
            f"got {pending_at_green!r}"
        )

        final = SessionState.load(session_path)
        assert final.green_attempts == 0, (
            "AC-PLAN-002: TRAIN_EXHAUSTED zeros green_attempts so the next "
            f"task starts at 0; got {final.green_attempts!r}"
        )
        assert final.red_attempts == 0, (
            "AC-PLAN-002: TRAIN_EXHAUSTED zeros red_attempts so the next "
            f"task starts at 0; got {final.red_attempts!r}"
        )

    def test_finish_tdd_cycle_zeros_retry_counters_on_skip_refactor(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful skip_refactor exit writes 0/0 so the next task is fresh."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        session = SessionState(
            active_issue_id="ISS-ADH-017",
            current_phase="JUDGE",
            pending_judge_action="skip_refactor",
            green_attempts=2,
            red_attempts=1,
            train_feedback=STANDING_FEEDBACK,
            judge_rejected=False,
        )
        session.save(session_path)
        console = Console(file=io.StringIO(), force_terminal=False, width=200)

        result = _finish_tdd_cycle(
            task, ledger_path, session, session_path, console, no_refactor=False
        )

        assert result.green_attempts == 0, (
            "AC-PLAN-002: _finish_tdd_cycle skip_refactor must zero "
            f"green_attempts; got {result.green_attempts!r}"
        )
        assert result.red_attempts == 0, (
            "AC-PLAN-002: _finish_tdd_cycle skip_refactor must zero "
            f"red_attempts; got {result.red_attempts!r}"
        )
        reloaded = SessionState.load(session_path)
        assert reloaded.green_attempts == 0
        assert reloaded.red_attempts == 0


def _install_escalate_note_stubs(
    monkeypatch: pytest.MonkeyPatch,
    task: dict,
    *,
    judge_action: str,
) -> dict[str, object]:
    """Stub phases and capture the ``train_feedback`` retry RED forwards.

    ``judge_action`` is ``revert_before`` (escalate) or ``revert_to_red``
    (GREEN train). After the first retry path, JUDGE forwards
    ``skip_refactor`` so the loop exits.
    """
    call_log: list[str] = []
    feedback_at_red: list[str] = []
    prompts_at_red: list[str] = []
    feedback_at_green: list[str] = []

    def _guard() -> None:
        if len(call_log) > _MAX_PHASES:
            raise AssertionError(
                f"TDD loop did not terminate after {_MAX_PHASES} phases: {call_log!r}"
            )

    def _red(*args: object, **kwargs: object) -> SessionState:
        call_log.append("RED")
        _guard()
        session_arg = args[2]
        session_path_arg = args[3]
        assert isinstance(session_arg, SessionState)
        assert isinstance(session_path_arg, Path)
        feedback_at_red.append(session_arg.train_feedback)
        prompts_at_red.append(
            _build_auto_prompt(
                "red",
                task,
                Path.cwd(),
                train_feedback=session_arg.train_feedback,
            )
        )
        if not session_arg.red_commit_sha:
            session_arg.red_commit_sha = STANDING_RED_SHA
        session_arg.current_phase = "RED"
        session_arg.save(session_path_arg)
        return session_arg

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        feedback_at_green.append(current.train_feedback)
        current.current_phase = "GREEN"
        current.train_feedback = GREEN_DUMP
        current.failure_kind = "test_defect"
        current.save(session_path_arg)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        if call_log.count("JUDGE") >= 2:
            current.judge_rejected = False
            current.pending_judge_action = "skip_refactor"
            current.failure_kind = ""
            current.train_feedback = ""
        else:
            current.judge_rejected = True
            current.pending_judge_action = judge_action
            current.failure_kind = "test_defect"
            current.train_feedback = GREEN_DUMP
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
    return {
        "call_log": call_log,
        "feedback_at_red": feedback_at_red,
        "prompts_at_red": prompts_at_red,
        "feedback_at_green": feedback_at_green,
    }


class TestEscalateInjectsShortNoteNotGreenDump:
    """AC-PLAN-004 / US-017-02 / FR-ADHOC-017 / AC-ADHOC-017-04."""

    def test_escalate_injects_short_note_not_green_dump(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Escalate RED gets a short note; the GREEN dump is absent.

        After GREEN stores a long ``train_feedback`` dump that includes
        ``<test_output>`` and a full rationale, JUDGE returns
        ``revert_before``. The retry RED prompt that
        ``_build_auto_prompt`` builds from ``session.train_feedback``
        contains ``previous cycle failed because`` and omits the dump.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_escalate_note_stubs(
            monkeypatch, task, judge_action="revert_before"
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-004: one revert_before escalate must re-author RED "
                f"without TRAIN_EXHAUSTED; got {exc!r}\n{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        feedback_at_red = traces["feedback_at_red"]
        assert isinstance(feedback_at_red, list)
        prompts_at_red = traces["prompts_at_red"]
        assert isinstance(prompts_at_red, list)

        assert call_log.count("RED") >= 2, (
            "AC-PLAN-004: revert_before must dispatch a retry RED so the "
            f"escalate note can be observed; got {call_log!r}"
        )
        retry_feedback = feedback_at_red[1]
        retry_prompt = prompts_at_red[1]
        assert isinstance(retry_feedback, str)
        assert isinstance(retry_prompt, str)

        assert "previous cycle failed because" in retry_feedback, (
            "AC-PLAN-004: escalate must wipe GREEN train_feedback and set a "
            "short 'previous cycle failed because …' note for retry RED; "
            f"got {retry_feedback!r}"
        )
        assert "<test_output>" not in retry_feedback, (
            "AC-PLAN-004: escalate RED must omit raw GREEN <test_output>; "
            f"got {retry_feedback!r}"
        )
        assert GREEN_DUMP_MARKER not in retry_feedback, (
            "AC-PLAN-004: escalate RED must omit the full GREEN rationale "
            f"dump; got {retry_feedback!r}"
        )
        assert retry_feedback is not None
        assert retry_feedback.count("\n") <= 3, (
            "AC-PLAN-004: the escalate note must stay short (not a dump); "
            f"got {retry_feedback!r}"
        )

        assert "previous cycle failed because" in retry_prompt, (
            "AC-PLAN-004: _build_auto_prompt must inject the short note as "
            "{train_feedback} into the retry RED prompt; "
            f"prompt excerpt={retry_prompt[-800:]!r}"
        )
        assert "<test_output>" not in retry_prompt, (
            "AC-PLAN-004: retry RED prompt must omit raw GREEN <test_output>; "
            f"prompt excerpt={retry_prompt[-800:]!r}"
        )
        assert GREEN_DUMP_MARKER not in retry_prompt, (
            "AC-PLAN-004: retry RED prompt must omit the full GREEN dump; "
            f"prompt excerpt={retry_prompt[-800:]!r}"
        )

    def test_escalate_revert_to_red_keeps_green_train_feedback(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GREEN-train (``revert_to_red``) keeps the existing dump."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_escalate_note_stubs(
            monkeypatch, task, judge_action="revert_to_red"
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-004: revert_to_red must keep GREEN train_feedback "
                f"and retry GREEN, not TRAIN_EXHAUSTED; got {exc!r}\n"
                f"{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)

        assert call_log.count("GREEN") >= 2, (
            "AC-PLAN-004: revert_to_red must retry GREEN against the standing "
            f"RED; got {call_log!r}"
        )
        assert feedback_at_green[1] == GREEN_DUMP, (
            "AC-PLAN-004: revert_to_red keeps the existing GREEN "
            "train_feedback for the next GREEN; "
            f"got {feedback_at_green[1]!r}"
        )
        assert "previous cycle failed because" not in feedback_at_green[1], (
            "AC-PLAN-004: GREEN-train must not replace train_feedback with "
            f"the escalate note; got {feedback_at_green[1]!r}"
        )
