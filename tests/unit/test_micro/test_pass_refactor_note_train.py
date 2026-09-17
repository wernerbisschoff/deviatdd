"""GH-260: COMPLIANCE_PASS + advisory REFACTOR NOTE must not retrain GREEN.

A passing JUDGE that only emits ``REFACTOR NOTE:`` style/polish advice
must advance to REFACTOR or ``skip_refactor`` COMPLETED. Treating the
note as ``train_feedback`` (including after ``pending_judge_action`` is
lost) used to loop GREEN until TRAIN_EXHAUSTED and leave the ledger
FAILED.
"""

from __future__ import annotations

import io
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import (
    PhaseFailedError,
    _apply_judge_verdict,
    _run_green_phase,
    _run_tdd_cycle,
    _train_feedback_is_advisory,
)
from deviate.core.agent import HandoverManifest
from deviate.core.judge_policy import train_feedback_is_advisory
from deviate.state.config import SessionState
from tests.unit.test_micro.test_judge_refactor_note_routing import (
    _NOTE,
    _PASS_FEEDBACK,
    _SPEC_GAP_FEEDBACK,
    _TASK_ID,
    _ledger_statuses,
    _manifest,
    _seed_green_repo,
    _task,
)

_PYTEST_MARK_NOTE = (
    "REFACTOR NOTE: register a pytest mark for this module; "
    "out of scope for this slice."
)
_GREEN_TEST_DUMP = (
    "The test suite failed after GREEN implementation.\n\n"
    "<test_output>\n1 failed\n</test_output>"
)


class TestTrainFeedbackIsAdvisory:
    """``train_feedback_is_advisory`` is the GH-260 retrain gate."""

    def test_pass_preamble_plus_note(self) -> None:
        assert train_feedback_is_advisory(_PASS_FEEDBACK) is True
        assert _train_feedback_is_advisory(_PASS_FEEDBACK) is True

    def test_extracted_refactor_note(self) -> None:
        assert train_feedback_is_advisory(_NOTE) is True
        assert train_feedback_is_advisory(_PYTEST_MARK_NOTE) is True

    def test_spec_gap_is_not_advisory(self) -> None:
        assert train_feedback_is_advisory(_SPEC_GAP_FEEDBACK) is False

    def test_green_test_dump_is_not_advisory(self) -> None:
        assert train_feedback_is_advisory(_GREEN_TEST_DUMP) is False

    def test_empty_is_not_advisory(self) -> None:
        assert train_feedback_is_advisory("") is False

    def test_retry_instruction_is_not_advisory(self) -> None:
        assert (
            train_feedback_is_advisory(
                "REFACTOR NOTE: unused import.\n"
                "The next GREEN attempt must: implement the error path."
            )
            is False
        )


