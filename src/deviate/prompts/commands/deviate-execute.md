---
name: deviate-execute
description: Direct task execution (no TDD cycle) for low-complexity tasks, trivial changes, docs, or refactors with existing coverage.
category: deviattd-micro-layer
version: 1.0.0
layer: micro
aliases:
  - execute
  - /spec.execute
  - /x
---

## Manual Slash-Command Overlay

Manual mode: run the scripts yourself.

1. Run `deviate execute pre` to allocate the direct task and emit the JSON
   contract on stdout.
2. Execute the task work described in the core body.
3. Run `deviate execute post` after the task completes. The command stages
   the changed files, runs pre-commit hooks (lint, format-check, tests),
   updates the task ledger, and commits.

### Rich Handover Manifest

Emit this manifest:

```yaml
phase: "EXECUTE"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>