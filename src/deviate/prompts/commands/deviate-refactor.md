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

Manual mode: run the scripts yourself.

1. Run `deviate refactor pre` to allocate the active TDD task and emit the
   JSON contract on stdout. The contract carries `files_to_refactor` — the RED+GREEN production set (`HEAD~2..HEAD`, or
   the task `Files:` list minus tests when that range is empty). Scope
   cleanup to those production files; do not modify tests.
2. Execute the REFACTOR (structural cleanup) work described in the core body.
3. Run `deviate refactor post` after the cleanup. The command stages the
   changed files, runs pre-commit hooks (lint, format-check, tests), updates
   the task ledger, and commits.

### Rich Handover Manifest

Emit this manifest:

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