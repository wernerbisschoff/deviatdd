"""Soft 12-point handover checklist shared by Plan CLI print and overlays.

Meso Plan entry only. Never blocks: no prompt, no Gate 2, no hard fail.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

HANDOVER_CHECKLIST_BANNER = "Handover ready?"

HANDOVER_CHECKLIST_PREAMBLE = (
    "Soft 12-point handover checklist. Do not wait for answers; "
    "continue planning. Not a gate."
)

HANDOVER_CHECKLIST_SKIPPED_LOG = "HANDOVER_CHECKLIST skipped (non-TTY)"

HANDOVER_CHECKLIST_QUESTIONS: tuple[str, ...] = (
    "What problem does this solve?",
    "Who uses it?",
    "What is in / out of scope?",
    "Happy path?",
    "Alternate / error / timeout / recovery paths?",
    "Data and state involved?",
    "Interfaces and dependencies?",
    "Constraints and quality targets?",
    "How each requirement is verified?",
    "What changed from the original plan? (at first Plan: none yet)",
    "What remains unresolved?",
    "What must operators / users / maintainers know?",
)


def format_handover_checklist() -> str:
    """Return the shared checklist text used by CLI print and Plan overlays."""
    numbered = "\n".join(
        f"{i}. {question}" for i, question in enumerate(HANDOVER_CHECKLIST_QUESTIONS, 1)
    )
    return f"{HANDOVER_CHECKLIST_BANNER}\n{HANDOVER_CHECKLIST_PREAMBLE}\n{numbered}"


def should_emit_handover_checklist() -> bool:
    """True when stdout is a TTY (interactive Plan entry)."""
    stdout = getattr(sys, "stdout", None)
    if stdout is None:
        return False
    isatty = getattr(stdout, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def emit_plan_handover_checklist() -> None:
    """Print the checklist on a TTY; one-line log otherwise. Never blocks."""
    if should_emit_handover_checklist():
        print(format_handover_checklist(), flush=True)
        return
    logger.info(HANDOVER_CHECKLIST_SKIPPED_LOG)
