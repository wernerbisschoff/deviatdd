"""Two-counter TDD retry pins (ISS-ADH-017 / AC-PLAN-001..005).

GREEN trains three times against one standing RED contract on
``revert_green`` (each GREEN start counts, including the first;
TRAIN 3/3 is a real GREEN), then escalates. Cycle 1 does not print
``TRAIN_EXHAUSTED``. ``revert_red`` escalates immediately; three
escalates print ``TRAIN_EXHAUSTED`` and stop. Counters seed from
``SessionState`` so a crash mid-train cannot zero the budget via a
local ``train_attempts = 0``. Escalate RED receives a short
``previous cycle failed because`` note, not the GREEN dump.
AC-PLAN-005 keeps JUDGE verbs, the coerce matrix, and 3/3 caps.
"""

from __future__ import annotations

import inspect
import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import (
    PhaseFailedError,
    _JUDGE_ACTIONS,
    _MAX_GREEN_ATTEMPTS,
    _MAX_RED_ATTEMPTS,
    _build_auto_prompt,
    _coerce_judge_action,
    _finish_tdd_cycle,
    _run_execute_phase,
    _run_tdd_cycle,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition

STANDING_RED_SHA = "abc-red-contract"
STANDING_FEEDBACK = (
    "implementation wrong: slice misses AC-PLAN-001 boundary on revert_green"
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
        "description": "Train GREEN three times on revert_green, then escalate",
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


def _install_always_revert_green_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pass_after_red_count: int,
) -> dict[str, object]:
    """Stub JUDGE to return ``revert_green`` until a new RED (escalate).

    After ``pass_after_red_count`` RED dispatches, JUDGE forwards
    ``skip_refactor`` so this task cannot hang waiting for the later
    three-escalate stop (TSK-017-03).
    """
    call_log: list[str] = []
    green_attempts_at_green: list[int] = []
    feedback_at_green: list[str] = []
    sha_at_green: list[str] = []
    pending_at_green: list[str] = []
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
        current.green_attempts += 1
        current.save(session_path_arg)
        green_attempts_at_green.append(current.green_attempts)
        feedback_at_green.append(current.train_feedback)
        sha_at_green.append(current.red_commit_sha)
        pending_at_green.append(current.pending_judge_action)
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
            current.pending_judge_action = "revert_green"
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
        "pending_at_green": pending_at_green,
        "counters_at_red": counters_at_red,
    }


