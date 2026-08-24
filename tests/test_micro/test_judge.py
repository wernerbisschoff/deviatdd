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


class TestJudgePost:
    """Manual ``deviate judge post`` applies auto-mode JUDGE side effects."""

    _TASK_ID = "TSK-004-01"
    _ISSUE_ID = "ISS-001-004"

    def _rev_parse(self, root: Path, rev: str = "HEAD") -> str:
        return subprocess.run(
            ["git", "rev-parse", rev],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout.strip()

    def _commit(self, root: Path, message: str) -> None:
        subprocess.run(
            ["git", "add", "."], cwd=root, env=_git_env(), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=root,
            env=_git_env(),
            check=True,
        )

    def _seed_judge_post_repo(self, root: Path) -> tuple[str, str, Path]:
        """Seed meso artifacts, RED, GREEN, session, and ledger.

        ``tasks.md`` is committed before RED so ``revert_to_red`` keeps
        the card for the feedback commit.
        """
        source = "specs/004-micro-layer/issues/001-judge-post.md"
        issue_md = root / source
        issue_md.parent.mkdir(parents=True)
        issue_md.write_text("# Judge post issue\n")
        workspace = root / "specs" / "004-micro-layer" / "001-judge-post"
        workspace.mkdir(parents=True)
        tasks_md = workspace / "tasks.md"
        tasks_md.write_text(f"- [ ] {self._TASK_ID}: Judge post task\n")
        (root / "specs" / "issues.jsonl").write_text(
            json.dumps({"issue_id": self._ISSUE_ID, "source_file": source})
            + "\n",
            encoding="utf-8",
        )
        (root / "specs" / "constitution.md").write_text("# constitution\n")
        ledger_path = workspace / "tasks.jsonl"
        _write_ledger(
            ledger_path,
            _make_task_record(
                task_id=self._TASK_ID,
                issue_id=self._ISSUE_ID,
                status="GREEN",
            ),
        )
        self._commit(root, "chore: seed meso artifacts")

        (root / "feature.py").write_text("def feature(): pass\n")
        self._commit(root, f"test({self._TASK_ID}): RED phase")
        red_sha = self._rev_parse(root)

        (root / "impl.py").write_text("def impl(): pass\n")
        self._commit(root, f"feat({self._TASK_ID}): GREEN phase")
        green_sha = self._rev_parse(root)

        session = SessionState(
            active_issue_id=self._ISSUE_ID,
            current_phase="GREEN",
            red_commit_sha=red_sha,
        )
        session.save(root / ".deviate" / "session.json")
        return red_sha, green_sha, ledger_path

    def _handover_yaml(
        self,
        *,
        verdict: str,
        next_action: str,
        rationale: str = "GREEN drifted from the spec",
        status: str = "PASS",
    ) -> str:
        return (
            "phase: JUDGE\n"
            f"status: {status}\n"
            f"task_id: {self._TASK_ID}\n"
            f'verdict: "{verdict}"\n'
            f"next_action: {next_action}\n"
            f'rationale: "{rationale}"\n'
        )

    def test_manual_overlay_names_revert_and_feedback(self) -> None:
        from importlib.resources import files

        text = (
            files("deviate.prompts.commands")
            .joinpath("deviate-judge.md")
            .read_text(encoding="utf-8")
        )
        assert "reverts GREEN" in text
        assert "tasks.md" in text
        assert "git reset" in text
        assert "validates the verdict" not in text

    def test_judge_post_is_registered_on_judge_app(self) -> None:
        result = runner.invoke(cli, ["judge", "--help"])
        assert result.exit_code == 0, result.output
        assert "post" in result.output, result.output

    def test_auto_judge_phase_does_not_shell_out_to_judge_post(self) -> None:
        import inspect

        from deviate.cli.micro import _apply_judge_verdict, _run_judge_phase

        src = inspect.getsource(_run_judge_phase)
        assert "judge_post" not in src
        assert "_apply_judge_verdict" in src
        assert callable(_apply_judge_verdict)

    def test_revert_to_red_drops_green_keeps_red_and_commits_feedback(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, _green_sha, _ledger = self._seed_judge_post_repo(tmp_git_repo)
        manifest = tmp_git_repo / "judge-handover.yaml"
        manifest.write_text(
            self._handover_yaml(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_to_red",
                rationale="missing error path",
            ),
            encoding="utf-8",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["judge", "post", str(manifest)])

        assert result.exit_code == 0, result.output
        assert "revert_to_red" in result.output, result.output
        assert (tmp_git_repo / "feature.py").exists()
        assert not (tmp_git_repo / "impl.py").exists()

        tasks_md = (
            tmp_git_repo / "specs" / "004-micro-layer" / "001-judge-post" / "tasks.md"
        )
        card = tasks_md.read_text(encoding="utf-8")
        assert "**Judge Feedback**" in card
        assert "missing error path" in card

        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
            check=True,
        ).stdout.strip()
        assert "add judge feedback" in subject, subject
        head = self._rev_parse(tmp_git_repo)
        assert head != red_sha
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.red_commit_sha == head
        assert session.current_phase == "GREEN"
        assert session.pending_judge_action == "revert_to_red"

    def test_revert_before_drops_red_and_green(self, tmp_git_repo: Path) -> None:
        red_sha, _green_sha, _ledger = self._seed_judge_post_repo(tmp_git_repo)
        yaml_text = self._handover_yaml(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_before",
            rationale="RED test asserts the wrong contract",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["judge", "post"], input=yaml_text)

        assert result.exit_code == 0, result.output
        assert "revert_before" in result.output, result.output
        assert not (tmp_git_repo / "feature.py").exists()
        assert not (tmp_git_repo / "impl.py").exists()
        head = self._rev_parse(tmp_git_repo)
        pre_red = self._rev_parse(tmp_git_repo, f"{red_sha}^")
        assert head == pre_red
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.red_commit_sha == ""
        assert session.current_phase == "RED"
        assert session.pending_judge_action == "revert_before"

    def test_forward_route_does_not_reset(self, tmp_git_repo: Path) -> None:
        _red_sha, green_sha, _ledger = self._seed_judge_post_repo(tmp_git_repo)
        yaml_text = self._handover_yaml(
            verdict="COMPLIANCE_PASS",
            next_action="continue_refactor",
            rationale="",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["judge", "post"], input=yaml_text)

        assert result.exit_code == 0, result.output
        assert "continue_refactor" in result.output, result.output
        assert (tmp_git_repo / "feature.py").exists()
        assert (tmp_git_repo / "impl.py").exists()
        assert self._rev_parse(tmp_git_repo) == green_sha
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.pending_judge_action == "continue_refactor"
        assert session.current_phase == "JUDGE"
        assert session.judge_rejected is False

    def test_test_failure_remaps_forward_route_to_train(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha, green_sha, _ledger = self._seed_judge_post_repo(tmp_git_repo)
        dump = (
            "The test suite failed after GREEN implementation.\n\n"
            "FAILED tests/test_feature.py::test_feature"
        )
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        session.train_feedback = dump
        session.failure_kind = ""
        session.red_commit_sha = red_sha
        session.save(tmp_git_repo / ".deviate" / "session.json")
        yaml_text = self._handover_yaml(
            verdict="COMPLIANCE_PASS",
            next_action="continue_refactor",
            rationale="Polish naming after the suite is green.",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["judge", "post"], input=yaml_text)

        assert result.exit_code == 0, result.output
        assert "remap_to_train" in result.output, result.output
        assert (tmp_git_repo / "impl.py").exists()
        assert self._rev_parse(tmp_git_repo) == green_sha
        session = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert session.current_phase == "GREEN"
        assert session.pending_judge_action == ""
        assert session.train_feedback.startswith(
            "The test suite failed after GREEN implementation."
        )
        assert session.judge_rejected is False

    def test_rejection_without_feedback_is_fatal(self, tmp_git_repo: Path) -> None:
        self._seed_judge_post_repo(tmp_git_repo)
        yaml_text = self._handover_yaml(
            verdict="COMPLIANCE_VIOLATION",
            next_action="revert_to_red",
            rationale="",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["judge", "post"], input=yaml_text)

        assert result.exit_code != 0, result.output
        assert "JUDGE_AGENT_NO_FEEDBACK" in result.output, result.output
        assert (tmp_git_repo / "impl.py").exists()


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

    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.Path.cwd")
    def test_judge_diff_includes_dirty_green_implementation_after_test_failure(
        self,
        mock_cwd: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        tmp_git_repo: Path,
    ) -> None:
        """JUDGE must assess uncommitted GREEN work retained after tests fail."""
        from deviate.cli.micro import _run_judge_phase
        from deviate.core.agent import HandoverManifest
        from deviate.state.config import SessionState

        mock_cwd.return_value = tmp_git_repo
        mock_build.return_value = "test prompt"
        mock_callback.return_value = None
        mock_resolve.return_value = None
        mock_done.return_value = False
        mock_agent.return_value = (
            HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS"),
            "",
        )

        red_test = tmp_git_repo / "test_feature.py"
        red_test.write_text("def test_feature():\n    assert feature() == 1\n")
        subprocess.run(["git", "add", str(red_test)], cwd=tmp_git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "test(TSK-002-05): RED phase - failing test"],
            cwd=tmp_git_repo,
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        implementation = tmp_git_repo / "feature.py"
        implementation.write_text("def feature():\n    return 1\n")

        task = {
            "id": "TSK-002-05",
            "issue_id": "ISS-002",
            "description": "Assess dirty GREEN implementation",
            "status": "GREEN",
            "execution_mode": "TDD",
        }
        session = SessionState(
            current_phase="GREEN",
            red_commit_sha=red_sha,
            train_feedback="The test suite failed after GREEN implementation.",
        )
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True)

        _run_judge_phase(
            task,
            tmp_git_repo / "tasks.jsonl",
            session,
            session_path,
            Console(),
        )

        prompt = mock_agent.call_args.args[0]
        assert "feature.py" in prompt
        assert "+def feature():" in prompt
        assert "+    return 1" in prompt

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
        """One feedback round is one bullet; return count preserves source lines."""
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
        assert (
            "**Judge Feedback**: First line of feedback\nSecond line of feedback"
            in content
        )

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

    def test_feedback_is_bounded_deduplicated_and_task_scoped(
        self, tmp_path: Path
    ) -> None:
        from deviate.cli.micro import _append_judge_feedback

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "- TSK-011-05: Sample task\n"
            "  - detail: sibling\n"
            "    nested detail line\n"
            "- TSK-011-06: Other task\n"
            "  - **Judge Feedback**: untouched\n",
            encoding="utf-8",
        )
        for feedback in ["one", "two", "three", "four", "four"]:
            _append_judge_feedback(tasks_md, "TSK-011-05", feedback)

        lines = tasks_md.read_text(encoding="utf-8").splitlines()
        assert "one" not in "\n".join(lines)
        assert "two" in "\n".join(lines)
        assert "three" in "\n".join(lines)
        assert lines.count("  - **Judge Feedback**: four") == 1
        assert "sibling" in "\n".join(lines)
        assert "nested" in "\n".join(lines)
        assert "untouched" in "\n".join(lines)

    def test_append_judge_feedback_stays_under_rejected_card_across_phase_header(
        self, tmp_path: Path
    ) -> None:
        """GH-102: feedback stays under TSK-004-01, not Phase 2 ``### Tasks``."""
        from deviate.cli.micro import _TASK_BULLET_HEAD_RE, _append_judge_feedback

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "## Phase 1: Serialize UUID payloads\n"
            "### Tasks\n"
            "- TSK-004-01: UUID serialization\n"
            "  - **Type**: Feature_Batch\n"
            "  - **Rationale**: AC-PLAN-001\n"
            "\n"
            "## Phase 2: Wire existing admin force-notify route\n"
            "### Tasks\n"
            "- TSK-004-02: Admin force-notify route mentions TSK-004-01\n"
            "  - **Type**: Feature_Batch\n",
            encoding="utf-8",
        )

        added = _append_judge_feedback(
            tasks_md,
            "TSK-004-01",
            "UUID is not JSON-serializable (AC-PLAN-001)",
        )

        assert added == 1, f"Expected one feedback line, got {added}"
        lines = tasks_md.read_text(encoding="utf-8").splitlines()
        idx_01 = next(
            i
            for i, line in enumerate(lines)
            if (head := _TASK_BULLET_HEAD_RE.match(line))
            and head.group(1) == "TSK-004-01"
        )
        idx_phase2 = next(
            i for i, line in enumerate(lines) if line.startswith("## Phase 2")
        )
        idx_phase2_tasks = next(
            i
            for i, line in enumerate(lines)
            if i > idx_phase2 and line.startswith("### Tasks")
        )
        idx_02 = next(
            i
            for i, line in enumerate(lines)
            if (head := _TASK_BULLET_HEAD_RE.match(line))
            and head.group(1) == "TSK-004-02"
        )
        fb_idxs = [i for i, line in enumerate(lines) if "**Judge Feedback**" in line]
        assert fb_idxs, f"GH-102: expected a Judge Feedback bullet; lines={lines!r}"
        assert len(fb_idxs) == 1, (
            "GH-102: exactly one Judge Feedback bullet under TSK-004-01; "
            f"lines={lines!r}"
        )
        assert idx_01 < fb_idxs[0] < idx_phase2 < idx_phase2_tasks < idx_02, (
            "GH-102: the Judge Feedback bullet must sit under TSK-004-01 "
            f"before the Phase 2 heading; lines={lines!r}"
        )
        assert not any(idx_phase2_tasks < i < idx_02 for i in fb_idxs), (
            "GH-102: feedback must not land under Phase 2 ### Tasks / TSK-004-02; "
            f"lines={lines!r}"
        )

    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
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
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
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
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
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
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
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
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
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


