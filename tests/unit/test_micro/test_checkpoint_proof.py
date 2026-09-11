"""AC-PLAN-004: reject incomplete checkpoint proof."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deviate.cli import micro as micro_mod


def _handover(**overrides: object) -> dict:
    base: dict = {
        "task_id": "TSK-001-04",
        "phase": "CHECKPOINT",
        "status": "PASS",
        "declared_commands": ["mise unit"],
        "command_reports": [{"command": "mise unit", "exit_code": 0}],
        "declared_criteria": ["AC-PLAN-004"],
        "criterion_coverage": ["AC-PLAN-004"],
        "exit_code": 0,
        "evidence": [{"observed": "tests fail without proof gate"}],
    }
    base.update(overrides)
    return base


def _assert_invalid(handover: dict) -> str:
    try:
        result = micro_mod.validate_checkpoint_proof(handover)
    except (ValueError, AssertionError) as exc:
        return str(exc)
    if isinstance(result, tuple):
        ok, reason = result[0], str(result[1] if len(result) > 1 else "")
        assert not ok, "partial proof must not validate"
        return reason
    assert not result, "partial proof must not validate"
    return "invalid"


def _assert_no_completed(ledger: Path) -> None:
    if not ledger.exists():
        return
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert json.loads(line).get("status") != "COMPLETED"


class TestRejectIncompleteProof:
    @pytest.mark.behavioral
    def test_missing_command_report_fails(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        handover = _handover(command_reports=[])
        _assert_invalid(handover)
        _assert_no_completed(ledger)

    @pytest.mark.behavioral
    def test_missing_criterion_fails(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        handover = _handover(criterion_coverage=[])
        _assert_invalid(handover)
        _assert_no_completed(ledger)

    @pytest.mark.behavioral
    def test_nonzero_exit_on_pass_fails(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        handover = _handover(exit_code=1)
        _assert_invalid(handover)
        _assert_no_completed(ledger)

    @pytest.mark.behavioral
    def test_empty_evidence_fails(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        handover = _handover(evidence=[])
        _assert_invalid(handover)
        _assert_no_completed(ledger)

    @pytest.mark.behavioral
    def test_preflight_empty_results_fails(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        handover = _handover(
            status="FAIL",
            command_reports=[],
            criterion_coverage=[],
            evidence=[],
            exit_code=0,
            results=[],
        )
        _assert_invalid(handover)
        _assert_no_completed(ledger)
