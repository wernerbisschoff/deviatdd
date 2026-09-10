from __future__ import annotations

from pathlib import Path

from deviate.core.explore_routing import (
    ADHOC,
    ATTACH_EXISTING_EPIC,
    NEW_EPIC,
    UNKNOWN,
    parse_explore_routing,
    resolve_explore_routing,
)
from deviate.core.validation import ARTIFACT_VALIDATORS, validate_artifact
from deviate.state.config import SessionState

from tests.explore_artifact import render_explore_md


class TestRelatedEpicCandidatesValidator:
    def test_related_epic_candidates_is_required(self) -> None:
        assert "Related Epic Candidates" in ARTIFACT_VALIDATORS["explore"]

    def test_missing_candidates_section_fails_validation(self) -> None:
        content = render_explore_md()
        content = content.replace(
            "## Related Epic Candidates\n\nNone observed\n",
            "",
        )
        result = validate_artifact(content, "explore")
        assert result.passed is False
        assert any("Related Epic Candidates" in err for err in result.errors)

    def test_none_observed_candidates_passes(self) -> None:
        result = validate_artifact(render_explore_md(), "explore")
        assert result.passed is True


class TestParseExploreRouting:
    def test_next_action_attach_with_slug(self) -> None:
        content = render_explore_md(
            next_action="attach_existing_epic `006-setup-interactive-config`",
            attach_epic="006-setup-interactive-config",
            candidates=(
                "| Path | Title | Evidence |\n"
                "| :--- | :--- | :--- |\n"
                "| specs/006-setup-interactive-config/ | setup | "
                '"interactive config" in `prd.md` |\n'
            ),
        )
        routing = parse_explore_routing(content)
        assert routing.next_action == ATTACH_EXISTING_EPIC
        assert routing.epic_slug == "006-setup-interactive-config"
        assert routing.hitl_pending is False

    def test_next_action_new_epic(self) -> None:
        routing = parse_explore_routing(render_explore_md(next_action="new_epic"))
        assert routing.next_action == NEW_EPIC
        assert routing.epic_slug == ""

    def test_next_action_adhoc(self) -> None:
        routing = parse_explore_routing(
            render_explore_md(next_action="adhoc — `/deviate-adhoc`")
        )
        assert routing.next_action == ADHOC

    def test_legacy_dual_next_action_stays_unknown(self) -> None:
        routing = parse_explore_routing(render_explore_md())
        assert routing.next_action == UNKNOWN

    def test_hitl_override_wins_over_next_action(self) -> None:
        content = render_explore_md(
            next_action="new_epic",
            hitl_override="attach_existing_epic 002-deviatdd-gap-analysis",
        )
        routing = parse_explore_routing(content)
        assert routing.next_action == ATTACH_EXISTING_EPIC
        assert routing.epic_slug == "002-deviatdd-gap-analysis"
        assert routing.source == "hitl_override"

    def test_hitl_override_pending(self) -> None:
        routing = parse_explore_routing(
            render_explore_md(next_action="adhoc", hitl_override="pending")
        )
        assert routing.hitl_pending is True

    def test_pending_hitl_table_row(self) -> None:
        extra = (
            "## Pending HITL Decisions\n\n"
            "| ID | Question | Context | Alternatives | Recommendation | Status |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| `HITL-001` | Attach or new epic? | overlap with 006 | "
            "attach / new_epic / adhoc | attach_existing_epic 006-foo | PENDING |\n"
        )
        routing = parse_explore_routing(render_explore_md(extra_sections=extra))
        assert routing.hitl_pending is True

    def test_resolved_hitl_table_row_overrides(self) -> None:
        extra = (
            "## Pending HITL Decisions\n\n"
            "| ID | Question | Context | Alternatives | Recommendation | Status |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| `HITL-001` | Attach or new epic? | overlap | "
            "attach / new_epic | attach_existing_epic 006-foo | RESOLVED |\n"
        )
        routing = parse_explore_routing(
            render_explore_md(next_action="new_epic", extra_sections=extra)
        )
        assert routing.next_action == ATTACH_EXISTING_EPIC
        assert routing.epic_slug == "006-foo"
        assert routing.hitl_pending is False


class TestResolveExploreRouting:
    def test_parsed_content_wins_over_session(self) -> None:
        session = SessionState(
            current_phase="EXPLORE",
            explore_next_action=NEW_EPIC,
            attach_epic_slug="",
        )
        routing = resolve_explore_routing(
            content=render_explore_md(
                next_action="attach_existing_epic 006-foo",
                attach_epic="006-foo",
            ),
            session=session,
        )
        assert routing.next_action == ATTACH_EXISTING_EPIC
        assert routing.epic_slug == "006-foo"

    def test_session_fallback_when_content_unknown(self) -> None:
        session = SessionState(
            current_phase="EXPLORE",
            explore_next_action=ATTACH_EXISTING_EPIC,
            attach_epic_slug="006-foo",
        )
        routing = resolve_explore_routing(content=render_explore_md(), session=session)
        assert routing.next_action == ATTACH_EXISTING_EPIC
        assert routing.epic_slug == "006-foo"
        assert routing.source == "session"

    def test_empty_inputs_are_unknown(self) -> None:
        routing = resolve_explore_routing(content=None, session=None)
        assert routing.next_action == UNKNOWN


def test_session_fields_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    original = SessionState(
        current_phase="EXPLORE",
        explore_next_action=ATTACH_EXISTING_EPIC,
        attach_epic_slug="006-foo",
        explore_hitl_pending=True,
    )
    original.save(path)
    loaded = SessionState.load(path)
    assert loaded.explore_next_action == ATTACH_EXISTING_EPIC
    assert loaded.attach_epic_slug == "006-foo"
    assert loaded.explore_hitl_pending is True
