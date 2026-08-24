"""GH-101: ``deviate micro run --review`` pauses before each phase commit.

Contract pins:
* pause is called before ``git add -A`` / commit
* commit is not created until TTY confirmation (Enter / yes)
* non-TTY / ``--json`` / missing stdin fail closed with ``REVIEW_REQUIRES_TTY``
* RED still stamps ``session.red_commit_sha`` after the RED pause
* JUDGE feedback commits are not paused
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from tests.conftest import _git_env

runner = CliRunner()

_TASK = {
    "id": "TSK-101-01",
    "issue_id": "ISS-001-101",
    "description": "review pause task",
    "status": "PENDING",
    "execution_mode": "TDD",
}


@pytest.fixture(autouse=True)
def _reset_review_context() -> object:
    from deviate.cli import micro

    micro._set_review_context(enabled=False, json_mode=False, task_id="")
    yield
    micro._set_review_context(enabled=False, json_mode=False, task_id="")


def _rev_parse(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout.strip()


def _porcelain(root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
        check=True,
    ).stdout


def _write_dirty_file(root: Path, name: str = "review_me.py") -> Path:
    path = root / name
    path.write_text("x = 1\n", encoding="utf-8")
    return path


def _tty_stdin(answers: list[str]) -> SimpleNamespace:
    queued = list(answers)

    def readline() -> str:
        if not queued:
            return ""
        return queued.pop(0)

    return SimpleNamespace(isatty=lambda: True, readline=readline)


class TestReviewFlag:
    def test_micro_run_exposes_review_flag(self) -> None:
        from typer.main import get_command

        click_app = get_command(cli)
        run = click_app.commands["micro"].commands["run"]
        option_names = {
            opt for param in run.params for opt in (*param.opts, *param.secondary_opts)
        }
        assert "--review" in option_names

    def test_review_plus_json_fails_closed_without_commit(
        self, tmp_git_repo: Path
    ) -> None:
        with chdir(tmp_git_repo):
            head_before = _rev_parse(tmp_git_repo)
            result = runner.invoke(
                cli, ["micro", "run", "TSK-101-01", "--review", "--json"]
            )
        assert result.exit_code != 0
        assert "REVIEW_REQUIRES_TTY" in result.output
        assert _rev_parse(tmp_git_repo) == head_before


class TestMaybeReviewPause:
    def test_pause_is_noop_when_review_is_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        stdin = _tty_stdin(["\n"])
        monkeypatch.setattr(micro.sys, "stdin", stdin)
        micro._maybe_review_pause("RED", "TSK-101-01")
        # Off by default: never reads stdin.
        assert stdin.readline() == "\n"

    def test_judge_phase_does_not_pause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from deviate.cli import micro

        stdin = _tty_stdin(["\n"])
        monkeypatch.setattr(micro.sys, "stdin", stdin)
        micro._set_review_context(enabled=True, task_id="TSK-101-01")
        micro._maybe_review_pause("JUDGE", "TSK-101-01")
        assert stdin.readline() == "\n"

    def test_non_tty_fail_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from deviate.cli import micro

        monkeypatch.setattr(
            micro.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: False, readline=lambda: "\n"),
        )
        micro._set_review_context(enabled=True, task_id="TSK-101-01")
        with pytest.raises(micro.ReviewRequiresTtyError, match="REVIEW_REQUIRES_TTY"):
            micro._maybe_review_pause("RED", "TSK-101-01")

    def test_missing_stdin_fail_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from deviate.cli import micro

        monkeypatch.setattr(micro.sys, "stdin", None)
        micro._set_review_context(enabled=True, task_id="TSK-101-01")
        with pytest.raises(micro.ReviewRequiresTtyError, match="REVIEW_REQUIRES_TTY"):
            micro._maybe_review_pause("GREEN", "TSK-101-01")

    def test_json_mode_fail_closed_even_on_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        monkeypatch.setattr(micro.sys, "stdin", _tty_stdin(["\n"]))
        micro._set_review_context(enabled=True, json_mode=True, task_id="TSK-101-01")
        with pytest.raises(micro.ReviewRequiresTtyError, match="REVIEW_REQUIRES_TTY"):
            micro._maybe_review_pause("REFACTOR", "TSK-101-01")


class TestCommitPhaseReviewPause:
    def test_pause_called_before_git_add(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        order: list[str] = []
        real_run = subprocess.run

        def tracking_run(cmd: object, *args: object, **kwargs: object):
            if isinstance(cmd, (list, tuple)) and len(cmd) >= 2:
                if cmd[0] == "git" and cmd[1] == "add":
                    order.append("add")
                elif cmd[0] == "git" and cmd[1] == "commit":
                    order.append("commit")
            return real_run(cmd, *args, **kwargs)

        def fake_pause(phase: str | None, task_id: str | None = None) -> None:
            order.append(f"pause:{phase}:{task_id}")

        _write_dirty_file(tmp_git_repo)
        monkeypatch.setattr(micro.sys, "stdin", _tty_stdin(["\n"]))
        micro._set_review_context(enabled=True, task_id="TSK-101-01")
        with (
            patch.object(micro, "_maybe_review_pause", side_effect=fake_pause),
            patch.object(micro.subprocess, "run", side_effect=tracking_run),
        ):
            committed = micro._commit_phase(
                "test(TSK-101-01): RED phase - failing test",
                tmp_git_repo,
                no_verify=True,
                phase="red",
                task_id="TSK-101-01",
            )

        assert committed is True
        assert order[0] == "pause:red:TSK-101-01"
        assert "add" in order
        assert "commit" in order
        assert order.index("pause:red:TSK-101-01") < order.index("add")
        assert order.index("add") < order.index("commit")

    def test_commit_not_called_until_confirm(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        _write_dirty_file(tmp_git_repo)
        head_before = _rev_parse(tmp_git_repo)
        saw_dirty_at_confirm = False

        def readline() -> str:
            nonlocal saw_dirty_at_confirm
            assert _rev_parse(tmp_git_repo) == head_before
            assert _porcelain(tmp_git_repo).strip(), "worktree must stay dirty at pause"
            saw_dirty_at_confirm = True
            return "yes\n"

        monkeypatch.setattr(
            micro.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: True, readline=readline),
        )
        buf = StringIO()
        monkeypatch.setattr(
            micro, "console", Console(file=buf, force_terminal=False, highlight=False)
        )
        micro._set_review_context(enabled=True, task_id="TSK-101-01")

        committed = micro._commit_phase(
            "test(TSK-101-01): RED phase - failing test",
            tmp_git_repo,
            no_verify=True,
            phase="red",
            task_id="TSK-101-01",
        )

        assert saw_dirty_at_confirm
        assert committed is True
        assert _rev_parse(tmp_git_repo) != head_before
        assert "REVIEW_PAUSE RED TSK-101-01" in buf.getvalue()
        assert not _porcelain(tmp_git_repo).strip()

    def test_non_tty_does_not_auto_commit(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        _write_dirty_file(tmp_git_repo)
        head_before = _rev_parse(tmp_git_repo)
        monkeypatch.setattr(
            micro.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: False, readline=lambda: "\n"),
        )
        micro._set_review_context(enabled=True, task_id="TSK-101-01")

        with pytest.raises(micro.ReviewRequiresTtyError, match="REVIEW_REQUIRES_TTY"):
            micro._commit_phase(
                "test(TSK-101-01): RED phase - failing test",
                tmp_git_repo,
                no_verify=True,
                phase="red",
                task_id="TSK-101-01",
            )

        assert _rev_parse(tmp_git_repo) == head_before
        assert _porcelain(tmp_git_repo).strip()

    def test_execute_recovery_helper_pauses_before_commit(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli import micro

        target = tmp_git_repo / "exec.py"
        target.write_text("# execute\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "exec.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        head_before = _rev_parse(tmp_git_repo)
        confirmed = False

        def readline() -> str:
            nonlocal confirmed
            assert _rev_parse(tmp_git_repo) == head_before
            confirmed = True
            return "\n"

        monkeypatch.setattr(
            micro.sys,
            "stdin",
            SimpleNamespace(isatty=lambda: True, readline=readline),
        )
        micro._set_review_context(enabled=True, task_id="TSK-101-02")

        committed = micro._commit_phase_with_recovery(
            "feat(TSK-101-02): EXECUTE phase - TSK-101-02",
            tmp_git_repo,
            task_id="TSK-101-02",
            attempt=0,
            phase="EXECUTE",
        )

        assert confirmed
        assert committed is True
        assert _rev_parse(tmp_git_repo) != head_before


class TestRedShaAfterReviewPause:
    def test_red_commit_sha_stamped_after_red_pause(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from deviate.cli.micro import _run_red_phase

        root = tmp_git_repo
        monkeypatch.chdir(root)
        tests_dir = root / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_file = tests_dir / "test_review_red.py"

        ledger_path = root / "tasks.jsonl"
        ledger_path.write_text("", encoding="utf-8")
        session_path = root / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session = SessionState(current_phase="IDLE", red_commit_sha="")
        session.save(session_path)

        from deviate.cli import micro

        monkeypatch.setattr(micro.sys, "stdin", _tty_stdin(["\n"]))
        micro._set_review_context(enabled=True, task_id=_TASK["id"])

        def _return_manifest(*_args: object, **_kwargs: object):
            test_file.write_text(
                "def test_contract():\n    assert False\n",
                encoding="utf-8",
            )
            return (
                HandoverManifest(
                    phase="RED",
                    status="PASS",
                    task_id=_TASK["id"],
                    test_file="tests/test_review_red.py",
                ),
                "",
            )

        with (
            patch("deviate.cli.micro._invoke_agent", side_effect=_return_manifest),
            patch("deviate.cli.micro._build_auto_prompt", return_value="prompt"),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._emit_phase_callout"),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch(
                "deviate.cli.micro._run_test_cmd",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="1 failed", stderr=""
                ),
            ),
            patch(
                "deviate.cli.micro._run_format_cmd",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch("deviate.cli.micro._verify_clean_worktree"),
        ):
            result = _run_red_phase(
                dict(_TASK),
                ledger_path,
                session,
                session_path,
                Console(),
            )

        assert result.red_commit_sha, (
            "RED must stamp session.red_commit_sha after the --review pause"
        )
        persisted = SessionState.load(session_path)
        assert persisted.red_commit_sha == result.red_commit_sha
        log = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        )
        assert "RED phase" in log.stdout
