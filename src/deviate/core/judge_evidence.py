"""Mechanical TDD JUDGE evidence gate (path + exact substring)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def evaluate_judge_evidence(
    *,
    plan_contract: str,
    injected_diff: str,
    evidence: Sequence[Any],
    next_action: str | None = None,
    head_contents: Mapping[str, str] | None = None,
) -> str | None:
    """Return runner-authored feedback when citations fail; None on pass.

    Tokens come only from ``<authoritative_acceptance_contract source="plan.md">``.
    """
    raise NotImplementedError("TSK-020-02 evidence gate is not implemented")
