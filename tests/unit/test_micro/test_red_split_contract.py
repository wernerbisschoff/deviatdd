from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from rich.console import Console

from deviate.cli import cli
from deviate.cli.micro import (
    KernelError,
    PhaseFailedError,
    _pre_layer_contract,
    _red_pre_kernel,
    _run_red_phase,
)
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


def _write_layer_mise(tmp_path: Path) -> None:
    (tmp_path / "mise.toml").write_text(
        '[tasks.unit]\nrun = "pytest tests/unit"\n'
        '[tasks.integration]\nrun = "pytest tests/integration"\n',
        encoding="utf-8",
    )


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
def test_red_pre_preserves_split_token_not_task_not_found(tmp_path: Path):
    """GH-252: manual red pre keeps SPLIT_TASK_REQUIRED instead of TASK_NOT_FOUND."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        _setup_root(tmp_path, task, card)
        result = runner.invoke(cli, ["red", "pre", "--task", TASK_ID])
    assert result.exit_code != 0
    assert "SPLIT_TASK_REQUIRED" in result.output
    assert "TASK_NOT_FOUND" not in result.output


@pytest.mark.behavioral
def test_red_pre_kernel_preserves_split_token(tmp_path: Path):
    """GH-252: `_red_pre_kernel` raises SPLIT_TASK_REQUIRED, not TASK_NOT_FOUND."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        _setup_root(tmp_path, task, card)
        with pytest.raises(KernelError) as exc:
            _red_pre_kernel(TASK_ID, tmp_path)
    assert exc.value.token == "SPLIT_TASK_REQUIRED"
    assert "integration" in exc.value.detail
    assert "unit" in exc.value.detail


@pytest.mark.behavioral
def test_mixed_contract_run_red_phase_does_not_spawn_unit_fallback(tmp_path: Path):
    """GH-252: auto RED hard-stops on SPLIT_TASK_REQUIRED and does not spawn."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: unit\n"
        "  - Files: tests/unit/test_a.py tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        session_path = tmp_path / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        ledger_path = tmp_path / "specs" / "043-red-split" / "tasks.jsonl"
        with (
            patch("deviate.cli.micro._invoke_agent") as spawn,
            patch("deviate.cli.micro._run_pytest") as run_pytest,
            patch("deviate.cli.micro._build_auto_prompt") as build_prompt,
        ):
            with pytest.raises(PhaseFailedError) as exc:
                _run_red_phase(
                    row, ledger_path, session, session_path, Console(quiet=True)
                )
        spawn.assert_not_called()
        run_pytest.assert_not_called()
        build_prompt.assert_not_called()
    assert "SPLIT_TASK_REQUIRED" in str(exc.value)
    assert "TASK_NOT_FOUND" not in str(exc.value)


@pytest.mark.behavioral
def test_refresh_layer_restamps_stale_unit_from_corrected_card(tmp_path: Path):
    """GH-252: operator card correction can restamp stale ledger layer metadata."""
    from deviate.cli.micro import _find_task_record, _refresh_task_layer

    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: integration\n  - Files: tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        _write_layer_mise(tmp_path)
        with pytest.raises(KernelError) as before:
            _red_pre_kernel(TASK_ID, tmp_path)
        assert before.value.token == "SPLIT_TASK_REQUIRED"
        result = _refresh_task_layer(tmp_path, TASK_ID)
        assert result["test_strategy"] == "integration"
        assert result["previous_test_strategy"] == "unit"
        assert result["refreshed"] is True
        contract = _red_pre_kernel(TASK_ID, tmp_path)
        assert contract["test_strategy"] == "integration"
        latest = _find_task_record(tmp_path, TASK_ID)
        assert latest is not None
        assert latest[0].get("test_strategy") == "integration"
        assert row.get("test_strategy") == "unit"


@pytest.mark.behavioral
def test_refresh_layer_cli_restamps_and_exits_zero(tmp_path: Path):
    """GH-252: `deviate red refresh-layer` is the supported restamp surface."""
    task = _mixed_task(test_strategy="unit")
    card = _card(
        "  - **Test Strategy**: integration\n  - Files: tests/integration/test_b.py\n"
    )
    with chdir(tmp_path):
        _setup_root(tmp_path, task, card)
        _write_layer_mise(tmp_path)
        result = runner.invoke(cli, ["red", "refresh-layer", "--task", TASK_ID])
    assert result.exit_code == 0, result.output
    assert "integration" in result.output
    assert "TASK_NOT_FOUND" not in result.output


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


@pytest.mark.behavioral
def test_e2e_mixed_with_unit_fires_split_error(tmp_path: Path):
    """AC-PLAN-004: e2e file plus unit file stops with the split-task error."""
    task = _mixed_task()
    card = _card("  - Files: tests/unit/test_a.py tests/e2e/test_x.py\n")
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        with pytest.raises(typer.Exit) as exc:
            _pre_layer_contract(tmp_path, row)
        assert exc.value.exit_code != 0


@pytest.mark.behavioral
def test_execution_mode_e2e_plus_unit_path_fires(tmp_path: Path, capsys):
    """AC-PLAN-004: execution_mode E2E stamp plus a unit path fires split error."""
    task = _mixed_task(execution_mode="E2E")
    card = _card("  - Files: tests/unit/test_a.py\n")
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        with pytest.raises(typer.Exit) as exc:
            _pre_layer_contract(tmp_path, row)
        assert exc.value.exit_code != 0
        out = capsys.readouterr().out.lower()
        assert "split" in out and "e2e" in out and "unit" in out


@pytest.mark.behavioral
def test_keyword_only_card_keeps_fallback(tmp_path: Path):
    """AC-PLAN-004: ambiguous keywords with no concrete paths keep fallback."""
    from deviate.cli.micro import _layer_contract_fields

    task = _mixed_task()
    card = _card("  - Notes: unit and integration keywords without paths\n")
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        contract = _pre_layer_contract(tmp_path, row)
        assert contract == _layer_contract_fields(tmp_path, row)


@pytest.mark.behavioral
def test_single_concrete_path_plus_keyword_noise_passes(tmp_path: Path):
    """AC-PLAN-003 edge: one concrete path plus keyword noise stays single-layer."""
    task = _mixed_task()
    card = _card(
        "  - Files: tests/unit/test_a.py\n"
        "  - Notes: integration e2e keyword noise in prose\n"
    )
    with chdir(tmp_path):
        row = _setup_root(tmp_path, task, card)
        contract = _pre_layer_contract(tmp_path, row)
        assert contract["test_strategy"] == "unit"
