from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import pytest


def _read_red() -> str:
    ref = files("deviate.prompts.auto").joinpath("red.md")
    with as_file(ref) as p:
        return Path(p).read_text(encoding="utf-8")


@pytest.mark.behavioral
def test_red_requires_offline_signature_inspection():
    """AC-PLAN-006: adapter tasks inspect the installed signature offline."""
    red = _read_red().lower()
    assert "offline" in red
    assert "inspect" in red
    assert "installed" in red
    assert "no network" in red or "without network" in red or "no live" in red


@pytest.mark.behavioral
def test_red_pins_declared_version_on_missing_dependency():
    """AC-PLAN-006 edge: missing dependency pins the declared version."""
    red = _read_red().lower()
    assert "pin" in red
    assert "version" in red
    assert "missing" in red or "absent" in red


@pytest.mark.behavioral
def test_red_requires_import_boundary_and_deferred_construction():
    """AC-PLAN-003: adapter tests cover import safety plus deferred construction."""
    red = _read_red().lower()
    assert "import" in red
    assert "deferred" in red


@pytest.mark.behavioral
def test_red_requires_auth_negative_tests_with_dependency_evidence():
    """AC-PLAN-003: missing auth fails with dependency evidence, no live calls."""
    red = _read_red().lower()
    assert "auth" in red
    assert "evidence" in red or "dependency" in red
    assert "no live" in red or "without live" in red or "no network" in red
