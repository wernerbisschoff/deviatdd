"""AC-PLAN-005: classify every checkpoint failure with rationale (AO-010)."""

import json
from pathlib import Path

import pytest

from deviate.state.ledger import TaskRecord


def _base_kwargs(**overrides):
    kwargs = {
        "id": "TSK-001-05",
        "issue_id": "008-001",
        "description": "checkpoint failure classification",
    }
    kwargs.update(overrides)
    return kwargs


@pytest.mark.behavioral
def test_task_record_accepts_checkpoint_started() -> None:
    rec = TaskRecord(**_base_kwargs(status="CHECKPOINT_STARTED"))
    assert rec.status == "CHECKPOINT_STARTED"


@pytest.mark.behavioral
def test_task_record_accepts_checkpoint_failed() -> None:
    rec = TaskRecord(**_base_kwargs(status="CHECKPOINT_FAILED"))
    assert rec.status == "CHECKPOINT_FAILED"


@pytest.mark.behavioral
def test_failing_handover_appends_checkpoint_failed_with_classification_and_rationale(
    tmp_path: Path,
) -> None:
    from deviate.cli import micro as micro_mod

    task = _base_kwargs(task_type="Verification_Batch", execution_mode="IMMEDIATE")
    ledger = tmp_path / "tasks.jsonl"
    handover = {"status": "FAIL", "results": [], "evidence": ""}
    micro_mod.record_checkpoint_verdict(task, handover, ledger)
    rows = [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]
    failed = [r for r in rows if r.get("status") == "CHECKPOINT_FAILED"]
    assert len(failed) == 1
    assert failed[0].get("classification")
    assert failed[0].get("rationale")


@pytest.mark.behavioral
def test_preflight_empty_results_failure_carries_own_classification(
    tmp_path: Path,
) -> None:
    from deviate.cli import micro as micro_mod

    task = _base_kwargs(task_type="Verification_Batch", execution_mode="IMMEDIATE")
    ledger = tmp_path / "tasks.jsonl"
    handover = {"status": "FAIL", "results": [], "evidence": ""}
    micro_mod.record_checkpoint_verdict(task, handover, ledger)
    rows = [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]
    failed = [r for r in rows if r.get("status") == "CHECKPOINT_FAILED"]
    assert failed and failed[0].get("classification") == "PREFLIGHT_EMPTY_RESULTS"
    rows2 = [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]
    assert [r.get("status") for r in rows2].index("CHECKPOINT_FAILED") == len(rows2) - 1
