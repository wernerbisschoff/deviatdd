"""AC-PLAN-003: route checkpoint model through existing config (AO-007)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from deviate.state.config import resolve_phase_model


@pytest.mark.behavioral
def test_checkpoint_key_wins() -> None:
    models = {"checkpoint": "ckpt/model", "default": "def/model"}
    assert resolve_phase_model("checkpoint", models) == "ckpt/model"


@pytest.mark.behavioral
def test_checkpoint_falls_back_to_default() -> None:
    models = {"default": "def/model"}
    assert resolve_phase_model("checkpoint", models) == "def/model"


@pytest.mark.behavioral
def test_checkpoint_empty_models_sends_no_flag() -> None:
    assert resolve_phase_model("checkpoint", {}) is None


@pytest.mark.behavioral
def test_checkpoint_prompt_carries_template_provenance() -> None:
    from deviate.cli.micro import _load_checkpoint_template, _render_checkpoint_prompt

    template = _load_checkpoint_template()
    expected = Path("src/deviate/prompts/auto/checkpoint.md").read_text(
        encoding="utf-8"
    )
    assert template == expected
    task = {
        "id": "TSK-001-03",
        "issue_id": "008-001",
        "contract": "c",
        "commands": ["pytest"],
        "worktree": "/tmp/wt",
        "doc": "d",
        "capabilities": ["cap"],
    }
    prompt = _render_checkpoint_prompt(task)
    assert prompt.startswith(template)
    for field in (
        "task",
        "issue",
        "contract",
        "commands",
        "worktree",
        "doc",
        "capabilities",
    ):
        assert f"{field}:" in prompt


@pytest.mark.spy
def test_micro_passes_checkpoint_model_to_invocation(tmp_path: Path) -> None:
    from deviate.cli import micro as micro_mod

    task = {"id": "TSK-001-03", "issue_id": "008-001", "description": "ckpt"}
    ledger = tmp_path / "tasks.jsonl"
    fake_backend = MagicMock()
    with (
        patch.object(
            micro_mod, "resolve_phase_model", return_value="ckpt/model"
        ) as spy,
        patch.object(
            micro_mod,
            "resolve_model_for_phase",
            side_effect=AssertionError("must not route via wrapper"),
        ),
        patch.object(micro_mod, "AgentBackend", return_value=fake_backend),
    ):
        micro_mod._run_checkpoint_phase(task, ledger, Console(), agent="pi")
    spy.assert_called_once()
    args, _ = spy.call_args
    assert args[0] == "checkpoint"
    _, kwargs = fake_backend.invoke.call_args
    assert kwargs.get("model") == "ckpt/model"
