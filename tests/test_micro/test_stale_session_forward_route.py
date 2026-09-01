"""GH-148: stale session forward-route must not skip GREEN/JUDGE.

``.deviate/session.json`` is gitignored and survives across tasks in a
worktree. A leftover ``pending_judge_action: skip_refactor`` (or
``continue_refactor`` / ``proceed_to_refactor_no_diff``) plus
``last_judge_verdict: COMPLIANCE_PASS`` / ``validated_evidence`` from
another task must not make ``_tdd_pre_green_decision`` return
``complete`` after this task's RED. Same-task skip_refactor from this
task's JUDGE, and ``--no-refactor`` after a fresh this-task pass, stay
forward routes. No ``SESSION_STALE`` HITL prompt. No new failure_kind.
"""

from __future__ import annotations

import io
import json
from contextlib import chdir
from pathlib import Path

import pytest
from rich.console import Console

from deviate.cli.micro import (
    PhaseFailedError,
    _apply_judge_verdict,
    _run_tdd_cycle,
    _tdd_pre_green_decision,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_A = "TSK-148-01"
_TASK_B = "TSK-148-02"
_ISSUE_ID = "ISS-148-001"
_STALE_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_RED_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_STALE_EVIDENCE = [
    {
        "ac": "AC-PLAN-002",
        "test_path": "test/meepleinn_web/live_runtime/route_reachability_test.exs",
        "test_quote": 'assert live(conn, ~p"/")',
        "impl_path": "lib/meepleinn_web.ex",
        "impl_quote": ("use Phoenix.LiveView, layout: {MeepleInnWeb.Layouts, :app}"),
    }
]


def _task(task_id: str, *, status: str = "PENDING") -> dict[str, str]:
    return {
        "id": task_id,
        "issue_id": _ISSUE_ID,
        "description": f"GH-148 {task_id}",
        "status": status,
        "execution_mode": "TDD",
    }


def _write_ledger(path: Path, *records: TaskRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.model_dump_json() + "\n")


def _seed_repo(root: Path, *, task_id: str, status: str = "PENDING") -> Path:
    import subprocess

    source = "specs/148-stale-session/issues/001-forward-route.md"
    issue_md = root / source
    issue_md.parent.mkdir(parents=True)
    issue_md.write_text("# GH-148 stale forward-route\n", encoding="utf-8")
    workspace = root / "specs" / "148-stale-session" / "001-forward-route"
    workspace.mkdir(parents=True)
    (workspace / "tasks.md").write_text(
        f"- [ ] {task_id}: GH-148 slice\n",
        encoding="utf-8",
    )
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": _ISSUE_ID, "source_file": source}) + "\n",
        encoding="utf-8",
    )
    (root / "specs" / "constitution.md").write_text(
        "# constitution\n", encoding="utf-8"
    )
    ledger_path = workspace / "tasks.jsonl"
    _write_ledger(
        ledger_path,
        TaskRecord(
            id=task_id,
            issue_id=_ISSUE_ID,
            description="GH-148 slice",
            status=status,
            execution_mode="TDD",
        ),
    )
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: seed GH-148 meso artifacts"],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    return ledger_path


