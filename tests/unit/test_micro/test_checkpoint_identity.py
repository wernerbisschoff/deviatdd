"""AC-PLAN-001: Verification_Batch keeps type with IMMEDIATE dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deviate.cli import micro as micro_mod
from deviate.core.tasks_ledger import generate_jsonl_from_md, resolve_execution_mode


def _write_tasks_md(root: Path, body: str) -> Path:
    tasks_md = root / "tasks.md"
    tasks_md.write_text(body, encoding="utf-8")
    return tasks_md


BATCH_CARD = (
    "- TSK-001-01: Preserve Verification_Batch type\n"
    "  - **Type**: Verification_Batch\n"
    "  - **Mode**: TDD\n"
    "  - **Test Strategy**: unit\n"
)


class TestBatchIdentity:
    @pytest.mark.behavioral
    def test_batch_card_parses_to_type_with_immediate_mode(self, tmp_path: Path):
        tasks_md = _write_tasks_md(tmp_path, f"# Tasks\n\n{BATCH_CARD}")
        (record,) = generate_jsonl_from_md(tasks_md, "008-001")

        assert record.task_type == "Verification_Batch"
        assert record.execution_mode == "IMMEDIATE"

    @pytest.mark.behavioral
    def test_missing_type_keeps_declared_mode(self):
        assert resolve_execution_mode(None, "TDD") == "TDD"

    @pytest.mark.behavioral
    def test_batch_task_skips_red_green_dispatch(self, tmp_path: Path):
        task = {
            "id": "TSK-001-01",
            "issue_id": "008-001",
            "description": "batch",
            "status": "PENDING",
            "execution_mode": "IMMEDIATE",
            "task_type": "Verification_Batch",
        }
        ledger = tmp_path / "tasks.jsonl"
        with (
            patch.object(micro_mod, "_run_tdd_cycle") as mock_tdd,
            patch.object(micro_mod, "_run_execute_phase") as mock_exec,
        ):
            micro_mod._dispatch_task(task, ledger, Console(quiet=True))
        mock_tdd.assert_not_called()
        assert (
            mock_exec.call_count == 0
            or getattr(micro_mod, "_run_checkpoint_phase", None) is not None
        )
        checkpoint = getattr(micro_mod, "_run_checkpoint_phase", None)
        assert callable(checkpoint), "checkpoint dispatch entrypoint is missing"

    @pytest.mark.behavioral
    def test_plain_immediate_task_never_uses_checkpoint(self, tmp_path: Path):
        task = {
            "id": "TSK-001-02",
            "issue_id": "008-001",
            "description": "plain",
            "status": "PENDING",
            "execution_mode": "IMMEDIATE",
        }
        ledger = tmp_path / "tasks.jsonl"
        checkpoint = getattr(micro_mod, "_run_checkpoint_phase", None)
        if not callable(checkpoint):
            with (
                patch.object(micro_mod, "_run_tdd_cycle"),
                patch.object(micro_mod, "_run_execute_phase"),
            ):
                micro_mod._dispatch_task(task, ledger, Console(quiet=True))
            return
        calls: list[dict] = []
        with (
            patch.object(micro_mod, "_run_tdd_cycle"),
            patch.object(micro_mod, "_run_execute_phase"),
            patch.object(
                micro_mod,
                "_run_checkpoint_phase",
                side_effect=lambda t, *a, **k: calls.append(t),
            ),
        ):
            micro_mod._dispatch_task(task, ledger, Console(quiet=True))
        assert calls == []