class TestAlwaysRevertGreenTrainsThenEscalates:
    """AC-PLAN-001 / US-017-01 / FR-ADHOC-017 / AC-ADHOC-017-01."""

    def test_always_revert_green_trains_green_three_times_then_escalates(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Three ``revert_green`` trains increment ``green_attempts``.

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

        traces = _install_always_revert_green_stubs(monkeypatch, pass_after_red_count=2)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-001: three revert_green trains must escalate to a "
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
            "AC-PLAN-001: a JUDGE that always revert_green must not print "
            f"TRAIN_EXHAUSTED before the first escalate; got {output!r}"
        )
        assert call_log.count("RED") >= 2, (
            "AC-PLAN-001: after 3 revert_green trains the runner must "
            f"dispatch a new _run_red_phase; got {call_log!r}"
        )
        assert green_attempts_at_green[:3] == [1, 2, 3], (
            "AC-PLAN-001: each GREEN start (including the first) increments "
            "green_attempts so TRAIN 3/3 is a real GREEN; got "
            f"{green_attempts_at_green!r}"
        )
        first_contract_greens = call_log[: call_log.index("RED", 1)]
        n_green_before_escalate = first_contract_greens.count("GREEN")
        assert n_green_before_escalate == 3, (
            "AC-PLAN-001: the standing RED contract trains GREEN three "
            f"times before escalate; got {call_log!r}"
        )
        assert sha_at_green[:3] == [STANDING_RED_SHA] * 3, (
            "AC-PLAN-001: revert_green keeps session.red_commit_sha for "
            f"trains 1-3; got {sha_at_green[:3]!r}"
        )
        assert feedback_at_green[1:3] == [STANDING_FEEDBACK, STANDING_FEEDBACK], (
            "AC-PLAN-001: revert_green keeps GREEN train_feedback for "
            f"trains 1-3; got {feedback_at_green!r}"
        )

    def test_fresh_cycle_resets_leftover_budget_first_green_is_one(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A new cycle zeros leftover TRAIN counters, not JUDGE notes.

        ``.deviate/session.json`` is gitignored, so ``git reset`` and a
        fresh ``micro run`` used to reload ``green_attempts=3`` and
        block the first GREEN as exhausted. Cycle entry resets only
        ``green_attempts`` / ``red_attempts``. ``train_feedback`` stays
        and is injected. In-cycle increment is unchanged (see
        ``test_always_revert_green_trains_green_three_times_then_escalates``).
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            current_phase="GREEN",
            green_attempts=3,
            red_attempts=2,
            red_commit_sha=STANDING_RED_SHA,
            pending_judge_action="revert_green",
            train_feedback=STANDING_FEEDBACK,
        ).save(session_path)

        reloaded = SessionState.load(session_path)
        assert reloaded.green_attempts == 3
        assert reloaded.red_attempts == 2
        assert reloaded.train_feedback == STANDING_FEEDBACK
        assert reloaded.pending_judge_action == "revert_green"
        assert reloaded.red_commit_sha == STANDING_RED_SHA

        traces = _install_always_revert_green_stubs(monkeypatch, pass_after_red_count=0)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console, start_phase="GREEN")
        except PhaseFailedError as exc:
            raise AssertionError(
                "fresh cycle entry must reset leftover TRAIN 3/3 so the "
                "first GREEN is TRAIN 1/3, not TRAIN_EXHAUSTED; "
                f"got {exc!r}\n{buf.getvalue()}"
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
            "leftover green_attempts=3 / red_attempts=2 must not exhaust "
            f"on a new cycle; got {output!r} log={call_log!r}"
        )
        assert call_log[0] == "GREEN", (
            "start_phase=GREEN with leftover TRAIN 3/3 must run GREEN, "
            f"not escalate; got {call_log!r}"
        )
        assert green_attempts_at_green[0] == 1, (
            "cycle-entry _reset_tdd_retry_budget must make the first "
            f"GREEN TRAIN 1/3; got {green_attempts_at_green!r}"
        )
        assert feedback_at_green[0] == STANDING_FEEDBACK, (
            "reset must keep leftover train_feedback for the first GREEN; "
            f"got {feedback_at_green!r}"
        )
        assert sha_at_green[0] == STANDING_RED_SHA, (
            "reset must keep red_commit_sha; got {sha_at_green!r}"
        )
        pending_at_green = traces["pending_at_green"]
        assert isinstance(pending_at_green, list)
        assert pending_at_green[0] == "revert_green", (
            "reset must keep pending_judge_action; got {pending_at_green!r}"
        )
        assert call_log.count("RED") == 0, (
            "leftover 3/3 must not escalate on a fresh cycle that then "
            f"passes; got {call_log!r}"
        )

    @pytest.mark.parametrize(
        "start_phase,pending,pass_after_red_count,expect_first",
        [
            (None, "", 1, "RED"),
            ("JUDGE", "revert_green", 0, "GREEN"),
        ],
        ids=["fresh_micro_run", "idle_judge_resume"],
    )
    def test_cycle_entry_reset_covers_fresh_run_and_judge_resume(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        start_phase: str | None,
        pending: str,
        pass_after_red_count: int,
        expect_first: str,
    ) -> None:
        """Pinned ``micro run``, bare start, and IDLE+JUDGE resume reset."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            current_phase="IDLE",
            green_attempts=3,
            red_attempts=2,
            red_commit_sha=STANDING_RED_SHA,
            pending_judge_action=pending,
            train_feedback=STANDING_FEEDBACK,
        ).save(session_path)

        traces = _install_always_revert_green_stubs(
            monkeypatch, pass_after_red_count=pass_after_red_count
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console, start_phase=start_phase)
        except PhaseFailedError as exc:
            raise AssertionError(
                "cycle-entry reset must cover fresh micro run and JUDGE "
                f"resume; got {exc!r}\n{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        green_attempts_at_green = traces["green_attempts_at_green"]
        assert isinstance(green_attempts_at_green, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)

        assert call_log[0] == expect_first, (
            f"start_phase={start_phase!r} must begin at {expect_first}; "
            f"got {call_log!r}"
        )
        assert "TRAIN_EXHAUSTED" not in buf.getvalue(), (
            "leftover red_attempts=2 plus green_attempts=3 must not "
            f"TRAIN_EXHAUSTED on a new cycle; log={call_log!r}"
        )
        assert green_attempts_at_green[0] == 1, (
            "first GREEN after cycle-entry reset is TRAIN 1/3; "
            f"got {green_attempts_at_green!r}"
        )
        assert feedback_at_green[0] == STANDING_FEEDBACK, (
            f"train_feedback must still be injected; got {feedback_at_green!r}"
        )


def _install_always_revert_red_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """Stub JUDGE to always set ``pending_judge_action`` to ``revert_red``.

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
        current.pending_judge_action = "revert_red"
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


