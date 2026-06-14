from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deviate.core.agent import (
    AiderBackend,
    AgentBinaryNotFoundError,
    ConstitutionMissingError,
    HandoverManifest,
)
from deviate.state.config import AgentConfig, DeviateConfig


SAMPLE_SUCCESS = """\
Aider v0.75.0
Model: claude-sonnet-4-20250514
Applied edit to src/deviate/core/micro.py.
✓ All tests passed!
"""

SAMPLE_FAILURE = """\
Aider v0.75.0
Model: claude-sonnet-4-20250514
Applied edit to src/deviate/core/micro.py.
Tests: 1 failed
FAILED test_micro.py::test_something - AssertionError: assert False
"""


class TestAiderBackendIntegration:
    def test_aider_backend_integration_invoke(self, tmp_git_repo: Path):
        repo = tmp_git_repo
        (repo / "specs").mkdir(parents=True, exist_ok=True)
        (repo / "specs" / "constitution.md").write_text("# Constitution")
        (repo / "CLAUDE.md").write_text("# CLAUDE")

        aider_result = MagicMock(spec=subprocess.CompletedProcess)
        aider_result.returncode = 0
        aider_result.stdout = SAMPLE_SUCCESS
        aider_result.stderr = ""

        guard_result = MagicMock(spec=subprocess.CompletedProcess)
        guard_result.returncode = 0
        guard_result.stdout = "1 passed"
        guard_result.stderr = ""

        with (
            chdir(repo),
            patch(
                "subprocess.run", side_effect=[aider_result, guard_result]
            ) as mock_run,
        ):
            config = DeviateConfig(agent=AgentConfig(backend="aider"))
            backend = AiderBackend(config=config.agent)
            manifest = backend.invoke("test prompt")

        assert isinstance(manifest, HandoverManifest)
        assert manifest.status == "PASS"
        assert manifest.phase == "aider"
        assert manifest.verification_result == "PASS"
        assert "src/deviate/core/micro.py" in manifest.files_touched

        first_call_args = mock_run.call_args_list[0][0][0]
        assert first_call_args[0] == "aider"
        assert "--message" in first_call_args
        assert "--yes" in first_call_args
        assert "--no-auto-commits" in first_call_args
        assert "--no-suggest-shell-commands" in first_call_args
        msg_idx = first_call_args.index("--message")
        assert first_call_args[msg_idx + 1] == "test prompt"

        second_call_args = mock_run.call_args_list[1][0][0]
        assert second_call_args == ["mise", "run", "test"]

    def test_aider_backend_integration_post_guard_catches_failure(
        self, tmp_git_repo: Path
    ):
        repo = tmp_git_repo
        (repo / "specs").mkdir(parents=True, exist_ok=True)
        (repo / "specs" / "constitution.md").write_text("# Constitution")
        (repo / "CLAUDE.md").write_text("# CLAUDE")

        aider_result = MagicMock(spec=subprocess.CompletedProcess)
        aider_result.returncode = 0
        aider_result.stdout = SAMPLE_SUCCESS
        aider_result.stderr = ""

        failed_guard = MagicMock(spec=subprocess.CompletedProcess)
        failed_guard.returncode = 1
        failed_guard.stdout = "1 failed"
        failed_guard.stderr = "Tests failed"

        with (
            chdir(repo),
            patch(
                "subprocess.run", side_effect=[aider_result, failed_guard]
            ) as mock_run,
        ):
            config = DeviateConfig(agent=AgentConfig(backend="aider"))
            backend = AiderBackend(config=config.agent)
            manifest = backend.invoke("test prompt")

        assert manifest.status == "FAIL"
        assert mock_run.call_count == 2
        mise_call_args = mock_run.call_args_list[1][0][0]
        assert mise_call_args == ["mise", "run", "test"]

    def test_aider_backend_integration_not_found(self, tmp_git_repo: Path):
        repo = tmp_git_repo
        (repo / "specs").mkdir(parents=True, exist_ok=True)
        (repo / "specs" / "constitution.md").write_text("# Constitution")

        with (
            chdir(repo),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            config = DeviateConfig(agent=AgentConfig(backend="aider"))
            backend = AiderBackend(config=config.agent)
            with pytest.raises(AgentBinaryNotFoundError) as exc_info:
                backend.invoke("test prompt")

        assert "aider" in str(exc_info.value).lower()

    def test_aider_backend_integration_constitution_missing(self, tmp_git_repo: Path):
        repo = tmp_git_repo
        (repo / "specs").mkdir(parents=True, exist_ok=True)

        with chdir(repo):
            config = DeviateConfig(agent=AgentConfig(backend="aider"))
            backend = AiderBackend(config=config.agent)
            with pytest.raises(ConstitutionMissingError) as exc_info:
                backend.invoke("test prompt")

        assert "constitution" in str(exc_info.value).lower()
