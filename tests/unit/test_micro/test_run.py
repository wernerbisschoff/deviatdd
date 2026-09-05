from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import typer
from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import _find_test_files, _run_single
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition

runner = CliRunner()


def _mock_invoke_agent(*args, **kwargs):
    """Mock _invoke_agent to return a valid manifest for testing."""
    return HandoverManifest(
        phase=kwargs.get("phase", "RED"),
        status="SUCCESS",
        task_id=kwargs.get("task_id", "TSK-000-00"),
    ), ""


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-007",
    description: str = "Test TDD task",
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


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


def _seed_tracked_test_file(root: Path, name: str = "test_seed_failing.py") -> None:
    """Create and commit a tracked failing test so the RED test run has a
    non-empty ``_find_test_files`` glob."""
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / name).write_text("def test_seed():\n    assert False\n")
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: seed"],
        cwd=root,
        env=_git_env(),
        check=True,
    )


class TestRunCommand:
    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_dispatches_tdd_task_to_rgr(
        self,
        mock_agent,
        mock_run_test,
        mock_find_tests,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-007",
                description="Implement TDD task",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-01"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to reach COMPLETED state: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._run_test_cmd")
    def test_run_elixir_repo_red_accepts_exs_test(
        self,
        mock_run_test,
        mock_agent,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """An Elixir/Phoenix repo (``test/**/*_test.exs``, no Python tests)
        must pass the RED gate.

        Regression: ``_find_test_files`` only globbed ``tests/**/test_*.py``,
        so a correctly authored ``.exs`` test was rejected with ``RED phase
        produced no test files`` before any test command ran. The red/green
        run for this repo resolves ``mix test`` via the manifest table."""
        with chdir(tmp_git_repo):
            (tmp_git_repo / "mix.exs").write_text(
                "defmodule TailwindPipeline.MixProject do\n"
                "  use Mix.Project\n"
                "  def project, do: [app: :tailwind_pipeline]\n"
                "end\n"
            )
            test_path = tmp_git_repo / "test" / "integration"
            test_path.mkdir(parents=True)
            (test_path / "tailwind_pipeline_test.exs").write_text(
                "defmodule TailwindPipelineTest do\n"
                "  use ExUnit.Case\n"
                '  test "compiles" do assert true end\n'
                "end\n"
            )
            assert _find_test_files(tmp_git_repo) == []  # no Python tests
            mock_run_test.side_effect = [
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="1 file, 1 test, 1 failure", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="1 file, 1 test, 0 failures",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="1 file, 1 test, 0 failures",
                    stderr="",
                ),
            ]
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            task = _make_task_record(
                task_id="TSK-999-01",
                issue_id="ISS-999-001",
                description="Run tailwind pipeline tests",
                status="PENDING",
            )
            ledger_path = Path("specs") / "elix" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            result = runner.invoke(cli, ["micro", "run", "TSK-999-01"])
            assert result.exit_code == 0, result.output
            assert "COMPLETED" in result.output, result.output
            assert "produced no test files" not in result.output, result.output

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_dispatches_immediate_task_to_execute(
        self, mock_agent, tmp_git_repo: Path, approve_gate2
    ):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-02",
                issue_id="ISS-001-007",
                description="Implement immediate task",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-02"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" not in result.output
            assert "COMPLETED" in result.output, (
                f"Expected immediate task to reach COMPLETED: {result.output}"
            )

    def test_run_execute_commits_untracked_deliverable_without_pre_stage(
        self, tmp_git_repo: Path
    ):
        """EXECUTE must commit the agent's new untracked file even when
        nothing was pre-staged (regression: _commit_phase_with_recovery does
        not git add, so the micro-run EXECUTE path must stage first)."""
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            SessionState(current_phase="IDLE").save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-05",
                issue_id="ISS-001-004",
                description="EXECUTE with untracked deliverable",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            def _execute_agent(*args, **kwargs):
                if kwargs.get("phase") == "EXECUTE":
                    deliverable = Path("src/deviate/impl.py")
                    deliverable.parent.mkdir(parents=True, exist_ok=True)
                    deliverable.write_text("# executed deliverable\n")
                return HandoverManifest(
                    phase=kwargs.get("phase", "EXECUTE"),
                    status="PASS",
                    task_id=kwargs.get("task_id", task.id),
                ), ""

            with patch("deviate.cli.micro._invoke_agent", side_effect=_execute_agent):
                result = runner.invoke(cli, ["micro", "run", task.id])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            # The untracked deliverable must be committed.
            committed = subprocess.run(
                ["git", "cat-file", "-e", "HEAD:src/deviate/impl.py"],
                cwd=tmp_git_repo,
                env=_git_env(),
                capture_output=True,
            )
            assert committed.returncode == 0, (
                "EXECUTE did not commit the untracked deliverable"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_all_iterates_mixed_modes(
        self,
        mock_agent,
        mock_run_test,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            tdd_task = _make_task_record(
                task_id="TSK-004-03",
                issue_id="ISS-001-007",
                description="TDD task",
                status="PENDING",
                execution_mode="TDD",
            )
            imm_task = _make_task_record(
                task_id="TSK-004-04",
                issue_id="ISS-001-007",
                description="Immediate task",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, tdd_task, imm_task)
            approve_gate2(tmp_git_repo, issue_id=tdd_task.issue_id)
            _seed_tracked_test_file(tmp_git_repo)

            result = runner.invoke(cli, ["micro", "run", "--all"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert result.output.count("COMPLETED") >= 2, (
                f"Expected all tasks to reach COMPLETED: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_accepts_legacy_TNNN_format(
        self,
        mock_agent,
        mock_run_test,
        mock_find_tests,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-05",
                issue_id="ISS-001-001",
                description="Legacy format task",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "001-initial" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-05"])
            assert result.exit_code == 0, (
                f"Expected exit code 0, got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected TSK-004-05 task to reach COMPLETED: {result.output}"
            )

    def test_run_unknown_task_id_exits_not_found(self, tmp_path: Path, approve_gate2):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            approve_gate2(tmp_path, issue_id="ISS-001")

            result = runner.invoke(cli, ["micro", "run", "TSK-999-99"])
            assert result.exit_code != 0, (
                f"Expected non-zero exit for unknown task, got {result.output}"
            )
            assert "TASK_NOT_FOUND" in result.output or "NOT_FOUND" in result.output

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_with_profile_fast(
        self,
        mock_agent,
        mock_run_test,
        mock_find_tests,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Profile flag test",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(
                cli, ["micro", "run", "TSK-001-03", "--profile", "fast"]
            )
            assert result.exit_code == 0, (
                f"Expected exit code 0 with --profile fast, got {result.exit_code}: {result.output}"
            )
            assert "JUDGE" not in result.output, (
                f"Expected JUDGE skipped with --profile fast: {result.output}"
            )
            assert "REFACTOR" not in result.output, (
                f"Expected REFACTOR skipped with --profile fast: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    def test_run_with_flag_overrides(
        self,
        mock_agent,
        mock_run_test,
        mock_find_tests,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="1 failed", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="1 passed", stderr=""
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Profile flag overrides",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(
                cli,
                ["micro", "run", "TSK-001-03", "--profile", "fast", "--no-judge"],
            )
            assert result.exit_code == 0, (
                f"Expected exit code 0 with override, got {result.exit_code}: {result.output}"
            )

    def test_run_with_profile_invalid(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-001-03",
                issue_id="ISS-002-001",
                description="Invalid profile",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = (
                Path("specs") / "001-foundation-cli-infrastructure" / "tasks.jsonl"
            )
            _write_ledger(ledger_path, task)

            result = runner.invoke(
                cli, ["micro", "run", "TSK-001-03", "--profile", "invalid"]
            )
            assert result.exit_code != 0, (
                f"Expected non-zero exit for invalid profile, got {result.exit_code}: {result.output}"
            )
            assert "Invalid value" in result.output, (
                f"Expected 'Invalid value' in output: {result.output}"
            )

    def test_run_skips_already_completed_task(self, tmp_path: Path, approve_gate2):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-06",
                issue_id="ISS-001-007",
                description="Already done",
                status="COMPLETED",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "007-macro-meso" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_path, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-004-06"])
            assert result.exit_code == 0, result.output
            assert "TASK_ALREADY_DONE" in result.output, (
                f"Expected TASK_ALREADY_DONE warning: {result.output}"
            )


class TestPinnedRunIssueScopedAlreadyDone:
    """AC-PLAN-001 / AC-PLAN-007: TASK_ALREADY_DONE is issue-owned."""

    _SIBLING_COMPLETED = {
        "id": "TSK-001-04",
        "issue_id": "001-001",
        "description": "sibling already done",
        "status": "COMPLETED",
        "execution_mode": "TDD",
    }

    def _seed_empty_active_with_sibling_completed(
        self, root: Path, *, tasks_md_body: str
    ) -> Path:
        """Sibling COMPLETED TSK-001-04; active 001-002 has zero JSONL rows."""
        sibling_ledger = (
            root / "specs" / "001-phone-to-pi-relay" / "001-handshake" / "tasks.jsonl"
        )
        sibling_ledger.parent.mkdir(parents=True, exist_ok=True)
        sibling_ledger.write_text(
            json.dumps(self._SIBLING_COMPLETED) + "\n", encoding="utf-8"
        )
        issues = root / "specs" / "issues.jsonl"
        issues.parent.mkdir(parents=True, exist_ok=True)
        issues.write_text(
            json.dumps(
                {
                    "issue_id": "001-001",
                    "source_file": (
                        "specs/001-phone-to-pi-relay/issues/001-handshake.md"
                    ),
                }
            )
            + "\n"
            + json.dumps(
                {
                    "issue_id": "001-002",
                    "source_file": (
                        "specs/001-phone-to-pi-relay/issues/"
                        "002-node-pairing-and-presence.md"
                    ),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        tasks_md = (
            root
            / "specs"
            / "001-phone-to-pi-relay"
            / "002-node-pairing-and-presence"
            / "tasks.md"
        )
        tasks_md.parent.mkdir(parents=True, exist_ok=True)
        tasks_md.write_text(tasks_md_body, encoding="utf-8")
        subprocess.run(
            [
                "git",
                "checkout",
                "-b",
                "feat/001-phone-to-pi-relay/002-node-pairing-and-presence",
            ],
            cwd=root,
            env=_git_env(),
            check=True,
        )
        return sibling_ledger

    def _idle_session(self, root: Path) -> None:
        dot_dir = root / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        SessionState(current_phase="IDLE").save(dot_dir / "session.json")

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._dispatch_task")
    def test_pinned_run_TSK_001_04_skips_sibling_TASK_ALREADY_DONE(
        self,
        mock_dispatch,
        mock_agent,
        mock_pytest,
        mock_run_test,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-001: pinned run does not skip this issue's PENDING TSK."""
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        self._seed_empty_active_with_sibling_completed(
            tmp_git_repo,
            tasks_md_body="# Tasks\n\n- [ ] TSK-001-04: pair node presence\n",
        )
        self._idle_session(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["micro", "run", "TSK-001-04"])

        assert "TASK_ALREADY_DONE" not in result.output, (
            "sibling COMPLETED TSK-001-04 must not print TASK_ALREADY_DONE: "
            f"{result.output}"
        )
        mock_dispatch.assert_called()
        task = mock_dispatch.call_args[0][0]
        assert task.get("issue_id") == "001-002", (
            "pinned dispatch must use the branch issue_id 001-002, "
            f"got {task.get('issue_id')!r}"
        )
        assert task.get("status") == "PENDING"
        assert task.get("id") == "TSK-001-04"

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._dispatch_task")
    def test_run_single_refuses_TASK_ALREADY_DONE_for_foreign_completed(
        self,
        mock_dispatch,
        mock_agent,
        mock_pytest,
        tmp_git_repo: Path,
    ) -> None:
        """AC-PLAN-007: IDLE + foreign COMPLETED must not take already-done."""
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        sibling_ledger = self._seed_empty_active_with_sibling_completed(
            tmp_git_repo,
            tasks_md_body="# Tasks\n\n- [ ] TSK-001-04: pair node presence\n",
        )
        self._idle_session(tmp_git_repo)
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)

        with chdir(tmp_git_repo):
            with patch(
                "deviate.cli.micro._find_task_record",
                return_value=(self._SIBLING_COMPLETED, sibling_ledger),
            ):
                try:
                    _run_single("TSK-001-04", tmp_git_repo, console)
                    exit_code = 0
                except typer.Exit as exc:
                    exit_code = exc.exit_code

        output = buf.getvalue()
        assert "TASK_ALREADY_DONE" not in output, (
            f"foreign COMPLETED record must not print TASK_ALREADY_DONE: {output}"
        )
        if "TASK_NOT_FOUND" in output:
            assert exit_code == 1
            mock_dispatch.assert_not_called()
        else:
            mock_dispatch.assert_called()
            task = mock_dispatch.call_args[0][0]
            assert task.get("issue_id") == "001-002", (
                "_run_single must re-resolve the branch issue 001-002, "
                f"got {task.get('issue_id')!r}"
            )
            assert task.get("id") == "TSK-001-04"
            assert task.get("status") == "PENDING"


class TestSessionResume:
    """JSONL-authoritative resume: _run_single dispatches from the task's
    latest records status in tasks.jsonl, not from session.json."""

    _RESUME_MANIFEST = HandoverManifest(
        phase="JUDGE", status="SUCCESS", task_id="TSK-005-07"
    )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._invoke_agent")
    def test_run_resumes_from_judge(
        self, mock_agent, mock_verify, tmp_git_repo: Path, approve_gate2
    ):
        mock_agent.return_value = (self._RESUME_MANIFEST, "")
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            # Tracked JSONL parks the task in JUDGE (crash mid-cycle).
            session = SessionState(current_phase="JUDGE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Resume from JUDGE",
                status="JUDGE",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-005-07"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" not in result.output, (
                f"JUDGE JSONL resume must skip RED phase: {result.output}"
            )
            assert "JUDGE" in result.output, (
                f"Expected JUDGE phase in output: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._find_test_files", return_value=["tests/test_red.py"])
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent")
    def test_stale_session_phase_ignored_after_jsonl_reset(
        self,
        mock_agent,
        mock_run_test,
        mock_find_tests,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """A stale session phase must not drive dispatch after a JSONL reset.

        ``git reset`` reverts the tracked ``specs/**/tasks.jsonl`` to an
        earlier state (here PENDING), but ``.deviate/session.json`` is not
        tracked and survives. The runner must read RED/GREEN/REFACTOR
        progress from the JSONL, so the stale ``current_phase="JUDGE"`` session
        must NOT resume JUDGE — the reset task must start at RED."""
        recorded_phases: list[str] = []

        def _recording_agent(*args, **kwargs):
            phase = kwargs.get("phase", "RED")
            recorded_phases.append(phase)
            return HandoverManifest(
                phase=phase,
                status="SUCCESS",
                task_id=kwargs.get("task_id", "TSK-005-07"),
            ), ""

        mock_agent.side_effect = _recording_agent
        # Side effects: RED (fail) -> GREEN (pass) -> REFACTOR (pass).
        mock_run_test.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="1 failed",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="1 passed",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="1 passed",
                stderr="",
            ),
        ]
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            # Stale session: parked at JUDGE from a previous interrupted run.
            # The tracked JSONL was reset to PENDING, so this is inconsistent.
            session = SessionState(current_phase="JUDGE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Reset task must start at RED",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-005-07"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "RED" in recorded_phases, (
                "Stale JUDGE session must not suppress RED after a JSONL "
                + f"reset; got agent phases: {recorded_phases}"
            )
            assert recorded_phases[0] == "RED", (
                "A PENDING JSONL task must start at RED, not resume the stale "
                + f"JUDGE phase: {recorded_phases}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._commit_phase", return_value=True)
    @patch("deviate.cli.micro._run_test_cmd")
    @patch("deviate.cli.micro._invoke_agent")
    def test_run_profile_fast_resumes_green_when_red_done(
        self,
        mock_agent,
        mock_run_test,
        mock_commit,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """--profile fast must still run GREEN when RED is already done.

        Regression: the fast profile (no_judge=True) eagerly set
        ``judge_passed``, which short-circuited the GREEN train loop entirely —
        a task whose RED phase was already recorded was marked COMPLETED
        without its test ever being implemented.
        """
        recorded_phases: list[str] = []

        def _recording_agent(*args, **kwargs):
            phase = kwargs.get("phase", "RED")
            recorded_phases.append(phase)
            return HandoverManifest(
                phase=phase,
                status="SUCCESS",
                task_id=kwargs.get("task_id", "TSK-005-07"),
            ), ""

        mock_agent.side_effect = _recording_agent
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            # RED is already done: session parked in RED, ledger records the
            # RED transition after the PENDING entry.
            session = SessionState(
                current_phase="RED",
                red_commit_sha="deadbeef1234567890abcdef1234567890abcdef",
            )
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Resume GREEN after RED with fast profile",
                status="PENDING",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            red_record = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Resume GREEN after RED with fast profile",
                status="RED",
                execution_mode="TDD",
            )
            append_task_transition(red_record, ledger_path)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            result = runner.invoke(
                cli, ["micro", "run", "TSK-005-07", "--profile", "fast"]
            )

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "GREEN" in result.output, (
                f"Expected GREEN to resume when JSONL records RED done: {result.output}"
            )
            assert "RED →" not in result.output and "◐  RED" not in result.output, (
                f"RED must not re-enter when JSONL records it done: {result.output}"
            )
            assert "GREEN" in recorded_phases, (
                "Expected GREEN phase to run when RED is already done, "
                f"got agent phases: {recorded_phases}"
            )
            assert "RED" not in recorded_phases, (
                f"RED agent must not re-run when RED is already done: {recorded_phases}"
            )
            assert "JUDGE" not in result.output, (
                f"JUDGE phase should be skipped with --profile fast: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to reach COMPLETED: {result.output}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._invoke_agent")
    def test_idle_session_ledger_judge_resumes_judge(
        self, mock_agent, mock_pytest, mock_verify, tmp_git_repo: Path, approve_gate2
    ):
        """GH-193: IDLE + ledger JUDGE (no COMPLETED) is mid-flight, not done.

        After COMPLETED_EVIDENCE_MISSING or a mid-JUDGE interrupt, session.json
        resets to IDLE while tasks.jsonl stays at JUDGE. ``TASK_ALREADY_DONE``
        is only for COMPLETED — re-enter JUDGE instead of exiting 0.
        """
        recorded_phases: list[str] = []

        def _recording_agent(*args, **kwargs):
            phase = kwargs.get("phase", "RED")
            recorded_phases.append(phase)
            return HandoverManifest(
                phase=phase,
                status="SUCCESS",
                task_id=kwargs.get("task_id", "TSK-005-07"),
            ), ""

        mock_agent.side_effect = _recording_agent
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            pending = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Interrupted at JUDGE",
                status="PENDING",
                execution_mode="TDD",
            )
            red = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Interrupted at JUDGE",
                status="RED",
                execution_mode="TDD",
            )
            green = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Interrupted at JUDGE",
                status="GREEN",
                execution_mode="TDD",
            )
            judge = _make_task_record(
                task_id="TSK-005-07",
                issue_id="ISS-002-005",
                description="Interrupted at JUDGE",
                status="JUDGE",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, pending, red, green, judge)
            approve_gate2(tmp_git_repo, issue_id=judge.issue_id)

            result = runner.invoke(cli, ["micro", "run", "TSK-005-07"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            assert "TASK_ALREADY_DONE" not in result.output, (
                "IDLE + ledger JUDGE without COMPLETED must not claim "
                f"already completed: {result.output}"
            )
            assert "JUDGE" in recorded_phases, (
                "IDLE + ledger JUDGE must resume JUDGE; "
                f"got agent phases: {recorded_phases}"
            )
            assert recorded_phases[0] == "JUDGE", (
                f"must re-enter at JUDGE, not restart RED: {recorded_phases}"
            )
            assert "RED" not in recorded_phases, (
                f"JUDGE resume must skip RED: {recorded_phases}"
            )

    @patch("deviate.cli.micro._verify_clean_worktree")
    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._dispatch_task")
    def test_idle_session_ledger_refactor_and_yellow_resume(
        self,
        mock_dispatch,
        mock_agent,
        mock_pytest,
        mock_verify,
        tmp_git_repo: Path,
        approve_gate2,
    ):
        """IDLE + REFACTOR / YELLOW is mid-flight: resume, do not already-done."""
        mock_pytest.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        )
        mock_agent.return_value = (self._RESUME_MANIFEST, "")

        def _invoke_idle(status: str, task_id: str) -> object:
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True, exist_ok=True)
            SessionState(current_phase="IDLE").save(dot_dir / "session.json")
            if status == "YELLOW":
                ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
                ledger_path.parent.mkdir(parents=True, exist_ok=True)
                ledger_path.write_text(
                    json.dumps(
                        {
                            "id": task_id,
                            "issue_id": "ISS-002-005",
                            "description": f"Interrupted at {status}",
                            "status": status,
                            "execution_mode": "TDD",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                approve_gate2(tmp_git_repo, issue_id="ISS-002-005")
            else:
                task = _make_task_record(
                    task_id=task_id,
                    issue_id="ISS-002-005",
                    description=f"Interrupted at {status}",
                    status=status,
                    execution_mode="TDD",
                )
                ledger_path = Path("specs") / "005-micro-layer" / "tasks.jsonl"
                _write_ledger(ledger_path, task)
                approve_gate2(tmp_git_repo, issue_id=task.issue_id)
            return runner.invoke(cli, ["micro", "run", task_id])

        with chdir(tmp_git_repo):
            refactor = _invoke_idle("REFACTOR", "TSK-005-07")
            yellow = _invoke_idle("YELLOW", "TSK-005-08")

        assert "TASK_ALREADY_DONE" not in refactor.output, (
            f"IDLE + ledger REFACTOR must resume: {refactor.output}"
        )
        assert "TASK_ALREADY_DONE" not in yellow.output, (
            f"IDLE + ledger YELLOW must resume: {yellow.output}"
        )
        assert mock_dispatch.call_count == 2, (
            f"expected REFACTOR and YELLOW to dispatch, got {mock_dispatch.call_count}"
        )
        start_phases = [
            call.kwargs.get("start_phase") for call in mock_dispatch.call_args_list
        ]
        assert start_phases[0] == "REFACTOR", (
            f"REFACTOR ledger must resume REFACTOR, got {start_phases[0]!r}"
        )
        assert start_phases[1] == "YELLOW", (
            f"YELLOW ledger must resume YELLOW, got {start_phases[1]!r}"
        )

    @patch("deviate.cli.micro._invoke_agent", side_effect=_mock_invoke_agent)
    @patch("deviate.cli.micro._run_test_cmd")
    def test_execute_phase_trusts_agent_no_test_retry(
        self, mock_run_test, mock_agent, tmp_git_repo: Path, approve_gate2
    ):
        """EXECUTE phase trusts the agent's manifest and skips a post-run test gate.

        Tests may fail after EXECUTE — JUDGE is the authoritative verification phase.
        The runner must not invoke _run_test_cmd after EXECUTE implementation.
        """
        mock_run_test.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="FAILED test_exec_fail\n1 failed", stderr=""
        )
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-98",
                issue_id="ISS-001-004",
                description="Execute trusts agent",
                status="PENDING",
                execution_mode="DIRECT",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)
            approve_gate2(tmp_git_repo, issue_id=task.issue_id)

            Path("README.md").write_text("# repo\n")
            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: init"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["micro", "run", "TSK-004-98"])

            assert result.exit_code == 0, (
                f"Expected zero exit when EXECUTE trusts the agent, "
                f"got {result.exit_code}: {result.output}"
            )
            assert "COMPLETED" in result.output, (
                f"Expected task to reach COMPLETED: {result.output}"
            )
            assert "TEST_FAILURE" not in result.output, (
                f"EXECUTE must not surface test-failure retries: {result.output}"
            )
            mock_run_test.assert_not_called()


class TestAutoFlag:
    """``deviate micro run --auto`` spawns the agent with the deviatdd slash
    command as the prompt instead of running an internal micro phase."""

    def _seed_minimal_worktree(self, tmp_path: Path, backend: str) -> None:
        from deviate.cli.micro import _DEVIATDD_SLASH_COMMAND  # noqa: F401

        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text(f'[agent]\nbackend = "{backend}"\n', encoding="utf-8")
        session = SessionState(current_phase="IDLE")
        session.save(dot_dir / "session.json")

    def test_auto_flag_uses_slash_command_for_pi_backend(self, tmp_path: Path) -> None:
        from deviate.cli.micro import _DEVIATDD_SLASH_COMMAND

        self._seed_minimal_worktree(tmp_path, "pi")
        captured: dict[str, object] = {}

        def fake_invoke_agent(
            prompt, c, *, backend_name, task_id, phase, output_callback=None, model=None
        ):
            captured["prompt"] = prompt
            captured["backend_name"] = backend_name
            captured["phase"] = phase
            return None, ""

        with chdir(tmp_path):
            with patch(
                "deviate.cli.micro._invoke_agent", side_effect=fake_invoke_agent
            ):
                result = runner.invoke(cli, ["micro", "run", "--auto"])

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}: {result.output}"
        )
        assert captured["prompt"] == _DEVIATDD_SLASH_COMMAND["pi"]
        assert captured["prompt"] == "/skills:deviatdd"
        assert captured["backend_name"] == "pi"
        assert captured["phase"] == "AUTO"

    def test_auto_flag_uses_slash_command_for_claude_backend(
        self, tmp_path: Path
    ) -> None:
        self._seed_minimal_worktree(tmp_path, "claude")
        captured: dict[str, object] = {}

        def fake_invoke_agent(
            prompt, c, *, backend_name, task_id, phase, output_callback=None, model=None
        ):
            captured["prompt"] = prompt
            return None, ""

        with chdir(tmp_path):
            with patch(
                "deviate.cli.micro._invoke_agent", side_effect=fake_invoke_agent
            ):
                result = runner.invoke(cli, ["micro", "run", "--auto"])

        assert result.exit_code == 0
        assert captured["prompt"] == "/deviatdd"

    def test_auto_flag_unknown_backend_exits_nonzero(self, tmp_path: Path) -> None:
        self._seed_minimal_worktree(tmp_path, "droid")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["micro", "run", "--auto"])

        assert result.exit_code != 0, (
            f"Expected non-zero exit for unsupported backend, got "
            f"{result.exit_code}: {result.output}"
        )
        assert "AUTO_NO_SLASH_COMMAND" in result.output

    def test_auto_flag_skips_normal_dispatch(self, tmp_path: Path) -> None:
        """``--auto`` must NOT call ``_run_single`` or ``_run_all``."""
        from deviate.cli.micro import _DEVIATDD_SLASH_COMMAND

        self._seed_minimal_worktree(tmp_path, "omp")
        with chdir(tmp_path):
            with patch("deviate.cli.micro._invoke_agent", return_value=(None, "")):
                with patch("deviate.cli.micro._run_single") as mock_single:
                    with patch("deviate.cli.micro._run_all") as mock_all:
                        result = runner.invoke(cli, ["micro", "run", "--auto"])

        assert result.exit_code == 0
        mock_single.assert_not_called()
        mock_all.assert_not_called()
        # Slash command still forwarded correctly for omp.
        assert _DEVIATDD_SLASH_COMMAND["omp"] == "/skills:deviatdd"
