"""Acceptance tests for TSK-001-01 (visual RED-phase demonstration).

Task:    TSK-001-01
Issue:   ISS-001-001 (CLI Initialization & Governance Provisioning)
Spec:    "# Test issue" (minimal — visual demo of RED phase)

These tests intentionally target a not-yet-implemented module to satisfy the
RED-phase invariant: the suite MUST fail before implementation exists. The
GREEN phase will introduce `src/deviate/visual/__init__.py::visual_init()` and
its supporting scaffold logic.
"""

from __future__ import annotations

from pathlib import Path


def test_visual_init_creates_workstation_marker(tmp_path: Path) -> None:
    """Given a clean directory, `visual_init` must create the workstation marker."""
    from deviate.visual import visual_init

    workdir = tmp_path
    visual_init(workdir)

    marker = workdir / ".deviate_visual"
    assert marker.exists(), (
        f"Expected {marker} to exist after visual_init on a clean directory"
    )
    assert marker.is_dir(), f"Expected {marker} to be a directory"


def test_visual_init_is_idempotent(tmp_path: Path) -> None:
    """Given an already-initialized directory, a second `visual_init` must not raise."""
    from deviate.visual import visual_init

    workdir = tmp_path
    visual_init(workdir)
    visual_init(workdir)

    marker = workdir / ".deviate_visual"
    assert marker.exists(), "Marker must persist across idempotent invocations"


def test_visual_init_writes_acceptance_receipt(tmp_path: Path) -> None:
    """Given any workdir, `visual_init` must leave a human-readable acceptance receipt."""
    from deviate.visual import visual_init

    workdir = tmp_path
    visual_init(workdir)

    receipt = workdir / ".deviate_visual" / "RECEIPT.md"
    assert receipt.exists(), f"Expected acceptance receipt at {receipt}"
    contents = receipt.read_text(encoding="utf-8")
    assert "TSK-001-01" in contents, "Receipt must reference the originating task id"