class TestGreenSkipsAdvisoryNoteRetry:
    """GREEN already done + leftover REFACTOR NOTE must not re-invoke GREEN."""

    def test_already_done_plus_note_does_not_invoke_green(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_green_repo(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.train_feedback = _NOTE
        session.last_judge_verdict = "COMPLIANCE_PASS"
        session.pending_judge_action = ""
        session.save(session_path)
        ledger = (
            tmp_git_repo
            / "specs"
            / "158-refactor-note"
            / "001-pass-note"
            / "tasks.jsonl"
        )
        invoke_count = {"n": 0}

        def _capture_invoke(*_args: object, **_kwargs: object) -> tuple[object, str]:
            invoke_count["n"] += 1
            return (
                HandoverManifest(phase="GREEN", status="SUCCESS", task_id=_TASK_ID),
                "",
            )

        monkeypatch.setattr("deviate.cli.micro._invoke_agent", _capture_invoke)
        monkeypatch.setattr(
            "deviate.cli.micro._run_test_cmd",
            lambda *_a, **_k: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        )
        monkeypatch.setattr(
            "deviate.cli.micro._run_pytest",
            lambda *_a, **_k: subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="", stderr=""
            ),
        )
        monkeypatch.setattr(
            "deviate.cli.micro._verify_clean_worktree", lambda *_a, **_k: None
        )
        monkeypatch.setattr("deviate.cli.micro._commit_phase", lambda *_a, **_k: True)
        attempts_before = session.green_attempts
        with chdir(tmp_git_repo):
            result = _run_green_phase(
                _task(),
                ledger,
                session,
                session_path,
                Console(file=io.StringIO(), force_terminal=False),
            )
        assert invoke_count["n"] == 0, (
            "GH-260: leftover REFACTOR NOTE must not re-run GREEN; "
            f"invoked {invoke_count['n']} time(s)"
        )
        assert result.green_attempts == attempts_before, (
            "GH-260: skipping an advisory note must not burn GREEN train budget; "
            f"attempts {attempts_before} → {result.green_attempts}"
        )
        assert _NOTE in result.train_feedback


class TestPassNoteDoesNotTrainExhaust:
    """Pending-loss hole: PASS+note with empty pending_judge_action.

    Production TSK-005-02 logged 9 COMPLIANCE_PASS / JUDGE_REFACTOR_NOTE
    rows (including skip_refactor) then TRAIN_EXHAUSTED. The runner treated
    the leftover note as a GREEN retrain contract after the forward route
    was cleared.
    """

    @pytest.mark.parametrize(
        "next_action",
        ["continue_refactor", "skip_refactor", None],
    )
    def test_lost_pending_after_pass_note_goes_to_refactor_or_complete(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        next_action: str | None,
    ) -> None:
        _seed_green_repo(tmp_git_repo)
        call_log: list[str] = []
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        ledger = (
            tmp_git_repo
            / "specs"
            / "158-refactor-note"
            / "001-pass-note"
            / "tasks.jsonl"
        )
        no_refactor = next_action == "skip_refactor"

        def _red(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("RED")
            session_path = args[3]
            assert isinstance(session_path, Path)
            current = SessionState.load(session_path)
            current.current_phase = "RED"
            current.save(session_path)
            return current

        def _green(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("GREEN")
            session_path = args[3]
            assert isinstance(session_path, Path)
            current = SessionState.load(session_path)
            current.green_attempts += 1
            current.current_phase = "GREEN"
            current.train_feedback = ""
            current.failure_kind = ""
            current.judge_rejected = False
            current.save(session_path)
            return current

        def _judge(*args: object, **kwargs: object) -> SessionState:
            call_log.append("JUDGE")
            session_path = args[3]
            assert isinstance(session_path, Path)
            current = SessionState.load(session_path)
            manifest = _manifest(
                next_action=next_action,
                train_feedback=_PASS_FEEDBACK,
            )
            applied = _apply_judge_verdict(
                _task(),
                ledger,
                current,
                session_path,
                Console(file=io.StringIO(), force_terminal=False),
                manifest,
                injected_diff="",
                no_refactor=no_refactor,
            )
            # Reproduce the suspected hole: forward route dropped, note stays.
            applied.pending_judge_action = ""
            applied.judge_rejected = False
            applied.train_feedback = _NOTE
            applied.last_judge_verdict = "COMPLIANCE_PASS"
            applied.save(session_path)
            return applied

        def _refactor(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("REFACTOR")
            session = args[2]
            assert isinstance(session, SessionState)
            session.pending_judge_action = ""
            return session.force_transition_to("IDLE")

        monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
        monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
        monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
        monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
        monkeypatch.setattr(
            "deviate.cli.micro._verify_worktree_branch", lambda *_a, **_k: None
        )
        monkeypatch.setattr(
            "deviate.cli.micro._run_pytest",
            lambda *_a, **_k: subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="", stderr=""
            ),
        )

        with chdir(tmp_git_repo):
            try:
                _run_tdd_cycle(
                    _task(),
                    ledger,
                    console,
                    start_phase="GREEN",
                    no_refactor=no_refactor,
                )
                error: BaseException | None = None
            except PhaseFailedError as exc:
                error = exc

        output = buf.getvalue()
        assert error is None or "TRAIN_EXHAUSTED" not in str(error), (
            f"GH-260: PASS + REFACTOR NOTE must not TRAIN_EXHAUSTED "
            f"(next_action={next_action!r}); error={error!r} phases={call_log!r}\n"
            f"{output}"
        )
        assert "TRAIN_EXHAUSTED" not in output, (
            f"GH-260: console must not print TRAIN_EXHAUSTED; "
            f"phases={call_log!r}\n{output}"
        )
        assert call_log.count("GREEN") == 1, (
            f"GH-260: advisory note must not retrain GREEN; got {call_log!r}\n{output}"
        )
        assert call_log.count("JUDGE") == 1, (
            f"GH-260: one PASS is enough; got {call_log!r}\n{output}"
        )
        assert "RED" not in call_log, (
            f"GH-260: must not escalate to RED; got {call_log!r}\n{output}"
        )
        if no_refactor:
            assert "REFACTOR" not in call_log, (
                f"GH-260: skip_refactor must not enter REFACTOR; "
                f"got {call_log!r}\n{output}"
            )
            assert "FAILED" not in _ledger_statuses(ledger), (
                f"GH-260: skip_refactor + note must not FAILED; "
                f"{_ledger_statuses(ledger)!r}\n{output}"
            )
        else:
            assert call_log == ["GREEN", "JUDGE", "REFACTOR"], (
                f"GH-260: expected GREEN→JUDGE→REFACTOR; got {call_log!r}\n{output}"
            )

    def test_nine_pass_notes_never_reach_train_exhausted(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Always-PASS + note (2× skip_refactor) must converge, not 3×3 exhaust."""
        _seed_green_repo(tmp_git_repo)
        call_log: list[str] = []
        judge_actions = [
            "continue_refactor",
            "skip_refactor",
            "continue_refactor",
            "skip_refactor",
            "continue_refactor",
        ]
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        ledger = (
            tmp_git_repo
            / "specs"
            / "158-refactor-note"
            / "001-pass-note"
            / "tasks.jsonl"
        )

        def _red(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("RED")
            path = args[3]
            assert isinstance(path, Path)
            current = SessionState.load(path)
            current.current_phase = "RED"
            current.save(path)
            return current

        def _green(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("GREEN")
            path = args[3]
            assert isinstance(path, Path)
            current = SessionState.load(path)
            current.green_attempts += 1
            current.current_phase = "GREEN"
            current.train_feedback = ""
            current.failure_kind = ""
            current.judge_rejected = False
            current.save(path)
            return current

        def _judge(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("JUDGE")
            path = args[3]
            assert isinstance(path, Path)
            current = SessionState.load(path)
            judge_n = call_log.count("JUDGE") - 1
            action = judge_actions[min(judge_n, len(judge_actions) - 1)]
            applied = _apply_judge_verdict(
                _task(),
                ledger,
                current,
                path,
                Console(file=io.StringIO(), force_terminal=False),
                _manifest(next_action=action, train_feedback=_PASS_FEEDBACK),
                injected_diff="",
                no_refactor=action == "skip_refactor",
            )
            applied.pending_judge_action = ""
            applied.train_feedback = _NOTE
            applied.judge_rejected = False
            applied.last_judge_verdict = "COMPLIANCE_PASS"
            applied.save(path)
            return applied

        def _refactor(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("REFACTOR")
            session_arg = args[2]
            assert isinstance(session_arg, SessionState)
            session_arg.pending_judge_action = ""
            return session_arg.force_transition_to("IDLE")

        monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
        monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
        monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
        monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
        monkeypatch.setattr(
            "deviate.cli.micro._verify_worktree_branch", lambda *_a, **_k: None
        )

        with chdir(tmp_git_repo):
            try:
                _run_tdd_cycle(
                    _task(),
                    ledger,
                    console,
                    start_phase="GREEN",
                )
                error: BaseException | None = None
            except PhaseFailedError as exc:
                error = exc

        output = buf.getvalue()
        statuses = _ledger_statuses(ledger)
        assert error is None, (
            f"GH-260: always-PASS notes must converge; error={error!r} "
            f"phases={call_log!r} statuses={statuses!r}\n{output}"
        )
        assert "TRAIN_EXHAUSTED" not in output
        assert call_log.count("GREEN") <= 1
        assert call_log.count("JUDGE") == 1
        assert "FAILED" not in statuses
