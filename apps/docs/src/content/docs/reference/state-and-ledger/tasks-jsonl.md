---
title: "Tasks JSONL Schema"
description: "Reference for the append-only specs/**/tasks.jsonl ledger: the TaskRecord Pydantic model, execution modes, status state machine, and markdown-to-JSONL parser."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues:
  - ISS-001-003
  - ISS-001-004
prev: state-and-ledger/issues-jsonl.md
next: false
---

`specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` is the append-only per-issue task ledger written exclusively by the `deviate` CLI. Each non-empty line is one JSON object validated against the `TaskRecord` Pydantic model in `src/deviate/state/ledger.py`; the parser/validator helpers live in `src/deviate/core/tasks_ledger.py`.

## File location

| Path | Owner | Write mode |
|---|---|---|
| `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` | `deviate` meso/micro-layer commands | Append-only JSONL; written via `append_task_record()` or `append_task_transition()` with `(id, status)` compound-key idempotency |

Agents must not edit this file directly — `specs/**/tasks.jsonl` is generated from the human-authored `tasks.md` by `generate_jsonl_from_md()` and then mutated only by CLI commands.

## TaskRecord fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `string` | (required) | Unique task identifier; must match `^TSK-\d{3}-\d{2}$` (enforced by `TaskRecord._validate_task_id`) |
| `issue_id` | `string` | (required) | Parent issue ID (e.g., `ISS-001-004`); the `generate_jsonl_from_md()` parser injects this from its second positional argument |
| `description` | `string` | (required) | Human-readable task summary; rejected by Pydantic when empty (`min_length=1`) |
| `status` | `enum` | `"PENDING"` | Lifecycle state — see the Status enum table below |
| `execution_mode` | `enum` | `"TDD"` | Execution strategy — see the Execution mode table below |
| `created_at` | `datetime` | `datetime.now(timezone.utc)` | First-write timestamp; preserved across status transitions |

`TaskRecord` is configured with `model_config = {"extra": "forbid"}` — any unknown key in a JSONL line fails Pydantic validation.

## Status enum

| Value | Meaning | Terminal? |
|---|---|---|
| `PENDING` | Initial entry from `generate_jsonl_from_md()`; task not yet started | No |
| `RED` | The red phase has claimed the task; tests failing | No |
| `GREEN` | Tests passing; implementation present | No |
| `YELLOW` | In-session yellow phase running (session phase only, not a persisted terminal state for the micro cycle) | No |
| `YELLOW_APPROVED` | Yellow verdict accepted; cycle advances to `JUDGE` | No |
| `YELLOW_REJECTED` | Yellow verdict rejected; cycle returns to `GREEN` after `git restore .` | No |
| `JUDGE` | Isolated V4 Pro session judging the GREEN implementation | No |
| `REFACTOR` | Refactor phase running in the same session as RED/GREEN | No |
| `COMPLETED` | Terminal success state | Yes |
| `FAILED` | Terminal failure state — train retries exhausted or unrecoverable error | Yes |

Canonical state is derived bottom-up: the latest entry per `(id, status)` compound key. Re-running the same transition is a no-op (`append_task_transition()` returns `False`).

## Execution mode enum

| Value | Meaning | Used by |
|---|---|---|
| `TDD` | Standard RED → GREEN → JUDGE → REFACTOR cycle | Default; set when `tasks.md` lacks a `**Mode**: ...` annotation |
| `DIRECT` | Boilerplate / config; no RED phase | `**Mode**: DIRECT` annotation in `tasks.md` |
| `EXECUTE` | Single-shot execution without TDD gates | `**Mode**: EXECUTE` annotation in `tasks.md` |
| `E2E` | End-to-end integration task; runs the full pipeline | `**Mode**: E2E` annotation in `tasks.md` |
| `IMMEDIATE` | Inline write, no subprocess isolation | `**Mode**: IMMEDIATE` annotation in `tasks.md` |

The parser reads `**Mode**: <value>` lines from `tasks.md` after a `- TSK-NNN-NN: ...` line. The default `TDD` applies when no `**Mode**` annotation is present.