_GH103_CITATION = "tests/foo.py:121"
_GH103_FEEDBACK = (
    "COMPLIANCE_VIOLATION: RED test is defective. "
    f"{_GH103_CITATION} and :153 assert "
    "row.payload['data']['status'] == live['status'] where live is "
    "charge.as_dict() (ChargeStatus enum) and payload is JSONB.\n"
    "The next GREEN attempt must: not proceed. revert_before and re-run RED.\n"
    "The next RED attempt must: compare payload['data']['status'] "
    "to a JSON-safe value."
)


class TestRevertFeedbackStripsLineCitations:
    """GH-103: revert-route feedback must not persist discarded file:line cites.

    After ``revert_before`` / ``revert_to_red`` the cited RED/GREEN lines
    no longer exist. The runner strips ``path:line`` tokens before writing
    ``session.train_feedback`` or ``tasks.md``, and keeps the durable
    rewrite contract ("The next RED/GREEN attempt must: …").
    """

    def test_strip_helper_removes_file_line_keeps_behavior(self) -> None:
        from deviate.cli.micro import _strip_revert_line_citations

        result = _strip_revert_line_citations(_GH103_FEEDBACK)
        assert _GH103_CITATION not in result, (
            f"strip must drop the discarded citation {_GH103_CITATION!r}; "
            f"got {result!r}"
        )
        assert "The next RED attempt must:" in result, (
            f"strip must keep the behavioral rewrite contract; got {result!r}"
        )
        assert "JSON-safe value" in result
        assert "COMPLIANCE_VIOLATION:" in result, (
            "non-citation colons (verdict labels) must survive the strip"
        )

    @pytest.mark.parametrize("next_action", ["revert_before", "revert_to_red"])
    @patch("deviate.cli.micro._run_pytest")
    @patch("deviate.cli.micro._execute_rollback")
    @patch("deviate.cli.micro.resolve_model_for_phase")
    @patch("deviate.cli.micro._invoke_agent")
    @patch("deviate.cli.micro._build_auto_prompt")
    @patch("deviate.cli.micro._make_agent_output_callback")
    @patch("deviate.cli.micro._log_run")
    @patch("deviate.cli.micro._phase_already_done")
    @patch("deviate.cli.micro.subprocess.run")
    @patch("deviate.cli.micro.Path.cwd")
    def test_persisted_feedback_omits_discarded_file_line(
        self,
        mock_cwd: MagicMock,
        mock_subprocess: MagicMock,
        mock_done: MagicMock,
        mock_log: MagicMock,
        mock_callback: MagicMock,
        mock_build: MagicMock,
        mock_agent: MagicMock,
        mock_resolve: MagicMock,
        mock_rollback: MagicMock,
        mock_pytest: MagicMock,
        tmp_path: Path,
        next_action: str,
    ) -> None:
        """Feedback with ``tests/foo.py:121`` is stored without that citation."""
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
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

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
                rationale="",
                train_feedback=_GH103_FEEDBACK,
                next_action=next_action,
            ),
            "",
        )

        task = {
            "id": "TSK-001-01",
            "issue_id": "ISS-ADH-001",
            "description": "GH-103 strip discarded file:line citations",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        ledger_path = tmp_path / "tasks.jsonl"
        session = SessionState()
        session.red_commit_sha = "deadbeef1234567890abcdef1234567890abcdef"
        session_path = tmp_path / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        result = _run_judge_phase(task, ledger_path, session, session_path, console)

        assert _GH103_CITATION not in result.train_feedback, (
            f"{next_action}: session.train_feedback must drop "
            f"{_GH103_CITATION!r} after rollback; got {result.train_feedback!r}"
        )
        assert "The next RED attempt must:" in result.train_feedback, (
            f"{next_action}: session.train_feedback must keep the "
            f"behavioral rewrite contract; got {result.train_feedback!r}"
        )
        persisted = SessionState.load(session_path)
        assert _GH103_CITATION not in persisted.train_feedback, (
            f"{next_action}: saved session must also drop {_GH103_CITATION!r}; "
            f"got {persisted.train_feedback!r}"
        )
        if next_action == "revert_to_red":
            tasks_body = tasks_md.read_text(encoding="utf-8")
            assert _GH103_CITATION not in tasks_body, (
                f"{next_action}: tasks.md must drop {_GH103_CITATION!r}; "
                f"got {tasks_body!r}"
            )
            assert "The next RED attempt must:" in tasks_body, (
                f"{next_action}: tasks.md must keep the behavioral contract; "
                f"got {tasks_body!r}"
            )


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


class TestJudgeSecurityChecksField:
    """The JUDGE prompt must declare `security_checks` as a required manifest field.

    Pins the contract that the JUDGE verdict manifest carries a structured
    `security_checks: {pass | fail | warn}` field. The vocabulary is locked
    (`pass | fail | warn`, not `true | false`, not `ok | warn`) so future
    renames are a deliberate design decision, not prompt drift. The instruction
    tells the agent that absence of the field is a Judge rejection.
    """

    def test_judge_prompt_declares_security_checks_as_required_field(
        self,
        tmp_path: Path,
    ) -> None:
        from deviate.cli.micro import _build_auto_prompt

        spec_dir = tmp_path / "specs" / "adhoc" / "issues"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "014-judge-security-checks.md"
        spec_file.write_text("# Stub Spec\n", encoding="utf-8")
        issues_jsonl = tmp_path / "specs" / "issues.jsonl"
        issues_jsonl.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-014",
                    "source_file": "specs/adhoc/issues/014-judge-security-checks.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        task = {
            "id": "TSK-014-01",
            "issue_id": "ISS-ADH-014",
            "description": "Verify security_checks manifest field",
            "status": "PENDING",
            "execution_mode": "TDD",
        }

        prompt = _build_auto_prompt("judge", task, tmp_path)

        # The field name is present in the manifest schema.
        assert "security_checks" in prompt, (
            "Auto judge prompt must declare `security_checks` as a manifest field"
        )

        # The vocabulary is exactly `pass | fail | warn`. Pin the literal
        # delimiter-pipe form so future renames are a deliberate design
        # decision, not prompt drift.
        assert "pass | fail | warn" in prompt, (
            "Auto judge prompt must enumerate `security_checks` allowed "
            "values as `pass | fail | warn` (not `true | false`, "
            "not `ok | warn`, not `green | red`)"
        )

        # The field is mandatory — absence on the manifest is a rejection.
        assert (
            ("security_checks" in prompt and "mandatory" in prompt.lower())
            or "security_checks" in prompt
            and "required" in prompt.lower()
        ), (
            "Auto judge prompt must instruct the agent that `security_checks` "
            "is mandatory on the manifest; absence is a Judge rejection"
        )


