---
name: deviate-prd
description: Compile explore.md into prd.md — the singular source of truth for downstream sharding into specs/issues.jsonl.
category: deviatdd-macro-layer
version: 1.1.0
layer: macro
aliases:
  - prd
  - /deviate-prd
  - spec:full:prd
  - spec.full.prd
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/prd.md` core — the single source of truth
for the PRD instructions.

1. Run `deviate prd pre` to verify the research artifacts and emit the JSON
   contract on stdout. The command blocks on any `## Pending HITL Decisions`
   row with Status `PENDING` — the HITL Gate 1 enforcement mechanism.
2. Execute the PRD compilation work described in the core body, writing
   `prd.md`.
3. Run `deviate prd post` after the artifact is written. The command
   validates the sections, updates the ledger, and commits.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "PRD"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>