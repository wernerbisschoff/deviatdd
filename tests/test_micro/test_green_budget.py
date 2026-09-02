"""GREEN budget (TRAIN 3/3 is a real GREEN) and escalate pre-RED walk.

Two ``revert_green`` JUDGE rejects after GREEN TEST_FAILURE must run a
third GREEN (TRAIN 3/3). Escalating after that third fail must reset to
the parent of the real RED-phase commit, not a stacked docs-feedback SHA.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from deviate.cli.micro import (
    _rollback_pre_red_if_resolvable,
    _resolve_pre_red_sha,
)
from deviate.state.config import SessionState
from tests.conftest import _git_env
from tests.helpers.cycle_driver import (
    CycleStep,
    CycleTask,
    green_files,
    green_handover_yaml,
    judge_pass_yaml,
    judge_revert_green_yaml,
    red_files,
    red_handover_yaml,
    refactor_handover_yaml,
    run_scripted_cycle,
    seed_cycle_repo,
)

_TASK = CycleTask(
    task_id="TSK-001-01",
    description="GREEN budget and pre-RED walk",
    ac="AC-PLAN-001",
)


def _sha(root: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _commit(root: Path, message: str, relpath: str, body: str) -> str:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", relpath], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    return _sha(root)


def _test_failure_then_revert_green(*, passing_third: bool) -> list[CycleStep]:
    """RED + two TEST_FAILURE→revert_green trains, then a third GREEN."""
    tid = _TASK.task_id
    ac = _TASK.ac
    steps = [
        CycleStep(
            phase="RED",
            handover=red_handover_yaml(tid),
            files=red_files(tid),
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(tid),
            files=green_files(tid),
            test_returncode=1,
        ),
        CycleStep(phase="JUDGE", handover=judge_revert_green_yaml(tid)),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(tid),
            files=green_files(tid),
            test_returncode=1,
        ),
        CycleStep(phase="JUDGE", handover=judge_revert_green_yaml(tid)),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(tid),
            files=green_files(tid),
            test_returncode=0 if passing_third else 1,
        ),
    ]
    if passing_third:
        steps.extend(
            [
                CycleStep(phase="JUDGE", handover=judge_pass_yaml(tid, ac=ac)),
                CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(tid)),
            ]
        )
        return steps
    steps.extend(
        [
            CycleStep(phase="JUDGE", handover=judge_revert_green_yaml(tid)),
            CycleStep(
                phase="RED",
                handover=red_handover_yaml(tid),
                files=red_files(tid),
            ),
            CycleStep(
                phase="GREEN",
                handover=green_handover_yaml(tid),
                files=green_files(tid),
            ),
            CycleStep(phase="JUDGE", handover=judge_pass_yaml(tid, ac=ac)),
            CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(tid)),
        ]
    )
    return steps


class TestThirdGreenRunsAfterTwoRevertGreenTestFailures:
    """Two TEST_FAILURE → revert_green cycles must still run TRAIN 3/3."""

    def test_third_green_runs_without_escalate_or_pre_red_ambiguous(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        with caplog.at_level(logging.WARNING):
            result = run_scripted_cycle(
                seeded,
                _test_failure_then_revert_green(passing_third=True),
                monkeypatch,
                mode="auto",
            )
        assert result.error is None, (
            f"third GREEN must complete the cycle; got {result.error!r}\n"
            f"{result.output}"
        )
        assert result.phases[:7] == [
            "RED",
            "GREEN",
            "JUDGE",
            "GREEN",
            "JUDGE",
            "GREEN",
            "JUDGE",
        ], f"expected RED + three GREEN/JUDGE pairs; got {result.phases!r}"
        assert result.phases.count("GREEN") >= 3, (
            f"TRAIN 3/3 must be a real GREEN; got {result.phases!r}"
        )
        assert result.phases.count("RED") == 1, (
            f"two revert_green trains must not open a new RED; got {result.phases!r}"
        )
        escalate = [
            d
            for d in result.decisions
            if d.get("decision") == "escalate_to_red"
            or d.get("reason") == "green_budget_exhausted"
        ]
        assert not escalate, (
            f"third GREEN must run, not escalate; decisions={result.decisions!r}"
        )
        reroutes = [
            d for d in result.decisions if d.get("decision") == "reroute_to_green"
        ]
        assert reroutes, (
            f"expected reroute_to_green before TRAIN 3/3; got {result.decisions!r}"
        )
        assert "TRAIN (3/3)" in result.output, (
            f"TRAIN 3/3 must print for the third GREEN; output={result.output!r}"
        )
        assert not any("PRE_RED_AMBIGUOUS" in rec.message for rec in caplog.records), (
            f"two revert_green trains must not log PRE_RED_AMBIGUOUS; {caplog.text}"
        )


class TestThirdGreenFailEscalates:
    """After three real GREENs, revert_green exhausts the GREEN budget."""

    def test_third_revert_green_escalates_to_red(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        result = run_scripted_cycle(
            seeded,
            _test_failure_then_revert_green(passing_third=False),
            monkeypatch,
            mode="auto",
        )
        assert result.error is None, (
            f"escalate after GREEN 3/3 must dispatch a new RED; got "
            f"{result.error!r}\n{result.output}"
        )
        first_contract = result.phases[: result.phases.index("RED", 1)]
        assert first_contract.count("GREEN") == 3, (
            f"three GREEN phase runs before escalate; got {result.phases!r}"
        )
        assert result.phases.count("RED") >= 2, (
            f"green_budget_exhausted must open a new RED; got {result.phases!r}"
        )
        escalate = [
            d
            for d in result.decisions
            if d.get("decision") == "escalate_to_red"
            and d.get("reason") == "green_budget_exhausted"
        ]
        assert escalate, (
            f"third revert_green must escalate with green_budget_exhausted; "
            f"got {result.decisions!r}"
        )


class TestResolvePreRedWalksPastDocsFeedback:
    """Escalate pre-RED is the parent of the real RED, not a docs SHA."""

    def test_resolve_pre_red_sha_returns_parent_of_red_not_docs(
        self,
        tmp_git_repo: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        root = tmp_git_repo
        pre_red = _sha(root)
        red_sha = _commit(
            root,
            "test(TSK-001-01): RED phase - failing test",
            "tests/test_tsk_001_01.py",
            "def test_feature() -> None:\n    assert False\n",
        )
        docs1 = _commit(
            root,
            "docs(TSK-001-01): add judge feedback for retry",
            "specs/tasks.md",
            "- **Judge Feedback**: round 1\n",
        )
        docs2 = _commit(
            root,
            "docs(TSK-001-01): add judge feedback for retry",
            "specs/tasks.md",
            "- **Judge Feedback**: round 1\n- **Judge Feedback**: round 2\n",
        )
        assert docs2 != docs1
        assert _sha(root, f"{docs2}^") == docs1

        with caplog.at_level(logging.WARNING):
            resolved = _resolve_pre_red_sha(root, docs2)
        assert resolved == pre_red, (
            f"pre-RED must be the parent of the RED commit {red_sha[:7]}, "
            f"not docs parent {docs1[:7]}; got {resolved}"
        )
        assert resolved != docs1
        assert not any("PRE_RED_AMBIGUOUS" in rec.message for rec in caplog.records), (
            caplog.text
        )

        _commit(
            root,
            "feat(TSK-001-01): GREEN phase - implementation",
            "src/tsk_001_01.py",
            "def feature() -> str:\n    return 'x'\n",
        )
        session = SessionState(red_commit_sha=docs2)
        _rollback_pre_red_if_resolvable(
            root,
            session,
            task_id="TSK-001-01",
            attempt=1,
            reason="green_budget_exhausted",
        )
        assert _sha(root) == pre_red, (
            f"escalate reset must land on the RED parent {pre_red[:7]}; "
            f"HEAD is {_sha(root)}"
        )
        assert not (root / "tests" / "test_tsk_001_01.py").exists(), (
            "escalate reset must discard this task's RED tests"
        )
