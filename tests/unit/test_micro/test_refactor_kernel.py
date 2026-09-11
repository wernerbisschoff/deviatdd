"""AC-PLAN-009..012: REFACTOR pre/post shared kernels (RED)."""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

pytestmark = pytest.mark.behavioral

runner = CliRunner()

SHARED_KEYS = [
    "status",
    "task_id",
    "task_title",
    "task_type",
    "test_strategy",
    "test_write_dir",
    "test_command",
    "lint_command",
]


def _make_task_record(status: str = "GREEN") -> TaskRecord:
    return TaskRecord(
        id="TSK-001-05",
        issue_id="ISS-001-007",
        description="Refactor kernel parity",
        status=status,  # type: ignore[arg-type]
        execution_mode="TDD",
    )


def _seed(repo: Path, status: str = "GREEN") -> None:
    spec_dir = repo / "specs" / "001-007"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "tasks.md").write_text(
        "# Tasks\n\n- TSK-001-05: Refactor kernel parity\n"
        "  - **Type**: Feature_Batch\n"
        "  - **Mode**: TDD\n"
        "  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`\n"
        "  - **Files**:\n    - `src/deviate/cli/micro.py`\n",
        encoding="utf-8",
    )
    (spec_dir / "tasks.jsonl").write_text(
        _make_task_record(status).model_dump_json() + "\n", encoding="utf-8"
    )
    dot_dir = repo / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="GREEN", active_issue_id="ISS-001-007").save(
        dot_dir / "session.json"
    )


def _manual_contract(
    repo: Path, capsys: pytest.CaptureFixture[str], task_id: str = "TSK-001-05"
) -> dict:
    with chdir(repo):
        result = runner.invoke(cli, ["refactor", "pre", "--task", task_id])
    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    raw = result.stdout if result.stdout else capsys.readouterr().out
    return json.loads(raw.strip().splitlines()[0])


@pytest.mark.behavioral
def test_manual_refactor_pre_holds_eight_field_contract(
    tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
):
    """AC-PLAN-009: stdout holds the eight-field contract plus doctor fields."""
    _seed(tmp_git_repo)
    data = _manual_contract(tmp_git_repo, capsys)
    for key in SHARED_KEYS:
        assert key in data, f"missing contract key: {key}"
    assert data["status"] == "READY"
    assert data["task_id"] == "TSK-001-05"
    assert "spec_dir" in data


@pytest.mark.behavioral
def test_refactor_pre_kernel_builds_identical_shared_keys(
    tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
):
    """AC-PLAN-010: auto kernel builds the same shared keys as manual."""
    from deviate.cli.micro import _refactor_pre_kernel

    _seed(tmp_git_repo)
    manual = _manual_contract(tmp_git_repo, capsys)
    with chdir(tmp_git_repo):
        kernel_contract = _refactor_pre_kernel(task_id="TSK-001-05", root=Path.cwd())
    for key in SHARED_KEYS:
        assert kernel_contract[key] == manual[key], f"drift on shared key: {key}"


@pytest.mark.behavioral
def test_refactor_pre_kernel_guard_rejects_non_green_ledger(
    tmp_git_repo: Path,
):
    """Edge: GREEN-passed precondition missing raises KernelError."""
    from deviate.cli.micro import KernelError, _refactor_pre_kernel

    _seed(tmp_git_repo, status="PENDING")
    with chdir(tmp_git_repo):
        with pytest.raises(KernelError):
            _refactor_pre_kernel(task_id="TSK-001-05", root=Path.cwd())


@pytest.mark.behavioral
def test_refactor_post_kernel_matches_manual_side_effects(tmp_git_repo: Path):
    """AC-PLAN-011: both post surfaces match side effects, print token."""
    import deviate.cli.micro as micro

    _seed(tmp_git_repo)
    with chdir(tmp_git_repo):
        result = runner.invoke(cli, ["refactor", "post"])
    assert "REFACTOR_POST_OK" in (result.stdout or result.output)
    with chdir(tmp_git_repo):
        outcome = micro._refactor_post_kernel(task_id="TSK-001-05", root=Path.cwd())
    assert outcome.token == "REFACTOR_POST_OK"


@pytest.mark.behavioral
def test_refactor_post_kernel_gate_failure_writes_no_completed(
    tmp_git_repo: Path,
):
    """AC-PLAN-012: failed regression gate exits current code, no COMPLETED."""
    from deviate.cli.micro import KernelError, _refactor_post_kernel

    _seed(tmp_git_repo)
    with chdir(tmp_git_repo):
        with pytest.raises(KernelError):
            _refactor_post_kernel(
                task_id="TSK-001-05",
                root=Path.cwd(),
                regression_passed=False,
            )
        ledger = Path("specs") / "001-007" / "tasks.jsonl"
        rows = ledger.read_text(encoding="utf-8")
    assert "COMPLETED" not in rows
