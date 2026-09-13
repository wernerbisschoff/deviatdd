"""GH-231: COMPLETED tasks.jsonl rows must be committed.

Two durable-ledger holes left the worktree dirty after a successful run:

1. EXECUTE → JUDGE ``COMPLIANCE_PASS`` ``skip_refactor`` → COMPLETE writes
   the COMPLETED row *after* the EXECUTE implementation commit, then
   returns without a follow-up ledger commit.
2. Verification_Batch / CHECKPOINT COMPLETE with no implementation diff
   never has a phase commit to piggyback on, so CHECKPOINT_STARTED +
   COMPLETED stay untracked or unstaged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from tests.conftest import _git_env


_ISSUE_ID = "ISS-231-01"
_EXECUTE_TASK_ID = "TSK-231-03"
_VERIFY_TASK_ID = "TSK-231-04"


def _porcelain(root: Path, *paths: Path) -> str:
    rels = [p.relative_to(root).as_posix() for p in paths]
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *rels],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    return result.stdout.strip()


def _commit_names(root: Path, rev: str) -> list[str]:
    result = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", rev],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _ledger_statuses(ledger: Path) -> list[str]:
    return [
        json.loads(line)["status"]
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _seed_issue(root: Path) -> Path:
    issue_dir = root / "specs" / "231-completed-ledger" / "001-durable-rows"
    issue_dir.mkdir(parents=True, exist_ok=True)
    spec = issue_dir / "001-durable-rows.md"
    spec.write_text("# GH-231 durable ledger\n\n## Acceptance\n", encoding="utf-8")
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": _ISSUE_ID,
                "source_file": (
                    "specs/231-completed-ledger/001-durable-rows/001-durable-rows.md"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return issue_dir


def _commit(root: Path, message: str, *paths: Path) -> None:
    rels = [p.relative_to(root).as_posix() for p in paths]
    subprocess.run(
        ["git", "add", "--", *rels],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        env=_git_env(),
        check=True,
        capture_output=True,
    )


class TestExecuteJudgeSkipRefactorCommitsLedger:
    """(1) JUDGE COMPLIANCE_PASS skip_refactor leaves ledger committed."""

    @pytest.mark.behavioral
    def test_skip_refactor_commits_completed_row(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli.micro import _run_execute_phase

        root = tmp_git_repo
        monkeypatch.chdir(root)
        issue_dir = _seed_issue(root)
        ledger = issue_dir / "tasks.jsonl"
        task = {
            "id": _EXECUTE_TASK_ID,
            "issue_id": _ISSUE_ID,
            "description": "Fall back unknown slugs to 404",
            "status": "PENDING",
            "execution_mode": "DIRECT",
        }
        ledger.write_text(json.dumps(task) + "\n", encoding="utf-8")
        _commit(root, "chore: seed issue + pending ledger", root / "specs")

        impl = root / "impl.py"
        impl.write_text("VALUE = 1\n", encoding="utf-8")

        session_path = root / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        SessionState(active_issue_id=_ISSUE_ID).save(session_path)

        execute_manifest = HandoverManifest(
            phase="EXECUTE",
            status="SUCCESS",
            task_id=_EXECUTE_TASK_ID,
            files=["impl.py"],
        )
        judge_manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_PASS",
            next_action="skip_refactor",
            task_id=_EXECUTE_TASK_ID,
        )

        def _invoke(prompt: str, *args: object, **kwargs: object):
            if kwargs.get("phase") == "JUDGE":
                return judge_manifest, ""
            return execute_manifest, ""

        with (
            patch("deviate.cli.micro._invoke_agent", side_effect=_invoke),
            patch("deviate.cli.micro._build_auto_prompt", return_value="prompt"),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        ):
            _run_execute_phase(task, ledger, Console(quiet=True))

        assert "COMPLETED" in _ledger_statuses(ledger), (
            "GH-231: skip_refactor must still mark the task COMPLETED"
        )
        dirty = _porcelain(root, ledger)
        assert dirty == "", (
            "GH-231: COMPLETED ledger row must be committed after "
            f"EXECUTE→JUDGE skip_refactor; porcelain={dirty!r}"
        )
        head_files = _commit_names(root, "HEAD")
        ledger_rel = ledger.relative_to(root).as_posix()
        impl_rel = impl.relative_to(root).as_posix()
        assert ledger_rel in head_files, (
            f"GH-231: HEAD must include the COMPLETED ledger; files={head_files!r}"
        )
        parent_files = _commit_names(root, "HEAD~1")
        assert impl_rel in parent_files, (
            "GH-231: preserve the EXECUTE implementation commit; "
            f"parent files={parent_files!r}"
        )
        assert ledger_rel not in parent_files, (
            "GH-231: EXECUTE commit stays implementation-only; "
            f"parent files={parent_files!r}"
        )


class TestVerifyCompleteCommitsLedgerOnly:
    """(2) VERIFY/COMPLETE with ledger-only changes commits the ledger."""

    @pytest.mark.behavioral
    def test_checkpoint_pass_with_no_file_changes_commits_ledger(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro as micro_mod

        root = tmp_git_repo
        monkeypatch.chdir(root)
        issue_dir = _seed_issue(root)
        ledger = issue_dir / "tasks.jsonl"
        task = {
            "id": _VERIFY_TASK_ID,
            "issue_id": _ISSUE_ID,
            "description": "[VERIFY] Verify all guides build and checks pass",
            "status": "PENDING",
            "execution_mode": "IMMEDIATE",
            "task_type": "Verification_Batch",
        }
        ledger.write_text(json.dumps(task) + "\n", encoding="utf-8")
        _commit(root, "chore: seed pending verify ledger", root / "specs")

        manifest = HandoverManifest(
            phase="CHECKPOINT",
            status="PASS",
            results=[{"check": "mise unit", "ok": True}],
            declared_commands=["mise unit"],
            command_reports=[{"command": "mise unit", "exit_code": 0}],
            declared_criteria=["AC-PLAN-001"],
            criterion_coverage=["AC-PLAN-001"],
            evidence=[
                {
                    "ac": "verification",
                    "test_path": "tests/",
                    "test_quote": "1 passed",
                }
            ],
        )
        with patch.object(micro_mod.AgentBackend, "invoke", return_value=manifest):
            micro_mod._run_checkpoint_phase(task, ledger, Console(quiet=True))

        assert _ledger_statuses(ledger)[-2:] == ["CHECKPOINT_STARTED", "COMPLETED"], (
            "GH-231: VERIFY must still record CHECKPOINT_STARTED then COMPLETED"
        )
        dirty = _porcelain(root, ledger)
        assert dirty == "", (
            "GH-231: VERIFY/COMPLETE with no file changes must commit "
            f"the ledger; porcelain={dirty!r}"
        )
        head_files = _commit_names(root, "HEAD")
        ledger_rel = ledger.relative_to(root).as_posix()
        assert head_files == [ledger_rel], (
            f"GH-231: VERIFY commit must be ledger-only; HEAD files={head_files!r}"
        )
        shown = subprocess.run(
            ["git", "show", f"HEAD:{ledger_rel}"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout
        assert "COMPLETED" in shown
        assert "CHECKPOINT_STARTED" in shown
