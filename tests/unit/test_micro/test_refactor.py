from __future__ import annotations

import json
import subprocess
import textwrap
from contextlib import chdir
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rich.console import Console

from typer.testing import CliRunner
from deviate.cli import cli
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
    description: str = "REFACTOR phase task",
    status: str = "GREEN",
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


_REFACTOR_PRE_CONTRACT_KEYS = {
    "status",
    "task_id",
    "task_title",
    "task_type",
    "test_strategy",
    "test_write_dir",
    "test_command",
    "lint_command",
    "spec_dir",
    "verification",
    "repo_root",
    "git_branch",
    "timestamp",
    "files_to_refactor",
}

_OUTBOX_PROD = "src/router/admin/webhook_outbox.py"
_OUTBOX_TEST = "tests/outbox/test_admin_replay.py"
_EXTRA_SRC = (
    "src/binance/client.py",
    "src/luno/client.py",
    "src/grpc/server.py",
)


def _seed_refactor_pre_workspace(
    root: Path,
    *,
    include_extra_src: bool = True,
) -> None:
    """Seed session, ledger, tasks.md, and issues.jsonl for TSK-003-03."""
    spec_dir = root / "specs" / "001-feature" / "003-outbox"
    spec_dir.mkdir(parents=True, exist_ok=True)
    issues = root / "specs" / "issues.jsonl"
    issues.parent.mkdir(parents=True, exist_ok=True)
    issues.write_text(
        json.dumps(
            {
                "issue_id": "ISS-001-003",
                "source_file": "specs/001-feature/issues/003-outbox.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    file_lines = "\n".join(
        f"    - `{path}`" for path in (_OUTBOX_PROD, _OUTBOX_TEST, *_EXTRA_SRC)
    )
    (spec_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- TSK-003-03: Replay admin webhook outbox\n"
        "  - **Type**: Feature_Batch\n"
        "  - **Mode**: TDD\n"
        "  - **Verification**: `pytest tests/outbox/test_admin_replay.py -v`\n"
        "  - **Files**:\n"
        f"{file_lines}\n",
        encoding="utf-8",
    )
    task = _make_task_record(
        task_id="TSK-003-03",
        issue_id="ISS-001-003",
        description="Replay admin webhook outbox",
        status="GREEN",
    )
    _write_ledger(spec_dir / "tasks.jsonl", task)

    dot_dir = root / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    session = SessionState(current_phase="GREEN", active_issue_id="ISS-001-003")
    session.save(dot_dir / "session.json")

    if include_extra_src:
        for rel in _EXTRA_SRC:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# extra production module\n", encoding="utf-8")


def _git_commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_env(),
        check=True,
    )


def _seed_red_green_slice(repo: Path) -> None:
    """Two-commit RED+GREEN slice plus extra src files outside that range."""
    _seed_refactor_pre_workspace(repo, include_extra_src=True)
    _git_commit(repo, "chore: baseline with extra src")

    test_file = repo / _OUTBOX_TEST
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "def test_replay():\n    assert False\n",
        encoding="utf-8",
    )
    _git_commit(repo, "test(TSK-003-03): RED")

    prod = repo / _OUTBOX_PROD
    prod.parent.mkdir(parents=True, exist_ok=True)
    prod.write_text("def replay():\n    return True\n", encoding="utf-8")
    test_file.write_text(
        "def test_replay():\n    assert True\n",
        encoding="utf-8",
    )
    _git_commit(repo, "feat(TSK-003-03): GREEN")


