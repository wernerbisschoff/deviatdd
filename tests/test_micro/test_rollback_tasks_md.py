"""GH-201: JUDGE rollback must never drop a committed ``tasks.md``.

Wallet-service (deviate 2.27.1) reset the feature branch to
``docs(001-001): create plan.md``. The Tasks commit
``docs(001-001): create tasks.md`` (same parent) left the active
lineage. ``git ls-tree -r HEAD`` had no ``…/tasks.md``; meso then
regenerated Tasks.

Pinned contract:
1. Replay plan.md → tasks.md → RED → GREEN. ``revert_red`` / escalate
   pre-RED must leave ``tasks.md`` on HEAD (``git ls-tree``).
2. A stored ``red_commit_sha`` equal to the tasks.md commit must not
   resolve pre-RED to plan.md (walk past meso docs).
3. Even when the caller threads plan.md as ``boundary_sha``,
   ``_execute_rollback`` checkouts every ``tasks.md`` that existed at
   the pre-reset HEAD and is missing after ``reset --hard`` +
   ``git clean -fd``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.cli.micro import (
    _execute_rollback,
    _resolve_judge_diff_base,
    _resolve_pre_red_sha,
    _rollback_pre_red_if_resolvable,
)
from deviate.state.config import SessionState
from tests.conftest import _git_env

_TASK_ID = "TSK-001-01"
_ISSUE_DIR = "specs/001-crypto-create-reserve"
_TASKS_MD = f"{_ISSUE_DIR}/tasks.md"
_PLAN_MD = f"{_ISSUE_DIR}/plan.md"


def _sha(root: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _commit(root: Path, message: str, relpath: str, body: str) -> str:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "--", relpath], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _sha(root)


def _ls_tree(root: Path, rev: str = "HEAD") -> list[str]:
    return subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.splitlines()


def _ls_files(root: Path) -> list[str]:
    return subprocess.run(
        ["git", "ls-files", "--", _TASKS_MD],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.splitlines()


def _seed_wallet_graph(root: Path) -> tuple[str, str, str, str]:
    """plan.md → tasks.md → RED → GREEN. Returns those four SHAs."""
    plan_sha = _commit(
        root,
        "docs(001-001): create plan.md",
        _PLAN_MD,
        "# Plan\n\n### AC-PLAN-001: reserve\n",
    )
    tasks_sha = _commit(
        root,
        "docs(001-001): create tasks.md",
        _TASKS_MD,
        f"# Tasks\n\n- {_TASK_ID} create reserve (tdd)\n",
    )
    red_sha = _commit(
        root,
        f"test({_TASK_ID}): RED phase - failing test",
        "tests/test_tsk_001_01.py",
        "def test_reserve() -> None:\n    assert False\n",
    )
    green_sha = _commit(
        root,
        f"feat({_TASK_ID}): GREEN phase - implementation",
        "src/tsk_001_01.py",
        "def reserve() -> str:\n    return 'ok'\n",
    )
    return plan_sha, tasks_sha, red_sha, green_sha


class TestRollbackPreservesTasksMd:
    """Replay the wallet-service graph (GH-201)."""

    def test_revert_red_pre_red_keeps_tasks_md_on_head(
        self, tmp_git_repo: Path
    ) -> None:
        """Escalate / revert_red from a real RED must not drop tasks.md."""
        root = tmp_git_repo
        plan_sha, tasks_sha, red_sha, _green_sha = _seed_wallet_graph(root)

        pre_red = _resolve_pre_red_sha(root, red_sha)
        assert pre_red == tasks_sha, (
            f"true pre-RED is the tasks.md commit {tasks_sha[:7]}, "
            f"not plan.md {plan_sha[:7]}; got {pre_red}"
        )
        assert pre_red != plan_sha

        session = SessionState(red_commit_sha=red_sha)
        _rollback_pre_red_if_resolvable(
            root,
            session,
            task_id=_TASK_ID,
            attempt=1,
            reason="revert_red",
        )
        assert _TASKS_MD in _ls_tree(root, "HEAD"), (
            "GH-201: git ls-tree -r HEAD must list tasks.md after "
            f"revert_red / escalate pre-RED; HEAD={_sha(root)[:7]} "
            f"tree={_ls_tree(root)}"
        )
        assert (root / _TASKS_MD).is_file(), (
            "GH-201: tasks.md must remain on disk after revert_red"
        )

    def test_stored_tasks_md_sha_does_not_reset_to_plan_md(
        self, tmp_git_repo: Path
    ) -> None:
        """``red_commit_sha`` pointing at create-tasks.md is not pre-RED=plan."""
        root = tmp_git_repo
        plan_sha, tasks_sha, red_sha, _green_sha = _seed_wallet_graph(root)
        assert red_sha  # graph includes a real RED after tasks.md

        walked = _resolve_judge_diff_base(root, tasks_sha)
        assert walked != tasks_sha, (
            f"walk past meso docs: create tasks.md is not a RED boundary; got {walked}"
        )
        resolved = _resolve_pre_red_sha(root, tasks_sha)
        assert resolved != plan_sha, (
            "GH-201: stored red_commit_sha equal to the tasks.md commit "
            f"must not resolve pre-RED to plan.md {plan_sha[:7]}; "
            f"got {resolved}"
        )

        session = SessionState(red_commit_sha=tasks_sha)
        _rollback_pre_red_if_resolvable(
            root,
            session,
            task_id=_TASK_ID,
            attempt=1,
            reason="green_budget_exhausted",
        )
        assert _TASKS_MD in _ls_tree(root, "HEAD"), (
            "GH-201: escalate with red_commit_sha=tasks.md must leave "
            f"tasks.md on HEAD; tree={_ls_tree(root)}"
        )
        assert (root / _TASKS_MD).is_file()

    def test_execute_rollback_checkouts_tasks_md_dropped_by_boundary(
        self, tmp_git_repo: Path
    ) -> None:
        """Hard invariant: missing tasks.md is restored after reset+clean."""
        root = tmp_git_repo
        plan_sha, _tasks_sha, _red_sha, _green_sha = _seed_wallet_graph(root)
        scratch = root / "scratch_untracked.py"
        scratch.write_text("# gone after clean\n", encoding="utf-8")

        assert _TASKS_MD in _ls_tree(root, "HEAD")
        assert _TASKS_MD not in _ls_tree(root, plan_sha), (
            "precondition: plan.md commit must not already carry tasks.md"
        )

        _execute_rollback(
            root,
            boundary_sha=plan_sha,
            reason="GH-201 forced early pre-RED",
            phase="JUDGE",
            task_id=_TASK_ID,
            attempt=1,
        )

        assert _sha(root) == plan_sha, (
            f"rollback still lands on the caller boundary {plan_sha[:7]}; "
            f"HEAD is {_sha(root)[:7]}"
        )
        assert not scratch.exists(), (
            "git clean -fd must still remove untracked GREEN scratch"
        )
        assert (root / _TASKS_MD).is_file(), (
            "GH-201: _execute_rollback must checkout tasks.md from "
            "pre-reset HEAD after clean so the file is not absent"
        )
        assert _TASKS_MD in _ls_files(root), (
            "restored tasks.md must be staged from pre-reset HEAD "
            f"(git checkout {plan_sha[:7]} is the wrong tree)"
        )
        # Issue diagnostic: `git ls-tree` must list tasks.md after rollback.
        # Checkout stages the file; write-tree is that staged tree. Do not
        # wait for the later feedback commit to recreate the path.
        index_tree = subprocess.run(
            ["git", "write-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout.strip()
        assert _TASKS_MD in _ls_tree(root, index_tree), (
            "GH-201: git ls-tree after rollback must list tasks.md "
            f"(index tree {index_tree[:7]}); got {_ls_tree(root, index_tree)}"
        )