## Idempotency keys

| Function | Idempotency key | Behaviour |
|---|---|---|
| `append_task_record(record, ledger_path)` | `id` | Refuses to rewrite a task with the same `id`; returns `False` on duplicate |
| `append_task_transition(record, ledger_path)` | `(id, status)` tuple | Multiple transitions for one task are all recorded; re-running the same transition is a no-op |

On POSIX filesystems both helpers acquire an exclusive `fcntl.flock` around the read-then-write window (`HAS_FCNTL` guards the import). On non-POSIX systems the lock is skipped.

## `tasks.md` → `tasks.jsonl` parser

`generate_jsonl_from_md(tasks_md, issue_id)` in `src/deviate/core/tasks_ledger.py:15` reads the human-authored `tasks.md` and emits `TaskRecord` instances with `status="PENDING"`.

| Pattern | Regex | Effect |
|---|---|---|
| Task line | `^\s*-\s+(?:\[(?:x\| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.+)` | Captures `id` (group 1) and description (group 2); supports both `- TSK-...` and `- [x] TSK-...` forms |
| Mode annotation | `\*\*Mode\*\*:\s*(\S+)` | Sets the next task's `execution_mode`; defaults to `"TDD"` |
| `issue_id` argument | (positional) | Injected into every emitted record from the second positional argument |

A task is emitted as a `TaskRecord` only when a subsequent task line is matched, or at end-of-file. Tasks without a `**Mode**` annotation inherit the running `current_mode` (initially `"TDD"`).

## Validation rules

| Rule | Source | Failure mode |
|---|---|---|
| `id` must match `^TSK-\d{3}-\d{2}$` | `TaskRecord._validate_task_id` at `src/deviate/state/ledger.py:81` | Pydantic raises `ValidationError`; `validate_tasks_jsonl()` returns the error message |
| `extra` keys forbidden on every line | `TaskRecord.model_config = {"extra": "forbid"}` | Pydantic raises `ValidationError` |
| `description` must be non-empty | `Field(min_length=1)` | Pydantic raises `ValidationError` |
| `status` must be a known literal | `Literal[...]` | Pydantic raises `ValidationError` |
| `execution_mode` must be a known literal | `Literal[...]` | Pydantic raises `ValidationError` |
| JSON lines must parse | `json.loads()` in `validate_tasks_jsonl()` | Error string `Record {i}: {loc}: {msg}` returned to caller |

`validate_tasks_jsonl(records)` is a *list* validator (it accepts a `list[dict]` and returns a `list[str]` of error messages — empty list means all records are valid).

## Example records

A complete, currently-valid `tasks.jsonl` line — full record from the parser:

```json
{"id": "TSK-004-01", "issue_id": "ISS-001-004", "description": "Automated deviate micro orchestration with session state, ledger updates, and --all multi-task pipeline", "status": "PENDING", "execution_mode": "TDD", "created_at": "2026-06-10T10:00:05.705625+00:00"}
```

A transition-only line (a follow-up append changing the same task to `COMPLETED`):

```json
{"id": "TSK-004-01", "issue_id": "ISS-001-004", "description": "Automated deviate micro orchestration with session state, ledger updates, and --all multi-task pipeline", "status": "COMPLETED", "execution_mode": "TDD", "created_at": "2026-06-15T13:56:25.820463Z"}
```

A minimal `tasks.md` block that the parser handles:

```
- TSK-005-06: Implement tasks.jsonl proposal pattern
  - **Mode**: TDD
- TSK-005-07: Do something else
  - **Mode**: IMMEDIATE
```

## See Also

- [Issues JSONL Schema](./issues-jsonl) — sibling reference for the macro-layer `specs/issues.jsonl` ledger
- [How to read the DeviaTDD ledgers](/how-to/inspect-the-ledger) — procedural walk-through of `resolve_issue_record`, `filter_tasks`, and the `LedgerFilter` model
- [Why the ledgers are append-only](/explanation/append-only-ledgers) — rationale for the read-append-read-before-write idempotency pattern