class TestRefactorPre:
    def test_refactor_pre_emits_red_green_production_files_and_contract_keys(
        self, tmp_git_repo: Path
    ):
        """Extra src files plus a two-commit RED+GREEN slice list only
        the production file(s) from that slice, plus the documented keys."""
        _seed_red_green_slice(tmp_git_repo)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["refactor", "pre", "--task", "TSK-003-03"])

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}: {result.output}"
        )
        data = json.loads(result.output)
        missing = _REFACTOR_PRE_CONTRACT_KEYS - data.keys()
        assert not missing, f"refactor pre missing contract keys: {sorted(missing)}"
        assert data["status"] == "READY"
        assert data["task_id"] == "TSK-003-03"
        assert data["task_title"] == "Replay admin webhook outbox"
        assert data["task_type"] == "Feature_Batch"
        assert data["verification"] == "pytest tests/outbox/test_admin_replay.py -v"
        assert data["files_to_refactor"] == [_OUTBOX_PROD]
        for extra in _EXTRA_SRC:
            assert extra not in data["files_to_refactor"]
        assert _OUTBOX_TEST not in data["files_to_refactor"]

    def test_refactor_pre_falls_back_to_task_files_minus_tests(
        self, tmp_git_repo: Path
    ):
        """When git HEAD~2..HEAD is unavailable (only the fixture's
        initial commit), use the task Files: list minus tests — never
        glob every src/**/*.py."""
        _seed_refactor_pre_workspace(tmp_git_repo, include_extra_src=True)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["refactor", "pre", "--task", "TSK-003-03"])

        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}: {result.output}"
        )
        data = json.loads(result.output)
        missing = _REFACTOR_PRE_CONTRACT_KEYS - data.keys()
        assert not missing, f"refactor pre missing contract keys: {sorted(missing)}"
        assert _OUTBOX_TEST not in data["files_to_refactor"]
        assert _OUTBOX_PROD in data["files_to_refactor"]
        for extra in _EXTRA_SRC:
            assert extra in data["files_to_refactor"]

    def test_build_auto_prompt_scopes_refactor_to_red_green_production(
        self, tmp_git_repo: Path
    ):
        """Auto assemble_prompt must inject the same RED+GREEN production
        set — not a glob of every src file — and keep the HEAD~2 inspect."""
        from deviate.cli.micro import _build_auto_prompt

        _seed_red_green_slice(tmp_git_repo)
        task = {
            "id": "TSK-003-03",
            "issue_id": "ISS-001-003",
            "description": "Replay admin webhook outbox",
            "status": "GREEN",
            "execution_mode": "TDD",
        }
        prompt = _build_auto_prompt("refactor", task, tmp_git_repo)
        assert "git log -2" in prompt
        assert "git diff HEAD~2..HEAD" in prompt
        start = prompt.index("The REFACTOR production scope")
        end = prompt.index("Do not expand scope beyond these production files.")
        scoped = prompt[start:end]
        assert _OUTBOX_PROD in scoped
        for extra in _EXTRA_SRC:
            assert extra not in scoped, (
                f"auto refactor files_to_refactor must not list extra src file {extra}"
            )


class TestRefactorPost:
    def test_refactor_post_test_invariance(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(
                current_phase="REFACTOR", active_issue_id="ISS-001-004"
            )
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
            )

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: implementation with passing tests"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hi, {name}!'  # refactored\n"
            )

            result = runner.invoke(cli, ["refactor", "post"])

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

    def test_refactor_post_regression_rollback(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(
                current_phase="REFACTOR", active_issue_id="ISS-001-004"
            )
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                status="GREEN",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            test_file = Path("tests") / "test_passing.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            implementation = Path("src") / "deviate" / "impl.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text(
                "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
            )

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: implementation with passing tests"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            implementation.write_text(
                "def greet(name: str) -> str:\n    return 42  # breaks type contract\n"
            )

            result = runner.invoke(cli, ["refactor", "post"])

            assert "RefactorRegressionError" in result.output, (
                f"Expected RefactorRegressionError in output: {result.output}"
            )

            restored = implementation.read_text()
            assert "42" not in restored, (
                "Expected implementation to be restored after regression"
            )


