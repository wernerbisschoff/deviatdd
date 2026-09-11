"""AC-PLAN-009..012: REFACTOR pre/post shared kernels (RED)."""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from tests.conftest import _git_env
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


@pytest.mark.parametrize("entrypoint", ["kernel", "manual", "manual-tests"])
@pytest.mark.parametrize("reject_commit", [False, True])
def test_refactor_post_commits_ledger_or_reports_failure(
    tmp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
    reject_commit: bool,
):
    import deviate.cli.micro as micro

    _seed(tmp_git_repo)
    (tmp_git_repo / ".gitignore").write_text(".deviate/\n")
    monkeypatch.setattr(
        micro,
        "_test_command_candidates",
        lambda root: ["pytest"] if entrypoint == "manual-tests" else [],
    )
    monkeypatch.setattr(
        micro,
        "_run_pytest",
        lambda root: subprocess.CompletedProcess([], 0, stdout="1 passed", stderr=""),
    )
    if reject_commit:
        hooks = tmp_git_repo / ".git" / "hooks"
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'commit rejected' >&2\nexit 1\n")
        hook.chmod(0o755)
        subprocess.run(
            ["git", "config", "core.hooksPath", str(hooks)],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

    with chdir(tmp_git_repo):
        if entrypoint == "kernel":
            if reject_commit:
                with pytest.raises(micro.KernelError) as exc:
                    micro._refactor_post_kernel(task_id="TSK-001-05", root=tmp_git_repo)
                assert exc.value.token == "COMMIT_FAILED"
            else:
                outcome = micro._refactor_post_kernel(
                    task_id="TSK-001-05", root=tmp_git_repo
                )
                assert outcome.token == "REFACTOR_POST_OK"
        else:
            result = runner.invoke(cli, ["refactor", "post"])
            if reject_commit:
                assert result.exit_code != 0, result.output
                assert "COMMIT_FAILED" in result.output
                assert "REFACTOR_POST_OK" not in result.output
                assert "NOTHING_CHANGED" not in result.output
            else:
                assert result.exit_code == 0, result.output
                assert "REFACTOR_POST_OK" in result.output

    ledger = tmp_git_repo / "specs/001-007/tasks.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert sum(row["status"] == "COMPLETED" for row in rows) == 1
    if not reject_commit:
        committed = subprocess.run(
            ["git", "show", "HEAD:specs/001-007/tasks.jsonl"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert committed.stdout == ledger.read_text()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert not status.stdout.strip()
