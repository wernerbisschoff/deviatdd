"""Import-target lock for TSK-001-03 (AC-PLAN-006, AO-005, AO-007).

Callers must import directly from ``deviate.cli.micro`` submodules with
zero bare ``from deviate.cli.micro import`` references outside the shim,
and no ``src/deviate/cli/micro/*.py`` submodule may import the shim.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MICRO_PKG_DIR = REPO_ROOT / "src" / "deviate" / "cli" / "micro"
SHIM_PATH = REPO_ROOT / "src" / "deviate" / "cli" / "micro.py"

BARE_SHIM_RE = re.compile(r"^\s*from\s+deviate\.cli\.micro\s+import\s+", re.MULTILINE)

CALLER_FILES = [
    REPO_ROOT / "src" / "deviate" / "cli" / "__init__.py",
    REPO_ROOT / "src" / "deviate" / "core" / "converge.py",
    REPO_ROOT / "src" / "deviate" / "cli" / "meso.py",
]

PUBLIC_NAMES = [
    "_run_all",
    "_find_all_pending_tasks",
    "existing_verification_suites",
    "micro_app",
    "red_app",
    "green_app",
    "judge_app",
    "refactor_app",
    "execute_app",
    "e2e_app",
    "hotfix_app",
]


def _bare_shim_hits(path: Path) -> list[str]:
    return BARE_SHIM_RE.findall(path.read_text(encoding="utf-8"))


@pytest.mark.behavioral
def test_callers_hold_zero_bare_shim_imports():
    hits = {str(p): _bare_shim_hits(p) for p in CALLER_FILES if p.exists()}
    offenders = {k: len(v) for k, v in hits.items() if v}
    assert not offenders, f"bare shim imports remain: {offenders}"


@pytest.mark.behavioral
def test_no_micro_submodule_imports_the_shim():
    offenders = {}
    for path in sorted(MICRO_PKG_DIR.glob("*.py")):
        hits = _bare_shim_hits(path)
        if hits:
            offenders[path.name] = len(hits)
    assert not offenders, f"micro submodules import the shim: {offenders}"


@pytest.mark.behavioral
def test_public_names_resolve_from_submodules_via_importlib():
    pkg = importlib.import_module("deviate.cli.micro")
    submodules = [
        importlib.import_module(f"deviate.cli.micro.{sub}")
        for sub in ("surface", "pending", "suites")
    ]
    unresolved = []
    for name in PUBLIC_NAMES:
        obj = getattr(pkg, name, None)
        if obj is None:
            unresolved.append(f"{name}: missing on deviate.cli.micro")
            continue
        module = getattr(obj, "__module__", "")
        if module.startswith("deviate.cli.micro."):
            continue
        # Instances (e.g. Typer apps) carry their type's __module__;
        # they are served from a submodule when identical to its attribute.
        if not any(getattr(sub, name, None) is obj for sub in submodules):
            unresolved.append(f"{name}: resolves from {module!r}, not a submodule")
    assert not unresolved, f"names not served from submodules: {unresolved}"


@pytest.mark.behavioral
def test_converge_resolves_pending_tasks_without_shim_module():
    text = (REPO_ROOT / "src" / "deviate" / "core" / "converge.py").read_text(
        encoding="utf-8"
    )
    assert not BARE_SHIM_RE.search(text), "converge.py keeps a bare shim import"
    assert re.search(
        r"from\s+deviate\.cli\.micro\.\w+\s+import\s+[^\n]*_find_all_pending_tasks",
        text,
    ), "converge.py does not resolve _find_all_pending_tasks from a submodule"


@pytest.mark.behavioral
def test_meso_resolves_verification_suites_without_shim_module():
    text = (REPO_ROOT / "src" / "deviate" / "cli" / "meso.py").read_text(
        encoding="utf-8"
    )
    assert not BARE_SHIM_RE.search(text), "meso.py keeps a bare shim import"
    assert re.search(
        r"from\s+deviate\.cli\.micro\.\w+\s+import\s+[^\n]*existing_verification_suites",
        text,
    ), "meso.py does not resolve existing_verification_suites from a submodule"
