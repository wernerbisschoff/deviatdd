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
from deviate.cli.micro import PhaseFailedError, _run_red_phase
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "RED phase task",
    status: str = "PENDING",
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


class TestRedPre:
    def test_red_pre_contract_includes_task_entry(self, tmp_path: Path):
        """RED's pre contract carries the tasks.md card so the manual RED
        agent sees Judge Feedback history without placeholder wiring."""
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="RED test task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            issue_dir = Path("specs") / "001" / "004-micro-layer"
            issue_dir.mkdir(parents=True)
            (issue_dir / "tasks.md").write_text(
                "# Tasks\n\n"
                "- TSK-004-01: RED test task\n"
                "  - **Judge Feedback**: cover the downgrade path\n"
                "  - **Mode**: TDD\n",
                encoding="utf-8",
            )
            (Path("specs") / "issues.jsonl").write_text(
                json.dumps(
                    {
                        "issue_id": "ISS-001-004",
                        "source_file": "specs/001/issues/004-micro-layer.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "Judge Feedback" in data["task_entry"]
            assert "downgrade path" in data["task_entry"]

    def test_red_pre_emits_contract(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="RED test task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "task_id" in data
            assert "test_strategy" in data
            assert "test_write_dir" in data
            assert "test_command" in data
            assert "lint_command" in data
            assert "spec_dir" in data


class TestRedPost:
    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_validates_test_fails(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="1 failed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_failing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_fail():\n    assert False\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

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

    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_rejects_passing_test(self, mock_run_test, tmp_git_repo: Path):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit, got {result.exit_code}: {result.output}"
            )
            assert "RedMustPassError" in result.output

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_accepts_syntax_error_as_fail(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="SyntaxError: invalid syntax"
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_syntax_error.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_syntax_error(:\n    pass\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["red", "post"])

            assert result.exit_code == 0


class TestRedPostTaskId:
    """GH-154 AC-6: ``deviate red post --task-id`` matches the pending record."""

    def _seed_pending(self, root: Path, *, task_id: str = "TSK-004-01") -> Path:
        from tests.conftest import _git_env as isolation_git_env

        dot_dir = root / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        session = SessionState(current_phase="IDLE", active_issue_id="ISS-001-004")
        session.save(dot_dir / "session.json")

        task = _make_task_record(
            task_id=task_id, issue_id="ISS-001-004", status="PENDING"
        )
        ledger_path = root / "specs" / "004-micro-layer" / "tasks.jsonl"
        _write_ledger(ledger_path, task)

        test_file = root / "tests" / "test_failing.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_fail():\n    assert False\n")
        subprocess.run(
            ["git", "add", "."], cwd=root, env=isolation_git_env(), check=True
        )
        return ledger_path

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_task_id_match_follows_existing_post_path(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="1 failed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        from tests.conftest import _git_env as isolation_git_env

        with chdir(tmp_git_repo):
            ledger_path = self._seed_pending(tmp_git_repo)
            result = runner.invoke(cli, ["red", "post", "--task-id", "TSK-004-01"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "TASK_ID_MISMATCH" not in result.output
            assert "RED_POST_OK" in result.output
            rows = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert any(
                row.get("status") == "RED" and row.get("id") == "TSK-004-01"
                for row in rows
            )
            log = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=isolation_git_env(),
            )
            assert "RED phase" in log.stdout

    @patch("deviate.cli.micro._run_format_cmd")
    @patch("deviate.cli.micro._run_test_cmd")
    def test_red_post_task_id_mismatch_exits_without_ledger_or_commit(
        self, mock_run_test, mock_run_format, tmp_git_repo: Path
    ):
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="1 failed", stderr=""
        )
        mock_run_format.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        from tests.conftest import _git_env as isolation_git_env

        with chdir(tmp_git_repo):
            head_before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=isolation_git_env(),
                check=True,
            ).stdout.strip()
            ledger_path = self._seed_pending(tmp_git_repo)
            ledger_before = ledger_path.read_text(encoding="utf-8")

            result = runner.invoke(cli, ["red", "post", "--task-id", "TSK-004-02"])

            assert result.exit_code == 1, (
                f"Expected exit 1, got {result.exit_code}: {result.output}"
            )
            assert "TASK_ID_MISMATCH" in result.output
            assert ledger_path.read_text(encoding="utf-8") == ledger_before
            rows = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert all(row.get("status") == "PENDING" for row in rows)
            assert not any(row.get("status") == "RED" for row in rows)
            head_after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=isolation_git_env(),
                check=True,
            ).stdout.strip()
            assert head_after == head_before


def _write_red_feedback_specs(root: Path) -> tuple[dict, Path]:
    issue_id = "ISS-ADH-043"
    source_file = "specs/adhoc/issues/043-auto-red-feedback.md"
    issue_path = root / source_file
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    issue_path.write_text("# Auto RED feedback regression\n", encoding="utf-8")
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": issue_id, "source_file": source_file}) + "\n",
        encoding="utf-8",
    )
    task_dir = root / "specs" / "adhoc" / "043-auto-red-feedback"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "tasks.md").write_text(
        "# Implementation Tasks: `feat/adhoc/043-auto-red-feedback`\n\n"
        "## Phase 1: Auto RED feedback\n\n"
        "- TSK-043-01: Consume persisted Judge feedback in RED\n"
        "  - **Judge Feedback**: forbid offline SQL rendering in the RED test\n"
        "  - **Mode**: TDD\n",
        encoding="utf-8",
    )
    record = _make_task_record(
        task_id="TSK-043-01",
        issue_id=issue_id,
        description="Consume persisted Judge feedback in RED",
        status="PENDING",
    )
    ledger_path = task_dir / "tasks.jsonl"
    _write_ledger(ledger_path, record)
    return json.loads(record.model_dump_json()), ledger_path


def _capture_red_prompt(
    root: Path,
    task: dict,
    ledger_path: Path,
    *,
    session_feedback: str = "",
) -> str:
    session = SessionState(current_phase="IDLE", train_feedback=session_feedback)
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    captured_prompts: list[str] = []

    def capture_agent_prompt(prompt: str, *args, **kwargs):
        captured_prompts.append(prompt)
        return (
            HandoverManifest(phase="RED", status="SUCCESS", task_id=task["id"]),
            "",
        )

    failure = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    with (
        chdir(root),
        patch("deviate.cli.micro._phase_already_done", return_value=False),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._invoke_agent", side_effect=capture_agent_prompt),
        patch("deviate.cli.micro._run_test_cmd", return_value=failure),
        patch("deviate.cli.micro._run_format_cmd", return_value=failure),
        patch("deviate.cli.micro.append_task_transition"),
        patch("deviate.cli.micro._commit_phase", return_value=True),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        _run_red_phase(task, ledger_path, session, session_path, Console(quiet=True))

    return captured_prompts[0]


class TestAutoRedPersistedFeedback:
    def test_auto_red_reads_persisted_feedback_without_session_feedback(
        self, tmp_path: Path
    ):
        task, ledger_path = _write_red_feedback_specs(tmp_path)

        prompt = _capture_red_prompt(tmp_path, task, ledger_path)

        expected_line = (
            "- **Judge Feedback**: forbid offline SQL rendering in the RED test"
        )
        assert "<persisted_judge_feedback>" in prompt
        persisted_block = prompt.rsplit("<persisted_judge_feedback>", 1)[1].split(
            "</persisted_judge_feedback>", 1
        )[0]
        assert expected_line in persisted_block
        # Card carries the history too, and nothing duplicates it a third time.
        # (Count-based: <task_content> also appears in template prose, so block
        # extraction by tag is ambiguous in the composed RED prompt.)
        assert prompt.count(expected_line) == 2

    def test_auto_red_prefers_session_feedback_without_persisted_duplicate(
        self, tmp_path: Path
    ):
        session_feedback = "Use the Judge-required transaction boundary."
        stale_persisted_feedback = "STALE PERSISTED FEEDBACK MUST NOT LEAK"
        task, ledger_path = _write_red_feedback_specs(tmp_path)
        tasks_md = ledger_path.parent / "tasks.md"
        tasks_md.write_text(
            tasks_md.read_text(encoding="utf-8").replace(
                "forbid offline SQL rendering in the RED test",
                stale_persisted_feedback,
            ),
            encoding="utf-8",
        )

        prompt = _capture_red_prompt(
            tmp_path, task, ledger_path, session_feedback=session_feedback
        )

        # RED's template embeds the feedback inside its own <train_feedback>
        # block (with retry prose), unlike GREEN's wrapped placeholder.
        assert session_feedback in prompt
        # Same discriminator GREEN pins: the injected block, not the bare tag
        # name (which also appears in the feedback_ingestion instructions).
        assert "<persisted_judge_feedback>\n- **Judge Feedback**:" not in prompt
        # The card keeps its history bullet; with no persisted block injected
        # it must appear exactly once.
        assert prompt.count(stale_persisted_feedback) == 1


def _drive_red_phase(root: Path, task: dict, ledger_path: Path, proc):
    """Drive `_run_red_phase` with a success manifest and a stubbed toolchain."""
    from deviate.cli.micro import append_task_transition as _real_append  # noqa: F401

    session = SessionState(current_phase="IDLE")
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id=task["id"])
    appended: list[dict] = []

    def _capture_append(record, path):
        appended.append(record.model_dump())

    with (
        chdir(root),
        patch("deviate.cli.micro._phase_already_done", return_value=False),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._invoke_agent", return_value=(manifest, "")),
        patch("deviate.cli.micro._run_test_cmd", return_value=proc),
        patch("deviate.cli.micro._run_pytest", return_value=proc),
        patch("deviate.cli.micro._run_format_cmd", return_value=proc),
        patch("deviate.cli.micro.append_task_transition", side_effect=_capture_append),
        patch("deviate.cli.micro._commit_phase", return_value=True),
        patch("deviate.cli.micro._verify_clean_worktree"),
    ):
        out = _run_red_phase(
            task, ledger_path, session, session_path, Console(quiet=True)
        )
    if isinstance(out, tuple):
        return out[0], out[1], appended
    return out, None, appended


class TestRedHandoffAdvisory:
    """`AC-PLAN-001` through `AC-PLAN-004`: RED returns an in-memory advisory."""

    @pytest.mark.behavioral
    def test_pass_returns_warning_advisory_without_error(self, tmp_git_repo: Path):
        from deviate.cli.micro import RedHandoffAdvisory  # noqa: F401

        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        _, advisory, _ = _drive_red_phase(tmp_git_repo, task, ledger_path, proc)

        assert isinstance(advisory, RedHandoffAdvisory)
        assert advisory.task_id == "TSK-003-01"
        assert advisory.passes is True
        assert advisory.severity == "warning"

    @pytest.mark.behavioral
    def test_fail_returns_ok_advisory(self, tmp_git_repo: Path):
        from deviate.cli.micro import RedHandoffAdvisory  # noqa: F401

        proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="1 failed", stderr=""
        )
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        _, advisory, appended = _drive_red_phase(tmp_git_repo, task, ledger_path, proc)

        assert isinstance(advisory, RedHandoffAdvisory)
        assert advisory.passes is False
        assert advisory.severity == "ok"
        assert any(row.get("status") == "RED" for row in appended)

    @pytest.mark.spy
    def test_pass_logs_red_passed_warning(self, tmp_git_repo: Path):
        from deviate.cli.micro import RedHandoffAdvisory  # noqa: F401

        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        session = SessionState(current_phase="IDLE")
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id="TSK-003-01")
        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._invoke_agent", return_value=(manifest, "")),
            patch("deviate.cli.micro._run_test_cmd", return_value=proc),
            patch("deviate.cli.micro._run_pytest", return_value=proc),
            patch("deviate.cli.micro._run_format_cmd", return_value=proc),
            patch("deviate.cli.micro.append_task_transition"),
            patch("deviate.cli.micro._commit_phase", return_value=True),
            patch("deviate.cli.micro._verify_clean_worktree"),
            patch("deviate.cli.micro.log_event") as mock_log_event,
        ):
            _run_red_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )
        mock_log_event.assert_any_call("RED_PASSED_WARNING", task_id="TSK-003-01")

    @pytest.mark.behavioral
    def test_crash_surfaces_phase_error_with_no_advisory(self, tmp_git_repo: Path):
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        session = SessionState(current_phase="IDLE")
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id="TSK-003-01")
        proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch("deviate.cli.micro._invoke_agent", return_value=(manifest, "")),
            patch("deviate.cli.micro._run_test_cmd", side_effect=OSError("boom")),
            patch("deviate.cli.micro._run_pytest", return_value=proc),
            patch("deviate.cli.micro.append_task_transition") as mock_append,
        ):
            with pytest.raises(PhaseFailedError):
                _run_red_phase(
                    task, ledger_path, session, session_path, Console(quiet=True)
                )
        mock_append.assert_not_called()

    @pytest.mark.behavioral
    def test_absent_test_file_skips_checkpoint_with_no_advisory(
        self, tmp_git_repo: Path
    ):
        proc = subprocess.CompletedProcess(
            args=["deviate", "test"],
            returncode=127,
            stdout="",
            stderr="No test command configured",
        )
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        _, advisory, appended = _drive_red_phase(tmp_git_repo, task, ledger_path, proc)

        assert advisory is None
        assert not any(row.get("status") == "RED" for row in appended)

    @pytest.mark.behavioral
    def test_advisory_never_persists_to_ledger(self, tmp_git_repo: Path):
        from deviate.cli.micro import RedHandoffAdvisory  # noqa: F401

        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        task = _make_task_record(task_id="TSK-003-01").model_dump()
        ledger_path = tmp_git_repo / "specs" / "005" / "tasks.jsonl"
        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(
                    HandoverManifest(
                        phase="RED", status="SUCCESS", task_id="TSK-003-01"
                    ),
                    "",
                ),
            ),
            patch("deviate.cli.micro._run_test_cmd", return_value=proc),
            patch("deviate.cli.micro._run_pytest", return_value=proc),
            patch("deviate.cli.micro._run_format_cmd", return_value=proc),
            patch("deviate.cli.micro._commit_phase", return_value=True),
            patch("deviate.cli.micro._verify_clean_worktree"),
        ):
            session = SessionState(current_phase="IDLE")
            session_path = tmp_git_repo / ".deviate" / "session.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session.save(session_path)
            _run_red_phase(
                task, ledger_path, session, session_path, Console(quiet=True)
            )
        text = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
        assert "RedHandoffAdvisory" not in text
        assert "advisory" not in text.lower()