class TestJudgeOwaspNistSection:
    """The JUDGE prompt must evaluate the diff against OWASP Top 10 and NIST
    SSDF categories."""

    def _build_prompt(self, tmp_path: Path) -> str:
        from deviate.cli.micro import _build_auto_prompt

        spec_dir = tmp_path / "specs" / "adhoc" / "issues"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "015-judge-owasp-nist.md"
        spec_file.write_text("# Stub Spec\n", encoding="utf-8")
        issues_jsonl = tmp_path / "specs" / "issues.jsonl"
        issues_jsonl.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-015",
                    "source_file": "specs/adhoc/issues/015-judge-owasp-nist.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        task = {
            "id": "TSK-015-01",
            "issue_id": "ISS-ADH-015",
            "description": "Verify OWASP/NIST security section",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        return _build_auto_prompt("judge", task, tmp_path)

    def test_judge_prompt_names_owasp_top_ten(self, tmp_path: Path) -> None:
        """The prompt must reference OWASP Top 10 as a security taxonomy."""
        prompt = self._build_prompt(tmp_path)
        assert "OWASP" in prompt, (
            "Auto judge prompt must reference the OWASP Top 10 taxonomy"
        )
        assert "Top 10" in prompt, (
            "Auto judge prompt must name OWASP's Top 10 vulnerability list"
        )

    def test_judge_prompt_names_nist_ssdf(self, tmp_path: Path) -> None:
        """The prompt must reference the NIST Secure Software Development
        Framework (SSDF) as a security baseline."""
        prompt = self._build_prompt(tmp_path)
        assert "NIST" in prompt, (
            "Auto judge prompt must reference NIST as a security baseline"
        )
        assert "SSDF" in prompt, "Auto judge prompt must name the NIST SSDF framework"

    def test_judge_prompt_maps_flat_scan_to_framework(self, tmp_path: Path) -> None:
        """The existing flat security categories must map to framework names.

        The OWASP/NIST section must not discard the concrete flat categories
        (secrets, injection, deserialization, path traversal, log leakage)."""
        prompt = self._build_prompt(tmp_path)
        assert "secrets" in prompt.lower()
        assert "injection" in prompt.lower()
        assert "path traversal" in prompt.lower()
        assert "log leakage" in prompt.lower()

    def test_judge_prompt_names_owasp_llm_top_ten(self, tmp_path: Path) -> None:
        """The prompt must add the OWASP Top 10 for LLM Applications (LLM01-LLM10).

        deviatdd produces LLM-agent-shaped products, so prompt injection and the
        other agentic risk classes must be a named, auditable lens alongside the
        web Top 10."""
        prompt = self._build_prompt(tmp_path)
        assert "LLM01" in prompt, (
            "Auto judge prompt must name LLM01 in the LLM Applications lens"
        )
        assert "LLM10" in prompt, (
            "Auto judge prompt must name LLM10 in the LLM Applications lens"
        )
        assert "LLM Applications" in prompt, (
            "Auto judge prompt must name the OWASP LLM Applications taxonomy"
        )

    def test_judge_prompt_language_agnostic_domain_catalogue(
        self, tmp_path: Path
    ) -> None:
        """The domain-catalogue directive must be language-agnostic.

        It must name generic forbidden patterns (native serialization, SQL
        interpolation, unsafe self-referential deserialization) without tying to a
        specific stack or toolchain. No Elixir/Phoenix tools (Sobelow, Credo, mix
        audit, binary_to_term) and no Python tools (Bandit, pip-audit) are named."""
        prompt = self._build_prompt(tmp_path)
        # Language-agnostic forbidden-pattern framing is present.
        assert (
            "forbidden pattern" in prompt.lower()
            or "domain catalogue" in prompt.lower()
        ), "Auto judge prompt must include a language-agnostic domain catalogue"
        # The catalogue must not name stack-specific tools.
        for tool in ["Sobelow", "Credo", "mix audit", "Bandit", "binary_to_term"]:
            assert tool.lower() not in prompt.lower(), (
                f"Domain catalogue must be language-agnostic; it must not name "
                f"stack-specific tool {tool!r}"
            )


