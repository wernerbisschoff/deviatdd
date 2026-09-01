from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import PhaseFailedError, _run_green_phase
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()

_PREFIX_COLLISION_FEEDBACK = "PREFIX COLLISION FEEDBACK MUST NOT LEAK"
_NEIGHBOR_TASK_FEEDBACK = "NEIGHBOR TASK FEEDBACK MUST NOT LEAK"


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "GREEN phase task",
    status: str = "RED",
    execution_mode: str = "TDD",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description,
        status=status,
        execution_mode=execution_mode,
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


def _write_feedback_specs(root: Path, *target_feedback_lines: str) -> tuple[dict, Path]:
    issue_id = "ISS-ADH-042"
    source_file = "specs/adhoc/issues/042-auto-green-feedback.md"

    issue_path = root / source_file
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    issue_path.write_text("# Auto GREEN feedback regression\n", encoding="utf-8")
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": issue_id, "source_file": source_file}) + "\n",
        encoding="utf-8",
    )

    task_dir = root / "specs" / "adhoc" / "042-auto-green-feedback"
    task_dir.mkdir(parents=True, exist_ok=True)
    feedback_bullets = "\n".join(
        f"  - **Judge Feedback**: {line}" for line in target_feedback_lines
    )
    (task_dir / "tasks.md").write_text(
        "# Implementation Tasks: `feat/adhoc/042-auto-green-feedback`\n\n"
        "## Phase 1: Auto GREEN feedback\n\n"
        "- TSK-042-010: Prefix-collision decoy\n"
        f"  - **Judge Feedback**: {_PREFIX_COLLISION_FEEDBACK}\n\n"
        "- TSK-042-01: Consume persisted Judge feedback\n"
        f"{feedback_bullets}\n"
        "  - **Mode**: TDD\n\n"
        "- TSK-042-02: Unrelated neighboring task\n"
        f"  - **Judge Feedback**: {_NEIGHBOR_TASK_FEEDBACK}\n",
        encoding="utf-8",
    )

    record = _make_task_record(
        task_id="TSK-042-01",
        issue_id=issue_id,
        description="Consume persisted Judge feedback",
        status="RED",
    )
    ledger_path = task_dir / "tasks.jsonl"
    _write_ledger(ledger_path, record)
    return json.loads(record.model_dump_json()), ledger_path


