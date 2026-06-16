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
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "YELLOW phase task",
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


class TestYellowPre:
    def test_yellow_pre_emits_contract(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="GREEN")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="YELLOW test task",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["yellow", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "proposed_changes" in data
            assert "rationale" in data
            assert "test_files" in data


class TestYellowPost:
    def test_yellow_post_accept_amendments(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="YELLOW")
            session.save(dot_dir / "session.json")

            test_file = Path("tests") / "test_failing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            implementation = Path("src") / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# implementation\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "test: RED test and GREEN implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            test_file.write_text(
                "def test_fail():\n    assert False\n\ndef test_new():\n    assert 1 == 1\n"
            )

            result = runner.invoke(cli, ["yellow", "post", "--approved"])

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

    def test_yellow_post_reject_amendments(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="YELLOW")
            session.save(dot_dir / "session.json")

            test_file = Path("tests") / "test_failing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "test: initial test"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            original = test_file.read_text()

            test_file.write_text(
                "def test_fail():\n    assert False\n\ndef test_tampered():\n    assert 1 == 1\n"
            )

            result = runner.invoke(cli, ["yellow", "post", "--rejected"])

            assert "NO_CHANGES_PROPOSED" in result.output or result.exit_code == 0

            restored = test_file.read_text()
            assert restored == original, (
                "Expected test file to be restored to original state"
            )


class TestYellowPostTransitions:
    def test_yellow_post_approved_transitions_to_judge(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="YELLOW")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-04",
                issue_id="ISS-002-005",
                description="YELLOW approved to JUDGE",
                status="YELLOW",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_judge_transition.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# implementation\n")

            subprocess.run(
                ["git", "add", "."],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: state for YELLOW post"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            test_file.write_text(
                "def test_pass():\n    assert True\n\ndef test_extra():\n    assert 1 == 1\n"
            )

            result = runner.invoke(cli, ["yellow", "post", "--approved"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )

            session_data = json.loads(
                (dot_dir / "session.json").read_text(encoding="utf-8")
            )
            assert session_data.get("current_phase") == "JUDGE", (
                f"Expected session to be JUDGE, got {session_data.get('current_phase')}: {result.output}"
            )

            ledger_lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
            statuses = [
                json.loads(line).get("status", "") for line in ledger_lines if line
            ]
            assert "YELLOW_APPROVED" in statuses, (
                f"Expected YELLOW_APPROVED in ledger: {statuses}"
            )

    def test_yellow_post_rejected_transitions_to_green(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="YELLOW")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-04",
                issue_id="ISS-002-005",
                description="YELLOW rejected to GREEN",
                status="YELLOW",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_rejected.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "test: initial test for rejection"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            original = test_file.read_text()

            test_file.write_text(
                "def test_pass():\n    assert True\n\ndef test_tampered():\n    assert 1 == 1\n"
            )

            result = runner.invoke(cli, ["yellow", "post", "--rejected"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )

            session_data = json.loads(
                (dot_dir / "session.json").read_text(encoding="utf-8")
            )
            assert session_data.get("current_phase") == "GREEN", (
                f"Expected session to be GREEN, got {session_data.get('current_phase')}: {result.output}"
            )

            restored = test_file.read_text()
            assert restored == original, (
                "Expected test file to be restored to original state"
            )

            ledger_lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
            statuses = [
                json.loads(line).get("status", "") for line in ledger_lines if line
            ]
            assert "YELLOW_REJECTED" in statuses, (
                f"Expected YELLOW_REJECTED in ledger: {statuses}"
            )
