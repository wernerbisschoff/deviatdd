"""Lifecycle contract for the micro TDD loop.

Pins the rewrite spec from the outside: ledger in, CLI, ledger out.
Refactors must keep these green. Agent + test-runner seams are mocked
(never real pytest/agent binaries); real git passes through via the
autouse ``mock_micro_subprocess`` fixture in ``conftest.py``.
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _ok(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )


def _fail(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 failed", stderr=""
    )


def _manifest_ok(*args, **kwargs):
    return HandoverManifest(
        phase=kwargs.get("phase", "RED"),
        status="SUCCESS",
        task_id=kwargs.get("task_id", "TSK-004-01"),
    ), ""


def _make_task(
    task_id="TSK-004-01", issue_id="ISS-001-007", status="PENDING"
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=f"Golden task {task_id}",
        status=status,
        execution_mode="TDD",
    )


def _write_ledger(path: Path, *records: TaskRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(r.model_dump_json() + "\n")


def _ledger_statuses(ledger: Path) -> list[str]:
    import json

    return [
        json.loads(line)["status"]
        for line in ledger.read_text().splitlines()
        if line.strip()
    ]


def _setup_repo(repo: Path, task: TaskRecord, issue_id: str) -> Path:
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "test_seed_failing.py").write_text(
        "def test_seed():\n    assert False\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: seed"], cwd=repo, env=_git_env(), check=True
    )
    dot_dir = repo / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE").save(dot_dir / "session.json")
    ledger = repo / "specs" / "007-macro-meso" / "tasks.jsonl"
    _write_ledger(ledger, task)
    return ledger


class TestGoldenLifecycle:
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_manifest_ok)
    def test_happy_path_reaches_completed(
        self,
        m_agent,
        m_run,
        m_find,
        m_commit,
        m_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """GOLDEN 1: PENDING TDD task runs RED(fail)->GREEN(pass)->JUDGE->COMPLETED."""
        task = _make_task()
        m_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            ledger = _setup_repo(tmp_git_repo, task, task.issue_id)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            result = runner.invoke(cli, ["micro", "run", task.id])
            assert result.exit_code == 0, result.output
            assert "COMPLETED" in result.output, result.output
            assert "COMPLETED" in _ledger_statuses(ledger)

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._invoke_agent", side_effect=_manifest_ok)
    @patch("deviate.cli.micro._run_test_cmd", side_effect=_ok)
    def test_no_pending_tasks_when_ledger_drained(
        self, m_run, m_agent, m_commit, m_verify, tmp_git_repo: Path, approve_gate2
    ):
        """GOLDEN 2: all-COMPLETED ledger reports NO_PENDING_TASKS, exit 0, no agent call."""
        task = _make_task(status="COMPLETED")
        with chdir(tmp_git_repo):
            _setup_repo(tmp_git_repo, task, task.issue_id)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            result = runner.invoke(cli, ["micro", "run", "--all"])
            assert result.exit_code == 0, result.output
            assert "No PENDING tasks found" in result.output, result.output
            m_agent.assert_not_called()

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_manifest_ok)
    def test_green_gate_blocks_completed_on_failing_tests(
        self,
        m_agent,
        m_run,
        m_find,
        m_commit,
        m_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """GOLDEN 3: RED fails then GREEN still fails -> never mints COMPLETED."""
        task = _make_task()
        m_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            ledger = _setup_repo(tmp_git_repo, task, task.issue_id)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            result = runner.invoke(cli, ["micro", "run", task.id])
            assert "COMPLETED" not in _ledger_statuses(ledger), result.output

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_manifest_ok)
    def test_completed_task_is_idempotent(
        self,
        m_agent,
        m_run,
        m_find,
        m_commit,
        m_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """GOLDEN 4: re-running a COMPLETED task is a no-op (no duplicate COMPLETED row)."""
        task = _make_task(status="COMPLETED")
        m_run.side_effect = _ok
        with chdir(tmp_git_repo):
            ledger = _setup_repo(tmp_git_repo, task, task.issue_id)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            before = _ledger_statuses(ledger).count("COMPLETED")
            result = runner.invoke(cli, ["micro", "run", task.id])
            assert result.exit_code == 0, result.output
            assert _ledger_statuses(ledger).count("COMPLETED") == before, result.output
