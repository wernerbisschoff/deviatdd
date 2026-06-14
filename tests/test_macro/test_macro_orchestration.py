from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _git_env

from deviate.state.config import SessionState


def _setup_macro_workspace(
    tmp_git_repo: Path,
    target_slug: str = "001-test-feature",
    with_explore: bool = True,
    with_design: bool = True,
    with_data_model: bool = True,
    with_prd: bool = False,
    configure_session: str = "IDLE",
    with_bucket_dir: bool = True,
) -> None:
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase=configure_session)
    session.save(dot_dir / "session.json")

    spec_root = tmp_git_repo / "specs"
    spec_root.mkdir(parents=True)
    (spec_root / "constitution.md").write_text(
        "# Constitution\ntest_command = pytest\nlint_command = ruff\n"
    )

    if with_bucket_dir:
        feature_dir = spec_root / target_slug
        feature_dir.mkdir(parents=True)

        if with_explore:
            (feature_dir / "explore.md").write_text(
                "# Explore\n\nProblem: test feature\n\n## Repo Structure\n- src/\n"
            )

        if with_design:
            (feature_dir / "design.md").write_text(
                "# Design\n\n## Architecture\n- Option A\n\n## Trade-offs\nNone\n"
            )

        if with_data_model:
            (feature_dir / "data-model.md").write_text(
                "# Data Model\n\n## Entities\n- Foo\n\n## Relationships\n- Foo has Bar\n"
            )

        if with_prd:
            (feature_dir / "prd.md").write_text(
                "# PRD\n\n## Requirements\nFR-001: do the thing\n\n"
                "## Acceptance Criteria\nGiven X, When Y, Then Z\n"
            )

    (spec_root / "issues.jsonl").write_text("")

    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "setup macro workspace"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )


class TestMacroOrchestration:
    def test_macro_full_pipeline_success(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(tmp_git_repo, target_slug="001-test-feature")

        with (
            patch("deviate.cli.macro._explore_pre", create=True) as mock_explore_pre,
            patch("deviate.cli.macro._explore_post", create=True) as mock_explore_post,
            patch("deviate.cli.macro._research_pre", create=True) as mock_research_pre,
            patch(
                "deviate.cli.macro._research_post", create=True
            ) as mock_research_post,
            patch("deviate.cli.macro._prd_pre", create=True) as mock_prd_pre,
            patch("deviate.cli.macro._prd_post", create=True) as mock_prd_post,
            patch("deviate.cli.macro._shard_pre", create=True) as mock_shard_pre,
            patch("deviate.cli.macro._shard_post", create=True) as mock_shard_post,
            patch("deviate.core.agent.AgentBackend.invoke") as mock_invoke,
        ):
            mock_invoke.return_value = MagicMock(
                status="PASS",
                phase="explore",
                next_phase="/deviate-research",
            )

            with chdir(tmp_git_repo):
                _macro_run(target="001-test-feature")

                loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
                assert loaded.current_phase == "IDLE", (
                    f"Expected IDLE, got {loaded.current_phase}"
                )

        assert mock_explore_pre.call_count == 1
        assert mock_research_pre.call_count == 1
        assert mock_prd_pre.call_count == 1
        assert mock_shard_pre.call_count == 1
        assert mock_invoke.call_count == 4
        assert mock_explore_post.call_count == 1
        assert mock_research_post.call_count == 1
        assert mock_prd_post.call_count == 1
        assert mock_shard_post.call_count == 1

    def test_macro_from_prd_resume(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(
            tmp_git_repo,
            target_slug="001-test-feature",
            with_explore=True,
            with_design=True,
            with_data_model=True,
            configure_session="PRD",
        )

        with (
            patch("deviate.cli.macro._prd_pre", create=True) as mock_prd_pre,
            patch("deviate.cli.macro._prd_post", create=True) as mock_prd_post,
            patch("deviate.cli.macro._shard_pre", create=True) as mock_shard_pre,
            patch("deviate.cli.macro._shard_post", create=True) as mock_shard_post,
            patch("deviate.core.agent.AgentBackend.invoke") as mock_invoke,
        ):
            mock_invoke.return_value = MagicMock(
                status="PASS",
                phase="prd",
                next_phase="/deviate-shard",
            )

            with chdir(tmp_git_repo):
                _macro_run(target="001-test-feature", from_phase="prd")

                loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
                assert loaded.current_phase == "IDLE", (
                    f"Expected IDLE, got {loaded.current_phase}"
                )

        assert mock_invoke.call_count == 2
        mock_prd_pre.assert_called_once()
        mock_prd_post.assert_called_once()
        mock_shard_pre.assert_called_once()
        mock_shard_post.assert_called_once()

    def test_macro_invalid_from_phase(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(tmp_git_repo, target_slug="001-test-feature")

        with chdir(tmp_git_repo):
            with pytest.raises(SystemExit) as exc_info:
                _macro_run(target="001-test-feature", from_phase="invalid_phase")
            assert exc_info.value.code != 0

    def test_macro_bucket_not_found(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(
            tmp_git_repo,
            target_slug="001-test-feature",
            with_bucket_dir=False,
        )

        with chdir(tmp_git_repo):
            with pytest.raises(SystemExit) as exc_info:
                _macro_run(target="nonexistent-slug")
            assert exc_info.value.code != 0

    def test_macro_dry_run_no_artifacts(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(tmp_git_repo, target_slug="001-test-feature")

        with patch("deviate.core.agent.AgentBackend.invoke") as mock_invoke:
            mock_invoke.return_value = MagicMock(
                status="PASS",
                phase="explore",
                next_phase="/deviate-research",
            )

            with chdir(tmp_git_repo):
                _macro_run(target="001-test-feature", dry_run=True)

                loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
                assert loaded.current_phase == "IDLE", (
                    "Dry run should not advance session"
                )

        mock_invoke.assert_not_called()

    def test_macro_upstream_missing_aborts(
        self,
        tmp_git_repo: Path,
    ) -> None:
        try:
            from deviate.cli.macro import _macro_run
        except (ImportError, AttributeError):
            pytest.fail("_macro_run is not implemented yet in deviate.cli.macro")
            return

        _setup_macro_workspace(
            tmp_git_repo,
            target_slug="001-test-feature",
            with_explore=False,
        )

        with (
            patch("deviate.cli.macro._explore_pre", create=True) as mock_explore_pre,
            patch("deviate.cli.macro._explore_post", create=True) as mock_explore_post,
            patch("deviate.core.agent.AgentBackend.invoke") as mock_invoke,
        ):
            mock_invoke.return_value = MagicMock(
                status="PASS",
                phase="explore",
                next_phase="/deviate-research",
            )

            with chdir(tmp_git_repo):
                with pytest.raises(SystemExit) as exc_info:
                    _macro_run(target="001-test-feature")
                assert exc_info.value.code != 0

        mock_explore_pre.assert_called_once()
        mock_invoke.assert_called_once()
        mock_explore_post.assert_called_once()
