---
title: "Issues JSONL Schema"
description: "Reference for the append-only specs/issues.jsonl ledger: the IssueRecord Pydantic model, status transitions, idempotency keys, and helper API."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues:
  - ISS-001-002
prev: false
next: state-and-ledger/tasks-jsonl.md
---

`specs/issues.jsonl` is the append-only ledger that records every macro-layer issue and every status transition issued by `deviate` (research → PRD → shard → specify → completion). Each non-empty line is one JSON object validated against the `IssueRecord` Pydantic model in `src/deviate/state/ledger.py`; the public read/claim helpers live in `src/deviate/core/issues.py`.

## File location

| Path | Owner | Write mode |
|---|---|---|
| `<repo>/specs/issues.jsonl` | `deviate` macro-layer commands | Append-only JSONL; new entries are written via `append_issue_record()` or `append_issue_transition()` and idempotency is checked before each write |

The default location resolves through `_resolve_ledger()` at `src/deviate/core/issues.py:9`, which returns `Path("specs/issues.jsonl")` when no explicit path is supplied. Parent directories are created on first append.

## IssueRecord fields

| Field | Type | Default | Description |
|---|---|---|---|
| `issue_id` | `string` | (required) | Unique issue identifier; also the idempotency key for `append_issue_record()` |
| `type` | `string` | (required) | Issue category (e.g., `feature`, `adhoc`, `bug`); `_get_unblocked_backlog_features()` filters out records where `type` is `null` |
| `title` | `string` | (required) | Human-readable title; rejected by Pydantic when empty (`min_length=1`) |
| `status` | `enum` | `"DRAFT"` | Lifecycle state — see the Status enum table below |
| `source_file` | `string` | (required) | Repository-relative path to the originating issue markdown, e.g., `specs/001-deviate-cli-python/issues/008-meso-macro-automated-orchestration.md` |
| `blocked_by` | `list[string]` | `[]` | Ordered list of upstream `issue_id` values that must reach `COMPLETED` before this issue becomes selectable; evaluated by `_get_unblocked_backlog_features()` |
| `coordinates_with` | `list[string]` | `[]` | Soft dependencies (peer issues that should land in the same release) — informational only |
| `timestamp` | `datetime` | (required) | Wall-clock time the entry was written; updated on every status transition |
| `created_at` | `datetime` | `datetime.now(timezone.utc)` | First-write timestamp; preserved across status transitions by `model_copy(update=...)` |
| `flow_refs` | `list[string]` | `[]` | Optional FLOW identifiers (e.g., `FLOW-04`, `FLOW-07`) that anchor the issue to product flows under `specs/_product/flows/` |

`IssueRecord` is configured with `model_config = {"extra": "forbid"}` — any unknown key in a JSONL line fails Pydantic validation and the line is skipped with a `warnings.warn()` from `_read_ledger()` (strict mode via `_read_ledger_strict()` raises `ValueError` instead).

## Status enum

`status` is a `Literal[...]` field. Transitions are appended as separate JSONL lines; the canonical "latest" state for an issue is the *last* entry matching its `issue_id` when read top-to-bottom.

| Value | Meaning | Set by |
|---|---|---|
| `DRAFT` | Initial issue seed before entering the backlog | `IssueRecord` default |
| `BACKLOG` | Visible to the select loop; only `BACKLOG` issues are candidates for `select_next_unblocked_issue()` | Pre-specify writes |
| `SPECIFIED` | A specify command has claimed the issue | `claim_issue()` in `src/deviate/core/issues.py:17` sets `status="SPECIFIED"` and re-stamps `timestamp` |
| `SHARDED` | The issue has been decomposed into a per-feature `tasks.jsonl` | Shard-phase writes |
| `COMPLETED` | Terminal state — entry exists in the ledger as a status line with only `issue_id`, `status: "COMPLETED"`, and `timestamp` | Completion append |

## Idempotency keys

Append functions read the existing file, compare each new record against prior entries, and refuse to write a duplicate.

