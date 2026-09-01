"""Scripted TDD-cycle driver fixtures — auto ``_run_tdd_cycle`` and manual pre/post.

These are the regressions that would have caught GH-158 and GH-148 before
production: a real handover YAML through the agent-result / ``judge post``
path, with phase functions and ``_apply_judge_verdict`` left intact.
Existing coerce / prompt / stubbed-phase tests stay; this file is
additional coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.cycle_driver import (
    _REFACTOR_NOTE,
    CycleTask,
    gh158_steps,
    happy_path_steps,
    poison_stale_skip_refactor,
    run_scripted_cycle,
    seed_cycle_repo,
    skip_refactor_steps,
)

_TASK_A = CycleTask(
    task_id="TSK-160-01",
    description="First cycle slice",
    ac="AC-PLAN-001",
)
_TASK_B = CycleTask(
    task_id="TSK-160-02",
    description="Second cycle slice",
    ac="AC-PLAN-002",
)


def _assert_no_reject(result: object) -> None:
    output = getattr(result, "output", "")
    session = getattr(result, "session", None)
    assert getattr(result, "error", None) is None, (
        f"cycle driver raised {result.error!r}\n{output}"
    )
    assert "JUDGE_REJECTED" not in output, output
    assert "COMPLETED_EVIDENCE_MISSING" not in output, output
    if session is not None:
        assert session.judge_rejected is False


@pytest.mark.parametrize("mode", ["auto", "manual"])
class TestHappyPath:
    def test_red_green_judge_pass_reaches_refactor(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        mode: str,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK_A])
        result = run_scripted_cycle(
            seeded,
            happy_path_steps(_TASK_A.task_id, ac=_TASK_A.ac),
            monkeypatch,
            mode=mode,  # type: ignore[arg-type]
        )
        _assert_no_reject(result)
        assert result.phases == ["RED", "GREEN", "JUDGE", "REFACTOR"], (
            f"{mode}: expected full cycle; got {result.phases!r}\n{result.output}"
        )
        statuses = result.statuses_for(_TASK_A.task_id)
        assert statuses == ["PENDING", "RED", "GREEN", "JUDGE", "COMPLETED"], (
            f"{mode}: ledger {statuses!r}\n{result.output}"
        )
        assert "JUDGE_REJECTED" not in {d.get("event") for d in result.decisions}


@pytest.mark.parametrize("mode", ["auto", "manual"])
@pytest.mark.parametrize("next_action", ["revert_red", "revert_to_red"])
class TestGh158PassPlusRefactorNote:
    def test_judge_pass_plus_note_goes_to_refactor_not_red(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        mode: str,
        next_action: str,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK_A])
        result = run_scripted_cycle(
            seeded,
            gh158_steps(_TASK_A.task_id, ac=_TASK_A.ac, next_action=next_action),
            monkeypatch,
            mode=mode,  # type: ignore[arg-type]
        )
        _assert_no_reject(result)
        assert result.phases == ["RED", "GREEN", "JUDGE", "REFACTOR"], (
            f"{mode}/{next_action}: expected JUDGE→REFACTOR, not RED; "
            f"got {result.phases!r}\n{result.output}"
        )
        statuses = result.statuses_for(_TASK_A.task_id)
        assert "RED" in statuses
        assert statuses.count("RED") == 1, (
            f"{mode}/{next_action}: ledger must not return to RED; "
            f"got {statuses!r}\n{result.output}"
        )
        assert "JUDGE" in statuses
        assert statuses[-1] == "COMPLETED"
        assert result.session is not None
        assert result.session.pending_judge_action != "revert_red"
        assert _REFACTOR_NOTE in result.session.train_feedback, (
            f"{mode}/{next_action}: REFACTOR train_feedback must keep the note; "
            f"got {result.session.train_feedback!r}"
        )
        if mode == "auto":
            refactor_prompts = result.prompts.get("REFACTOR", [])
            assert refactor_prompts, f"{mode}: REFACTOR agent was not invoked"
            assert _REFACTOR_NOTE in refactor_prompts[0]


@pytest.mark.parametrize("mode", ["auto", "manual"])
class TestGh148StaleSkipRefactor:
    def test_second_task_after_red_enters_green_judge(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        mode: str,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK_A, _TASK_B])
        first = run_scripted_cycle(
            seeded,
            skip_refactor_steps(_TASK_A.task_id, ac=_TASK_A.ac),
            monkeypatch,
            mode=mode,  # type: ignore[arg-type]
            task_id=_TASK_A.task_id,
        )
        _assert_no_reject(first)
        assert first.statuses_for(_TASK_A.task_id)[-1] == "COMPLETED"

        poison_stale_skip_refactor(tmp_git_repo, prior_task_id=_TASK_A.task_id)

        second = run_scripted_cycle(
            seeded,
            happy_path_steps(_TASK_B.task_id, ac=_TASK_B.ac),
            monkeypatch,
            mode=mode,  # type: ignore[arg-type]
            task_id=_TASK_B.task_id,
        )
        _assert_no_reject(second)
        assert "GREEN" in second.phases, (
            f"{mode}: TSK-B after canned RED must enter GREEN; "
            f"got {second.phases!r}\n{second.output}"
        )
        assert "JUDGE" in second.phases, (
            f"{mode}: TSK-B after canned RED must enter JUDGE; "
            f"got {second.phases!r}\n{second.output}"
        )
        assert second.phases.index("GREEN") < second.phases.index("JUDGE")
        assert "COMPLETED_EVIDENCE_MISSING" not in second.output
        statuses = second.statuses_for(_TASK_B.task_id)
        assert statuses[:3] == ["PENDING", "RED", "GREEN"], (
            f"{mode}: TSK-B must not complete from stale skip_refactor; "
            f"got {statuses!r}\n{second.output}"
        )
        assert "JUDGE" in statuses or "COMPLETED" in statuses
        assert statuses[-1] == "COMPLETED"
