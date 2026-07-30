"""Tests for the `deviate flows sync` command — ownership of flows.jsonl creation."""

from __future__ import annotations

import json
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.ledger import FlowEvent, FlowRecord

runner = CliRunner()


def _write_flows_index(path: Path, flow_ids: list[str]) -> Path:
    index = path / "specs" / "_product" / "flows" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "| Flow ID | Name | Actor | Domain | Status | Source |",
        "|---------|------|-------|--------|--------|--------|",
    ]
    for flow_id in flow_ids:
        rows.append(
            f"| {flow_id} | Flow {flow_id} | Developer | Agent Integration "
            "| Active | specs/_product/flows/flows-streaming.md |"
        )
    index.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return index


def _flows_ledger_path(path: Path) -> Path:
    return path / "specs" / "_product" / "flows.jsonl"


def _read_ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


class TestFlowsSyncOwnership:
    """`deviate flows sync` is the sole owner of flows.jsonl creation."""

    def test_sync_seeds_identity_and_event_rows_from_index(
        self, tmp_path: Path
    ) -> None:
        _write_flows_index(tmp_path, ["FLOW-04", "FLOW-05"])

        with chdir(tmp_path):
            result = runner.invoke(cli, ["flows", "sync"])

        assert result.exit_code == 0, result.output

        ledger = _flows_ledger_path(tmp_path)
        assert ledger.exists()

        rows = _read_ledger_rows(ledger)
        flow_ids = {r["flow_id"] for r in rows if "event_type" not in r}
        event_types_by_flow: dict[str, set[str]] = {}
        for row in rows:
            if "event_type" in row:
                event_types_by_flow.setdefault(row["flow_id"], set()).add(
                    row["event_type"]
                )

        assert flow_ids == {"FLOW-04", "FLOW-05"}
        assert event_types_by_flow.get("FLOW-04") == {
            "FLOW_DISCOVERED",
            "FLOW_DOCUMENTED",
        }
        assert event_types_by_flow.get("FLOW-05") == {
            "FLOW_DISCOVERED",
            "FLOW_DOCUMENTED",
        }

    def test_sync_idempotent_on_repeat_invocations(self, tmp_path: Path) -> None:
        _write_flows_index(tmp_path, ["FLOW-04"])

        with chdir(tmp_path):
            first = runner.invoke(cli, ["flows", "sync"])
            assert first.exit_code == 0, first.output
            first_rows = _read_ledger_rows(_flows_ledger_path(tmp_path))

            second = runner.invoke(cli, ["flows", "sync"])
            assert second.exit_code == 0, second.output
            second_rows = _read_ledger_rows(_flows_ledger_path(tmp_path))

        assert first_rows == second_rows
        assert len(second_rows) == 3  # 1 identity + 2 events

    def test_sync_emits_no_rows_when_index_missing(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["flows", "sync"])

        assert result.exit_code != 0
        assert "FLOWS_INDEX_MISSING" in result.stderr
        assert not _flows_ledger_path(tmp_path).exists()

    def test_sync_records_carry_iso_timestamps_within_run(self, tmp_path: Path) -> None:
        _write_flows_index(tmp_path, ["FLOW-04"])

        before = datetime.now(timezone.utc)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["flows", "sync"])
        after = datetime.now(timezone.utc)

        assert result.exit_code == 0, result.output

        events = [
            r
            for r in _read_ledger_rows(_flows_ledger_path(tmp_path))
            if "event_type" in r
        ]
        assert len(events) == 2
        for event in events:
            ts = datetime.fromisoformat(event["timestamp"])
            assert ts.tzinfo is not None
            assert before <= ts <= after


class TestFlowsSyncRoundTrip:
    def test_seeded_rows_validate_against_pydantic_models(self, tmp_path: Path) -> None:
        _write_flows_index(tmp_path, ["FLOW-04", "FLOW-05"])

        with chdir(tmp_path):
            result = runner.invoke(cli, ["flows", "sync"])
        assert result.exit_code == 0, result.output

        for row in _read_ledger_rows(_flows_ledger_path(tmp_path)):
            if "event_type" in row:
                FlowEvent.model_validate(row)
            else:
                FlowRecord.model_validate(row)
