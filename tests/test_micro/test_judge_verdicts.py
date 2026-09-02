"""Per-task JUDGE verdicts JSONL + CYCLE_END postmortem (not AGENT_RAW_OUTPUT).

``_apply_judge_verdict`` writes one JSON object per JUDGE application
(pass and reject) to ``.deviate/logs/<issue>/<task>.verdicts.jsonl``.
``_run_tdd_cycle`` appends a ``cycle_end`` object to the same file and
emits a ``CYCLE_END`` ``_log_run`` event. The file is JSONL — not the
``[<ts>] EVENT`` transcript format.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.cycle_driver import (
    _REFACTOR_NOTE,
    CycleTask,
    gh158_steps,
    load_verdicts,
    reject_then_pass_steps,
    run_scripted_cycle,
    seed_cycle_repo,
    verdicts_path,
)
from tests.test_micro.test_judge_refactor_note_routing import (
    _ISSUE_ID,
    _NOTE,
    _TASK_ID,
    _apply,
    _manifest,
)

_TASK = CycleTask(
    task_id="TSK-160-01",
    description="Verdicts postmortem slice",
    ac="AC-PLAN-001",
)

_VERDICT_KEYS = {
    "ts",
    "task_id",
    "issue_id",
    "verdict",
    "next_action",
    "next_action_raw",
    "coerced",
    "blast",
    "feedback",
    "feedback_source",
    "violations",
    "test_integrity",
    "failure_kind",
}


def _verdict_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in records if row.get("event") != "cycle_end"]


def _cycle_end_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in records if row.get("event") == "cycle_end"]


def _assert_jsonl_not_transcript(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"expected JSONL at {path}"
    for line in text.splitlines():
        if not line.strip():
            continue
        assert not line.startswith("["), (
            f"verdicts file must be JSONL, not the run transcript format; got {line!r}"
        )
        obj = json.loads(line)
        assert isinstance(obj, dict), f"each JSONL line must be an object: {line!r}"
        assert "AGENT_RAW_OUTPUT" not in obj
        assert "prompt" not in obj
        assert "raw_output" not in obj


class TestApplyJudgeVerdictWritesVerdictsJsonl:
    """Unit: ``_apply_judge_verdict`` is the shared auto / ``judge post`` writer."""

    def test_gh158_pass_plus_note_blast_none_and_refactor_note(
        self, tmp_git_repo: Path
    ) -> None:
        _apply(tmp_git_repo, _manifest(next_action="revert_red"))
        path = verdicts_path(tmp_git_repo, _ISSUE_ID, _TASK_ID)
        assert path.exists(), f"expected verdicts JSONL at {path}"
        _assert_jsonl_not_transcript(path)
        rows = _verdict_rows(load_verdicts(tmp_git_repo, _ISSUE_ID, _TASK_ID))
        assert len(rows) == 1, f"one JUDGE application, got {rows!r}"
        row = rows[0]
        assert _VERDICT_KEYS <= set(row)
        assert row["task_id"] == _TASK_ID
        assert row["issue_id"] == _ISSUE_ID
        assert row["verdict"] == "COMPLIANCE_PASS"
        assert row["next_action"] == "continue_refactor"
        assert row["next_action_raw"] == "revert_red"
        assert row["coerced"] is True
        assert row["blast"] == "none"
        assert "REFACTOR NOTE" in str(row["feedback"])
        assert _NOTE.split(":")[0] in str(row["feedback"]) or _NOTE in str(
            row["feedback"]
        )
        assert row["violations"] == []
        assert row["test_integrity"] is None

    def test_compliance_fail_revert_green_blast_green(self, tmp_git_repo: Path) -> None:
        feedback = (
            "COMPLIANCE_FAIL: missing behavior. "
            "The next GREEN attempt must: implement the error path."
        )
        _apply(
            tmp_git_repo,
            _manifest(
                verdict="COMPLIANCE_FAIL",
                next_action="revert_green",
                train_feedback=feedback,
            ),
        )
        rows = _verdict_rows(load_verdicts(tmp_git_repo, _ISSUE_ID, _TASK_ID))
        assert len(rows) == 1, rows
        row = rows[0]
        assert row["verdict"] == "COMPLIANCE_FAIL"
        assert row["next_action"] == "revert_green"
        assert row["next_action_raw"] == "revert_green"
        assert row["coerced"] is False
        assert row["blast"] == "green"
        assert str(row["feedback"]).strip(), "reject feedback must be non-empty"
        assert "missing behavior" in str(row["feedback"])

    def test_test_integrity_after_green_pass_coerces_to_red(
        self, tmp_git_repo: Path
    ) -> None:
        _apply(
            tmp_git_repo,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_green",
                train_feedback=(
                    "The next RED attempt must: author a test that "
                    "actually validates the AC."
                ),
                extra={
                    "violations": [
                        {
                            "category": "Test Integrity Violation",
                            "file": "tests/test_feature.py",
                            "detail": "assert True",
                            "severity": "CRITICAL",
                            "recommendation": "Assert the AC.",
                        }
                    ],
                    "evaluation": {"test_integrity": "FAIL"},
                },
            ),
        )
        rows = _verdict_rows(load_verdicts(tmp_git_repo, _ISSUE_ID, _TASK_ID))
        assert len(rows) == 1, rows
        row = rows[0]
        assert row["blast"] == "red"
        assert row["next_action"] == "revert_red"
        assert row["next_action_raw"] == "revert_green"
        assert row["coerced"] is True
        assert "Test Integrity Violation" in row["violations"]
        assert row["test_integrity"] == "FAIL"
        assert str(row["feedback"]).strip()


class TestCycleDriverVerdictsAndCycleEnd:
    """Cycle driver: verdicts.jsonl + CYCLE_END on auto ``_run_tdd_cycle``."""

    def test_gh158_cycle_writes_jsonl_and_cycle_end(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        result = run_scripted_cycle(
            seeded,
            gh158_steps(_TASK.task_id, ac=_TASK.ac, next_action="revert_red"),
            monkeypatch,
            mode="auto",
        )
        assert result.error is None, result.output
        path = verdicts_path(tmp_git_repo, seeded.issue_id, _TASK.task_id)
        assert path.exists(), f"expected {path}"
        _assert_jsonl_not_transcript(path)
        records = load_verdicts(tmp_git_repo, seeded.issue_id, _TASK.task_id)
        rows = _verdict_rows(records)
        assert len(rows) == 1, records
        row = rows[0]
        assert row["blast"] == "none"
        assert row["next_action"] == "continue_refactor"
        assert row["next_action_raw"] == "revert_red"
        assert row["coerced"] is True
        assert _REFACTOR_NOTE in str(row["feedback"]) or "REFACTOR NOTE" in str(
            row["feedback"]
        )

        assert result.cycle_ends, "CYCLE_END _log_run must fire when the cycle leaves"
        cycle_log = result.cycle_ends[-1]
        assert cycle_log["task_id"] == _TASK.task_id
        assert cycle_log["completed"] is True
        assert cycle_log["last_blast"] == "none"
        assert cycle_log["reject_count"] == 0
        assert "continue_refactor" in cycle_log["phase_decisions"]

        ends = _cycle_end_rows(records)
        assert len(ends) == 1, records
        end = ends[0]
        assert end["event"] == "cycle_end"
        assert end["task_id"] == _TASK.task_id
        assert end["completed"] is True
        assert end["reject_count"] == 0
        assert end["last_blast"] == "none"
        assert "continue_refactor" in end["phase_decisions"]

    def test_reject_then_continue_increments_reject_count(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        result = run_scripted_cycle(
            seeded,
            reject_then_pass_steps(_TASK.task_id, ac=_TASK.ac),
            monkeypatch,
            mode="auto",
        )
        assert result.error is None, result.output
        records = load_verdicts(tmp_git_repo, seeded.issue_id, _TASK.task_id)
        rows = _verdict_rows(records)
        assert len(rows) == 2, records
        assert rows[0]["blast"] == "green"
        assert rows[0]["next_action"] == "revert_green"
        assert str(rows[0]["feedback"]).strip()
        assert rows[1]["blast"] == "none"
        assert rows[1]["next_action"] == "continue_refactor"

        assert result.cycle_ends, result.output
        cycle_log = result.cycle_ends[-1]
        assert cycle_log["completed"] is True
        assert cycle_log["reject_count"] == 1
        assert cycle_log["last_blast"] == "none"
        assert "revert_green" in cycle_log["phase_decisions"]
        assert "continue_refactor" in cycle_log["phase_decisions"]

        ends = _cycle_end_rows(records)
        assert len(ends) == 1, records
        assert ends[0]["reject_count"] == 1
        assert ends[0]["completed"] is True
        assert ends[0]["last_blast"] == "none"

    def test_verdicts_file_is_jsonl_not_transcript(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        result = run_scripted_cycle(
            seeded,
            gh158_steps(_TASK.task_id, ac=_TASK.ac),
            monkeypatch,
            mode="auto",
        )
        assert result.error is None, result.output
        path = verdicts_path(tmp_git_repo, seeded.issue_id, _TASK.task_id)
        _assert_jsonl_not_transcript(path)
        transcript = (
            tmp_git_repo
            / ".deviate"
            / "logs"
            / seeded.issue_id
            / f"{_TASK.task_id}.log"
        )
        # Per-task transcript is optional here (cycle driver may not
        # install TaskLogger); when present it must stay a different file.
        assert path != transcript
        assert path.name.endswith(".verdicts.jsonl")
