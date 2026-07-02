---
title: "Tome Classification Report Schema"
description: "Reference for the `/tome-classify` markdown report — section shape, the 11-column Capability row, DocType / Action / ThemeGroup enums, and parser robustness."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: reference/tome/tome-list.md
next: false
---

Reference for the `/tome-classify` classification report — the markdown contract emitted by C1 and consumed by C2-C5 writers via `src/deviate/tome/parser.py::parse_classification_report`.

## Report Sections

| Section | Required | Description |
|---|---|---|
| `# Classification Report — <sha-or-mode>` | yes | H1 carrying the source SHA or run-mode label that names the report. |
| `## Summary` | yes | One-paragraph change summary; plain text, no bullets or sub-headings. |
| `## Capabilities` | yes | Markdown table of capability rows; the parser accepts rows whose column count is 7 or 11. |
| `## No-Touch List` | yes | Bulleted list of files that must not be modified; C2-C5 surface these as `[REJECT]` triggers. |

## Capability Row Schema

11-column markdown table; legacy 7-column rows (pre-IA v1.2.0) are accepted and the four trailing IA fields fall back to dataclass defaults.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `capability` | `string` | yes | `""` | User-facing capability identifier; rendered as the `Capability` column in `deviate tome list` and truncated to 60 chars. |
| `evidence` | `string` | yes | `""` | Verbatim file paths or commit anchors cited by the classifier; typically `<specs/_product/*.md>:<line>:<line>` ranges. |
| `audience` | `enum` | yes | `""` | One of `user`, `operator`, `contributor`, `developer`, `internal`. |
| `doc_type` | `DocType` | yes | `""` | Quadrant selector — `tutorial`, `how-to`, `reference`, or `explanation`. Routes the row to one writer. |
| `action` | `Action` | yes | `""` | Writer intent — `create`, `update`, `no-change`, `human-review`, or `setup-required`. |
| `target_file` | `path` | yes | `""` | Repo-relative path the writer emits to; the literal `null` normalizes to `""`. May include a theme sub-dir. |
| `confidence` | `float` | yes | `0.0` | Classifier confidence in `[0.0, 1.0]`; unparseable cells default to `0.0`. |
| `layer_order` | `int` | no | `0` | IA position within the row's `group`; emitted by C1, consumed by C2-C5 and C6. |
| `parent` | `path\|null` | no | `null` | Prior page in the same `group`'s reading order; `null` for quadrant intros and the first page in a theme. |
| `next` | `path\|null` | no | `null` | Next page in the same `group`'s reading order; `null` for the last page in a theme. |
| `group` | `ThemeGroup\|null` | no | `null` | Theme sub-dir the writer targets; `null` when the capability does not map to a known theme. |

## DocType Values

| Value | Quadrant | Writer |
|---|---|---|
| `tutorial` | `tutorials/` | C2 tutorial writer |
| `how-to` | `how-to/` | C3 how-to writer |
| `reference` | `reference/` | C4 reference writer |
| `explanation` | `explanation/` | C5 explanation writer |

## Action Values

| Value | Writer Behavior |
|---|---|
| `create` | Write a new file at `target_file`. |
| `update` | Read the existing file at `target_file`, preserve valid tables, append or amend rows. |
| `no-change` | Skip the row; the surface is already accurate. |
| `human-review` | Halt and surface the row for human judgement. |
| `setup-required` | Halt and instruct the user to run `/tome-setup` (C7) before proceeding. |

## ThemeGroup Values

| Value | Sub-dir |
|---|---|
| `cli` | `reference/cli/`, `how-to/cli/`, etc. |
| `config` | `reference/config/`, `how-to/config/`, etc. |
| `slash-commands` | `reference/slash-commands/`, `how-to/slash-commands/`, etc. |
| `state-and-ledger` | `reference/state-and-ledger/`, `how-to/state-and-ledger/`, etc. |
| `tome` | `reference/tome/`, `how-to/tome/`, etc. |
| `null` | Capability does not map to a known theme; `target_file` is flat. |

## Parser Robustness

| Behaviour | Value |
|---|---|
| Entry point | `src/deviate/tome/parser.py::parse_classification_report(from_report)` |
| Encoding | `from_report.read_text(encoding="utf-8")` |
| Column count | `7` (legacy, pre-IA v1.2.0) or `11`; other counts silently skipped |
| Empty `## Capabilities` | Returns `[]` |
| Missing `## Capabilities` | Returns `[]` |
| Unparseable `confidence` | Defaults to `0.0` |
| Unparseable `layer_order` | Defaults to `0` |
| Literal `null` in `parent` / `next` / `group` | Normalizes to `""` in JSON output |

## Source Anchors

| Anchor | Content |
|---|---|
| `specs/_product/architecture.md:130-156` | C1 → C2-C5 contract — inlined schema, DocType / Action values, IA column semantics. |
| `specs/_product/domain-model.md:23-41` | `Capability` attributes and relationships; `layer_order` / `parent` / `next` / `group` semantics. |

## See Also

- [Reference index](/reference/index) — quadrant navigation pivot for the `reference/tome/` family
- [Tutorial: a guided first run](/tutorials/starter-first-run) — exercises the pipeline that produces classification reports
- [Explanation: starter architecture overview](/explanation/architecture/starter-architecture) — grounding for the macro/meso/micro layer split the Tome pipeline records against