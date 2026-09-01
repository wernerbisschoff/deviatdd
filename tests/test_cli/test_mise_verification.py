"""GH-156: mise-aware verification for pre, prompt, and runner.

One resolver decides the exact command for ``deviate <phase> pre``,
``_build_auto_prompt`` ``{test_command}``, and ``_run_test_cmd``.
Partial/filtered commands stay partial (``mise exec --``); full suite
picks an allowlisted named task; ``mise doctor`` is preflight only.
"""

from __future__ import annotations

import json
import re
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli import micro
from deviate.cli._safe_commands import is_safe_test_command, parse_safe_command
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()

_PRE_ISSUE_SLUG = "001-wallet"


def _pre_ledger_path(root: Path) -> Path:
    return root / "specs" / "001-feature" / _PRE_ISSUE_SLUG / "tasks.jsonl"


def _write_mise(root: Path, body: str, *, hidden: bool = False) -> Path:
    path = root / (".mise.toml" if hidden else "mise.toml")
    path.write_text(body, encoding="utf-8")
    return path


def _make_task(
    *,
    task_id: str = "TSK-001-01",
    issue_id: str = "ISS-001",
    description: str = "wallet withdrawal",
    verification: str | None = None,
    status: str = "PENDING",
) -> dict[str, str]:
    task: dict[str, str] = {
        "id": task_id,
        "issue_id": issue_id,
        "description": description,
        "status": status,
        "execution_mode": "TDD",
    }
    if verification is not None:
        task["verification"] = verification
    return task


def _seed_pre_workspace(
    root: Path,
    *,
    task_id: str = "TSK-001-01",
    issue_id: str = "ISS-001",
    description: str = "wallet withdrawal",
    verification: str | None = None,
    status: str = "PENDING",
    phase: str = "IDLE",
) -> dict[str, str]:
    task = _make_task(
        task_id=task_id,
        issue_id=issue_id,
        description=description,
        verification=verification,
        status=status,
    )
    issue_slug = _PRE_ISSUE_SLUG
    source_file = f"specs/001-feature/issues/{issue_slug}.md"
    spec_dir = root / "specs" / "001-feature" / issue_slug
    spec_dir.mkdir(parents=True, exist_ok=True)
    issue_md = root / source_file
    issue_md.parent.mkdir(parents=True, exist_ok=True)
    issue_md.write_text(f"# {description}\n", encoding="utf-8")
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": issue_id, "source_file": source_file}) + "\n",
        encoding="utf-8",
    )
    record = TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description,
        status=status,
        execution_mode="TDD",
    )
    (spec_dir / "tasks.jsonl").write_text(
        record.model_dump_json() + "\n", encoding="utf-8"
    )
    verification_line = (
        f"  - **Verification**: `{verification}`\n" if verification else ""
    )
    (spec_dir / "tasks.md").write_text(
        f"# Tasks\n\n- {task_id}: {description}\n{verification_line}",
        encoding="utf-8",
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase=phase, active_issue_id=issue_id).save(session_path)
    return task


