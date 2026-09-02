"""Post-reset JUDGE revert persists JSONL + tasks.md in one commit.

``_apply_judge_verdict`` must reset first, then append ``tasks.jsonl``
(``judge_action`` + ``judge_feedback``) and ``tasks.md`` Judge Feedback,
then make one ``docs(<tid>): add judge feedback for retry`` commit that
contains both files. Writing JSONL before the reset would vanish.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import _git_env
from tests.helpers.cycle_driver import load_verdicts
from tests.test_micro.test_judge_refactor_note_routing import (
    _ISSUE_ID,
    _TASK_ID,
    _manifest,
    _seed_green_repo,
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
