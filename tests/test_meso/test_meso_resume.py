from __future__ import annotations

from contextlib import chdir
from unittest.mock import MagicMock, patch

import pytest
import typer

from deviate.cli.meso import _meso_run
from tests.test_meso.test_meso_orchestration import _setup_minimal_workspace


VALID_PLAN = """# Plan

## Acceptance Contract

**Scenario AC-PLAN-001: Complete the meso preparation**
**Source Outline**: `AO-001`
**Upstream Traceability**: `US-001-01`, `FR-001-READY`, `AC-001-READY-01`
**Current-Code Evidence**: `src/example.py:run`
**Given**: A claimed issue is available.
**When**: The meso pipeline prepares the issue.
**Then**: The task queue is ready for Micro.
"""


class TestMesoIdempotentResume:
    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._invoke_agent_phase")
    def test_valid_plan_and_tasks_skip_both_phases(
        self,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_minimal_workspace(tmp_git_repo, seed_plan=True, seed_tasks=True)
        (tmp_git_repo / "specs/test-epic/iss-001/plan.md").write_text(VALID_PLAN)

        with chdir(tmp_git_repo):
            result = _meso_run(issue_id="ISS-001-001", no_setup=True)

        assert result == str(tmp_git_repo.resolve())
        mock_invoke.assert_not_called()
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_not_called()
        assert "MESO_ALREADY_COMPLETE" in capsys.readouterr().out

    @patch("deviate.cli.meso._plan_post")
    @patch("deviate.cli.meso._tasks_post")
    @patch("deviate.cli.meso._invoke_agent_phase")
    def test_valid_plan_without_tasks_resumes_at_tasks(
        self,
        mock_invoke: MagicMock,
        mock_tasks_post: MagicMock,
        mock_plan_post: MagicMock,
        tmp_git_repo,
    ) -> None:
        _setup_minimal_workspace(tmp_git_repo, seed_plan=True, seed_tasks=False)
        (tmp_git_repo / "specs/test-epic/iss-001/plan.md").write_text(VALID_PLAN)
        tasks_path = tmp_git_repo / "specs/test-epic/iss-001/tasks.md"

        def write_tasks(phase: str, _contract: dict, **_kwargs: object) -> None:
            assert phase == "tasks"
            tasks_path.write_text("# Tasks\n\n- [ ] TSK-001-01 smoke\n")

        mock_invoke.side_effect = write_tasks

        with chdir(tmp_git_repo):
            _meso_run(issue_id="ISS-001-001", no_setup=True)

        assert mock_invoke.call_count == 1
        assert mock_invoke.call_args.args[0] == "tasks"
        mock_plan_post.assert_not_called()
        mock_tasks_post.assert_called_once_with(force=False, issue_id="ISS-001-001")

    @patch("deviate.cli.meso._invoke_agent_phase")
    def test_invalid_existing_plan_stops_without_overwrite(
        self,
        mock_invoke: MagicMock,
        tmp_git_repo,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_minimal_workspace(tmp_git_repo, seed_plan=False, seed_tasks=False)
        plan_path = tmp_git_repo / "specs/test-epic/iss-001/plan.md"
        original = "# Plan\n\nThis plan has no acceptance contract.\n"
        plan_path.write_text(original)

        with chdir(tmp_git_repo):
            with pytest.raises(typer.Exit):
                _meso_run(issue_id="ISS-001-001", no_setup=True)

        assert plan_path.read_text() == original
        mock_invoke.assert_not_called()
        assert "MESO_PLAN_INVALID" in capsys.readouterr().out

    @patch("deviate.cli.meso._invoke_agent_phase")
    def test_empty_existing_tasks_stops_without_overwrite(
        self,
        mock_invoke: MagicMock,
        tmp_git_repo,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_minimal_workspace(tmp_git_repo, seed_plan=True, seed_tasks=False)
        (tmp_git_repo / "specs/test-epic/iss-001/plan.md").write_text(VALID_PLAN)
        tasks_path = tmp_git_repo / "specs/test-epic/iss-001/tasks.md"
        tasks_path.write_text("\n")

        with chdir(tmp_git_repo):
            with pytest.raises(typer.Exit):
                _meso_run(issue_id="ISS-001-001", no_setup=True)

        assert tasks_path.read_text() == "\n"
        mock_invoke.assert_not_called()
        assert "MESO_TASKS_INVALID" in capsys.readouterr().out
