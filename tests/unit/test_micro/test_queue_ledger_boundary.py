import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.cli import micro
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord


@pytest.fixture
def dependent_task(tmp_git_repo: Path):
    root = tmp_git_repo
    spec_dir = root / "specs/001-feature/001-issue"
    spec_dir.mkdir(parents=True)
    (root / "specs/issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": "001-001",
                "source_file": "specs/001-feature/issues/001-issue.md",
            }
        )
        + "\n"
    )
    (spec_dir / "tasks.md").write_text(
        "- TSK-001-01: prerequisite\n"
        "- TSK-001-02: dependent\n"
        "  - **Mode**: TDD\n"
        "  - **Test Strategy**: unit\n"
        "  - **Dependency**: TSK-001-01\n"
    )
    ledger = spec_dir / "tasks.jsonl"
    ledger.write_text(
        TaskRecord(
            id="TSK-001-01",
            issue_id="001-001",
            description="prerequisite",
            status="COMPLETED",
        ).model_dump_json()
        + "\n"
    )
    session_path = root / ".deviate/session.json"
    session_path.parent.mkdir(exist_ok=True)
    SessionState(active_issue_id="001-001").save(session_path)
    task, path = micro._find_all_pending_tasks(root, "001-001")[0]
    assert path == ledger
    assert task["depends_on"] == ["TSK-001-01"]
    return root, ledger, task


@pytest.mark.behavioral
@pytest.mark.parametrize("pinned", [False, True])
def test_red_post_persists_discovered_task_without_queue_metadata(
    dependent_task, pinned
):
    root, ledger, task = dependent_task
    before = ledger.read_bytes()
    with (
        patch(
            "deviate.cli.micro._run_test_cmd",
            return_value=subprocess.CompletedProcess([], 1, "1 failed", ""),
        ),
        patch(
            "deviate.cli.micro._run_format_cmd",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
        patch("deviate.cli.micro._commit_phase"),
    ):
        micro._red_post_kernel(task["id"] if pinned else None, root)

    assert ledger.read_bytes().startswith(before)
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(records) == 2
    record = TaskRecord.model_validate(records[-1])
    assert (record.id, record.status, record.test_strategy) == (
        task["id"],
        "RED",
        "unit",
    )
    assert "depends_on" not in records[-1]
    assert task["depends_on"] == ["TSK-001-01"]
    assert SessionState.load(root / ".deviate/session.json").current_phase == "RED"


@pytest.mark.behavioral
def test_passing_red_preserves_layer_metadata_from_queue(dependent_task):
    root, ledger, task = dependent_task

    micro._ensure_red_ledger_transition(task, ledger, root)

    record = TaskRecord.model_validate(json.loads(ledger.read_text().splitlines()[-1]))
    assert record.status == "RED"
    assert record.test_strategy == "unit"
    assert task["depends_on"] == ["TSK-001-01"]


@pytest.mark.behavioral
def test_queue_normalization_keeps_unknown_fields_invalid(dependent_task):
    from pydantic import ValidationError

    _, _, task = dependent_task
    with pytest.raises(ValidationError, match="unexpected_field"):
        micro._ledger_task_record({**task, "unexpected_field": True})