def _capture_green_prompt(
    root: Path,
    task: dict,
    ledger_path: Path,
    *,
    session_feedback: str = "",
) -> str:
    session = SessionState(
        current_phase="RED",
        train_feedback=session_feedback,
        red_commit_sha="seed-red-boundary",
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    captured_prompts: list[str] = []

    def capture_agent_prompt(prompt: str, *args, **kwargs):
        captured_prompts.append(prompt)
        return (
            HandoverManifest(phase="GREEN", status="SUCCESS", task_id=task["id"]),
            "",
        )

    success = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with (
        chdir(root),
        patch("deviate.cli.micro._phase_already_done", return_value=False),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._invoke_agent", side_effect=capture_agent_prompt),
        patch("deviate.cli.micro._run_test_cmd", return_value=success),
        patch("deviate.cli.micro._run_format_cmd", return_value=success),
        patch("deviate.cli.micro.append_task_transition"),
        patch("deviate.cli.micro._commit_phase", return_value=True),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        _run_green_phase(task, ledger_path, session, session_path, Console(quiet=True))

    return captured_prompts[0]


class TestGreenPre:
    def test_green_pre_loads_red_task(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="GREEN test task",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_red_task.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            result = runner.invoke(cli, ["green", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "test_file" in data
            assert "implementation_targets" in data


class TestGreenPost:
    def test_green_post_validates_tests_pass(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RED", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="RED",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_green_task.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "green_impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("# GREEN implementation stub\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: RED test and GREEN implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            test_file.write_text("def test_pass():\n    assert True\n")
            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["green", "post"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )

            log = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
            )
            assert log.returncode == 0
            assert len(log.stdout.strip()) > 0


class TestGreenAutoPromptFeedback:
    def test_auto_green_uses_exact_persisted_judge_feedback_when_session_empty(
        self, tmp_path: Path
    ) -> None:
        feedback = "Keep the rollback atomic and restore the original exception."
        task, ledger_path = _write_feedback_specs(tmp_path, feedback)

        prompt = _capture_green_prompt(tmp_path, task, ledger_path)

        expected_line = f"- **Judge Feedback**: {feedback}"
        assert "<persisted_judge_feedback>" in prompt
        persisted_block = prompt.rsplit("<persisted_judge_feedback>", 1)[1].split(
            "</persisted_judge_feedback>", 1
        )[0]
        assert expected_line in persisted_block
        task_block = prompt.rsplit("<task_content>", 1)[1].split("</task_content>", 1)[
            0
        ]
        assert expected_line in task_block, (
            "GH-150: this-task card in <task_content> keeps Judge Feedback history"
        )
        assert prompt.count(expected_line) == 2, (
            "Judge Feedback belongs in <task_content> and <persisted_judge_feedback> "
            "only — not a third copy"
        )
        assert _PREFIX_COLLISION_FEEDBACK not in prompt
        assert _NEIGHBOR_TASK_FEEDBACK not in prompt

    def test_auto_green_prefers_session_feedback_without_persisted_duplicate(
        self, tmp_path: Path
    ) -> None:
        session_feedback = "Use the Judge-required transaction boundary."
        stale_persisted_feedback = "STALE PERSISTED FEEDBACK MUST NOT LEAK"
        task, ledger_path = _write_feedback_specs(
            tmp_path, session_feedback, stale_persisted_feedback
        )

        prompt = _capture_green_prompt(
            tmp_path,
            task,
            ledger_path,
            session_feedback=session_feedback,
        )

        assert f"<train_feedback>\n{session_feedback}\n</train_feedback>" in prompt
        assert "<persisted_judge_feedback>\n- **Judge Feedback**:" not in prompt
        task_block = prompt.rsplit("<task_content>", 1)[1].split("</task_content>", 1)[
            0
        ]
        assert session_feedback in task_block
        assert stale_persisted_feedback in task_block, (
            "GH-150: this-task card keeps persisted Judge Feedback history"
        )
        assert stale_persisted_feedback not in prompt.split("</task_content>", 1)[-1], (
            "stale persisted feedback must not leak outside the this-task card"
        )
        assert _PREFIX_COLLISION_FEEDBACK not in prompt
        assert _NEIGHBOR_TASK_FEEDBACK not in prompt

    def test_auto_green_feedback_retry_declares_rollback_clean_slate(
        self, tmp_path: Path
    ) -> None:
        feedback = "Create lib/guildwright/credo/check/render_only_tui.ex."
        task, ledger_path = _write_feedback_specs(tmp_path, feedback)
        session = SessionState(
            current_phase="GREEN",
            train_feedback=feedback,
            judge_rejected=True,
            pending_judge_action="revert_to_red",
            red_commit_sha="seed-red-boundary",
        )
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        captured_prompts: list[str] = []

        def capture_agent_prompt(prompt: str, *args, **kwargs):
            captured_prompts.append(prompt)
            return (
                HandoverManifest(phase="GREEN", status="SUCCESS", task_id=task["id"]),
                "",
            )

        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with (
            chdir(tmp_path),
            patch("deviate.cli.micro._phase_already_done", return_value=True),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._invoke_agent", side_effect=capture_agent_prompt),
            patch("deviate.cli.micro._run_test_cmd", return_value=success),
            patch("deviate.cli.micro._run_format_cmd", return_value=success),
            patch("deviate.cli.micro.append_task_transition"),
            patch("deviate.cli.micro._commit_phase", return_value=True),
            patch("deviate.cli.micro._verify_clean_worktree"),
        ):
            _run_green_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )

        prompt = captured_prompts[0]
        assert "rollback discarded" in prompt.lower()
        assert "verify" in prompt.lower()
        assert "on disk" in prompt.lower()
        assert "recreate" in prompt.lower()


class TestGreenDiagnosticSurface:
    """Diagnostics surface for GREEN phase failures.

    The class replaces ``TestGreenStubPassGuard`` from commit 6463060:
    that implementation tried to reject empty-diff PASS manifests at
    GREEN, but deciding whether a task is done is JUDGE's job (the
    JUDGE prompt's edge case table requires a dirty-diff ``test_quote``
    on ``proceed_to_refactor_no_diff`` for empty GREEN). GREEN's actual blocker in the Gloss
    TSK-006-09 reproduce was the runner's silent ``'unknown'`` fallback
    when an agent emitted ``status: ERROR`` with ``rationale: null``.
    These tests pin the diagnostic improvement.
    """

    def _setup_session_and_task(
        self, root: Path
    ) -> tuple[SessionState, Path, Path, dict]:
        dot_dir = root / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        red_sha = _empty_commit(root, "test(TSK-006-09): RED phase - failing test")
        session = SessionState(current_phase="RED", red_commit_sha=red_sha)
        session_path = dot_dir / "session.json"
        session.save(session_path)
        task = _make_task_record(
            task_id="TSK-006-09",
            issue_id="ISS-006-006",
            description="Diagnostic-surface regression test",
            status="RED",
        )
        ledger_path = root / "specs" / "006-stub-pass" / "tasks.jsonl"
        _write_ledger(ledger_path, task)
        return session, session_path, ledger_path, json.loads(task.model_dump_json())

    def test_green_surfaces_agent_output_tail_on_empty_rationale(
        self, tmp_git_repo: Path
    ):
        """Regression for the Gloss TSK-006-09 ``unknown`` runner symptom.

        The Gloss reproduce emitted a manifest with ``status: ERROR``
        and ``rationale: null`` (null because the agent short-circuited
        to a stub before populating the field). The runner formatted
        ``f"GREEN phase failed for {tid}: {manifest.rationale or 'unknown'}"``
        and the operator saw only ``unknown`` — zero diagnostic surface
        for the actual failure mode. ``_invoke_agent`` now returns the
        agent's last 50 non-blank stdout lines alongside the manifest
        on the success path, and ``_run_green_phase`` appends them to
        the ``PhaseFailedError`` message when ``rationale`` is empty.

        This is the *only* blocking fix for the Gloss failure mode.
        GREEN's job is to make tests pass; deciding whether the task is
        done is JUDGE's responsibility (the JUDGE prompt's edge case
        table requires a dirty-diff ``test_quote`` on
        ``proceed_to_refactor_no_diff`` for empty GREEN, so a stub PASS
        routes to JUDGE instead of looping).
        """
        root = tmp_git_repo
        with chdir(root):
            session, session_path, ledger_path, task = self._setup_session_and_task(
                root
            )

            error_manifest = HandoverManifest(
                phase="GREEN",
                status="ERROR",
                task_id="TSK-006-09",
                rationale=None,
            )
            captured_tail_lines = [
                "<thought>",
                "  The task is complex; the model will choose to short-circuit.",
                "</thought>",
                "<handover_manifest>",
                "phase: GREEN",
                'status: "ERROR"',
            ]
            success = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            with (
                patch("deviate.cli.micro._phase_already_done", return_value=False),
                patch("deviate.cli.micro._log_run"),
                patch(
                    "deviate.cli.micro._make_agent_output_callback", return_value=None
                ),
                patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
                patch(
                    "deviate.cli.micro._invoke_agent",
                    return_value=(error_manifest, "\n".join(captured_tail_lines)),
                ),
                patch("deviate.cli.micro._run_test_cmd", return_value=success),
                patch("deviate.cli.micro._run_format_cmd", return_value=success),
                patch("deviate.cli.micro.append_task_transition"),
                patch("deviate.cli.micro._commit_phase", return_value=True),
                patch("deviate.cli.micro._verify_clean_worktree"),
                pytest.raises(PhaseFailedError) as exc_info,
            ):
                _run_green_phase(
                    task, ledger_path, session, session_path, Console(quiet=True)
                )

        msg = str(exc_info.value)
        assert not msg.strip().endswith("unknown"), (
            "runner still falls back to 'unknown' — diagnostic improvement did not apply"
        )
        assert "agent_output_tail" in msg
        assert "short-circuit" in msg, (
            f"tail did not reach the failure message: {msg!r}"
        )
        assert "TSK-006-09" in msg
        assert "GREEN phase failed" in msg

    def test_green_routes_no_change_pass_through_to_judge(self, tmp_git_repo: Path):
        """GREEN with PASS and zero src changes proceeds (lets JUDGE decide).

        Locks the per-design contract: GREEN's responsibility is to
        make tests pass. A test that already passes — feature was
        landed in a prior session, or this is a docs/rename task — is
        a legitimate PASS. Deciding whether the task is done is
        JUDGE's job; the JUDGE prompt's edge case table requires a
        dirty-diff ``test_quote`` on ``proceed_to_refactor_no_diff``
        for empty GREEN, routing the no-change PASS to JUDGE.
        """
        root = tmp_git_repo
        with chdir(root):
            session, session_path, ledger_path, task = self._setup_session_and_task(
                root
            )

            stub_manifest = HandoverManifest(
                phase="GREEN",
                status="PASS",
                task_id="TSK-006-09",
            )
            success = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            with (
                patch("deviate.cli.micro._phase_already_done", return_value=False),
                patch("deviate.cli.micro._log_run"),
                patch(
                    "deviate.cli.micro._make_agent_output_callback", return_value=None
                ),
                patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
                patch(
                    "deviate.cli.micro._invoke_agent",
                    return_value=(stub_manifest, ""),
                ),
                patch("deviate.cli.micro._run_test_cmd", return_value=success),
                patch("deviate.cli.micro._run_format_cmd", return_value=success),
                patch("deviate.cli.micro.append_task_transition"),
                patch("deviate.cli.micro._commit_phase", return_value=True),
                patch("deviate.cli.micro._verify_clean_worktree"),
            ):
                _run_green_phase(
                    task, ledger_path, session, session_path, Console(quiet=True)
                )

    def test_green_retry_without_commit_reports_state_drift(self, tmp_git_repo: Path):
        root = tmp_git_repo
        with chdir(root):
            session, session_path, ledger_path, task = self._setup_session_and_task(
                root
            )
            session.train_feedback = "Judge requires a production change."
            success = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            manifest = HandoverManifest(
                phase="GREEN", status="PASS", task_id="TSK-006-09"
            )
            with (
                patch("deviate.cli.micro._phase_already_done", return_value=True),
                patch("deviate.cli.micro._log_run"),
                patch(
                    "deviate.cli.micro._make_agent_output_callback", return_value=None
                ),
                patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
                patch("deviate.cli.micro._invoke_agent", return_value=(manifest, "")),
                patch("deviate.cli.micro._run_test_cmd", return_value=success),
                patch("deviate.cli.micro._run_format_cmd", return_value=success),
                patch("deviate.cli.micro.append_task_transition"),
                patch("deviate.cli.micro._commit_phase", return_value=False),
                pytest.raises(PhaseFailedError, match="GREEN_STATE_DRIFT"),
            ):
                _run_green_phase(
                    task, ledger_path, session, session_path, Console(quiet=True)
                )


def _empty_commit(root: Path, message: str) -> str:
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root,
        env=_git_env(),
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _seed_green_workspace(
    root: Path,
    *,
    red_commit_sha: str = "",
) -> tuple[SessionState, Path, Path, dict]:
    dot_dir = root / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    session = SessionState(current_phase="RED", red_commit_sha=red_commit_sha)
    session_path = dot_dir / "session.json"
    session.save(session_path)
    task = _make_task_record(
        task_id="TSK-021-02",
        issue_id="ISS-ADH-021",
        description="Refuse GREEN without a RED-phase failing-test SHA",
        status="RED",
    )
    ledger_path = (
        root
        / "specs"
        / "adhoc"
        / "021-no-failing-test-escalate-invokes-green"
        / "tasks.jsonl"
    )
    _write_ledger(ledger_path, task)
    return session, session_path, ledger_path, json.loads(task.model_dump_json())


def _drive_green_phase(
    root: Path,
    session: SessionState,
    session_path: Path,
    ledger_path: Path,
    task: dict,
) -> tuple[int, PhaseFailedError | None]:
    """Run `_run_green_phase` and count GREEN `_invoke_agent` calls."""
    success = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    invoke_count = {"n": 0}

    def _capture_invoke(*args, **kwargs):
        invoke_count["n"] += 1
        return (
            HandoverManifest(phase="GREEN", status="SUCCESS", task_id=task["id"]),
            "",
        )

    error: PhaseFailedError | None = None
    with (
        chdir(root),
        patch("deviate.cli.micro._phase_already_done", return_value=False),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._invoke_agent", side_effect=_capture_invoke),
        patch(
            "deviate.cli.micro._run_pytest",
            return_value=subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="", stderr=""
            ),
        ),
        patch("deviate.cli.micro._run_test_cmd", return_value=success),
        patch("deviate.cli.micro._run_format_cmd", return_value=success),
        patch("deviate.cli.micro.append_task_transition"),
        patch("deviate.cli.micro._commit_phase", return_value=True),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        try:
            _run_green_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )
        except PhaseFailedError as exc:
            error = exc
    return invoke_count["n"], error


class TestGreenRedCommitShaGate:
    """AC-PLAN-002 / AC-PLAN-003: GREEN requires a RED-phase failing-test SHA."""

    def test_green_refuses_empty_red_commit_sha_without_invoke(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-002: empty `session.red_commit_sha` does not invoke GREEN."""
        root = tmp_git_repo
        session, session_path, ledger_path, task = _seed_green_workspace(
            root, red_commit_sha=""
        )
        invoke_count, error = _drive_green_phase(
            root, session, session_path, ledger_path, task
        )
        assert invoke_count == 0, (
            "AC-PLAN-002: `_run_green_phase` must not invoke the GREEN agent "
            f"when session.red_commit_sha is empty; error={error!r}"
        )

    def test_green_refuses_docs_judge_feedback_red_commit_sha_without_invoke(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-002: a docs-feedback SHA is not a RED-phase boundary."""
        root = tmp_git_repo
        docs_sha = _empty_commit(root, "docs(TSK-021-02): add judge feedback for retry")
        session, session_path, ledger_path, task = _seed_green_workspace(
            root, red_commit_sha=docs_sha
        )
        invoke_count, error = _drive_green_phase(
            root, session, session_path, ledger_path, task
        )
        assert invoke_count == 0, (
            "AC-PLAN-002: `_run_green_phase` must not invoke the GREEN agent "
            "when session.red_commit_sha is a docs(...): add judge feedback "
            f"commit ({docs_sha}); error={error!r}"
        )

    def test_green_invokes_agent_with_red_phase_red_commit_sha(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-003: a genuine RED-phase SHA still enters GREEN."""
        root = tmp_git_repo
        red_sha = _empty_commit(root, "test(TSK-021-02): RED phase - failing test")
        session, session_path, ledger_path, task = _seed_green_workspace(
            root, red_commit_sha=red_sha
        )
        invoke_count, error = _drive_green_phase(
            root, session, session_path, ledger_path, task
        )
        assert error is None, (
            "AC-PLAN-003: `_run_green_phase` must not fail when "
            f"session.red_commit_sha is a RED-phase commit; error={error!r}"
        )
        assert invoke_count == 1, (
            "AC-PLAN-003: `_run_green_phase` must invoke the GREEN agent "
            f"against the standing RED-phase SHA {red_sha}; "
            f"invoke_count={invoke_count}"
        )