def _poison_session(
    root: Path,
    *,
    red_commit_sha: str = _STALE_SHA,
    pending: str = "skip_refactor",
    judge_task_id: str = "",
    judge_red_commit_sha: str = "",
) -> Path:
    session = SessionState(
        current_phase="RED",
        active_issue_id=_ISSUE_ID,
        last_command=f"micro run {_TASK_B}",
        pending_judge_action=pending,
        red_commit_sha=red_commit_sha,
        last_judge_verdict="COMPLIANCE_PASS",
        validated_evidence=list(_STALE_EVIDENCE),
        judge_task_id=judge_task_id,
        judge_red_commit_sha=judge_red_commit_sha,
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    return session_path


def _bind_this_task_skip(
    root: Path,
    *,
    task_id: str,
    red_commit_sha: str,
) -> Path:
    session = SessionState(
        current_phase="GREEN",
        active_issue_id=_ISSUE_ID,
        last_command=f"micro run {task_id}",
        pending_judge_action="skip_refactor",
        red_commit_sha=red_commit_sha,
        last_judge_verdict="COMPLIANCE_PASS",
        judge_task_id=task_id,
        judge_red_commit_sha=red_commit_sha,
        validated_evidence=[],
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    return session_path


def _install_cycle_stubs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_git_repo: Path,
    *,
    red_sha: str = _RED_SHA,
    judge_action: str = "skip_refactor",
    apply_real_judge: bool = False,
    ledger_path: Path | None = None,
) -> list[str]:
    call_log: list[str] = []

    def _red(*args: object, **_kwargs: object) -> SessionState:
        call_log.append("RED")
        session_path = args[3]
        assert isinstance(session_path, Path)
        current = SessionState.load(session_path)
        current.red_commit_sha = red_sha
        current.current_phase = "RED"
        current.save(session_path)
        return current

    def _green(*args: object, **_kwargs: object) -> SessionState:
        call_log.append("GREEN")
        session_path = args[3]
        assert isinstance(session_path, Path)
        current = SessionState.load(session_path)
        current.current_phase = "GREEN"
        current.failure_kind = ""
        current.train_feedback = ""
        current.save(session_path)
        return current

    def _judge(*args: object, **kwargs: object) -> SessionState:
        call_log.append("JUDGE")
        session_path = args[3]
        assert isinstance(session_path, Path)
        current = SessionState.load(session_path)
        if apply_real_judge:
            assert ledger_path is not None
            manifest = HandoverManifest.model_construct(
                phase="JUDGE",
                status="PASS",
                task_id=_TASK_B,
                verdict="COMPLIANCE_PASS",
                next_action=judge_action,
                rationale="",
                train_feedback="",
            )
            buf = io.StringIO()
            console = Console(file=buf, force_terminal=False, width=200)
            with chdir(tmp_git_repo):
                return _apply_judge_verdict(
                    _task(_TASK_B, status="GREEN"),
                    ledger_path,
                    current,
                    session_path,
                    console,
                    manifest,
                    injected_diff="",
                    no_refactor=bool(kwargs.get("no_refactor")),
                )
        current.judge_rejected = False
        current.pending_judge_action = judge_action
        current.last_judge_verdict = "COMPLIANCE_PASS"
        current.judge_task_id = _TASK_B
        current.judge_red_commit_sha = current.red_commit_sha
        current.train_feedback = ""
        current.failure_kind = ""
        current.validated_evidence = []
        current.save(session_path)
        return current

    def _refactor(*args: object, **_kwargs: object) -> SessionState:
        call_log.append("REFACTOR")
        session = args[2]
        assert isinstance(session, SessionState)
        session.pending_judge_action = ""
        return session.force_transition_to("IDLE")

    def _finish(*args: object, **_kwargs: object) -> SessionState:
        call_log.append("FINISH")
        session = args[2]
        assert isinstance(session, SessionState)
        if session.validated_evidence == _STALE_EVIDENCE:
            raise PhaseFailedError(
                "COMPLETED_EVIDENCE_MISSING: JUDGE evidence is missing, "
                "empty, or partial for injected acceptance tokens: "
                "AC-PLAN-001, AC-PLAN-003"
            )
        return session

    monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
    monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
    monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
    monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)
    monkeypatch.setattr("deviate.cli.micro._finish_tdd_cycle", _finish)
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *_a, **_k: None
    )
    return call_log


class TestTddPreGreenStaleForwardRoute:
    """Unbound or cross-task forward routes must not complete."""

    def test_unbound_skip_refactor_with_red_sha_is_green(self) -> None:
        session = SessionState(
            pending_judge_action="skip_refactor",
            last_judge_verdict="COMPLIANCE_PASS",
            red_commit_sha=_RED_SHA,
            validated_evidence=list(_STALE_EVIDENCE),
        )
        assert _tdd_pre_green_decision(session, task_id=_TASK_B) == "green"
        assert session.pending_judge_action == ""
        assert session.last_judge_verdict == ""
        assert session.validated_evidence == []

    def test_foreign_task_skip_refactor_is_green(self) -> None:
        session = SessionState(
            pending_judge_action="skip_refactor",
            last_judge_verdict="COMPLIANCE_PASS",
            red_commit_sha=_RED_SHA,
            judge_task_id=_TASK_A,
            judge_red_commit_sha=_STALE_SHA,
            validated_evidence=list(_STALE_EVIDENCE),
        )
        assert _tdd_pre_green_decision(session, task_id=_TASK_B) == "green"
        assert session.pending_judge_action == ""
        assert session.validated_evidence == []

    def test_sha_mismatch_skip_refactor_is_green(self) -> None:
        session = SessionState(
            pending_judge_action="continue_refactor",
            last_judge_verdict="COMPLIANCE_PASS",
            red_commit_sha=_RED_SHA,
            judge_task_id=_TASK_B,
            judge_red_commit_sha=_STALE_SHA,
        )
        assert _tdd_pre_green_decision(session, task_id=_TASK_B) == "green"
        assert session.pending_judge_action == ""

    def test_this_task_skip_refactor_still_completes(self) -> None:
        session = SessionState(
            pending_judge_action="skip_refactor",
            last_judge_verdict="COMPLIANCE_PASS",
            red_commit_sha=_RED_SHA,
            judge_task_id=_TASK_B,
            judge_red_commit_sha=_RED_SHA,
        )
        assert _tdd_pre_green_decision(session, task_id=_TASK_B) == "complete"
        assert session.pending_judge_action == "skip_refactor"

    def test_unbound_skip_refactor_without_red_sha_still_completes(self) -> None:
        """no_failing_test stubs set skip_refactor with an empty SHA."""
        session = SessionState(
            pending_judge_action="skip_refactor",
            last_judge_verdict="COMPLIANCE_PASS",
            red_commit_sha="",
        )
        assert _tdd_pre_green_decision(session, task_id=_TASK_B) == "complete"


