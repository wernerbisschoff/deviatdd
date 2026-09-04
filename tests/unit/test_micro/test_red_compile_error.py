"""RED: compile-error output counts as a failing RED (ISS-ADH-041, TSK-041-01).

AC-PLAN-001: non-zero result with compile-error markers commits RED / GREEN.
AC-PLAN-002: exit 0 / exit 5 / exit 127 still route to adjudication.
AC-PLAN-003: mixed compile-error plus passing output counts as failing.
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

import deviate.cli.micro as micro
from deviate.cli.micro import _run_red_phase
from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState


def _proc(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _classifier():
    fn = getattr(micro, "_is_compile_error", None)
    assert fn is not None, (
        "_is_compile_error missing on deviate.cli.micro (RED: implement it)"
    )
    return fn


@pytest.mark.behavioral
def test_python_collection_traceback_is_compile_error():
    out = "ERROR tests/test_x.py - ModuleNotFoundError: No module named 'foo'\nTraceback (most recent call last):\n"
    assert _classifier()(_proc(2, stdout=out)) is True


@pytest.mark.behavioral
def test_exunit_markers_are_compile_errors():
    assert (
        _classifier()(_proc(1, stdout="** (CompileError) Compilation failed")) is True
    )
    assert _classifier()(_proc(1, stderr="error: undefined function foo/0")) is True


@pytest.mark.behavioral
def test_exit_zero_with_markers_still_adjudicates():
    assert _classifier()(_proc(0, stdout="1 passed, Compilation failed")) is False


@pytest.mark.behavioral
def test_exit_five_and_127_are_not_compile_errors():
    assert _classifier()(_proc(5, stdout="no tests ran")) is False
    assert _classifier()(_proc(127, stderr="No test command configured")) is False


@pytest.mark.behavioral
def test_empty_stdout_with_stderr_markers_counts():
    assert (
        _classifier()(_proc(2, stderr="ModuleNotFoundError: No module named 'x'"))
        is True
    )


def _drive_red(root: Path, result: subprocess.CompletedProcess):
    task = {
        "id": "TSK-041-01",
        "issue_id": "ISS-ADH-041",
        "description": "compile error RED",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    session = SessionState(current_phase="IDLE")
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session.save(session_path)
    ledger_path = root / "specs" / "adhoc" / "tasks.jsonl"
    manifest = HandoverManifest(phase="RED", status="SUCCESS", task_id=task["id"])
    with (
        chdir(root),
        patch.object(micro, "_phase_already_done", return_value=False),
        patch.object(micro, "_log_run"),
        patch.object(micro, "_make_agent_output_callback", return_value=None),
        patch.object(micro, "resolve_model_for_phase", return_value=None),
        patch.object(micro, "_invoke_agent", return_value=(manifest, "")),
        patch.object(micro, "_run_test_cmd", return_value=result),
        patch.object(micro, "_run_format_cmd", return_value=_proc(0)),
        patch.object(micro, "append_task_transition"),
        patch.object(micro, "_commit_phase", return_value=True),
        patch.object(micro, "_verify_clean_worktree"),
        patch.object(
            micro, "_adjudicate_red_no_failing_test", return_value=session
        ) as adjudicate,
    ):
        _run_red_phase(task, ledger_path, session, session_path, Console(quiet=True))
    return adjudicate


@pytest.mark.behavioral
def test_red_phase_routes_compile_error_to_green(tmp_git_repo: Path):
    out = "ERROR tests/test_x.py - ModuleNotFoundError: No module named 'foo'"
    adjudicate = _drive_red(tmp_git_repo, _proc(2, stdout=out))
    adjudicate.assert_not_called()


@pytest.mark.behavioral
def test_red_phase_routes_exit_zero_to_adjudication(tmp_git_repo: Path):
    adjudicate = _drive_red(tmp_git_repo, _proc(0, stdout="1 passed"))
    adjudicate.assert_called_once()


@pytest.mark.behavioral
def test_red_phase_routes_mixed_output_to_green(tmp_git_repo: Path):
    out = "1 passed\nERROR tests/test_y.py - ModuleNotFoundError: No module named 'bar'"
    adjudicate = _drive_red(tmp_git_repo, _proc(2, stdout=out))
    adjudicate.assert_not_called()
