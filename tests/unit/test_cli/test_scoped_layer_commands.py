"""GH-258: scoped Verification stays in pre, layer lock, and runner.

A stamped task that names a file / ``-k`` subset must keep that selection
in the pre contract and agent layer lock. The named layer suite is only
the fallback for unscoped cards. Same-layer scoped commands must not
raise SPLIT_TASK_REQUIRED (#252 is a different mixed-layer path).
"""

from pathlib import Path

import pytest

from deviate.cli import micro
from tests.unit.test_cli.test_mise_verification import (
    _seed_pre_workspace,
    _write_mise,
)

_ADMISSION = (
    "mise integration tests/integration/test_crypto_withdrawal.py -k 'admission'"
)
_UNIT_SCOPED = "mise unit tests/unit/test_crypto_withdrawal.py -k 'admission'"


def _seed_scoped(tmp_path: Path, *, strategy: str, command: str) -> dict[str, str]:
    _write_mise(
        tmp_path,
        '[tasks.unit]\nrun = "pytest tests/unit"\n'
        '[tasks.integration]\nrun = "pytest tests/integration"\n'
        '[tasks.e2e]\nrun = "pytest tests/e2e"\n',
    )
    return _seed_pre_workspace(tmp_path, verification=command, test_strategy=strategy)


def _assert_same_scoped_selection(
    tmp_path: Path, task: dict[str, str], expected: str, strategy: str
) -> None:
    declared = micro._task_verification_command(tmp_path, task)
    rungs = micro._resolve_verification_rungs(tmp_path, task)
    layer = micro._layer_contract_fields(tmp_path, task)
    pre = micro._pre_layer_contract(tmp_path, task)
    red = micro._red_pre_kernel(task["id"], tmp_path)
    green = micro._green_pre_kernel(task["id"], tmp_path)

    assert declared == task["verification"]
    assert rungs == [expected]
    assert layer["test_strategy"] == strategy
    assert layer["test_command"] == expected
    assert micro._resolve_layer_command(tmp_path, task) == expected
    assert micro._resolve_verification_command(tmp_path, task) == expected
    assert pre == layer
    assert red["test_command"] == expected
    assert red["test_strategy"] == strategy
    assert green["test_command"] == expected
    assert green["test_strategy"] == strategy
    for phase in ("red", "green", "judge"):
        prompt = micro._build_auto_prompt(phase, task, tmp_path)
        assert f"Run only: {expected}" in prompt
        assert f"test_command: {expected}" in prompt
        assert f"<layer_lock>\nLayer: {strategy}\n" in prompt


@pytest.mark.behavioral
def test_gh258_integration_admission_keeps_scoped_command(tmp_path: Path):
    """Wallet-service reproduction: integration stamp + file + ``-k``."""
    task = _seed_scoped(tmp_path, strategy="integration", command=_ADMISSION)
    expected = f"mise run {_ADMISSION[5:]}"

    _assert_same_scoped_selection(tmp_path, task, expected, "integration")
    assert micro._layer_contract_fields(tmp_path, task)["test_command"] != (
        "mise integration"
    )


@pytest.mark.behavioral
def test_gh258_unit_admission_keeps_scoped_command(tmp_path: Path):
    """Same-layer unit scoped path must not expand to ``mise unit``."""
    task = _seed_scoped(tmp_path, strategy="unit", command=_UNIT_SCOPED)
    expected = f"mise run {_UNIT_SCOPED[5:]}"

    _assert_same_scoped_selection(tmp_path, task, expected, "unit")
    assert micro._layer_contract_fields(tmp_path, task)["test_command"] != "mise unit"


@pytest.mark.behavioral
@pytest.mark.parametrize("strategy", ["unit", "integration", "e2e"])
@pytest.mark.parametrize("prefix", ["mise", "mise run", "pytest"])
def test_scoped_layer_command_matches_pre_prompt_and_runner(
    tmp_path: Path, strategy: str, prefix: str
):
    command = (
        f"{prefix} {strategy}" if prefix.startswith("mise") else prefix
    ) + f" tests/{strategy}/test_contract.py -k 'selected or retained'"
    task = _seed_scoped(tmp_path, strategy=strategy, command=command)
    expected = (
        command
        if prefix == "mise run"
        else (
            f"mise run {command[5:]}" if prefix == "mise" else f"mise exec -- {command}"
        )
    )

    _assert_same_scoped_selection(tmp_path, task, expected, strategy)
