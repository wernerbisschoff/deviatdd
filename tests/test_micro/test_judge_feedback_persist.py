"""Post-reset JUDGE revert persists JSONL + tasks.md in one commit.

``_apply_judge_verdict`` must reset first, then append ``tasks.jsonl``
(``judge_action`` + ``judge_feedback``) and ``tasks.md`` Judge Feedback,
then make one ``docs(<tid>): add judge feedback for retry`` commit that
contains both files. Writing JSONL before the reset would vanish.

GH-170: ``revert_red`` with structured ``violations`` (no ``train_feedback``)
must persist that payload and keep it through escalate-to-RED. A second
pre-RED reset must not delete the feedback commit.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import (
    PhaseFailedError,
    _build_auto_prompt,
    _escalate_to_new_red,
    _run_tdd_cycle,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from tests.conftest import _git_env
from tests.helpers.cycle_driver import load_verdicts
from tests.test_micro.test_judge_refactor_note_routing import (
    _ISSUE_ID,
    _TASK_ID,
    _manifest,
    _seed_green_repo,
    _task,
)
from tests.test_micro.test_judge_verdicts import _apply_existing


def _head_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _head_subject(root: Path) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _head_names(root: Path) -> list[str]:
    raw = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _head_blob(root: Path, relpath: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{relpath}"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout


def _parent_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _jsonl_rows(text: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _latest_judge_row(rows: list[dict[str, object]]) -> dict[str, object]:
    matching = [row for row in rows if row.get("judge_action")]
    assert matching, f"expected a judge_action row in {rows!r}"
    return matching[-1]


def _rev_parse(root: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _assert_discarded_commit_index(
    root: Path,
    *,
    ledger_path: Path,
    issue_id: str,
    task_id: str,
    expected_head: str,
    expected_reset: str,
) -> None:
    """Verdicts + tasks.jsonl share head_sha; recovery_ref points at it."""
    jsonl_rel = ledger_path.relative_to(root).as_posix()
    task_row = _latest_judge_row(_jsonl_rows(_head_blob(root, jsonl_rel)))
    verdicts = [
        row
        for row in load_verdicts(root, issue_id, task_id)
        if row.get("event") != "cycle_end"
        and row.get("next_action") in {"revert_red", "revert_green"}
    ]
    assert verdicts, "expected a reject row in verdicts.jsonl"
    verdict = verdicts[-1]
    for row, label in ((task_row, "tasks.jsonl"), (verdict, "verdicts.jsonl")):
        assert row.get("head_sha") == expected_head, (label, row)
        assert row.get("reset_to") == expected_reset, (label, row)
        ref = str(row.get("recovery_ref") or "")
        assert ref, f"{label} recovery_ref must be set when HEAD != boundary"
        assert _rev_parse(root, ref) == expected_head, (
            f"{label} git rev-parse {ref} != head_sha {expected_head}"
        )
    assert task_row["head_sha"] == verdict["head_sha"]
    assert task_row["recovery_ref"] == verdict["recovery_ref"]


class TestJudgeRevertPersistsAfterReset:
    """tmp_git_repo + ``_git_env()``: one post-reset feedback commit."""

    def test_revert_green_commit_has_jsonl_and_tasks_md(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        green_sha = _head_sha(tmp_git_repo)
        feedback = (
            "COMPLIANCE_FAIL: missing behavior. "
            "The next GREEN attempt must: implement the error path."
        )
        _apply_existing(
            tmp_git_repo,
            ledger_path,
            _manifest(
                verdict="COMPLIANCE_FAIL",
                next_action="revert_green",
                train_feedback=feedback,
            ),
        )
        assert _head_sha(tmp_git_repo) != red_sha, (
            "HEAD must be the feedback commit, not the RED sha we reset to"
        )
        assert _parent_sha(tmp_git_repo) == red_sha, (
            "feedback commit must sit on top of the RED boundary, "
            "not leave the repo at the reset sha"
        )
        assert "add judge feedback for retry" in _head_subject(tmp_git_repo)

        names = _head_names(tmp_git_repo)
        jsonl_rel = ledger_path.relative_to(tmp_git_repo).as_posix()
        md_rel = jsonl_rel.replace("tasks.jsonl", "tasks.md")
        assert jsonl_rel in names, f"HEAD missed {jsonl_rel}: {names}"
        assert md_rel in names, f"HEAD missed {md_rel}: {names}"
        assert not any("session.json" in name for name in names), names

        show = subprocess.run(
            ["git", "show", "HEAD"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout
        assert "judge_action" in show, show
        assert "**Judge Feedback**" in show, show

        rows = _jsonl_rows(_head_blob(tmp_git_repo, jsonl_rel))
        row = _latest_judge_row(rows)
        assert row["id"] == _TASK_ID
        assert row["issue_id"] == _ISSUE_ID
        assert row["judge_action"] == "revert_green"
        assert row["status"] == "RED"
        assert feedback in str(row["judge_feedback"])
        assert "Judge Feedback" in _head_blob(tmp_git_repo, md_rel)
        assert feedback in _head_blob(tmp_git_repo, md_rel)
        _assert_discarded_commit_index(
            tmp_git_repo,
            ledger_path=ledger_path,
            issue_id=_ISSUE_ID,
            task_id=_TASK_ID,
            expected_head=green_sha,
            expected_reset=red_sha,
        )

    def test_revert_red_commit_has_jsonl_on_top_of_pre_red(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        green_sha = _head_sha(tmp_git_repo)
        pre_red = subprocess.run(
            ["git", "rev-parse", f"{red_sha}^"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout.strip()
        feedback = "The next RED attempt must: author an honest test."
        _apply_existing(
            tmp_git_repo,
            ledger_path,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_red",
                train_feedback=feedback,
                extra={"evaluation": {"test_integrity": "FAIL"}},
            ),
        )
        assert _head_sha(tmp_git_repo) != red_sha
        assert _parent_sha(tmp_git_repo) == pre_red, (
            "revert_red feedback commit must sit on pre-RED, "
            f"got parent={_parent_sha(tmp_git_repo)} pre_red={pre_red}"
        )
        assert "add judge feedback for retry" in _head_subject(tmp_git_repo)

        names = _head_names(tmp_git_repo)
        jsonl_rel = ledger_path.relative_to(tmp_git_repo).as_posix()
        md_rel = jsonl_rel.replace("tasks.jsonl", "tasks.md")
        assert jsonl_rel in names, names
        assert md_rel in names, names
        assert not any("session.json" in name for name in names), names

        rows = _jsonl_rows(_head_blob(tmp_git_repo, jsonl_rel))
        row = _latest_judge_row(rows)
        assert row["judge_action"] == "revert_red"
        assert row["status"] == "PENDING"
        assert feedback in str(row["judge_feedback"])
        assert feedback in _head_blob(tmp_git_repo, md_rel)
        _assert_discarded_commit_index(
            tmp_git_repo,
            ledger_path=ledger_path,
            issue_id=_ISSUE_ID,
            task_id=_TASK_ID,
            expected_head=green_sha,
            expected_reset=pre_red,
        )


_REWRITE_RECOMMENDATION = (
    "Rewrite the RED tests to submit requests through the real application "
    "transport and assert committed rows, balance mutations, idempotency "
    "outcomes, snapshots, whitelist status, concurrency, and rollback."
)
_IDEMPOTENCY_RECOMMENDATION = (
    "Implement transactional idempotency admission that serializes the unique "
    "key and returns one committed row with one reservation under concurrent "
    "PostgreSQL requests."
)
_VIOLATIONS_ONLY = [
    {
        "category": "Test Integrity Violation",
        "severity": "CRITICAL",
        "detail": ("RED tests mock the transport instead of exercising the live app."),
        "recommendation": _REWRITE_RECOMMENDATION,
    },
    {
        "category": "Spec Non-Compliance",
        "severity": "HIGH",
        "detail": "Concurrent admission is not serialized on the unique key.",
        "recommendation": _IDEMPOTENCY_RECOMMENDATION,
    },
]


def _violations_only_manifest() -> HandoverManifest:
    return _manifest(
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_red",
        train_feedback="",
        violations=_VIOLATIONS_ONLY,
    )


def _mock_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="1 failed", stderr=""
        ),
    )


class TestRevertRedViolationsReachRetryRed:
    """GH-170: violations-only revert_red keeps Judge Feedback through escalate."""

    def test_revert_red_violations_only_persist_on_head(
        self, tmp_git_repo: Path
    ) -> None:
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        _apply_existing(tmp_git_repo, ledger_path, _violations_only_manifest())

        assert "add judge feedback for retry" in _head_subject(tmp_git_repo)
        md_rel = (
            ledger_path.relative_to(tmp_git_repo)
            .as_posix()
            .replace("tasks.jsonl", "tasks.md")
        )
        md_text = _head_blob(tmp_git_repo, md_rel)
        assert "**Judge Feedback**" in md_text
        assert _REWRITE_RECOMMENDATION in md_text
        assert _IDEMPOTENCY_RECOMMENDATION in md_text
        rows = _jsonl_rows(
            _head_blob(tmp_git_repo, ledger_path.relative_to(tmp_git_repo).as_posix())
        )
        row = _latest_judge_row(rows)
        assert row["judge_action"] == "revert_red"
        assert _REWRITE_RECOMMENDATION in str(row["judge_feedback"])

    def test_escalate_keeps_violation_payload_and_feedback_commit(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Escalate after apply must not wipe violations or the persist commit.

        Re-point ``red_commit_sha`` at the feedback commit so a naive second
        pre-RED rollback would delete it. Retry RED must still see the
        recommendation text, not ``previous cycle failed because test defect``.
        """
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        session = _apply_existing(
            tmp_git_repo, ledger_path, _violations_only_manifest()
        )
        feedback_sha = _head_sha(tmp_git_repo)
        feedback_parent = _parent_sha(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session.red_commit_sha = feedback_sha
        session.save(session_path)

        captured_feedback: list[str] = []
        captured_prompts: list[str] = []

        def _red(*args: object, **kwargs: object) -> SessionState:
            session_arg = args[2]
            session_path_arg = args[3]
            assert isinstance(session_arg, SessionState)
            assert isinstance(session_path_arg, Path)
            captured_feedback.append(session_arg.train_feedback)
            captured_prompts.append(
                _build_auto_prompt(
                    "red",
                    _task(),
                    Path.cwd(),
                    train_feedback=session_arg.train_feedback,
                )
            )
            session_arg.red_commit_sha = "b" * 40
            session_arg.save(session_path_arg)
            return session_arg

        monkeypatch.chdir(tmp_git_repo)
        _mock_pytest(monkeypatch)
        monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        session = _escalate_to_new_red(
            _task(),
            ledger_path,
            session,
            session_path,
            console,
            agent=None,
            monitor=None,
            no_judge=False,
            root=tmp_git_repo,
            reason="test_defect",
        )

        assert captured_feedback, "retry RED must run after escalate"
        retry = captured_feedback[0]
        prompt = captured_prompts[0]
        assert _REWRITE_RECOMMENDATION in retry, retry
        assert _IDEMPOTENCY_RECOMMENDATION in retry, retry
        assert "previous cycle failed because" not in retry, retry
        assert _REWRITE_RECOMMENDATION in prompt, prompt
        assert "previous cycle failed because" not in prompt, prompt
        assert session.train_feedback == retry
        assert _head_sha(tmp_git_repo) == feedback_sha, (
            "escalate must not reset to a parent of the feedback commit; "
            f"HEAD={_head_sha(tmp_git_repo)} parent={feedback_parent} "
            f"feedback={feedback_sha}"
        )
        assert _head_sha(tmp_git_repo) != feedback_parent

    def test_tdd_cycle_revert_red_keeps_violations_on_retry_red(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``pending == revert_red`` in ``_run_tdd_cycle`` must not replace payload."""
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        session = _apply_existing(
            tmp_git_repo, ledger_path, _violations_only_manifest()
        )
        feedback_sha = _head_sha(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session.red_commit_sha = feedback_sha
        session.save(session_path)

        captured_feedback: list[str] = []

        def _red(*args: object, **kwargs: object) -> SessionState:
            session_arg = args[2]
            session_path_arg = args[3]
            assert isinstance(session_arg, SessionState)
            assert isinstance(session_path_arg, Path)
            captured_feedback.append(session_arg.train_feedback)
            session_arg.red_commit_sha = "c" * 40
            session_arg.save(session_path_arg)
            raise PhaseFailedError("stop-after-retry-red")

        monkeypatch.chdir(tmp_git_repo)
        _mock_pytest(monkeypatch)
        monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)

        with pytest.raises(PhaseFailedError, match="stop-after-retry-red"):
            _run_tdd_cycle(_task(), ledger_path, console, start_phase="GREEN")

        assert captured_feedback, "cycle escalate must dispatch retry RED"
        retry = captured_feedback[0]
        assert _REWRITE_RECOMMENDATION in retry, retry
        assert "previous cycle failed because" not in retry, retry
        assert _head_sha(tmp_git_repo) == feedback_sha


def _is_ancestor(root: Path, commit: str, of: str = "HEAD") -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, of],
            cwd=root,
            env=_git_env(),
            capture_output=True,
        ).returncode
        == 0
    )


class TestMislabeledRevertRedAfterGreenPass:
    """After GREEN PASS, ``revert_red`` without Test Integrity keeps RED."""

    def test_spec_gap_revert_red_coerces_to_revert_green_and_keeps_red(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        feedback = (
            "COMPLIANCE_VIOLATION: implementation misses the AC. "
            "The next GREEN attempt must: implement the error path."
        )
        session = _apply_existing(
            tmp_git_repo,
            ledger_path,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_red",
                train_feedback=feedback,
                extra={
                    "violations": [
                        {
                            "category": "Spec Non-Compliance",
                            "file": "impl.py",
                            "detail": "error path missing",
                            "severity": "CRITICAL",
                            "recommendation": "Implement the missing slice.",
                        }
                    ],
                    "evaluation": {"test_integrity": "PASS"},
                },
            ),
        )
        assert session.pending_judge_action == "revert_green", (
            "mis-labeled revert_red after GREEN PASS must coerce to "
            f"revert_green; got {session.pending_judge_action!r}"
        )
        assert (tmp_git_repo / "feature.py").exists(), (
            "RED test commit must stay when JUDGE only failed GREEN"
        )
        assert not (tmp_git_repo / "impl.py").exists(), (
            "GREEN implementation must be discarded on coerced revert_green"
        )
        assert _is_ancestor(tmp_git_repo, red_sha), (
            f"RED SHA {red_sha} must remain an ancestor after coerce"
        )
        assert session.red_commit_sha, "revert_green must keep a RED boundary"
        assert "The next GREEN attempt must:" in session.train_feedback
        md_rel = (
            ledger_path.relative_to(tmp_git_repo)
            .as_posix()
            .replace("tasks.jsonl", "tasks.md")
        )
        assert "The next GREEN attempt must:" in _head_blob(tmp_git_repo, md_rel)

    def test_integrity_fail_keeps_revert_red_and_persists_red_feedback(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        feedback = (
            "The next RED attempt must: author a test that actually fails the AC."
        )
        session = _apply_existing(
            tmp_git_repo,
            ledger_path,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_red",
                train_feedback=feedback,
                extra={
                    "violations": [
                        {
                            "category": "Test Integrity Violation",
                            "file": "feature.py",
                            "detail": "filename-only test",
                            "severity": "CRITICAL",
                            "recommendation": "Assert the AC.",
                        }
                    ],
                    "evaluation": {"test_integrity": "FAIL"},
                },
            ),
        )
        assert session.pending_judge_action == "revert_red"
        assert not (tmp_git_repo / "feature.py").exists(), (
            "genuine Test Integrity revert_red must discard RED"
        )
        assert not (tmp_git_repo / "impl.py").exists()
        assert not _is_ancestor(tmp_git_repo, red_sha), (
            "RED SHA must not survive a genuine revert_red"
        )
        assert "The next RED attempt must:" in session.train_feedback
        assert "actually fails the AC" in session.train_feedback
        md_rel = (
            ledger_path.relative_to(tmp_git_repo)
            .as_posix()
            .replace("tasks.jsonl", "tasks.md")
        )
        assert "The next RED attempt must:" in _head_blob(tmp_git_repo, md_rel)

    def test_integrity_revert_red_empty_feedback_does_not_discard_red(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        with pytest.raises(PhaseFailedError, match="JUDGE_AGENT_NO_FEEDBACK"):
            _apply_existing(
                tmp_git_repo,
                ledger_path,
                _manifest(
                    verdict="COMPLIANCE_VIOLATION",
                    next_action="revert_red",
                    train_feedback="",
                    extra={"evaluation": {"test_integrity": "FAIL"}},
                ),
            )
        assert (tmp_git_repo / "feature.py").exists(), (
            "empty revert_red must not discard RED"
        )
        assert (tmp_git_repo / "impl.py").exists(), (
            "empty revert_red must not discard GREEN either"
        )
        assert _is_ancestor(tmp_git_repo, red_sha)
        assert _head_sha(tmp_git_repo) != red_sha, "GREEN commit must still be HEAD"

    def test_integrity_revert_red_green_only_feedback_rewrites_to_red(
        self, tmp_git_repo: Path
    ) -> None:
        _red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        session = _apply_existing(
            tmp_git_repo,
            ledger_path,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_red",
                train_feedback=(
                    "The next GREEN attempt must: author an honest failing test."
                ),
                extra={
                    "violations": [
                        {
                            "category": "Test Integrity Violation",
                            "file": "feature.py",
                            "detail": "assert True",
                            "severity": "CRITICAL",
                            "recommendation": "Assert the AC.",
                        }
                    ],
                    "evaluation": {"test_integrity": "FAIL"},
                },
            ),
        )
        assert session.pending_judge_action == "revert_red"
        assert "The next RED attempt must:" in session.train_feedback
        assert "author an honest failing test" in session.train_feedback
        assert "The next GREEN attempt must:" not in session.train_feedback
        md_rel = (
            ledger_path.relative_to(tmp_git_repo)
            .as_posix()
            .replace("tasks.jsonl", "tasks.md")
        )
        md_text = _head_blob(tmp_git_repo, md_rel)
        assert "The next RED attempt must:" in md_text
        assert not (tmp_git_repo / "feature.py").exists()
