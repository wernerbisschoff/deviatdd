"""AC-PLAN-006 / AC-PLAN-007: checkpoint queue close path plus halt path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deviate.cli import micro as micro_mod
from deviate.state.ledger import TaskEvidenceBundle


def _task(task_id: str, description: str = "checkpoint") -> dict:
    return {
        "id": task_id,
        "issue_id": "008-001",
        "description": description,
        "status": "PENDING",
        "execution_mode": "IMMEDIATE",
        "task_type": "Verification_Batch",
    }


def _passing_handover(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "phase": "CHECKPOINT",
        "status": "PASS",
        "results": [{"check": "mise unit", "ok": True}],
        "declared_commands": ["mise unit"],
        "command_reports": [{"command": "mise unit", "exit_code": 0}],
        "declared_criteria": ["AC-PLAN-006"],
        "criterion_coverage": ["AC-PLAN-006"],
        "exit_code": 0,
        "evidence": [{"observed": "queue advanced after recorded proof"}],
    }


def _failing_handover(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "phase": "CHECKPOINT",
        "status": "FAIL",
        "results": [{"check": "mise unit", "ok": False}],
        "declared_commands": ["mise unit"],
        "command_reports": [],
        "declared_criteria": ["AC-PLAN-007"],
        "criterion_coverage": [],
        "exit_code": 1,
        "evidence": [],
    }


def _rows(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    return [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _scaffold_queue(root: Path) -> Path:
    spec_dir = root / "specs" / "008-slice"
    spec_dir.mkdir(parents=True)
    (spec_dir / "tasks.md").write_text(
        "- TSK-001-01: first checkpoint\n- TSK-001-02: second checkpoint\n",
        encoding="utf-8",
    )
    return spec_dir / "tasks.jsonl"


class TestCheckpointQueue:
    @pytest.mark.behavioral
    def test_pass_appends_completed_with_typed_evidence(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        micro_mod.record_checkpoint_verdict(
            _task("TSK-001-01"), _passing_handover("TSK-001-01"), ledger
        )
        completed = [r for r in _rows(ledger) if r.get("status") == "COMPLETED"]
        assert completed, "passing handover must append COMPLETED"
        bundle = TaskEvidenceBundle.model_validate(completed[-1]["evidence"])
        assert bundle.items, "COMPLETED row must carry a typed evidence bundle"

    @pytest.mark.behavioral
    def test_pass_advances_queue_to_next_task(self, tmp_path: Path):
        ledger = _scaffold_queue(tmp_path)
        micro_mod.record_checkpoint_verdict(
            _task("TSK-001-01"), _passing_handover("TSK-001-01"), ledger
        )
        pending = micro_mod._find_all_pending_tasks(tmp_path, issue_id="008-001")
        pending_ids = [task["id"] for task, _ in pending]
        assert pending_ids == ["TSK-001-02"], (
            f"queue must advance past completed checkpoint: {pending_ids}"
        )

    @pytest.mark.behavioral
    def test_fail_halts_queue_and_preserves_predecessors(self, tmp_path: Path):
        ledger = _scaffold_queue(tmp_path)
        predecessor = _task("TSK-001-01", "done work")
        from deviate.state.ledger import TaskRecord, append_task_transition

        append_task_transition(
            TaskRecord.model_validate({**predecessor, "status": "COMPLETED"}), ledger
        )
        micro_mod.record_checkpoint_verdict(
            _task("TSK-001-02"), _failing_handover("TSK-001-02"), ledger
        )
        rows = _rows(ledger)
        failed = [
            r
            for r in rows
            if r.get("id") == "TSK-001-02" and r.get("status") == "CHECKPOINT_FAILED"
        ]
        assert failed, "failing handover must append CHECKPOINT_FAILED"
        assert failed[-1].get("classification"), (
            "CHECKPOINT_FAILED must carry a classification"
        )
        assert failed[-1].get("rationale"), "CHECKPOINT_FAILED must carry a rationale"
        assert "CHECKPOINT_FAILED" in micro_mod._TERMINAL_STATUSES, (
            "halt requires terminal CHECKPOINT_FAILED"
        )
        assert not [
            r
            for r in rows
            if r.get("id") == "TSK-001-02" and r.get("status") == "COMPLETED"
        ]
        assert [
            r
            for r in rows
            if r.get("id") == "TSK-001-01" and r.get("status") == "COMPLETED"
        ], "predecessor COMPLETED rows stay intact"
        pending = micro_mod._find_all_pending_tasks(tmp_path, issue_id="008-001")
        assert "TSK-001-02" not in [task["id"] for task, _ in pending], (
            "failed checkpoint halts the queue"
        )

    @pytest.mark.behavioral
    def test_fail_on_first_task_starts_nothing_after_it(self, tmp_path: Path):
        ledger = _scaffold_queue(tmp_path)
        micro_mod.record_checkpoint_verdict(
            _task("TSK-001-01"), _failing_handover("TSK-001-01"), ledger
        )
        rows = _rows(ledger)
        assert [r for r in rows if r.get("status") == "CHECKPOINT_FAILED"]
        assert not [r for r in rows if r.get("id") == "TSK-001-02"], (
            "zero tasks start after a first-task failure"
        )
        pending = micro_mod._find_all_pending_tasks(tmp_path, issue_id="008-001")
        assert "TSK-001-01" not in [task["id"] for task, _ in pending], (
            "failed first task halts the queue"
        )
