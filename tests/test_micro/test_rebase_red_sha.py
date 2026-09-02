"""GH-168: rebase rewrite must refresh RED SHA before revert_green.

A commit-train rebase (concurrent docs landed under RED+GREEN) changes
the RED SHA. Session state that still holds the pre-rebase SHA must not
be used as a ``git reset --hard`` target — that drops the rewritten RED
and any unrelated commits the rebase replayed.

Pinned behaviour:
- ``_refresh_session_commit_anchors`` remaps ``red_commit_sha`` (and
  ``judge_red_commit_sha``) to the rewritten SHA.
- ``revert_green`` resets to the rewritten RED, not the stale SHA.
- ``revert_red`` remaps a rewritten RED to the current-train parent
  (keeps unrelated commits) and no-ops a second call after HEAD is
  already behind the stored SHA.
- The unrelated rebased commit remains on the active branch.
- A stale SHA that cannot be remapped refuses ``revert_green`` and
  leaves HEAD where it is.
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from rich.console import Console

from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env


_TASK_ID = "TSK-001-01"
_RED_SUBJECT = f"test({_TASK_ID}): RED phase - failing test"
_GREEN_SUBJECT = f"feat({_TASK_ID}): GREEN phase - implementation"
_DOCS_SUBJECT = "docs(001-001): remove obsolete flow catalog references"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _subject(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%s", rev],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
        ).returncode
        == 0
    )


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


def _log_oneline(repo: Path) -> list[str]:
    return (
        subprocess.run(
            ["git", "log", "--oneline", "--format=%s"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .splitlines()
    )


def _rebase_red_green_onto_docs(repo: Path) -> dict[str, str]:
    """Replay RED+GREEN on top of a concurrent docs commit.

    Returns stale (pre-rebase) and rewritten SHAs. After the rebase the
    stale RED is no longer an ancestor of HEAD.
    """
    base = _rev_parse(repo)
    stale_red = _commit_file(repo, "test_feat.py", "assert False\n", _RED_SUBJECT)
    stale_green = _commit_file(
        repo, "feat.py", "def feat():\n    return 1\n", _GREEN_SUBJECT
    )

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
    docs_sha = _commit_file(repo, "FLOW.md", "removed catalog refs\n", _DOCS_SUBJECT)
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

    rewritten_green = _rev_parse(repo)
    rewritten_red = _rev_parse(repo, "HEAD~1")
    assert _subject(repo, rewritten_red) == _RED_SUBJECT
    assert _subject(repo, rewritten_green) == _GREEN_SUBJECT
    assert rewritten_red != stale_red
    assert not _is_ancestor(repo, stale_red, "HEAD")
    assert _is_ancestor(repo, rewritten_red, "HEAD")
    assert _is_ancestor(repo, docs_sha, "HEAD")
    return {
        "stale_red": stale_red,
        "stale_green": stale_green,
        "rewritten_red": rewritten_red,
        "rewritten_green": rewritten_green,
        "docs_sha": docs_sha,
    }


def _write_session(repo: Path, **kwargs: object) -> Path:
    path = repo / ".deviate" / "session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    session = SessionState(current_phase="GREEN", **kwargs)
    session.save(path)
    return path


def _seed_judge_ledger(repo: Path) -> tuple[dict, Path]:
    workspace = repo / "specs" / "001-crypto" / "001-create-reserve"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "tasks.md").write_text(f"- [ ] {_TASK_ID}: create reserve\n")
    ledger = workspace / "tasks.jsonl"
    record = TaskRecord(
        id=_TASK_ID,
        issue_id="001-001",
        description="create reserve",
        status="GREEN",
        execution_mode="TDD",
    )
    ledger.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    return record.model_dump(), ledger


class TestRefreshSessionCommitAnchors:
    """Rebase rewrite remaps session SHAs to the new objects."""

    def test_refresh_rewrites_red_and_judge_red_after_rebase(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _refresh_session_commit_anchors

        shas = _rebase_red_green_onto_docs(tmp_git_repo)
        session = SessionState(
            current_phase="GREEN",
            red_commit_sha=shas["stale_red"],
            judge_red_commit_sha=shas["stale_red"],
        )

        changed = _refresh_session_commit_anchors(tmp_git_repo, session)

        assert changed is True
        assert session.red_commit_sha == shas["rewritten_red"], (
            "session.red_commit_sha must move to the rewritten RED; "
            f"got {session.red_commit_sha!r} expected {shas['rewritten_red']!r}"
        )
        assert session.judge_red_commit_sha == shas["rewritten_red"], (
            "judge_red_commit_sha must remap with red_commit_sha after rebase"
        )

    def test_refresh_is_noop_when_red_is_already_ancestor(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _refresh_session_commit_anchors

        red = _commit_file(tmp_git_repo, "t.py", "assert False\n", _RED_SUBJECT)
        session = SessionState(current_phase="GREEN", red_commit_sha=red)

        changed = _refresh_session_commit_anchors(tmp_git_repo, session)

        assert changed is False
        assert session.red_commit_sha == red


class TestRedAnchorKind:
    """Rebase rewrite vs already-applied revert_red must not be confused."""

    def test_kind_rewritten_after_rebase_and_already_reverted_after_reset(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _red_anchor_kind, _resolve_revert_red_boundary

        shas = _rebase_red_green_onto_docs(tmp_git_repo)
        assert _red_anchor_kind(tmp_git_repo, shas["stale_red"]) == "rewritten", (
            "rebase must classify the pre-rewrite RED as rewritten, not already_reverted"
        )
        assert _red_anchor_kind(tmp_git_repo, shas["rewritten_red"]) == "current"

        subprocess.run(
            ["git", "reset", "--hard", shas["docs_sha"]],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        assert _is_ancestor(tmp_git_repo, "HEAD", shas["rewritten_red"])
        assert (
            _red_anchor_kind(tmp_git_repo, shas["rewritten_red"]) == "already_reverted"
        )
        session = SessionState(
            current_phase="GREEN", red_commit_sha=shas["rewritten_red"]
        )
        boundary = _resolve_revert_red_boundary(tmp_git_repo, session)
        assert _is_ancestor(tmp_git_repo, boundary, "HEAD"), (
            "second revert_red must no-op or reset to the already-applied "
            f"pre-RED; got {boundary!r}"
        )


class TestRevertRedAfterRebaseAndReplay:
    """revert_red remaps a rewritten RED and does not raise after a prior reset."""

    def test_revert_red_after_rebase_resets_to_rewritten_parent_and_keeps_docs(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _apply_judge_verdict

        shas = _rebase_red_green_onto_docs(tmp_git_repo)
        task, ledger = _seed_judge_ledger(tmp_git_repo)
        session_path = _write_session(
            tmp_git_repo,
            red_commit_sha=shas["stale_red"],
            judge_red_commit_sha=shas["stale_red"],
            active_issue_id="001-001",
        )
        session = SessionState.load(session_path)
        manifest = HandoverManifest(
            phase="JUDGE",
            status="PASS",
            task_id=_TASK_ID,
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_red",
            rationale="RED test asserts the wrong contract",
        )

        with chdir(tmp_git_repo):
            _apply_judge_verdict(
                task,
                ledger,
                session,
                session_path,
                Console(),
                manifest,
                injected_diff="diff --git a/feat.py b/feat.py\n",
            )

        subjects = _log_oneline(tmp_git_repo)
        assert _DOCS_SUBJECT in subjects, (
            "revert_red after rebase must keep the unrelated docs commit; "
            f"log={subjects!r}"
        )
        assert _RED_SUBJECT not in subjects
        assert _GREEN_SUBJECT not in subjects
        assert (tmp_git_repo / "FLOW.md").exists()
        assert not (tmp_git_repo / "test_feat.py").exists()
        assert not _is_ancestor(tmp_git_repo, shas["stale_red"], "HEAD")

    def test_second_revert_red_after_reset_does_not_raise(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import PhaseFailedError, _apply_judge_verdict

        red = _commit_file(tmp_git_repo, "test_feat.py", "assert False\n", _RED_SUBJECT)
        _commit_file(
            tmp_git_repo, "feat.py", "def feat():\n    return 1\n", _GREEN_SUBJECT
        )
        task, ledger = _seed_judge_ledger(tmp_git_repo)
        session_path = _write_session(
            tmp_git_repo, red_commit_sha=red, active_issue_id="001-001"
        )
        manifest = HandoverManifest(
            phase="JUDGE",
            status="PASS",
            task_id=_TASK_ID,
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_red",
            rationale="The next RED attempt must: author an honest test.",
        )

        def _apply() -> None:
            session = SessionState.load(session_path)
            with chdir(tmp_git_repo):
                _apply_judge_verdict(
                    task,
                    ledger,
                    session,
                    session_path,
                    Console(),
                    manifest,
                    injected_diff="",
                )

        _apply()
        session = SessionState.load(session_path)
        session.red_commit_sha = red
        session.current_phase = "GREEN"
        session.pending_judge_action = ""
        session.judge_rejected = False
        session.failure_kind = ""
        session.save(session_path)
        try:
            _apply()
        except PhaseFailedError as exc:
            raise AssertionError(
                "second revert_red after HEAD is already behind the stored "
                f"RED must not raise; got {exc}"
            ) from exc
        assert _is_ancestor(tmp_git_repo, "HEAD", red) or not _is_ancestor(
            tmp_git_repo, red, "HEAD"
        )


class TestRevertGreenAfterRebase:
    """revert_green must reset to the rewritten RED and keep docs."""

    def test_revert_green_resets_to_rewritten_red_and_keeps_docs(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _apply_judge_verdict

        shas = _rebase_red_green_onto_docs(tmp_git_repo)
        task, ledger = _seed_judge_ledger(tmp_git_repo)
        session_path = _write_session(
            tmp_git_repo,
            red_commit_sha=shas["stale_red"],
            judge_red_commit_sha=shas["stale_red"],
            active_issue_id="001-001",
        )
        session = SessionState.load(session_path)
        manifest = HandoverManifest(
            phase="JUDGE",
            status="PASS",
            task_id=_TASK_ID,
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            rationale="implementation misses the reserve lock",
        )

        with chdir(tmp_git_repo):
            result = _apply_judge_verdict(
                task,
                ledger,
                session,
                session_path,
                Console(),
                manifest,
                injected_diff="diff --git a/feat.py b/feat.py\n",
            )

        head = _rev_parse(tmp_git_repo)
        subjects = _log_oneline(tmp_git_repo)
        assert _DOCS_SUBJECT in subjects, (
            "unrelated rebased docs commit must remain after revert_green; "
            f"log={subjects!r}"
        )
        assert _GREEN_SUBJECT not in subjects, (
            "GREEN must be discarded; log={0!r}".format(subjects)
        )
        assert _is_ancestor(tmp_git_repo, shas["rewritten_red"], head), (
            "HEAD after revert_green must sit on the rewritten RED train"
        )
        assert not _is_ancestor(tmp_git_repo, shas["stale_red"], head), (
            "revert_green must not reset onto the stale pre-rebase RED"
        )
        assert result.red_commit_sha != shas["stale_red"]
        persisted = SessionState.load(session_path)
        assert persisted.red_commit_sha != shas["stale_red"]
        assert (tmp_git_repo / "FLOW.md").exists(), (
            "docs file from the unrelated commit must survive revert_green"
        )
        assert not (tmp_git_repo / "feat.py").exists(), (
            "GREEN implementation must be discarded"
        )
        assert (tmp_git_repo / "test_feat.py").exists(), "current RED test must remain"

    def test_require_revert_green_boundary_resolves_rewritten_sha(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _require_revert_green_boundary

        shas = _rebase_red_green_onto_docs(tmp_git_repo)
        session = SessionState(current_phase="GREEN", red_commit_sha=shas["stale_red"])

        boundary = _require_revert_green_boundary(tmp_git_repo, session, _TASK_ID)

        assert boundary == shas["rewritten_red"]
        assert session.red_commit_sha == shas["rewritten_red"]

    def test_stale_unresolvable_red_refuses_reset(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import (
            PhaseFailedError,
            _execute_rollback,
            _require_revert_green_boundary,
        )

        head_before = _rev_parse(tmp_git_repo)
        _commit_file(tmp_git_repo, "keep.md", "stay\n", "docs: keep this")
        head_with_docs = _rev_parse(tmp_git_repo)
        session = SessionState(
            current_phase="GREEN",
            red_commit_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        )

        with pytest.raises(PhaseFailedError, match="ROLLBACK_STALE_RED_SHA"):
            _require_revert_green_boundary(tmp_git_repo, session, _TASK_ID)

        assert _rev_parse(tmp_git_repo) == head_with_docs, (
            "refusing a stale RED must not move HEAD"
        )

        with pytest.raises(PhaseFailedError, match="ROLLBACK_STALE_BOUNDARY"):
            _execute_rollback(
                tmp_git_repo,
                boundary_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                reason="stale",
                phase="JUDGE",
                task_id=_TASK_ID,
                attempt=1,
            )

        assert _rev_parse(tmp_git_repo) == head_with_docs
        assert (tmp_git_repo / "keep.md").exists()
        assert head_before != head_with_docs
