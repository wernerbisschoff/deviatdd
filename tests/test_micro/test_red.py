from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "RED phase task",
    status: str = "PENDING",
    execution_mode: str = "TDD",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description,
        status=status,
        execution_mode=execution_mode,
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


class TestRedPre:
    def test_red_pre_emits_contract(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="RED test task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "task_id" in data
            assert "test_command" in data
            assert "lint_command" in data
            assert "spec_dir" in data


class TestRedPost:
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_validates_test_fails(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="1 failed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_failing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            log = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
            )
            assert log.returncode == 0
            assert len(log.stdout.strip()) > 0

    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_rejects_passing_test(self, mock_run_test, tmp_git_repo: Path):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit, got {result.exit_code}: {result.output}"
            )
            assert "RedMustPassError" in result.output

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_accepts_syntax_error_as_fail(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="SyntaxError: invalid syntax"
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_syntax_error.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_syntax_error(:\n    pass\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert result.exit_code == 0
