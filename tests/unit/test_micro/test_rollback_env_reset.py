"""GH-198: JUDGE git rollback recovers isolated env via ``mise run reset``.

Integration/e2e RED/GREEN may apply a project-owned catalog mutation.
``_execute_rollback`` restores git only. After a successful
``revert_green`` / ``revert_red`` (and the RED-escalate pre-RED reset
*after* JUDGE feedback is re-persisted), the runner runs
``mise run reset`` when ``test_strategy`` is ``integration`` or ``e2e``.
Unit tasks skip it. Missing or failing reset is ``ENV_NOT_READY``.

GREEN-budget escalate after ``revert_green`` must not drop the JUDGE
feedback commit: reset to pre-RED, then re-commit the same payload.
"""

from __future__ import annotations

import io
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deviate.cli.micro import (
    EnvNotReadyError,
    _apply_judge_verdict,
    _build_auto_prompt,
    _escalate_to_new_red,
    _rollback_pre_red_if_resolvable,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_ID = "TSK-001-01"
_ISSUE_ID = "001-001"
_RATIONALE = "implementation misses the reserve lock"
_MISE_RUN_RESET = "mise run reset"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _subject(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%s", rev],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _rev_parse(repo)


def _write_mise(repo: Path, *, reset: bool) -> None:
    body = '[tasks.unit]\nrun = "pytest tests/unit"\n\n[tasks.integration]\nrun = "pytest tests/integration"\n'
    if reset:
        body += '\n[tasks.reset]\nrun = "echo isolated-env-recreate"\n'
    (repo / "mise.toml").write_text(body, encoding="utf-8")


def _seed_rollback_workspace(
    repo: Path,
    *,
    test_strategy: str,
    reset: bool = True,
) -> tuple[dict, Path, str, str]:
    """Commit mise.toml + tasks card, then RED and GREEN. Return pre-RED + RED."""
    workspace = repo / "specs" / "001-wallet" / "001-001"
    workspace.mkdir(parents=True, exist_ok=True)
    source = "specs/001-wallet/issues/001-001.md"
    issue_md = repo / source
    issue_md.parent.mkdir(parents=True, exist_ok=True)
    issue_md.write_text("# wallet withdrawal\n", encoding="utf-8")
    (repo / "specs" / "issues.jsonl").write_text(
        '{"issue_id": "' + _ISSUE_ID + '", "source_file": "' + source + '"}\n',
        encoding="utf-8",
    )
    card = (
        f"- [ ] {_TASK_ID}: wallet withdrawal\n  - **Test Strategy**: {test_strategy}\n"
    )
    (workspace / "tasks.md").write_text(card, encoding="utf-8")
    _write_mise(repo, reset=reset)
    gitignore = repo / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if ".deviate/" not in existing.splitlines():
        gitignore.write_text(existing.rstrip() + "\n.deviate/\n", encoding="utf-8")
    pre_red = _commit(repo, "chore: seed mise and tasks")

    test_path = repo / "tests" / "integration" / "test_wallet.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("assert False\n", encoding="utf-8")
    red_sha = _commit(repo, f"test({_TASK_ID}): RED phase - failing test")

    impl = repo / "wallet.py"
    impl.write_text("def withdraw():\n    return 1\n", encoding="utf-8")
    _commit(repo, f"feat({_TASK_ID}): GREEN phase - implementation")

    record = TaskRecord(
        id=_TASK_ID,
        issue_id=_ISSUE_ID,
        description="wallet withdrawal",
        status="GREEN",
        execution_mode="TDD",
        test_strategy=test_strategy,  # type: ignore[arg-type]
    )
    ledger = workspace / "tasks.jsonl"
    ledger.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(
        current_phase="GREEN",
        active_issue_id=_ISSUE_ID,
        red_commit_sha=red_sha,
    ).save(session_path)
    task = record.model_dump()
    return task, ledger, pre_red, red_sha


def _violation(next_action: str) -> HandoverManifest:
    return HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id=_TASK_ID,
        verdict="COMPLIANCE_VIOLATION",
        next_action=next_action,
        rationale=_RATIONALE,
    )


def _apply(
    repo: Path,
    task: dict,
    ledger: Path,
    manifest: HandoverManifest,
) -> SessionState:
    session_path = repo / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    buf = io.StringIO()
    with chdir(repo):
        return _apply_judge_verdict(
            task,
            ledger,
            session,
            session_path,
            Console(file=buf, force_terminal=False, width=200),
            manifest,
            injected_diff="diff --git a/wallet.py b/wallet.py\n",
        )


def _fake_ok(calls: list[str], heads: list[str] | None = None) -> object:
    def _fake(
        command: str, cwd: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess:
        calls.append(command)
        if heads is not None and command == _MISE_RUN_RESET:
            heads.append(_rev_parse(Path(cwd)))
        return subprocess.CompletedProcess(command.split(), 0, "ok", "")

    return _fake


class TestJudgeRollbackRunsMiseReset:
    @pytest.mark.parametrize("action", ["revert_green", "revert_red"])
    def test_integration_revert_runs_mise_run_reset_after_git_rollback(
        self, tmp_git_repo: Path, action: str
    ) -> None:
        task, ledger, pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration"
        )
        calls: list[str] = []
        heads: list[str] = []

        with patch(
            "deviate.cli.micro._execute_test_command",
            side_effect=_fake_ok(calls, heads),
        ):
            _apply(tmp_git_repo, task, ledger, _violation(action))

        assert calls == [_MISE_RUN_RESET], (
            f"{action} on an integration-stamped task must run "
            f"{_MISE_RUN_RESET} after git rollback; got {calls!r}"
        )
        expected = red_sha if action == "revert_green" else pre_red
        assert heads == [expected], (
            f"{_MISE_RUN_RESET} must run after git rollback to "
            f"{expected[:7]}; HEAD at call was {heads!r}"
        )
        assert not (tmp_git_repo / "wallet.py").exists()

    def test_e2e_revert_green_runs_mise_run_reset(self, tmp_git_repo: Path) -> None:
        task, ledger, _pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="e2e"
        )
        calls: list[str] = []

        with patch(
            "deviate.cli.micro._execute_test_command",
            side_effect=_fake_ok(calls),
        ):
            _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert calls == [_MISE_RUN_RESET]
        assert not (tmp_git_repo / "wallet.py").exists()
        assert _rev_parse(tmp_git_repo, "HEAD^") == red_sha

    def test_unit_revert_does_not_run_mise_run_reset(self, tmp_git_repo: Path) -> None:
        task, ledger, _pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="unit"
        )
        calls: list[str] = []

        with patch(
            "deviate.cli.micro._execute_test_command",
            side_effect=_fake_ok(calls),
        ):
            session = _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert calls == [], (
            f"unit-stamped task must not run {_MISE_RUN_RESET}; got {calls!r}"
        )
        assert session.pending_judge_action == "revert_green"
        assert not (tmp_git_repo / "wallet.py").exists()


