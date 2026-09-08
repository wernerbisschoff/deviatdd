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

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

1. Run `deviate prd pre` to verify the research artifacts and emit the JSON contract (`epic_slug`, `prd_path`, `plan_target`). It blocks on any `## Pending HITL Decisions` row with Status `PENDING` (Gate 1).
2. Compile the PRD per the core body above, writing `specs/<epic_slug>/prd.md`.
3. Write the manifest to the contract's `plan_target` path with the `epic_slug` field.
4. Run `deviate prd post .deviate/artifacts/manifest_prd.json`, or the `plan_target` path when it differs.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>