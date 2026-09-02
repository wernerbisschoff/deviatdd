"""Per-task JUDGE verdicts JSONL + CYCLE_END postmortem (not AGENT_RAW_OUTPUT).

``_apply_judge_verdict`` writes one JSON object per JUDGE application
(pass and reject) to ``.deviate/logs/<issue>/<task>.verdicts.jsonl``.
``_run_tdd_cycle`` appends a ``cycle_end`` object to the same file and
emits a ``CYCLE_END`` ``_log_run`` event. The file is JSONL — not the
``[<ts>] EVENT`` transcript format.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from contextlib import chdir
from unittest.mock import patch

from rich.console import Console

from deviate.cli.micro import _apply_judge_verdict, _build_auto_prompt, _invoke_agent
from deviate.core.agent import AgentBackend, HandoverManifest
from deviate.core.run_logger import TaskLogger, set_task_logger
from deviate.prompts.assembly import AGENT_REASONS_BLOCK
from deviate.state.config import SessionState
from tests.helpers.cycle_driver import (
    _REFACTOR_NOTE,
    CycleTask,
    gh158_steps,
    load_verdicts,
    reject_then_pass_steps,
    run_scripted_cycle,
    seed_cycle_repo,
    two_revert_green_then_pass_steps,
    verdicts_path,
)
from tests.test_micro.test_judge_refactor_note_routing import (
    _ISSUE_ID,
    _NOTE,
    _TASK_ID,
    _apply,
    _manifest,
    _seed_green_repo,
    _task,
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
    "streak",
    "loop",
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


def _apply_existing(
    root: Path,
    ledger_path: Path,
    manifest: HandoverManifest,
    *,
    no_refactor: bool = False,
) -> SessionState:
    session_path = root / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    with chdir(root):
        return _apply_judge_verdict(
            _task(),
            ledger_path,
            session,
            session_path,
            console,
            manifest,
            injected_diff="",
            no_refactor=no_refactor,
        )


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
        assert row["streak"] == 0
        assert row["loop"] is False

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
        assert row["streak"] == 1
        assert row["loop"] is False

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
        assert row["streak"] == 1
        assert row["loop"] is False

    def test_two_revert_red_sets_loop_and_emits_loop_detected(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, ledger_path = _seed_green_repo(tmp_git_repo)
        reject = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_red",
            train_feedback="The next RED attempt must: author an honest test.",
        )
        logger = TaskLogger(tmp_git_repo, _ISSUE_ID, _TASK_ID)
        set_task_logger(logger)
        try:
            _apply_existing(tmp_git_repo, ledger_path, reject)
            session_path = tmp_git_repo / ".deviate" / "session.json"
            session = SessionState.load(session_path)
            session.red_commit_sha = red_sha
            session.current_phase = "GREEN"
            session.pending_judge_action = ""
            session.judge_rejected = False
            session.failure_kind = ""
            session.save(session_path)
            _apply_existing(tmp_git_repo, ledger_path, reject)
        finally:
            set_task_logger(None)
            logger.close()

        rows = _verdict_rows(load_verdicts(tmp_git_repo, _ISSUE_ID, _TASK_ID))
        assert len(rows) == 2, rows
        assert rows[0]["blast"] == "red"
        assert rows[0]["streak"] == 1
        assert rows[0]["loop"] is False
        assert rows[1]["blast"] == "red"
        assert rows[1]["streak"] == 2
        assert rows[1]["loop"] is True
        task_log = logger.log_file.read_text(encoding="utf-8")
        assert "LOOP_DETECTED" in task_log, task_log


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
        assert cycle_log["max_streak"] == 0
        assert "continue_refactor" in cycle_log["phase_decisions"]

        ends = _cycle_end_rows(records)
        assert len(ends) == 1, records
        end = ends[0]
        assert end["event"] == "cycle_end"
        assert end["task_id"] == _TASK.task_id
        assert end["completed"] is True
        assert end["reject_count"] == 0
        assert end["last_blast"] == "none"
        assert end["max_streak"] == 0
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
        assert cycle_log["max_streak"] == 1
        assert "revert_green" in cycle_log["phase_decisions"]
        assert "continue_refactor" in cycle_log["phase_decisions"]

        ends = _cycle_end_rows(records)
        assert len(ends) == 1, records
        assert ends[0]["reject_count"] == 1
        assert ends[0]["completed"] is True
        assert ends[0]["last_blast"] == "none"
        assert ends[0]["max_streak"] == 1

    def test_two_revert_green_sets_loop_and_max_streak(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        result = run_scripted_cycle(
            seeded,
            two_revert_green_then_pass_steps(_TASK.task_id, ac=_TASK.ac),
            monkeypatch,
            mode="auto",
        )
        assert result.error is None, result.output
        records = load_verdicts(tmp_git_repo, seeded.issue_id, _TASK.task_id)
        rows = _verdict_rows(records)
        assert len(rows) == 3, records
        assert rows[0]["blast"] == "green"
        assert rows[0]["streak"] == 1
        assert rows[0]["loop"] is False
        assert rows[1]["blast"] == "green"
        assert rows[1]["streak"] == 2
        assert rows[1]["loop"] is True
        assert rows[2]["blast"] == "none"
        assert rows[2]["loop"] is False
        assert result.loop_events, result.output
        assert result.loop_events[0]["streak"] == 2
        assert result.loop_events[0]["blast"] == "green"
        assert result.cycle_ends[-1]["max_streak"] == 2
        ends = _cycle_end_rows(records)
        assert ends[0]["max_streak"] == 2

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


class TestInvokeAgentTranscriptIsScannable:
    """INVOKE_AGENT / AGENT_RESULT stay short; raw stdout goes to a sidecar."""

    def test_transcript_omits_prompt_and_raw_stdout(self, tmp_path: Path) -> None:
        issue_id = "ISS-LOG-001"
        task_id = "TSK-LOG-01"
        prompt_body = "FULL PROMPT BODY secret-token-do-not-log"
        stdout_line = "agent-stdout-verbatim-line"
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        SessionState(active_issue_id=issue_id).save(session_path)
        logger = TaskLogger(tmp_path, issue_id, task_id)
        set_task_logger(logger)
        manifest = HandoverManifest(
            phase="RED", status="PASS", next_action="continue_refactor"
        )
        manifest.verdict = "COMPLIANCE_PASS"  # type: ignore[attr-defined]

        def fake_invoke(
            self: object, prompt: str, **kwargs: object
        ) -> HandoverManifest:
            callback = kwargs.get("output_callback")
            if callable(callback):
                callback(stdout_line)
            return manifest

        try:
            with (
                chdir(tmp_path),
                patch.object(AgentBackend, "invoke", new=fake_invoke),
            ):
                _invoke_agent(
                    prompt=prompt_body,
                    c=Console(file=io.StringIO()),
                    backend_name="pi",
                    task_id=task_id,
                    phase="RED",
                )
        finally:
            set_task_logger(None)
            logger.close()

        transcript = logger.log_file.read_text(encoding="utf-8")
        assert "INVOKE_AGENT" in transcript
        assert "AGENT_RESULT" in transcript
        assert "AGENT_RAW_OUTPUT" not in transcript
        assert prompt_body not in transcript
        assert "secret-token-do-not-log" not in transcript
        assert stdout_line not in transcript
        sidecar = (
            tmp_path / ".deviate" / "logs" / issue_id / f"{task_id}.raw" / "red-1.log"
        )
        assert sidecar.exists(), f"expected raw sidecar at {sidecar}"
        assert stdout_line in sidecar.read_text(encoding="utf-8")
        prompt_sidecar = sidecar.with_name("red-1.prompt.log")
        assert prompt_sidecar.exists()
        assert prompt_body in prompt_sidecar.read_text(encoding="utf-8")


class TestAgentReasonsPromptGate:
    """``[log].agent_reasons`` is off by default; on injects a rationale block."""

    def test_default_red_and_judge_prompts_do_not_ask_to_log(
        self, tmp_git_repo: Path
    ) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        red = _build_auto_prompt("red", seeded.task(), seeded.root)
        judge = _build_auto_prompt("judge", seeded.task(), seeded.root)
        for prompt in (red, judge):
            lowered = prompt.lower()
            assert "log your reasons" not in lowered
            assert "deviate log" not in lowered
            assert "write a reason file" not in lowered
            assert "one-line handover" not in prompt
            assert AGENT_REASONS_BLOCK.strip() not in prompt

    def test_flag_on_injects_rationale_block(self, tmp_git_repo: Path) -> None:
        seeded = seed_cycle_repo(tmp_git_repo, tasks=[_TASK])
        cfg = seeded.root / ".deviate" / "config.toml"
        cfg.write_text("[log]\nagent_reasons = true\n", encoding="utf-8")
        red = _build_auto_prompt("red", seeded.task(), seeded.root)
        judge = _build_auto_prompt("judge", seeded.task(), seeded.root)
        assert "one-line handover" in red
        assert "one-line handover" in judge
        assert "revert_red" in judge
        assert "revert_green" in judge