class TestExecuteRollbackUntrackedCleanup:
    """``_execute_rollback()`` must remove untracked files and directories.

    Regression: prior to this change, ``_execute_rollback()`` ran
    ``git checkout .deviate/`` + ``git reset --hard <red_sha>`` but never
    touched untracked artifacts. When a failed GREEN attempt left behind
    scratch files (``*.pyc``, build outputs, helper scripts), those files
    persisted into the next RED attempt and could be picked up by pytest
    collection, produce false positives, or interfere with the test writer
    agent's edits.

    The fix: after the ``git reset --hard``, run ``git clean -fd`` (force
    + directories, **without** ``-x`` so gitignored state like
    ``.deviate/``, ``.mise/``, ``__pycache__/`` is preserved).
    """

    def _setup_repo_with_red_boundary(
        self,
        tmp_git_repo: Path,
        *,
        with_green_commit: bool = False,
    ) -> tuple[str, str]:
        """Build a RED boundary SHA in ``tmp_git_repo`` and return (red_sha, green_sha_or_empty).

        Creates a tracked ``red.py`` file and commits it as the RED
        boundary. Optionally adds a second commit (``green.py``) so the
        rollback has history to discard. Writes ``.deviate/session.json``
        with ``red_commit_sha`` so production rollback tests can pin the
        boundary that the JUDGE/EXECUTE runners should thread into
        ``_execute_rollback`` (the runner no longer falls back to
        ``HEAD~1`` when ``boundary_sha`` is missing). In production
        ``.deviate/`` is gitignored, so ``git clean -fd`` (without ``-x``)
        preserves the audit trail. The fixture mirrors that by writing a
        ``.gitignore`` ignoring ``.deviate/`` *before* the RED boundary
        commit, so the safety invariant is exercised.
        """
        # Mirror the project `.gitignore`: `.deviate/` is gitignored so
        # `git clean -fd` (without `-x`) skips it. This must be committed
        # to take effect, so it's the very first tracked content.
        (tmp_git_repo / ".gitignore").write_text(".deviate/\n")
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: initial .gitignore"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        red_file = tmp_git_repo / "red.py"
        red_file.write_text("# RED: failing test\n")
        subprocess.run(
            ["git", "add", "red.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "RED: add failing test"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        red_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        green_sha = ""
        if with_green_commit:
            green_file = tmp_git_repo / "green.py"
            green_file.write_text("# GREEN: implementation\n")
            subprocess.run(
                ["git", "add", "green.py"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "GREEN: implementation"],
                cwd=tmp_git_repo,
                env=_git_env(),
                check=True,
            )
            green_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_git_repo,
                env=_git_env(),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

        # Persist session.json so the JUDGE/EXECUTE runners can observe the
        # boundary they should thread into ``_execute_rollback``. The runner
        # itself no longer reads ``session.red_commit_sha`` to discover the
        # boundary (it must be passed explicitly), but the audit trail and
        # downstream code paths still rely on the field being set.
        deviate_dir = tmp_git_repo / ".deviate"
        deviate_dir.mkdir(parents=True, exist_ok=True)
        session_payload = {
            "current_phase": "JUDGE",
            "active_issue_id": None,
            "last_command": "",
            "train_feedback": "",
            "judge_rejected": False,
            "red_commit_sha": red_sha,
            "timestamp": "2026-07-13T00:00:00Z",
        }
        (deviate_dir / "session.json").write_text(
            json.dumps(session_payload), encoding="utf-8"
        )

        return red_sha, green_sha

    def test_rollback_removes_untracked_files(self, tmp_git_repo: Path) -> None:
        """Untracked files left by a failed GREEN are wiped on rollback.

        Scenario: RED committed ``red.py``. GREEN committed ``green.py`` and
        also left behind an untracked ``scratch.py`` (simulating a build
        artifact or scratch file the agent created). After rollback:
        ``scratch.py`` must NOT exist, ``green.py`` must be gone (reset to
        red_sha), and ``red.py`` must still be present.

        ``_execute_rollback`` requires keyword-only ``boundary_sha``,
        ``task_id``, and ``attempt``; the runner no longer infers the
        boundary from session state.
        """
        from deviate.cli.micro import _execute_rollback

        red_sha, _green_sha = self._setup_repo_with_red_boundary(
            tmp_git_repo, with_green_commit=True
        )

        # GREEN leaves behind an untracked artifact
        scratch = tmp_git_repo / "scratch.py"
        scratch.write_text("# scratch\n")
        assert scratch.exists(), "Pre-condition: scratch.py must exist before rollback"

        # Pre-condition: HEAD is ahead of red_sha
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head_before != red_sha, (
            "Pre-condition: HEAD must differ from red_sha so reset is meaningful"
        )

        red_sha_returned = _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_sha,
            reason="violation: stray file",
            phase="JUDGE",
            task_id="TSK-EXEC-001",
            attempt=0,
        )

        assert red_sha_returned == red_sha

        # Untracked artifact must be gone
        assert not scratch.exists(), (
            f"_execute_rollback must remove untracked files (scratch.py still exists at {scratch})"
        )

        # Tracked history must be reset to red_sha
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head_after == red_sha, (
            f"_execute_rollback must reset HEAD to red_sha; got {head_after}"
        )

        # RED file must still be present (preserved by the reset)
        assert (tmp_git_repo / "red.py").exists(), (
            "_execute_rollback must preserve the RED boundary's tracked files"
        )
        # GREEN file must be gone (reset discards tracked commits)
        assert not (tmp_git_repo / "green.py").exists(), (
            "_execute_rollback must discard tracked commits made during GREEN"
        )

    def test_rollback_removes_untracked_directories(self, tmp_git_repo: Path) -> None:
        """Untracked DIRECTORIES (with contents) are wiped by ``git clean -fd``.

        The ``-d`` flag is what enables this — without it, ``git clean -f``
        would skip directories and leave their contents behind.
        """
        from deviate.cli.micro import _execute_rollback

        red_sha, _green_sha = self._setup_repo_with_red_boundary(
            tmp_git_repo, with_green_commit=True
        )

        # GREEN leaves behind an untracked artifact directory
        scratch_dir = tmp_git_repo / "scratch_dir"
        scratch_dir.mkdir()
        (scratch_dir / "inner.py").write_text("# inner\n")
        assert (scratch_dir / "inner.py").exists(), (
            "Pre-condition: scratch_dir/inner.py must exist before rollback"
        )

        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_sha,
            reason="violation: stray directory",
            phase="JUDGE",
            task_id="TSK-EXEC-002",
            attempt=0,
        )

        assert not scratch_dir.exists(), (
            f"_execute_rollback must remove untracked directories (scratch_dir still exists at {scratch_dir})"
        )
        assert not (scratch_dir / "inner.py").exists(), (
            "Contents of untracked directories must be removed"
        )

        # Tracked history must still be reset to red_sha
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head_after == red_sha

    def test_rollback_preserves_gitignored_dotdeviate(self, tmp_git_repo: Path) -> None:
        """``git clean -fd`` (without ``-x``) must preserve gitignored state.

        ``.deviate/`` is gitignored (per the project ``.gitignore``). The
        rollback calls ``append_rollback_snapshot`` which writes to
        ``.deviate/rollback.jsonl``. After rollback:
          * ``.deviate/`` directory must still exist (we wrote to it).
          * ``.deviate/session.json`` (the file we authored) must still
            exist — it's gitignored, NOT a tracked file, so the
            ``git checkout .deviate/`` step is a no-op for it and the
            ``git clean -fd`` step (no ``-x``) must skip it.
          * ``.deviate/rollback.jsonl`` (created by the rollback itself)
            must still exist for the audit trail to be intact.
        """
        from deviate.cli.micro import _execute_rollback

        red_sha, _green_sha = self._setup_repo_with_red_boundary(
            tmp_git_repo, with_green_commit=False
        )

        # Sanity: setup wrote .deviate/session.json (gitignored)
        deviate_dir = tmp_git_repo / ".deviate"
        assert (deviate_dir / "session.json").exists()

        _execute_rollback(
            tmp_git_repo,
            boundary_sha=red_sha,
            reason="violation: audit-trail safety",
            phase="JUDGE",
            task_id="TSK-EXEC-003",
            attempt=0,
        )

        # The gitignored .deviate/ directory must survive — `git clean -fd`
        # without `-x` does not touch gitignored paths.
        assert deviate_dir.exists(), (
            ".deviate/ must survive rollback (gitignored, `git clean -fd` without `-x` skips it)"
        )
        assert (deviate_dir / "session.json").exists(), (
            ".deviate/session.json must survive rollback"
        )
        # The rollback ledger entry itself must persist
        assert (deviate_dir / "rollback.jsonl").exists(), (
            ".deviate/rollback.jsonl (audit trail) must persist across rollback"
        )


# ---------------------------------------------------------------------------
# TSK-020-03 / TSK-028-02: TDD `_run_judge_phase` mechanical evidence gate.
# TSK-028-02: required tokens come from the task card / criteria, not the
# full plan set (AC-PLAN-001, AC-PLAN-003, AC-PLAN-004). Constitution §3:
# pytest under tests/; git isolation via tmp_git_repo + _git_env(); mock
# _invoke_agent and _run_pytest. Flow References: [].
# ---------------------------------------------------------------------------

_GATE_ISSUE_ID = "ISS-ADH-020"
_GATE_TASK_ID = "TSK-020-03"
_GATE_SLUG = "020-judge-compliance-pass-evidence"
_GATE_TEST_PATH = "tests/example.py"
_GATE_IMPL_PATH = "src/example.py"
_GATE_TEST_QUOTE = "assert increment(2) == 3"
_GATE_IMPL_QUOTE = "return n + 1"
_GATE_TEST_BODY = "def test_increment() -> None:\n    assert increment(2) == 3\n"
_GATE_IMPL_BODY = "def increment(n: int) -> int:\n    return n + 1\n"
_GATE_SHORT_TEST_BODY = (
    "def test_placeholder() -> None:\n"
    "    assert True  # increment contract placeholder\n"
)


