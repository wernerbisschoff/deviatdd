from __future__ import annotations

import io
import shutil
import subprocess
from contextlib import chdir, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tests.conftest import _git_env

from deviate.cli import cli
from deviate.cli.meso import (
    _build_slim_prompt,
    _build_plan_digest,
    _discover_claimable_issue,
    _effective_local,
    _meso_discover_and_sequence,
    _meso_run,
)
from deviate.core.worktree import create_worktree
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord, append_issue_transition

runner = CliRunner()


def _setup_minimal_workspace(
    tmp_git_repo: Path,
    issue_id: str = "ISS-001-001",
    issue_status: str = "BACKLOG",
    create_spec_md: bool = False,
    seed_plan: bool = True,
    seed_tasks: bool = True,
    seed_slug: str = "iss-001",
) -> None:
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    spec_root = tmp_git_repo / "specs"
    spec_root.mkdir(parents=True)
    (spec_root / "constitution.md").write_text(
        "# Constitution\ntest_command = pytest\nlint_command = ruff\n"
    )

    issue_body_dir = spec_root / "test-epic" / "issues"
    issue_body_dir.mkdir(parents=True)
    (issue_body_dir / f"{seed_slug}.md").write_text(
        "# Test Issue\n\nFR-001: do the thing\n"
    )

    prd_dir = spec_root / "test-epic"
    (prd_dir / "prd.md").write_text("# PRD\n\nFR-001: do the thing\n")

    if create_spec_md:
        spec_dir = spec_root / "test-epic" / seed_slug
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "# Spec\n\n**Scenario 1:**\n- **Given** precondition\n"
            "- **When** action\n- **Then** result\n"
        )

    # Seed plan.md / tasks.md at the spec-path location so the
    # ``_enforce_phase_artifact`` guard (added 2026-07-27 to close the
    # false-success validation gap) passes for tests that mock
    # ``AgentBackend.invoke`` to return PASS without writing files.
    # Regression tests pass ``seed_plan=False`` / ``seed_tasks=False`` to
    # exercise the missing-artifact path without an ``os.remove`` dance.
    # ``seed_slug`` overrides the default issue-slug location so tests
    # that resolve a different ``source_file`` (e.g. ``iss-002``) seed
    # at the matching path the orchestrator will look up.
    issue_dir = spec_root / "test-epic" / seed_slug
    issue_dir.mkdir(parents=True, exist_ok=True)
    if seed_plan:
        (issue_dir / "plan.md").write_text(
            "## Acceptance Contract\n\n"
            "**Scenario AC-PLAN-001: Complete the seeded smoke**\n"
            "**Source Outline**: `AO-001`\n"
            "**Upstream Traceability**: `US-001-01`, `FR-001-X`, `AC-001-X-01`\n"
            "**Current-Code Evidence**: `src/example.py:run`\n"
            "**Given**: A seeded repository is available.\n"
            "**When**: The plan phase runs.\n"
            "**Then**: The contract is honored.\n"
            "**Verification Mode**: automated\n"
        )
    if seed_tasks:
        (issue_dir / "tasks.md").write_text("# Tasks\n\n- TSK-001-01 smoke (tdd)\n")
    ledger = spec_root / "issues.jsonl"
    record = IssueRecord(
        issue_id=issue_id,
        type="feature",
        title="Test Meso Issue",
        status=issue_status,
        source_file=f"specs/test-epic/issues/{seed_slug}.md",
        timestamp=datetime.now(timezone.utc),
    )
    ledger.write_text(record.model_dump_json() + "\n")

    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "setup workspace"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )


def _make_mock_subprocess() -> MagicMock:
    real_run = subprocess.run

    def side_effect(args, **kwargs):
        args_str = " ".join(args) if isinstance(args, list) else str(args)
        if "mise" in args_str or "git push" in args_str:
            return MagicMock(returncode=0, stdout="", stderr="")
        return real_run(args, **kwargs)

    return MagicMock(side_effect=side_effect)


