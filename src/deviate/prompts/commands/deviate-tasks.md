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

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

Task ids use the runner-enforced `TSK-NNN-NN` format.

1. Run `deviate tasks pre` to locate the active issue and emit the JSON contract on stdout.
2. Do the task-decomposition work in the core body above.
3. Run `deviate tasks post` after `tasks.md` is written.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>