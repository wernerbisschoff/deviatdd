from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from deviate.state.config import SessionState


def _approve_gate2(
    repo: Path,
    issue_id: str = "ISS-001",
    plan_path: str = "plan.md",
    tasks_path: str = "tasks.md",
) -> Path:
    """Seed ``plan.md`` / ``tasks.md`` and stamp the active issue on the session.

    This fixture used to also record ``hitl_gate_2_*`` SHA-256 hashes so the
    Gate 2 fail-closed check would pass. That hard gate has been removed —
    the system never blocks on human approval — so this helper now only
    seeds the canonical artifacts and the active issue. Tests that exercise
    the legacy approval-stamping path must NOT call this helper; it exists
    for tests that want the minimum session state needed to drive the micro
    TDD cycle (active issue + the files RED/GREEN/JUDGE will read).
    """
    plan = Path(repo) / plan_path
    tasks = Path(repo) / tasks_path
    plan.parent.mkdir(parents=True, exist_ok=True)
    tasks.parent.mkdir(parents=True, exist_ok=True)
    if not plan.exists():
        plan.write_text(
            "## Acceptance Contract\n\n"
            f"### AC-PLAN-001: {issue_id} smoke\n"
            "**Source Outline**: AO-001\n"
            "**Upstream Traceability**: ISS-001\n"
            "**Current-Code Evidence**: tests/test_conftest.py\n"
            "**Given** a seeded repo\n"
            "**When** the task runs\n"
            "**Then** the contract is honored\n",
            encoding="utf-8",
        )
    if not tasks.exists():
        tasks.write_text(
            "# Tasks\n\n- TSK-001-01 smoke (tdd)\n",
            encoding="utf-8",
        )
    dot_dir = Path(repo) / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    session = SessionState.load(dot_dir / "session.json")
    session.active_issue_id = issue_id
    session.save(dot_dir / "session.json")
    return repo


@pytest.fixture
def approve_gate2() -> Callable[..., Path]:
    """Factory fixture returning the helper so tests can approve ``tmp_path``
    and any ``issue_id`` after their own session setup. Usage::

        def test_foo(self, tmp_path, approve_gate2):
            SessionState(current_phase="IDLE").save(tmp_path / ".deviate/session.json")
            approve_gate2(tmp_path, issue_id="ISS-007")
    """
    return _approve_gate2


@pytest.fixture
def gate2_approved_repo(tmp_git_repo: Path) -> Path:
    """``tmp_git_repo`` with the canonical plan.md / tasks.md seeded and the
    active issue stamped on the session. The fixture name is retained for
    backward compatibility with the existing test suite, but it no longer
    stamps Gate 2 approval (the hard gate was removed).

    Opt in by listing this fixture alongside ``tmp_git_repo``.
    """
    return _approve_gate2(tmp_git_repo)


def _git_env() -> dict[str, str]:
    """Strip GIT_*/GH_* env vars so tests never inherit the parent repo's config.

    Every test that invokes `git` must pass `cwd=<tmp_git_repo>` AND `env=_git_env()`
    so the subprocess targets the temp repo without leaking parent config.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """Provide an isolated git repo for tests (git config user.name is Test Runner)."""
    subprocess.run(["git", "init"], cwd=tmp_path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "runner@test.local"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/repo.git"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    return tmp_path
