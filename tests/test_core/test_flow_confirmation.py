"""Tests for flow-ledger confirmation and release-candidate helpers.

These tests pin the two runtime contracts that /deviate-merge and
/deviate-release now depend on:

1. ``_confirm_implemented_flows`` returns a ``FlowConfirmationResult``
   whose ``flow_ids`` lists the refs that are confirmed (newly written
   or already recorded on a prior call), ``appended_count`` separates
   new writes from idempotent no-ops, and ``skipped_refs`` carries
   orphan tokens and malformed entries. The dedup key is
   ``(flow_id, event_type, event_issue_id, evidence_path)`` with
   ``evidence_path=None`` as the merge-emitted marker.

2. ``select_release_candidate_flows`` returns ``FlowCoverage`` rows
   with ``impl_status == "CONFIRMED_IMPLEMENTED"`` ordered by issue
   reference timestamp desc; honours ``exclude_released=True`` to
   drop flows already tagged by a ``FLOW_INCLUDED_IN_RELEASE`` event;
   returns ``[]`` when the flows ledger is missing (first-run state).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from deviate.state.ledger import (
    FlowEvent,
    FlowRecord,
    IssueRecord,
    _confirm_implemented_flows,
    _iter_flow_ledger_rows,
    select_release_candidate_flows,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _seed_flow(ledger_path: Path, flow_id: str) -> None:
    """Append a FlowRecord identity row for *flow_id*."""
    record = FlowRecord(
        flow_id=flow_id,
        name=f"Test flow {flow_id}",
        actor="tester",
        domain="test",
        source="specs/_product/flows/flows-test.md",
    )
    line = record.model_dump_json()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _seed_issue_at(
    ledger_path: Path,
    issue_id: str,
    *,
    flow_refs: list[str] | None = None,
    source_file: str = "specs/test/issues/test-001.md",
    timestamp: datetime | None = None,
) -> None:
    """Append a SPECIFIED IssueRecord with a controlled timestamp."""
    record = IssueRecord(
        issue_id=issue_id,
        type="feature",
        title=f"Test issue {issue_id}",
        status="SPECIFIED",
        source_file=source_file,
        flow_refs=flow_refs or [],
        timestamp=timestamp or datetime.now(timezone.utc),
        created_at=timestamp or datetime.now(timezone.utc),
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def _seed_issue(
    ledger_path: Path,
    issue_id: str,
    *,
    flow_refs: list[str] | None = None,
    source_file: str = "specs/test/issues/test-001.md",
) -> None:
    _seed_issue_at(ledger_path, issue_id, flow_refs=flow_refs, source_file=source_file)


# ---------------------------------------------------------------------------
# _confirm_implemented_flows
# ---------------------------------------------------------------------------


class TestConfirmImplementedFlows:
    """Pin the merge-time flow confirmation helper."""

    def test_writes_one_event_per_flow_ref(self, tmp_path: Path) -> None:
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_flow(flows_ledger, "FLOW-02")
        _seed_issue(issues_ledger, "ISS-001", flow_refs=["FLOW-01", "FLOW-02"])

        result = _confirm_implemented_flows(
            issue_id="ISS-001",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01", "FLOW-02"]
        assert result.appended_count == 2
        assert result.skipped_refs == []
        _, events = _iter_flow_ledger_rows(flows_ledger)
        assert len(events) == 2
        types_by_flow = {(e.flow_id, e.event_type) for e in events}
        assert types_by_flow == {
            ("FLOW-01", "FLOW_CONFIRMED_IMPLEMENTED"),
            ("FLOW-02", "FLOW_CONFIRMED_IMPLEMENTED"),
        }
        for e in events:
            assert e.event_issue_id == "ISS-001"
            assert e.evidence_path is None

    def test_idempotent_on_repeat_call(self, tmp_path: Path) -> None:
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_issue(issues_ledger, "ISS-002", flow_refs=["FLOW-01"])

        first = _confirm_implemented_flows(
            issue_id="ISS-002",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )
        second = _confirm_implemented_flows(
            issue_id="ISS-002",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        # First call writes the event; second call reports the same
        # flow as confirmed but appends nothing.
        assert first.flow_ids == ["FLOW-01"]
        assert first.appended_count == 1
        assert second.flow_ids == ["FLOW-01"]
        assert second.appended_count == 0
        _, events = _iter_flow_ledger_rows(flows_ledger)
        # Exactly one event row — second call deduped on the
        # (flow_id, event_type, event_issue_id, evidence_path) key.
        assert len(events) == 1

    def test_zero_flow_refs_returns_empty_result(self, tmp_path: Path) -> None:
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_issue(issues_ledger, "ISS-003", flow_refs=[])

        result = _confirm_implemented_flows(
            issue_id="ISS-003",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == []
        assert result.appended_count == 0
        assert result.skipped_refs == []
        # No ledger file should have been created when there were no flows.
        assert not flows_ledger.exists()

    def test_orphaned_ref_still_confirmed(self, tmp_path: Path) -> None:
        """A flow_ref that has no FlowRecord in the flows ledger is
        still confirmed: merge is the moment the user shipped, and
        orphan classification is a coverage concern.  ``skipped_refs``
        remains empty for syntactically valid refs."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_issue(issues_ledger, "ISS-004", flow_refs=["FLOW-01", "FLOW-99"])

        result = _confirm_implemented_flows(
            issue_id="ISS-004",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01", "FLOW-99"]
        assert result.skipped_refs == []
        assert result.appended_count == 2
        _, events = _iter_flow_ledger_rows(flows_ledger)
        # Both refs produced events.
        assert sorted(e.flow_id for e in events) == ["FLOW-01", "FLOW-99"]

    def test_unknown_issue_returns_empty_result(self, tmp_path: Path) -> None:
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        # No issues seeded.

        result = _confirm_implemented_flows(
            issue_id="ISS-DOES-NOT-EXIST",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == []
        assert result.appended_count == 0
        assert result.skipped_refs == []
        assert not flows_ledger.exists()

    def test_dedup_uses_none_evidence_path(self, tmp_path: Path) -> None:
        """Re-calling with evidence_path left at its default ``None``
        produces a single event, not two — the dedup key is
        ``(flow_id, event_type, event_issue_id, evidence_path)``."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_issue(issues_ledger, "ISS-005", flow_refs=["FLOW-01"])

        _confirm_implemented_flows(
            issue_id="ISS-005",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )
        _confirm_implemented_flows(
            issue_id="ISS-005",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        _, events = _iter_flow_ledger_rows(flows_ledger)
        assert len(events) == 1
        assert events[0].evidence_path is None

    def test_missing_flows_ledger_confirms_all_valid_refs(self, tmp_path: Path) -> None:
        """First-run: flows.jsonl absent. Valid refs are still confirmed."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_issue(issues_ledger, "ISS-006", flow_refs=["FLOW-01", "FLOW-02"])

        result = _confirm_implemented_flows(
            issue_id="ISS-006",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01", "FLOW-02"]
        assert result.skipped_refs == []
        assert flows_ledger.exists()
        _, events = _iter_flow_ledger_rows(flows_ledger)
        assert {e.flow_id for e in events} == {"FLOW-01", "FLOW-02"}

    def test_empty_flows_ledger_treated_as_unseeded(self, tmp_path: Path) -> None:
        """The file exists but has no identity rows — refs are not orphans."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        flows_ledger.parent.mkdir(parents=True, exist_ok=True)
        flows_ledger.write_text("", encoding="utf-8")
        _seed_issue(issues_ledger, "ISS-007", flow_refs=["FLOW-01"])

        result = _confirm_implemented_flows(
            issue_id="ISS-007",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01"]
        assert result.skipped_refs == []
        _, events = _iter_flow_ledger_rows(flows_ledger)
        assert [e.flow_id for e in events] == ["FLOW-01"]

    def test_event_only_ledger_treated_as_unseeded(self, tmp_path: Path) -> None:
        """The ledger has events but no FlowRecord identity rows —
        refs are still not orphans."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        # Pre-seed an event with no matching identity row.
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_DISCOVERED",
        )
        _seed_issue(issues_ledger, "ISS-008", flow_refs=["FLOW-01"])

        result = _confirm_implemented_flows(
            issue_id="ISS-008",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01"]
        assert result.skipped_refs == []
        _, events = _iter_flow_ledger_rows(flows_ledger)
        event_types = [e.event_type for e in events]
        assert "FLOW_DISCOVERED" in event_types
        assert "FLOW_CONFIRMED_IMPLEMENTED" in event_types

    def test_partial_seed_confirms_all_valid_refs(self, tmp_path: Path) -> None:
        """A partially seeded identity ledger (some FlowRecords present,
        others missing) confirms every syntactically valid ref.
        Orphan classification is a coverage concern."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        # Only FLOW-01 has an identity row; FLOW-02 does not.
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_issue(issues_ledger, "ISS-009", flow_refs=["FLOW-01", "FLOW-02"])

        result = _confirm_implemented_flows(
            issue_id="ISS-009",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        assert result.flow_ids == ["FLOW-01", "FLOW-02"]
        assert result.skipped_refs == []
        _, events = _iter_flow_ledger_rows(flows_ledger)
        assert sorted(e.flow_id for e in events) == ["FLOW-01", "FLOW-02"]

    def test_malformed_token_added_to_skipped(self, tmp_path: Path) -> None:
        """Tokens that fail the canonical regex are not confirmed and
        are surfaced in ``skipped_refs`` for the operator to triage."""
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _seed_flow(flows_ledger, "FLOW-01")
        _seed_issue(
            issues_ledger,
            "ISS-010",
            flow_refs=["FLOW-01", "BAD-ID", "FLOW-1"],
        )

        result = _confirm_implemented_flows(
            issue_id="ISS-010",
            issues_ledger=issues_ledger,
            flows_ledger=flows_ledger,
        )

        # FLOW-1 is malformed (only one digit); BAD-ID is not a flow ref.
        assert result.flow_ids == ["FLOW-01"]
        assert set(result.skipped_refs) == {"BAD-ID", "FLOW-1"}


# ---------------------------------------------------------------------------
# select_release_candidate_flows
# ---------------------------------------------------------------------------


def _write_index(path: Path, flow_ids: list[str]) -> None:
    """Write a minimal flows/index.md that yields FlowRecord rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| Flow ID | Name | Actor | Domain | Status | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for flow_id in flow_ids:
        lines.append(
            f"| {flow_id} | name {flow_id} | actor | domain | Active | "
            f"specs/_product/flows/flows-test.md |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _emit_event(
    flows_ledger: Path,
    *,
    flow_id: str,
    event_type: str,
    issue_id: str | None = None,
    release_version: str | None = None,
) -> None:
    event = FlowEvent(
        flow_id=flow_id,
        event_type=event_type,  # type: ignore[arg-type]
        event_issue_id=issue_id,
        event_release_version=release_version,
        timestamp=datetime.now(timezone.utc),
    )
    flows_ledger.parent.mkdir(parents=True, exist_ok=True)
    with flows_ledger.open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")


class TestSelectReleaseCandidateFlows:
    """Pin the release-time flow selection contract."""

    def test_returns_confirmed_implemented_not_yet_released(
        self, tmp_path: Path
    ) -> None:
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02", "FLOW-03"])
        # FLOW-01 + FLOW-02 are confirmed; FLOW-03 has no events.
        _emit_event(flows_ledger, flow_id="FLOW-01", event_type="FLOW_DISCOVERED")
        _emit_event(flows_ledger, flow_id="FLOW-02", event_type="FLOW_DISCOVERED")
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-001",
        )
        _emit_event(
            flows_ledger,
            flow_id="FLOW-02",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-002",
        )
        # Equal timestamps: ordering falls back to flow_id ascending.
        _seed_issue_at(
            issues_ledger,
            "ISS-001",
            flow_refs=["FLOW-01"],
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        _seed_issue_at(
            issues_ledger,
            "ISS-002",
            flow_refs=["FLOW-02"],
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        candidates = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
        )

        # Only the two confirmed flows; FLOW-03 is UNCONFIRMED.
        # Equal timestamps → flow_id ascending tiebreak.
        assert [c.flow_id for c in candidates] == ["FLOW-01", "FLOW-02"]
        for c in candidates:
            assert c.impl_status == "CONFIRMED_IMPLEMENTED"

    def test_exclude_released_false_returns_all_confirmed(self, tmp_path: Path) -> None:
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02"])
        _emit_event(flows_ledger, flow_id="FLOW-01", event_type="FLOW_DISCOVERED")
        _emit_event(flows_ledger, flow_id="FLOW-02", event_type="FLOW_DISCOVERED")
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-001",
        )
        _emit_event(
            flows_ledger,
            flow_id="FLOW-02",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-002",
        )
        # FLOW-01 was already in a prior release.
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_INCLUDED_IN_RELEASE",
            release_version="1.0.0",
        )
        _seed_issue(issues_ledger, "ISS-001", flow_refs=["FLOW-01"])
        _seed_issue(issues_ledger, "ISS-002", flow_refs=["FLOW-02"])

        all_confirmed = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
            exclude_released=False,
        )
        assert {c.flow_id for c in all_confirmed} == {"FLOW-01", "FLOW-02"}

    def test_exclude_released_true_drops_already_released(self, tmp_path: Path) -> None:
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02"])
        _emit_event(flows_ledger, flow_id="FLOW-01", event_type="FLOW_DISCOVERED")
        _emit_event(flows_ledger, flow_id="FLOW-02", event_type="FLOW_DISCOVERED")
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-001",
        )
        _emit_event(
            flows_ledger,
            flow_id="FLOW-02",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-002",
        )
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_INCLUDED_IN_RELEASE",
            release_version="1.0.0",
        )
        _seed_issue(issues_ledger, "ISS-001", flow_refs=["FLOW-01"])
        _seed_issue(issues_ledger, "ISS-002", flow_refs=["FLOW-02"])

        candidates = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
            exclude_released=True,
        )

        assert [c.flow_id for c in candidates] == ["FLOW-02"]

    def test_ordered_by_last_referenced_issue_desc(self, tmp_path: Path) -> None:
        """The most recently referenced issue comes first; flow_id
        ascending is the tiebreaker when timestamps are equal."""
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02", "FLOW-03"])
        for flow_id in ("FLOW-01", "FLOW-02", "FLOW-03"):
            _emit_event(flows_ledger, flow_id=flow_id, event_type="FLOW_DISCOVERED")
            _emit_event(
                flows_ledger,
                flow_id=flow_id,
                event_type="FLOW_CONFIRMED_IMPLEMENTED",
                issue_id=f"ISS-{flow_id[-1]}",
            )
        # Issue timestamps: ISS-1 earliest, ISS-2 middle, ISS-3 latest.
        _seed_issue_at(
            issues_ledger,
            "ISS-3",
            flow_refs=["FLOW-03"],
            source_file="specs/test/issues/3.md",
            timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
        _seed_issue_at(
            issues_ledger,
            "ISS-1",
            flow_refs=["FLOW-01"],
            source_file="specs/test/issues/1.md",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        _seed_issue_at(
            issues_ledger,
            "ISS-2",
            flow_refs=["FLOW-02"],
            source_file="specs/test/issues/2.md",
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        candidates = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
        )

        # Newest issue (ISS-3 → FLOW-03) first; oldest (ISS-1 → FLOW-01)
        # last.
        assert [c.flow_id for c in candidates] == [
            "FLOW-03",
            "FLOW-02",
            "FLOW-01",
        ]

    def test_unreferenced_flows_sort_last(self, tmp_path: Path) -> None:
        """Rows whose referencing issue is absent from the issues
        ledger (so ``last_referenced_by_issue_id`` is ``None``) sort
        after referenced ones, in flow_id ascending order."""
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02", "FLOW-03"])
        _emit_event(flows_ledger, flow_id="FLOW-01", event_type="FLOW_DISCOVERED")
        _emit_event(flows_ledger, flow_id="FLOW-02", event_type="FLOW_DISCOVERED")
        _emit_event(flows_ledger, flow_id="FLOW-03", event_type="FLOW_DISCOVERED")
        # FLOW-01: confirmation references an issue present in the
        # issues ledger.
        _emit_event(
            flows_ledger,
            flow_id="FLOW-01",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-001",
        )
        # FLOW-02 + FLOW-03: confirmations reference an issue that
        # is NOT in the issues ledger.  The event is well-formed
        # (event_issue_id is set) but the issue row's flow_refs
        # never names these flows, so ``last_referenced_by_issue_id``
        # is None at coverage time.
        _emit_event(
            flows_ledger,
            flow_id="FLOW-02",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-LOST",
        )
        _emit_event(
            flows_ledger,
            flow_id="FLOW-03",
            event_type="FLOW_CONFIRMED_IMPLEMENTED",
            issue_id="ISS-LOST",
        )
        _seed_issue(issues_ledger, "ISS-001", flow_refs=["FLOW-01"])

        candidates = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
        )

        # Referenced first, then unreferenced in flow_id ascending order.
        assert [c.flow_id for c in candidates] == [
            "FLOW-01",
            "FLOW-02",
            "FLOW-03",
        ]

    def test_empty_ledger_returns_empty(self, tmp_path: Path) -> None:
        flows_index = tmp_path / "index.md"
        flows_ledger = tmp_path / "flows.jsonl"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01", "FLOW-02"])
        # No events seeded — the flows_ledger does not exist.

        candidates = select_release_candidate_flows(
            flows_ledger=flows_ledger,
            flows_index=flows_index,
            issues_ledger=issues_ledger,
        )

        assert candidates == []

    def test_missing_ledger_returns_empty_not_raises(self, tmp_path: Path) -> None:
        """First-run state: flows ledger absent. Caller treats as State 2."""
        flows_index = tmp_path / "index.md"
        issues_ledger = tmp_path / "issues.jsonl"
        _write_index(flows_index, ["FLOW-01"])
        # flows_ledger intentionally not created.
        # issues_ledger intentionally not created.

        candidates = select_release_candidate_flows(
            flows_ledger=tmp_path / "flows.jsonl",
            flows_index=flows_index,
            issues_ledger=issues_ledger,
        )

        assert candidates == []
