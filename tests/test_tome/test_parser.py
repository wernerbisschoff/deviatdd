"""Tests for ``deviate.tome.parser``.

Covers the four canonical capabilities + the three robustness cases
(``null`` target, malformed confidence, escaped pipe inside a cell).
"""

from __future__ import annotations

from deviate.tome.parser import (
    WRITER_SKILL_FOR_DOC_TYPE,
    CapabilityRow,
    filter_actionable_rows,
    parse_classification_report_text,
    writer_skill_for,
)


# ---------------------------------------------------------------------------
# Sample reports
# ---------------------------------------------------------------------------


SAMPLE_REPORT = """# Classification Report — codebase:abc1234

**Status**: mixed

## Summary

First-run classification of a fictional repo.

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Setup workspace | `pyproject.toml:34`; `src/cli/__init__.py:600` | developer | how-to | create | apps/docs/src/content/docs/how-to/setup.md | 0.85 |
| CLI flags | `pyproject.toml:34` | developer | reference | create | apps/docs/src/content/docs/reference/flags.md | 0.80 |
| Architecture rationale | `specs/architecture.md:11` | developer | explanation | update | apps/docs/src/content/docs/explanation/arch.md | 0.75 |
| Pre-existing valid doc | `src/x.py:1` | developer | tutorial | update | apps/docs/src/content/docs/tutorials/pre-existing.md | 0.90 |
| Internal refactor | `src/internal.py:1` | developer | tutorial | no-change | apps/docs/src/content/docs/tutorials/internal.md | 0.95 |
| Setup required | — | developer | how-to | setup-required | null | 0.50 |
| Human review | `src/ambiguous.py` | developer | how-to | human-review | apps/docs/src/content/docs/how-to/ambiguous.md | 0.42 |

## No-Touch List
- apps/docs/src/content/docs/index.mdx
"""


SINGLE_ROW_REPORT = """# Classification Report — HEAD

**Status**: mixed

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Single row | `x.py:1` | developer | tutorial | create | apps/docs/src/content/docs/tutorials/single.md | 0.50 |
"""


EMPTY_REPORT = """# Classification Report — empty

**Status**: no-change

## Summary

No capabilities.

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|

## No-Touch List
"""


REPORT_WITH_ESCAPED_PIPE = """# Classification Report

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| One with escaped pipe | `x.py:1`; cell contains \\| inside | dev | how-to | create | apps/docs/h.md | 0.6 |
"""


# ---------------------------------------------------------------------------
# parse_classification_report_text
# ---------------------------------------------------------------------------


def test_parses_all_rows_in_order() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    assert len(rows) == 7
    assert [r.action for r in rows] == [
        "create",
        "create",
        "update",
        "update",
        "no-change",
        "setup-required",
        "human-review",
    ]


def test_parses_row_fields() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    first = rows[0]
    assert isinstance(first, CapabilityRow)
    assert first.capability == "Setup workspace"
    assert first.evidence == "`pyproject.toml:34`; `src/cli/__init__.py:600`"
    assert first.audience == "developer"
    assert first.doc_type == "how-to"
    assert first.action == "create"
    assert first.target_file == "apps/docs/src/content/docs/how-to/setup.md"
    assert first.confidence == 0.85


def test_normalizes_null_target_to_empty_string() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    setup_row = next(r for r in rows if r.action == "setup-required")
    assert setup_row.target_file == ""


def test_parses_single_row_report() -> None:
    rows = parse_classification_report_text(SINGLE_ROW_REPORT)
    assert len(rows) == 1
    assert rows[0].capability == "Single row"
    assert rows[0].confidence == 0.5


def test_empty_table_returns_no_rows() -> None:
    rows = parse_classification_report_text(EMPTY_REPORT)
    assert rows == []


def test_no_capabilities_section_returns_no_rows() -> None:
    text = "# Some Other Report\n\n## Summary\n\nNothing here.\n"
    assert parse_classification_report_text(text) == []


def test_handles_escaped_pipes_in_cells() -> None:
    rows = parse_classification_report_text(REPORT_WITH_ESCAPED_PIPE)
    assert len(rows) == 1
    assert rows[0].evidence == "`x.py:1`; cell contains | inside"


def test_skips_rows_with_wrong_column_count() -> None:
    text = """## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Short row | x.py | dev
| Full row | x.py | dev | how-to | create | apps/docs/h.md | 0.7 |
"""
    rows = parse_classification_report_text(text)
    # Only the 7-column row survives; the 3-column row is dropped.
    assert len(rows) == 1
    assert rows[0].capability == "Full row"


def test_malformed_confidence_defaults_to_zero() -> None:
    text = """## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Bad confidence | x.py | dev | how-to | create | apps/docs/h.md | not-a-number |
"""
    rows = parse_classification_report_text(text)
    assert rows[0].confidence == 0.0


def test_stops_at_next_section() -> None:
    # The parser should stop at ## No-Touch List, not include its content.
    text = """## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Real row | x.py | dev | how-to | create | apps/docs/h.md | 0.5 |

## No-Touch List
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Should be ignored | — | dev | how-to | create | apps/docs/x.md | 0.5 |
"""
    rows = parse_classification_report_text(text)
    assert len(rows) == 1
    assert rows[0].capability == "Real row"


# ---------------------------------------------------------------------------
# filter_actionable_rows
# ---------------------------------------------------------------------------


def test_filter_default_actions_returns_create_and_update() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    actionable = filter_actionable_rows(rows)
    assert len(actionable) == 4
    assert {r.action for r in actionable} == {"create", "update"}


def test_filter_custom_actions() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    only_creates = filter_actionable_rows(rows, actions={"create"})
    assert len(only_creates) == 2
    assert {r.action for r in only_creates} == {"create"}


def test_filter_empty_actions_returns_nothing() -> None:
    rows = parse_classification_report_text(SAMPLE_REPORT)
    assert filter_actionable_rows(rows, actions=set()) == []


# ---------------------------------------------------------------------------
# writer_skill_for
# ---------------------------------------------------------------------------


def test_writer_skill_for_known_doctypes() -> None:
    assert writer_skill_for("tutorial") == "tome-write-tutorial"
    assert writer_skill_for("how-to") == "tome-write-how-to"
    assert writer_skill_for("reference") == "tome-write-reference"
    assert writer_skill_for("explanation") == "tome-write-explanation"


def test_writer_skill_for_unknown_doctype_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        writer_skill_for("not-a-quadrant")


def test_writer_skill_map_is_complete() -> None:
    # Sanity: every Diátaxis quadrant has a writer skill mapping.
    assert set(WRITER_SKILL_FOR_DOC_TYPE) == {
        "tutorial",
        "how-to",
        "reference",
        "explanation",
    }
