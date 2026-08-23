---
name: deviate-refactor
description: TDD REFACTOR phase — behavior-preserving structural improvement after tests pass.
category: deviattd-macro-layer
version: 1.0.0
layer: micro
aliases:
  - refactor
  - /spec.tdd.refactor
  - /refactor
  - /tdd.refactor
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/refactor.md` core — the single source of
truth for the REFACTOR instructions.

1. Run `deviate refactor pre` to allocate the active TDD task and emit the
   JSON contract on stdout.
2. Execute the REFACTOR (structural cleanup) work described in the core body.
3. Run `deviate refactor post` after the cleanup. The command stages the
   changed files, runs pre-commit hooks (lint, format-check, tests), updates
   the task ledger, and commits.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "REFACTOR"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>