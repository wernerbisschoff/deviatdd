---
name: deviate-plan
description: Per-issue localized research — scan codebase and prior implementations; produce plan.md with strategy, file mappings, and risks.
category: deviatdd-meso-layer
version: 1.0.0
layer: meso
aliases:
  - plan
  - /deviate-plan
  - spec:core:plan
  - spec.core.plan
  - /plan
---

## Manual Slash-Command Overlay

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

1. Run `deviate plan pre` to locate the active issue and emit the JSON contract on stdout.
2. Do the planning work in the core body above.
3. Run `deviate plan post` after `plan.md` is written.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>