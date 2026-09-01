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

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/plan.md` core — the single source of truth
for the PLAN instructions.

1. Run `deviate plan pre` to locate the active issue and emit the JSON
   contract on stdout.
2. Execute the planning work described in the core body.
3. Run `deviate plan post` after `plan.md` is written. The command validates
   the artifact, updates the task ledger, and commits.

<consumer_repository_boundary>
The plan is for application implementation in a consumer repository. The
plan covers only the requested application behavior and the application
files required to deliver it. Do not add DeviaTDD setup, agent skills, slash
commands, catalog authoring, release scaffolding, or
workflow-ledger maintenance to any plan section. If any issue scope is meta
work, halt with `META_WORK_NOT_ALLOWED`.
</consumer_repository_boundary>

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "PLAN"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>