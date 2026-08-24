"""GH-84: persist validated JUDGE evidence on the COMPLETED ledger row.

Durability only — not a new gate kind. Constitution §3: pytest under
tests/; git isolation via tmp_git_repo + _git_env(); mock _run_pytest.
Reuse the TSK-020-03 / TSK-028-02 gate fixtures from test_judge.
"""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.test_micro.test_judge import (
    _GATE_IMPL_PATH,
    _GATE_IMPL_QUOTE,
    _GATE_ISSUE_ID,
    _GATE_SLUG,
    _GATE_TASK_ID,
    _GATE_TEST_PATH,
    _GATE_TEST_QUOTE,
    _assert_forward,
    _gate_evidence,
    _gate_git,
    _gate_manifest,
    _run_tdd_judge,
    _seed_already_exists,
    _seed_red_green,
)

runner = CliRunner()


def _completed_rows(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    rows: list[dict] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("status") == "COMPLETED":
            rows.append(data)
    return rows


def _non_completed_rows(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    rows: list[dict] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("status") != "COMPLETED":
            rows.append(data)
    return rows


def _head_sha(repo: Path) -> str:
    return _gate_git(repo, "rev-parse", "HEAD").stdout.strip()


class TestCompletedEvidenceDurability:
    """Toy TDD PASS writes citations + SHAs on the COMPLETED tasks.jsonl row."""

    def test_skip_refactor_writes_citations_and_shas_on_completed(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(session, ledger, action="skip_refactor", completed=True)
        rows = _completed_rows(ledger)
        assert len(rows) == 1, f"expected one COMPLETED row, got {rows!r}"
        evidence = rows[0].get("evidence")
        assert evidence, f"COMPLETED row must persist evidence; row={rows[0]!r}"
        items = evidence["items"] if isinstance(evidence, dict) else evidence
        assert items[0]["ac"] == "AC-PLAN-001"
        assert items[0]["test_path"] == _GATE_TEST_PATH
        assert items[0]["test_quote"] == _GATE_TEST_QUOTE
        assert items[0]["impl_path"] == _GATE_IMPL_PATH
        assert items[0]["impl_quote"] == _GATE_IMPL_QUOTE
        if isinstance(evidence, dict):
            assert evidence.get("red") == red_sha
            head = _head_sha(tmp_git_repo)
            assert evidence.get("head") == head
            assert evidence.get("green") == head

    def test_earlier_rows_stay_lean(self, tmp_git_repo: Path) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="continue_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        ledger = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.jsonl"
        for row in _non_completed_rows(ledger):
            assert not row.get("evidence"), (
                f"non-COMPLETED rows must stay lean; status={row.get('status')} "
                f"evidence={row.get('evidence')!r}"
            )

    def test_inspect_tasks_show_prints_evidence_after_session_gone(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(session, ledger, action="skip_refactor", completed=True)
        session_path = tmp_git_repo / ".deviate" / "session.json"
        if session_path.exists():
            session_path.unlink()
        issues = tmp_git_repo / "specs" / "issues.jsonl"
        assert issues.is_file()
        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["inspect", "tasks", "show", _GATE_TASK_ID, "--json"]
            )
        assert result.exit_code == 0, result.output
        shown = json.loads(result.stdout)
        evidence = shown.get("evidence")
        assert evidence, f"inspect tasks show must print evidence; got {shown!r}"
        blob = json.dumps(evidence)
        assert "AC-PLAN-001" in blob
        assert _GATE_TEST_PATH in blob
        assert _GATE_TEST_QUOTE in blob

    def test_tdd_complete_without_evidence_is_rejected(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import PhaseFailedError, _append_status_transition

        _seed_red_green(tmp_git_repo)
        ledger = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.jsonl"
        task = {
            "id": _GATE_TASK_ID,
            "issue_id": _GATE_ISSUE_ID,
            "description": "TDD complete without persisted evidence",
            "status": "JUDGE",
            "execution_mode": "TDD",
            "acceptance_criteria": [
                {"criterion_id": "AC-PLAN-001", "verification_mode": "manual"}
            ],
        }
        session = SessionState(current_phase="JUDGE", validated_evidence=[])
        session_path = tmp_git_repo / ".deviate" / "session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.save(session_path)
        with chdir(tmp_git_repo), pytest.raises(PhaseFailedError) as exc:
            _append_status_transition(task, "COMPLETED", ledger)
        assert "COMPLETED_EVIDENCE" in str(exc.value)
        assert (
            "COMPLETED"
            not in [
                json.loads(line).get("status")
                for line in ledger.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if ledger.exists()
            else True
        )

    def test_no_ac_tokens_may_complete_with_empty_evidence(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _append_status_transition

        _seed_red_green(tmp_git_repo, acs=(), card_acs=())
        ledger = tmp_git_repo / "specs" / "adhoc" / _GATE_SLUG / "tasks.jsonl"
        task = {
            "id": _GATE_TASK_ID,
            "issue_id": _GATE_ISSUE_ID,
            "description": "Enabling / infra slice",
            "status": "JUDGE",
            "execution_mode": "TDD",
        }
        with chdir(tmp_git_repo):
            _append_status_transition(task, "COMPLETED", ledger)
        rows = _completed_rows(ledger)
        assert len(rows) == 1
        evidence = rows[0].get("evidence")
        if evidence:
            items = evidence["items"] if isinstance(evidence, dict) else evidence
            assert items == []

    def test_execute_complete_stays_ungated(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _append_status_transition

        _seed_red_green(tmp_git_repo)
        ledger = tmp_git_repo / "specs" / "adhoc" / "exec" / "tasks.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        task = {
            "id": "TSK-084-09",
            "issue_id": _GATE_ISSUE_ID,
            "description": "DIRECT execute",
            "status": "PENDING",
            "execution_mode": "EXECUTE",
        }
        with chdir(tmp_git_repo):
            _append_status_transition(task, "COMPLETED", ledger)
        rows = _completed_rows(ledger)
        assert len(rows) == 1
        record = TaskRecord.model_validate(rows[0])
        assert record.status == "COMPLETED"

    def test_proceed_to_refactor_no_diff_persists_test_citations(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _append_status_transition

        red_sha = _seed_red_green(
            tmp_git_repo,
            impl_body=None,
            commit_test=False,
        )
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="proceed_to_refactor_no_diff",
                evidence=[_gate_evidence(impl_path="", impl_quote="")],
            ),
            red_sha,
        )
        _assert_forward(
            session,
            ledger,
            action="proceed_to_refactor_no_diff",
            completed=False,
        )
        task = {
            "id": _GATE_TASK_ID,
            "issue_id": _GATE_ISSUE_ID,
            "description": "Empty-green slice",
            "status": "JUDGE",
            "execution_mode": "TDD",
        }
        with chdir(tmp_git_repo):
            _append_status_transition(task, "COMPLETED", ledger)
        rows = _completed_rows(ledger)
        assert len(rows) == 1
        evidence = rows[0]["evidence"]
        items = evidence["items"] if isinstance(evidence, dict) else evidence
        assert items[0]["ac"] == "AC-PLAN-001"
        assert items[0]["test_path"] == _GATE_TEST_PATH
        assert items[0]["test_quote"] == _GATE_TEST_QUOTE
        assert items[0].get("impl_quote", "") == ""

    def test_already_satisfied_persists_head_citations_and_shas(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_already_exists(tmp_git_repo)
        session, _, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                next_action="skip_refactor",
                evidence=[_gate_evidence()],
            ),
            red_sha,
        )
        _assert_forward(session, ledger, action="skip_refactor", completed=True)
        rows = _completed_rows(ledger)
        assert len(rows) == 1
        evidence = rows[0]["evidence"]
        items = evidence["items"] if isinstance(evidence, dict) else evidence
        assert items[0]["ac"] == "AC-PLAN-001"
        assert items[0]["test_quote"] == _GATE_TEST_QUOTE
        if isinstance(evidence, dict):
            head = _head_sha(tmp_git_repo)
            assert evidence.get("head") == head
            assert evidence.get("green") == head
            assert evidence.get("red") == red_sha