class TestMissingOrFailedResetFailsClosed:
    def test_missing_reset_on_integration_is_env_not_ready_no_next_phase(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, _pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration", reset=False
        )
        calls: list[str] = []

        with (
            patch(
                "deviate.cli.micro._execute_test_command",
                side_effect=_fake_ok(calls),
            ),
            pytest.raises(EnvNotReadyError, match="ENV_NOT_READY") as caught,
        ):
            _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert "mise run reset" in str(caught.value)
        assert calls == [], "missing reset must not spawn a substitute command"
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.pending_judge_action == "", (
            "ENV_NOT_READY must not proceed into the next RED/GREEN; "
            f"pending={session.pending_judge_action!r}"
        )
        assert session.current_phase == "GREEN"
        assert not (tmp_git_repo / "wallet.py").exists(), (
            "git rollback still happens before the env-not-ready stop"
        )

    def test_failed_reset_is_env_not_ready_with_stderr(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, _pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration"
        )
        stderr = "Can't locate revision identified by 'c6f1a2b3c4d5'"

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(["mise", "run", "reset"], 1, "", stderr)

        with pytest.raises(EnvNotReadyError, match="ENV_NOT_READY") as caught:
            with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
                _apply(tmp_git_repo, task, ledger, _violation("revert_red"))

        assert stderr in str(caught.value)
        assert "mise run reset" in str(caught.value)
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.pending_judge_action == ""
        assert session.current_phase == "GREEN"


