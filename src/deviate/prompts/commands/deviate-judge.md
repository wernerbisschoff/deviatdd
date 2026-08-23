---
name: deviate-judge
description: TDD JUDGE phase — review GREEN implementation against spec.md for correctness and integrity; emit COMPLIANCE_PASS.
category: deviattd-micro-layer
version: 1.2.0
layer: micro
aliases:
  - judge
  - /judge
  - /tdd.judge
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/judge.md` core — the single source of truth
for the JUDGE instructions.

1. Run `deviate judge pre` to allocate the GREEN handover to review and emit
   the JSON contract on stdout.
2. Execute the JUDGE (compliance review) work described in the core body.
3. Run `deviate judge post` after the verdict is emitted. The command
   validates the verdict, updates the task ledger, and commits.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "JUDGE"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>