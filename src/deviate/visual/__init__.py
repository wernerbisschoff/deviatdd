"""Visual RED-phase demonstration module (TSK-001-01 / ISS-001-001).

This module provides the ``visual_init`` scaffold — a minimal demonstration of
the RED → GREEN → REFACTOR cycle for purely visual/layout logic.

``visual_init`` is intentionally trivial: it creates a workstation marker
directory and a human-readable acceptance receipt. Its purpose is to validate
the full RED-phase workflow, not to carry real implementation weight.
"""

from __future__ import annotations

from pathlib import Path


def visual_init(workdir: str | Path) -> None:
    """Idempotently initialise a workstation marker directory.

    Creates ``{workdir}/.deviate_visual/`` and writes a human-readable
    acceptance receipt (``RECEIPT.md``) into it that references the originating
    task identifier (TSK-001-01).
    """
    marker = Path(workdir) / ".deviate_visual"
    marker.mkdir(exist_ok=True)
    receipt = marker / "RECEIPT.md"
    receipt.write_text(
        "# Acceptance Receipt\n\n"
        "Task: TSK-001-01\n"
        "Issue: ISS-001-001\n"
        'Spec: "# Test issue" (minimal — visual demo of RED phase)\n',
        encoding="utf-8",
    )
