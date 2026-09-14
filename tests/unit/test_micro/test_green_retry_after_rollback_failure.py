"""GH-236: GREEN retry after rollback recovery failure keeps the RED boundary.

When JUDGE ``revert_green`` cannot finish recovery (missing migration
hook, or any non-fatal ``ROLLBACK_FAILED``), the runner still appends
train feedback and retries GREEN. That path must not stamp
``session.red_commit_sha`` onto a docs-feedback commit that sits on
GREEN, and GREEN entry must recover the standing RED-phase SHA instead
of raising ``GREEN_ENTRY_REFUSED`` while printing that SHA.
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
    PhaseFailedError,
    _apply_judge_verdict,
    _is_red_phase_failing_test_sha,
    _maybe_advance_red_sha_past_feedback,
    _run_green_phase,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_ID = "TSK-004-11"
_ISSUE_ID = "001-004"
_RATIONALE = "implementation misses the reserve lock"


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


def _empty_commit(repo: Path, message: str) -> str:
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _rev_parse(repo)


def _seed_workspace(
    repo: Path,
    *,
    with_migration: bool = False,
    feedback_on_green: bool = False,
) -> tuple[dict, Path, str, str]:
    """Commit tasks + RED + GREEN. Return task, ledger, red SHA, green SHA."""
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
        f"- [ ] {_TASK_ID}: keep RED boundary after rollback failure\n"
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
    if with_migration:
        mig = repo / "alembic" / "versions" / "001_green.py"
        mig.parent.mkdir(parents=True, exist_ok=True)
        mig.write_text("revision = '001'\n", encoding="utf-8")
    green_sha = _commit(repo, f"feat({_TASK_ID}): GREEN phase - implementation")
    if feedback_on_green:
        _empty_commit(repo, f"docs({_TASK_ID}): add judge feedback for retry")

    record = TaskRecord(
        id=_TASK_ID,
        issue_id=_ISSUE_ID,
        description="keep RED boundary after rollback failure",
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
    return json.loads(record.model_dump_json()), ledger, red_sha, green_sha


def _violation() -> HandoverManifest:
    return HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id=_TASK_ID,
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_green",
        rationale=_RATIONALE,
    )


def _apply(repo: Path, task: dict, ledger: Path) -> tuple[SessionState, str]:
    session_path = repo / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    buf = io.StringIO()
    with chdir(repo):
        result = _apply_judge_verdict(
            task,
            ledger,
            session,
            session_path,
            Console(file=buf, force_terminal=False, width=200),
            _violation(),
            injected_diff="diff --git a/wallet.py b/wallet.py\n",
        )
    return result, buf.getvalue()


def _drive_green(
    root: Path,
    session: SessionState,
    session_path: Path,
    ledger_path: Path,
    task: dict,
) -> tuple[int, PhaseFailedError | None]:
    success = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    invoke_count = {"n": 0}

    def _capture_invoke(*args, **kwargs):
        invoke_count["n"] += 1
        return (
            HandoverManifest(phase="GREEN", status="SUCCESS", task_id=task["id"]),
            "",
        )

    error: PhaseFailedError | None = None
    with (
        chdir(root),
        patch("deviate.cli.micro._phase_already_done", return_value=False),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._invoke_agent", side_effect=_capture_invoke),
        patch(
            "deviate.cli.micro._run_pytest",
            return_value=subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="", stderr=""
            ),
        ),
        patch("deviate.cli.micro._run_test_cmd", return_value=success),
        patch("deviate.cli.micro._run_format_cmd", return_value=success),
        patch("deviate.cli.micro.append_task_transition"),
        patch("deviate.cli.micro._commit_phase", return_value=True),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        try:
            _run_green_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )
        except PhaseFailedError as exc:
            error = exc
    return invoke_count["n"], error


class TestGreenRetryAfterRollbackFailure:
    """GH-236: rollback-failure TRAIN must keep a usable RED boundary."""

    def test_hook_missing_keeps_usable_red_boundary_for_green_retry(
        self, tmp_git_repo: Path
    ) -> None:
        """Real migration revert with no hook still retries GREEN on RED."""
        task, ledger, red_sha, _green = _seed_workspace(
            tmp_git_repo, with_migration=True
        )
        session, output = _apply(tmp_git_repo, task, ledger)

        assert "ROLLBACK_FAILED" in output, output
        assert "ROLLBACK_RECOVERY_HOOK_MISSING" in output, output
        assert _is_red_phase_failing_test_sha(tmp_git_repo, session.red_commit_sha), (
            "GH-236: after hook-missing rollback the session must still "
            f"hold a usable RED boundary; got {session.red_commit_sha!r}"
        )
        assert session.pending_judge_action == "revert_green"
        session_path = tmp_git_repo / ".deviate" / "session.json"
        invoke_count, error = _drive_green(
            tmp_git_repo, session, session_path, ledger, task
        )
        assert error is None, (
            "GH-236: GREEN retry after ROLLBACK_RECOVERY_HOOK_MISSING must "
            f"not refuse a standing RED commit; error={error!r} "
            f"red_commit_sha={session.red_commit_sha!r} red_sha={red_sha!r}"
        )
        assert invoke_count == 1, (
            f"GH-236: GREEN agent must run after rollback-failure TRAIN; "
            f"invoke_count={invoke_count}"
        )
        assert "GREEN_ENTRY_REFUSED" not in str(error or "")

    def test_rollback_failed_before_reset_does_not_stamp_feedback_on_green(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Feedback committed on GREEN must not become the RED boundary."""
        import deviate.cli.micro as micro

        task, ledger, red_sha, green_sha = _seed_workspace(tmp_git_repo)
        monkeypatch.setattr(
            micro,
            "_execute_rollback",
            lambda *a, **k: (_ for _ in ()).throw(
                PhaseFailedError(
                    "ROLLBACK_RECOVERY_HOOK_MISSING: migration-bearing "
                    "rollback requires a [rollback] recovery hook "
                    f"(hook='[rollback] recovery hook', boundary={red_sha}, "
                    f"task_id={_TASK_ID!r})."
                )
            ),
        )
        session, output = _apply(tmp_git_repo, task, ledger)

        assert "ROLLBACK_FAILED" in output, output
        assert _is_red_phase_failing_test_sha(tmp_git_repo, session.red_commit_sha), (
            "GH-236: rollback-failure must not stamp red_commit_sha onto a "
            f"docs-feedback commit that sits on GREEN; "
            f"got {session.red_commit_sha!r} red={red_sha!r} green={green_sha!r}"
        )
        session_path = tmp_git_repo / ".deviate" / "session.json"
        invoke_count, error = _drive_green(
            tmp_git_repo, session, session_path, ledger, task
        )
        assert error is None, (
            "GH-236: GREEN retry must use the standing RED SHA after a "
            f"failed rollback that left HEAD on GREEN; error={error!r}"
        )
        assert invoke_count == 1
        assert "GREEN_ENTRY_REFUSED" not in str(error or "")

    def test_green_recovers_feedback_on_green_sha_to_red_boundary(
        self, tmp_git_repo: Path
    ) -> None:
        """Corrupted session SHA that prints in GREEN_ENTRY_REFUSED is recovered."""
        task, ledger, red_sha, _green = _seed_workspace(
            tmp_git_repo, feedback_on_green=True
        )
        red_row = TaskRecord.model_validate(task)
        red_row.status = "RED"
        ledger.open("a", encoding="utf-8").write(red_row.model_dump_json() + "\n")
        feedback_sha = _rev_parse(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.red_commit_sha = feedback_sha
        session.current_phase = "GREEN"
        session.train_feedback = _RATIONALE
        session.pending_judge_action = "revert_green"
        session.save(session_path)

        assert not _is_red_phase_failing_test_sha(tmp_git_repo, feedback_sha), (
            "precondition: feedback-on-GREEN is not a GREEN-entry boundary"
        )
        invoke_count, error = _drive_green(
            tmp_git_repo, session, session_path, ledger, task
        )
        persisted = SessionState.load(session_path)
        assert error is None, (
            "GH-236: GREEN must recover the RED-phase SHA instead of "
            f"GREEN_ENTRY_REFUSED (red_commit_sha={feedback_sha}); "
            f"error={error!r}"
        )
        assert invoke_count == 1
        assert _is_red_phase_failing_test_sha(tmp_git_repo, persisted.red_commit_sha), (
            "GH-236: recovered red_commit_sha must be a usable RED boundary; "
            f"got {persisted.red_commit_sha!r}"
        )
        assert persisted.red_commit_sha == red_sha, (
            f"recovered SHA {persisted.red_commit_sha!r} must be the RED "
            f"commit {red_sha!r}, not the feedback SHA {feedback_sha!r}"
        )
        assert "GREEN_ENTRY_REFUSED" not in str(error or "")

    def test_unusable_sha_without_red_ancestor_is_deviatdd_bug(
        self, tmp_git_repo: Path
    ) -> None:
        """A printed SHA that is not a RED boundary is DEVIATDD_BUG, not refused."""
        docs_sha = _empty_commit(
            tmp_git_repo, f"docs({_TASK_ID}): add judge feedback for retry"
        )
        workspace = (
            tmp_git_repo
            / "specs"
            / "001-crypto-withdrawals"
            / "004-crypto-withdrawal-safety"
        )
        workspace.mkdir(parents=True, exist_ok=True)
        record = TaskRecord(
            id=_TASK_ID,
            issue_id=_ISSUE_ID,
            description="no RED ancestor",
            status="GREEN",
            execution_mode="TDD",
        )
        ledger = workspace / "tasks.jsonl"
        ledger.write_text(record.model_dump_json() + "\n", encoding="utf-8")
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session = SessionState(current_phase="GREEN", red_commit_sha=docs_sha)
        session.save(session_path)
        task = json.loads(record.model_dump_json())

        invoke_count, error = _drive_green(
            tmp_git_repo, session, session_path, ledger, task
        )
        assert invoke_count == 0
        assert error is not None
        text = str(error)
        assert "DEVIATDD_BUG" in text, text
        assert "ROLLBACK_BOUNDARY_MISSING" in text, text
        assert "GREEN_ENTRY_REFUSED" not in text, (
            "GH-236: a present-but-unusable SHA must not use "
            f"GREEN_ENTRY_REFUSED; got {text!r}"
        )

    def test_maybe_advance_keeps_red_sha_when_feedback_sits_on_green(
        self, tmp_git_repo: Path
    ) -> None:
        _task, _ledger, red_sha, _green = _seed_workspace(
            tmp_git_repo, feedback_on_green=True
        )
        fb_sha = _rev_parse(tmp_git_repo)
        session = SessionState(current_phase="GREEN", red_commit_sha=red_sha)
        _maybe_advance_red_sha_past_feedback(session, tmp_git_repo, red_sha, fb_sha)
        assert session.red_commit_sha == red_sha, (
            "GH-236: do not advance red_commit_sha onto feedback that does "
            f"not rest on RED; got {session.red_commit_sha!r} fb={fb_sha!r}"
        )
        assert not _is_red_phase_failing_test_sha(tmp_git_repo, fb_sha)
