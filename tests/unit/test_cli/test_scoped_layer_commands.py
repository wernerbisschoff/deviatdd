from pathlib import Path

import pytest

from deviate.cli import micro
from tests.unit.test_cli.test_mise_verification import (
    _seed_pre_workspace,
    _write_mise,
)


@pytest.mark.behavioral
@pytest.mark.parametrize("strategy", ["unit", "integration", "e2e"])
@pytest.mark.parametrize("prefix", ["mise", "mise run", "pytest"])
def test_scoped_layer_command_matches_pre_prompt_and_runner(
    tmp_path: Path, strategy: str, prefix: str
):
    _write_mise(
        tmp_path,
        '[tasks.unit]\nrun = "pytest tests/unit"\n'
        '[tasks.integration]\nrun = "pytest tests/integration"\n'
        '[tasks.e2e]\nrun = "pytest tests/e2e"\n',
    )
    command = (
        f"{prefix} {strategy}" if prefix.startswith("mise") else prefix
    ) + f" tests/{strategy}/test_contract.py -k 'selected or retained'"
    task = _seed_pre_workspace(tmp_path, verification=command, test_strategy=strategy)
    expected = command if prefix == "mise run" else f"mise exec -- {command}"

    contract = micro._red_pre_kernel(task["id"], tmp_path)

    assert contract["test_strategy"] == strategy
    assert contract["test_command"] == expected
    assert micro._resolve_verification_rungs(tmp_path, task) == [expected]
    for phase in ("red", "green"):
        prompt = micro._build_auto_prompt(phase, task, tmp_path)
        assert f"Run only: {expected}" in prompt
        assert f"test_command: {expected}" in prompt
