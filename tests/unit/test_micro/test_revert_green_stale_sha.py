"""TSK-042-01 RED: stale rewritten RED remaps, current passes, empty refuses."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.state.config import SessionState
from tests.conftest import _git_env

_TASK_ID = "TSK-042-01"
_RED_SUBJECT = f"test({_TASK_ID}): RED phase - failing test"
_GREEN_SUBJECT = f"feat({_TASK_ID}): GREEN phase - implementation"
_DOCS_SUBJECT = "docs(042): concurrent docs"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_file(repo: Path, relpath: str, content: str, message: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--", relpath], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _rev_parse(repo)


def _rebase_red_green_onto_docs(repo: Path) -> dict[str, str]:
    base = _rev_parse(repo)
    stale_red = _commit_file(repo, "test_feat.py", "assert False\n", _RED_SUBJECT)
    _commit_file(repo, "feat.py", "def feat():\n    return 1\n", _GREEN_SUBJECT)
    subprocess.run(
        ["git", "branch", "docs-side", base],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", "docs-side"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    _commit_file(repo, "FLOW.md", "docs\n", _DOCS_SUBJECT)
    subprocess.run(
        ["git", "checkout", "--quiet", "main"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    rebase = subprocess.run(
        ["git", "rebase", "docs-side"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert rebase.returncode == 0, rebase.stderr
    rewritten_red = _rev_parse(repo, "HEAD~1")
    assert rewritten_red != stale_red
    return {"stale_red": stale_red, "rewritten_red": rewritten_red}


@pytest.fixture(autouse=True)
def _mock_run_pytest():
    with patch(
        "deviate.cli.micro._run_pytest",
        return_value=subprocess.CompletedProcess(args=["pytest"], returncode=0),
    ):
        yield


@pytest.mark.behavioral
def test_stale_rewritten_sha_remaps_with_old_and_new_sha_log(
    tmp_git_repo: Path,
) -> None:
    from deviate.cli import micro

    shas = _rebase_red_green_onto_docs(tmp_git_repo)
    session = SessionState(current_phase="GREEN", red_commit_sha=shas["stale_red"])
    with patch.object(micro, "_log_run") as log_run:
        boundary = micro._require_revert_green_boundary(tmp_git_repo, session, _TASK_ID)
    assert boundary == shas["rewritten_red"]
    assert session.red_commit_sha == shas["rewritten_red"]
    calls = [
        c for c in log_run.call_args_list if c.args and c.args[0] == "RED_SHA_REWRITTEN"
    ]
    assert calls, "rewritten remap must log RED_SHA_REWRITTEN"
    kwargs = calls[0].kwargs
    assert kwargs.get("old_sha") == shas["stale_red"]
    assert kwargs.get("new_sha") == shas["rewritten_red"]


@pytest.mark.behavioral
def test_ancestor_sha_passes_through_with_no_remap_log(tmp_git_repo: Path) -> None:
    from deviate.cli import micro

    red = _commit_file(tmp_git_repo, "t.py", "assert False\n", _RED_SUBJECT)
    session = SessionState(current_phase="GREEN", red_commit_sha=red)
    with patch.object(micro, "_log_run") as log_run:
        boundary = micro._require_revert_green_boundary(tmp_git_repo, session, _TASK_ID)
    assert boundary == red
    assert session.red_commit_sha == red
    assert not [
        c for c in log_run.call_args_list if c.args and c.args[0] == "RED_SHA_REWRITTEN"
    ], "ancestor passthrough must not log a remap"


@pytest.mark.behavioral
def test_empty_sha_raises_boundary_missing(tmp_git_repo: Path) -> None:
    from deviate.cli.micro import PhaseFailedError, _require_revert_green_boundary

    session = SessionState(current_phase="GREEN", red_commit_sha="")
    with pytest.raises(PhaseFailedError, match="ROLLBACK_BOUNDARY_MISSING"):
        _require_revert_green_boundary(tmp_git_repo, session, _TASK_ID)


_TASK_02 = "TSK-042-02"
_FEEDBACK_SUBJECT = f"docs({_TASK_02}): add judge feedback for retry"


def _head(repo: Path) -> str:
    return _rev_parse(repo)


def _discarded_red_beside_feedback(repo: Path) -> dict[str, str]:
    base = _commit_file(repo, "base.txt", "base\n", "chore: seed\n".strip())
    tasks_safe = _commit_file(
        repo, "tasks.md", "# tasks v1\n", "chore: seed tasks\n".strip()
    )
    pre = _commit_file(repo, "pre.txt", "pre\n", "chore: pre-red\n".strip())
    stored_red = _commit_file(repo, "t.py", "assert False\n", _RED_SUBJECT)
    subprocess.run(
        ["git", "reset", "--hard", "--quiet", pre],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    feedback = _commit_file(repo, "fb.txt", "fb\n", _FEEDBACK_SUBJECT)
    return {
        "stored_red": stored_red,
        "tasks_safe": tasks_safe,
        "feedback": feedback,
        "base": base,
    }


@pytest.mark.behavioral
def test_discarded_red_beside_feedback_resolves_at_or_after_tasks_safe(
    tmp_git_repo: Path,
) -> None:
    from deviate.cli import micro

    fix = _discarded_red_beside_feedback(tmp_git_repo)
    head_before = _head(tmp_git_repo)
    session = SessionState(current_phase="GREEN", red_commit_sha=fix["stored_red"])
    boundary = micro._require_revert_green_boundary(tmp_git_repo, session, _TASK_02)
    assert micro._is_ancestor(tmp_git_repo, fix["tasks_safe"], boundary)
    assert micro._is_ancestor(tmp_git_repo, boundary, head_before)


@pytest.mark.behavioral
def test_dangling_sha_with_no_match_refuses_with_head_unchanged(
    tmp_git_repo: Path,
) -> None:
    from deviate.cli.micro import PhaseFailedError, _require_revert_green_boundary

    _commit_file(tmp_git_repo, "base.txt", "base\n", "chore: seed")
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dangling = subprocess.run(
        ["git", "commit-tree", tree, "-m", "unrelated orphan"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    head_before = _head(tmp_git_repo)
    session = SessionState(current_phase="GREEN", red_commit_sha=dangling)
    with pytest.raises(PhaseFailedError):
        _require_revert_green_boundary(tmp_git_repo, session, _TASK_02)
    assert _head(tmp_git_repo) == head_before


@pytest.mark.behavioral
def test_recovery_keeps_latest_tasks_md_plus_feedback(tmp_git_repo: Path) -> None:
    from deviate.cli import micro

    fix = _discarded_red_beside_feedback(tmp_git_repo)
    committed = (tmp_git_repo / "tasks.md").read_text(encoding="utf-8")
    session = SessionState(current_phase="GREEN", red_commit_sha=fix["stored_red"])
    boundary = micro._require_revert_green_boundary(tmp_git_repo, session, _TASK_02)
    micro._execute_rollback(
        tmp_git_repo,
        boundary_sha=boundary,
        reason="test-recovery",
        phase="JUDGE",
        task_id=_TASK_02,
        attempt=1,
    )
    _commit_file(tmp_git_repo, "fb2.txt", "fb2\n", _FEEDBACK_SUBJECT)
    assert (tmp_git_repo / "tasks.md").read_text(encoding="utf-8") == committed


@pytest.mark.behavioral
def test_rerouted_train_completes_rollback_to_remapped_boundary(
    tmp_git_repo: Path,
) -> None:
    from deviate.cli import micro

    fix = _discarded_red_beside_feedback(tmp_git_repo)
    green = _commit_file(
        tmp_git_repo, "feat.py", "def feat():\n    return 1\n", _GREEN_SUBJECT
    )
    assert green != fix["feedback"]
    session = SessionState(current_phase="GREEN", red_commit_sha=fix["stored_red"])
    boundary = micro._require_revert_green_boundary(tmp_git_repo, session, _TASK_02)
    trace = micro._execute_rollback(
        tmp_git_repo,
        boundary_sha=boundary,
        reason="test-reroute",
        phase="JUDGE",
        task_id=_TASK_02,
        attempt=2,
    )
    assert _head(tmp_git_repo) == trace.reset_to == boundary
    assert micro._is_ancestor(tmp_git_repo, fix["tasks_safe"], boundary)
