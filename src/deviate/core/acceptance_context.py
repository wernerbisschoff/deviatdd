"""Select task acceptance text without changing its source wording."""

from __future__ import annotations

import re

from deviate.core.validation import (
    _SCENARIO_PATTERN,
    _iter_scenario_bodies,
    extract_section_body,
)

_AO_TOKEN = re.compile(r"\bAO-\d{3}(?:-\d+)?\b")
_AO_ENTRY = re.compile(
    r"^[ \t]*(?:[-*]\s+|#{3,6}\s+|\|\s*)(?:\*\*|`)?"
    r"(?P<label>AO-\d{3}(?:-\d+)?)(?![\d-])",
    re.MULTILINE,
)


def _select_section(
    content: str,
    header: str,
    pattern: re.Pattern[str],
    tokens: list[str],
    *,
    legacy_body: bool = False,
) -> tuple[str, str]:
    body = extract_section_body(content, header)
    source = body if body is not None else content if legacy_body else ""
    entries: dict[str, list[str]] = {}
    for match, tail in _iter_scenario_bodies(source, pattern):
        token = match.group("label").removeprefix("Scenario ")
        entries.setdefault(token, []).append((match.group() + tail).rstrip())
    unresolved = [token for token in tokens if len(entries.get(token, [])) != 1]
    if unresolved:
        raise ValueError(f"{header}: missing or duplicate {', '.join(unresolved)}")
    selected = "\n\n".join(entries[token][0] for token in tokens)
    if body is None:
        return (selected if legacy_body else content), selected
    section = re.search(rf"^## {re.escape(header)}\s*$", content, re.MULTILINE)
    assert section is not None
    start = section.end()
    narrowed = content[:start] + "\n" + selected + "\n\n" + content[start + len(body) :]
    return narrowed, selected


def scope_acceptance_context(
    issue: str, plan: str, tokens: list[str]
) -> tuple[str, str]:
    """Keep assigned AC scenarios and linked AO entries; retain other sections."""
    if not tokens:
        return issue, plan
    plan, scenarios = _select_section(
        plan, "Acceptance Contract", _SCENARIO_PATTERN, tokens, legacy_body=True
    )
    outlines = list(
        dict.fromkeys(
            token
            for line in scenarios.splitlines()
            if "**Source Outline**:" in line
            for token in _AO_TOKEN.findall(line)
        )
    )
    issue, _ = _select_section(issue, "Acceptance Outline", _AO_ENTRY, outlines)
    return issue, plan
