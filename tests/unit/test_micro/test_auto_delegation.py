"""AC-PLAN-015/016: auto phase delegation with single agent call (RED)."""

from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.core.agent import HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord


def _agent_ok(*args, **kwargs):
    phase = kwargs.get("phase", "RED")
    tid = kwargs.get("task_id", "TSK-001-07")
    return HandoverManifest(phase=phase, status="SUCCESS", task_id=tid), ""


def _agent_ok_3tuple(*args, **kwargs):
    m, tail = _agent_ok(*args, **kwargs)
    return m, tail, False


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        ledger_path.open("a", encoding="utf-8").write(r.model_dump_json() + "\n")


def _seed_repo(root: Path, status: str = "PENDING") -> tuple[Path, Path]:
    (root / ".deviate").mkdir(parents=True, exist_ok=True)
    session_path = root / ".deviate" / "session.json"
    SessionState(current_phase="IDLE").save(session_path)
    task = TaskRecord(
        id="TSK-001-07",
        issue_id="ISS-007-001",
        description="auto delegation",
        status=status,  # type: ignore[arg-type]
        execution_mode="TDD",
    )
    ledger_path = root / "specs" / "007-shared-phase-kernel" / "tasks.jsonl"
    _write_ledger(ledger_path, task)
    return ledger_path, session_path


def _head_count(root: Path) -> int:
    proc = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return int(proc.stdout.strip()) if proc.returncode == 0 else 0


@pytest.mark.behavioral
def test_red_auto_delegates_to_kernels_with_one_agent_call(tmp_git_repo: Path):
    from deviate.cli import micro as micro

    ledger_path, session_path = _seed_repo(tmp_git_repo)
    failing = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 failed", stderr=""
    )
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_invoke_agent", side_effect=_agent_ok_3tuple) as spy_agent,
        patch.object(micro, "_red_pre_kernel", wraps=micro._red_pre_kernel) as spy_pre,
        patch.object(
            micro, "_red_post_kernel", wraps=micro._red_post_kernel
        ) as spy_post,
        patch.object(micro, "_run_test_cmd", return_value=failing),
        patch.object(
            micro,
            "_run_format_cmd",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        from rich.console import Console

        task = {"id": "TSK-001-07", "issue_id": "ISS-007-001"}
        session = SessionState.load(session_path)
        micro._run_red_phase(task, ledger_path, session, session_path, Console())
    assert spy_pre.call_count == 1
    assert spy_post.call_count == 1
    assert spy_agent.call_count == 1


@pytest.mark.behavioral
def test_green_auto_delegates_to_kernel_with_one_agent_call(tmp_git_repo: Path):
    from deviate.cli import micro as micro

    ledger_path, session_path = _seed_repo(tmp_git_repo, status="RED")
    passing = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_invoke_agent", side_effect=_agent_ok_3tuple) as spy_agent,
        patch.object(
            micro, "_green_post_kernel", wraps=micro._green_post_kernel
        ) as spy_post,
        patch.object(micro, "_run_test_cmd", return_value=passing),
        patch.object(
            micro,
            "_run_format_cmd",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        from rich.console import Console

        task = {"id": "TSK-001-07", "issue_id": "ISS-007-001"}
        session = SessionState.load(session_path)
        micro._run_green_phase(task, ledger_path, session, session_path, Console())
    assert spy_post.call_count == 1
    assert spy_agent.call_count == 1


@pytest.mark.behavioral
def test_refactor_auto_delegates_to_kernels_with_one_agent_call(tmp_git_repo: Path):
    from deviate.cli import micro as micro

    ledger_path, session_path = _seed_repo(tmp_git_repo, status="GREEN")
    passing = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_invoke_agent", side_effect=_agent_ok) as spy_agent,
        patch.object(
            micro, "_refactor_pre_kernel", wraps=micro._refactor_pre_kernel
        ) as spy_pre,
        patch.object(
            micro, "_refactor_post_kernel", wraps=micro._refactor_post_kernel
        ) as spy_post,
        patch.object(micro, "_run_test_cmd", return_value=passing),
        patch.object(
            micro,
            "_run_format_cmd",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        from rich.console import Console

        task = {"id": "TSK-001-07", "issue_id": "ISS-007-001"}
        session = SessionState.load(session_path)
        micro._run_refactor_phase(task, ledger_path, session, session_path, Console())
    assert spy_pre.call_count == 1
    assert spy_post.call_count == 1
    assert spy_agent.call_count == 1


@pytest.mark.spy
def test_kernels_make_zero_agent_calls(tmp_git_repo: Path):
    from deviate.cli import micro as micro

    ledger_path, _ = _seed_repo(tmp_git_repo, status="RED")
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_invoke_agent", side_effect=_agent_ok) as spy_agent,
    ):
        micro._green_post_kernel(root=tmp_git_repo, task_id="TSK-001-07")
    assert spy_agent.call_count == 0
    assert ledger_path.read_text(encoding="utf-8").count("TSK-001-07") >= 2


KERNELS = [
    "_red_pre_kernel",
    "_red_post_kernel",
    "_green_post_kernel",
    "_refactor_pre_kernel",
    "_refactor_post_kernel",
]


@pytest.mark.behavioral
@pytest.mark.parametrize("kernel_name", KERNELS)
def test_kernel_error_caught_per_step_with_no_side_effect(
    tmp_git_repo: Path, kernel_name: str
):
    from deviate.cli import micro as micro
    from deviate.cli.micro import KernelError

    stripped = kernel_name.lstrip("_")
    if stripped.startswith("green"):
        phase = "green"
        seed_status = "RED"
    elif stripped.startswith("refactor"):
        phase = "refactor"
        seed_status = "GREEN"
    else:
        phase = "red"
        seed_status = "PENDING"
    ledger_path, session_path = _seed_repo(tmp_git_repo, status=seed_status)
    ledger_before = ledger_path.read_text(encoding="utf-8")
    session_before = session_path.read_text(encoding="utf-8")
    commits_before = _head_count(tmp_git_repo)
    failing = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 failed", stderr=""
    )
    passing = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )
    with (
        chdir(tmp_git_repo),
        patch.object(micro, "_invoke_agent", side_effect=_agent_ok_3tuple),
        patch.object(
            micro, kernel_name, side_effect=KernelError("GUARD_REJECTED", "injected")
        ) as spy_kernel,
        patch.object(
            micro, "_run_test_cmd", return_value=failing if phase == "red" else passing
        ),
        patch.object(
            micro,
            "_run_format_cmd",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        from rich.console import Console

        task = {"id": "TSK-001-07", "issue_id": "ISS-007-001"}
        session = SessionState.load(session_path)
        runner = {
            "red": micro._run_red_phase,
            "green": micro._run_green_phase,
            "refactor": micro._run_refactor_phase,
        }[phase]
        try:
            runner(task, ledger_path, session, session_path, Console())
        except Exception:
            pass
    assert spy_kernel.call_count >= 1
    assert ledger_path.read_text(encoding="utf-8") == ledger_before
    assert session_path.read_text(encoding="utf-8") == session_before
    assert _head_count(tmp_git_repo) == commits_before