def _install_empty_red_sha_revert_red_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """RED returns empty SHA + ``revert_red`` (``no_failing_test``).

    GREEN is a counter so the pin can prove it is never dispatched.
    """
    call_log: list[str] = []
    green_calls: list[str] = []

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
        current.red_commit_sha = ""
        current.current_phase = "RED"
        current.pending_judge_action = "revert_red"
        current.failure_kind = "no_failing_test"
        current.judge_rejected = True
        current.save(session_path_arg)
        return current

    def _green(*args: object, **kwargs: object) -> SessionState:
        call_log.append("GREEN")
        green_calls.append("GREEN")
        _guard()
        session_path_arg = args[3]
        assert isinstance(session_path_arg, Path)
        current = SessionState.load(session_path_arg)
        current.current_phase = "GREEN"
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
        current.failure_kind = "no_failing_test"
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
    return {"call_log": call_log, "green_calls": green_calls}


class TestAlwaysRevertRedStopsAfterThreeEscalates:
    """AC-PLAN-002 / US-017-02 / US-017-03 / FR-ADHOC-017 / AC-ADHOC-017-02."""

    def test_always_revert_red_stops_after_three_escalates(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Three ``revert_red`` escalates hand off; no fourth RED.

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

        traces = _install_always_revert_red_stubs(monkeypatch)
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
            "AC-PLAN-002: each revert_red is consumed once so the next "
            f"cycle is GREEN, not an extra RED; got {call_log!r}"
        )
        assert "REFACTOR" not in call_log, (
            f"AC-PLAN-002: TRAIN_EXHAUSTED returns to the operator; got {call_log!r}"
        )
        assert counters_at_red[0] == (0, 0), (
            "AC-PLAN-002: the first RED is not an escalate; leftover "
            "green_attempts=2 is zeroed at cycle entry; "
            f"got {counters_at_red!r}"
        )
        assert counters_at_red[1:] == [(0, 1), (0, 2)], (
            "AC-PLAN-002: each revert_red resets green_attempts to 0 and "
            "adds 1 to red_attempts before the retry RED; "
            f"got {counters_at_red!r}"
        )
        assert pending_at_green[1:] == ["", ""], (
            "AC-PLAN-002: pending_judge_action is consumed once after each "
            "escalate so GREEN does not see revert_red; "
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

    def test_escalate_to_red_does_not_dispatch_green_without_red_sha(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-PLAN-001: empty red_commit_sha after escalate never calls GREEN.

        ``_run_red_phase`` returns with empty ``session.red_commit_sha`` and
        ``pending_judge_action == revert_red`` (no_failing_test
        adjudicated). ``_run_green_phase`` is a counter. The loop re-invokes
        RED or raises TRAIN_EXHAUSTED / PhaseFailedError. Caps stay 3.
        """
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-021",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_empty_red_sha_revert_red_stubs(monkeypatch)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        with pytest.raises(PhaseFailedError) as excinfo:
            _run_tdd_cycle(task, ledger_path, console)

        output = buf.getvalue()
        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        green_calls = traces["green_calls"]
        assert isinstance(green_calls, list)

        assert _MAX_RED_ATTEMPTS == 3, (
            "AC-PLAN-001: _MAX_RED_ATTEMPTS stays 3 from ISS-ADH-017; "
            f"got {_MAX_RED_ATTEMPTS!r}"
        )
        assert green_calls == [], (
            "AC-PLAN-001: escalate_to_red / no_failing_test_adjudicated must "
            "not dispatch GREEN when red_commit_sha is empty; "
            f"got green_calls={green_calls!r} log={call_log!r}\n{output}"
        )
        assert "GREEN" not in call_log, (
            "AC-PLAN-001: _run_green_phase must never run on the empty-SHA "
            f"revert_red path; got {call_log!r}\n{output}"
        )
        assert "TRAIN_EXHAUSTED" in str(excinfo.value), (
            "AC-PLAN-001: _account_red_escalate must still stop the loop at "
            f"the existing cap; got {excinfo.value!r}\n{output}"
        )
        assert call_log.count("RED") == 3, (
            "AC-PLAN-001: initial RED plus two escalates, then the third "
            "escalate raises TRAIN_EXHAUSTED with no GREEN; "
            f"got {call_log!r}\n{output}"
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

    ``judge_action`` is ``revert_red`` (escalate) or ``revert_green``
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
        ``revert_red``. The retry RED prompt that
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
            monkeypatch, task, judge_action="revert_red"
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-004: one revert_red escalate must re-author RED "
                f"without TRAIN_EXHAUSTED; got {exc!r}\n{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        feedback_at_red = traces["feedback_at_red"]
        assert isinstance(feedback_at_red, list)
        prompts_at_red = traces["prompts_at_red"]
        assert isinstance(prompts_at_red, list)

        assert call_log.count("RED") >= 2, (
            "AC-PLAN-004: revert_red must dispatch a retry RED so the "
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

    def test_escalate_revert_green_keeps_green_train_feedback(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GREEN-train (``revert_green``) keeps the existing dump."""
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
            monkeypatch, task, judge_action="revert_green"
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-004: revert_green must keep GREEN train_feedback "
                f"and retry GREEN, not TRAIN_EXHAUSTED; got {exc!r}\n"
                f"{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        feedback_at_green = traces["feedback_at_green"]
        assert isinstance(feedback_at_green, list)

        assert call_log.count("GREEN") >= 2, (
            "AC-PLAN-004: revert_green must retry GREEN against the standing "
            f"RED; got {call_log!r}"
        )
        assert feedback_at_green[1] == GREEN_DUMP, (
            "AC-PLAN-004: revert_green keeps the existing GREEN "
            "train_feedback for the next GREEN; "
            f"got {feedback_at_green[1]!r}"
        )
        assert "previous cycle failed because" not in feedback_at_green[1], (
            "AC-PLAN-004: GREEN-train must not replace train_feedback with "
            f"the escalate note; got {feedback_at_green[1]!r}"
        )


_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_JUDGE_ACTIONS = frozenset(
    {
        "revert_red",
        "revert_green",
        "continue_refactor",
        "skip_refactor",
        "proceed_to_refactor_no_diff",
    }
)


def _unreleased_changelog(text: str) -> str:
    marker = "## [Unreleased]"
    start = text.index(marker)
    rest = text[start:]
    nxt = rest.find("\n## [", 1)
    return rest if nxt < 0 else rest[:nxt]


def _install_coerce_violation_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure_kind: str,
    declared_next_action: str | None,
    pass_after_red_count: int = 2,
    violations: list[object] | None = None,
    evaluation: dict[str, str] | None = None,
) -> dict[str, object]:
    """Stub JUDGE as an agent that declares ``declared_next_action``.

    The stub then applies ``_coerce_judge_action`` the same way
    ``_run_judge_phase`` does, so a ``test_defect`` / ``no_failing_test``
    ``COMPLIANCE_VIOLATION`` becomes ``revert_red`` even when the
    agent asked for ``revert_green``. GREEN PASS Test Integrity
    (empty ``failure_kind`` + structured category / ``test_integrity``)
    uses the same coerce path.
    """
    call_log: list[str] = []
    coerced_actions: list[str | None] = []
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
        current.current_phase = "GREEN"
        current.failure_kind = failure_kind
        current.train_feedback = STANDING_FEEDBACK
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
            current.failure_kind = ""
            current.train_feedback = ""
            coerced_actions.append("skip_refactor")
        else:
            manifest_kwargs: dict[str, object] = {
                "phase": "JUDGE",
                "status": "SUCCESS",
                "verdict": "COMPLIANCE_VIOLATION",
                "task_id": "TSK-017-05",
                "rationale": "AC-PLAN-005 coerce matrix pin",
            }
            if declared_next_action is not None:
                manifest_kwargs["next_action"] = declared_next_action
            if violations is not None:
                manifest_kwargs["violations"] = violations
            if evaluation is not None:
                manifest_kwargs["evaluation"] = evaluation
            manifest = HandoverManifest(**manifest_kwargs)
            action = _coerce_judge_action(
                manifest,
                "COMPLIANCE_VIOLATION",
                failure_kind=failure_kind,
            )
            coerced_actions.append(action)
            current.failure_kind = failure_kind
            current.judge_rejected = True
            current.pending_judge_action = action or ""
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
        "coerced_actions": coerced_actions,
        "counters_at_red": counters_at_red,
    }


