"""GH-248: integration layer stamp stays locked across RED/GREEN/JUDGE.

Wallet-service TSK-005-08 named tests/integration/test_crypto_withdrawal.py
and required HTTP/DB/scheduler coverage. JUDGE alternately rejected unit
artifacts then later cycles produced them again, until GH-230's
JUDGE_REQUIREMENT_CONTRADICTION halt fired. The runner must stamp the
task layer into prompts and carry-forward so agents cannot migrate the
suite. HITL from GH-230 remains the backstop, not the first defense.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deviate.cli import micro
from tests.unit.test_cli.test_mise_verification import _make_task, _write_mise

pytestmark = pytest.mark.behavioral

_UNIT_JUDGE_FEEDBACK = """\
The next RED attempt must:
- Requirement: AC-PLAN-001 requires FastAPI admission coverage.
- Evidence: The rejected tests lived under tests/unit and mocked the app.
- Correction: Author unit tests in tests/unit/test_crypto_withdrawal.py.
- Verification: Run mise unit; expect an assertion failure, not setup failure.
- Boundary: Change tests only. Do not edit production code.
"""

_INTEG_TASK_DESCRIPTION = (
    "HTTP admission, database reservations, balances, scheduler dispatch, "
    "and all 16 status combinations in "
    "tests/integration/test_crypto_withdrawal.py"
)


def _integration_task(tmp_path: Path) -> dict[str, str]:
    _write_mise(
        tmp_path,
        '[tasks.unit]\nrun = "pytest -m unit"\n'
        '[tasks.integration]\nrun = "pytest -m integration"\n',
    )
    return _make_task(
        task_id="TSK-005-08",
        issue_id="001-005",
        description=_INTEG_TASK_DESCRIPTION,
        test_strategy="integration",
        verification="mise integration",
    )


def _assert_integration_lock(prompt: str) -> None:
    assert "Layer: integration" in prompt
    assert "Write tests only in: tests/integration" in prompt
    assert "Run only: mise integration" in prompt
    assert "<layer_lock>" in prompt
    assert "test_strategy: integration" in prompt
    assert "test_write_dir: tests/integration" in prompt
    assert "test_command: mise integration" in prompt
    assert "cannot reclassify" in prompt.lower()


class TestLayerStamp:
    def test_integration_task_stamps_write_dir_and_command(
        self, tmp_path: Path
    ) -> None:
        task = _integration_task(tmp_path)
        layer = micro._layer_contract_fields(tmp_path, task)
        assert layer["test_strategy"] == "integration"
        assert layer["test_write_dir"] == "tests/integration"
        assert layer["test_command"] == "mise integration"
        lock = micro._layer_lock_block(layer)
        assert "test_strategy: integration" in lock
        assert "test_write_dir: tests/integration" in lock
        assert "test_command: mise integration" in lock


class TestPromptInjection:
    def test_red_green_judge_prompts_inject_integration_layer(
        self, tmp_path: Path
    ) -> None:
        task = _integration_task(tmp_path)
        for phase in ("red", "green", "judge"):
            prompt = micro._build_auto_prompt(phase, task, tmp_path)
            _assert_integration_lock(prompt)
            assert "```bash\nmise unit\n```" not in prompt


class TestFeedbackCarryForward:
    def test_unit_judge_feedback_cannot_move_an_integration_task(
        self, tmp_path: Path
    ) -> None:
        task = _integration_task(tmp_path)
        combined = micro._task_train_feedback(tmp_path, task, _UNIT_JUDGE_FEEDBACK)
        assert "tests/unit/test_crypto_withdrawal.py" in combined
        assert "mise unit" in combined
        for phase in ("red", "green", "judge"):
            prompt = micro._build_auto_prompt(
                phase, task, tmp_path, train_feedback=_UNIT_JUDGE_FEEDBACK
            )
            _assert_integration_lock(prompt)
            assert "tests/unit/test_crypto_withdrawal.py" in prompt
            lock_at = prompt.index("<layer_lock>")
            feedback_at = prompt.index("tests/unit/test_crypto_withdrawal.py")
            assert lock_at < feedback_at
            assert "Layer: unit" not in prompt
            assert "Write tests only in: tests/unit" not in prompt
            assert "Run only: mise unit" not in prompt