class TestTddCycleStaleForwardRoute:
    """Canned RED then a second task must enter GREEN, not finish."""

    def test_canned_red_on_second_task_enters_green(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _seed_repo(tmp_git_repo, task_id=_TASK_B, status="PENDING")
        _poison_session(tmp_git_repo, red_commit_sha=_STALE_SHA)
        call_log = _install_cycle_stubs(monkeypatch, tmp_git_repo)

        with chdir(tmp_git_repo):
            _run_tdd_cycle(
                _task(_TASK_B),
                ledger,
                Console(file=io.StringIO(), force_terminal=False),
            )

        assert "GREEN" in call_log, (
            f"GH-148: TSK-B after canned RED must enter GREEN; got {call_log!r}"
        )
        assert "JUDGE" in call_log, (
            f"GH-148: TSK-B after canned RED must enter JUDGE; got {call_log!r}"
        )
        assert call_log.index("GREEN") < call_log.index("JUDGE")
        assert "FINISH" in call_log
        assert call_log.index("GREEN") < call_log.index("FINISH")

    def test_resume_after_red_with_poisoned_session_enters_green(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _seed_repo(tmp_git_repo, task_id=_TASK_B, status="RED")
        _poison_session(tmp_git_repo, red_commit_sha=_RED_SHA)
        call_log = _install_cycle_stubs(monkeypatch, tmp_git_repo)

        with chdir(tmp_git_repo):
            _run_tdd_cycle(
                _task(_TASK_B, status="RED"),
                ledger,
                Console(file=io.StringIO(), force_terminal=False),
                start_phase="GREEN",
            )

        assert call_log[0] == "GREEN", (
            f"GH-148: GREEN-resume must not finish on stale skip_refactor; "
            f"got {call_log!r}"
        )
        assert "JUDGE" in call_log
        assert "FINISH" in call_log

    def test_same_task_skip_refactor_still_skips_refactor(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _seed_repo(tmp_git_repo, task_id=_TASK_B, status="GREEN")
        _bind_this_task_skip(tmp_git_repo, task_id=_TASK_B, red_commit_sha=_RED_SHA)
        call_log = _install_cycle_stubs(monkeypatch, tmp_git_repo)

        with chdir(tmp_git_repo):
            _run_tdd_cycle(
                _task(_TASK_B, status="GREEN"),
                ledger,
                Console(file=io.StringIO(), force_terminal=False),
                start_phase="GREEN",
            )

        assert "GREEN" not in call_log, (
            f"GH-148: this-task skip_refactor must not re-enter GREEN; got {call_log!r}"
        )
        assert "JUDGE" not in call_log
        assert "REFACTOR" not in call_log
        assert call_log == ["FINISH"]

    def test_no_refactor_after_this_task_judge_still_completes(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ledger = _seed_repo(tmp_git_repo, task_id=_TASK_B, status="GREEN")
        session = SessionState(
            current_phase="GREEN",
            active_issue_id=_ISSUE_ID,
            red_commit_sha=_RED_SHA,
        )
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        call_log = _install_cycle_stubs(
            monkeypatch,
            tmp_git_repo,
            apply_real_judge=True,
            ledger_path=ledger,
            judge_action="skip_refactor",
        )

        with chdir(tmp_git_repo):
            _run_tdd_cycle(
                _task(_TASK_B, status="GREEN"),
                ledger,
                Console(file=io.StringIO(), force_terminal=False),
                start_phase="GREEN",
                no_refactor=True,
            )

        assert call_log == ["GREEN", "JUDGE", "FINISH"], (
            f"GH-148: --no-refactor after this-task JUDGE must complete; "
            f"got {call_log!r}"
        )
        persisted = SessionState.load(session_path)
        assert persisted.judge_task_id == _TASK_B
        assert persisted.judge_red_commit_sha == _RED_SHA


class TestApplyJudgeVerdictStampsForwardRoute:
    """JUDGE forward routes bind task id + RED SHA for later resume."""

    def test_skip_refactor_records_judge_context(self, tmp_git_repo: Path) -> None:
        ledger = _seed_repo(tmp_git_repo, task_id=_TASK_B, status="GREEN")
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        SessionState(
            current_phase="GREEN",
            active_issue_id=_ISSUE_ID,
            red_commit_sha=_RED_SHA,
        ).save(session_path)
        session = SessionState.load(session_path)
        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="PASS",
            task_id=_TASK_B,
            verdict="COMPLIANCE_PASS",
            next_action="skip_refactor",
            rationale="",
            train_feedback="",
        )
        buf = io.StringIO()
        with chdir(tmp_git_repo):
            session = _apply_judge_verdict(
                _task(_TASK_B, status="GREEN"),
                ledger,
                session,
                session_path,
                Console(file=buf, force_terminal=False, width=200),
                manifest,
                injected_diff="",
                no_refactor=True,
            )
        assert session.judge_task_id == _TASK_B
        assert session.judge_red_commit_sha == _RED_SHA
        assert session.pending_judge_action == "skip_refactor"
