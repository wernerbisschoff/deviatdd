"""GH-230: contradictory successive JUDGE requirements halt to HITL.

Wallet-service TSK-001-06 burned the GREEN/RED train budget because the
runner treated each oscillating JUDGE reject as more implementation
training. The post-verdict gate must stop on the second incompatible
requirement and mark HITL_PENDING instead of TRAIN_EXHAUSTED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deviate.cli.micro import HitlEscalationError, _MAX_RED_ATTEMPTS
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from tests.helpers.cycle_driver import (
    CycleStep,
    CycleTask,
    green_files,
    green_handover_yaml,
    judge_fail_yaml,
    red_files,
    red_handover_yaml,
    run_scripted_cycle,
    seed_cycle_repo,
)
from tests.unit.test_core.test_judge_contradiction import (
    ERROR_PATH,
    INCREMENT,
    PRESERVE_FIXTURE,
    STRICT_IDENTITY,
)
from tests.unit.test_micro.test_judge_refactor_note_routing import (
    _manifest,
    _seed_green_repo,
)
from tests.unit.test_micro.test_judge_verdicts import _apply_existing


def _reject_manifest(feedback: str) -> HandoverManifest:
    return _manifest(
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_green",
        train_feedback=feedback,
        status="FAILURE",
    )


def _ledger_statuses_path(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        json.loads(line).get("status", "")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestApplyJudgeVerdictContradictionHalt:
    def test_second_contradictory_reject_is_hitl_not_train(
        self, tmp_git_repo: Path
    ) -> None:
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        first = _apply_existing(
            tmp_git_repo, ledger_path, _reject_manifest(STRICT_IDENTITY)
        )
        assert first.pending_judge_action == "revert_green"
        assert first.red_attempts == 0

        with pytest.raises(HitlEscalationError, match="requirement contradiction"):
            _apply_existing(
                tmp_git_repo, ledger_path, _reject_manifest(PRESERVE_FIXTURE)
            )

        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.red_attempts == 0
        assert session.green_attempts == 0
        statuses = _ledger_statuses_path(ledger_path)
        assert "HITL_PENDING" in statuses
        assert "FAILED" not in statuses

    def test_compatible_successive_rejects_still_train(
        self, tmp_git_repo: Path
    ) -> None:
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        _apply_existing(tmp_git_repo, ledger_path, _reject_manifest(INCREMENT))
        session = _apply_existing(
            tmp_git_repo, ledger_path, _reject_manifest(ERROR_PATH)
        )
        assert session.pending_judge_action == "revert_green"
        statuses = _ledger_statuses_path(ledger_path)
        assert "HITL_PENDING" not in statuses


class TestCycleContradictionStopsBeforeTrainExhausted:
    def test_oscillating_judge_requirements_do_not_burn_red_budget(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        task = CycleTask(
            task_id="TSK-160-01",
            description="Contradictory JUDGE identity vs fixture",
            ac="AC-PLAN-001",
        )
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[task])
        steps = [
            CycleStep(
                phase="RED",
                handover=red_handover_yaml(task.task_id),
                files=red_files(task.task_id),
            ),
            CycleStep(
                phase="GREEN",
                handover=green_handover_yaml(task.task_id),
                files=green_files(task.task_id),
            ),
            CycleStep(
                phase="JUDGE",
                handover=judge_fail_yaml(task.task_id, train_feedback=STRICT_IDENTITY),
            ),
            CycleStep(
                phase="GREEN",
                handover=green_handover_yaml(task.task_id),
                files=green_files(task.task_id),
            ),
            CycleStep(
                phase="JUDGE",
                handover=judge_fail_yaml(task.task_id, train_feedback=PRESERVE_FIXTURE),
            ),
        ]
        result = run_scripted_cycle(seeded, steps, monkeypatch, mode="auto")
        assert result.error is not None, result.output
        assert isinstance(result.error, HitlEscalationError), result.output
        assert "TRAIN_EXHAUSTED" not in result.output
        assert "JUDGE_REQUIREMENT_CONTRADICTION" in result.output
        assert result.session is not None
        assert result.session.red_attempts < _MAX_RED_ATTEMPTS
        assert result.session.red_attempts == 0
        assert result.phases.count("GREEN") == 2
        assert result.phases.count("JUDGE") == 2
        assert "HITL_PENDING" in result.ledger_statuses
        assert "FAILED" not in result.ledger_statuses