| Function | Idempotency key | Behaviour |
|---|---|---|
| `append_issue_record(record, ledger_path)` | `issue_id` | Refuses to rewrite a record with the same `issue_id` — returns `False` |
| `append_issue_transition(record, ledger_path)` | `(issue_id, status)` tuple | Multiple transitions for one issue are all recorded; re-running the same transition is a no-op — returns `False` |
| `append_task_record(record, ledger_path)` | `id` | Refuses to rewrite a task with the same `id` — returns `False` |
| `append_task_transition(record, ledger_path)` | `(id, status)` tuple | Same compound-key rule as `append_issue_transition()` |

On POSIX filesystems all four helpers acquire an exclusive `fcntl.flock` around the read-then-write window (`HAS_FCNTL` guards the import); on non-POSIX systems the lock is skipped and concurrency safety degrades to single-process semantics.

## Helper API

The wrapping helpers used by every macro-layer command live in `src/deviate/core/issues.py`. They accept an optional `ledger_path` that overrides the default of `specs/issues.jsonl`.

| Function | Returns | Purpose |
|---|---|---|
| `resolve_issue(issue_id, ledger_path=None)` | `IssueRecord | None` | Returns the *latest* validated `IssueRecord` for `issue_id` (walks `_read_ledger()` in reverse) or `None` if not found |
| `claim_issue(issue_id, ledger_path=None)` | `bool` | Appends a `SPECIFIED` transition entry for `issue_id`; returns `False` when the issue is missing |
| `read_issue_body(issue_id, ledger_path=None)` | `string` | Pretty-printed `model_dump_json(indent=2)` of the resolved record; returns `""` when missing |
| `is_issue_completed(issue_id, ledger_path=None)` | `bool` | `True` when the resolved record's latest `status` is `"COMPLETED"` |
| `select_next_unblocked_issue(ledger_path)` | `IssueRecord | None` | Oldest unblocked `BACKLOG` issue (single candidate); used by the specify pre command |
| `select_unblocked_candidates(ledger_path)` | `list[IssueRecord]` | All unblocked `BACKLOG` issues, sorted oldest-first; multi-candidate variant for the try-claim loop |

## Example record

A complete, currently-valid `specs/issues.jsonl` line:

```json
{"issue_id": "ISS-001-008", "type": "feature", "title": "[FR-008] Meso/Macro Automated Orchestration Layer", "status": "COMPLETED", "source_file": "specs/001-deviate-cli-python/issues/008-meso-macro-automated-orchestration.md", "blocked_by": [], "coordinates_with": [], "timestamp": "2026-06-14T16:32:10Z", "created_at": "2026-06-14T12:31:20.443625Z"}
```

A minimal completion-only transition line (terminal append with no body fields):

```json
{"issue_id": "ISS-002-004", "status": "COMPLETED", "timestamp": "2026-06-15T16:40:05Z"}
```

## Validation rules

| Rule | Source | Failure mode |
|---|---|---|
| `extra` keys forbidden on every line | `IssueRecord.model_config = {"extra": "forbid"}` at `src/deviate/state/ledger.py:37` | Pydantic raises `ValidationError`; `_read_ledger()` warns and skips, `_read_ledger_strict()` raises `ValueError` |
| `title` must be non-empty | `Field(min_length=1)` at `src/deviate/state/ledger.py:28` | Pydantic raises `ValidationError` |
| JSON lines must parse | `json.loads()` in `_read_ledger()` / `_read_ledger_strict()` | Same skip-or-raise split as the `extra` rule above |
| `type` required for selection | `_get_unblocked_backlog_features()` filters via `r.get("type") is not None` | Records with `type: null` never appear as backlog candidates |

## See Also

- [Tasks JSONL Schema](./tasks-jsonl) — sibling reference for `specs/**/tasks.jsonl` (`TaskRecord`, `execution_mode`, `id` validator `^TSK-\d{3}-\d{2}$`)
- [How to read the DeviaTDD ledgers](/how-to/inspect-the-ledger) — procedural walk-through of `resolve_issue_record`, `filter_tasks`, and the `LedgerFilter` model
- [Why the ledgers are append-only](/explanation/append-only-ledgers) — rationale for the read-append-read-before-write idempotency pattern