def _fake_run_ok(
    command: str, cwd: Path, **kwargs: object
) -> subprocess.CompletedProcess:
    argv = command.split()
    return subprocess.CompletedProcess(argv, 0, "ok", "")


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class TestResolveVerificationCommand:
    def test_full_suite_with_test_task_returns_mise_test(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        assert micro._resolve_verification_command(tmp_path) == "mise test"

    def test_hidden_mise_toml_is_detected(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n', hidden=True)
        assert micro._resolve_verification_command(tmp_path) == "mise test"

    def test_partial_file_wraps_mise_exec_and_does_not_expand_to_mise_test(
        self, tmp_path: Path
    ) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        declared = "pytest tests/test_crypto_withdrawal.py"
        task = _make_task(verification=declared)
        resolved = micro._resolve_verification_command(tmp_path, task)
        assert resolved == f"mise exec -- {declared}"
        assert "mise test" not in resolved
        assert "mise unit" not in resolved

    def test_partial_k_filter_wraps_mise_exec(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n[tasks.unit]\nrun = "pytest -m unit"\n',
        )
        declared = (
            "pytest tests/test_crypto_withdrawal.py "
            "-k 'crypto_withdrawal and migration'"
        )
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(verification=declared)
        )
        assert resolved == f"mise exec -- {declared}"
        assert resolved.startswith("mise exec -- ")
        assert "mise test" not in resolved

    def test_partial_node_id_wraps_mise_exec(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        declared = "pytest tests/test_foo.py::test_bar"
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(verification=declared)
        )
        assert resolved == f"mise exec -- {declared}"

    def test_mise_present_no_test_task_wraps_declared(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.lint]\nrun = "ruff check"\n')
        declared = "pytest tests/foo.py"
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(verification=declared)
        )
        assert resolved == f"mise exec -- {declared}"

    def test_no_mise_keeps_declared_command(self, tmp_path: Path) -> None:
        declared = "pytest tests/foo.py -q"
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(verification=declared)
        )
        assert resolved == declared

    def test_named_unit_task_for_unit_markers(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n[tasks.unit]\nrun = "pytest -m unit"\n',
        )
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(description="unit test for withdrawal")
        )
        assert resolved == "mise unit"

    def test_named_integ_task_prefers_repo_name(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.integ]\nrun = "pytest -m integ"\n')
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(description="integration path for ledger")
        )
        assert resolved == "mise integ"

    def test_named_integration_task_when_that_is_the_defined_name(
        self, tmp_path: Path
    ) -> None:
        _write_mise(tmp_path, '[tasks.integration]\nrun = "pytest -m integration"\n')
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(description="integration coverage")
        )
        assert resolved == "mise integration"

    def test_ambiguous_unit_and_integ_prefers_mise_test(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n'
            '[tasks.unit]\nrun = "pytest -m unit"\n'
            '[tasks.integ]\nrun = "pytest -m integ"\n',
        )
        resolved = micro._resolve_verification_command(
            tmp_path,
            _make_task(description="unit and integration coverage"),
        )
        assert resolved == "mise test"

    def test_ambiguous_without_test_task_prefers_unit_never_e2e(
        self, tmp_path: Path
    ) -> None:
        _write_mise(
            tmp_path,
            '[tasks.unit]\nrun = "pytest -m unit"\n'
            '[tasks.integ]\nrun = "pytest -m integ"\n'
            '[tasks.e2e]\nrun = "pytest -m e2e"\n',
        )
        resolved = micro._resolve_verification_command(
            tmp_path,
            _make_task(description="unit and integration coverage"),
        )
        assert resolved == "mise unit"
        assert resolved != "mise e2e"

    def test_generic_green_does_not_select_e2e(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n[tasks.e2e]\nrun = "playwright"\n',
        )
        resolved = micro._resolve_verification_command(
            tmp_path, _make_task(description="GREEN implement withdrawal")
        )
        assert resolved == "mise test"
        assert resolved != "mise e2e"

    def test_explicit_e2e_verification_selects_mise_e2e(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n[tasks.e2e]\nrun = "playwright"\n',
        )
        resolved = micro._resolve_verification_command(
            tmp_path,
            _make_task(
                description="e2e browser flow",
                verification="pytest tests/e2e -v",
            ),
        )
        assert resolved == "mise e2e"

    def test_allowlisted_tasks_omit_unrelated_names(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.test]\nrun = "pytest"\n'
            '[tasks.doctor]\nrun = "true"\n'
            '[tasks.setup]\nrun = "uv sync"\n'
            '[tasks.watch]\nrun = "true"\n'
            '[tasks.fmt]\nrun = "ruff format"\n',
        )
        names = micro._mise_allowlisted_tasks(tmp_path)
        assert names == ["doctor", "test"]
        assert "setup" not in names
        assert "watch" not in names
        assert "fmt" not in names


# ---------------------------------------------------------------------------
# Prompt + runner share the resolver
# ---------------------------------------------------------------------------


