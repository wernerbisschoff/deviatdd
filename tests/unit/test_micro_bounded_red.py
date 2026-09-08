"""RED: bounded RED subset for child-process E2E verification.

Covers AC-PLAN-003 (US-052-01, AO-052-01): RED runs only the bounded
verification subset within the card timeout, never the full E2E ladder.
Constitution: Micro-layer RED verification boundary; pytest unit suite.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deviate.cli import micro


def _e2e_root(tmp_path: Path) -> Path:
    (tmp_path / "mise.toml").write_text(
        '[tasks.unit]\nrun = "pytest tests/unit"\n'
        '[tasks.integration]\nrun = "pytest tests/integration"\n'
        '[tasks.e2e]\nrun = "pytest tests/e2e"\n',
        encoding="utf-8",
    )
    for d in ("tests/unit", "tests/integration", "tests/e2e"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _child_task() -> dict:
    return {
        "id": "TSK-052-04",
        "test_strategy": "e2e",
        "description": "E2E test that starts a child API process",
        "verification": "mise e2e",
    }


@pytest.mark.behavioral
def test_child_process_e2e_detected(tmp_path: Path) -> None:
    assert micro.is_child_process_e2e(_child_task()) is True
    plain = {"id": "TSK-052-04", "test_strategy": "e2e", "verification": "mise e2e"}
    assert micro.is_child_process_e2e(plain) is False


@pytest.mark.behavioral
def test_bounded_red_runs_subset_not_full_ladder(tmp_path: Path) -> None:
    root = _e2e_root(tmp_path)
    task = _child_task()
    full = micro._resolve_verification_rungs(root, task)
    assert len(full) > 1
    bounded = micro.resolve_red_verification_rungs(root, task)
    assert len(bounded) == 1
    assert bounded != full
    assert "mise e2e" not in bounded


@pytest.mark.behavioral
def test_non_child_process_e2e_keeps_full_ladder(tmp_path: Path) -> None:
    root = _e2e_root(tmp_path)
    task = {"id": "TSK-052-04", "test_strategy": "e2e", "verification": "mise e2e"}
    assert micro.resolve_red_verification_rungs(
        root, task
    ) == micro._resolve_verification_rungs(root, task)


@pytest.mark.behavioral
def test_bounded_red_stops_at_card_timeout(tmp_path: Path) -> None:
    root = _e2e_root(tmp_path)
    task = dict(_child_task())
    task["timeout_seconds"] = 60
    bounded = micro.resolve_red_verification_rungs(root, task)
    assert micro.red_timeout_seconds(root, task) <= 60
    assert len(bounded) == 1


@pytest.mark.behavioral
def test_absent_preconditions_emit_named_signal(tmp_path: Path) -> None:
    root = _e2e_root(tmp_path)
    task = dict(_child_task())
    task["preconditions"] = "mise run setup:e2e"
    with pytest.raises(micro.PreconditionNotReadyError) as exc:
        micro.resolve_red_verification_rungs(root, task, preconditions_ready=False)
    text = str(exc.value)
    assert micro.PRECONDITION_SIGNAL_NAME in text
    assert "mise run setup:e2e" in text


@pytest.mark.spy
def test_signal_path_does_not_execute_setup_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _e2e_root(tmp_path)
    calls: list[str] = []

    def fake_run(cmd: str, cwd: Path, **kw: object) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(micro, "run_safe_command", fake_run)
    task = dict(_child_task())
    task["preconditions"] = "mise run setup:e2e"
    with pytest.raises(micro.PreconditionNotReadyError):
        micro.resolve_red_verification_rungs(root, task, preconditions_ready=False)
    assert calls == []
