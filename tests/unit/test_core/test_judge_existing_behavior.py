from pathlib import Path

import pytest

from deviate.core.commands import install_command
from deviate.prompts.assembly import load_template


@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_judge_credits_existing_task_behavior(mode: str, tmp_path: Path) -> None:
    if mode == "auto":
        prompt = load_template("judge")
    else:
        install_command("deviate-judge", tmp_path)
        prompt = (tmp_path / "deviate-judge.md").read_text(encoding="utf-8")

    for requirement in (
        "Read the current task-scoped tests and implementation, including unchanged code.",
        "Do not require new code or duplicate tests for behavior already satisfied.",
        "A renamed test earns coverage only when its assertions exercise the assigned behavior.",
    ):
        assert requirement in prompt
    assert "do not analyze pre-existing code" not in prompt
    assert "Confirm the test is present in the diff" not in prompt
    assert "or HEAD on the already-exists" not in prompt
