---
title: "deviate inspect issues"
description: "Reference for `deviate inspect issues list` — flags, status/type filters, JSON output, and ORPHAN_CLAIM detection against the issues ledger."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-002-004
prev: false
next: false
---

`deviate inspect issues list` reads `specs/issues.jsonl`, deduplicates the append-only ledger (latest record per `issue_id` wins), and renders the parsed state as a Rich `Table` or a JSON array. The command is the canonical operator view of in-flight issue state and replaces ad-hoc `jq` over the ledger file.

## Synopsis

```
deviate inspect issues list [--type <type>] [--status <status>] [--json] [--quiet]
```

## Flags

| Name | Type | Default | Description |
|---|---|---|---|
| `--type` | `string` | `null` | Filter rows by the issue's `type` field (e.g., `feature`, `epic`, `adhoc`). |
| `--status` | `string` | `null` | Filter rows by the issue's `status` field (e.g., `DRAFT`, `BACKLOG`, `SPECIFIED`, `SHARDED`, `COMPLETED`). |
| `--json` | `bool` | `false` | Emit the parsed record array as JSON on stdout instead of rendering a Rich table. |
| `--quiet` | `bool` | `false` | Suppress all output; combine with `--json` for machine-readable logs, or alone to short-circuit the render path. |

## Issue Statuses

Statuses are validated against the `IssueRecord.status` `Literal` in `src/deviate/state/ledger.py`. Only these values pass strict validation; unrecognised values are accepted by the CLI filter but rendered as raw strings.

| Status | Meaning |
|---|---|
| `DRAFT` | Initial state captured by the macro-layer capture phase; not yet queued. |
| `BACKLOG` | Issue is captured but waiting on dependencies (`blocked_by`). |
| `SPECIFIED` | Issue has a `source_file` and is eligible for shard; triggers the ORPHAN_CLAIM check against the remote. |
| `SHARDED` | Issue has been decomposed into tasks via `/shard`; downstream planning is unblocked. |
| `COMPLETED` | All tasks for the issue have completed; terminal state. |

## Output Fields (JSON mode)

The `--json` flag emits a JSON array of records, one per deduplicated issue.

| Field | Type | Notes |
|---|---|---|
| `issue_id` | `string` | Canonical identifier (e.g., `ISS-001-002`); primary key for deduplication. |
| `type` | `string` | Issue archetype; passed through `--type` filter. |
| `title` | `string` | Human-readable title from the ledger record. |
| `status` | `string` | Current derived status; passed through `--status` filter. |
| `source_file` | `string` | Path to the spec file backing this issue (e.g., `specs/.../issues/<slug>.md`). |
| `blocked_by` | `list[string]` | Issue IDs whose `COMPLETED` status must precede this one. |
| `coordinates_with` | `list[string]` | Issue IDs that must move in lockstep (soft-link; no order implied). |
| `orphan_claim` | `bool \| null` | Populated only when `status == "SPECIFIED"`; see Orphan Claim Detection. |

## Orphan Claim Detection

For every issue with `status == "SPECIFIED"`, the command derives the deterministic branch name `feat/{bucket}/{slug}` and probes the configured remote via `git ls-remote --heads`.

| Field | Value |
|---|---|
| Branch template | `feat/{bucket}/{slug}` (e.g., `feat/001-deviate-cli-python/002-macro-layer-state-ledger-management`) |
| `bucket` source | `_resolve_bucket_dir(source_file)` — first non-`specs` directory segment below `specs/` |
| `slug` source | `_source_stem(source_file)` — filename without extension |
| Remote | `detect_remote(repo)` (throws `RuntimeError` when no remote is configured) |
| Timeout | `30s` per `git ls-remote` invocation |
| `orphan_claim = True` | Remote reachable, branch template does not exist on remote |
| `orphan_claim = False` | Remote reachable, branch template exists on remote |
| `orphan_claim = null` | Remote unreachable, no remote configured, timeout, or non-zero `git` exit |

When `orphan_claim` is `True`, the Rich table renders a `🟡 ORPHAN_CLAIM` badge in the `Orphan` column. JSON mode emits the literal `true` and downstream tooling can route the claim for re-push.

## Example

List every `SPECIFIED` issue and pipe the JSON array into `jq` for further filtering:

```
deviate inspect issues list --status SPECIFIED --json | jq '.[] | select(.orphan_claim == true) | .issue_id'
```

Render the same set as a Rich table for an operator console:

```
deviate inspect issues list --status SPECIFIED
```

## See Also

- [How to run a DIRECT-mode task](/how-to/issue-execution/execute) — exercises the issue lifecycle that `inspect issues` reports on
- [Tutorial: a guided first run](/tutorials/starter-first-run) — see issues appear in the ledger as you walk the pipeline
- [Starter architecture overview](/explanation/architecture/starter-architecture) — grounding for the macro/meso/micro layer split the issues ledger records against