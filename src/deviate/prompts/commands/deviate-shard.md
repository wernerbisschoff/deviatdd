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
  - /shard
---

## Manual Slash-Command Overlay

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

1. Run `deviate shard pre` to allocate the numbered epic bucket and emit the JSON contract on stdout.
2. Do the sharding work in the core body above.
3. Run `deviate shard post <plan_target>` with the absolute manifest path from the contract. Keep generated issue paths local to the consumer repository.

### Issue ID Assignment

New issues in a numbered epic bucket (e.g. `002-embedder-vector-search`) emit
per-epic ids of the form `<epic-prefix>-<ordinal>` (e.g. `002-001`, `002-002`,
...), where `<epic-prefix>` is the leading 3-digit segment of the epic bucket
dir; the adhoc bucket and bootstrap contexts fall back to the legacy
global-counter `ISS-NNN`. Sequential blockages use string-based `blocked_by`
frontmatter arrays referencing other shards' `issue_id` values, e.g.
`blocked_by: ["002-001"]`.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>