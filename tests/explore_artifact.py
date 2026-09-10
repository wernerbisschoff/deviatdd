"""Shared explore.md bodies for attach-routing tests (GH-221 / ADH-060)."""

from __future__ import annotations

EXPLORE_SECTIONS = [
    "Problem Definition",
    "Discovery Audit Results",
    "Constitution Quotes",
    "Architectural Baselines",
    "Related Epic Candidates",
    "Ecosystem Research",
    "File Registry",
    "Status Summary",
]


def render_explore_md(
    *,
    next_action: str = (
        "Run `/deviate-adhoc` (Low/Medium complexity) or "
        "`/deviate-research` (High complexity) — see `## Scope Sizing`"
    ),
    candidates: str = "None observed",
    hitl_override: str = "none",
    attach_epic: str = "",
    extra_sections: str = "",
) -> str:
    parts: list[str] = []
    for section in EXPLORE_SECTIONS:
        if section == "Related Epic Candidates":
            body = candidates
        elif section == "Status Summary":
            body = (
                "| Metric | Value |\n"
                "| :--- | :--- |\n"
                "| STATUS | SUCCESS |\n"
                f"| NEXT_ACTION | {next_action} |\n"
                f"| ATTACH_EPIC | {attach_epic} |\n"
                f"| HITL_OVERRIDE | {hitl_override} |\n"
            )
        else:
            body = "substance"
        parts.append(f"## {section}\n\n{body}\n")
    if extra_sections:
        parts.append(extra_sections)
    return "\n".join(parts)
