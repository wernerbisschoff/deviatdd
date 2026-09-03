"""GH-198: JUDGE git rollback must recover isolated env via ``mise reset``.

Integration/e2e RED/GREEN may apply a project-owned catalog mutation.
``_execute_rollback`` restores git only. After a successful
``revert_green`` / ``revert_red`` (and the RED-escalate pre-RED reset),
the runner runs ``mise reset`` when ``test_strategy`` is ``integration``
or ``e2e``. Unit tasks skip it. Missing or failing reset is
``ENV_NOT_READY`` — no next RED/GREEN.
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
    _rollback_pre_red_if_resolvable,
)
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

_TASK_ID = "TSK-001-01"
_ISSUE_ID = "001-001"


def _rev_parse(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", rev],
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
        rationale="implementation misses the reserve lock",
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


class TestJudgeRollbackRunsMiseReset:
    @pytest.mark.parametrize("action", ["revert_green", "revert_red"])
    def test_integration_revert_runs_mise_reset_after_git_rollback(
        self, tmp_git_repo: Path, action: str
    ) -> None:
        task, ledger, pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration"
        )
        calls: list[str] = []
        heads: list[str] = []

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            if command == "mise reset":
                heads.append(_rev_parse(Path(cwd)))
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
            _apply(tmp_git_repo, task, ledger, _violation(action))

        assert calls == ["mise reset"], (
            f"{action} on an integration-stamped task must run mise reset "
            f"after git rollback; got {calls!r}"
        )
        expected = red_sha if action == "revert_green" else pre_red
        assert heads == [expected], (
            f"mise reset must run after git rollback to {expected[:7]}; "
            f"HEAD at call was {heads!r}"
        )
        assert not (tmp_git_repo / "wallet.py").exists()

    def test_e2e_revert_green_runs_mise_reset(self, tmp_git_repo: Path) -> None:
        task, ledger, _pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="e2e"
        )
        calls: list[str] = []

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
            _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert calls == ["mise reset"]
        assert not (tmp_git_repo / "wallet.py").exists()
        assert _rev_parse(tmp_git_repo, "HEAD^") == red_sha

    def test_unit_revert_does_not_run_mise_reset(self, tmp_git_repo: Path) -> None:
        task, ledger, _pre_red, _red = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="unit"
        )
        calls: list[str] = []

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
            session = _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert calls == [], f"unit-stamped task must not run mise reset; got {calls!r}"
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

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with (
            patch("deviate.cli.micro._execute_test_command", side_effect=_fake),
            pytest.raises(EnvNotReadyError, match="ENV_NOT_READY") as caught,
        ):
            _apply(tmp_git_repo, task, ledger, _violation("revert_green"))

        assert "mise reset" in str(caught.value)
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
            return subprocess.CompletedProcess(["mise", "reset"], 1, "", stderr)

        with pytest.raises(EnvNotReadyError, match="ENV_NOT_READY") as caught:
            with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
                _apply(tmp_git_repo, task, ledger, _violation("revert_red"))

        assert stderr in str(caught.value)
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.pending_judge_action == ""
        assert session.current_phase == "GREEN"


class TestEscalatePreRedReset:
    def test_integration_escalate_runs_mise_reset_after_git(
        self, tmp_git_repo: Path
    ) -> None:
        task, _ledger, pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="integration"
        )
        session = SessionState(
            current_phase="GREEN",
            red_commit_sha=red_sha,
        )
        calls: list[str] = []
        heads: list[str] = []

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            heads.append(_rev_parse(Path(cwd)))
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
            _rollback_pre_red_if_resolvable(
                tmp_git_repo,
                session,
                task_id=_TASK_ID,
                attempt=1,
                reason="green_budget_exhausted",
                task=task,
            )

        assert calls == ["mise reset"]
        assert heads == [pre_red]
        assert _rev_parse(tmp_git_repo) == pre_red

    def test_unit_escalate_skips_mise_reset(self, tmp_git_repo: Path) -> None:
        task, _ledger, pre_red, red_sha = _seed_rollback_workspace(
            tmp_git_repo, test_strategy="unit"
        )
        session = SessionState(current_phase="GREEN", red_commit_sha=red_sha)
        calls: list[str] = []

        def _fake(
            command: str, cwd: Path, **_kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro._execute_test_command", side_effect=_fake):
            _rollback_pre_red_if_resolvable(
                tmp_git_repo,
                session,
                task_id=_TASK_ID,
                attempt=1,
                reason="green_budget_exhausted",
                task=task,
            )

        assert calls == []
        assert _rev_parse(tmp_git_repo) == pre_red
