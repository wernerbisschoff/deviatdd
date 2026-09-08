"""RED prompt orders the named precondition signal for missing infrastructure.

Covers AC-PLAN-004 (named signal plus non-error RED status) and AC-PLAN-005
(exactly one outcome; the signal always names the setup command).
"""

from __future__ import annotations

from pathlib import Path

import pytest

RED_MD = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "deviate"
    / "prompts"
    / "auto"
    / "red.md"
)


def _prompt() -> str:
    return RED_MD.read_text(encoding="utf-8")


@pytest.mark.behavioral
def test_red_prompt_orders_named_signal_with_non_error_status():
    text = _prompt()
    assert "PRECONDITIONS_NOT_READY" in text
    assert '"BLOCKED"' in text or "`BLOCKED`" in text


@pytest.mark.behavioral
def test_red_prompt_signal_always_names_setup_command():
    text = _prompt().lower()
    assert "always names the setup command" in text


@pytest.mark.behavioral
def test_red_prompt_does_not_order_error_for_unavailable_infrastructure():
    for line in _prompt().splitlines():
        lowered = line.lower()
        if "unavailable" in lowered and (
            "infrastructure" in lowered or "service" in lowered
        ):
            assert 'emit `status: "ERROR"`' not in line, (
                f"line still orders ERROR: {line}"
            )
            assert "PRECONDITIONS_NOT_READY" in line, f"line lacks named signal: {line}"


@pytest.mark.behavioral
def test_red_prompt_keeps_error_for_non_infrastructure_failures():
    text = _prompt()
    assert 'status: "ERROR"' in text
    assert "tool failures" in text
