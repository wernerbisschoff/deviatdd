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
    def test_specify_pre_auto_selects_unblocked_issue(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")

            ledger = spec_root / "issues.jsonl"
            now = datetime.now(timezone.utc)

            iss1 = IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="Oldest unblocked",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-001.md",
                timestamp=now,
            )
            iss2 = IssueRecord(
                issue_id="ISS-001-002",
                type="feature",
                title="Blocked issue",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-002.md",
                timestamp=datetime.now(timezone.utc),
                blocked_by=["ISS-001-003"],
            )
            ledger.write_text(
                iss1.model_dump_json() + "\n" + iss2.model_dump_json() + "\n"
            )
            # Commit ledger so worktree checkout inherits it
            subprocess.run(
                ["git", "add", "specs/issues.jsonl"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "add issues ledger"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["specify", "pre", "--force"])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "SPECIFY"
            assert loaded.active_issue_id == "ISS-001-001"

            wt_output = subprocess.run(
                ["git", "worktree", "list"],
                cwd=tmp_git_repo,
                env=_git_env(),
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            assert len(wt_output.strip().splitlines()) >= 2, (
                "expected at least 2 worktrees (main + newly created)"
            )

            wt_ledger = (
                tmp_git_repo
                / ".worktrees"
                / "feat"
                / "test-epic"
                / "iss-001"
                / "specs"
                / "issues.jsonl"
            )
            assert wt_ledger.exists(), "expected worktree ledger to exist"
            ledger_lines = wt_ledger.read_text(encoding="utf-8").strip().splitlines()
            claims = [
                json.loads(line)
                for line in ledger_lines
                if json.loads(line).get("issue_id") == "ISS-001-001"
                and json.loads(line).get("status") == "SPECIFIED"
            ]
            assert len(claims) >= 1, (
                "expected ISS-001-001 claim (SPECIFIED) in worktree ledger"
            )

    def test_specify_pre_errors_when_no_backlog(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")
            (spec_root / "issues.jsonl").write_text("")

            result = runner.invoke(cli, ["specify", "pre"])
            assert result.exit_code != 0


class TestSpecifyPost:
    def test_specify_post_validates_and_commits(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(
                current_phase="SPECIFY", active_issue_id="ISS-001-001"
            )
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            bucket_dir = spec_root / "test-specify" / "iss-001"
            bucket_dir.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")

            spec_md = bucket_dir / "spec.md"
            spec_md.write_text(
                "# Spec Title\n\n"
                "**Scenario 1: Test scenario**\n\n"
                "- **Given** a precondition\n"
                "- **When** an action occurs\n"
                "- **Then** a result is observed\n"
            )

            ledger = spec_root / "issues.jsonl"
            record = IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="Test",
                status="BACKLOG",
                source_file="specs/test-specify/issues/iss-001.md",
                timestamp=datetime.now(timezone.utc),
            )
            ledger.write_text(record.model_dump_json() + "\n")

            result = runner.invoke(cli, ["specify", "post"])
            assert result.exit_code == 0, result.output

            log = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                cwd=tmp_git_repo,
                env=_git_env(),
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            assert "spec.md" in log or "SPECIFY" in log.upper()

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "TASKS"

    def test_specify_post_rejects_invalid_gherkin(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SPECIFY")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            bucket_dir = spec_root / "test-invalid"
            bucket_dir.mkdir(parents=True)
            (spec_root / "constitution.md").write_text("# Constitution\n")

            spec_md = bucket_dir / "spec.md"
            spec_md.write_text(
                "# Bad Spec\n\n**Scenario 1: Incomplete**\n\n- **Given** only given\n"
            )

            result = runner.invoke(cli, ["specify", "post"])
            assert result.exit_code != 0


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

            with patch("subprocess.run") as mock_run:
                real_run = subprocess.run

                def side_effect(args, **kwargs):
                    args_str = " ".join(args) if isinstance(args, list) else args
                    if "gh" in args_str and "pr" in args_str:
                        mock = type("Result", (), {})()
                        mock.returncode = 0
                        mock.stdout = "https://github.com/owner/repo/pull/42\n"
                        return mock
                    return real_run(args, **kwargs)

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

            with patch("subprocess.run") as mock_run:
                real_run = subprocess.run

                def side_effect(args, **kwargs):
                    args_str = " ".join(args) if isinstance(args, list) else args
                    if "gh" in args_str and "pr" in args_str:
                        mock = type("Result", (), {})()
                        mock.returncode = 0
                        mock.stdout = "https://github.com/owner/repo/pull/42\n"
                        return mock
                    return real_run(args, **kwargs)

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
