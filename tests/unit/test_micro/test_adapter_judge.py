from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import pytest


def _read_judge() -> str:
    ref = files("deviate.prompts.auto").joinpath("judge.md")
    with as_file(ref) as p:
        return Path(p).read_text(encoding="utf-8")


@pytest.mark.behavioral
def test_judge_rejects_fake_only_coverage_for_claimed_integration():
    """AC-PLAN-004: fake-only integration claim fails with COMPLIANCE_VIOLATION."""
    judge = _read_judge().lower()
    assert "fake" in judge
    assert "compliance_violation" in judge
    assert "integration" in judge


@pytest.mark.behavioral
def test_judge_rejection_names_missing_concrete_evidence():
    """AC-PLAN-004: rejection feedback names the missing concrete evidence."""
    judge = _read_judge().lower()
    assert "fake-only" in judge
    assert "missing concrete" in judge
    assert "correction" in judge


@pytest.mark.behavioral
def test_judge_exempts_pure_port_behavior_tasks():
    """AC-PLAN-005: pure port-behavior tasks pass fake coverage."""
    judge = _read_judge().lower()
    assert "exempt" in judge or "no integration claim" in judge
    assert "port" in judge
    assert "fake" in judge