class TestMesoOrchestration:
    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_full_pipeline_success(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run()

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"Expected IDLE, got {loaded.current_phase}"
            )

        assert mock_invoke.call_count == 2
        mock_plan_post.assert_called_once_with(force=False, issue_id="ISS-001-001")
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_specific_issue(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo, issue_id="ISS-001-004")

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-004")

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"
            assert loaded.active_issue_id == "ISS-001-004"

        mock_plan_post.assert_called_once_with(force=False, issue_id="ISS-001-004")
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-004")

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_worktree_claim_copy_keys_session_to_claimed_issue(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-006: worktree session after copy names the claimed issue."""
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo, issue_id="ISS-001-001")
        SessionState(current_phase="IDLE", active_issue_id="ISS-001-000").save(
            tmp_git_repo / ".deviate" / "session.json"
        )

        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

        wt_session = SessionState.load(worktree_path / ".deviate" / "session.json")
        assert wt_session.active_issue_id == "ISS-001-001", (
            "Worktree session after claim/copy must name the claimed issue, "
            f"not leftover {wt_session.active_issue_id!r}"
        )

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_issue_progress_reset(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo, issue_id="ISS-001-001")

        ledger = tmp_git_repo / "specs" / "issues.jsonl"
        progress = IssueRecord(
            issue_id="ISS-001-001",
            type="feature",
            title="Test Meso Issue",
            status="SPECIFIED",
            source_file="specs/test-epic/issues/iss-001.md",
            timestamp=datetime.now(timezone.utc),
        )
        append_issue_transition(progress, ledger)

        with chdir(tmp_git_repo):
            dot_dir = tmp_git_repo / ".deviate"
            session = SessionState(
                current_phase="SPECIFY", active_issue_id="ISS-001-001"
            )
            session.save(dot_dir / "session.json")

            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "IDLE"

        mock_plan_post.assert_called_once_with(force=False, issue_id="ISS-001-001")
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    def test_meso_completed_issue_aborts(
        self,
        tmp_git_repo: Path,
    ) -> None:
        _setup_minimal_workspace(
            tmp_git_repo, issue_id="ISS-001-001", issue_status="COMPLETED"
        )

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit) as exc_info:
                    _meso_run(issue_id="ISS-001-001")
            assert exc_info.value.code != 0

    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_dry_run_no_side_effects(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(dry_run=True)

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"

            wt_path = tmp_git_repo / ".worktrees"
            assert not wt_path.exists(), "Dry run should not create worktrees"

        mock_invoke.assert_not_called()

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_run_with_spec_md(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(
            tmp_git_repo, issue_id="ISS-001-001", create_spec_md=True
        )

        with chdir(tmp_git_repo):
            dot_dir = tmp_git_repo / ".deviate"
            session = SessionState(
                current_phase="SPECIFY", active_issue_id="ISS-001-001"
            )
            session.save(dot_dir / "session.json")

            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "IDLE"

        assert mock_invoke.call_count == 2
        mock_plan_post.assert_called_once_with(force=False, issue_id="ISS-001-001")
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_agent_failure_aborts(
        self,
        mock_pytest: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        from deviate.core.agent import AgentSubprocessError

        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with patch(
                    "deviate.core.agent.AgentBackend.invoke",
                    side_effect=[
                        MagicMock(status="PASS", phase="plan"),
                        AgentSubprocessError(
                            "TASKS failed: agent exited with code 1", exit_code=1
                        ),
                    ],
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        _meso_run(issue_id="ISS-001-001")
            assert exc_info.value.code != 0

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "PLAN", (
                "Session advances to PLAN before plan invoke; "
                "plan post runs after plan invoke so task failure "
                "leaves session at PLAN"
            )

    def test_meso_blocked_issue_rejected(
        self,
        tmp_git_repo: Path,
    ) -> None:
        _setup_minimal_workspace(tmp_git_repo, issue_id="ISS-001-001")

        ledger = tmp_git_repo / "specs" / "issues.jsonl"
        blocked = IssueRecord(
            issue_id="ISS-001-002",
            type="feature",
            title="Blocked Issue",
            status="BACKLOG",
            source_file="specs/test-epic/issues/iss-002.md",
            timestamp=datetime.now(timezone.utc),
            blocked_by=["ISS-001-001"],
        )
        append_issue_transition(blocked, ledger)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit) as exc_info:
                    _meso_run(issue_id="ISS-001-002")
            assert exc_info.value.code != 0

    def test_meso_no_unblocked_issues(
        self,
        tmp_git_repo: Path,
    ) -> None:
        _setup_minimal_workspace(
            tmp_git_repo, issue_id="ISS-001-001", issue_status="COMPLETED"
        )

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit) as exc_info:
                    _meso_run()
            assert exc_info.value.code != 0

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_force_guard_bypass(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(
            tmp_git_repo, issue_id="ISS-001-001", seed_slug="iss-002"
        )

        ledger = tmp_git_repo / "specs" / "issues.jsonl"
        blocked = IssueRecord(
            issue_id="ISS-001-002",
            type="feature",
            title="Blocked Issue",
            status="BACKLOG",
            source_file="specs/test-epic/issues/iss-002.md",
            timestamp=datetime.now(timezone.utc),
            blocked_by=["ISS-001-001"],
        )
        append_issue_transition(blocked, ledger)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-002", force=True)

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"

        mock_plan_post.assert_called_once_with(force=True, issue_id="ISS-001-002")
        mock_tasks_post.assert_called_once_with(force=True, issue_id="ISS-001-002")


class TestBuildSlimPrompt:
    def test_build_slim_prompt_returns_string(self) -> None:
        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }
        result = _build_slim_prompt("tasks", contract)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_plan_digest_is_bounded_to_16_kib(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "# Plan\n" + "essential implementation detail\n" * 2_000,
            encoding="utf-8",
        )

        digest = _build_plan_digest(plan_path)

        assert len(digest.encode("utf-8")) <= 16 * 1024
        assert digest.startswith("# Plan\n")
        assert "PLAN_DIGEST_TRUNCATED" in digest


class TestMesoDiscoverAndSequence:
    def test_discover_returns_issue_id(self, tmp_git_repo: Path) -> None:
        _setup_minimal_workspace(tmp_git_repo)
        with chdir(tmp_git_repo):
            result = _meso_discover_and_sequence()
            assert result is not None
            assert isinstance(result, str)

    def test_discover_returns_none_when_empty(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = _meso_discover_and_sequence()
            assert result is None


class TestDiscoverClaimableIssue:
    def test_returns_next_unclaimed(self, tmp_git_repo: Path) -> None:
        """Returns the first BACKLOG when no remote branch exists."""
        _setup_minimal_workspace(tmp_git_repo)
        with chdir(tmp_git_repo):
            with patch("deviate.cli.meso.branch_exists_on_remote", return_value=False):
                result = _discover_claimable_issue()
            assert result == "ISS-001-001"

    def test_skips_issues_with_remote_branch(self, tmp_git_repo: Path) -> None:
        """Skips issues whose deterministic branch exists on remote."""
        _setup_minimal_workspace(tmp_git_repo)

        ledger = tmp_git_repo / "specs" / "issues.jsonl"
        second = IssueRecord(
            issue_id="ISS-001-002",
            type="feature",
            title="Second Unblocked",
            status="BACKLOG",
            source_file="specs/test-epic/issues/iss-002.md",
            timestamp=datetime.now(timezone.utc),
        )
        append_issue_transition(second, ledger)

        (tmp_git_repo / "specs" / "test-epic" / "issues" / "iss-002.md").write_text(
            "# Test Issue\n\nFR-002: do another thing\n"
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add second issue"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            with patch(
                "deviate.cli.meso.branch_exists_on_remote",
                side_effect=lambda branch, **kw: branch == "feat/test-epic/iss-001",
            ):
                result = _discover_claimable_issue()
            assert result == "ISS-001-002", (
                f"Expected ISS-001-002 (skipping ISS-001-001 which has a remote "
                f"branch), got {result}"
            )

    def test_returns_none_when_all_claimed_remotely(self, tmp_git_repo: Path) -> None:
        """Returns None when every BACKLOG issue has a remote branch."""
        _setup_minimal_workspace(tmp_git_repo)
        with chdir(tmp_git_repo):
            with patch("deviate.cli.meso.branch_exists_on_remote", return_value=True):
                result = _discover_claimable_issue()
            assert result is None

    def test_returns_none_when_ledger_empty(self, tmp_path: Path) -> None:
        """Returns None when no BACKLOG issues exist at all."""
        with chdir(tmp_path):
            result = _discover_claimable_issue()
            assert result is None

    def test_discover_local_returns_backlog_when_origin_branch_exists(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-005: local=True returns the first BACKLOG even if origin has the branch."""
        _setup_minimal_workspace(tmp_git_repo)
        with chdir(tmp_git_repo):
            with patch(
                "deviate.cli.meso.branch_exists_on_remote", return_value=True
            ) as mock_remote:
                result = _discover_claimable_issue(local=True)
            assert result == "ISS-001-001"
            mock_remote.assert_not_called()

    def test_discover_config_false_does_not_skip_origin(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-005: claim_remote = false is effective local; leftover origin stays claimable."""
        _setup_minimal_workspace(tmp_git_repo)
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = false\n", encoding="utf-8"
        )
        with chdir(tmp_git_repo):
            with patch(
                "deviate.cli.meso.branch_exists_on_remote", return_value=True
            ) as mock_remote:
                result = _discover_claimable_issue(local=_effective_local(False))
            assert result == "ISS-001-001"
            mock_remote.assert_not_called()

    def test_skips_issues_with_local_worktree(self, tmp_git_repo: Path) -> None:
        """Skips a BACKLOG issue that already has a local claim worktree.

        A ``deviate meso run`` / ``deviate specify`` continues to show the issue
        as BACKLOG in the main checkout's ledger (the SPECIFIED row lives on the
        feature branch), so auto-discover must skip it when ``feat/...`` already has
        a local worktree — otherwise two parallel terminals re-claim the same issue."""
        _setup_minimal_workspace(tmp_git_repo)

        ledger = tmp_git_repo / "specs" / "issues.jsonl"
        second = IssueRecord(
            issue_id="ISS-001-002",
            type="feature",
            title="Second Unblocked",
            status="BACKLOG",
            source_file="specs/test-epic/issues/iss-002.md",
            timestamp=datetime.now(timezone.utc),
        )
        append_issue_transition(second, ledger)
        (tmp_git_repo / "specs" / "test-epic" / "issues" / "iss-002.md").write_text(
            "# Test Issue\n\nFR-002: do another thing\n"
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add second issue"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        # A prior claim already registered a worktree for the first issue.
        create_worktree(
            branch="feat/test-epic/iss-001",
            path=tmp_git_repo / ".worktrees" / "feat-test-epic-iss-001",
            repo=tmp_git_repo,
        )

        with chdir(tmp_git_repo):
            with patch("deviate.cli.meso.branch_exists_on_remote", return_value=False):
                result = _discover_claimable_issue()
            assert result == "ISS-001-002", (
                "Expected ISS-001-002 (skipping ISS-001-001 which has a local ",
                f"claim worktree), got {result}",
            )


class TestMesoRunStdoutSuppression:
    """``_meso_run`` must not forward ``_plan_pre`` / ``_tasks_pre``'s
    JSON contract ``print()`` to the user's terminal — those dumps are for
    the agent-subprocess CLI workflow (``deviate plan pre``), not the
    in-process parent pipeline which builds its own contract.
    """

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_no_plan_or_tasks_contract_in_stdout(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        buf = io.StringIO()
        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with redirect_stdout(buf):
                    _meso_run()

        stdout = buf.getvalue()
        # ``plan_target`` is a key unique to ``_plan_pre``'s contract
        # and ``tasks_target`` to ``_tasks_pre``'s contract — confirming
        # neither JSON dump leaked into the user's terminal.
        assert '"plan_target"' not in stdout, (
            "_plan_pre's JSON contract leaked into _meso_run output:\n" + stdout
        )
        assert '"tasks_target"' not in stdout, (
            "_tasks_pre's JSON contract leaked into _meso_run output:\n" + stdout
        )


class TestMesoRunNoSetup:
    """``_meso_run`` must honor ``--no-setup`` (skip SPECIFY worktree +
    ledger claim) while preserving PLAN + TASKS execution and the default
    (no ``--no-setup``) flow's SPECIFY invocation.
    """

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_no_setup_skips_specify_pre(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        # If ``_specify_pre`` is ever invoked under ``no_setup=True`` the
        # assertion sentinel fires immediately — proving the bypass works.
        mock_specify_pre.side_effect = AssertionError(
            "_specify_pre must not be called when no_setup=True"
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001", no_setup=True)

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"Expected IDLE, got {loaded.current_phase}"
            )

        mock_specify_pre.assert_not_called()
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_not_called()

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_default_invokes_specify_pre(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """Backwards-compat: omitting ``no_setup`` MUST still drive SPECIFY.

        The pre-create of a real git worktree + ``.deviate`` sync keeps the
        downstream ``_plan_pre`` contract-mode dispatch working when both
        SPECIFY helpers are short-circuited by mocks.
        """
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        shutil.copytree(
            str(tmp_git_repo / ".deviate"),
            str(worktree_path / ".deviate"),
            dirs_exist_ok=True,
        )

        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

        mock_specify_pre.assert_called_once()

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_no_setup_banner_omits_specify(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_specify_pre: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """``PipelineBanner.steps`` must drop ``SPECIFY`` under ``no_setup``.

        Asserts only on the banner text — the rest of the pipeline is just
        stubbed to keep the two runs cheap and isolated.
        """
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        shutil.copytree(
            str(tmp_git_repo / ".deviate"),
            str(worktree_path / ".deviate"),
            dirs_exist_ok=True,
        )

        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        # ── Run 1: no_setup=True → banner must NOT mention SPECIFY ──
        buf_no_setup = io.StringIO()
        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with redirect_stdout(buf_no_setup):
                    _meso_run(issue_id="ISS-001-001", no_setup=True)
        no_setup_output = buf_no_setup.getvalue()
        # The WARN banner mentions SPECIFY ("skipping SPECIFY"), so a naive
        # ``"SPECIFY" not in output`` check would fail on the warning text.
        # The banner's steps are joined by ``  ▶  `` — that arrow pattern
        # only appears in the rendered PipelineBanner, never in the WARN.
        assert "SPECIFY  ▶" not in no_setup_output, (
            "SPECIFY must not appear in PipelineBanner steps when "
            f"no_setup=True:\n{no_setup_output}"
        )

        # ── Run 2: no_setup=False → banner MUST mention SPECIFY ──
        buf_default = io.StringIO()
        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with redirect_stdout(buf_default):
                    _meso_run(issue_id="ISS-001-001", no_setup=False)
        default_output = buf_default.getvalue()
        assert "SPECIFY  ▶" in default_output, (
            "SPECIFY must appear in PipelineBanner steps when "
            f"no_setup=False:\n{default_output}"
        )

    def test_meso_run_command_local_forwards_local_true(
        self,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-003: ``deviate meso run --local`` forwards ``local=True``.

        The flag is a one-shot skip-push claim, not ``--no-setup``.
        """
        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch(
                "deviate.cli.meso._meso_run", return_value=str(tmp_git_repo)
            ) as mock_run:
                result = runner.invoke(
                    cli, ["meso", "run", "--local", "--issue", "ISS-001-001"]
                )

        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("local") is True, (
            "meso run --local must forward local=True into _meso_run; "
            f"got kwargs={mock_run.call_args.kwargs}"
        )
        assert mock_run.call_args.kwargs.get("no_setup") is not True, (
            "--local must not be treated as --no-setup; "
            f"got kwargs={mock_run.call_args.kwargs}"
        )

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_run_omitted_flag_claim_remote_false_forwards_local_true(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-003: omitted ``--local`` plus ``claim_remote = false``
        still forwards ``local=True`` into ``_specify_pre``.
        """
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)
        (tmp_git_repo / ".deviate" / "config.toml").write_text("claim_remote = false\n")

        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        shutil.copytree(
            str(tmp_git_repo / ".deviate"),
            str(worktree_path / ".deviate"),
            dirs_exist_ok=True,
        )
        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

        mock_specify_pre.assert_called_once()
        assert mock_specify_pre.call_args.kwargs.get("local") is True, (
            "omitted --local with claim_remote=false must call "
            "_specify_pre(..., local=True); "
            f"got kwargs={mock_specify_pre.call_args.kwargs}"
        )

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_run_local_does_not_imply_no_setup(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-006: ``--local`` still runs SPECIFY (worktree + claim).

        Local mode skips only the remote lock. It does not skip
        ``_specify_pre``.
        """
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        shutil.copytree(
            str(tmp_git_repo / ".deviate"),
            str(worktree_path / ".deviate"),
            dirs_exist_ok=True,
        )
        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001", local=True)

        mock_specify_pre.assert_called_once()
        assert mock_specify_pre.call_args.kwargs.get("local") is True, (
            "_meso_run(..., local=True) must call _specify_pre(..., local=True); "
            f"got kwargs={mock_specify_pre.call_args.kwargs}"
        )

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_run_no_setup_with_local_skips_specify_pre(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-006: ``--no-setup --local`` still skips ``_specify_pre``.

        Combined flags do not invent a third mode. ``--no-setup`` wins for
        the worktree and ledger-claim skip.
        """
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="tasks",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_specify_pre.side_effect = AssertionError(
            "_specify_pre must not be called when no_setup=True, even with local=True"
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001", no_setup=True, local=True)

        mock_specify_pre.assert_not_called()
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_not_called()


class TestMesoArtifactEnforcement:
    """``_enforce_phase_artifact`` must fail fast when an agent returns
    PASS without producing its phase artifact.

    Regression tests for the false-success validation gap where
    ``_invoke_agent_phase`` trusted ``manifest.status == "PASS"`` and the
    orchestrator advanced to the next phase even though no plan.md /
    tasks.md existed. The earlier pipeline tests mocked ``_plan_post`` /
    ``_tasks_post`` so they could not catch this; here we let the post
    hooks run unmocked but trip the new guard first.
    """

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_plan_not_written_when_agent_returns_pass(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Defensive: if a prior test leaked cwd into tmp_git_repo, fail
        # loudly with a clear message rather than spinning on a wrong cwd.
        if Path.cwd().resolve() == tmp_git_repo.resolve():
            raise AssertionError(
                f"cwd leaked into tmp_git_repo before test started: {Path.cwd()}"
            )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        # Agent says PASS but writes nothing; ``_plan_post`` is mocked to
        # prove the guard (not the post-hook) is what catches the gap.
        mock_invoke.return_value = MagicMock(status="PASS", phase="plan")

        _setup_minimal_workspace(tmp_git_repo, seed_plan=False, seed_tasks=False)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit) as exc_info:
                    _meso_run(issue_id="ISS-001-001")

        assert exc_info.value.code != 0
        # The guard fires before ``_plan_post`` — the post-hook is never
        # invoked because the orchestrator aborts on the missing
        # artifact at the orchestrator layer, not the validator layer.
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_not_called()
        captured = capsys.readouterr()
        assert "PLAN_NOT_WRITTEN" in captured.out + captured.err

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_tasks_not_written_when_agent_returns_pass(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Defensive: see PLAN regression test above for rationale.
        if Path.cwd().resolve() == tmp_git_repo.resolve():
            raise AssertionError(
                f"cwd leaked into tmp_git_repo before test started: {Path.cwd()}"
            )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        # Both invocations return PASS without writing files; plan.md is
        # seeded so the PLAN guard passes, but tasks.md is missing so
        # the TASKS guard fires.
        mock_invoke.return_value = MagicMock(status="PASS", phase="tasks")

        _setup_minimal_workspace(tmp_git_repo, seed_plan=True, seed_tasks=False)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit) as exc_info:
                    _meso_run(issue_id="ISS-001-001")

        assert exc_info.value.code != 0
        # PLAN succeeded (artifact existed), so ``_plan_post`` ran; the
        # abort happens at the TASKS guard, before ``_tasks_post``.
        mock_plan_post.assert_called_once_with(force=False, issue_id="ISS-001-001")
        mock_tasks_post.assert_not_called()
        captured = capsys.readouterr()
        assert "TASKS_NOT_WRITTEN" in captured.out + captured.err


class TestMesoRunWorktreeAutoDetect:
    """``_meso_run`` must auto-skip SPECIFY when already inside a linked worktree.

    Inside the worktree, the operator wants a plain continuation: PLAN + TASKS
    for the active issue. Re-running SPECIFY would clobber the existing branch
    and violate the Git Isolation Principle.
    """

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_run_inside_worktree_skips_specify(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(status="PASS", phase="tasks")
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        # Sentinel: if SPECIFY runs, the test fails immediately.
        mock_specify_pre.side_effect = AssertionError(
            "_specify_pre must not run when already inside the worktree"
        )

        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("deviate.cli.meso._is_linked_worktree", lambda cwd=None: True):
                with patch("subprocess.run", _make_mock_subprocess()):
                    _meso_run()  # No explicit --issue: should resolve from branch.

        mock_specify_pre.assert_not_called()
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_not_called()
        loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert loaded.current_phase == "IDLE"

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._try_claim_issue")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_run_outside_worktree_does_not_skip_specify(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_try_claim_issue: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """Sanity: auto-detect must NOT fire outside a linked worktree.

        Sets up a real linked worktree at ``.worktrees/feat/test-epic/iss-001``
        so the subsequent ``shutil.copytree`` syncs the session into a distinct
        directory (avoiding the src==dst failure that bit the first draft).
        """
        mock_invoke.return_value = MagicMock(status="PASS", phase="tasks")
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        _setup_minimal_workspace(tmp_git_repo)

        # Create a real linked worktree so SPECIFY's setup pipeline (which
        # copies ``.deviate/`` into the worktree) has a distinct destination.
        worktree_path = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(worktree_path),
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        shutil.copytree(
            str(tmp_git_repo / ".deviate"),
            str(worktree_path / ".deviate"),
            dirs_exist_ok=True,
        )
        worktree_dict = {"worktree_path": str(worktree_path)}
        mock_specify_pre.return_value = worktree_dict
        mock_try_claim_issue.return_value = worktree_dict

        with chdir(tmp_git_repo):
            # ``tmp_git_repo`` has ``.git`` as a directory (it's the main
            # repo the test fixture created), so ``_is_linked_worktree()``
            # naturally returns False — no patch needed. The pre-created
            # worktree only takes effect after ``chdir``-ing into it.
            with patch("subprocess.run", _make_mock_subprocess()):
                _meso_run(issue_id="ISS-001-001")

        # Outside a worktree the SPECIFY step still runs (auto-claim path).
        mock_specify_pre.assert_called_once()

    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.cli.meso._is_linked_worktree")
    def test_run_inside_worktree_explicit_issue_overrides_branch(
        self,
        mock_is_worktree: MagicMock,
        mock_specify_pre: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """``--issue <other-id>`` should be honored even inside a worktree.

        The branch-derived issue lookup only fires when the operator omits
        ``--issue`` — an explicit override must skip the auto-detect branch
        entirely and fall through to the normal discovery / SPECIFY path.
        """
        mock_is_worktree.return_value = True
        _setup_minimal_workspace(tmp_git_repo)

        with chdir(tmp_git_repo):
            with patch("subprocess.run", _make_mock_subprocess()):
                with pytest.raises(SystemExit):
                    # Use an explicit issue ID not present in the ledger so
                    # the path aborts at INVALID_ISSUE_ID before SPECIFY
                    # but AFTER the auto-detect branch decides to skip.
                    _meso_run(issue_id="ISS-999-999")

        # No sentinel on mock_specify_pre: we just want to confirm the
        # explicit --issue path did not silently succeed — it must surface
        # the INVALID_ISSUE_ID failure instead of auto-claiming.
        mock_specify_pre.assert_not_called()
