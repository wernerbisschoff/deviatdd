"""Fail-to-pass pins: the Product layer is gone, not optional or tombstoned."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.commands import (
    OPTIONAL_PACKS,
    OPTIONAL_PACK_NAMES,
    UnknownPackError,
    classify_packaged_stems,
    parse_optional_packs,
)
from deviate.prompts.assembly import load_template
from deviate.state.ledger import AdhocRecord, IssueRecord

_PROMPTS = Path(__file__).resolve().parents[1] / "src" / "deviate" / "prompts"
_CONSTITUTION = Path(__file__).resolve().parents[1] / "specs" / "constitution.md"

runner = CliRunner()


class TestProductPackGone:
    def test_setup_has_no_product_pack(self) -> None:
        assert "product" not in OPTIONAL_PACKS
        assert "product" not in OPTIONAL_PACK_NAMES
        with pytest.raises(UnknownPackError, match="product"):
            parse_optional_packs("product")

    def test_product_triad_stems_are_not_packaged(self) -> None:
        stems = set(classify_packaged_stems())
        for stem in (
            "deviate-flows",
            "deviate-architecture",
            "deviate-release",
        ):
            assert stem not in stems
            assert not (_PROMPTS / "commands" / f"{stem}.md").exists()
            assert not (
                _PROMPTS / "auto" / f"{stem.removeprefix('deviate-')}.md"
            ).exists()

    def test_product_shared_prompt_is_gone(self) -> None:
        assert not (_PROMPTS / "core" / "product-shared.md").exists()


class TestFlowsCliGone:
    def test_cli_has_no_flows_group(self) -> None:
        result = runner.invoke(cli, ["flows", "--help"])
        assert result.exit_code != 0
        assert (
            "No such command" in result.output
            or "no such command" in result.output.lower()
        )

    def test_inspect_has_no_flows_coverage(self) -> None:
        result = runner.invoke(cli, ["inspect", "flows", "coverage"])
        assert result.exit_code != 0

    def test_flow_commands_module_is_gone(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("deviate.cli.flow_commands")


class TestFlowLedgerApiGone:
    def test_no_flow_models_or_seed_helpers(self) -> None:
        import deviate.state.ledger as ledger

        for name in (
            "FlowRecord",
            "FlowEvent",
            "FlowCoverage",
            "FlowIndexEmptyError",
            "FlowConfirmationResult",
            "seed_flow_ledger",
            "append_flow_record",
            "append_flow_event",
            "load_flow_coverage",
            "_confirm_implemented_flows",
            "select_release_candidate_flows",
        ):
            assert not hasattr(ledger, name), f"tombstone API left behind: {name}"

    def test_issue_record_has_no_flow_refs_field(self) -> None:
        assert "flow_refs" not in IssueRecord.model_fields
        assert "flow_refs" not in AdhocRecord.model_fields


class TestThreeLayersRemain:
    def test_constitution_says_three_layers(self) -> None:
        text = _CONSTITUTION.read_text(encoding="utf-8")
        assert "**Three-Layer Architecture**" in text
        assert "Macro" in text and "Meso" in text and "Micro" in text
        assert "Four-Layer Architecture" not in text.split("## 6. Version History")[0]
        protocol = text.split("## 2. Tech Stack")[0]
        assert "flows.jsonl" not in protocol
        database = text.split("## 2. Tech Stack")[1].split("## 3. Testing")[0]
        assert "flows.jsonl" not in database
        assert "Flow ledger" not in database

    def test_shard_still_writes_user_stories_and_atdd(self) -> None:
        shard = load_template("shard")
        assert "## User Stories Ledger" in shard
        assert "ATDD" in shard or "## ATDD Acceptance Criteria" in shard
        assert "flow_refs:" not in shard
        assert "product_specs_root" not in shard
        assert "FR-to-Flow" not in shard

    def test_red_encodes_issue_user_scenarios_as_failing_tests(self) -> None:
        red = load_template("red")
        lowered = red.lower()
        assert "user stories" in lowered
        assert "atdd" in lowered or "acceptance outline" in lowered
        assert "failing test" in lowered
        assert (
            "cannot edit tests" in lowered
            or "leave all `tests/` files untouched" in load_template("green").lower()
        )
        constitution = _CONSTITUTION.read_text(encoding="utf-8")
        assert "user scenarios" in constitution.lower()
        assert "User Stories" in constitution
