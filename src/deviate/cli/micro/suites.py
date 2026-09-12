"""Micro phase verification suites helpers (split of the god-file package)."""

from __future__ import annotations

from pathlib import Path


def existing_verification_suites(root: Path) -> list[str]:
    """Product-named rungs that exist (``unit``, ``integration``, ``e2e``)."""
    from deviate.cli.micro.surface import _suite_rung_command

    found: list[str] = []
    if _suite_rung_command(root, "unit"):
        found.append("unit")
    if _suite_rung_command(root, "integ"):
        found.append("integration")
    if _suite_rung_command(root, "e2e"):
        found.append("e2e")
    return found