class TestPromptAndRunnerShareResolver:
    def test_red_green_prompt_contains_mise_test(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        task = _make_task()
        for phase in ("red", "green", "refactor"):
            prompt = micro._build_auto_prompt(phase, task, tmp_path)
            assert "mise test" in prompt, phase
            assert "Run this exact test_command" in prompt, phase
            assert re.search(r"```bash\n\s*mise test\n\s*```", prompt), phase

    def test_green_prompt_contains_mise_exec_for_partial(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        declared = "pytest tests/test_crypto_withdrawal.py -k 'crypto_withdrawal and migration'"
        prompt = micro._build_auto_prompt(
            "green", _make_task(verification=declared), tmp_path
        )
        assert f"mise exec -- {declared}" in prompt
        assert (
            "mise test" not in prompt.split("mise exec")[0] or "mise exec --" in prompt
        )
        # The injected test_command must not be a bare full-suite mise test.
        assert "```bash\nmise test\n```" not in prompt

    def test_run_test_cmd_invokes_mise_test(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        calls: list[str] = []

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro.run_safe_command", side_effect=fake_run):
            result = micro._run_test_cmd(root)

        assert result.returncode == 0
        assert calls == ["mise test"]

    def test_run_test_cmd_invokes_mise_exec_for_partial_not_mise_test(
        self, tmp_git_repo: Path
    ) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        declared = "pytest tests/test_crypto_withdrawal.py -k 'crypto_withdrawal and migration'"
        calls: list[str] = []

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro.run_safe_command", side_effect=fake_run):
            result = micro._run_test_cmd(root, _make_task(verification=declared))

        assert result.returncode == 0
        assert calls == [f"mise exec -- {declared}"]
        assert "mise test" not in calls

    def test_transcript_logs_exact_command(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        logged: list[tuple[str, dict[str, object]]] = []

        def capture(event: str, **kwargs: object) -> None:
            logged.append((event, kwargs))

        with (
            patch("deviate.cli.micro.run_safe_command", side_effect=_fake_run_ok),
            patch("deviate.cli.micro._log_run", side_effect=capture),
        ):
            micro._run_test_cmd(root)

        commands = [
            kwargs.get("command")
            for event, kwargs in logged
            if event == "TEST_COMMAND" or "command" in kwargs
        ]
        assert "mise test" in commands


# ---------------------------------------------------------------------------
# Doctor preflight
# ---------------------------------------------------------------------------


class TestDoctorPreflight:
    def test_doctor_runs_before_test_command(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "true"\n[tasks.test]\nrun = "pytest"\n',
        )
        calls: list[str] = []

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro.run_safe_command", side_effect=fake_run):
            micro._run_test_cmd(root)

        assert calls[0] == "mise doctor"
        assert "mise test" in calls
        assert calls.index("mise doctor") < calls.index("mise test")

    def test_doctor_runs_before_partial_mise_exec(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "true"\n[tasks.test]\nrun = "pytest"\n',
        )
        declared = "pytest tests/foo.py"
        calls: list[str] = []

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro.run_safe_command", side_effect=fake_run):
            micro._run_test_cmd(root, _make_task(verification=declared))

        assert calls == ["mise doctor", f"mise exec -- {declared}"]

    def test_absent_doctor_skips_preflight(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        calls: list[str] = []

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with patch("deviate.cli.micro.run_safe_command", side_effect=fake_run):
            micro._run_test_cmd(root)

        assert "mise doctor" not in calls
        assert calls == ["mise test"]

    def test_failing_doctor_does_not_write_red_ledger(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "false"\n[tasks.test]\nrun = "pytest"\n',
        )
        task = _seed_pre_workspace(root)
        ledger = _pre_ledger_path(root)
        before = ledger.read_text(encoding="utf-8")
        session_path = root / ".deviate" / "session.json"
        session = SessionState.load(session_path)

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if command == "mise doctor":
                return subprocess.CompletedProcess(
                    ["mise", "doctor"], 1, "", "db is down"
                )
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with (
            chdir(root),
            patch("deviate.cli.micro.run_safe_command", side_effect=fake_run),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(
                    HandoverManifest(phase="RED", status="PASS", task_id=task["id"]),
                    "",
                ),
            ),
            pytest.raises(micro.EnvNotReadyError),
        ):
            micro._run_red_phase(
                task,
                ledger,
                session,
                session_path,
                Console(quiet=True),
            )

        after = ledger.read_text(encoding="utf-8")
        assert after == before
        assert '"status":"RED"' not in after.replace(" ", "")

    def test_failing_doctor_does_not_write_green_ledger(
        self, tmp_git_repo: Path
    ) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "false"\n[tasks.test]\nrun = "pytest"\n',
        )
        task = _seed_pre_workspace(root, status="RED", phase="RED")
        ledger = _pre_ledger_path(root)
        before = ledger.read_text(encoding="utf-8")
        session_path = root / ".deviate" / "session.json"
        session = SessionState.load(session_path)
        session.red_commit_sha = "seed-red-boundary"
        session.save(session_path)

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if command == "mise doctor":
                return subprocess.CompletedProcess(
                    ["mise", "doctor"], 1, "", "port in use"
                )
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with (
            chdir(root),
            patch("deviate.cli.micro.run_safe_command", side_effect=fake_run),
            patch("deviate.cli.micro._phase_already_done", return_value=False),
            patch("deviate.cli.micro._log_run"),
            patch("deviate.cli.micro._make_agent_output_callback", return_value=None),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch(
                "deviate.cli.micro._invoke_agent",
                return_value=(
                    HandoverManifest(phase="GREEN", status="PASS", task_id=task["id"]),
                    "",
                ),
            ),
            pytest.raises(micro.EnvNotReadyError),
        ):
            micro._run_green_phase(
                task,
                ledger,
                session,
                session_path,
                Console(quiet=True),
            )

        after = ledger.read_text(encoding="utf-8")
        assert after == before
        assert '"status":"GREEN"' not in after.replace(" ", "")
        session_after = SessionState.load(session_path)
        assert session_after.failure_kind != "mechanical"

    def test_prompt_includes_doctor_when_defined(self, tmp_path: Path) -> None:
        _write_mise(
            tmp_path,
            '[tasks.doctor]\nrun = "true"\n[tasks.test]\nrun = "pytest"\n',
        )
        prompt = micro._build_auto_prompt("red", _make_task(), tmp_path)
        assert "mise doctor" in prompt

    def test_prompt_omits_doctor_when_absent(self, tmp_path: Path) -> None:
        _write_mise(tmp_path, '[tasks.test]\nrun = "pytest"\n')
        prompt = micro._build_auto_prompt("red", _make_task(), tmp_path)
        assert "mise doctor" not in prompt


# ---------------------------------------------------------------------------
# Pre JSON
# ---------------------------------------------------------------------------


class TestPhasePreMiseContract:
    def test_red_pre_emits_mise_test_and_allowlisted_tasks(
        self, tmp_git_repo: Path
    ) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.test]\nrun = "pytest"\n'
            '[tasks.unit]\nrun = "pytest -m unit"\n'
            '[tasks.setup]\nrun = "uv sync"\n',
        )
        _seed_pre_workspace(root)
        with chdir(root):
            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-001-01"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output[result.output.find("{") :])
        assert data["test_command"] == "mise test"
        assert data["mise_tasks"] == ["test", "unit"]
        assert "setup" not in data["mise_tasks"]
        assert "doctor" not in data

    def test_green_pre_emits_resolved_partial_and_mise_tasks(
        self, tmp_git_repo: Path
    ) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        declared = "pytest tests/test_crypto_withdrawal.py -k 'crypto_withdrawal and migration'"
        _seed_pre_workspace(root, verification=declared, status="RED", phase="RED")
        with chdir(root):
            result = runner.invoke(cli, ["green", "pre", "--task", "TSK-001-01"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output[result.output.find("{") :])
        assert data["test_command"] == f"mise exec -- {declared}"
        assert data["mise_tasks"] == ["test"]

    def test_refactor_pre_emits_resolved_mise_test(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(root, '[tasks.test]\nrun = "pytest"\n')
        _seed_pre_workspace(root, status="GREEN", phase="GREEN")
        with chdir(root):
            result = runner.invoke(cli, ["refactor", "pre", "--task", "TSK-001-01"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output[result.output.find("{") :])
        assert data["test_command"] == "mise test"
        assert data["mise_tasks"] == ["test"]

    def test_red_pre_runs_doctor_and_records_ok(self, tmp_git_repo: Path) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "true"\n[tasks.test]\nrun = "pytest"\n',
        )
        _seed_pre_workspace(root)
        with (
            chdir(root),
            patch("deviate.cli.micro.run_safe_command", side_effect=_fake_run_ok),
        ):
            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-001-01"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output[result.output.find("{") :])
        assert data["test_command"] == "mise test"
        assert data["mise_tasks"] == ["doctor", "test"]
        assert data["doctor"]["command"] == "mise doctor"
        assert data["doctor"]["ok"] is True
        assert data["doctor"]["returncode"] == 0

    def test_doctor_failure_on_pre_does_not_write_ledger(
        self, tmp_git_repo: Path
    ) -> None:
        root = tmp_git_repo
        _write_mise(
            root,
            '[tasks.doctor]\nrun = "false"\n[tasks.test]\nrun = "pytest"\n',
        )
        _seed_pre_workspace(root)
        ledger = _pre_ledger_path(root)
        before = ledger.read_text(encoding="utf-8")

        def fake_run(
            command: str, cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess:
            if command == "mise doctor":
                return subprocess.CompletedProcess(
                    ["mise", "doctor"], 2, "", "deps missing"
                )
            return subprocess.CompletedProcess(command.split(), 0, "ok", "")

        with (
            chdir(root),
            patch("deviate.cli.micro.run_safe_command", side_effect=fake_run),
        ):
            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-001-01"])
        assert result.exit_code != 0
        assert "ENV_NOT_READY" in result.output or "doctor" in result.output.lower()
        assert ledger.read_text(encoding="utf-8") == before
        assert '"status": "RED"' not in ledger.read_text(encoding="utf-8")

    def test_no_mise_keeps_existing_red_pre_shape(self, tmp_path: Path) -> None:
        _seed_pre_workspace(tmp_path, verification="pytest tests/foo.py")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_x(): pass\n")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["red", "pre", "--task", "TSK-001-01"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output[result.output.find("{") :])
        assert data["test_command"] == "pytest tests/foo.py"
        assert "mise_tasks" not in data
        assert "doctor" not in data
        assert set(data) >= {"task_id", "test_command", "lint_command", "spec_dir"}


# ---------------------------------------------------------------------------
# Safe-command allowlist for the new mise forms
# ---------------------------------------------------------------------------


class TestMiseCommandsAreAllowlisted:
    @pytest.mark.parametrize(
        "command",
        [
            "mise test",
            "mise unit",
            "mise integ",
            "mise integration",
            "mise e2e",
            "mise doctor",
            "mise exec -- pytest tests/foo.py",
            "mise exec -- pytest tests/foo.py -k crypto_withdrawal",
        ],
    )
    def test_new_mise_forms_accepted(self, command: str) -> None:
        parsed = parse_safe_command(command)
        assert parsed.accepted, (command, parsed.reason)
        assert is_safe_test_command(command)

    @pytest.mark.parametrize(
        "command",
        ["mise setup", "mise seed", "mise watch", "mise fmt", "mise run setup"],
    )
    def test_unknown_mise_tasks_rejected(self, command: str) -> None:
        parsed = parse_safe_command(command)
        assert not parsed.accepted, command
        assert not is_safe_test_command(command)