class TestAcPlan005KeepJudgeVerbsCoerceAndCaps:
    """AC-PLAN-005 / US-017-02 / FR-ADHOC-017 / AC-ADHOC-017-05."""

    @pytest.mark.parametrize(
        "failure_kind,declared_next_action",
        [
            ("test_defect", "revert_green"),
            ("test_defect", None),
            ("no_failing_test", "revert_green"),
            ("no_failing_test", None),
        ],
    )
    def test_coerce_maps_test_defect_and_no_failing_test_to_revert_red(
        self,
        failure_kind: str,
        declared_next_action: str | None,
    ) -> None:
        manifest_kwargs: dict[str, object] = {}
        if declared_next_action is not None:
            manifest_kwargs["next_action"] = declared_next_action
        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-017-05",
            **manifest_kwargs,
        )
        result = _coerce_judge_action(
            manifest, "COMPLIANCE_VIOLATION", failure_kind=failure_kind
        )
        assert result == "revert_red", (
            "AC-PLAN-005: failure_kind "
            f"{failure_kind!r} on COMPLIANCE_VIOLATION must stay "
            f"revert_red even when next_action={declared_next_action!r}; "
            f"got {result!r}"
        )

    def test_judge_actions_remain_the_five_verb_frozenset(self) -> None:
        assert _JUDGE_ACTIONS == _EXPECTED_JUDGE_ACTIONS, (
            "AC-PLAN-005: _JUDGE_ACTIONS must stay the five-verb frozenset; "
            f"got {_JUDGE_ACTIONS!r}"
        )

    def test_green_and_red_caps_stay_three(self) -> None:
        assert _MAX_GREEN_ATTEMPTS == 3, (
            f"AC-PLAN-005: green_attempts cap must stay 3; got {_MAX_GREEN_ATTEMPTS!r}"
        )
        assert _MAX_RED_ATTEMPTS == 3, (
            f"AC-PLAN-005: red_attempts cap must stay 3; got {_MAX_RED_ATTEMPTS!r}"
        )

    def test_execute_phase_keeps_max_judge_attempts_three(self) -> None:
        source = inspect.getsource(_run_execute_phase)
        assert "max_judge_attempts = 3" in source, (
            "AC-PLAN-005: _run_execute_phase must keep max_judge_attempts = 3; "
            "do not retarget the EXECUTE loop."
        )

    @pytest.mark.parametrize("failure_kind", ["test_defect", "no_failing_test"])
    def test_coerced_violation_escalates_tdd_loop_now(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure_kind: str,
    ) -> None:
        """Coerced ``revert_red`` skips remaining GREEN trains."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_coerce_violation_stubs(
            monkeypatch,
            failure_kind=failure_kind,
            declared_next_action="revert_green",
            pass_after_red_count=2,
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "AC-PLAN-005: one coerced revert_red must escalate RED "
                f"without TRAIN_EXHAUSTED; got {exc!r}\n{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        coerced_actions = traces["coerced_actions"]
        assert isinstance(coerced_actions, list)
        counters_at_red = traces["counters_at_red"]
        assert isinstance(counters_at_red, list)

        assert coerced_actions[0] == "revert_red", (
            "AC-PLAN-005: _coerce_judge_action must force revert_red for "
            f"{failure_kind!r} on COMPLIANCE_VIOLATION; got {coerced_actions!r}"
        )
        assert call_log.count("RED") >= 2, (
            "AC-PLAN-005: coerced revert_red must dispatch a retry RED "
            f"now; got {call_log!r}"
        )
        first_contract = call_log[: call_log.index("RED", 1)]
        assert first_contract.count("GREEN") == 1, (
            "AC-PLAN-005: coerced revert_red must not burn remaining GREEN "
            f"tries; got {call_log!r}"
        )
        assert counters_at_red[1][0] == 0, (
            f"AC-PLAN-005: escalate resets green_attempts to 0; got {counters_at_red!r}"
        )
        assert counters_at_red[1][1] == 1, (
            f"AC-PLAN-005: escalate adds 1 to red_attempts; got {counters_at_red!r}"
        )
        assert "TRAIN_EXHAUSTED" not in buf.getvalue()

    def test_green_pass_test_integrity_explicit_revert_green_escalates(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GREEN PASS Test Integrity coerces ``revert_green`` to RED."""
        root = tmp_git_repo
        monkeypatch.chdir(root)
        _mock_pytest(monkeypatch)
        task, ledger_path, session_path = _seed_workspace(root)
        SessionState(
            active_issue_id="ISS-ADH-017",
            green_attempts=0,
            red_attempts=0,
        ).save(session_path)

        traces = _install_coerce_violation_stubs(
            monkeypatch,
            failure_kind="",
            declared_next_action="revert_green",
            pass_after_red_count=2,
            violations=[
                {
                    "category": "Test Integrity Violation",
                    "file": "tests/test_wallet.py",
                    "detail": "filename-only test does not validate AC",
                    "severity": "CRITICAL",
                    "recommendation": "Re-author RED",
                }
            ],
            evaluation={"test_integrity": "FAIL"},
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError as exc:
            raise AssertionError(
                "GH-149: GREEN PASS Test Integrity must escalate RED "
                f"without TRAIN_EXHAUSTED; got {exc!r}\n{buf.getvalue()}"
            ) from exc

        call_log = traces["call_log"]
        assert isinstance(call_log, list)
        coerced_actions = traces["coerced_actions"]
        assert isinstance(coerced_actions, list)

        assert coerced_actions[0] == "revert_red", (
            "GH-149: GREEN PASS + Test Integrity + explicit revert_green "
            f"must coerce to revert_red; got {coerced_actions!r}"
        )
        assert call_log.count("RED") >= 2, (
            f"GH-149: coerced revert_red must dispatch a retry RED; got {call_log!r}"
        )
        first_contract = call_log[: call_log.index("RED", 1)]
        assert first_contract.count("GREEN") == 1, (
            f"GH-149: Test Integrity revert_red must not train GREEN; got {call_log!r}"
        )


class TestAcPlan005SpecAlignment:
    """AC-PLAN-005: API, architecture, and CHANGELOG describe two counters."""

    def test_api_spec_documents_two_counter_tdd_retry(self) -> None:
        api = (_REPO_ROOT / "specs" / "DeviaTDD-api.md").read_text(encoding="utf-8")
        assert "green_attempts" in api, (
            "AC-PLAN-005: specs/DeviaTDD-api.md must document "
            "SessionState.green_attempts (max 3)."
        )
        assert "red_attempts" in api, (
            "AC-PLAN-005: specs/DeviaTDD-api.md must document "
            "SessionState.red_attempts (max 3)."
        )
        assert "_reset_tdd_retry_budget" in api, (
            "Cycle-entry reset: specs/DeviaTDD-api.md must name "
            "_reset_tdd_retry_budget at TDD cycle entry."
        )
        assert "TRAIN_EXHAUSTED" in api and "escalat" in api.lower(), (
            "AC-PLAN-005: specs/DeviaTDD-api.md must say TRAIN_EXHAUSTED "
            "only after three RED escalates."
        )
        assert "_coerce_judge_action" in api, (
            "AC-PLAN-005: specs/DeviaTDD-api.md must keep the "
            "_coerce_judge_action override."
        )
        assert "resetting `train_attempts`" not in api, (
            "AC-PLAN-005: specs/DeviaTDD-api.md must not reset "
            "train_attempts on revert_red."
        )
        assert "max_train_attempts" not in api, (
            "AC-PLAN-005: specs/DeviaTDD-api.md must replace "
            "max_train_attempts with green_attempts / red_attempts."
        )

    def test_architecture_spec_documents_two_counter_tdd_retry(self) -> None:
        arch = (_REPO_ROOT / "specs" / "DeviaTDD-architecture.md").read_text(
            encoding="utf-8"
        )
        assert "green_attempts" in arch, (
            "AC-PLAN-005: specs/DeviaTDD-architecture.md must document "
            "GREEN train via green_attempts."
        )
        assert "red_attempts" in arch, (
            "AC-PLAN-005: specs/DeviaTDD-architecture.md must document "
            "RED escalate via red_attempts."
        )
        assert "_reset_tdd_retry_budget" in arch, (
            "Cycle-entry reset: specs/DeviaTDD-architecture.md must name "
            "_reset_tdd_retry_budget at TDD cycle entry."
        )
        assert "TRAIN_EXHAUSTED" in arch, (
            "AC-PLAN-005: specs/DeviaTDD-architecture.md must name "
            "TRAIN_EXHAUSTED after three escalates."
        )
        assert "resetting `train_attempts`" not in arch, (
            "AC-PLAN-005: specs/DeviaTDD-architecture.md must not reset "
            "train_attempts on revert_red."
        )
        assert "max_train_attempts" not in arch, (
            "AC-PLAN-005: specs/DeviaTDD-architecture.md must replace "
            "max_train_attempts with GREEN train 3 then escalate."
        )

    def test_changelog_unreleased_records_two_counter_retry(self) -> None:
        changelog = (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = _unreleased_changelog(changelog)
        bullets = [ln for ln in unreleased.splitlines() if ln.lstrip().startswith("-")]
        matching = [
            b
            for b in bullets
            if "TRAIN_EXHAUSTED" in b
            and "revert_red" in b
            and ("GREEN" in b or "green_attempts" in b)
        ]
        assert matching, (
            "AC-PLAN-005: CHANGELOG.md [Unreleased] must have a Changed/Fixed "
            "bullet that GREEN trains three times then escalates and that "
            "three RED escalates print TRAIN_EXHAUSTED and stop the infinite "
            "revert_red loop."
        )
        reset_bullets = [
            b
            for b in bullets
            if "_reset_tdd_retry_budget" in b and "green_attempts" in b
        ]
        assert reset_bullets, (
            "CHANGELOG.md [Unreleased] must record cycle-entry "
            "_reset_tdd_retry_budget of leftover green_attempts."
        )
