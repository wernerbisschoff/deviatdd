from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import _pre_layer_contract
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()

TASK_ID = "TSK-043-01"
ISSUE_ID = "ISS-043"
SOURCE_FILE = "specs/adhoc/issues/043-red-split-test-contract-fails-fast.md"


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        ledger_path.open("a", encoding="utf-8").write(r.model_dump_json() + "\n")


def _setup_root(tmp_path: Path, task: TaskRecord, card: str) -> dict:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    SessionState(current_phase="IDLE").save(dot_dir / "session.json")
    ledger_path = tmp_path / "specs" / "043-red-split" / "tasks.jsonl"
    _write_ledger(ledger_path, task)
    issue_dir = tmp_path / "specs" / "adhoc" / "043-red-split-test-contract-fails-fast"
    issue_dir.mkdir(parents=True)
    (issue_dir / "tasks.md").write_text(card, encoding="utf-8")
    (tmp_path / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": ISSUE_ID, "source_file": SOURCE_FILE}) + "\n",
        encoding="utf-8",
    )
    return task.model_dump(mode="json")


def _card(body: str) -> str:
    return f"# Tasks\n\n- {TASK_ID}: split contract task\n{body}"


def _mixed_task(**over: object) -> TaskRecord:
    base: dict = {"id": TASK_ID, "issue_id": ISSUE_ID, "description": "split"}
    base.update(over)
    return TaskRecord(**base)  # type: ignore[arg-type]


@pytest.mark.behavioral
def test_mixed_unit_plus_integration_stops_red_pre(tmp_path: Path):
    """AC-PLAN-001: row unit stamp loses to card files in two layers; pre exits non-zero."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        with pytest.raises(typer.Exit) as exc:
            _pre_layer_contract(tmp_path, row)
        assert exc.value.exit_code != 0


@pytest.mark.behavioral
def test_split_error_names_layers_and_split_action(tmp_path: Path, capsys):
    """AC-PLAN-002: the split-task error names each layer plus the planner fix."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        with pytest.raises(typer.Exit):
            _pre_layer_contract(tmp_path, row)
        out = capsys.readouterr().out.lower()
        assert "unit" in out and "integration" in out
        assert "split" in out and "one task per layer" in out


@pytest.mark.behavioral
def test_red_pre_cli_exits_nonzero_without_spawning_agents(tmp_path: Path):
    """AC-PLAN-001: `red pre` on a mixed contract stops before any agent spawn."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        _setup_root(tmp_path, task, card)
        with patch("deviate.cli.micro._invoke_agent") as spawn:
            result = runner.invoke(cli, ["red", "pre", "--task", TASK_ID])
        assert result.exit_code != 0
        spawn.assert_not_called()


@pytest.mark.behavioral
def test_single_layer_contract_passes_untouched(tmp_path: Path):
    """AC-PLAN-003: a unit-only contract gets a layer contract with no split error."""
    task = _mixed_task(test_strategy="unit")
    card = _card("  - **Test Strategy**: unit\n  - Files: tests/unit/test_a.py\n")
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        contract = _pre_layer_contract(tmp_path, row)
        assert contract["test_strategy"] == "unit"


@pytest.mark.behavioral
def test_prose_only_mentions_keep_fallback(tmp_path: Path):
    """AC-PLAN-004: prose-only layer words with single-layer targets do not fire."""
    task = _mixed_task()
    card = _card(
        "  - Notes: the unit prose mentions integration in passing\n"
        "  - Files: tests/unit/test_a.py\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        contract = _pre_layer_contract(tmp_path, row)
        assert isinstance(contract, dict)
