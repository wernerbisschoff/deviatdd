"""GH-139: scope-minimization and cross-artifact consistency gates.

Pins the canonical auto prompts (and the derived manuals they feed) for
floor / bracket research, explore sibling-flow inventory, and PRD halt
tokens. Fixtures encode the parallel-withdrawal case from #139; they are
not snapshot dumps of the whole prompt.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deviate.core.commands import install_command
from deviate.prompts.assembly import load_template

_REPO = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO / "tests" / "fixtures" / "scope_gates"
_AUTO = _REPO / "src" / "deviate" / "prompts" / "auto"

_REQUIRED_EVIDENCE_KEYS = (
    "requested_user_flow",
    "existing_behavior_compatibility",
    "constitution",
    "auth_money_provider_integrity",
)

_FLOOR_EXTRAS = (
    "generic_payload_snapshot",
    "future_adapter",
    "metric",
    "alert",
    "circuit_breaker",
)

_REQUIRED_MECHANISMS = (
    "authorization",
    "ownership",
    "amount + fee",
    "reserve",
    "consume",
    "release",
    "skip_locked",
    "one vendor create",
    "UNKNOWN",
    "typed destination snapshot",
)


def _read_auto(name: str) -> str:
    return (_AUTO / name).read_text(encoding="utf-8")


def _load_bracket() -> dict:
    return yaml.safe_load((_FIXTURES / "floor_bracket_items.yaml").read_text())


def _classify_scope(evidence: dict) -> str:
    """Mirror the research floor test: Required iff one of the four keys is true."""
    if any(evidence.get(key) for key in _REQUIRED_EVIDENCE_KEYS):
        return "Required"
    return "not-Required"


class TestExploreSiblingFlowInventory:
    def test_explore_stays_factual_and_inventories_siblings(self) -> None:
        text = _read_auto("explore.md")
        assert "## Sibling Flow Inventory" in text
        assert "amount vs fee" in text.lower() or "amount + fee" in text
        assert "lock vs reserve" in text
        assert "vendor call" in text.lower()
        assert "idempotency" in text.lower()
        assert "destination shape" in text.lower()
        assert "Do not recommend" in text
        assert "Quote paths" in text or "quote paths" in text.lower()

    def test_ecosystem_rows_are_catalog_not_required(self) -> None:
        text = _read_auto("explore.md")
        assert "catalog only" in text.lower()
        assert "Required" in text
        research = _read_auto("research.md")
        assert "Ecosystem Research" in research
        assert "catalog only" in research.lower()


class TestResearchFloorAndSingleAgent:
    def test_parallel_withdrawal_fixture_preserves_separate_fee(self) -> None:
        inventory = (_FIXTURES / "sibling_withdrawal_inventory.md").read_text()
        assert "payout_request" in inventory
        assert "amount + fee" in inventory
        assert "src/wallet/models/payout.py" in inventory

        bracket = _load_bracket()
        assert bracket["sibling_flow"]["amount_vs_fee"] == "amount + fee"
        fee = next(item for item in bracket["items"] if item["id"] == "fee")
        assert _classify_scope(fee["evidence"]) == "Required"
        assert fee["on_floor"] is True
        assert fee["on_schema"] is True

        research = _read_auto("research.md")
        assert "amount + fee" in research
        assert "sibling" in research.lower()
        assert (
            "Floor includes a separate `fee` field when the sibling-flow "
            "inventory records an `amount + fee` convention."
        ) in research

    def test_unsupported_extras_stay_off_floor_and_schema(self) -> None:
        bracket = _load_bracket()
        by_id = {item["id"]: item for item in bracket["items"]}
        for extra_id in _FLOOR_EXTRAS:
            item = by_id[extra_id]
            assert _classify_scope(item["evidence"]) == "not-Required"
            assert item["on_floor"] is False
            assert item["on_schema"] is False

        research = _read_auto("research.md")
        assert (
            "Do not add an unsupported generic payload snapshot, future "
            "adapter, metric, alert, or circuit breaker to the floor or "
            "to Schema Tables."
        ) in research
        assert "Schema Tables = floor only" in research

    def test_gamma_job_labels_each_extra_with_scope_status(self) -> None:
        research = _read_auto("research.md")
        assert "Required" in research
        assert "Recommended" in research
        assert "Deferred" in research
        assert "Open Decision" in research
        assert "Scope Status" in research
        assert "job_attack" in research
        assert "generate at least one contrarian" not in research.lower()
        assert "quota" in research.lower()

    def test_research_does_not_spawn_or_forward_between_agents(self) -> None:
        research = _read_auto("research.md")
        assert "<subagent_alphabeta_prompt>" not in research
        assert "<subagent_gamma_prompt>" not in research
        assert "dispatch two sequential subagent" not in research
        assert "Each subagent receives a context bundle" not in research
        assert "map_phase_sequential_fork" not in research
        assert "one agent, two ordered jobs" in research.lower()
        assert "same prompt" in research.lower()
        assert "no spawn" in research.lower()
        assert "do not forward" in research.lower()
        assert "forward the full" not in research.lower()

    def test_populate_constitution_gated_on_greenfield(self) -> None:
        research = _read_auto("research.md")
        assert "populate_constitution" in research
        assert "is_greenfield" in research
        assert "read-only" in research.lower()
        assert (
            "must not rewrite" in research.lower()
            or "do not rewrite" in research.lower()
        )
        assert "explicit" in research.lower() and "amendment" in research.lower()
        assert "TBD" in research

    def test_required_concurrency_mechanisms_remain(self) -> None:
        research = _read_auto("research.md")
        prd = _read_auto("prd.md")
        combined = f"{research}\n{prd}"
        for token in _REQUIRED_MECHANISMS:
            assert token in combined, f"missing required mechanism {token!r}"
        assert "skip_locked" in research
        assert "reserve" in research and "consume" in research and "release" in research


class TestPrdScopeGates:
    def test_prd_halts_on_upstream_disagreement(self) -> None:
        prd = _read_auto("prd.md")
        assert "UPSTREAM_INCONSISTENT" in prd
        assert "design.md" in prd and "data-model.md" in prd
        assert "field, state, or storage type" in prd
        assert "Do not invent a third money definition" in prd

    def test_prd_rejects_required_item_without_upstream_source(self) -> None:
        prd = _read_auto("prd.md")
        assert "SCOPE_DRIFT" in prd
        assert "approved upstream" in prd.lower() or "upstream Required" in prd

    def test_prd_does_not_promote_recommended_or_deferred(self) -> None:
        prd = _read_auto("prd.md")
        assert "Do not promote `Recommended` or `Deferred`" in prd
        assert "Out-of-Scope Boundaries" in prd
        assert (
            "Every mechanism selected for the approved architecture must "
            "have a tracking match. Unselected mitigations remain out of scope."
        ) in prd
        assert (
            "Every functional mechanism, guardrail, or operational exception" not in prd
        )

    def test_prd_keeps_required_correctness_mechanisms(self) -> None:
        prd = _read_auto("prd.md")
        for token in (
            "authorization",
            "amount + fee",
            "reserve",
            "skip_locked",
            "one vendor create",
            "UNKNOWN",
            "typed destination snapshot",
        ):
            assert token in prd, f"PRD dropped required mechanism {token!r}"


class TestAutoPromptsCanonicalForDerivedManuals:
    def test_derived_research_and_prd_pick_up_gates(self, tmp_path: Path) -> None:
        target = tmp_path / "agent" / "commands"
        for name in ("deviate-explore", "deviate-research", "deviate-prd"):
            assert install_command(name, target) is True

        research = (target / "deviate-research.md").read_text(encoding="utf-8")
        prd = (target / "deviate-prd.md").read_text(encoding="utf-8")
        explore = (target / "deviate-explore.md").read_text(encoding="utf-8")

        assert _read_auto("research.md") in research
        assert _read_auto("prd.md") in prd
        assert _read_auto("explore.md") in explore
        assert "<subagent_alphabeta_prompt>" not in research
        assert "UPSTREAM_INCONSISTENT" in prd
        assert "SCOPE_DRIFT" in prd
        assert "## Sibling Flow Inventory" in explore
        assert research.count("$ARGUMENTS") == 1
        assert prd.count("$ARGUMENTS") == 1
        assert explore.count("$ARGUMENTS") == 1
        assert research.rfind("$ARGUMENTS") > research.rfind("<system_instructions>")

    def test_composed_auto_templates_carry_gates(self) -> None:
        research = load_template("research")
        prd = load_template("prd")
        explore = load_template("explore")
        assert "one agent, two ordered jobs" in research.lower()
        assert "UPSTREAM_INCONSISTENT" in prd
        assert "## Sibling Flow Inventory" in explore


class TestScopeGateFixtureIntegrity:
    def test_fixture_items_align_with_classifier(self) -> None:
        bracket = _load_bracket()
        for item in bracket["items"]:
            classified = _classify_scope(item["evidence"])
            if item["expected_scope"] == "Required":
                assert classified == "Required"
                assert item["on_floor"] is True
            else:
                assert classified == "not-Required"
                assert item["on_floor"] is False
                assert item["on_schema"] is False

    def test_research_prompt_names_the_four_required_conditions(self) -> None:
        research = _read_auto("research.md")
        assert "requested user flow" in research.lower()
        assert "existing behavior compatibility" in research.lower()
        assert "constitution" in research.lower()
        assert "authorization" in research.lower()
        assert "money safety" in research.lower() or "money" in research.lower()
        assert "provider" in research.lower()
        assert "data integrity" in research.lower()
