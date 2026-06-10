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
    issue_id: str = "ISS-004",
    description: str = "REFACTOR phase task",
    status: str = "GREEN",
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


class TestRefactorPre:
    def test_refactor_pre_emits_contract(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="GREEN")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-004",
                description="REFACTOR test task",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["refactor", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "files_to_refactor" in data


class TestRefactorPost:
    @patch("deviate.cli.micro._run_pytest")
    def test_refactor_post_test_invariance(self, mock_pytest, tmp_git_repo: Path):
        mock_pytest.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="REFACTOR", active_issue_id="ISS-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-004",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
            )

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: implementation with passing tests"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hi, {name}!'  # refactored\n"
            )

            result = runner.invoke(cli, ["refactor", "post"])

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

    @patch("deviate.cli.micro._run_pytest")
    def test_refactor_post_regression_rollback(self, mock_pytest, tmp_git_repo: Path):
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="REFACTOR", active_issue_id="ISS-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-004",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
            )

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: implementation with passing tests"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            implementation.write_text(
                "def greet(name: str) -> str:\n    return 42  # breaks type contract\n"
            )

            result = runner.invoke(cli, ["refactor", "post"])

            assert "RefactorRegressionError" in result.output, (
                f"Expected RefactorRegressionError in output: {result.output}"
            )

            restored = implementation.read_text()
            assert "42" not in restored, (
                "Expected implementation to be restored after regression"
            )
