from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.ledger import TaskRecord

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "JUDGE phase task",
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


class TestJudgePre:
    def test_judge_pre_clean_diff(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            src_file = Path("src") / "deviate" / "impl.py"
            src_file.parent.mkdir(parents=True)
            src_file.write_text("# implementation\n")

            test_file = Path("tests") / "test_impl.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: baseline implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            result = runner.invoke(cli, ["judge", "pre"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert data.get("verdict") == "COMPLIANCE_PASS", (
                f"Expected COMPLIANCE_PASS, got {data}"
            )

    def test_judge_pre_violation(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            spec_dir = Path("specs") / "004-micro-layer" / "issues"
            spec_dir.mkdir(parents=True)
            spec_file = spec_dir / "ISS-TEST-001.md"
            spec_file.write_text(
                "# Protected Module\n\nModule: src/deviate/core/protected.py\n"
            )

            src_file = Path("src") / "deviate" / "impl.py"
            src_file.parent.mkdir(parents=True)
            src_file.write_text("# implementation\n")

            test_file = Path("tests") / "test_impl.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("def test_pass():\n    assert True\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "feat: baseline"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )

            protected = Path("src") / "deviate" / "core" / "protected.py"
            protected.parent.mkdir(parents=True)
            protected.write_text("# protected module — modified\n")

            result = runner.invoke(cli, ["judge", "pre"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert data.get("verdict") == "COMPLIANCE_VIOLATION", (
                f"Expected COMPLIANCE_VIOLATION, got {data}"
            )
            assert "details" in data


class TestJudgeStructuredDiff:
    """Structured diff injection into JUDGE prompt (TSK-008-03)."""

    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_contains_structured_diff(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.core.treesitter import SymbolChange
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="diff --git a/src/mod.py b/src/mod.py\n@@ -1 +1 @@\n-def old():\n+def new():\n",
            stderr="",
        )

        mock_extract.return_value = [
            SymbolChange(
                language="python", kind="function", name="foo", change="modified"
            ),
        ]

        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-008-03",
            "issue_id": "ISS-ADH-008",
            "description": "Inject structured diff into JUDGE prompt",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        prompt_arg = mock_agent.call_args[0][0]
        assert "## Structured Diff Summary" in prompt_arg, (
            "Expected judge prompt to contain '## Structured Diff Summary' section"
        )
        assert "| python | function | foo | modified |" in prompt_arg, (
            "Expected structured diff table to contain the python function change row"
        )

    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_empty_diff_no_structured_diff_section(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-008-03",
            "issue_id": "ISS-ADH-008",
            "description": "Inject structured diff into JUDGE prompt",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        prompt_arg = mock_agent.call_args[0][0]
        assert "## Structured Diff Summary" not in prompt_arg, (
            "Expected NO structured diff section for empty diff"
        )

    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_structured_diff_mixed_languages(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.core.treesitter import SymbolChange
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "diff --git a/src/py_mod.py b/src/py_mod.py\n"
                "@@ -1 +1 @@\n"
                "-def old_py():\n"
                "+def new_py():\n"
                "diff --git a/src/rs_mod.rs b/src/rs_mod.rs\n"
                "@@ -1 +1 @@\n"
                "-fn old_rs() {}\n"
                "+fn new_rs() {}\n"
            ),
            stderr="",
        )

        mock_extract.side_effect = [
            [
                SymbolChange(
                    language="python",
                    kind="function",
                    name="py_func",
                    change="modified",
                )
            ],
            [
                SymbolChange(
                    language="rust", kind="function", name="rs_func", change="added"
                )
            ],
        ]

        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-008-03",
            "issue_id": "ISS-ADH-008",
            "description": "Inject structured diff into JUDGE prompt",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        prompt_arg = mock_agent.call_args[0][0]
        assert "| python" in prompt_arg, "Expected python row in structured diff table"
        assert "| rust" in prompt_arg, "Expected rust row in structured diff table"

    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_structured_diff_graceful_degradation(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=("diff --git a/src/mod.py b/src/mod.py\n@@ -1 +1 @@\n-foo\n+bar\n"),
            stderr="",
        )

        mock_extract.return_value = []

        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-008-03",
            "issue_id": "ISS-ADH-008",
            "description": "Inject structured diff into JUDGE prompt",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        prompt_arg = mock_agent.call_args[0][0]
        assert "## Structured Diff Summary" not in prompt_arg, (
            "Expected NO structured diff section when extract_changed_symbols returns empty"
        )