def _gate_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def _gate_commit(repo: Path, message: str, *relpaths: str) -> str:
    _gate_git(repo, "add", "--", *relpaths)
    _gate_git(repo, "commit", "-m", message)
    return _gate_git(repo, "rev-parse", "HEAD").stdout.strip()


def _seed_gate_issue(
    repo: Path,
    *acs: str,
    card_acs: tuple[str, ...] | None = None,
) -> None:
    issues_dir = repo / "specs" / "adhoc" / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    (issues_dir / f"{_GATE_SLUG}.md").write_text(
        "# TDD JUDGE evidence gate\n",
        encoding="utf-8",
    )
    (repo / "specs").mkdir(parents=True, exist_ok=True)
    (repo / "specs" / "issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": _GATE_ISSUE_ID,
                "source_file": f"specs/adhoc/issues/{_GATE_SLUG}.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    plan_dir = repo / "specs" / "adhoc" / _GATE_SLUG
    plan_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"**Scenario {ac}: example**" for ac in acs)
    if not body:
        body = "No AC-PLAN tokens in this contract.\n"
    (plan_dir / "plan.md").write_text(body + "\n", encoding="utf-8")
    # Default: this task owns the first plan token only so later-shard ACs
    # stay unclaimed at JUDGE (TSK-028-02 / AC-PLAN-001). Empty plan → no
    # card tokens (infra / enabling).
    owned = card_acs if card_acs is not None else ((acs[0],) if acs else ())
    card = f"# Tasks\n\n- {_GATE_TASK_ID}: Rewrite unmatched TDD PASS\n"
    if owned:
        named = ", ".join(owned)
        card += (
            f"  - **Acceptance Criteria**: {named}\n"
            f"  - **Rationale**: this task owns {named}\n"
        )
    (plan_dir / "tasks.md").write_text(card, encoding="utf-8")


def _write_gate_file(repo: Path, relpath: str, body: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _seed_red_green(
    repo: Path,
    *,
    acs: tuple[str, ...] = ("AC-PLAN-001",),
    card_acs: tuple[str, ...] | None = None,
    test_body: str = _GATE_TEST_BODY,
    impl_body: str | None = _GATE_IMPL_BODY,
    commit_test: bool = True,
    commit_impl: bool = True,
) -> str:
    """Seed specs + optional RED/GREEN commits. Returns red_commit_sha."""
    (repo / ".gitignore").write_text(".deviate/\n", encoding="utf-8")
    _seed_gate_issue(repo, *acs, card_acs=card_acs)
    _gate_commit(
        repo,
        "chore: seed issue and plan",
        ".gitignore",
        "specs",
    )
    if test_body:
        _write_gate_file(repo, _GATE_TEST_PATH, test_body)
        if commit_test:
            red_sha = _gate_commit(
                repo,
                f"test({_GATE_TASK_ID}): RED phase - failing test",
                _GATE_TEST_PATH,
            )
        else:
            red_sha = _gate_git(repo, "rev-parse", "HEAD").stdout.strip()
    else:
        red_sha = _gate_git(repo, "rev-parse", "HEAD").stdout.strip()
    if impl_body:
        _write_gate_file(repo, _GATE_IMPL_PATH, impl_body)
        if commit_impl:
            _gate_commit(
                repo,
                f"feat({_GATE_TASK_ID}): GREEN phase - implementation",
                _GATE_IMPL_PATH,
            )
    return red_sha


def _gate_evidence(**overrides: str) -> dict[str, str]:
    item = {
        "ac": "AC-PLAN-001",
        "test_path": _GATE_TEST_PATH,
        "test_quote": _GATE_TEST_QUOTE,
        "impl_path": _GATE_IMPL_PATH,
        "impl_quote": _GATE_IMPL_QUOTE,
    }
    item.update(overrides)
    return item


def _gate_manifest(
    *,
    next_action: str | None = "skip_refactor",
    evidence: list[dict[str, str]] | None = None,
    verdict: str = "COMPLIANCE_PASS",
    phase: str = "JUDGE",
    status: str = "PASS",
    files: list[str] | None = None,
    test_file: str | None = None,
    train_feedback: str = "",
    violations: list[dict[str, str]] | None = None,
) -> HandoverManifest:
    kwargs: dict = {
        "phase": phase,
        "status": status,
        "task_id": _GATE_TASK_ID,
        "verdict": verdict,
        "rationale": "",
        "train_feedback": train_feedback,
    }
    if next_action is not None:
        kwargs["next_action"] = next_action
    if evidence is not None:
        kwargs["evidence"] = evidence
    if files is not None:
        kwargs["files"] = files
    if test_file is not None:
        kwargs["test_file"] = test_file
    if violations is not None:
        kwargs["violations"] = violations
    return HandoverManifest(**kwargs)


def _run_tdd_judge(
    repo: Path,
    manifest: HandoverManifest,
    red_sha: str,
) -> tuple[SessionState, str, Path]:
    from deviate.cli.micro import _run_judge_phase
    from deviate.state.config import SessionState
    import io

    task = {
        "id": _GATE_TASK_ID,
        "issue_id": _GATE_ISSUE_ID,
        "description": "Rewrite unmatched TDD PASS to revert_to_red",
        "status": "GREEN",
        "execution_mode": "TDD",
    }
    ledger_path = repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.jsonl"
    session = SessionState(
        current_phase="GREEN",
        red_commit_sha=red_sha,
        active_issue_id=_GATE_ISSUE_ID,
    )
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    mock_pytest = patch(
        "deviate.cli.micro._run_pytest",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        ),
    )
    with (
        chdir(repo),
        patch(
            "deviate.cli.micro._invoke_agent",
            return_value=(manifest, ""),
        ),
        patch(
            "deviate.cli.micro._build_auto_prompt",
            return_value="test prompt",
        ),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        mock_pytest,
    ):
        session_out = _run_judge_phase(
            task, ledger_path, session, session_path, console
        )
    return session_out, buf.getvalue(), ledger_path


def _ledger_statuses(ledger_path: Path) -> list[str]:
    if not ledger_path.exists():
        return []
    statuses: list[str] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        statuses.append(json.loads(line).get("status", ""))
    return statuses


def _assert_reverted_to_red(session: SessionState, ledger_path: Path) -> None:
    assert session.pending_judge_action == "revert_to_red", (
        f"Expected revert_to_red, got {session.pending_judge_action!r}"
    )
    assert session.judge_rejected is True
    assert session.train_feedback.strip() != "", (
        "Runner-authored evidence feedback must train GREEN"
    )
    statuses = _ledger_statuses(ledger_path)
    assert "COMPLETED" not in statuses, (
        f"Unmatched PASS must not COMPLETE, statuses={statuses!r}"
    )


def _assert_forward(
    session: SessionState,
    ledger_path: Path,
    *,
    action: str,
    completed: bool,
) -> None:
    assert session.pending_judge_action == action, (
        f"Expected forward action {action!r}, got {session.pending_judge_action!r}"
    )
    assert session.judge_rejected is False
    statuses = _ledger_statuses(ledger_path)
    if completed:
        assert "COMPLETED" in statuses, (
            f"Expected COMPLETED ledger row, statuses={statuses!r}"
        )
    else:
        assert "COMPLETED" not in statuses, (
            f"Forward route must not COMPLETE yet, statuses={statuses!r}"
        )


def _seed_already_exists(repo: Path, *, include_test: bool = True) -> str:
    """Commit test/impl, then an unrelated HEAD so quotes live only at HEAD."""
    (repo / ".gitignore").write_text(".deviate/\n", encoding="utf-8")
    _seed_gate_issue(repo, "AC-PLAN-001")
    paths = [".gitignore", "specs", _GATE_IMPL_PATH]
    _write_gate_file(repo, _GATE_IMPL_PATH, _GATE_IMPL_BODY)
    if include_test:
        _write_gate_file(repo, _GATE_TEST_PATH, _GATE_TEST_BODY)
        paths.append(_GATE_TEST_PATH)
    _gate_commit(repo, "chore: already-exists baseline", *paths)
    note = repo / "docs" / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("unrelated HEAD commit\n", encoding="utf-8")
    return _gate_commit(repo, "docs: unrelated HEAD commit", "docs/note.txt")


def _assert_already_satisfied_not_completed(
    session: SessionState,
    ledger_path: Path,
) -> None:
    """AC-PLAN-005: unmatched already-exists PASS cannot COMPLETE."""
    action = session.pending_judge_action
    assert action in {"revert_before", "revert_to_red"}, (
        f"Expected revert_before or revert_to_red, got {action!r}"
    )
    assert session.train_feedback.strip() != "", (
        "Runner-authored feedback must name the missing declared test path"
    )
    statuses = _ledger_statuses(ledger_path)
    assert "COMPLETED" not in statuses, (
        f"Declared files absent from snapshot must not COMPLETE, "
        f"statuses={statuses!r} feedback={session.train_feedback!r}"
    )


