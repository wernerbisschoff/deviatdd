from __future__ import annotations

import json
import pytest
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


class TestJudgePromptDiffSection:
    """JUDGE prompt diff handling (TSK-008-03).

    The structured symbol table (`extract_changed_symbols` →
    `_build_structured_diff_section`) was removed in the tree-sitter
    segfault fix because the C extension left ``subprocess.Popen`` in a
    fork-unsafe state and `except Exception` cannot trap a SIGSEGV.
    These tests are now regression guards asserting the structured
    symbol section is **not** generated regardless of diff content.
    The raw ``<diff>`` block (verified in ``TestJudgePromptRawDiff``)
    remains the source of truth for symbol-level change visibility.
    """

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_no_structured_diff_section_for_python(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
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
            stdout="diff --git a/src/mod.py b/src/mod.py\n@@ -1 +1 @@\n-def old():\n+def new():\n",
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
            "Structured symbol section must NOT be generated: it triggered "
            "the tree-sitter SIGSEGV → subprocess.Popen fork crash. The raw "
            "<diff> block carries the same context."
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

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_no_structured_diff_section_for_mixed_languages(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
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
            "Structured symbol section must NOT be generated even for mixed-"
            "language diffs (a Rust file in particular triggered the SIGSEGV)."
        )

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_prompt_raw_diff_section_still_present(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Regression guard: dropping the tree-sitter section must NOT
        drop the raw ``<diff>`` block (it carries the per-file line-level
        context the JUDGE agent actually consumes)."""
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False

        diff_text = (
            "diff --git a/src/mod.py b/src/mod.py\n"
            "@@ -1 +1 @@\n"
            "-def old():\n"
            "+def new():\n"
        )
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=diff_text, stderr=""
        )

        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-008-03",
            "issue_id": "ISS-ADH-008",
            "description": "Raw diff preservation regression test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        prompt_arg = mock_agent.call_args[0][0]
        assert "<diff>" in prompt_arg, "Raw <diff> block must be present"
        assert "</diff>" in prompt_arg, "Raw </diff> close must be present"
        assert diff_text.strip() in prompt_arg, (
            "Raw diff text must be embedded in the JUDGE prompt verbatim"
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

    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_diff_spans_red_parent_to_include_tests(
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
        """JUDGE must diff against RED's parent so failing tests are visible.

        Regression for TSK-012-02: ``git diff red_sha..HEAD`` collapsed to the
        GREEN commit only (tests already live in ``red_sha``, so they're
        absent from ``..HEAD``). The judge then flagged "SHIP THE 5 TESTS" as
        missing. The diff base must be ``red_sha^`` whenever RED is recorded.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-012-02",
            "issue_id": "ISS-ADH-012",
            "description": "Diff scope regression",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        diff_calls = [
            call
            for call in mock_subprocess.call_args_list
            if call.args and call.args[0][:2] == ["git", "diff"]
        ]
        assert diff_calls, "Expected at least one `git diff` invocation"
        diff_args = diff_calls[0].args[0]
        assert diff_args[2] == "deadbeef1234567890abcdef1234567890abcdef^..HEAD", (
            "JUDGE must diff against RED's parent so RED tests are visible; "
            f"got diff base {diff_args[2]!r}"
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
    def test_judge_diff_fallback_when_no_red_commit(
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
        """When no RED commit is recorded, fallback to HEAD~1..HEAD.

        Mirrors the pre-fix fallback so isolated JUDGE runs (e.g.
        ``deviate micro run --start-phase JUDGE``) still get a meaningful diff
        against the immediate parent — not HEAD~2.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []

        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        task = {
            "id": "TSK-012-02",
            "issue_id": "ISS-ADH-012",
            "description": "Diff fallback regression",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()  # red_commit_sha empty
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        _run_judge_phase(task, ledger_path, session, session_path, Console())

        diff_calls = [
            call
            for call in mock_subprocess.call_args_list
            if call.args and call.args[0][:2] == ["git", "diff"]
        ]
        assert diff_calls
        diff_args = diff_calls[0].args[0]
        assert diff_args[2] == "HEAD~1..HEAD", (
            "Without red_commit_sha, fallback must be HEAD~1..HEAD; "
            f"got {diff_args[2]!r}"
        )


class TestJudgeFeedbackLogging:
    """Surface WHY judge rejected and WHAT changed in tasks.md.

    Regression coverage: prior to this change, ``JUDGE_REJECTED`` was printed
    with ``manifest.rationale`` only, so when the judge populated
    ``train_feedback`` instead of ``rationale`` (or returned an empty
    ``COMPLIANCE_VIOLATION``) the operator saw an empty reason. The tasks.md
    edit happened silently. This suite locks both behaviors down.
    """

    def test_append_judge_feedback_returns_line_count(self, tmp_path: Path) -> None:
        """``_append_judge_feedback`` returns the number of inserted lines.

        Multi-line feedback splits into one feedback-line per source line.
        """
        from deviate.cli.micro import _append_judge_feedback

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-011-05: Sample task\n"
            "  - **Type**: Feature_Batch\n"
            "\n"
            "- TSK-011-06: Another task\n",
            encoding="utf-8",
        )

        added = _append_judge_feedback(
            tasks_md,
            "TSK-011-05",
            "First line of feedback\nSecond line of feedback",
        )

        assert added == 2, f"Expected 2 lines inserted, got {added}"
        content = tasks_md.read_text(encoding="utf-8")
        assert "**Judge Feedback**: First line of feedback" in content
        assert "**Judge Feedback**: Second line of feedback" in content

    def test_append_judge_feedback_returns_none_when_no_match(
        self, tmp_path: Path
    ) -> None:
        """No matching task line → returns ``None`` and leaves the file alone."""
        from deviate.cli.micro import _append_judge_feedback

        tasks_md = tmp_path / "tasks.md"
        original = "# Tasks\n\n- TSK-999-99: Different task\n"
        tasks_md.write_text(original, encoding="utf-8")

        added = _append_judge_feedback(
            tasks_md, "TSK-011-05", "Feedback for missing task"
        )

        assert added is None, f"Expected None when no matching task line, got {added}"
        assert tasks_md.read_text(encoding="utf-8") == original, (
            "File should be unchanged when no task line matches"
        )

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_rejected_prints_train_feedback_not_empty_rationale(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """JUDGE_REJECTED print shows train_feedback even when rationale is empty.

        Regression: prior code printed ``JUDGE_REJECTED {tid}: {rationale}`` and
        then resolved the full feedback afterward, so a verdict carrying
        ``train_feedback="Implement the missing logic per spec"`` and
        ``rationale=""`` rendered as ``JUDGE_REJECTED TSK-...: `` with a
        trailing colon and no body.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        mock_agent.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                task_id="TSK-011-05",
                rationale="",
                train_feedback="Implement the missing logic per spec",
            ),
            "",
        )

        task = {
            "id": "TSK-011-05",
            "issue_id": "ISS-ADH-011",
            "description": "Test train_feedback propagation",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        # Capture console output to assert the train_feedback text appears
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        assert "JUDGE_REJECTED" in output, (
            f"Expected JUDGE_REJECTED in output: {output}"
        )
        assert "Implement the missing logic per spec" in output, (
            f"Expected train_feedback text in JUDGE_REJECTED output, got: {output!r}"
        )
        assert "source=train_feedback" in output, (
            f"Expected source=train_feedback label in output, got: {output!r}"
        )

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_rejected_logs_tasks_md_feedback_change(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """JUDGE_REJECTED path prints and logs TASKS_MD_FEEDBACK with line count.

        Regression: prior to this change the tasks.md edit was silent; the
        operator could not see what changed in the spec, and GREEN had no
        visual cue for the persisted feedback before being re-invoked.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        # Seed the issue ledger + tasks.md. The source_file must follow the
        # production convention specs/<epic>/issues/<slug>.md so
        # _find_tasks_md_for_issue derives the right path.
        specs_dir = tmp_path / "specs"
        (specs_dir / "adhoc" / "001-test-issue-pad-name").mkdir(parents=True)
        (specs_dir / "issues.jsonl").write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-001",
                    "source_file": ("specs/adhoc/issues/001-test-issue-pad-name.md"),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        tasks_md = specs_dir / "adhoc" / "001-test-issue-pad-name" / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n- TSK-001-01: Sample task\n",
            encoding="utf-8",
        )

        mock_agent.return_value = (
            HandoverManifest(
                phase="JUDGE",
                status="SUCCESS",
                verdict="COMPLIANCE_VIOLATION",
                task_id="TSK-001-01",
                rationale="Incomplete — missing required logic",
                train_feedback="",
            ),
            "",
        )

        task = {
            "id": "TSK-001-01",
            "issue_id": "ISS-ADH-001",
            "description": "Test tasks.md logging",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        # Console surface: TASKS_MD_FEEDBACK with line count + feedback preview
        assert "TASKS_MD_FEEDBACK" in output, (
            f"Expected TASKS_MD_FEEDBACK log line, got: {output!r}"
        )
        assert "feedback line appended" in output, (
            "Expected feedback line count in TASKS_MD_FEEDBACK output"
        )
        assert "Incomplete — missing required logic" in output, (
            f"Expected feedback preview in output, got: {output!r}"
        )

        # Structured log: TASKS_MD_FEEDBACK event captured with the full
        # feedback body and the line count.
        events = [c.args[0] for c in mock_log.call_args_list]
        assert "TASKS_MD_FEEDBACK" in events, (
            f"Expected TASKS_MD_FEEDBACK in structured log, got: {events}"
        )
        # Find the TASKS_MD_FEEDBACK call and inspect its kwargs
        tasks_md_call = next(
            c for c in mock_log.call_args_list if c.args[0] == "TASKS_MD_FEEDBACK"
        )
        assert tasks_md_call.kwargs.get("lines_added") == 1
        assert "Incomplete" in tasks_md_call.kwargs.get("feedback", "")

        # tasks.md was actually mutated
        updated = tasks_md.read_text(encoding="utf-8")
        assert "**Judge Feedback**" in updated
        assert "Incomplete" in updated

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_rejected_uses_summary_when_rationale_empty(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """JUDGE_REJECTED falls back to summary when rationale is empty.

        Regression: the auto judge template uses summary: (not
        rationale:), so the agent populates summary and the code's
        rationale lookup returned an empty string. Bridge the schema
        gap so auto-mode judge rejections surface their text.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-011-05",
            rationale="",
            train_feedback="",
        )
        # Inject the auto-mode summary field via extra-allow
        manifest.__pydantic_extra__["summary"] = (
            "Protected module modified: src/deviate/cli/micro.py"
        )
        mock_agent.return_value = (manifest, "")

        task = {
            "id": "TSK-011-05",
            "issue_id": "ISS-ADH-011",
            "description": "summary fallback test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        assert "JUDGE_REJECTED" in output, output
        assert "Protected module modified" in output, (
            f"Expected summary text in JUDGE_REJECTED output, got: {output!r}"
        )
        assert "source=summary" in output, (
            f"Expected source=summary label, got: {output!r}"
        )

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_rejected_builds_feedback_from_violations(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """JUDGE_REJECTED builds multi-line feedback from the violations list.

        Regression: when the agent returns violations: [...] with no
        rationale/train_feedback/summary, GREEN should still get
        actionable content extracted from the structured list.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-011-05",
            rationale="",
            train_feedback="",
        )
        # Inject the structured violations list — both schemas the
        # templates produce (category/file/detail vs file/requirement)
        # are supported.
        manifest.__pydantic_extra__["violations"] = [
            {
                "category": "Protected Module Modification",
                "file": "src/deviate/cli/micro.py",
                "detail": "Core orchestrator was modified; this is a",
                "severity": "CRITICAL",
                "requirement": "FR-001",
                "recommendation": "Revert and re-implement in helper module.",
            },
        ]
        mock_agent.return_value = (manifest, "")

        task = {
            "id": "TSK-011-05",
            "issue_id": "ISS-ADH-011",
            "description": "violations fallback test",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        assert "JUDGE_REJECTED" in output
        assert "Protected Module Modification" in output, (
            f"Expected violations-derived text in output, got: {output!r}"
        )
        assert "source=violations" in output, (
            f"Expected source=violations label, got: {output!r}"
        )

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_rejected_aborts_when_feedback_completely_empty(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """JUDGE_AGENT_NO_FEEDBACK aborts the run when no feedback source is populated.

        Regression: previously the code fell back to a generic message
        and reran GREEN with no actionable information, looping until
        TRAIN_EXHAUSTED. Now the run aborts loudly with a clear event
        the operator can act on.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from deviate.cli.micro import PhaseFailedError
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-011-05",
            rationale="",
            train_feedback="",
        )
        # No summary, no violations — the worst case
        mock_agent.return_value = (manifest, "")

        task = {
            "id": "TSK-011-05",
            "issue_id": "ISS-ADH-011",
            "description": "no feedback at all",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        with pytest.raises(PhaseFailedError) as exc_info:
            _run_judge_phase(task, ledger_path, session, session_path, console)

        assert "JUDGE_AGENT_NO_FEEDBACK" in str(exc_info.value), (
            f"Expected PhaseFailedError to mention JUDGE_AGENT_NO_FEEDBACK, got: {exc_info.value}"
        )

        output = buf.getvalue()
        assert "JUDGE_AGENT_NO_FEEDBACK" in output, (
            f"Expected JUDGE_AGENT_NO_FEEDBACK console event, got: {output!r}"
        )

        events = [c.args[0] for c in mock_log.call_args_list]
        assert "JUDGE_AGENT_NO_FEEDBACK" in events, (
            f"Expected JUDGE_AGENT_NO_FEEDBACK in structured log, got: {events}"
        )

    def test_format_violations_as_feedback_handles_both_schemas(
        self, tmp_path: Path
    ) -> None:
        """_format_violations_as_feedback accepts both judge schemas.

        The auto template uses category/file/detail/severity/recommendation;
        the manual skill uses file/detail/severity/requirement. The
        formatter must produce a readable bullet list for either shape.
        """
        from deviate.cli.micro import _format_violations_as_feedback

        auto_schema = [
            {
                "category": "Protected Module Modification",
                "file": "src/deviate/cli/micro.py",
                "detail": "Core orchestrator was modified",
                "severity": "CRITICAL",
                "recommendation": "Revert and re-implement in helper.",
            }
        ]
        feedback_auto = _format_violations_as_feedback(auto_schema)
        assert "Protected Module Modification" in feedback_auto
        assert "src/deviate/cli/micro.py" in feedback_auto
        assert "Core orchestrator was modified" in feedback_auto
        assert "CRITICAL" in feedback_auto
        assert "Revert and re-implement" in feedback_auto

        manual_schema = [
            {
                "file": "src/auth/jwt.py",
                "detail": "encode() returns hardcoded token",
                "severity": "HIGH",
                "requirement": "FR-01",
            }
        ]
        feedback_manual = _format_violations_as_feedback(manual_schema)
        assert "src/auth/jwt.py" in feedback_manual
        assert "encode() returns hardcoded token" in feedback_manual
        assert "HIGH" in feedback_manual
        assert "FR-01" in feedback_manual

        # Empty list returns empty string
        assert _format_violations_as_feedback([]) == ""


class TestJudgeRefactorNoteOnPass:
    """COMPLIANCE_PASS surfaces `REFACTOR NOTE:` observations as informational logs.

    Regression: prior to this change, `train_feedback` on COMPLIANCE_PASS was
    silently dropped (the orchestrator reset session.train_feedback to empty
    and never surfaced the LLM's structural observations). The new auto/judge
    prompt allows the LLM to emit informational `REFACTOR NOTE:` entries on a
    passing verdict, and the orchestrator must surface them via a structured
    `JUDGE_REFACTOR_NOTE` event so REFACTOR (or the operator) can pick them
    up. A passing verdict with no notes must not emit the event.
    """

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_pass_logs_refactor_note(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_PASS",
            task_id="TSK-013-01",
            rationale="",
            train_feedback=(
                "REFACTOR NOTE: src/deviate/cli/content.py is 240 lines; "
                "consider extracting renderers into a separate module."
            ),
        )
        mock_agent.return_value = (manifest, "")

        task = {
            "id": "TSK-013-01",
            "issue_id": "ISS-ADH-013",
            "description": "Surface refactor notes on pass",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        assert "JUDGE_REFACTOR_NOTE" in output, (
            f"Expected JUDGE_REFACTOR_NOTE console event on passing verdict, "
            f"got: {output!r}"
        )
        assert "src/deviate/cli/content.py is 240 lines" in output, (
            f"Expected refactor note text in console output, got: {output!r}"
        )

        events = [c.args[0] for c in mock_log.call_args_list]
        assert "JUDGE_REFACTOR_NOTE" in events, (
            f"Expected JUDGE_REFACTOR_NOTE in structured log, got: {events}"
        )
        note_call = next(
            c for c in mock_log.call_args_list if c.args[0] == "JUDGE_REFACTOR_NOTE"
        )
        assert "REFACTOR NOTE" in note_call.kwargs.get("note", "")

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.extract_changed_symbols", create=True)
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_pass_no_note_does_not_log_refactor_event(
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
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A passing verdict without train_feedback stays silent.

        Regression: must NOT emit `JUDGE_REFACTOR_NOTE` when the LLM did
        not surface a refactor observation. Otherwise the run log fills
        with empty events on every clean task.
        """
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState
        from deviate.cli.micro import _run_judge_phase
        from rich.console import Console

        import io

        cwd = tmp_path
        mock_cwd.return_value = cwd
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_extract.return_value = []
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        manifest = HandoverManifest(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_PASS",
            task_id="TSK-013-02",
            rationale="",
            train_feedback="",
        )
        mock_agent.return_value = (manifest, "")

        task = {
            "id": "TSK-013-02",
            "issue_id": "ISS-ADH-013",
            "description": "Clean pass — no refactor note",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        _run_judge_phase(task, ledger_path, session, session_path, console)

        output = buf.getvalue()
        assert "JUDGE_REFACTOR_NOTE" not in output, (
            f"Expected NO JUDGE_REFACTOR_NOTE on clean pass, got: {output!r}"
        )
        events = [c.args[0] for c in mock_log.call_args_list]
        assert "JUDGE_REFACTOR_NOTE" not in events, (
            f"Expected no JUDGE_REFACTOR_NOTE log event on clean pass, got: {events}"
        )

    def test_judge_prompt_marks_refactor_opinions_as_non_blocking(
        self,
        tmp_path: Path,
    ) -> None:
        """The auto/judge prompt instructs the LLM not to block on refactor concerns.

        Regression: prior to this change, the JUDGE prompt invited the LLM
        to flag refactor opportunities as blocking violations, producing
        false rejections like "split src/deviate/cli/content.py into 4
        modules". The corrected prompt must explicitly tell the LLM to
        treat refactor opinions as REFACTOR's domain.
        """
        from deviate.cli.micro import _build_auto_prompt

        # Minimal spec stub so _resolve_spec_md has something to read.
        spec_dir = tmp_path / "specs" / "adhoc" / "issues"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "013-judge-prompt.md"
        spec_file.write_text("# Stub Spec\n", encoding="utf-8")
        issues_jsonl = tmp_path / "specs" / "issues.jsonl"
        issues_jsonl.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-013",
                    "source_file": "specs/adhoc/issues/013-judge-prompt.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        task = {
            "id": "TSK-013-03",
            "issue_id": "ISS-ADH-013",
            "description": "Verify prompt mandate",
            "status": "PENDING",
            "execution_mode": "TDD",
        }

        prompt = _build_auto_prompt("judge", task, tmp_path)

        # Explicit mandate: refactoring is REFACTOR's domain
        assert "REFACTOR owns structural improvements" in prompt, (
            "Auto judge prompt must declare REFACTOR owns refactoring"
        )
        assert "Refactoring opportunities are NEVER blocking" in prompt, (
            "Auto judge prompt must forbid blocking refactor opinions"
        )
        assert "COMPLIANCE_PASS" in prompt, (
            "Auto judge prompt must declare the verdict vocabulary"
        )

        # Categories of Violations: Structural Drift and Protected Module
        # Modification were refactor-flavored and have been dropped.
        assert "Structural Drift" not in prompt, (
            "Auto judge prompt must drop 'Structural Drift' as a category"
        )

        # New dimensions aligned with correctness
        assert "Spec Compliance" in prompt, (
            "Auto judge prompt must include Spec Compliance dimension"
        )
        assert "Test Integrity" in prompt, (
            "Auto judge prompt must include Test Integrity dimension"
        )
        assert "Security & Governance" in prompt, (
            "Auto judge prompt must include Security & Governance dimension"
        )
