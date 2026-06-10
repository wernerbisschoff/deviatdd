from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "550e8400-e29b-41d4-a716-446655440001",
    issue_id: str = "ISS-004",
    description: str = "JUDGE phase task",
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


class TestJudgePre:
    def test_judge_pre_clean_diff(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            src_file = Path("src") / "deviate" / "impl.py"
            src_file.parent.mkdir(parents=True)
            src_file.write_text("# implementation\n")

            test_file = Path("tests") / "test_impl.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: baseline implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["judge", "pre"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert data.get("verdict") == "COMPLIANCE_PASS", (
                f"Expected COMPLIANCE_PASS, got {data}"
            )

    def test_judge_pre_violation(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            spec_dir = Path("specs") / "004-micro-layer"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / "spec.md"
            spec_file.write_text(
                "# Protected Module\n\nModule: src/deviate/core/protected.py\n"
            )

            src_file = Path("src") / "deviate" / "impl.py"
            src_file.parent.mkdir(parents=True)
            src_file.write_text("# implementation\n")

            test_file = Path("tests") / "test_impl.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: baseline"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            protected = Path("src") / "deviate" / "core" / "protected.py"
            protected.parent.mkdir(parents=True)
            protected.write_text("# protected module — modified\n")

            result = runner.invoke(cli, ["judge", "pre"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert data.get("verdict") == "COMPLIANCE_VIOLATION", (
                f"Expected COMPLIANCE_VIOLATION, got {data}"
            )
            assert "details" in data
