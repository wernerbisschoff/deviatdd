"""Adapter split rule prompts (AC-PLAN-001, AC-PLAN-002)."""

from pathlib import Path

import pytest

PLAN = Path("src/deviate/prompts/auto/plan.md")
TASKS = Path("src/deviate/prompts/auto/tasks.md")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


@pytest.mark.behavioral
def test_plan_names_adapter_split_keyed_on_external_sdk():
    text = _text(PLAN)
    assert "adapter" in text and "split" in text, (
        "plan.md lacks adapter split directive"
    )
    assert "external sdk" in text or "external provider" in text, (
        "plan.md split rule not keyed on external SDK naming"
    )


@pytest.mark.behavioral
def test_plan_requires_separate_adapter_criteria():
    text = _text(PLAN)
    assert "adapter" in text, "plan.md lacks adapter criteria rule"
    assert "separate" in text and "port" in text, (
        "plan.md must require separate adapter criteria apart from port behavior"
    )


@pytest.mark.behavioral
def test_tasks_requires_concrete_contract_rows():
    text = _text(TASKS)
    for row in ("signature", "auth", "request identity", "response lookup"):
        assert row in text, f"tasks.md lacks contract row: {row}"


@pytest.mark.behavioral
def test_tasks_splits_adapter_transport_from_port_behavior():
    text = _text(TASKS)
    assert "adapter transport" in text, (
        "tasks.md lacks adapter transport split directive"
    )
    assert "port behavior" in text, "tasks.md split rule must name port behavior"
