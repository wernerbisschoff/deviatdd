"""GH-246: resume must not skip a FAILED prerequisite to dispatch its dependent."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from deviate.cli import micro as micro_mod
from deviate.state.config import SessionState


ISSUE_ID = "ISS-062"


def _rows(*records: dict) -> str:
    return "".join(json.dumps(record) + "\n" for record in records)


def _task(
    task_id: str,
    status: str,
    description: str,
) -> dict:
    return {
        "id": task_id,
        "issue_id": ISSUE_ID,
        "description": description,
        "status": status,
        "execution_mode": "TDD",
    }


def _scaffold_failed_prerequisite(root: Path) -> Path:
    """ISS-062 resume shape: COMPLETED, FAILED prereq, dependent PENDING."""
    spec_dir = root / "specs" / "adhoc" / "062-resume"
    spec_dir.mkdir(parents=True)
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": ISSUE_ID,
                "source_file": "specs/adhoc/issues/062-resume.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        "# Implementation Tasks\n\n"
        "- TSK-062-01: first slice\n"
        "  - **Mode**: TDD\n"
        "- TSK-062-02: prerequisite slice\n"
        "  - **Mode**: TDD\n"
        "- TSK-062-03: dependent slice\n"
        "  - **Mode**: TDD\n"
        "  - **Dependency**: TSK-062-02\n"
        "- TSK-062-04: later independent slice\n"
        "  - **Mode**: TDD\n",
        encoding="utf-8",
    )
    ledger = spec_dir / "tasks.jsonl"
    ledger.write_text(
        _rows(
            _task("TSK-062-01", "COMPLETED", "first slice"),
            _task("TSK-062-02", "FAILED", "prerequisite slice"),
            _task("TSK-062-03", "PENDING", "dependent slice"),
            _task("TSK-062-04", "PENDING", "later independent slice"),
        ),
        encoding="utf-8",
    )
    session_dir = root / ".deviate"
    session_dir.mkdir(exist_ok=True)
    SessionState(active_issue_id=ISSUE_ID).save(session_dir / "session.json")
    return ledger


class TestFailedPrerequisiteQueue:
    @pytest.mark.behavioral
    def test_pending_queue_includes_failed_prerequisite(self, tmp_path: Path) -> None:
        _scaffold_failed_prerequisite(tmp_path)
        pending = micro_mod._find_all_pending_tasks(tmp_path, issue_id=ISSUE_ID)
        pending_ids = [task["id"] for task, _ in pending]
        assert "TSK-062-02" in pending_ids, (
            f"FAILED prerequisite must stay in the resume queue: {pending_ids}"
        )
        assert pending_ids.index("TSK-062-02") < pending_ids.index("TSK-062-03"), (
            "FAILED prerequisite must sort before its dependent"
        )

    @pytest.mark.behavioral
    def test_resolve_resumes_failed_prerequisite_not_dependent(
        self, tmp_path: Path
    ) -> None:
        _scaffold_failed_prerequisite(tmp_path)
        result = micro_mod._resolve_task_context(None, tmp_path)
        assert result is not None
        task, _ = result
        assert task.get("id") == "TSK-062-02", (
            f"bare resume must select FAILED TSK-062-02, not dependent {task.get('id')}"
        )
        assert task.get("status") == "FAILED"

    @pytest.mark.behavioral
    def test_dependent_is_blocked_while_prerequisite_failed(
        self, tmp_path: Path
    ) -> None:
        _scaffold_failed_prerequisite(tmp_path)
        pending = micro_mod._find_all_pending_tasks(tmp_path, issue_id=ISSUE_ID)
        latest = {task["id"]: task.get("status", "") for task, _ in pending}
        latest["TSK-062-01"] = "COMPLETED"
        dependent = next(task for task, _ in pending if task["id"] == "TSK-062-03")
        unmet = micro_mod._unmet_prerequisite_ids(dependent, latest)
        assert unmet == ["TSK-062-02"], (
            f"dependent must stay blocked on FAILED TSK-062-02, got {unmet}"
        )

    @pytest.mark.behavioral
    @patch("deviate.cli.micro._execute_task_with_retry", return_value=False)
    def test_run_all_does_not_dispatch_dependent_after_failed_prereq(
        self, mock_execute: MagicMock, tmp_path: Path
    ) -> None:
        _scaffold_failed_prerequisite(tmp_path)
        buf = StringIO()
        with pytest.raises(typer.Exit) as exc_info:
            micro_mod._run_all(
                tmp_path,
                Console(file=buf),
                agent="stub",
                json_mode=True,
            )
        assert exc_info.value.exit_code == 1
        dispatched = [call.args[0].get("id") for call in mock_execute.call_args_list]
        assert dispatched == ["TSK-062-02"], (
            "resume drain must retry FAILED TSK-062-02 and must not "
            f"dispatch TSK-062-03: {dispatched}"
        )
        assert "TSK-062-03" not in dispatched
