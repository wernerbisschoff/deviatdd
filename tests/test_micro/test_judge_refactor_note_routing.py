"""GH-158: COMPLIANCE_PASS + REFACTOR NOTE is advice, not a reject.

A passing JUDGE verdict that also emits ``REFACTOR NOTE:`` must forward
to REFACTOR (``continue_refactor``, or ``skip_refactor`` when
``--no-refactor``). The note is injected into the REFACTOR prompt via
``train_feedback``. It must not set ``JUDGE_REJECTED``,
``revert_red`` / ``revert_green`` / legacy ``revert_to_red``, or send
the ledger back to RED.

A mislabeled ``COMPLIANCE_VIOLATION`` + ``revert_green`` whose
``train_feedback`` is only a ``REFACTOR NOTE:`` (unused import, warning,
style) is the same advice after GREEN's suite is green. Structured Test
Integrity (GH-149) and real spec/compliance failures still revert.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import chdir
from pathlib import Path
import pytest
from rich.console import Console

from deviate.cli.micro import (
    _GREEN_TEST_FAILURE_PREFIX,
    _apply_judge_verdict,
    _build_auto_prompt,
    _coerce_judge_action,
    _feedback_is_refactor_only,
    _verdict_is_clean_pass,
)
from deviate.core.agent import AgentBackend, HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_ID = "TSK-158-01"
_ISSUE_ID = "ISS-158-001"
_NOTE = (
    "REFACTOR NOTE: The root layout is implemented as a function "
    "component root/1 in layouts.ex rather than a separate "
    "root.html.heex template file."
)
_PASS_FEEDBACK = "COMPLIANCE_PASS: No correctness issues.\n\n" + _NOTE
# Live MeepleInn TSK-002-01 shape: unused-import note labeled as a violation.
_LIVE_UNUSED_IMPORT_NOTE = (
    "REFACTOR NOTE: unused import of Phoenix.ConnTest in "
    "test/meepleinn_web/layouts_test.exs; assertions use "
    "render_component only, producing an unused-import warning "
    "at compile time"
)
_SPEC_GAP_FEEDBACK = (
    "COMPLIANCE_VIOLATION: missing AC-PLAN-001 behavior. "
    "The next GREEN attempt must: implement the error path."
)


def _task() -> dict[str, str]:
    return {
        "id": _TASK_ID,
        "issue_id": _ISSUE_ID,
        "description": "GH-158 pass plus refactor note",
        "status": "GREEN",
        "execution_mode": "TDD",
    }


def _write_ledger(path: Path, *records: TaskRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.model_dump_json() + "\n")


def _ledger_statuses(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        json.loads(line).get("status", "")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _seed_green_repo(root: Path) -> tuple[str, Path]:
    """Seed meso artifacts, a RED commit, a GREEN commit, and session."""
    import subprocess

    source = "specs/158-refactor-note/issues/001-pass-note.md"
    issue_md = root / source
    issue_md.parent.mkdir(parents=True)
    issue_md.write_text("# GH-158 pass-note issue\n", encoding="utf-8")
    workspace = root / "specs" / "158-refactor-note" / "001-pass-note"
    workspace.mkdir(parents=True)
    (workspace / "tasks.md").write_text(
        f"- [ ] {_TASK_ID}: Pass plus refactor note\n", encoding="utf-8"
    )
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": _ISSUE_ID, "source_file": source}) + "\n",
        encoding="utf-8",
    )
    (root / "specs" / "constitution.md").write_text(
        "# constitution\n", encoding="utf-8"
    )
    gitignore = root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        if ".deviate/" not in text.splitlines():
            gitignore.write_text(text.rstrip() + "\n.deviate/\n", encoding="utf-8")
    else:
        gitignore.write_text(".deviate/\n", encoding="utf-8")
    ledger_path = workspace / "tasks.jsonl"
    _write_ledger(
        ledger_path,
        TaskRecord(
            id=_TASK_ID,
            issue_id=_ISSUE_ID,
            description="Pass plus refactor note",
            status="GREEN",
            execution_mode="TDD",
        ),
    )
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: seed meso artifacts"],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    (root / "feature.py").write_text("def feature(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"test({_TASK_ID}): RED phase"],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    red_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()
    (root / "impl.py").write_text("def impl(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({_TASK_ID}): GREEN phase"],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    session = SessionState(
        active_issue_id=_ISSUE_ID,
        current_phase="GREEN",
        red_commit_sha=red_sha,
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    return red_sha, ledger_path


def _manifest(
    *,
    verdict: str = "COMPLIANCE_PASS",
    next_action: str | None = None,
    train_feedback: str = _PASS_FEEDBACK,
    extra: dict[str, object] | None = None,
    **kwargs: object,
) -> HandoverManifest:
    payload: dict[str, object] = {
        "phase": "JUDGE",
        "status": "PASS",
        "task_id": _TASK_ID,
        "verdict": verdict,
        "rationale": "",
        "train_feedback": train_feedback,
        **kwargs,
    }
    if next_action is not None:
        payload["next_action"] = next_action
    if extra:
        payload.update(extra)
    return HandoverManifest.model_construct(**payload)


def _apply(
    root: Path,
    manifest: HandoverManifest,
    *,
    no_refactor: bool = False,
) -> tuple[SessionState, str, Path]:
    _red_sha, ledger_path = _seed_green_repo(root)
    session_path = root / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    with chdir(root):
        session = _apply_judge_verdict(
            _task(),
            ledger_path,
            session,
            session_path,
            console,
            manifest,
            injected_diff="",
            no_refactor=no_refactor,
        )
    return session, buf.getvalue(), ledger_path


def _head_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


class TestFeedbackIsRefactorOnly:
    """``_feedback_is_refactor_only`` pins the live unused-import body."""

    def test_live_unused_import_note(self) -> None:
        assert _feedback_is_refactor_only(_LIVE_UNUSED_IMPORT_NOTE) is True

    def test_compliance_pass_preamble_plus_note(self) -> None:
        assert _feedback_is_refactor_only(_PASS_FEEDBACK) is True

    def test_spec_gap_is_not_refactor_only(self) -> None:
        assert _feedback_is_refactor_only(_SPEC_GAP_FEEDBACK) is False

    def test_empty_is_not_refactor_only(self) -> None:
        assert _feedback_is_refactor_only("") is False


class TestCoercePassPlusRefactorNote:
    """``_coerce_judge_action`` must not honor revert on a clean PASS."""

    def test_pass_plus_note_ignores_revert_red(self) -> None:
        manifest = _manifest(next_action="revert_red")
        result = _coerce_judge_action(manifest, "COMPLIANCE_PASS")
        assert result not in {"revert_red", "revert_green", "revert_to_red"}, (
            f"GH-158: COMPLIANCE_PASS + REFACTOR NOTE must not coerce to "
            f"a revert; got {result!r}"
        )

    def test_pass_plus_note_ignores_legacy_revert_to_red(self) -> None:
        manifest = _manifest(next_action="revert_to_red")
        result = _coerce_judge_action(manifest, "COMPLIANCE_PASS")
        assert result not in {"revert_red", "revert_green", "revert_to_red"}, (
            f"GH-158: legacy revert_to_red on COMPLIANCE_PASS must not "
            f"win; got {result!r}"
        )

    def test_pass_without_note_still_forwards(self) -> None:
        manifest = _manifest(train_feedback="", next_action=None)
        result = _coerce_judge_action(manifest, "COMPLIANCE_PASS")
        assert result not in {"revert_red", "revert_green", "revert_to_red"}

    def test_compliance_fail_still_reverts(self) -> None:
        manifest = _manifest(
            verdict="COMPLIANCE_FAIL",
            next_action="revert_green",
            train_feedback="COMPLIANCE_FAIL: spec gap. The next GREEN attempt must: fix it.",
        )
        result = _coerce_judge_action(manifest, "COMPLIANCE_FAIL")
        assert result == "revert_green", (
            f"GH-158: COMPLIANCE_FAIL must still revert; got {result!r}"
        )

    def test_compliance_violation_without_action_still_reverts(self) -> None:
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action=None,
            train_feedback="The next GREEN attempt must: implement the missing path.",
        )
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION")
        assert result == "revert_green"

    def test_gh149_test_integrity_after_green_pass_stays_revert_red(self) -> None:
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback="The next RED attempt must: author an honest test.",
            extra={
                "violations": [
                    {
                        "category": "Test Integrity Violation",
                        "file": "tests/test_feature.py",
                        "detail": "assert True",
                        "severity": "CRITICAL",
                        "recommendation": "Assert the AC.",
                    }
                ]
            },
        )
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION", failure_kind="")
        assert result == "revert_red", (
            f"GH-149: Test Integrity after GREEN PASS must stay "
            f"revert_red; got {result!r}"
        )

    def test_violation_plus_unused_import_note_drops_revert_green(self) -> None:
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback=_LIVE_UNUSED_IMPORT_NOTE,
        )
        assert _verdict_is_clean_pass("COMPLIANCE_VIOLATION", manifest) is True
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION")
        assert result not in {"revert_red", "revert_green", "revert_to_red"}, (
            f"refactor-only COMPLIANCE_VIOLATION must drop revert_green; "
            f"got {result!r}"
        )

    def test_real_spec_violation_still_reverts(self) -> None:
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback=_SPEC_GAP_FEEDBACK,
        )
        assert _verdict_is_clean_pass("COMPLIANCE_VIOLATION", manifest) is False
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION")
        assert result == "revert_green"


class TestApplyPassPlusRefactorNote:
    """``_apply_judge_verdict`` forwards a pass+note and keeps the note
    for REFACTOR only."""

    def test_pass_plus_note_forwards_and_keeps_note(self, tmp_git_repo: Path) -> None:
        session, output, ledger = _apply(
            tmp_git_repo,
            _manifest(next_action="revert_red"),
        )
        assert "JUDGE_REJECTED" not in output, output
        assert session.judge_rejected is False
        assert session.pending_judge_action == "continue_refactor"
        assert session.current_phase != "RED"
        assert _NOTE in session.train_feedback
        statuses = _ledger_statuses(ledger)
        assert "RED" not in statuses
        assert "JUDGE" in statuses or "COMPLETED" not in statuses

    def test_pass_without_note_still_forwards(self, tmp_git_repo: Path) -> None:
        session, output, ledger = _apply(
            tmp_git_repo,
            _manifest(train_feedback="", next_action=None),
        )
        assert "JUDGE_REJECTED" not in output, output
        assert session.judge_rejected is False
        assert session.pending_judge_action == "continue_refactor"
        assert "RED" not in _ledger_statuses(ledger)

    def test_no_refactor_skips(self, tmp_git_repo: Path) -> None:
        session, output, _ledger = _apply(
            tmp_git_repo,
            _manifest(next_action=None),
            no_refactor=True,
        )
        assert "JUDGE_REJECTED" not in output, output
        assert session.pending_judge_action == "skip_refactor"
        assert session.judge_rejected is False

    def test_legacy_revert_to_red_in_payload_does_not_win(
        self, tmp_git_repo: Path
    ) -> None:
        yaml_text = (
            "phase: JUDGE\n"
            "status: PASS\n"
            f"task_id: {_TASK_ID}\n"
            'verdict: "COMPLIANCE_PASS"\n'
            "next_action: revert_to_red\n"
            "train_feedback: |\n"
            "  COMPLIANCE_PASS: No correctness issues.\n"
            "\n"
            f"  {_NOTE}\n"
        )
        parsed = AgentBackend.parse_output(yaml_text, "cli")
        session, output, ledger = _apply(tmp_git_repo, parsed)
        assert "JUDGE_REJECTED" not in output, output
        assert session.pending_judge_action == "continue_refactor"
        assert session.judge_rejected is False
        assert _NOTE in session.train_feedback
        assert "RED" not in _ledger_statuses(ledger)

    def test_refactor_prompt_contains_note(self, tmp_git_repo: Path) -> None:
        session, _output, _ledger = _apply(
            tmp_git_repo,
            _manifest(next_action="continue_refactor"),
        )
        with chdir(tmp_git_repo):
            prompt = _build_auto_prompt(
                "refactor",
                _task(),
                tmp_git_repo,
                train_feedback=session.train_feedback,
            )
        assert _NOTE in prompt
        assert "<train_feedback>" in prompt

    def test_note_is_not_green_or_red_feedback(self, tmp_git_repo: Path) -> None:
        session, _output, _ledger = _apply(
            tmp_git_repo,
            _manifest(next_action="revert_red"),
        )
        assert session.pending_judge_action == "continue_refactor"
        assert session.current_phase != "GREEN"
        assert session.current_phase != "RED"
        with chdir(tmp_git_repo):
            green = _build_auto_prompt(
                "green",
                _task(),
                tmp_git_repo,
                train_feedback="",
            )
            red = _build_auto_prompt(
                "red",
                _task(),
                tmp_git_repo,
                train_feedback="",
            )
        assert _NOTE not in green
        assert _NOTE not in red

    def test_compliance_fail_still_rejects(self, tmp_git_repo: Path) -> None:
        session, output, ledger = _apply(
            tmp_git_repo,
            _manifest(
                verdict="COMPLIANCE_FAIL",
                next_action="revert_green",
                train_feedback=(
                    "COMPLIANCE_FAIL: missing behavior. "
                    "The next GREEN attempt must: implement the error path."
                ),
            ),
        )
        assert "JUDGE_REJECTED" in output, output
        assert session.judge_rejected is True
        assert session.pending_judge_action == "revert_green"
        assert session.current_phase == "GREEN"

    def test_test_integrity_still_reverts_red(self, tmp_git_repo: Path) -> None:
        session, output, _ledger = _apply(
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
                    ]
                },
            ),
        )
        assert "JUDGE_REJECTED" in output, output
        assert session.pending_judge_action == "revert_red"
        assert session.current_phase == "RED"

    def test_violation_plus_unused_import_note_keeps_green(
        self, tmp_git_repo: Path
    ) -> None:
        """Live TSK-002-01 shape: suite green + VIOLATION + revert_green
        + ``REFACTOR NOTE: unused import`` → continue_refactor, GREEN kept.
        """
        red_sha, ledger = _seed_green_repo(tmp_git_repo)
        green_sha = _head_sha(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback=_LIVE_UNUSED_IMPORT_NOTE,
        )
        with chdir(tmp_git_repo):
            session = _apply_judge_verdict(
                _task(),
                ledger,
                session,
                session_path,
                console,
                manifest,
                injected_diff="",
            )
        output = buf.getvalue()
        assert "JUDGE_REJECTED" not in output, output
        assert session.judge_rejected is False
        assert session.pending_judge_action == "continue_refactor"
        assert session.current_phase != "RED"
        assert session.current_phase != "GREEN"
        assert _LIVE_UNUSED_IMPORT_NOTE in session.train_feedback
        assert "RED" not in _ledger_statuses(ledger)
        assert _head_sha(tmp_git_repo) == green_sha, (
            "GREEN commit must be kept; harness must not reset to "
            f"{red_sha[:7]}"
        )
        assert (tmp_git_repo / "impl.py").exists()

    def test_violation_plus_note_no_refactor_skips(
        self, tmp_git_repo: Path
    ) -> None:
        session, output, ledger = _apply(
            tmp_git_repo,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_green",
                train_feedback=_LIVE_UNUSED_IMPORT_NOTE,
            ),
            no_refactor=True,
        )
        assert "JUDGE_REJECTED" not in output, output
        assert session.pending_judge_action == "skip_refactor"
        assert session.judge_rejected is False
        assert "RED" not in _ledger_statuses(ledger)

    def test_suite_still_red_does_not_continue_refactor(
        self, tmp_git_repo: Path
    ) -> None:
        """GREEN TEST_FAILURE remap stays; do not polish a red suite."""
        _red_sha, ledger = _seed_green_repo(tmp_git_repo)
        green_sha = _head_sha(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.train_feedback = (
            f"{_GREEN_TEST_FAILURE_PREFIX}\n1 failed in layouts_test.exs"
        )
        session.failure_kind = ""
        session.save(session_path)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback=_LIVE_UNUSED_IMPORT_NOTE,
        )
        with chdir(tmp_git_repo):
            session = _apply_judge_verdict(
                _task(),
                ledger,
                session,
                session_path,
                console,
                manifest,
                injected_diff="",
            )
        assert session.pending_judge_action != "continue_refactor"
        assert session.current_phase == "GREEN"
        assert session.judge_rejected is False
        assert _head_sha(tmp_git_repo) == green_sha
        assert "COMPLETED" not in _ledger_statuses(ledger)

    def test_test_defect_overlay_still_reverts_red(
        self, tmp_git_repo: Path
    ) -> None:
        """``failure_kind=test_defect`` must keep revert_red even if the
        body looks like a REFACTOR NOTE."""
        _red_sha, ledger = _seed_green_repo(tmp_git_repo)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.failure_kind = "test_defect"
        session.save(session_path)
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        manifest = _manifest(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_green",
            train_feedback=_LIVE_UNUSED_IMPORT_NOTE,
        )
        with chdir(tmp_git_repo):
            session = _apply_judge_verdict(
                _task(),
                ledger,
                session,
                session_path,
                console,
                manifest,
                injected_diff="",
            )
        assert "JUDGE_REJECTED" in buf.getvalue()
        assert session.pending_judge_action == "revert_red"
        assert session.current_phase == "RED"

    def test_spec_violation_still_resets_green(self, tmp_git_repo: Path) -> None:
        session, output, ledger = _apply(
            tmp_git_repo,
            _manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_green",
                train_feedback=_SPEC_GAP_FEEDBACK,
            ),
        )
        assert "JUDGE_REJECTED" in output, output
        assert session.judge_rejected is True
        assert session.pending_judge_action == "revert_green"
        assert session.current_phase == "GREEN"
        assert "RED" in _ledger_statuses(ledger)


class TestJudgePromptRefactorNoteIsAdvice:
    """auto/judge.md must tell the model a REFACTOR NOTE is not a revert."""

    def test_prompt_says_note_is_not_a_revert(self) -> None:
        from importlib import resources

        text = resources.files("deviate.prompts.auto").joinpath("judge.md").read_text()
        assert "REFACTOR NOTE" in text
        assert "not a reason to revert" in text.lower() or (
            "not a reason to revert" in text
        )
        assert "continue_refactor" in text
        assert "skip_refactor" in text
        lowered = text.lower()
        assert "optional advice" in lowered or "optional" in lowered
        assert "unused import" in lowered
        assert "warning" in lowered
        assert "style" in lowered
        assert "never" in lowered and "compliance_violation" in lowered
        assert "$ARGUMENTS" not in text

    def test_manual_overlay_keeps_arguments_at_end(self) -> None:
        from importlib import resources

        text = (
            resources.files("deviate.prompts.commands")
            .joinpath("deviate-judge.md")
            .read_text()
        )
        assert text.rstrip().endswith("$ARGUMENTS") or "$ARGUMENTS" in text[-80:]
        assert text.rfind("$ARGUMENTS") > text.rfind("Manual Slash-Command Overlay")


class TestTddCyclePassPlusNoteDoesNotLoopRed:
    """A full TDD handoff must not re-enter RED after a pass+note JUDGE."""

    def test_tdd_cycle_forwards_to_refactor(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli.micro import _run_tdd_cycle

        _seed_green_repo(tmp_git_repo)
        call_log: list[str] = []
        captured_feedback: list[str] = []

        def _red(*_args: object, **_kwargs: object) -> SessionState:
            call_log.append("RED")
            raise AssertionError("GH-158: pass+note must not dispatch RED")

        def _green(*_args: object, **_kwargs: object) -> SessionState:
            call_log.append("GREEN")
            raise AssertionError("GH-158: pass+note must not dispatch GREEN")

        def _judge(*args: object, **kwargs: object) -> SessionState:
            call_log.append("JUDGE")
            session_path = args[3]
            assert isinstance(session_path, Path)
            current = SessionState.load(session_path)
            manifest = _manifest(next_action="revert_red")
            buf = io.StringIO()
            console = Console(file=buf, force_terminal=False, width=200)
            ledger = (
                tmp_git_repo
                / "specs"
                / "158-refactor-note"
                / "001-pass-note"
                / "tasks.jsonl"
            )
            with chdir(tmp_git_repo):
                return _apply_judge_verdict(
                    _task(),
                    ledger,
                    current,
                    session_path,
                    console,
                    manifest,
                    injected_diff="",
                )

        def _refactor(*args: object, **_kwargs: object) -> SessionState:
            call_log.append("REFACTOR")
            session = args[2]
            assert isinstance(session, SessionState)
            captured_feedback.append(session.train_feedback)
            session.pending_judge_action = ""
            return session.force_transition_to("IDLE")

        monkeypatch.setattr("deviate.cli.micro._run_red_phase", _red)
        monkeypatch.setattr("deviate.cli.micro._run_green_phase", _green)
        monkeypatch.setattr("deviate.cli.micro._run_judge_phase", _judge)
        monkeypatch.setattr("deviate.cli.micro._run_refactor_phase", _refactor)

        with chdir(tmp_git_repo):
            _run_tdd_cycle(
                _task(),
                tmp_git_repo
                / "specs"
                / "158-refactor-note"
                / "001-pass-note"
                / "tasks.jsonl",
                Console(file=io.StringIO(), force_terminal=False),
                start_phase="JUDGE",
            )

        assert call_log == ["JUDGE", "REFACTOR"], (
            f"GH-158: expected JUDGE→REFACTOR; got {call_log!r}"
        )
        assert captured_feedback and _NOTE in captured_feedback[0]
        ledger = (
            tmp_git_repo
            / "specs"
            / "158-refactor-note"
            / "001-pass-note"
            / "tasks.jsonl"
        )
        assert "RED" not in _ledger_statuses(ledger)
