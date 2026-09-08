---
name: deviate-green
description: Use when executing the GREEN (implementation) phase of TDD for a single task
category: deviattd-macro-layer
version: 1.0.0
layer: micro
aliases:
  - green
  - /spec.tdd.green
  - /green
  - /tdd.green
---

## Manual Slash-Command Overlay

Manual mode: run the scripts yourself.

1. Run `deviate green pre` to allocate the active TDD task and emit the JSON
   contract on stdout.
2. Execute the GREEN (implementation) work described in the core body.
3. Run `deviate green post` after the tests pass. The command stages the
   changed files, runs pre-commit hooks (lint, format-check, tests), updates
   the task ledger, and commits.

### Rich Handover Manifest

Emit this manifest:

```yaml
phase: "GREEN"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>