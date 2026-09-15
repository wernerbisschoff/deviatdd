import json

from deviate.state.ledger import TaskRecord, append_task_event, append_task_transition


def test_retry_records_red_and_green_after_rollback(tmp_path):
    ledger = tmp_path / "tasks.jsonl"
    task = TaskRecord(
        id="TSK-004-03",
        issue_id="001-004",
        description="Claim withdrawals",
        status="PENDING",
    )
    for status in ("PENDING", "RED", "GREEN"):
        task.status = status
        assert append_task_transition(task, ledger)
    task.status = "PENDING"
    append_task_event(task, ledger)
    prefix = ledger.read_bytes()
    for status in ("RED", "GREEN"):
        task.status = status
        assert append_task_transition(task, ledger)
        other = task.model_copy(update={"id": "TSK-004-04", "status": "PENDING"})
        append_task_transition(other, ledger)
        assert not append_task_transition(task, ledger)
    assert ledger.read_bytes().startswith(prefix)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [row["status"] for row in rows if row["id"] == task.id] == [
        "PENDING",
        "RED",
        "GREEN",
        "PENDING",
        "RED",
        "GREEN",
    ]
