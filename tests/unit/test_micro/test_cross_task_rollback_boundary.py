"""GH-247: resume rollback must not cross a completed predecessor.

A leftover ``session.red_commit_sha`` from TSK-N-02 (gitignored
``.deviate/session.json``) must not become the rollback boundary for
TSK-N-03. Existing-test RED must write a RED ledger row before GREEN.
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
    KernelError,
    _apply_judge_verdict,
    _bind_session_red_boundary,
    _green_post_kernel,
    _planned_revert_anchor,
    _run_red_phase,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition
from tests.conftest import _git_env

_ISSUE_ID = "ISS-ADH-247"
_PRED = "TSK-247-02"
_CUR = "TSK-247-03"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _commit_tree(repo: Path, message: str) -> str:
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


def _is_ancestor(repo: Path, maybe_ancestor: str, descendant: str = "HEAD") -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=repo,
        capture_output=True,
        env=_git_env(),
    )
    return result.returncode == 0


def _subjects(repo: Path) -> str:
    return subprocess.run(
        ["git", "log", "--format=%s"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout


def _ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latest_status(path: Path, task_id: str) -> str:
    status = ""
    for row in _ledger_rows(path):
        if row.get("id") == task_id:
            status = str(row.get("status") or "")
    return status


def _seed_predecessor_and_current(repo: Path) -> tuple[dict, Path, str, str]:
    """Build TSK-247-02 COMPLETED plus TSK-247-03 RED on a later commit."""
    workspace = repo / "specs" / "adhoc" / "247-cross-task-rollback"
    workspace.mkdir(parents=True)
    (workspace / "tasks.md").write_text(
        f"- [x] {_PRED}: predecessor\n- [ ] {_CUR}: dependent\n",
        encoding="utf-8",
    )
    ledger = workspace / "tasks.jsonl"
    pred = {
        "id": _PRED,
        "issue_id": _ISSUE_ID,
        "description": "predecessor slice",
        "execution_mode": "TDD",
    }
    cur = {
        "id": _CUR,
        "issue_id": _ISSUE_ID,
        "description": "dependent slice",
        "execution_mode": "TDD",
    }
    for status in ("PENDING", "RED"):
        append_task_transition(TaskRecord(**{**pred, "status": status}), ledger)
    _commit_tree(repo, "chore: seed predecessor ledger")
    pred_feedback = _empty_commit(repo, f"docs({_PRED}): add judge feedback for retry")
    _empty_commit(repo, f"test({_PRED}): RED phase - failing test")
    _empty_commit(repo, f"feat({_PRED}): GREEN phase - implementation passes tests")
    for status in ("GREEN", "COMPLETED"):
        append_task_transition(TaskRecord(**{**pred, "status": status}), ledger)
    _commit_tree(repo, f"refactor({_PRED}): REFACTOR phase — code cleanup")
    for status in ("PENDING", "RED"):
        append_task_transition(TaskRecord(**{**cur, "status": status}), ledger)
    cur_red = _commit_tree(repo, f"test({_CUR}): RED phase - failing test")
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(
        current_phase="RED",
        active_issue_id=_ISSUE_ID,
        red_commit_sha=pred_feedback,
    ).save(session_path)
    return cur, ledger, pred_feedback, cur_red


@pytest.mark.behavioral
def test_resume_rollback_does_not_cross_completed_predecessor(
    tmp_git_repo: Path,
) -> None:
    """AC: JUDGE revert_green on TSK-03 keeps TSK-02 COMPLETED and its commits."""
    with chdir(tmp_git_repo):
        task, ledger, pred_feedback, cur_red = _seed_predecessor_and_current(
            tmp_git_repo
        )
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        assert session.red_commit_sha == pred_feedback

        bound = _bind_session_red_boundary(tmp_git_repo, session, _CUR)
        session.save(session_path)
        assert bound == cur_red
        assert session.red_commit_sha == cur_red

        planned = _planned_revert_anchor(
            tmp_git_repo,
            session=session,
            action="revert_green",
            tid=_CUR,
        )
        assert planned.reset_to == cur_red
        assert planned.reset_to != pred_feedback

        manifest = HandoverManifest(
            phase="JUDGE",
            status="FAILURE",
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            rationale="implementation misses the dependent slice",
            task_id=_CUR,
        )
        c = Console(file=io.StringIO())
        _apply_judge_verdict(
            task,
            ledger,
            session,
            session_path,
            c,
            manifest,
            injected_diff="diff --git a/src/x.py b/src/x.py\n",
            assume_yes=True,
        )
        assert _latest_status(ledger, _PRED) == "COMPLETED"
        assert _is_ancestor(tmp_git_repo, cur_red)
        log = _subjects(tmp_git_repo)
        assert f"refactor({_PRED}): REFACTOR phase" in log
        assert f"test({_CUR}): RED phase" in log


@pytest.mark.behavioral
def test_existing_test_red_writes_red_before_green(tmp_git_repo: Path) -> None:
    """AC: passing/existing-test RED appends RED so GREEN post does not see PENDING."""
    workspace = tmp_git_repo / "specs" / "adhoc" / "247-existing-test-red"
    workspace.mkdir(parents=True)
    ledger = workspace / "tasks.jsonl"
    task = {
        "id": _CUR,
        "issue_id": _ISSUE_ID,
        "description": "existing tests already cover the slice",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    append_task_transition(TaskRecord(**task), ledger)
    session_path = tmp_git_repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session = SessionState(current_phase="IDLE", active_issue_id=_ISSUE_ID)
    session.save(session_path)
    (workspace / "tasks.md").write_text(
        f"- [ ] {_CUR}: existing tests\n", encoding="utf-8"
    )
    passing = subprocess.CompletedProcess(
        args=["pytest"], returncode=0, stdout="1 passed", stderr=""
    )
    manifest = HandoverManifest(
        phase="RED",
        status="SUCCESS",
        task_id=_CUR,
        failure_kind="already_satisfied",
        files=["tests/test_existing.py"],
    )
    (tmp_git_repo / "tests").mkdir(exist_ok=True)
    (tmp_git_repo / "tests" / "test_existing.py").write_text(
        "def test_existing() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    with (
        chdir(tmp_git_repo),
        patch("deviate.cli.micro._red_pre_kernel", return_value={}),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._build_auto_prompt", return_value="prompt"),
        patch("deviate.cli.micro._worktree_status_paths", return_value=[]),
        patch("deviate.cli.micro._invoke_agent", return_value=(manifest, "")),
        patch("deviate.cli.micro._run_test_cmd", return_value=passing),
        patch("deviate.cli.micro._run_format_cmd", return_value=passing),
        patch("deviate.cli.micro._require_tdd_declared_regression_files"),
        patch("deviate.cli.micro._verify_red_worktree_clean"),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        _run_red_phase(task, ledger, session, session_path, Console(file=io.StringIO()))
        assert _latest_status(ledger, _CUR) == "RED", (
            "existing-test RED must record a RED ledger transition before GREEN"
        )
        outcome = _green_post_kernel(tmp_git_repo, _CUR, ledger_hint=ledger)
        assert outcome.token == "GREEN_POST_OK"
        assert _latest_status(ledger, _CUR) == "GREEN"


@pytest.mark.behavioral
def test_skip_red_rebinds_foreign_boundary_and_keeps_red_ledger(
    tmp_git_repo: Path,
) -> None:
    """Skip-RED resume discards a predecessor SHA and leaves latest status RED."""
    with chdir(tmp_git_repo):
        task, ledger, pred_feedback, cur_red = _seed_predecessor_and_current(
            tmp_git_repo
        )
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        c = Console(file=io.StringIO())
        _run_red_phase(task, ledger, session, session_path, c)
        session = SessionState.load(session_path)
        assert session.red_commit_sha == cur_red
        assert session.red_commit_sha != pred_feedback
        assert _latest_status(ledger, _CUR) == "RED"
        try:
            outcome = _green_post_kernel(tmp_git_repo, _CUR, ledger_hint=ledger)
        except KernelError as exc:
            raise AssertionError(
                f"GREEN post after skip-RED must see RED, got {exc.token}: {exc.detail}"
            ) from exc
        assert outcome.token == "GREEN_POST_OK"
