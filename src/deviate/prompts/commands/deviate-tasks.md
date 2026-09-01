---
name: deviate-tasks
description: Decompose issue intent plus plan.md's authoritative acceptance contract into autonomous Red-Green-Refactor units.
category: deviatdd-meso-layer
version: 1.0.0
layer: meso
aliases:
  - tasks
  - /deviate-tasks
  - spec:core:tasks
  - spec.core.tasks
  - /tasks
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/tasks.md` core — the single source of truth
for the TASKS instructions. Task ids use the runner-enforced `TSK-NNN-NN`
format.

1. Run `deviate tasks pre` to locate the active issue and emit the JSON
   contract on stdout.
2. Execute the task-decomposition work described in the core body.
3. Run `deviate tasks post` after `tasks.md` is written. The command
   validates the task ledger, updates it, and commits.

<consumer_repository_boundary>
Every task must implement or verify the requested application behavior and
cite its issue story plus `AC-PLAN-NNN`. Do not emit tasks for DeviaTDD setup,
agent skills or slash commands, catalog authoring, release
scaffolding, or workflow-ledger maintenance. Any meta-target task halts with
`META_WORK_NOT_ALLOWED`.
</consumer_repository_boundary>

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "TASKS"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>