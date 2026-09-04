from __future__ import annotations

import pytest

from deviate.cli.micro import JudgeCycleTransition, _judge_cycle_transition


@pytest.mark.parametrize(
    ("suite_red", "pending_action", "expected"),
    [
        (False, "", JudgeCycleTransition.FINISH),
        (False, "revert_green", JudgeCycleTransition.TRAIN_GREEN),
        (False, "revert_red", JudgeCycleTransition.TRAIN_GREEN),
        (True, "continue_refactor", JudgeCycleTransition.TRAIN_GREEN),
        (True, "skip_refactor", JudgeCycleTransition.TRAIN_GREEN),
    ],
)
def test_judge_cycle_transition(suite_red, pending_action, expected):
    assert (
        _judge_cycle_transition(
            suite_red=suite_red,
            pending_action=pending_action,
        )
        == expected
    )