def _run_already_satisfied_cycle(
    repo: Path,
    *,
    red_files: list[str] | None,
    red_test_file: str | None = None,
    write_on_red: dict[str, str] | None = None,
    tasks_mention: str | None = None,
    rationale: str = "Required behavior already exists.",
) -> tuple[list[str], list[str], str, Path]:
    """Drive RED already_satisfied + JUDGE skip_refactor through _run_tdd_cycle."""
    import io

    from deviate.cli.micro import PhaseFailedError, _run_tdd_cycle

    task_id = "TSK-022-02"
    issue_id = "ISS-ADH-022"
    slug = "022-already-satisfied-red-requires-tests"
    call_log: list[str] = []
    passing = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )
    (repo / ".gitignore").write_text(".deviate/\n", encoding="utf-8")
    specs = repo / "specs" / "adhoc" / slug
    specs.mkdir(parents=True, exist_ok=True)
    tasks_md = specs / "tasks.md"
    mention = tasks_mention or ""
    tasks_md.write_text(
        f"# Tasks\n\n- {task_id}: Require declared tests\n{mention}\n",
        encoding="utf-8",
    )
    (repo / "specs" / "issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": issue_id,
                "source_file": f"specs/adhoc/issues/{slug}.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    issue_dir = repo / "specs" / "adhoc" / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    (issue_dir / f"{slug}.md").write_text(
        "# already_satisfied requires declared tests\n",
        encoding="utf-8",
    )
    (specs / "plan.md").write_text(
        "No AC-PLAN tokens in this contract.\n",
        encoding="utf-8",
    )
    _gate_commit(repo, "chore: seed ISS-ADH-022 fixtures", ".gitignore", "specs")

    def _invoke(*args: object, **kwargs: object):
        phase = str(kwargs.get("phase", ""))
        tid = str(kwargs.get("task_id", task_id))
        call_log.append(phase)
        if len(call_log) > 24:
            raise AssertionError(
                f"TDD loop did not terminate after 24 agent invokes: {call_log!r}"
            )
        if phase == "RED":
            for rel, body in (write_on_red or {}).items():
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            return (
                HandoverManifest(
                    phase="RED",
                    status="SUCCESS",
                    task_id=tid,
                    failure_kind="already_satisfied",
                    files=red_files,
                    test_file=red_test_file,
                    rationale=rationale,
                ),
                "",
            )
        if phase == "JUDGE":
            return (
                HandoverManifest.model_construct(
                    phase="JUDGE",
                    status="SUCCESS",
                    verdict="COMPLIANCE_PASS",
                    task_id=tid,
                    next_action="skip_refactor",
                    summary=(
                        "The required behavior already exists; "
                        "no implementation needed."
                    ),
                ),
                "",
            )
        return (
            HandoverManifest(phase=phase, status="SUCCESS", task_id=tid),
            "",
        )

    task = {
        "id": task_id,
        "issue_id": issue_id,
        "description": "Require declared tests in the JUDGE snapshot",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    ledger_path = specs / "tasks.jsonl"
    _write_ledger(
        ledger_path,
        _make_task_record(
            task_id=task_id,
            issue_id=issue_id,
            description=task["description"],
            status="PENDING",
            execution_mode="TDD",
        ),
    )
    session_path = repo / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id=issue_id).save(session_path)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    with (
        chdir(repo),
        patch("deviate.cli.micro._invoke_agent", side_effect=_invoke),
        patch("deviate.cli.micro._build_auto_prompt", return_value="test prompt"),
        patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
        patch("deviate.cli.micro._verify_worktree_branch"),
        patch("deviate.cli.micro._verify_clean_worktree"),
        patch("deviate.cli.micro._run_format_cmd", return_value=passing),
        patch("deviate.cli.micro._run_test_cmd", return_value=passing),
        patch("deviate.cli.micro._run_pytest", return_value=passing),
    ):
        try:
            _run_tdd_cycle(task, ledger_path, console)
        except PhaseFailedError:
            pass
    return _ledger_statuses(ledger_path), call_log, buf.getvalue(), ledger_path


def _append_docs_feedback_commits(repo: Path, count: int = 2) -> str:
    """Stack ``docs(...): add judge feedback for retry`` commits on HEAD."""
    tasks_rel = f"specs/adhoc/{_GATE_SLUG}/tasks.md"
    tasks_md = repo / tasks_rel
    sha = ""
    for index in range(count):
        tasks_md.write_text(
            tasks_md.read_text(encoding="utf-8")
            + f"  - **Judge Feedback**: retry {index + 1}\n",
            encoding="utf-8",
        )
        sha = _gate_commit(
            repo,
            f"docs({_GATE_TASK_ID}): add judge feedback for retry",
            tasks_rel,
        )
    return sha


def _seed_train_feedback_on_red(
    repo: Path, *, feedback_count: int = 2, recommit_green: bool = True
) -> tuple[str, str]:
    """TRAIN topology: discard GREEN, stack docs-feedback on RED, retry GREEN."""
    red_sha = _seed_red_green(repo)
    _gate_git(repo, "reset", "--hard", red_sha)
    fb_sha = _append_docs_feedback_commits(repo, count=feedback_count)
    if recommit_green:
        _write_gate_file(repo, _GATE_IMPL_PATH, _GATE_IMPL_BODY)
        _gate_commit(
            repo,
            f"feat({_GATE_TASK_ID}): GREEN phase - implementation",
            _GATE_IMPL_PATH,
        )
    return red_sha, fb_sha


