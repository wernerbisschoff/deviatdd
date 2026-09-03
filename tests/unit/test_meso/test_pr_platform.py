"""Unit tests for the PR/MR platform helpers in `deviate.cli.meso`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.cli.meso import _gitlab_push_options, _pr_title, _resolve_pr_platform


class TestResolvePrPlatform:
    def test_github_remote(self, tmp_path: Path) -> None:
        with patch("deviate.cli.meso.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/owner/repo.git\n"
            assert _resolve_pr_platform(tmp_path) == "github"

    def test_gitlab_remote(self, tmp_path: Path) -> None:
        with patch("deviate.cli.meso.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "git@gitlab.com:owner/repo.git\n"
            assert _resolve_pr_platform(tmp_path) == "gitlab"

    def test_unknown_remote_defaults_to_github(self, tmp_path: Path) -> None:
        with patch("deviate.cli.meso.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://example.com/repo.git\n"
            assert _resolve_pr_platform(tmp_path) == "github"

    def test_override_wins(self, tmp_path: Path) -> None:
        with patch("deviate.cli.meso.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/owner/repo.git\n"
            assert _resolve_pr_platform(tmp_path, "gitlab") == "gitlab"

    def test_no_remote_defaults_to_github(self, tmp_path: Path) -> None:
        with patch(
            "deviate.cli.meso.subprocess.run", side_effect=Exception("no remote")
        ):
            assert _resolve_pr_platform(tmp_path) == "github"


class TestGitlabPushOptions:
    def test_includes_create_target_and_title(self) -> None:
        opts = _gitlab_push_options("feat(1): x", "", "main")
        assert "-o" in opts
        s = " ".join(opts)
        assert "merge_request.create" in s
        assert "merge_request.target=main" in s
        assert "merge_request.title=feat(1): x" in s
        assert "merge_request.description" not in s

    def test_includes_description_when_body_present(self) -> None:
        opts = _gitlab_push_options("title", "body\nline2", "dev")
        s = " ".join(opts)
        assert "merge_request.description=body\nline2" in s


class TestCompoundPrefixTitleStrip:
    @pytest.mark.behavioral
    def test_compound_prefix_strips_to_conventional_form(self) -> None:
        title = _pr_title("ISS-ADH-029", "[FR-029][UI] Fold pruning")
        assert title == "feat(ADH-029): Fold pruning"

    @pytest.mark.behavioral
    def test_spaced_compound_prefix_strips_to_conventional_form(self) -> None:
        title = _pr_title("ISS-ADH-029", "[FR-029] [UI] Fold pruning")
        assert title == "feat(ADH-029): Fold pruning"

    @pytest.mark.behavioral
    def test_empty_body_omits_description_option(self) -> None:
        opts = _gitlab_push_options("feat(ADH-029): Fold pruning", "   ", "main")
        assert " ".join(opts).find("merge_request.description") == -1
