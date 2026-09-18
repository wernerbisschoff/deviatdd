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
    """Provide an isolated git repo (identity + origin seeded via file write).

    Runs only two git subprocesses (init + empty commit). Identity and the
    ``origin`` remote are appended directly to ``.git/config`` instead of
    separate ``git config`` / ``git remote add`` calls.
    """
    subprocess.run(
        ["git", "init", "--initial-branch", "main"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    with open(tmp_path / ".git" / "config", "a", encoding="utf-8") as f:
        f.write(
            "[user]\n\temail = runner@test.local\n\tname = Test Runner\n"
            '[remote "origin"]\n'
            "\turl = https://example.com/repo.git\n"
            "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
        )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    return tmp_path


# Substring match on test node IDs that run full scripted cycles or real
# subprocesses with sleeps (4-10s each). Run them via `mise run test-slow`.
_SLOW_SUBSTRINGS = (
    "test_third_green_runs_without_escalate_or_pre_red_ambiguous",
    "test_third_revert_green_escalates_to_red",
    "test_two_revert_green_sets_loop_and_max_streak",
    "test_two_revert_red_sets_loop_and_emits_loop_detected",
    "test_test_integrity_after_green_pass_coerces_to_red",
    "test_green_test_failure_compliance_pass_continue_refactor_retrains",
    "test_no_failing_test_revert_red_invokes_red_not_green",
    "test_micro_green_train_feedback_still_retries_then_exhausts",
    "test_json_default_omits_agent_output_events",
    "test_run_all_with_live_display_agent_output",
    "test_micro_green_mechanical_failure_routes_to_judge_not_failed",
    "test_agent_output_lines_in_fifo_order",
    "test_micro_green_test_defect_failure_routes_to_judge",
    "test_additive_verification_changelog_aba_still_trains",
    "test_additive_coverage_evidence_aba_still_trains",
    "test_micro_judge_rejection_triggers_green_retry",
    "test_judge_repairs_survive_the_real_cycle",
    "test_compatible_successive_rejects_still_train",
    "test_judge_feedback_preserved_across_rejection_rounds",
    "test_run_safe_command_kills_sigterm_ignoring_descendants",
    "test_second_revert_red_after_reset_does_not_raise",
    "test_green_test_tampering_retains_red",
    "test_micro_all_processes_all_pending",
    "test_judge_rejection_advances_red_boundary_across_cycles",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if any(s in item.nodeid for s in _SLOW_SUBSTRINGS):
            item.add_marker(pytest.mark.slow)
