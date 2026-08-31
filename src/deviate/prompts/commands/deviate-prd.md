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
   contract on stdout. The contract includes `epic_slug`, `prd_path`, and
   `plan_target`. The command blocks on any `## Pending HITL Decisions`
   row with Status `PENDING` — the HITL Gate 1 enforcement mechanism.
2. Execute the PRD compilation work described in the core body, writing
   `specs/<epic_slug>/prd.md`. The PRD must include every required section,
   including a top-level `## Acceptance Outline` containing `AO-NNN` tokens.
3. Write the manifest to the contract's `plan_target` path. It must include
   the `epic_slug` field.
4. Run `deviate prd post .deviate/artifacts/manifest_prd.json` after the
   artifact and manifest are written. Replace the path when `plan_target`
   specifies another location. The command validates the PRD, stages it,
   and commits it.

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