class TestEscalatePreRedReset:
    def test_integration_escalate_runs_mise_run_reset_after_feedback_commit(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration"
        )
        with patch(
            "deviate.cli.micro._execute_test_command",
            side_effect=_fake_ok([]),
        ):
            session = _apply(tmp_git_repo, task, ledger, _violation("revert_green"))
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session.green_attempts = 3
        session.save(session_path)

        calls: list[str] = []
        heads: list[str] = []

        def _red(*_args: object, **_kwargs: object) -> SessionState:
            current = SessionState.load(session_path)
            current.red_commit_sha = "b" * 40
            current.save(session_path)
            return current

        with (
            chdir(tmp_git_repo),
            patch(
                "deviate.cli.micro._execute_test_command",
                side_effect=_fake_ok(calls, heads),
            ),
            patch("deviate.cli.micro._run_red_phase", side_effect=_red),
        ):
            _escalate_to_new_red(
                task,
                ledger,
                session,
                session_path,
                Console(file=io.StringIO(), force_terminal=False, width=200),
                agent=None,
                monitor=None,
                no_judge=False,
                root=tmp_git_repo,
                reason="green_budget_exhausted",
            )

        assert calls == [_MISE_RUN_RESET]
        assert heads, f"{_MISE_RUN_RESET} must run after the escalate persist"
        assert "judge feedback" in _subject(tmp_git_repo, heads[0])
        assert _rev_parse(tmp_git_repo, f"{heads[0]}^") == pre_red

    def test_unit_escalate_skips_mise_run_reset(self, tmp_git_repo: Path) -> None:
        task, ledger, pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="unit"
        )
        session = _apply(tmp_git_repo, task, ledger, _violation("revert_green"))
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session.green_attempts = 3
        session.save(session_path)
        calls: list[str] = []

        def _red(*_args: object, **_kwargs: object) -> SessionState:
            return SessionState.load(session_path)

        with (
            chdir(tmp_git_repo),
            patch(
                "deviate.cli.micro._execute_test_command",
                side_effect=_fake_ok(calls),
            ),
            patch("deviate.cli.micro._run_red_phase", side_effect=_red),
        ):
            _escalate_to_new_red(
                task,
                ledger,
                session,
                session_path,
                Console(file=io.StringIO(), force_terminal=False, width=200),
                agent=None,
                monitor=None,
                no_judge=False,
                root=tmp_git_repo,
                reason="green_budget_exhausted",
            )

        assert calls == []
        assert "judge feedback" in _subject(tmp_git_repo)
        assert _rev_parse(tmp_git_repo, "HEAD^") == pre_red


class TestEscalateKeepsJudgeFeedback:
    """revert_green + GREEN budget exhaust must re-commit JUDGE feedback."""

    def test_green_budget_escalate_repersists_judge_feedback_for_retry_red(
        self, tmp_git_repo: Path
    ) -> None:
        task, ledger, pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="unit"
        )
        session = _apply(tmp_git_repo, task, ledger, _violation("revert_green"))
        session_path = tmp_git_repo / ".deviate" / "session.json"
        (tmp_git_repo / "wallet.py").write_text(
            "def withdraw():\n    return 2\n", encoding="utf-8"
        )
        _commit(tmp_git_repo, f"feat({_TASK_ID}): GREEN train 3")
        session.green_attempts = 3
        session.save(session_path)

        captured_feedback: list[str] = []
        captured_prompts: list[str] = []

        def _red(*_args: object, **_kwargs: object) -> SessionState:
            current = SessionState.load(session_path)
            captured_feedback.append(current.train_feedback)
            captured_prompts.append(
                _build_auto_prompt(
                    "red",
                    task,
                    tmp_git_repo,
                    train_feedback=current.train_feedback,
                )
            )
            persisted = (
                tmp_git_repo / "specs" / "001-wallet" / "001-001" / "tasks.md"
            ).read_text(encoding="utf-8")
            assert _RATIONALE in persisted, persisted
            return current

        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._run_red_phase", side_effect=_red),
        ):
            session = _escalate_to_new_red(
                task,
                ledger,
                session,
                session_path,
                Console(file=io.StringIO(), force_terminal=False, width=200),
                agent=None,
                monitor=None,
                no_judge=False,
                root=tmp_git_repo,
                reason="green_budget_exhausted",
            )

        assert captured_feedback, "retry RED must run after escalate"
        assert _RATIONALE in captured_feedback[0], captured_feedback[0]
        assert "previous cycle failed because" not in captured_feedback[0]
        assert _RATIONALE in captured_prompts[0], captured_prompts[0]
        assert "judge feedback" in _subject(tmp_git_repo)
        assert _rev_parse(tmp_git_repo, "HEAD^") == pre_red
        body = subprocess.run(
            ["git", "show", "HEAD"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout
        assert _RATIONALE in body, body
        assert not (tmp_git_repo / "wallet.py").exists()
        assert not (tmp_git_repo / "tests" / "integration" / "test_wallet.py").exists()

        feedback_sha = _rev_parse(tmp_git_repo)
        session.red_commit_sha = feedback_sha
        session.save(session_path)
        result = _rollback_pre_red_if_resolvable(
            tmp_git_repo,
            session,
            task_id=_TASK_ID,
            attempt=2,
            reason="green_budget_exhausted",
            task=task,
        )
        assert result is None, (
            "second escalate reset must skip once HEAD is the re-persisted "
            f"feedback commit; got {result!r}"
        )
        assert _rev_parse(tmp_git_repo) == feedback_sha
        assert (
            _RATIONALE
            in subprocess.run(
                ["git", "show", "HEAD"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
                check=True,
            ).stdout
        )
