"""AC-PLAN-002: checkpoint dispatch carries full verification context."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deviate.cli import micro as micro_mod
from deviate.core.agent import HandoverManifest


def _checkpoint_task() -> dict:
    return {
        "id": "TSK-001-02",
        "issue_id": "008-001",
        "description": "checkpoint",
        "status": "PENDING",
        "execution_mode": "IMMEDIATE",
        "task_type": "Verification_Batch",
    }


CONTEXT_FIELDS = (
    "task",
    "issue",
    "contract",
    "commands",
    "worktree",
    "doc",
    "capabilit",
)


class TestCheckpointDispatch:
    @pytest.mark.behavioral
    def test_prompt_resource_exists(self):
        assert (Path("src/deviate/prompts/auto/checkpoint.md")).exists()

    @pytest.mark.spy
    def test_single_agent_call_with_full_context(self, tmp_path: Path):
        ledger = tmp_path / "tasks.jsonl"
        calls: list[str] = []
        with patch.object(
            micro_mod.AgentBackend,
            "invoke",
            autospec=True,
            side_effect=lambda self, prompt, **kw: (
                calls.append(prompt)
                or HandoverManifest(phase="CHECKPOINT", status="PASS")
            ),
        ):
            micro_mod._run_checkpoint_phase(
                _checkpoint_task(), ledger, Console(quiet=True)
            )
        assert len(calls) == 1
        lowered = calls[0].lower()
        for field in CONTEXT_FIELDS:
            assert field in lowered, f"context packet missing {field}"

    @pytest.mark.behavioral
    def test_agent_failure_records_checkpoint_failed_never_completed(
        self, tmp_path: Path
    ):
        from deviate.core.agent import AgentSubprocessError

        ledger = tmp_path / "tasks.jsonl"
        with patch.object(
            micro_mod.AgentBackend,
            "invoke",
            autospec=True,
            side_effect=AgentSubprocessError("boom"),
        ):
            micro_mod._run_checkpoint_phase(
                _checkpoint_task(), ledger, Console(quiet=True)
            )
        text = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
        assert "CHECKPOINT_FAILED" in text
        assert "COMPLETED" not in text

    @pytest.mark.behavioral
    def test_red_green_entrypoints_stay_wired(self, tmp_path: Path):
        task = {
            "id": "TSK-001-02",
            "issue_id": "008-001",
            "description": "tdd",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger = tmp_path / "tasks.jsonl"
        with (
            patch.object(micro_mod, "_run_tdd_cycle") as mock_tdd,
            patch.object(micro_mod, "_run_checkpoint_phase") as mock_cp,
        ):
            micro_mod._dispatch_task(task, ledger, Console(quiet=True))
        mock_tdd.assert_called_once()
        mock_cp.assert_not_called()
