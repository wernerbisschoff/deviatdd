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
    description: str = "GREEN phase task",
    status: str = "RED",
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


class TestGreenPre:
    def test_green_pre_loads_red_task(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="GREEN test task",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_red_task.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            result = runner.invoke(cli, ["green", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "test_file" in data
            assert "implementation_targets" in data


class TestGreenPost:
    @patch("deviate.cli.micro._run_pytest")
    def test_green_post_validates_tests_pass(self, mock_pytest, tmp_git_repo: Path):
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_green_task.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "green_impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# GREEN implementation stub\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: RED test and GREEN implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            test_file.write_text("def test_pass():\n    assert True\n")
            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["green", "post"])

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
    def test_green_post_tamper_detection(self, mock_pytest, tmp_git_repo: Path):
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_tamper.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_original():\n    assert True\n")

            implementation = Path("src") / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# implementation\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: initial RED test"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            test_file.write_text(
                "def test_original():\n    assert True\n\n"
                "def test_tampered():\n    assert 1 == 1\n"
            )

            result = runner.invoke(cli, ["green", "post"])

            assert "TAMPER_DETECTED" in result.output, (
                f"Expected TAMPER_DETECTED in output: {result.output}"
            )

            restored = test_file.read_text()
            assert "test_tampered" not in restored, (
                "Tamper Guard should have restored the original test file"
            )

    @patch("deviate.cli.micro._run_pytest")
    def test_green_post_yellow_handover(self, mock_pytest, tmp_git_repo: Path):
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_yellow.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_placeholder():\n    assert True\n")

            implementation = Path("src") / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# implementation\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: RED test"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["green", "post"])

            assert "GREEN_POST_OK" in result.output, (
                f"Expected GREEN_POST_OK in output: {result.output}"
            )
