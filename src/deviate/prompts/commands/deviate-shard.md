---
name: deviate-shard
description: Decompose prd.md into self-contained Feature Vertical issues registered in specs/issues.jsonl with a DAG dependency topology.
category: deviatdd-macro-layer
version: 1.0.0
layer: macro
aliases:
  - shard
  - /deviate-shard
  - spec:full:shard
  - spec:full:shard
  - /shard
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. This manual overlay overrides
the auto lifecycle instructions above: the CLI orchestrator does not run
lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/shard.md` core — the single source of truth
for the SHARD instructions.

1. Run `deviate shard pre` to allocate the numbered epic bucket and emit the
   JSON contract on stdout.
2. Execute the sharding work described in the core body.
3. Run `deviate shard post <plan_target>` after the issue files are written.
   Replace `<plan_target>` with the absolute manifest path from the contract.
   The command validates the frontmatter, updates `specs/issues.jsonl`, and
   commits. Keep generated issue paths local to the consumer repository.

### Issue ID Assignment

New issues in a numbered epic bucket (e.g. `002-embedder-vector-search`) emit
per-epic ids of the form `<epic-prefix>-<ordinal>` (e.g. `002-001`, `002-002`,
...), where `<epic-prefix>` is the leading 3-digit segment of the epic bucket
dir; the adhoc bucket and bootstrap contexts fall back to the legacy
global-counter `ISS-NNN`. Sequential blockages use string-based `blocked_by`
frontmatter arrays referencing other shards' `issue_id` values, e.g.
`blocked_by: ["002-001"]`.

### Manifest Schema

```yaml
"issue_id": "002-001"
"blocked_by": ["002-001"]
```

<consumer_repository_boundary>
The target is the consumer application's implementation. Assume the DeviaTDD
CLI and every required agent skill are already installed. Every emitted issue
must implement or verify the requested application behavior. User stories
plus ATDD on the issue are the user-visible job. Do not list
DeviaTDD setup, skill or slash-command creation, catalog authoring,
release scaffolding, or workflow-ledger maintenance in
issue titles, workstation paths, acceptance outlines, demonstration paths,
or manifest entries. If any PRD requirement is meta work rather than
application behavior, halt with `META_WORK_NOT_ALLOWED` before writing
issue files.
</consumer_repository_boundary>

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "SHARD"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>