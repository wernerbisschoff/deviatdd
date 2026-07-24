"""Tests for F3 (rollback safety) — agent-work preservation on JUDGE rejection.

Reproduces the parent-SIGTERM-during-rollback failure mode observed in
feat/001-wizards-mvp-booking/003-.../003-secure-desktop-availability-calendar
(2026-07-24): when the runner's ``_execute_rollback`` was interrupted
between ``git reset --hard`` and ``git clean -fd``, the agent's commit
was stranded in the worktree without being committed anywhere recoverable.

The fix: ``_preserve_agent_work`` snapshots the agent's HEAD onto
``tmp/deviate-agent-work`` BEFORE the destructive reset, so the agent's
work survives parent SIGTERMs that land mid-rollback.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch


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


def _recovery_sha(repo: Path, branch: str = "tmp/deviate-agent-work") -> str:
    """Return the SHA of the named recovery branch (assumes it exists)."""
    return subprocess.run(
        ["git", "rev-parse", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class TestPreserveAgentWork:
    """``_preserve_agent_work`` snapshots agent's HEAD on a recovery branch."""

    def test_preserves_agent_work_on_side_branch(self, tmp_git_repo: Path) -> None:
        """Agent's commit survives by being copied to tmp/deviate-agent-work."""
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent wrote code")

        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="COMPLIANCE_VIOLATION: hardcoded forward_window_weeks",
        )

        assert _recovery_sha(tmp_git_repo) == agent_sha

    def test_branch_overwrites_on_subsequent_rollbacks(
        self, tmp_git_repo: Path
    ) -> None:
        """Multiple rollbacks overwrite the same branch; latest wins."""
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)

        first_agent_sha = _make_commit(tmp_git_repo, "feat: attempt 1")
        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=first_agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="first rollback",
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
        )

        assert _recovery_sha(tmp_git_repo) == second_agent_sha

    def test_logs_preserve_event(self, tmp_git_repo: Path) -> None:
        """AGENT_WORK_PRESERVED event is emitted for the audit trail."""
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
        assert kwargs["recovery_branch"] == "tmp/deviate-agent-work"
        assert kwargs["reason"] == "test reason"

    def test_survives_destructive_reset(self, tmp_git_repo: Path) -> None:
        """End-to-end: agent commits, runner rolls back, recovery branch keeps it.

        This is the regression test for the parent-SIGTERM-during-rollback
        scenario that motivated the fix: after the runner's ``git reset
        --hard red_sha`` runs, the agent's commit must still be reachable
        via ``tmp/deviate-agent-work``.
        """
        from deviate.cli.micro import _preserve_agent_work

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent GREEN commit")

        # Snapshot before the destructive reset.
        _preserve_agent_work(
            tmp_git_repo,
            commit_sha=agent_sha,
            branch="feat/test",
            red_sha=red_sha,
            reason="JUDGE rejected",
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

        # But the agent's commit is still recoverable.
        assert _recovery_sha(tmp_git_repo) == agent_sha

        # And the commit's content is inspectable.
        show = subprocess.run(
            ["git", "show", "--stat", "tmp/deviate-agent-work"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert "feat: agent GREEN commit" in show.stdout


class TestExecuteRollbackCallsPreservation:
    """``_execute_rollback`` must invoke ``_preserve_agent_work`` before reset."""

    def test_calls_preserve_when_agent_made_a_commit(self, tmp_git_repo: Path) -> None:
        """When commit_sha != red_sha, _preserve_agent_work is called first."""
        from deviate.cli.micro import _execute_rollback

        red_sha = _current_head(tmp_git_repo)
        agent_sha = _make_commit(tmp_git_repo, "feat: agent wrote something")

        with (
            patch("deviate.cli.micro._preserve_agent_work") as mock_preserve,
            patch(
                "deviate.cli.micro._resolve_red_boundary_sha",
                return_value=red_sha,
            ),
            patch("deviate.cli.micro.append_rollback_snapshot"),
        ):
            _execute_rollback(
                tmp_git_repo,
                reason="test rejection",
                phase="JUDGE",
            )

        mock_preserve.assert_called_once()
        # All positional args: (root, commit_sha, branch, red_sha, reason).
        args = mock_preserve.call_args.args
        assert args[1] == agent_sha
        assert args[3] == red_sha
        assert args[4].startswith("test rejection")

    def test_skips_preserve_when_no_agent_commit(self, tmp_git_repo: Path) -> None:
        """When commit_sha == red_sha, _preserve_agent_work is NOT called.

        The runner shouldn't create spurious recovery refs for tasks where
        GREEN never committed (e.g. tests failed before the agent commit).
        """
        from deviate.cli.micro import _execute_rollback

        head_sha = _current_head(tmp_git_repo)

        with (
            patch("deviate.cli.micro._preserve_agent_work") as mock_preserve,
            patch(
                "deviate.cli.micro._resolve_red_boundary_sha",
                return_value=head_sha,
            ),
            patch("deviate.cli.micro.append_rollback_snapshot"),
        ):
            _execute_rollback(
                tmp_git_repo,
                reason="no commit",
                phase="JUDGE",
            )

        mock_preserve.assert_not_called()