class TestJudgeDiffBaseWalksPastFeedback:
    """GH-88 / GH-90: docs-feedback ``red_commit_sha`` must not hide the RED test.

    ``_maybe_advance_red_sha_past_feedback`` keeps the feedback commit as the
    GREEN-entry / ``revert_to_red`` boundary. The injected JUDGE diff must
    still start at the real RED-phase failing-test commit.
    """

    def test_injected_diff_keeps_red_test_when_red_sha_is_feedback(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _assemble_judge_injected_diff

        red_sha, fb_sha = _seed_train_feedback_on_red(tmp_git_repo)
        assert fb_sha != red_sha

        raw_feedback_range = _gate_git(tmp_git_repo, "diff", f"{fb_sha}^..HEAD").stdout
        assert _GATE_TEST_PATH not in raw_feedback_range, (
            "Precondition: docs-feedback^..HEAD must omit the RED test file"
        )

        injected = _assemble_judge_injected_diff(
            tmp_git_repo,
            red_commit_sha=fb_sha,
            red_baseline=None,
        )
        assert _GATE_TEST_PATH in injected, (
            "GH-88/GH-90: injected JUDGE diff must still include the RED "
            f"test file {_GATE_TEST_PATH} when session.red_commit_sha is "
            "a docs-feedback commit"
        )
        assert _GATE_IMPL_PATH in injected, (
            "injected JUDGE diff must still include the GREEN implementation"
        )

    def test_evidence_gate_does_not_false_reject_feedback_red_sha(
        self, tmp_git_repo: Path
    ) -> None:
        _, fb_sha = _seed_train_feedback_on_red(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="continue_refactor",
                evidence=[_gate_evidence()],
            ),
            fb_sha,
        )
        assert "test_path is not in the injected diff" not in session.train_feedback, (
            "GH-88/GH-90: evidence gate must not false-reject because the "
            f"RED test dropped out of a docs-only range; "
            f"feedback={session.train_feedback!r}"
        )
        assert "missing, empty, or partial" not in session.train_feedback, (
            "GH-88/GH-90: evidence gate must not report missing AC tokens "
            f"solely because the RED test is absent from a docs-only range; "
            f"feedback={session.train_feedback!r}"
        )
        _assert_forward(
            session,
            ledger,
            action="continue_refactor",
            completed=False,
        )

    def test_green_entry_and_advance_keep_feedback_boundary(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import (
            _maybe_advance_red_sha_past_feedback,
            _require_green_entry_red_sha,
        )

        red_sha, fb_sha = _seed_train_feedback_on_red(
            tmp_git_repo, feedback_count=1, recommit_green=False
        )
        session = SessionState(current_phase="GREEN", red_commit_sha=red_sha)
        _maybe_advance_red_sha_past_feedback(session, tmp_git_repo, red_sha, fb_sha)
        assert session.red_commit_sha == fb_sha, (
            "rollback / TRAIN must still advance red_commit_sha onto the "
            "docs-feedback commit"
        )
        _require_green_entry_red_sha(tmp_git_repo, session, _GATE_TASK_ID)


class TestTddJudgeEvidenceGate:
    """TSK-020-03 / TSK-028-02: TDD gate is task-scoped (AC-PLAN-001..004).

    Constitution §3 Testing Protocols. Flow References: [].
    """

    def test_missing_evidence_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=None),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_empty_evidence_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=[]),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_rewritten_pass_keeps_judge_train_feedback(
        self, tmp_git_repo: Path
    ) -> None:
        """GH-102: evidence-gate rewrite must not replace judge train_feedback."""
        red_sha = _seed_red_green(tmp_git_repo)
        judge_fb = (
            "UUID is not JSON-serializable for AC-PLAN-001. "
            f"See {_GATE_TEST_PATH}:12. "
            "The next GREEN attempt must: dump UUID as str."
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="continue_refactor",
                evidence=[],
                train_feedback=judge_fb,
            ),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)
        assert "UUID is not JSON-serializable" in session.train_feedback, (
            "GH-102: persist the judge train_feedback after the evidence-gate "
            f"rewrite; got {session.train_feedback!r}"
        )
        assert f"{_GATE_TEST_PATH}:12" not in session.train_feedback, (
            "GH-102: GH-103 citation strip still applies on the revert route; "
            f"got {session.train_feedback!r}"
        )
        assert "JUDGE evidence is missing" not in session.train_feedback, (
            "GH-102: generic evidence-gate string must not replace judge "
            f"train_feedback; got {session.train_feedback!r}"
        )
        tasks_md = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.md"
        body = tasks_md.read_text(encoding="utf-8")
        assert "UUID is not JSON-serializable" in body, (
            f"GH-102: tasks.md must keep judge train_feedback; got {body!r}"
        )
        assert "JUDGE evidence is missing" not in body, (
            f"GH-102: tasks.md must not persist the generic gate string; got {body!r}"
        )

    def test_rewritten_pass_keeps_judge_violations(self, tmp_git_repo: Path) -> None:
        """GH-102: evidence-gate rewrite must persist judge violations."""
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="continue_refactor",
                evidence=[],
                violations=[
                    {
                        "category": "Acceptance",
                        "detail": "UUID is not JSON-serializable (AC-PLAN-001)",
                        "severity": "HIGH",
                        "file": _GATE_IMPL_PATH,
                    }
                ],
            ),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)
        assert (
            "UUID is not JSON-serializable (AC-PLAN-001)" in session.train_feedback
        ), (
            "GH-102: persist formatted judge violations after the evidence-gate "
            f"rewrite; got {session.train_feedback!r}"
        )
        assert "JUDGE evidence is missing" not in session.train_feedback, (
            "GH-102: generic evidence-gate string must not replace judge "
            f"violations; got {session.train_feedback!r}"
        )
        tasks_md = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.md"
        body = tasks_md.read_text(encoding="utf-8")
        assert "UUID is not JSON-serializable (AC-PLAN-001)" in body, (
            f"GH-102: tasks.md must keep judge violations; got {body!r}"
        )
        assert "JUDGE evidence is missing" not in body, (
            f"GH-102: tasks.md must not persist the generic gate string; got {body!r}"
        )

    def test_mid_plan_this_task_evidence_completes(self, tmp_git_repo: Path) -> None:
        """AC-PLAN-001 / AC-PLAN-004: omitting later-shard AC-PLAN-002 is legal.

        Plan lists AC-PLAN-001 and AC-PLAN-002. The synthesized PENDING dict
        omits acceptance_criteria. The tasks.md card names only AC-PLAN-001.
        Matching this-task quotes COMPLETE. Constitution §3. Flow References: [].
        """
        red_sha = _seed_red_green(
            tmp_git_repo,
            acs=("AC-PLAN-001", "AC-PLAN-002"),
            card_acs=("AC-PLAN-001",),
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="skip_refactor",
            completed=True,
        )

    def test_missing_this_task_token_does_not_complete_mid_plan(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-003: ISS-ADH-020 stays fail-closed on this-task tokens."""
        red_sha = _seed_red_green(
            tmp_git_repo,
            acs=("AC-PLAN-001", "AC-PLAN-002"),
            card_acs=("AC-PLAN-001",),
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=[]),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_hallucinated_path_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                evidence=[_gate_evidence(test_path="tests/hallucinated.py")],
            ),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_empty_quote_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=[_gate_evidence(test_quote="")]),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_short_quote_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(
            tmp_git_repo,
            test_body=_GATE_SHORT_TEST_BODY,
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=[_gate_evidence(test_quote="assert True")]),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_wrong_file_quote_does_not_complete(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                evidence=[_gate_evidence(test_quote=_GATE_IMPL_QUOTE)],
            ),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_matching_quotes_keep_forward_route(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="continue_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="continue_refactor",
            completed=False,
        )

    def test_empty_green_accepts_dirty_test_quote_without_impl(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_red_green(
            tmp_git_repo,
            impl_body=None,
            commit_test=False,
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="proceed_to_refactor_no_diff",
                evidence=[
                    _gate_evidence(impl_path="", impl_quote=""),
                ],
            ),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="proceed_to_refactor_no_diff",
            completed=False,
        )

    def test_already_exists_head_quotes_pass(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_already_exists(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="skip_refactor",
            completed=True,
        )

    def test_already_exists_missing_test_file_fails(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_already_exists(tmp_git_repo, include_test=False)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_reverted_to_red(session, ledger)

    def test_already_satisfied_declared_files_missing_from_diff_fails(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-005 / AO-022-02: declared files must sit in diff or HEAD.

        JUDGE ``skip_refactor`` plus matching ISS-ADH-020 quotes still cannot
        COMPLETE when RED/JUDGE ``files`` name a path absent from the
        injected ``<diff>`` and from ``_evidence_head_contents``. Constitution
        §3: mock ``_run_pytest``. Flow References: [].
        """
        missing = "tests/ghost_regression.py"
        red_sha = _seed_already_exists(tmp_git_repo)
        session, output, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
                files=[missing],
                test_file=missing,
            ),
            red_sha,
        )
        _assert_already_satisfied_not_completed(session, ledger)
        assert missing in session.train_feedback or missing in output, (
            "AC-PLAN-005: runner-authored feedback must name the missing "
            f"declared path {missing!r}; feedback={session.train_feedback!r}\n"
            f"{output}"
        )

    def test_already_satisfied_path_named_only_in_tasks_md_does_not_complete(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-005: a path that lives only in tasks.md / rationale fails.

        Cross-check is path membership against the injected diff and HEAD,
        not semantic reading of class names. Constitution §3. Flow
        References: [].
        """
        ghost = "tests/test_gates.py"
        red_sha = _seed_already_exists(tmp_git_repo)
        tasks_md = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.md"
        tasks_md.write_text(
            tasks_md.read_text(encoding="utf-8")
            + "\nClass TestGreenAdvisoryGate lives in tests/test_gates.py\n",
            encoding="utf-8",
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
                files=[ghost],
                test_file=ghost,
            ),
            red_sha,
        )
        _assert_already_satisfied_not_completed(session, ledger)
        assert ghost in session.train_feedback, (
            "AC-PLAN-005: feedback must name the tasks.md-only path; "
            f"feedback={session.train_feedback!r}"
        )

    def test_already_satisfied_declared_files_in_snapshot_completes_and_keeps_file(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-004 / AO-022-02: dirty declared tests may COMPLETE and stay.

        RED lands an untracked regression test, names it in ``files``, and
        JUDGE emits ``skip_refactor``. The runner may COMPLETE only when that
        file remains on disk. Constitution §3: mock ``_run_pytest``. Flow
        References: [].
        """
        rel = "tests/test_gates.py"
        body = "def test_gates() -> None:\n    assert True\n"
        statuses, call_log, output, _ledger = _run_already_satisfied_cycle(
            tmp_git_repo,
            red_files=[rel],
            red_test_file=rel,
            write_on_red={rel: body},
        )
        assert "GREEN" not in call_log, (
            f"AC-PLAN-004: GREEN must not invent tests; call_log={call_log!r}\n{output}"
        )
        assert "COMPLETED" in statuses, (
            "AC-PLAN-004: declared path in the dirty snapshot may COMPLETE; "
            f"statuses={statuses!r} call_log={call_log!r}\n{output}"
        )
        assert (tmp_git_repo / rel).is_file(), (
            "AC-PLAN-004: COMPLETE must keep the declared dirty test on disk; "
            f"missing {rel!r} statuses={statuses!r}\n{output}"
        )
        assert (tmp_git_repo / rel).read_text(encoding="utf-8") == body, (
            "AC-PLAN-004: COMPLETE must keep the declared dirty test contents"
        )

    def test_already_satisfied_restore_does_not_wipe_only_declared_tests(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-006 / AO-022-03: restore-then-COMPLETE cannot discard tests.

        The only copy of the declared regression test is the dirty RED write.
        After adjudication the file remains, or the ledger has no COMPLETED
        row. Constitution §3. Flow References: [].
        """
        rel = "tests/test_already_satisfied_dirty.py"
        body = "def test_already_satisfied_dirty() -> None:\n    assert True\n"
        statuses, call_log, output, _ledger = _run_already_satisfied_cycle(
            tmp_git_repo,
            red_files=[rel],
            write_on_red={rel: body},
        )
        kept = (tmp_git_repo / rel).is_file()
        completed = "COMPLETED" in statuses
        assert "GREEN" not in call_log, (
            f"AC-PLAN-006: GREEN must not invent tests; call_log={call_log!r}\n{output}"
        )
        assert kept or not completed, (
            "AC-PLAN-006: runner must keep the only declared dirty tests or "
            "refuse COMPLETE; wipe-then-COMPLETE is a defect. "
            f"kept={kept} statuses={statuses!r} call_log={call_log!r}\n{output}"
        )

    def test_already_satisfied_declared_files_absent_from_cycle_does_not_complete(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-005: RED-named files missing from dirty diff and HEAD.

        A test-bearing TDD already_satisfied claim that names a path the
        snapshot never saw cannot write COMPLETED. Constitution §3. Flow
        References: [].
        """
        missing = "tests/ghost_regression.py"
        statuses, call_log, output, _ledger = _run_already_satisfied_cycle(
            tmp_git_repo,
            red_files=[missing],
            red_test_file=missing,
            rationale=("Required behavior already exists in tests/ghost_regression.py"),
        )
        assert "COMPLETED" not in statuses, (
            "AC-PLAN-005: RED-declared path absent from diff and HEAD must "
            f"not COMPLETE; statuses={statuses!r} call_log={call_log!r}\n"
            f"{output}"
        )
        assert "GREEN" not in call_log, (
            "AC-PLAN-005: GREEN must not invent missing tests; "
            f"call_log={call_log!r}\n{output}"
        )

    def test_no_ac_plan_empty_evidence_completes(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo, acs=())
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(evidence=[]),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="skip_refactor",
            completed=True,
        )

    @pytest.mark.parametrize("mode", ["DIRECT", "IMMEDIATE", "EXECUTE"])
    def test_non_tdd_judge_stays_ungated(self, tmp_git_repo: Path, mode: str) -> None:
        """AC-PLAN-004: EXECUTE / IMMEDIATE / DIRECT stay outside the TDD gate."""
        from deviate.cli.micro import _run_execute_phase
        import io

        _seed_red_green(tmp_git_repo)
        extra = tmp_git_repo / "src" / "execute_extra.py"
        extra.write_text("VALUE = 1\n", encoding="utf-8")
        task = {
            "id": _GATE_TASK_ID,
            "issue_id": _GATE_ISSUE_ID,
            "description": f"{mode} judge stays ungated",
            "status": "PENDING",
            "execution_mode": mode,
        }
        ledger_path = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.jsonl"
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        SessionState(active_issue_id=_GATE_ISSUE_ID).save(session_path)
        execute_manifest = HandoverManifest(
            phase="EXECUTE",
            status="SUCCESS",
            task_id=_GATE_TASK_ID,
        )
        judge_manifest = _gate_manifest(next_action="skip_refactor", evidence=[])

        def _invoke(prompt: str, *args: object, **kwargs: object):
            if kwargs.get("phase") == "JUDGE":
                return judge_manifest, ""
            return execute_manifest, ""

        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, width=200)
        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.micro._invoke_agent", side_effect=_invoke),
            patch(
                "deviate.cli.micro._build_auto_prompt",
                return_value="test prompt",
            ),
            patch("deviate.cli.micro.resolve_model_for_phase", return_value=None),
            patch(
                "deviate.cli.micro._run_pytest",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
        ):
            _run_execute_phase(task, ledger_path, console)
        statuses = _ledger_statuses(ledger_path)
        assert "COMPLETED" in statuses, (
            f"{mode} judge must stay ungated and COMPLETE, statuses={statuses!r}"
        )


