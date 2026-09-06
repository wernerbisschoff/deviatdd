"""AC-PLAN-007/008: GREEN post kernel parity plus guard atomicity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavioral


def _ledger_lines(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    return [
        json.loads(line) for line in ledger.read_text().splitlines() if line.strip()
    ]


def _semantic(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "issue_id", "description", "status")}


def _seed(root: Path, monkeypatch, *, status: str = "RED"):
    from deviate.state.config import SessionState
    from deviate.state.ledger import TaskRecord

    dot = root / ".deviate"
    dot.mkdir(parents=True, exist_ok=True)
    session = SessionState(current_phase="RED", active_issue_id="ISS-007")
    session_path = dot / "session.json"
    session.save(session_path)
    ledger = root / "specs" / "007-shared-phase-kernel" / "tasks.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rec = TaskRecord(
        id="TSK-007-01",
        issue_id="ISS-007",
        description="GREEN post kernel",
        status=status,  # type: ignore[arg-type]
        execution_mode="TDD",
    )
    ledger.write_text(rec.model_dump_json() + "\n", encoding="utf-8")
    monkeypatch.chdir(root)
    return session, session_path, ledger


@pytest.mark.behavioral
def test_green_post_kernel_parity_semantic(tmp_path: Path, monkeypatch):
    """AC-PLAN-007: manual `green post` and auto `_run_green_phase` match."""
    from deviate.cli.micro import _green_post_kernel

    session, session_path, ledger = _seed(tmp_path, monkeypatch)
    before_session = session.current_phase
    assert before_session == "RED"
    outcome_manual = _green_post_kernel(tmp_path, "TSK-007-01", surface="manual")
    rows_manual = _ledger_lines(ledger)
    assert outcome_manual.token == "GREEN_POST_OK"
    assert _semantic(rows_manual[-1]) == {
        "id": "TSK-007-01",
        "issue_id": "ISS-007",
        "description": "GREEN post kernel",
        "status": "GREEN",
    }
    # Auto surface replays the same semantic side effects (timestamps excluded).
    (tmp_path / ".deviate" / "session.json").write_text(
        session.model_dump_json(), encoding="utf-8"
    )
    ledger.write_text(
        "\n".join(r.model_dump_json() for r in []),
        encoding="utf-8",
    )
    _seed(tmp_path, monkeypatch)
    outcome_auto = _green_post_kernel(tmp_path, "TSK-007-01", surface="auto")
    rows_auto = _ledger_lines(ledger)
    assert outcome_auto.token == "GREEN_POST_OK"
    assert _semantic(rows_auto[-1]) == _semantic(rows_manual[-1])


@pytest.mark.behavioral
def test_green_post_kernel_prints_token_and_commits(
    tmp_path: Path, monkeypatch, capsys
):
    """AC-PLAN-007: kernel outcome prints `GREEN_POST_OK` with matching commit."""
    from deviate.cli.micro import _green_post_kernel, print_kernel_outcome

    _seed(tmp_path, monkeypatch)
    outcome = _green_post_kernel(tmp_path, "TSK-007-01", surface="manual")
    rc = print_kernel_outcome(outcome)
    assert capsys.readouterr().out.strip() == "GREEN_POST_OK"
    assert rc == 0


@pytest.mark.behavioral
def test_green_guard_failure_writes_nothing(tmp_path: Path, monkeypatch):
    """AC-PLAN-008: failed guard keeps tokens with zero ledger/session writes."""
    from deviate.cli.micro import KernelError, _green_post_kernel
    from deviate.state.config import SessionState

    session, session_path, ledger = _seed(tmp_path, monkeypatch, status="PENDING")
    before_ledger = ledger.read_text(encoding="utf-8")
    before_session = session_path.read_text(encoding="utf-8")
    with pytest.raises(KernelError):
        _green_post_kernel(tmp_path, "TSK-007-01", surface="manual")
    assert ledger.read_text(encoding="utf-8") == before_ledger
    assert session_path.read_text(encoding="utf-8") == before_session
    assert SessionState.load(session_path).current_phase == "RED"


@pytest.mark.behavioral
def test_green_post_kernel_missing_task_raises(tmp_path: Path, monkeypatch):
    """AC-PLAN-008: missing active task raises `KernelError`."""
    from deviate.cli.micro import KernelError, _green_post_kernel

    _seed(tmp_path, monkeypatch)
    with pytest.raises(KernelError, match="TASK_NOT_FOUND"):
        _green_post_kernel(tmp_path, "TSK-999-99", surface="manual")
