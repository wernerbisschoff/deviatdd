from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifyPre:
    @patch("deviate.cli.micro._run_pytest")
    def test_specify_pre_invokes_feature_create(
        self, mock_pytest, tmp_git_repo: Path
    ) -> None:
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )

        issue_record = {
            "issue_id": "ISS-001-042",
            "type": "feature",
            "title": "Test feature",
            "status": "BACKLOG",
            "source_file": "specs/test-epic/issues/ISS-001-042.md",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = specs_dir / "issues.jsonl"
        ledger_path.write_text(json.dumps(issue_record) + "\n")

        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["specify", "pre", "--issue", "ISS-001-042", "--dry-run"]
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}"
        assert (tmp_git_repo / "specs" / "test-feature").is_dir(), (
            "Feature workspace should exist"
        )
        assert (tmp_git_repo / ".deviate" / "session.json").exists(), (
            "Session file should exist"
        )
