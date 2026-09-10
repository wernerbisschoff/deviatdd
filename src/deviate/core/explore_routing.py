"""Parse Explore Status Summary routing for attach / new-epic / adhoc (ADH-060)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from deviate.core.validation import extract_section_body
from deviate.state.config import SessionState

ATTACH_EXISTING_EPIC = "attach_existing_epic"
NEW_EPIC = "new_epic"
ADHOC = "adhoc"
UNKNOWN = "unknown"

_ATTACH_RE = re.compile(
    r"(?:attach_existing_epic|attach_to_epic|ATTACH_TO_EPIC)"
    r"(?:\s*[`:]?\s*([A-Za-z0-9][\w.-]*))?",
    re.IGNORECASE,
)
_NEW_EPIC_RE = re.compile(
    r"\b(?:new_epic|NEW_EPIC|/deviate-research|deviate-research)\b",
    re.IGNORECASE,
)
_ADHOC_RE = re.compile(
    r"\b(?:adhoc|ADHOC|/deviate-adhoc|deviate-adhoc)\b",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"`?(\d{3}-[a-z0-9][a-z0-9-]*)`?", re.IGNORECASE)
_PENDING_RE = re.compile(r"^\s*pending\s*$", re.IGNORECASE)
_NONE_RE = re.compile(r"^\s*(?:none|-|)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ExploreRouting:
    next_action: str = UNKNOWN
    epic_slug: str = ""
    hitl_pending: bool = False
    source: str = "none"


def _table_rows(section: str | None) -> list[list[str]]:
    if not section:
        return []
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(cells)
    return rows


def _row_value(rows: list[list[str]], *keys: str) -> str:
    wanted = {k.lower().replace(" ", "_") for k in keys}
    for cells in rows:
        if len(cells) < 2:
            continue
        key = cells[0].lower().replace(" ", "_")
        if key in wanted:
            return cells[1]
    return ""


def _extract_slug(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        attach = _ATTACH_RE.search(text)
        if attach and attach.group(1):
            return attach.group(1).strip("`")
        slug = _SLUG_RE.search(text)
        if slug:
            return slug.group(1)
    return ""


def classify_routing_text(text: str) -> tuple[str, str]:
    """Return ``(next_action, epic_slug)`` for a Status / Scope Sizing cell."""
    if not text or _NONE_RE.match(text):
        return UNKNOWN, ""
    attach = _ATTACH_RE.search(text)
    if attach:
        slug = _extract_slug(text)
        if slug:
            return ATTACH_EXISTING_EPIC, slug
    has_new = bool(_NEW_EPIC_RE.search(text))
    has_adhoc = bool(_ADHOC_RE.search(text))
    if has_new and has_adhoc:
        return UNKNOWN, ""
    if has_new:
        return NEW_EPIC, ""
    if has_adhoc:
        return ADHOC, ""
    return UNKNOWN, ""


def _parse_pending_hitl(section: str | None) -> ExploreRouting | None:
    if not section:
        return None
    pending = False
    resolved: ExploreRouting | None = None
    for cells in _table_rows(section):
        if not cells:
            continue
        joined = " | ".join(cells)
        status = cells[-1].strip().strip("`") if cells else ""
        if status.upper() == "PENDING" or re.search(r"\|\s*PENDING\s*\|", joined):
            pending = True
            continue
        if status.upper() != "RESOLVED":
            continue
        recommendation = cells[-2] if len(cells) >= 2 else joined
        action, slug = classify_routing_text(recommendation)
        if action != UNKNOWN:
            resolved = ExploreRouting(
                next_action=action,
                epic_slug=slug or _extract_slug(joined),
                hitl_pending=False,
                source="pending_hitl",
            )
    if pending:
        return ExploreRouting(hitl_pending=True, source="pending_hitl")
    return resolved


def parse_explore_routing(content: str | None) -> ExploreRouting:
    """Read routing tokens from an explore.md body. Factual catalog only."""
    if not content or not content.strip():
        return ExploreRouting()

    status_rows = _table_rows(extract_section_body(content, "Status Summary"))
    sizing_rows = _table_rows(extract_section_body(content, "Scope Sizing"))
    hitl_section = extract_section_body(content, "Pending HITL Decisions")

    hitl_value = _row_value(status_rows, "HITL_OVERRIDE", "HITL")
    next_value = _row_value(status_rows, "NEXT_ACTION")
    attach_field = _row_value(status_rows, "ATTACH_EPIC", "ATTACH_EPIC_SLUG")
    sizing_value = _row_value(
        sizing_rows, "Related Epic Attach", "Related_Epic_Attach", "Routing"
    )

    if hitl_value and _PENDING_RE.match(hitl_value):
        action, slug = classify_routing_text(next_value)
        return ExploreRouting(
            next_action=action,
            epic_slug=slug or attach_field or _extract_slug(next_value),
            hitl_pending=True,
            source="hitl_override",
        )

    if hitl_value and not _NONE_RE.match(hitl_value):
        action, slug = classify_routing_text(hitl_value)
        if action != UNKNOWN:
            return ExploreRouting(
                next_action=action,
                epic_slug=slug or attach_field or _extract_slug(hitl_value),
                source="hitl_override",
            )

    table_hitl = _parse_pending_hitl(hitl_section)
    if table_hitl is not None:
        if table_hitl.hitl_pending:
            action, slug = classify_routing_text(next_value)
            return ExploreRouting(
                next_action=action,
                epic_slug=slug or attach_field or table_hitl.epic_slug,
                hitl_pending=True,
                source="pending_hitl",
            )
        return table_hitl

    for source, text in (
        ("next_action", next_value),
        ("scope_sizing", sizing_value),
    ):
        action, slug = classify_routing_text(text)
        if action != UNKNOWN:
            return ExploreRouting(
                next_action=action,
                epic_slug=slug or attach_field or _extract_slug(text),
                source=source,
            )

    if attach_field:
        return ExploreRouting(
            next_action=ATTACH_EXISTING_EPIC,
            epic_slug=attach_field,
            source="attach_epic",
        )
    return ExploreRouting()


def resolve_explore_routing(
    *,
    content: str | None = None,
    session: SessionState | None = None,
) -> ExploreRouting:
    """Prefer the explore.md text (human-editable); fall back to session."""
    parsed = parse_explore_routing(content)
    if parsed.next_action != UNKNOWN or parsed.hitl_pending:
        return parsed
    if session and session.explore_next_action:
        return ExploreRouting(
            next_action=session.explore_next_action,
            epic_slug=session.attach_epic_slug,
            hitl_pending=session.explore_hitl_pending,
            source="session",
        )
    return parsed


def apply_routing_to_session(session: SessionState, routing: ExploreRouting) -> None:
    session.explore_next_action = (
        routing.next_action if routing.next_action != UNKNOWN else ""
    )
    session.attach_epic_slug = routing.epic_slug
    session.explore_hitl_pending = routing.hitl_pending


def latest_explore_content(specs_root: Path | None = None) -> str | None:
    root = specs_root or Path("specs")
    explore_dir = root / "explore"
    if not explore_dir.is_dir():
        return None
    files = sorted(explore_dir.glob("*.md"))
    if not files:
        return None
    return files[-1].read_text(encoding="utf-8")
