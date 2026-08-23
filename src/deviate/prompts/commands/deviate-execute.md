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

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/execute.md` core — the single source of
truth for the EXECUTE instructions.

1. Run `deviate execute pre` to allocate the direct task and emit the JSON
   contract on stdout.
2. Execute the task work described in the core body.
3. Run `deviate execute post` after the task completes. The command stages
   the changed files, runs pre-commit hooks (lint, format-check, tests),
   updates the task ledger, and commits.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

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