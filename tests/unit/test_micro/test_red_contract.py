"""AC-PLAN-003/004: RED pre kernel manual/auto contract parity (RED)."""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

pytestmark = pytest.mark.behavioral

runner = CliRunner()

SHARED_KEYS = [
    "task_id",
    "test_strategy",
    "test_write_dir",
    "test_command",
    "lint_command",
]


def _make_task_record(task_id: str = "TSK-001-02") -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id="ISS-001-007",
        description="RED pre kernel parity",
        status="PENDING",
        execution_mode="TDD",
    )


def _seed(tmp_path: Path, task_id: str = "TSK-001-02") -> None:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    SessionState(current_phase="IDLE").save(dot_dir / "session.json")
    ledger = tmp_path / "specs" / "001-007" / "tasks.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        _make_task_record(task_id).model_dump_json() + "\n", encoding="utf-8"
    )


def _manual_contract(tmp_path: Path, task_id: str = "TSK-001-02") -> dict:
    with chdir(tmp_path):
        result = runner.invoke(cli, ["red", "pre", "--task", task_id])
    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    return json.loads(result.output)


@pytest.mark.behavioral
def test_manual_red_pre_holds_five_key_contract_additive(tmp_path: Path):
    """AC-PLAN-003: stdout holds the five-key contract plus doctor fields."""
    _seed(tmp_path)
    data = _manual_contract(tmp_path)
    for key in SHARED_KEYS:
        assert key in data, f"missing contract key: {key}"
    assert "spec_dir" in data
    assert "task_entry" in data


@pytest.mark.behavioral
def test_red_pre_kernel_builds_identical_shared_keys(tmp_path: Path):
    """AC-PLAN-004: in-process kernel builds the same shared keys as manual."""
    from deviate.cli.micro import _red_pre_kernel

    _seed(tmp_path)
    manual = _manual_contract(tmp_path)
    with chdir(tmp_path):
        kernel_contract = _red_pre_kernel(task_id="TSK-001-02", root=Path.cwd())
    for key in SHARED_KEYS:
        assert kernel_contract[key] == manual[key], f"drift on shared key: {key}"


@pytest.mark.behavioral
def test_unresolvable_pending_task_raises_kernel_error(tmp_path: Path):
    """Edge: pending task that fails to resolve raises KernelError."""
    from deviate.cli.micro import KernelError, _red_pre_kernel

    _seed(tmp_path)
    with chdir(tmp_path):
        with pytest.raises(KernelError):
            _red_pre_kernel(task_id="TSK-999-99", root=Path.cwd())


@pytest.mark.behavioral
def test_doctored_contract_json_rejected(tmp_path: Path):
    """Edge: doctored contract JSON is rejected input."""
    from deviate.cli.micro import KernelError, _red_pre_kernel

    _seed(tmp_path)
    with chdir(tmp_path):
        with pytest.raises(KernelError):
            _red_pre_kernel(
                task_id="TSK-001-02",
                root=Path.cwd(),
                contract_override={"task_id": "TSK-001-02", "injected": True},
            )
