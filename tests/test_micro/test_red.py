from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

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
    task_id: str = "550e8400-e29b-41d4-a716-446655440001",
    issue_id: str = "ISS-004",
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
                task_id="550e8400-e29b-41d4-a716-446655440001",
                issue_id="ISS-004",
                description="RED test task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["red", "pre", "--task", "T004"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "task_id" in data
            assert "test_command" in data
            assert "lint_command" in data
            assert "spec_dir" in data


class TestRedPost:
    def test_red_post_validates_test_fails(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
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

    def test_red_post_rejects_passing_test(self, tmp_git_repo: Path):
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

    def test_red_post_rejects_syntax_error(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            test_file = Path("tests") / "test_syntax_error.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_syntax_error(:\n    pass\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert "SyntaxCrashRejected" in result.output
