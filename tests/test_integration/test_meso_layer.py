from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class TestSpecifyPre:
    def test_specify_pre_emits_deprecation(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "pre", "--force"])
            assert result.exit_code == 0, result.output
            assert "DEPRECATED" in result.output


class TestSpecifyPost:
    def test_specify_post_emits_deprecation(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "post"])
            assert result.exit_code == 0, result.output
            assert "DEPRECATED" in result.output


class TestTasksPre:
    def test_tasks_pre_detects_worktree(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(
                current_phase="SPECIFY", active_issue_id="ISS-001-001"
            )
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            bucket_dir = spec_root / "test-tasks"
            bucket_dir.mkdir(parents=True)
            (bucket_dir / "spec.md").write_text("# Spec\n")
            (spec_root / "constitution.md").write_text("# Constitution\n")

            worktree_dir = tmp_git_repo.parent / "test-tasks-wt"
            subprocess.run(
                ["git", "branch", "feat/test-tasks"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "worktree", "add", str(worktree_dir), "feat/test-tasks"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            initial = (
                subprocess.run(
                    ["git", "worktree", "list"],
                    cwd=tmp_git_repo,
                    env=_git_env(),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                .stdout.strip()
                .splitlines()
            )

            result = runner.invoke(cli, ["tasks", "pre"])
            assert result.exit_code == 0, result.output

            post = (
                subprocess.run(
                    ["git", "worktree", "list"],
                    cwd=tmp_git_repo,
                    env=_git_env(),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                .stdout.strip()
                .splitlines()
            )
            assert len(post) == len(initial), "expected no new worktree creation"


class TestPrRun:
    def test_pr_run_creates_pr(self, tmp_git_repo: Path) -> None:
        body_file = tmp_git_repo.parent / "pr-body.md"
        body_file.write_text("PR description\n")

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="TASKS", active_issue_id="ISS-001-001")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")

            record = IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="PR test issue",
                status="BACKLOG",
                source_file="specs/test-pr/issues/iss-001.md",
                timestamp=datetime.now(timezone.utc),
            )
            ledger = spec_root / "issues.jsonl"
            ledger.write_text(record.model_dump_json() + "\n")

            readme = Path("README.md")
            readme.write_text("change")
            subprocess.run(
                ["git", "add", "README.md"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: test change"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            original_run = subprocess.run
            with patch("subprocess.run") as mock_run:

                def side_effect(args, **kwargs):
                    args_str = " ".join(args) if isinstance(args, list) else args
                    if "gh" in args_str and "pr" in args_str:
                        mock = type("Result", (), {})()
                        mock.returncode = 0
                        mock.stdout = "https://github.com/owner/repo/pull/42\n"
                        return mock
                    return original_run(args, **kwargs)

                mock_run.side_effect = side_effect

                result = runner.invoke(
                    cli, ["pr", "run", "--body-file", str(body_file)]
                )
                assert result.exit_code == 0, result.output

                lines = ledger.read_text(encoding="utf-8").strip().splitlines()
                completed = [
                    json.loads(line)
                    for line in lines
                    if json.loads(line).get("issue_id") == "ISS-001-001"
                    and json.loads(line).get("status") == "COMPLETED"
                ]
                assert len(completed) == 1, (
                    "COMPLETED should always be set on PR create"
                )

    def test_pr_run_with_merge_marks_completed(self, tmp_git_repo: Path) -> None:
        body_file = tmp_git_repo.parent / "pr-body.md"
        body_file.write_text("PR description\n")

        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="TASKS", active_issue_id="ISS-001-001")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")

            record = IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="PR test issue",
                status="BACKLOG",
                source_file="specs/test-pr/issues/iss-001.md",
                timestamp=datetime.now(timezone.utc),
            )
            ledger = spec_root / "issues.jsonl"
            ledger.write_text(record.model_dump_json() + "\n")

            readme = Path("README.md")
            readme.write_text("change")
            subprocess.run(
                ["git", "add", "README.md"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: test change"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            original_run = subprocess.run
            with patch("subprocess.run") as mock_run:

                def side_effect(args, **kwargs):
                    args_str = " ".join(args) if isinstance(args, list) else args
                    if "gh" in args_str and "pr" in args_str:
                        mock = type("Result", (), {})()
                        mock.returncode = 0
                        mock.stdout = "https://github.com/owner/repo/pull/42\n"
                        return mock
                    return original_run(args, **kwargs)

                mock_run.side_effect = side_effect

                result = runner.invoke(
                    cli, ["pr", "run", "--body-file", str(body_file), "--merge"]
                )
                assert result.exit_code == 0, result.output
                assert "COMPLETED" in result.output

                lines = ledger.read_text(encoding="utf-8").strip().splitlines()
                completed = [
                    json.loads(line)
                    for line in lines
                    if json.loads(line).get("issue_id") == "ISS-001-001"
                    and json.loads(line).get("status") == "COMPLETED"
                ]
                assert len(completed) >= 1, (
                    "expected COMPLETED event for ISS-001-001 with --merge"
                )