class TestJudgeEvidencePromptSchema:
    """AC-PLAN-004 / AC-PLAN-006: task-scoped evidence; no cite-every-plan."""

    _CARD_MARKER = "TSK-028-02-CARD-MARKER"

    def _build_prompt(self, tmp_path: Path) -> str:
        from deviate.cli.micro import _build_auto_prompt

        spec_dir = tmp_path / "specs" / "adhoc" / "issues"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "020-judge-evidence-prompt.md"
        spec_file.write_text("# Stub Spec\n", encoding="utf-8")
        issues_jsonl = tmp_path / "specs" / "issues.jsonl"
        issues_jsonl.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-020",
                    "source_file": "specs/adhoc/issues/020-judge-evidence-prompt.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        plan_dir = tmp_path / "specs" / "adhoc" / "020-judge-evidence-prompt"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan.md").write_text(
            "**Scenario AC-PLAN-001: this task**\n"
            "**Scenario AC-PLAN-002: later shard**\n",
            encoding="utf-8",
        )
        (plan_dir / "tasks.md").write_text(
            "# Tasks\n\n"
            "- TSK-020-04: Verify judge evidence prompt schema\n"
            "  - **Acceptance Criteria**: AC-PLAN-001\n"
            f"  - **Details**: {self._CARD_MARKER}\n",
            encoding="utf-8",
        )
        task = {
            "id": "TSK-020-04",
            "issue_id": "ISS-ADH-020",
            "description": "Verify judge evidence prompt schema",
            "status": "PENDING",
            "execution_mode": "TDD",
        }
        return _build_auto_prompt("judge", task, tmp_path)

    def test_auto_judge_prompt_requires_evidence_schema(self, tmp_path: Path) -> None:
        prompt = self._build_prompt(tmp_path)
        assert "evidence:" in prompt, (
            "Auto judge prompt must declare an evidence schema key"
        )
        assert "test_quote" in prompt, (
            "Auto judge prompt must declare test_quote on evidence items"
        )
        assert "impl_quote" in prompt, (
            "Auto judge prompt must declare impl_quote on evidence items"
        )

    def test_auto_judge_prompt_omits_default_pass_language(
        self, tmp_path: Path
    ) -> None:
        prompt = self._build_prompt(tmp_path)
        assert "Default to COMPLIANCE_PASS" not in prompt, (
            "Auto judge prompt must omit Default to COMPLIANCE_PASS"
        )
        assert "When in doubt, pass." not in prompt, (
            "Auto judge prompt must omit When in doubt, pass."
        )

    def test_auto_judge_prompt_does_not_cite_every_plan_ac(
        self, tmp_path: Path
    ) -> None:
        """AC-PLAN-004: evidence is only for resolved task tokens."""
        prompt = self._build_prompt(tmp_path)
        lowered = prompt.lower()
        assert "cite every injected" not in lowered, (
            "Auto judge prompt must drop cite-every-injected plan AC wording"
        )
        assert "every injected `ac-plan-nnn`" not in lowered, (
            "Auto judge prompt must not require every injected plan AC-PLAN-NNN"
        )
        assert "every plan scenario" not in lowered, (
            "Auto judge prompt must not require every plan scenario in this verdict"
        )

    def test_auto_judge_prompt_injects_task_card_next_to_plan(
        self, tmp_path: Path
    ) -> None:
        """AC-PLAN-004: inject the tasks.md card beside the plan contract."""
        prompt = self._build_prompt(tmp_path)
        assert self._CARD_MARKER in prompt, (
            "JUDGE prompt must inject the tasks.md card next to the plan contract"
        )
        assert '<authoritative_acceptance_contract source="plan.md">' in prompt, (
            "JUDGE prompt must still inject the plan acceptance contract"
        )

    def test_manual_judge_skill_does_not_cite_every_plan_ac(self) -> None:
        """AC-PLAN-004: /deviate-judge mirrors the task-scoped evidence rule."""
        from importlib.resources import files

        text = (
            files("deviate.prompts.commands")
            .joinpath("deviate-judge.md")
            .read_text(encoding="utf-8")
        )
        lowered = text.lower()
        assert "cite every injected" not in lowered, (
            "Manual judge skill must drop cite-every-injected plan AC wording"
        )
        assert "every injected `ac-plan-nnn`" not in lowered, (
            "Manual judge skill must not require every injected plan AC-PLAN-NNN"
        )
