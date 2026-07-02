---
title: "deviate inspect tasks"
description: "Reference for `deviate inspect tasks list` — flags, status filters, JSON output, and the project-root `tasks.jsonl` ledger."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: apps/docs/src/content/docs/reference/cli/inspect-issues.md
next: false
---

`deviate inspect tasks list` reads the project-root `tasks.jsonl` append-only ledger, deduplicates records (first-seen per `task_id` wins), filters by `--status`, and renders the parsed state as a Rich `Table` or a JSON array.

## Synopsis

```
deviate inspect tasks list [--status <status>] [--json] [--quiet]
```

## Flags

| Name | Type | Default | Description |
|---|---|---|---|
| `--status` | `string` | `null` | Filter rows by `TaskRecord.status` value (e.g., `PENDING`, `RED`, `GREEN`, `COMPLETED`). |
| `--json` | `bool` | `false` | Emit the parsed record array as JSON on stdout instead of rendering a Rich table. |
| `--quiet` | `bool` | `false` | Suppress all output; combine with `--json` for machine-readable logs, or alone to short-circuit the render path. |

## Task Statuses

Statuses are validated against the `TaskRecord.status` `Literal` in `src/deviate/state/ledger.py`. The CLI filter accepts any string but strict validation only permits these values.

| Status | Meaning |
|---|---|
| `PENDING` | Initial state; task registered in `tasks.jsonl` but not yet dispatched. |
| `RED` | TDD red phase committed; failing test authored. |
| `GREEN` | TDD green phase committed; failing test now passes. |
| `YELLOW` | Optional TDD yellow phase; awaiting operator approval. |
| `YELLOW_APPROVED` | Operator approved the yellow-phase artefact. |
| `YELLOW_REJECTED` | Operator rejected the yellow-phase artefact; task returns to active iteration. |
| `JUDGE` | JUDGE phase running isolated review of the green/yellow evidence. |
| `REFACTOR` | REFACTOR phase running cleanup on green/yellow-approved source. |
| `COMPLETED` | Terminal success state; all TDD phases passed. |
| `FAILED` | Terminal failure state; pipeline aborted. |

## Execution Modes

Modes are validated against `TaskRecord.execution_mode` `Literal` in `src/deviate/state/ledger.py`.

| Mode | Meaning |
|---|---|
| `TDD` | Default; task runs the full Red→Green→Yellow?→Judge→Refactor micro-cycle. |
| `DIRECT` | Single-shot task without TDD ceremony; commonly used for docs or scaffolding work. |
| `EXECUTE` | Pre-existing artefacts are committed directly without re-running phases. |
| `E2E` | End-to-end validation task; runs against a live or simulated system. |
| `IMMEDIATE` | Hotfix-style task that commits straight through without gate pauses. |

## Output Fields (JSON mode)

The `--json` flag emits a JSON array of `TaskRecord` objects.

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Canonical task identifier; regex `^TSK-\d{3}-\d{2}$` (e.g., `TSK-001-02`). |
| `issue_id` | `string` | Parent issue ID the task is bound to (e.g., `ISS-001-002`). |
| `description` | `string` | One-line task description; non-empty (`min_length=1`). |
| `status` | `string` | Current derived status; passed through `--status` filter. |
| `execution_mode` | `string` | Selected execution mode; see Execution Modes. |

## Ledger Source & Deduplication

The command reads `tasks.jsonl` at the **project root**, not from issue-scoped ledgers.

| Behaviour | Value |
|---|---|
| Source ledger | `<cwd>/tasks.jsonl` |
| Ledger semantics | Append-only; malformed JSONL raises `ValueError` via `_read_ledger_strict` |
| Deduplication | First-seen per `task_id` wins (opposite of `_deduplicate_issues`, which is latest-wins) |
| Sort key | `created_at` descending (`LedgerFilter.sort_by = "created_at"`, `sort_desc = True`) |
| Result window | Up to `LedgerFilter.limit = 20` rows from `offset = 0` |

## Examples

Render every `PENDING` task as a Rich table for an operator console:

```
deviate inspect tasks list --status PENDING
```

Pipe the same set as JSON for downstream tooling:

```
deviate inspect tasks list --status PENDING --json
```

## See Also

- [deviate inspect issues](./inspect-issues) — sibling command; reads `specs/issues.jsonl` and reports `ORPHAN_CLAIM` for `SPECIFIED` issues
- [How to run a DIRECT-mode task](/how-to/issue-execution/execute) — exercises the task lifecycle that `inspect tasks` reports on
- [Tutorial: a guided first run](/tutorials/starter-first-run) — see tasks appear in the ledger as you walk the pipeline
- [Starter architecture overview](/explanation/architecture/starter-architecture) — grounding for the macro/meso/micro layer split the task ledger records against