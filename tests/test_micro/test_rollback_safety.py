"""Tests for F3 (rollback safety) — explicit-boundary + per-attempt recovery refs.

Reproduces the parent-SIGTERM-during-rollback failure mode observed in
feat/001-wizards-mvp-booking/003-.../003-secure-desktop-availability-calendar
(2026-07-24): when the runner's ``_execute_rollback`` was interrupted
between ``git reset --hard`` and ``git clean -fd``, the agent's commit
was stranded in the worktree without being committed anywhere recoverable.

Two regressions are pinned here, both surfaced by the locked-rollback-safety
contract:

1. **Explicit ``boundary_sha`` contract.** ``_execute_rollback`` requires the
   boundary to be threaded by the caller — no fallback to
   ``SessionState.red_commit_sha`` or ``HEAD~1``. Missing / whitespace
   ``boundary_sha`` raises ``PhaseFailedError`` BEFORE any ``git reset`` /
   ``git clean`` so the runner never wipes work without an explicit anchor.

2. **Per-attempt recovery refs.** Each discarded commit lands on
   ``tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>``. A single
   global ref would let a second rollback silently overwrite an earlier
   attempt that the operator may still need to inspect.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import _git_env


def _current_head(repo: Path) -> str:
    """Return the SHA of HEAD on the given repo."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_commit(repo: Path, msg: str) -> str:
    """Create an empty commit and return its SHA."""
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", msg],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _current_head(repo)


def _ref_exists(repo: Path, ref: str) -> bool:
    """Return True iff ``git rev-parse`` can resolve ``ref``."""
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo,
            env=_git_env(),
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _ref_sha(repo: Path, ref: str) -> str:
    """Return the SHA of the named ref (assumes it exists)."""
    return subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _seed_session_red_sha(repo: Path, red_sha: str) -> None:
    """Write ``.deviate/session.json`` with the given RED boundary.

    Production places ``.deviate/`` under gitignore so ``git clean -fd``
    (without ``-x``) preserves the audit trail. Tests must mirror that
    or the cleanup assertions diverge from production behaviour.
    """
    deviate_dir = repo / ".deviate"
    deviate_dir.mkdir(parents=True, exist_ok=True)
    session_payload = {
        "current_phase": "JUDGE",
        "active_issue_id": None,
        "last_command": "",
        "train_feedback": "",
        "judge_rejected": False,
        "red_commit_sha": red_sha,
        "timestamp": "2026-07-13T00:00:00Z",
    }
    (deviate_dir / "session.json").write_text(
        json.dumps(session_payload), encoding="utf-8"
    )