class TestCheckReturnTypeMismatch:
    """_check_return_type_mismatch uses stdlib ``ast`` for Python-only checks."""

    @staticmethod
    def _write_file(tmp_path: Path, filename: str, content: str) -> Path:
        filepath = tmp_path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(textwrap.dedent(content))
        return filepath

    def test_check_return_type_mismatch_python_uses_stdlib_ast(
        self, tmp_path: Path
    ) -> None:
        from deviate.cli.micro import _check_return_type_mismatch

        p = self._write_file(
            tmp_path,
            "mod.py",
            """
            def greet() -> str:
                return 42
        """,
        )
        issues = _check_return_type_mismatch(str(p))
        assert len(issues) > 0, f"Expected return-type mismatch issues, got: {issues}"
        # Issue must be short (function name + line + type), not a dump of the function body.
        for issue in issues:
            assert len(issue) < 100, (
                f"Issue should be short, got {len(issue)} chars: {issue!r}"
            )
        assert any("greet" in issue and "line" in issue for issue in issues), (
            f"Expected issue to mention function name and line, got: {issues}"
        )

    def test_non_python_returns_empty(self, tmp_path: Path) -> None:
        from deviate.cli.micro import _check_return_type_mismatch

        p = self._write_file(
            tmp_path,
            "mod.js",
            """
            function greet() {
                return 42;
            }
        """,
        )
        issues = _check_return_type_mismatch(str(p))
        assert issues == [], f"Expected empty issues for non-Python file, got: {issues}"

    def test_non_supported_language_graceful(self, tmp_path: Path) -> None:
        from deviate.cli.micro import _check_return_type_mismatch

        p = self._write_file(
            tmp_path,
            "mod.rb",
            """
            def foo
              return 1
            end
        """,
        )
        issues = _check_return_type_mismatch(str(p))
        assert issues == [], (
            f"Expected empty issues for unsupported language, got: {issues}"
        )

    def test_syntax_error_no_crash(self, tmp_path: Path) -> None:
        from deviate.cli.micro import _check_return_type_mismatch

        p = self._write_file(
            tmp_path,
            "mod.py",
            """
            def broken(x):
                return x +
        """,
        )
        try:
            issues = _check_return_type_mismatch(str(p))
            assert isinstance(issues, list)
        except Exception as exc:
            raise AssertionError(
                f"_check_return_type_mismatch crashed on syntax error: {exc}"
            ) from exc

    def test_no_annotations_returns_empty(self, tmp_path: Path) -> None:
        from deviate.cli.micro import _check_return_type_mismatch

        p = self._write_file(
            tmp_path,
            "mod.py",
            """
            def greet():
                return 42
        """,
        )
        issues = _check_return_type_mismatch(str(p))
        assert issues == [], (
            f"Expected empty issues for unannotated function, got: {issues}"
        )


