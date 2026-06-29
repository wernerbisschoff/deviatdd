"""Parse ``/tome-classify`` markdown reports into structured rows.

A classification report (see ``src/deviate/prompts/commands/tome-classify.md``)
is a markdown document with three top-level sections: ``## Summary``,
``## Capabilities`` (a markdown table with seven columns), and
``## No-Touch List`` (a bullet list). This module extracts the
``## Capabilities`` table into ``CapabilityRow`` dataclasses that the
batch-write fan-out can consume.

The parser is pure: it takes a path (or string), returns a list of rows.
It does not invoke any agent, read the filesystem outside the report
file, or perform I/O beyond the single read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Canonical column count for the ## Capabilities table.
_EXPECTED_COLUMNS = 7

# Mapping of DocType value to the writer skill basename.
WRITER_SKILL_FOR_DOC_TYPE: dict[str, str] = {
    "tutorial": "tome-write-tutorial",
    "how-to": "tome-write-how-to",
    "reference": "tome-write-reference",
    "explanation": "tome-write-explanation",
}


@dataclass
class CapabilityRow:
    """One row from the ``## Capabilities`` table of a classification report.

    Attributes mirror the seven columns of the report schema
    (see ``<classification_report_schema>`` in ``tome-classify.md``).
    """

    capability: str
    evidence: str
    audience: str
    doc_type: str
    action: str
    target_file: str
    confidence: float


def parse_classification_report(report_path: Path) -> list[CapabilityRow]:
    """Parse a ``/tome-classify`` markdown report file into capability rows.

    Returns an empty list if the file has no ``## Capabilities`` section.
    Rows that fail to parse (wrong column count, malformed confidence)
    are silently skipped; the parser is best-effort.
    """
    return parse_classification_report_text(report_path.read_text(encoding="utf-8"))


def parse_classification_report_text(text: str) -> list[CapabilityRow]:
    """Parse the report text directly. Same semantics as the file variant."""
    lines = text.split("\n")
    in_capabilities = False
    in_table = False
    rows: list[CapabilityRow] = []

    for line in lines:
        stripped = line.strip()
        # Section detection: ## Capabilities starts the table block.
        if stripped.startswith("## Capabilities"):
            in_capabilities = True
            in_table = False
            continue
        if in_capabilities and stripped.startswith("## "):
            break  # Next section — done.
        if not in_capabilities:
            continue
        # First table row after ## Capabilities is the header.
        if not in_table:
            if stripped.startswith("| capability |"):
                in_table = True
            continue
        # In-table rows.
        if not stripped.startswith("|"):
            in_table = False
            continue
        if _is_separator_row(stripped):
            continue
        cells = _split_row(stripped)
        if len(cells) != _EXPECTED_COLUMNS:
            continue
        rows.append(
            CapabilityRow(
                capability=cells[0].strip(),
                evidence=cells[1].strip(),
                audience=cells[2].strip(),
                doc_type=cells[3].strip(),
                action=cells[4].strip(),
                target_file=_normalize_target_file(cells[5].strip()),
                confidence=_parse_confidence(cells[6].strip()),
            )
        )
    return rows


def filter_actionable_rows(
    rows: list[CapabilityRow],
    actions: set[str] | None = None,
) -> list[CapabilityRow]:
    """Return only rows whose ``action`` is in the given set.

    Defaults to ``{"create", "update"}`` — the actions a writer can
    act on. Rows with ``setup-required``, ``human-review``, or
    ``no-change`` are excluded by default.
    """
    if actions is None:
        actions = {"create", "update"}
    return [r for r in rows if r.action in actions]


def writer_skill_for(doc_type: str) -> str:
    """Map a ``doc_type`` value to the corresponding writer skill basename.

    Raises ``KeyError`` if ``doc_type`` is not one of the four Diátaxis
    quadrants — callers should treat that as a classification-report
    invariant violation.
    """
    return WRITER_SKILL_FOR_DOC_TYPE[doc_type]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|$")


def _is_separator_row(stripped: str) -> bool:
    """True for the ``|---|---|`` row in a markdown table."""
    return bool(_SEPARATOR_RE.match(stripped))


def _split_row(line: str) -> list[str]:
    """Split a markdown table row on unescaped pipes.

    Markdown escapes pipes inside cells as ``\\|``; we replace those
    with a placeholder, split, then restore. Strips the leading and
    trailing empty cells produced by the row's outer ``|``.
    """
    placeholder = "\x00PIPE\x00"
    line = line.replace("\\|", placeholder)
    cells = line.split("|")
    cells = [c.replace(placeholder, "|") for c in cells]
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return cells


def _normalize_target_file(value: str) -> str:
    """Normalize the ``target_file`` cell: ``null`` literal becomes empty."""
    if value.lower() == "null":
        return ""
    return value


def _parse_confidence(value: str) -> float:
    """Parse a confidence value like ``0.85``; default 0.0 on failure."""
    try:
        return float(value)
    except ValueError:
        return 0.0
