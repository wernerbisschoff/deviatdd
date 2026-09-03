"""Pins: the optional Product pack exists for greenfield scope tracking.

Covers the 0.11.0 reintroduction: `product` optional pack with the
flows/architecture/release slash commands, standalone `specs/_product/`
artifacts, and no machine-consumed `flow_refs` contract anywhere.
"""

from __future__ import annotations

from pathlib import Path

from deviate.core.commands import (
    OPTIONAL_PACKS,
    OPTIONAL_PACK_NAMES,
    classify_packaged_stems,
    commands_for_packs,
    parse_optional_packs,
)
from deviate.prompts.assembly import load_template
from deviate.state.ledger import AdhocRecord, IssueRecord

_PROMPTS = Path(__file__).resolve().parents[1] / "src" / "deviate" / "prompts"
_CONSTITUTION = Path(__file__).resolve().parents[1] / "specs" / "constitution.md"

_TRIAD = (
    "deviate-flows",
    "deviate-architecture",
    "deviate-release",
)


def _body(stem: str) -> str:
    return (_PROMPTS / "commands" / f"{stem}.md").read_text(encoding="utf-8")


class TestProductPackPresent:
    def test_setup_offers_product_pack(self) -> None:
        assert OPTIONAL_PACKS["product"] == _TRIAD
        assert "product" in OPTIONAL_PACK_NAMES
        assert parse_optional_packs("product") == ("product",)

    def test_product_triad_stems_are_packaged(self) -> None:
        assert set(commands_for_packs(("product",))) >= set(_TRIAD)
        unclassified = set(classify_packaged_stems())
        for stem in _TRIAD:
            assert stem not in unclassified
            assert (_PROMPTS / "commands" / f"{stem}.md").exists()

    def test_product_prompts_are_standalone(self) -> None:
        for stem in _TRIAD:
            body = _body(stem)
            assert "layer: product" in body
            assert "flow_refs:" not in body
            assert "inspect flows" not in body
            assert "flows sync" not in body
            for line in body.splitlines():
                if "flows.jsonl" in line or "flow_refs" in line:
                    assert "no " in line.lower(), line


class TestNoDownstreamFlowRefs:
    def test_no_flow_ledger_api(self) -> None:
        import deviate.state.ledger as ledger

        for name in (
            "FlowRecord",
            "FlowEvent",
            "FlowCoverage",
            "FlowIndexEmptyError",
            "seed_flow_ledger",
            "append_flow_record",
            "append_flow_event",
            "load_flow_coverage",
            "select_release_candidate_flows",
        ):
            assert not hasattr(ledger, name), f"flow ledger API present: {name}"

    def test_issue_record_has_no_flow_refs_field(self) -> None:
        assert "flow_refs" not in IssueRecord.model_fields
        assert "flow_refs" not in AdhocRecord.model_fields

    def test_shard_still_writes_user_stories_without_flow_refs(self) -> None:
        shard = load_template("shard")
        assert "## User Stories Ledger" in shard
        assert "flow_refs" not in shard
        assert "product_specs_root" not in shard

    def test_red_encodes_issue_user_scenarios_without_flows(self) -> None:
        red = load_template("red")
        lowered = red.lower()
        assert "user stories" in lowered
        assert "failing test" in lowered
        assert "flow_refs" not in lowered

    def test_no_downstream_template_mentions_flow_refs(self) -> None:
        for stem in ("plan", "tasks", "green", "judge"):
            assert "flow_refs" not in load_template(stem).lower()


class TestConstitutionRecordsOptionalProductLayer:
    def test_constitution_says_optional_product(self) -> None:
        text = _CONSTITUTION.read_text(encoding="utf-8")
        assert "Version: 0.11.0" in text
        assert "Optional Product Layer" in text
        assert "There is no Product layer" not in text
