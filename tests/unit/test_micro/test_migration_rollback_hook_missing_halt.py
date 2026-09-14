"""GH-240: migration rollback without a recovery hook must hard-stop.

A JUDGE ``revert_green`` that discards migration files and cannot run a
``[rollback]`` hook (or ``test:reset``) must not print
``ROLLBACK_FAILED … proceeding with train feedback`` and must not enter
further TRAIN / GREEN / REFACTOR on the unrestored catalog.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deviate.cli.micro import (
    EnvNotReadyError,
    PhaseFailedError,
    _apply_judge_verdict,
    _is_fatal_missing_revert_green_boundary,
    _run_judge_phase,
    _run_tdd_cycle,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_ID = "TSK-004-01"
_ISSUE_ID = "001-004"
_RATIONALE = "GREEN added currency_symbol without restoring the catalog after rollback"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _rev_parse(repo)


def _seed_migration_workspace(repo: Path) -> tuple[dict, Path, str]:
    """Commit tasks + RED + migration-bearing GREEN. Return task, ledger, red SHA."""
    workspace = (
        repo / "specs" / "001-crypto-withdrawals" / "004-crypto-withdrawal-safety"
    )
    workspace.mkdir(parents=True, exist_ok=True)
    source = "specs/001-crypto-withdrawals/issues/004-crypto-withdrawal-safety.md"
    issue_md = repo / source
    issue_md.parent.mkdir(parents=True, exist_ok=True)
    issue_md.write_text("# crypto withdrawal safety\n", encoding="utf-8")
    (repo / "specs" / "issues.jsonl").write_text(
        '{"issue_id": "' + _ISSUE_ID + '", "source_file": "' + source + '"}\n',
        encoding="utf-8",
    )
    (workspace / "tasks.md").write_text(
        f"- [ ] {_TASK_ID}: recover migration rollback without a hook\n"
        "  - **Test Strategy**: unit\n",
        encoding="utf-8",
    )
    gitignore = repo / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if ".deviate/" not in existing.splitlines():
        gitignore.write_text(existing.rstrip() + "\n.deviate/\n", encoding="utf-8")
    _commit(repo, "chore: seed tasks")

    test_path = repo / "tests" / "unit" / "test_wallet.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("assert False\n", encoding="utf-8")
    red_sha = _commit(repo, f"test({_TASK_ID}): RED phase - failing test")

    impl = repo / "wallet.py"
    impl.write_text("def withdraw():\n    return 1\n", encoding="utf-8")
    mig = repo / "alembic" / "versions" / "001_currency_symbol.py"
    mig.parent.mkdir(parents=True, exist_ok=True)
    mig.write_text("revision = '001'\n", encoding="utf-8")
    _commit(repo, f"feat({_TASK_ID}): GREEN phase - implementation")

    record = TaskRecord(
        id=_TASK_ID,
        issue_id=_ISSUE_ID,
        description="recover migration rollback without a hook",
        status="GREEN",
        execution_mode="TDD",
        test_strategy="unit",
    )
    ledger = workspace / "tasks.jsonl"
    ledger.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(
        current_phase="GREEN",
        active_issue_id=_ISSUE_ID,
        red_commit_sha=red_sha,
    ).save(session_path)
    return json.loads(record.model_dump_json()), ledger, red_sha


def _violation() -> HandoverManifest:
    return HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id=_TASK_ID,
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_green",
        rationale=_RATIONALE,
    )


class TestMigrationRollbackHookMissingHalt:
    """GH-240: missing recovery hook is fatal; do not continue train."""

    def test_hook_missing_is_fatal_for_revert_green(self) -> None:
        err = PhaseFailedError(
            "ROLLBACK_RECOVERY_HOOK_MISSING: migration-bearing "
            "rollback requires a [rollback] recovery hook "
            "(hook='[rollback] recovery hook', boundary=abc, "
            f"task_id={_TASK_ID!r})."
        )
        assert _is_fatal_missing_revert_green_boundary("revert_green", err) is True
        assert _is_fatal_missing_revert_green_boundary("revert_red", err) is True
        failed = PhaseFailedError(
            "ROLLBACK_RECOVERY_HOOK_FAILED: recovery hook failed: boom"
        )
        assert _is_fatal_missing_revert_green_boundary("revert_green", failed) is True

    def test_apply_does_not_continue_train_when_hook_missing(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, red_sha = _seed_migration_workspace(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_before = SessionState.load(session_path)
        head_before = _rev_parse(tmp_git_repo)
        buf = io.StringIO()

        with chdir(tmp_git_repo), pytest.raises(PhaseFailedError) as caught:
            _apply_judge_verdict(
                task,
                ledger,
                session_before,
                session_path,
                Console(file=buf, force_terminal=False, width=200),
                _violation(),
                injected_diff="diff --git a/wallet.py b/wallet.py\n",
            )

        text = str(caught.value)
        output = buf.getvalue()
        assert "ROLLBACK_RECOVERY_HOOK_MISSING" in text, text
        assert "ENV_NOT_READY" in text, text
        assert "[rollback]" in text, text
        assert "proceeding with train feedback" not in output, output
        assert "ROLLBACK_FAILED" not in output, output
        assert not isinstance(caught.value, type(None))
        assert isinstance(caught.value, EnvNotReadyError), type(caught.value)

        session_after = SessionState.load(session_path)
        assert session_after.pending_judge_action != "revert_green", (
            "GH-240: hook-missing must not mark TRAIN revert_green; "
            f"got {session_after.pending_judge_action!r}"
        )
        assert not session_after.train_feedback, (
            "GH-240: hook-missing must not persist train feedback; "
            f"got {session_after.train_feedback!r}"
        )
        log_after = subprocess.run(
            ["git", "log", "--pretty=%s", "-n", "5"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout
        assert "add judge feedback" not in log_after, log_after
        assert session_after.red_commit_sha == red_sha, (
            "GH-236/240: keep the standing RED boundary; "
            f"got {session_after.red_commit_sha!r} expected {red_sha!r}"
        )
        # Git reset may have landed on the RED boundary before the hook
        # refused; do not resume GREEN/REFACTOR from that unrestored catalog.
        assert _rev_parse(tmp_git_repo) in {red_sha, head_before}

    def test_run_judge_phase_surfaces_actionable_env_error(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, _red = _seed_migration_workspace(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._build_auto_prompt", return_value="# judge"),
            patch(
                "deviate.cli.micro._load_skill_content", return_value="# JUDGE skill"
            ),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(_violation(), ""),
            ),
            patch("deviate.cli.micro._run_pytest", return_value=success),
            pytest.raises(PhaseFailedError) as caught,
        ):
            _run_judge_phase(task, ledger, session, session_path, console)

        text = str(caught.value)
        output = buf.getvalue()
        assert "ROLLBACK_RECOVERY_HOOK_MISSING" in text, text
        assert "ENV_NOT_READY" in text, text
        assert "proceeding with train feedback" not in output, output

    def test_tdd_cycle_does_not_enter_green_or_refactor(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, _red = _seed_migration_workspace(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.current_phase = "JUDGE"
        session.save(session_path)

        green_calls = {"n": 0}
        refactor_calls = {"n": 0}
        finish_calls = {"n": 0}

        def _boom_green(*_a, **_k):
            green_calls["n"] += 1
            raise AssertionError("GH-240: GREEN must not run after hook-missing")

        def _boom_refactor(*_a, **_k):
            refactor_calls["n"] += 1
            raise AssertionError("GH-240: REFACTOR must not run after hook-missing")

        def _boom_finish(*_a, **_k):
            finish_calls["n"] += 1
            raise AssertionError(
                "GH-240: _finish_tdd_cycle must not run after hook-missing"
            )

        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        buf = io.StringIO()

        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._build_auto_prompt", return_value="# judge"),
            patch(
                "deviate.cli.micro._load_skill_content", return_value="# JUDGE skill"
            ),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(_violation(), ""),
            ),
            patch("deviate.cli.micro._run_pytest", return_value=success),
            patch("deviate.cli.micro._run_test_cmd", return_value=success),
            patch("deviate.cli.micro._run_format_cmd", return_value=success),
            patch("deviate.cli.micro._run_green_phase", side_effect=_boom_green),
            patch("deviate.cli.micro._run_refactor_phase", side_effect=_boom_refactor),
            patch("deviate.cli.micro._finish_tdd_cycle", side_effect=_boom_finish),
            pytest.raises(PhaseFailedError) as caught,
        ):
            _run_tdd_cycle(
                task,
                ledger,
                Console(file=buf, force_terminal=False, width=200),
                start_phase="JUDGE",
            )

        text = str(caught.value)
        assert "ROLLBACK_RECOVERY_HOOK_MISSING" in text, text
        assert "ENV_NOT_READY" in text, text
        assert green_calls["n"] == 0, green_calls
        assert refactor_calls["n"] == 0, refactor_calls
        assert finish_calls["n"] == 0, finish_calls
        assert "proceeding with train feedback" not in buf.getvalue()
