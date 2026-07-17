"""Tests for deviate.core.run_logger.

Covers the per-task structured log surface (``TaskLogger``) which
complements the per-run ``RunLogger``. Each task gets its own log file
under ``.deviate/logs/<issue_id>/<task_id>.log`` so the operator can
recover the full prompt/agent-output transcript for one task without
grepping a single chronological run log.
"""

from __future__ import annotations

from pathlib import Path

from deviate.core.run_logger import RunLogger, TaskLogger


def test_task_logger_writes_to_issue_and_task_path(tmp_path: Path) -> None:
    """A TaskLogger routes events to .deviate/logs/<issue_id>/<task_id>.log."""
    log = TaskLogger(tmp_path, issue_id="TSK-001", task_id="TSK-001-02")
    log.log(
        "INVOKE_AGENT",
        task_id="TSK-001-02",
        phase="RED",
        prompt="write a failing test",
    )
    log.close()

    expected = tmp_path / ".deviate" / "logs" / "TSK-001" / "TSK-001-02.log"
    assert expected.exists(), f"expected per-task log at {expected}"
    contents = expected.read_text(encoding="utf-8")
    assert "INVOKE_AGENT" in contents
    assert "write a failing test" in contents
    assert "TSK-001-02" in contents


def test_task_loggers_for_different_tasks_do_not_collide(tmp_path: Path) -> None:
    """Two TaskLoggers for different tasks land in different files."""
    a = TaskLogger(tmp_path, issue_id="TSK-001", task_id="TSK-001-02")
    a.log("INVOKE_AGENT", task_id="TSK-001-02", phase="RED", prompt="alpha")
    a.close()

    b = TaskLogger(tmp_path, issue_id="TSK-001", task_id="TSK-001-03")
    b.log("INVOKE_AGENT", task_id="TSK-001-03", phase="RED", prompt="beta")
    b.close()

    file_a = tmp_path / ".deviate" / "logs" / "TSK-001" / "TSK-001-02.log"
    file_b = tmp_path / ".deviate" / "logs" / "TSK-001" / "TSK-001-03.log"
    assert file_a.exists()
    assert file_b.exists()
    assert "alpha" in file_a.read_text(encoding="utf-8")
    assert "beta" in file_b.read_text(encoding="utf-8")
    # Cross-contamination guard
    assert "alpha" not in file_b.read_text(encoding="utf-8")
    assert "beta" not in file_a.read_text(encoding="utf-8")


def test_task_logger_appends_across_invocations(tmp_path: Path) -> None:
    """Re-instantiating a TaskLogger for the same task continues the file
    rather than overwriting — a re-run on the same task accumulates history."""
    first = TaskLogger(tmp_path, issue_id="TSK-002", task_id="TSK-002-01")
    first.log("PHASE_START", task_id="TSK-002-01", phase="RED", attempt=1)
    first.close()

    second = TaskLogger(tmp_path, issue_id="TSK-002", task_id="TSK-002-01")
    second.log("PHASE_START", task_id="TSK-002-01", phase="RED", attempt=2)
    second.close()

    target = tmp_path / ".deviate" / "logs" / "TSK-002" / "TSK-002-01.log"
    contents = target.read_text(encoding="utf-8")
    assert "attempt: 1" in contents
    assert "attempt: 2" in contents


def test_run_logger_still_writes_per_run_file(tmp_path: Path) -> None:
    """Regression guard: RunLogger behaviour is unchanged (back-compat)."""
    run = RunLogger(tmp_path)
    run.log("RUN_START", command="deviate micro run")
    run.close()
    matches = list((tmp_path / ".deviate" / "logs").glob("run_*.log"))
    assert len(matches) == 1
    assert "RUN_START" in matches[0].read_text(encoding="utf-8")
