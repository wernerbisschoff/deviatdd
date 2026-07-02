---
title: "deviate tome list"
description: "Reference for `deviate tome list` — the table-or-JSON inspector for `/tome-classify` markdown reports, sourced from src/deviate/cli/tome.py."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: false
next: reference/tome/report-schema.md
---

`deviate tome list` parses a `/tome-classify` markdown report (via `src/deviate/tome/parser.py::parse_classification_report`) and prints each row as either a Rich `Table` or a JSON array; the command is defined at `src/deviate/cli/tome.py:221`.

## Synopsis

```
deviate tome list --from-report <path> [--json]
```

## Flags

| Name | Type | Default | Description |
|---|---|---|---|
| `--from-report` | `path` | (required) | Path to a `/tome-classify` markdown report; rejected by Typer when the file is missing or unreadable (`exists=True, readable=True`). |
| `--json` | `bool` | `false` | Emit a JSON array on stdout instead of rendering a Rich table. |

## Output Modes

| Mode | Shape | Notes |
|---|---|---|
| Table (default) | Rich `Table` titled `Classification Report — <name> (<n> rows)` | Columns: `Capability`, `DocType`, `Action`, `Confidence`, `Target`. Capability cells truncate to 60 chars with a trailing ellipsis; `Confidence` is right-justified at two decimals; `Target` renders `—` when `target_file` is empty. |
| `--json` | `json.dumps(..., indent=2)` on stdout | Each element mirrors the eleven `CapabilityRow` dataclass fields; the `target_file` cell is normalized so the literal `null` becomes `""`. |

## Action Styles (table mode)

Action cells are colorized via the per-action style mapping at `src/deviate/cli/tome.py:268-274`.

| Action | Color |
|---|---|
| `create` | green |
| `update` | yellow |
| `no-change` | dim |
| `human-review` | red |
| `setup-required` | red |
| (other) | white |

## Parsed Fields (table or JSON)

Columns and JSON keys are extracted from the eleven-column `## Capabilities` table. Older 7-column reports (pre-IA v1.2.0) are accepted but the four trailing IA fields fall back to their dataclass defaults.

| Field | Type | Source column | Notes |
|---|---|---|---|
| `capability` | `string` | 1 | User-facing capability identifier; truncated to 60 chars in the `Capability` column. |
| `evidence` | `string` | 2 | Verbatim file paths or commit anchors cited by the classifier; not rendered in table mode. |
| `audience` | `string` | 3 | One of `operator`, `contributor`, `developer`, `end-user`; not rendered in table mode. |
| `doc_type` | `string` | 4 | One of `tutorial`, `how-to`, `reference`, `explanation`; rendered as `DocType` (magenta). |
| `action` | `string` | 5 | One of `create`, `update`, `no-change`, `human-review`, `setup-required`; rendered as `Action` with the style above. |
| `target_file` | `string` | 6 | Resolved repo-relative path the writer would emit to; the literal `null` normalizes to `""`. Rendered as `Target` (or `—` when empty). |
| `confidence` | `float` | 7 | Decimal in `[0.0, 1.0]`; unparseable cells default to `0.0`. Rendered as `Confidence` (two decimals, right-justified). |
| `layer_order` | `int` | 8 | IA position within the row's `group`; unparseable cells default to `0`. JSON mode only. |
| `parent` | `string` | 9 | Repo-relative path of the prior page in the same group; the literal `null` normalizes to `""`. JSON mode only. |
| `next` | `string` | 10 | Repo-relative path of the next page in the same group; the literal `null` normalizes to `""`. JSON mode only. |
| `group` | `string` | 11 | ThemeGroup value (`cli`, `config`, `slash-commands`, `state-and-ledger`, `tome`, …); the literal `null` normalizes to `""`. JSON mode only. |

## Parser Source & Robustness

| Behaviour | Value |
|---|---|
| Parser entry point | `src/deviate/tome/parser.py::parse_classification_report(from_report)` |
| Source read | `from_report.read_text(encoding="utf-8")` |
| Empty `## Capabilities` | Returns `[]`; the table renders with `(0 rows)` in its title. |
| Missing `## Capabilities` section | Returns `[]`; the table renders with `(0 rows)`. |
| Malformed rows | Silently skipped — wrong column count (not 7 or 11) or unparseable `confidence` / `layer_order` cells. |
| `--from-report` not found | Typer rejects the path before invocation (`exists=True`). |
| `--from-report` unreadable | Typer rejects the path before invocation (`readable=True`). |

## Examples

Render every row of a freshly-classified report as a Rich table:

```
deviate tome list --from-report tome-report.md
```

Pipe the same set as JSON for downstream tooling:

```
deviate tome list --from-report tome-report.md --json
```

## See Also

- [Reference index](/reference/index) — quadrant navigation pivot for the `reference/tome/` family
- [Tutorial: a guided first run](/tutorials/starter-first-run) — exercises the pipeline that produces the reports `tome list` consumes
- [Starter architecture overview](/explanation/architecture/starter-architecture) — grounding for the macro/meso/micro layer split the Tome pipeline records against
