from __future__ import annotations

import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _git_env

from deviate.cli.meso import _build_slim_prompt, _meso_discover_and_sequence, _meso_run
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord, append_issue_transition


def _setup_minimal_workspace(
    tmp_git_repo: Path,
    issue_id: str = "ISS-001-001",
    issue_status: str = "BACKLOG",
    create_spec_md: bool = False,
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
    (issue_body_dir / "iss-001.md").write_text("# Test Issue\n\nFR-001: do the thing\n")

    prd_dir = spec_root / "test-epic"
    (prd_dir / "prd.md").write_text("# PRD\n\nFR-001: do the thing\n")

    if create_spec_md:
        spec_dir = spec_root / "test-epic" / "iss-001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text(
            "# Spec\n\n**Scenario 1:**\n- **Given** precondition\n"
            "- **When** action\n- **Then** result\n"
        )

    ledger = spec_root / "issues.jsonl"
    record = IssueRecord(
        issue_id=issue_id,
        type="feature",
        title="Test Meso Issue",
        status=issue_status,
        source_file="specs/test-epic/issues/iss-001.md",
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
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_full_pipeline_success(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_specify_post: MagicMock,
        mock_tasks_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="specify",
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

        mock_specify_pre.assert_called_once_with(
            issue_id="ISS-001-001", force=False, dry_run=False
        )
        assert mock_invoke.call_count == 2
        mock_specify_post.assert_called_once_with(force=False)
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_specific_issue(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_specify_post: MagicMock,
        mock_tasks_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="specify",
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

        mock_specify_pre.assert_called_once_with(
            issue_id="ISS-001-004", force=False, dry_run=False
        )
        mock_specify_post.assert_called_once_with(force=False)
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-004")

    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_issue_progress_reset(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_specify_post: MagicMock,
        mock_tasks_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="specify",
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

        mock_specify_pre.assert_called_once_with(
            issue_id="ISS-001-001", force=False, dry_run=False
        )
        mock_specify_post.assert_called_once_with(force=False)
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

    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_dry_run_no_side_effects(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_specify_post: MagicMock,
        mock_tasks_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="specify",
            next_phase="/deviate-green",
        )
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

        mock_specify_pre.assert_not_called()
        mock_specify_post.assert_not_called()
        mock_tasks_post.assert_not_called()
        mock_invoke.assert_not_called()

    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_recovery_skip_specify(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
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

        assert mock_invoke.call_count == 1
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_agent_failure_aborts(
        self,
        mock_pytest: MagicMock,
        mock_specify_pre: MagicMock,
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
                    side_effect=AgentSubprocessError(
                        "SPECIFY failed: agent exited with code 1", exit_code=1
                    ),
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        _meso_run(issue_id="ISS-001-001")
            assert exc_info.value.code != 0

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE", (
                "Session should remain at initial phase on agent failure"
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

    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._specify_post")
    @patch("deviate.cli.meso._specify_pre")
    @patch("deviate.core.agent.AgentBackend.invoke")
    @patch("deviate.cli.micro._run_pytest")
    def test_meso_force_guard_bypass(
        self,
        mock_pytest: MagicMock,
        mock_invoke: MagicMock,
        mock_specify_pre: MagicMock,
        mock_specify_post: MagicMock,
        mock_tasks_post: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        mock_invoke.return_value = MagicMock(
            status="PASS",
            phase="specify",
            next_phase="/deviate-green",
        )
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

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
                _meso_run(issue_id="ISS-001-002", force=True)

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"

        mock_specify_pre.assert_called_once_with(
            issue_id="ISS-001-002", force=True, dry_run=False
        )
        mock_specify_post.assert_called_once_with(force=True)
        mock_tasks_post.assert_called_once_with(force=True, issue_id="ISS-001-002")


class TestBuildSlimPrompt:
    def test_build_slim_prompt_returns_string(self) -> None:
        contract = {
            "issue_id": "ISS-001-001",
            "issue_title": "Test",
            "epic_slug": "test-epic",
        }
        result = _build_slim_prompt("specify", contract)
        assert isinstance(result, str)
        assert len(result) > 0


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