class TestPreserveAgentWork:
    """``_preserve_agent_work`` snapshots agent's HEAD on a per-attempt ref.

    Each call writes to the caller-supplied ``recovery_branch``; the helper
    itself does not invent a global name. Per-attempt refs keep distinct
    rollbacks from overwriting each other.
    """

    def test_preserves_agent_work_on_per_task_ref(self, tmp_git_repo: Path) -> None:
        """Agent's commit survives by being copied to the threaded ref name."""
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent wrote code")

        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="COMPLIANCE_VIOLATION: hardcoded forward_window_weeks",
            recovery_branch="tmp/deviate-agent-work/TSK-001-01/attempt-0",
        )

        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-001-01/attempt-0")
            == agent_sha
        )

    def test_distinct_recovery_refs_for_distinct_attempts(
        self, tmp_git_repo: Path
    ) -> None:
        """Two rollbacks of the same task land on distinct per-attempt refs.

        Regression: the previous global ref (`tmp/deviate-agent-work`) was
        overwritten on every rollback, so the operator could only ever
        recover the most-recently-discarded commit. Per-attempt refs
        preserve every discarded commit until the branch is GC'd.
        """
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)

        first_agent_sha = _make_commit(tmp_git_repo, "feat: attempt 1")
        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=first_agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="first rollback",
            recovery_branch="tmp/deviate-agent-work/TSK-001-01/attempt-0",
        )

        # Reset to red_sha (simulates a successful first rollback), then
        # make a second agent commit and trigger another rollback.
        subprocess.run(
            ["git", "reset", "--hard", red_sha],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        second_agent_sha = _make_commit(tmp_git_repo, "feat: attempt 2")
        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=second_agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="second rollback",
            recovery_branch="tmp/deviate-agent-work/TSK-001-01/attempt-1",
        )

        # Both refs exist with their distinct SHAs — neither was clobbered.
        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-001-01/attempt-0")
            == first_agent_sha
        )
        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-001-01/attempt-1")
            == second_agent_sha
        )

    def test_logs_preserve_event_with_ref_name(self, tmp_git_repo: Path) -> None:
        """AGENT_WORK_PRESERVED event records the per-attempt recovery ref."""
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent")

        with patch("deviate.cli.micro._log_run") as mock_log:
            _preserve_agent_work(
                tmp_git_repo,
                commit_sha=agent_sha,
                branch="feat/test",
                red_sha=red_sha,
                reason="test reason",
                recovery_branch="tmp/deviate-agent-work/TSK-007-03/attempt-2",
            )

        preserved_calls = [
            call
            for call in mock_log.call_args_list
            if call.args and call.args[0] == "AGENT_WORK_PRESERVED"
        ]
        assert len(preserved_calls) == 1
        kwargs = preserved_calls[0].kwargs
        assert kwargs["commit_sha"] == agent_sha
        assert kwargs["red_sha"] == red_sha
        assert kwargs["recovery_branch"] == (
            "tmp/deviate-agent-work/TSK-007-03/attempt-2"
        )
        assert kwargs["reason"] == "test reason"

    def test_survives_destructive_reset(self, tmp_git_repo: Path) -> None:
        """End-to-end: agent commits, runner rolls back, recovery ref keeps it.

        This is the regression test for the parent-SIGTERM-during-rollback
        scenario that motivated the fix: after the runner's ``git reset
        --hard <boundary>`` runs, the agent's commit must still be reachable
        via the per-attempt recovery ref.
        """
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent GREEN commit")
        recovery_branch = "tmp/deviate-agent-work/TSK-008-01/attempt-0"

        # Snapshot before the destructive reset.
        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="JUDGE rejected",
            recovery_branch=recovery_branch,
        )

        # Simulate the destructive reset that would strand the commit
        # without the recovery branch.
        subprocess.run(
            ["git", "reset", "--hard", red_sha],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

        # HEAD should be back at red_sha.
        assert _current_head(tmp_git_repo) == red_sha

        # But the agent's commit is still recoverable on its per-attempt ref.
        assert _ref_sha(tmp_git_repo, recovery_branch) == agent_sha

        # And the commit's content is inspectable.
        show = subprocess.run(
            ["git", "show", "--stat", recovery_branch],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert "feat: agent GREEN commit" in show.stdout


class TestExecuteRollbackCallsPreservation:
    """``_execute_rollback`` must invoke ``_preserve_agent_work`` before reset.

    The boundary_sha, task_id, and attempt kwargs are REQUIRED and forwarded
    to the per-attempt recovery ref; the runner never falls back to session
    state or ``HEAD~1``.
    """

    def test_calls_preserve_with_per_attempt_ref(self, tmp_git_repo: Path) -> None:
        """When commit_sha != boundary_sha, _preserve_agent_work is called
        with a per-task/per-attempt recovery ref derived from
        ``_recovery_branch_for``.
        """
        from deviate.cli.micro import _execute_rollback, _recovery_branch_for

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent wrote something")

        with (
            patch("deviate.cli.micro._preserve_agent_work") as mock_preserve,
            patch("deviate.cli.micro.append_rollback_snapshot"),
        ):
            _execute_rollback(
                tmp_git_repo,
                boundary_sha=red_sha,
                reason="test rejection",
                phase="JUDGE",
                task_id="TSK-042-07",
                attempt=3,
            )

        mock_preserve.assert_called_once()
        kwargs = mock_preserve.call_args.kwargs
        assert kwargs["commit_sha"] == agent_sha
        assert kwargs["red_sha"] == red_sha
        assert kwargs["recovery_branch"] == _recovery_branch_for("TSK-042-07", 3)
        assert kwargs["reason"].startswith("test rejection")
        # Positional args now: just root.
        args = mock_preserve.call_args.args
        assert args == (tmp_git_repo,)

    def test_skips_preserve_when_no_agent_commit(self, tmp_git_repo: Path) -> None:
        """When commit_sha == boundary_sha, _preserve_agent_work is NOT called.

        The runner shouldn't create spurious recovery refs for tasks where
        GREEN never committed (e.g. tests failed before the agent commit).
        """
        from deviate.cli.micro import _execute_rollback

        head_sha = _current_head(tmp_git_repo)

        with (
            patch("deviate.cli.micro._preserve_agent_work") as mock_preserve,
            patch("deviate.cli.micro.append_rollback_snapshot"),
        ):
            _execute_rollback(
                tmp_git_repo,
                boundary_sha=head_sha,
                reason="no commit",
                phase="JUDGE",
                task_id="TSK-099-01",
                attempt=0,
            )

        mock_preserve.assert_not_called()


class TestExecuteRollbackBoundaryContract:
    """``_execute_rollback`` requires an explicit ``boundary_sha``.

    The runner no longer falls back to ``SessionState.red_commit_sha`` or
    ``HEAD~1``. A missing / whitespace ``boundary_sha`` raises
    ``PhaseFailedError`` BEFORE any ``git reset`` / ``git clean`` so the
    worktree is never wiped without an explicit anchor.
    """

    def test_explicit_boundary_honored_over_session_state(
        self, tmp_git_repo: Path
    ) -> None:
        """``boundary_sha`` wins even when ``session.red_commit_sha`` differs.

        Scenario: session.json records one boundary, the caller supplies a
        different one (e.g. an EXECUTE-phase ``pre_execute_sha`` that
        happens to be older than the cached RED). The rollback must reset
        to the caller's boundary, not the cached one.
        """
        from deviate.cli.micro import _execute_rollback

        # Seed a "cached" RED boundary older than what the caller will supply.
        old_red_sha = _make_commit(tmp_git_repo, "chore: stale boundary seed")
        _seed_session_red_sha(tmp_git_repo, old_red_sha)

        # Caller's boundary is the more recent commit (e.g. pre_execute_sha).
        caller_boundary = _make_commit(tmp_git_repo, "chore: pre_execute anchor")
        agent_sha = _make_commit(tmp_git_repo, "feat: agent commit")

        _execute_rollback(
            tmp_git_repo,
            boundary_sha=caller_boundary,
            reason="EXECUTE rollback",
            phase="EXECUTE",
            task_id="TSK-100-01",
            attempt=0,
        )

        # HEAD must reset to the caller's boundary — not the stale cached one.
        assert _current_head(tmp_git_repo) == caller_boundary, (
            "_execute_rollback must honour the caller-supplied boundary_sha "
            "even when session.red_commit_sha points elsewhere."
        )

        # Session was not consulted: nothing else mutated HEAD past the caller's
        # boundary (the agent commit is gone, but the older cached boundary is
        # also unreachable from this HEAD).
        assert _current_head(tmp_git_repo) != old_red_sha
        assert _current_head(tmp_git_repo) != agent_sha

    def test_missing_boundary_raises_before_reset(self, tmp_git_repo: Path) -> None:
        """Empty ``boundary_sha`` raises ``PhaseFailedError`` without touching git.

        Guards against the regressed behavior where ``_execute_rollback``
        silently fell back to ``HEAD~1`` and wiped recent commits. The
        failure must fire BEFORE ``git reset`` / ``git clean`` so the
        worktree is intact when the operator inspects the abort.
        """
        from deviate.cli.micro import _execute_rollback
        from deviate.cli.micro import PhaseFailedError

        head_before = _current_head(tmp_git_repo)
        head_before_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        with pytest.raises(PhaseFailedError) as excinfo:
            _execute_rollback(
                tmp_git_repo,
                boundary_sha="",
                reason="missing boundary",
                phase="JUDGE",
                task_id="TSK-200-01",
                attempt=0,
            )

        assert "ROLLBACK_BOUNDARY_MISSING" in str(excinfo.value)
        assert "explicit boundary_sha" in str(excinfo.value)

        # No destructive reset fired: HEAD is unchanged and commit count is
        # the same as before the call.
        assert _current_head(tmp_git_repo) == head_before, (
            "_execute_rollback must not touch HEAD when boundary_sha is missing"
        )
        head_after_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        assert head_after_count == head_before_count

    def test_whitespace_boundary_raises_before_reset(self, tmp_git_repo: Path) -> None:
        """Whitespace-only ``boundary_sha`` is treated as missing.

        Same contract as the empty-string case — the runner rejects before
        resetting, never falls back to ``HEAD~1``.
        """
        from deviate.cli.micro import _execute_rollback
        from deviate.cli.micro import PhaseFailedError

        head_before = _current_head(tmp_git_repo)

        with pytest.raises(PhaseFailedError):
            _execute_rollback(
                tmp_git_repo,
                boundary_sha="   \t  ",
                reason="whitespace boundary",
                phase="JUDGE",
                task_id="TSK-201-02",
                attempt=0,
            )

        assert _current_head(tmp_git_repo) == head_before

    def test_distinct_recovery_refs_per_task_and_attempt(
        self, tmp_git_repo: Path
    ) -> None:
        """Each (task_id, attempt) pair resolves to a distinct recovery ref.

        Regression: the previous global ``tmp/deviate-agent-work`` ref
        meant a second rollback in any task silently overwrote the first.
        Per-task/per-attempt refs preserve every discarded commit until GC.
        """
        from deviate.cli.micro import _execute_rollback

        # Two rollbacks of the SAME task at DIFFERENT attempts.
        red_a = _current_head(tmp_git_repo)
        agent_a = _make_commit(tmp_git_repo, "feat: agent attempt 0")
        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_a,
            reason="first rollback",
            phase="JUDGE",
            task_id="TSK-301-01",
            attempt=0,
        )

        agent_b = _make_commit(tmp_git_repo, "feat: agent attempt 1")
        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_a,
            reason="second rollback",
            phase="JUDGE",
            task_id="TSK-301-01",
            attempt=1,
        )

        # A rollback of a DIFFERENT task at attempt 0.
        agent_c = _make_commit(tmp_git_repo, "feat: agent of other task")
        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_a,
            reason="third rollback",
            phase="JUDGE",
            task_id="TSK-302-01",
            attempt=0,
        )

        # Every discarded commit is recoverable at its distinct ref.
        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-301-01/attempt-0")
            == agent_a
        )
        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-301-01/attempt-1")
            == agent_b
        )
        assert (
            _ref_sha(tmp_git_repo, "tmp/deviate-agent-work/TSK-302-01/attempt-0")
            == agent_c
        )

    def test_global_recovery_ref_is_not_written(self, tmp_git_repo: Path) -> None:
        """The legacy global ``tmp/deviate-agent-work`` must NOT be written.

        Pin: any code path that does ``git branch -f tmp/deviate-agent-work``
        silently overwrites the recovery handle left behind by older
        versions of the runner (e.g. the bb0b955 commit). Per-attempt refs
        live under ``tmp/deviate-agent-work/<task>/attempt-N`` and never
        touch the parent ref itself.
        """
        from deviate.cli.micro import _execute_rollback

        red_sha = _current_head(tmp_git_repo)
        _make_commit(tmp_git_repo, "feat: agent commit")

        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_sha,
            reason="guard test",
            phase="JUDGE",
            task_id="TSK-400-01",
            attempt=0,
        )

        # The legacy global ref must not exist (or, if it pre-existed from
        # an earlier version, must still point at whatever it pointed at
        # before this call). Either way, no new write landed on it.
        legacy_ref = "tmp/deviate-agent-work"
        if _ref_exists(tmp_git_repo, legacy_ref):
            # If a pre-existing legacy ref is present (from older code),
            # _execute_rollback must not have force-updated it.
            pre_sha = subprocess.run(
                ["git", "rev-parse", legacy_ref],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            # Re-run and verify the ref is unchanged.
            _make_commit(tmp_git_repo, "feat: another agent commit")
            _execute_rollback(
                tmp_git_repo,
                boundary_sha=red_sha,
                reason="guard test 2",
                phase="JUDGE",
                task_id="TSK-400-02",
                attempt=0,
            )
            post_sha = subprocess.run(
                ["git", "rev-parse", legacy_ref],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            assert pre_sha == post_sha, (
                "_execute_rollback must not force-update the legacy global "
                "tmp/deviate-agent-work ref; per-attempt refs only."
            )


class TestRecoveryBranchFor:
    """``_recovery_branch_for`` sanitises task ids and threads attempt index."""

    def test_emits_per_task_per_attempt_path(self) -> None:
        from deviate.cli.micro import _recovery_branch_for

        assert (
            _recovery_branch_for("TSK-001-01", 0)
            == "tmp/deviate-agent-work/TSK-001-01/attempt-0"
        )
        assert (
            _recovery_branch_for("TSK-001-01", 3)
            == "tmp/deviate-agent-work/TSK-001-01/attempt-3"
        )

    def test_sanitises_path_hostile_characters(self) -> None:
        """Task ids with slashes / colons / whitespace collapse to safe form."""
        from deviate.cli.micro import _recovery_branch_for

        # Colons are git-ref-hostile; the sanitiser must collapse them.
        result = _recovery_branch_for("feat/001:abc", 1)
        assert ":" not in result.split("attempt-")[0]
        assert "/" not in result.split("tmp/deviate-agent-work/")[1].split("/attempt-")[
            0
        ] or all(
            # allow forward slashes inside the sanitised task id (git refs
            # accept slashes); what we forbid is the raw `:` and whitespace.
            ch not in ": \t\n"
            for ch in result
        )

    def test_empty_task_id_falls_back_to_unknown(self) -> None:
        from deviate.cli.micro import _recovery_branch_for

        assert _recovery_branch_for("", 0) == "tmp/deviate-agent-work/unknown/attempt-0"
        assert (
            _recovery_branch_for("   ", 2) == "tmp/deviate-agent-work/unknown/attempt-2"
        )