def _gate_harness(tmp_path: Path, monkeypatch):
    """Patch REFACTOR seams; return (task, ledger, session, path, spies)."""
    import deviate.cli.micro as m

    ledger = tmp_path / "tasks.jsonl"
    ledger.write_text("", encoding="utf-8")
    task = {
        "id": "TSK-004-01",
        "issue_id": "ISS-001-004",
        "description": "REFACTOR phase task",
        "status": "GREEN",
        "execution_mode": "TDD",
    }
    session = SessionState(current_phase="REFACTOR", active_issue_id="ISS-001-004")
    session_path = tmp_path / "session.json"
    session.save(session_path)
    monkeypatch.setattr(m, "_build_auto_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(m, "resolve_model_for_phase", lambda *a, **k: None)
    monkeypatch.setattr(
        m,
        "_invoke_agent",
        lambda *a, **k: (SimpleNamespace(status="PASS", rationale="ok"), ""),
    )
    monkeypatch.setattr(m, "_verify_clean_worktree", lambda *a, **k: None)
    return task, ledger, session, session_path


class TestRefactorRegressionGate:
    @pytest.mark.behavioral
    def test_nonzero_test_result_raises_with_tail_and_no_completed(
        self, tmp_path, monkeypatch
    ):
        """AC-PLAN-001 (US-005-09): non-zero gate raises PhaseFailedError."""
        import deviate.cli.micro as m

        task, ledger, session, session_path = _gate_harness(tmp_path, monkeypatch)
        fail = subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="FAILED test_x", stderr="boom"
        )
        with (
            patch.object(m, "_run_pytest", return_value=fail),
            patch.object(m, "_run_test_cmd", return_value=fail),
            patch.object(m, "_run_format_cmd") as run_format,
            patch.object(m, "_append_status_transition") as append,
            patch.object(m, "_commit_phase") as commit,
        ):
            with chdir(tmp_path):
                with pytest.raises(m.PhaseFailedError) as exc_info:
                    m._run_refactor_phase(
                        task, ledger, session, session_path, Console()
                    )
            assert "TSK-004-01" in str(exc_info.value)
            assert "FAILED test_x" in str(exc_info.value)
            run_format.assert_not_called()
            commit.assert_not_called()
            assert append.call_count == 0 or all(
                c.args[1] != "COMPLETED" for c in append.call_args_list
            )

    @pytest.mark.behavioral
    def test_zero_test_result_runs_format_appends_completed_goes_idle(
        self, tmp_path, monkeypatch
    ):
        """AC-PLAN-002 (US-005-10): zero gate completes the task."""
        import deviate.cli.micro as m

        task, ledger, session, session_path = _gate_harness(tmp_path, monkeypatch)
        ok = subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="ok", stderr=""
        )
        with (
            patch.object(m, "_run_pytest", return_value=ok),
            patch.object(m, "_run_test_cmd", return_value=ok),
            patch.object(m, "_run_format_cmd") as run_format,
            patch.object(m, "_append_status_transition") as append,
            patch.object(m, "_commit_phase") as commit,
        ):
            with chdir(tmp_path):
                out = m._run_refactor_phase(
                    task, ledger, session, session_path, Console()
                )
            run_format.assert_called_once()
            append.assert_called_once()
            assert append.call_args.args[1] == "COMPLETED"
            commit.assert_called_once()
            assert out.current_phase == "IDLE"

    @pytest.mark.behavioral
    def test_unchanged_passing_suite_has_only_normal_completion_path(
        self, tmp_path, monkeypatch
    ):
        """AC-PLAN-003 (US-005-10): clean gate adds no extra side effects."""
        import deviate.cli.micro as m

        task, ledger, session, session_path = _gate_harness(tmp_path, monkeypatch)
        ok = subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="3 passed", stderr=""
        )
        with (
            patch.object(m, "_run_pytest", return_value=ok),
            patch.object(m, "_run_test_cmd", return_value=ok) as run_test,
            patch.object(m, "_run_format_cmd") as run_format,
            patch.object(m, "_append_status_transition") as append,
            patch.object(m, "_commit_phase") as commit,
        ):
            with chdir(tmp_path):
                m._run_refactor_phase(task, ledger, session, session_path, Console())
            assert run_test.call_count == 1
            assert run_format.call_count == 1
            assert append.call_count == 1
            assert commit.call_count == 1

    @pytest.mark.behavioral
    def test_crash_with_empty_output_raises_without_completed(
        self, tmp_path, monkeypatch
    ):
        """Edge: test-command crash (non-zero, empty output) still fails."""
        import deviate.cli.micro as m

        task, ledger, session, session_path = _gate_harness(tmp_path, monkeypatch)
        crash = subprocess.CompletedProcess(
            args=["pytest"], returncode=2, stdout="", stderr=""
        )
        with (
            patch.object(m, "_run_pytest", return_value=crash),
            patch.object(m, "_run_test_cmd", return_value=crash),
            patch.object(m, "_run_format_cmd") as run_format,
            patch.object(m, "_append_status_transition") as append,
            patch.object(m, "_commit_phase") as commit,
        ):
            with chdir(tmp_path):
                with pytest.raises(m.PhaseFailedError):
                    m._run_refactor_phase(
                        task, ledger, session, session_path, Console()
                    )
            run_format.assert_not_called()
            commit.assert_not_called()
            assert all(c.args[1] != "COMPLETED" for c in append.call_args_list)

    @pytest.mark.behavioral
    def test_already_completed_bypasses_gate(self, tmp_path, monkeypatch):
        """AC-PLAN-004: COMPLETED ledger row skips the gate entirely."""
        import deviate.cli.micro as m

        task, ledger, session, session_path = _gate_harness(tmp_path, monkeypatch)
        done = TaskRecord(
            id="TSK-004-01", issue_id="ISS-001-004", description="t", status="COMPLETED"
        )
        ledger.write_text(done.model_dump_json() + "\n", encoding="utf-8")
        with (
            patch.object(m, "_run_pytest") as run_pytest,
            patch.object(m, "_run_test_cmd") as run_test,
            patch.object(m, "_run_format_cmd") as run_format,
            patch.object(m, "_invoke_agent") as invoke,
        ):
            with chdir(tmp_path):
                m._run_refactor_phase(task, ledger, session, session_path, Console())
            run_test.assert_not_called()
            run_pytest.assert_not_called()
            run_format.assert_not_called()
            invoke.assert_not_called()
