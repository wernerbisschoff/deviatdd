"""Parity tests for unified RED no-failing-test adjudication (TSK-001-09)."""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import _run_red_phase
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    status: str = "PENDING",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description="RED phase task",
        status=status,
        execution_mode="TDD",
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        ledger_path.open("a", encoding="utf-8").write(r.model_dump_json() + "\n")


def _ledger_rows(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    return [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestManualRedPostSharedHelper:
    def test_zero_failing_routes_through_shared_helper(self, tmp_git_repo: Path):
        passing = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._run_test_cmd", return_value=passing),
            patch(
                "deviate.cli.micro._adjudicate_red_no_failing_test",
                wraps=__import__(
                    "deviate.cli.micro", fromlist=["_adjudicate_red_no_failing_test"]
                )._adjudicate_red_no_failing_test,
            ) as spy,
        ):
            result = runner.invoke(cli, ["red", "post"])
            assert result.exit_code == 1
            assert "RedMustPassError" in result.output
            assert spy.call_count == 1
            assert spy.call_args.kwargs.get("dry_run") is True

    def test_guard_rejection_writes_no_ledger_row(self, tmp_git_repo: Path):
        from tests.conftest import _git_env as isolation_git_env

        passing = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True, exist_ok=True)
            session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(
                ledger_path,
                _make_task_record(status="PENDING"),
            )
            rows_before = _ledger_rows(ledger_path)
            head_before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                env=isolation_git_env(),
            ).stdout.strip()
            with patch("deviate.cli.micro._run_test_cmd", return_value=passing):
                result = runner.invoke(cli, ["red", "post"])
            assert result.exit_code == 1
            assert _ledger_rows(ledger_path) == rows_before
            head_after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                env=isolation_git_env(),
            ).stdout.strip()
            assert head_after == head_before


class TestAutoRedPhaseSharedHelper:
    def test_zero_failing_routes_through_shared_helper(self, tmp_path: Path):
        """Reconciled with 005-003: the kernel owns the RedMustPassError guard
        through the shared helper (dry_run), while the auto runner keeps
        the non-blocking advisory checkpoint (no JUDGE route)."""
        from deviate.cli.micro import RedHandoffAdvisory

        task = {
            "id": "TSK-004-01",
            "issue_id": "ISS-001-004",
            "description": "RED phase task",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState(current_phase="IDLE")
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id="TSK-004-01")
        passing = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with (
            chdir(tmp_path),
            patch("deviate.cli.micro._red_pre_kernel", return_value=None),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._build_auto_prompt", return_value="prompt"),
            patch("deviate.cli.micro._worktree_status_paths", return_value=[]),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(manifest, ""),
            ),
            patch("deviate.cli.micro._run_test_cmd", return_value=passing),
            patch("deviate.cli.micro._run_pytest", return_value=passing),
            patch("deviate.cli.micro._run_format_cmd", return_value=passing),
            patch("deviate.cli.micro.append_task_transition"),
            patch("deviate.cli.micro._commit_phase", return_value=True),
            patch("deviate.cli.micro._verify_clean_worktree"),
            patch(
                "deviate.cli.micro._adjudicate_red_no_failing_test",
                wraps=__import__(
                    "deviate.cli.micro", fromlist=["_adjudicate_red_no_failing_test"]
                )._adjudicate_red_no_failing_test,
            ) as spy,
        ):
            out = _run_red_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )
            assert spy.call_count >= 1
            assert all(c.kwargs.get("dry_run") is True for c in spy.call_args_list)
            assert isinstance(out[1], RedHandoffAdvisory)
            assert out[1].passes is True
