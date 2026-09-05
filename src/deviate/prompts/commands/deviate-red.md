---
name: deviate-red
description: Use when executing the RED (test-writing) phase of TDD for a single task
category: deviattd-macro-layer
version: 1.0.0
layer: micro
aliases:
  - red
  - /spec.tdd.red
  - /red
  - /tdd.red
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/red.md` core — the single source of truth
for the RED instructions.

1. Run `deviate red pre` to allocate the active TDD task and emit the JSON
   contract on stdout.
2. Parse the contract's `task_entry` field. It carries this task's
   `tasks.md` card verbatim, including any `**Judge Feedback**` bullets a
   prior JUDGE run persisted. Treat those bullets as the
   `<persisted_judge_feedback>` correction list defined in the core body —
   resolve every bullet before declaring RED done. There is no separate
   `<train_feedback>` injection in manual mode.
3. Execute the RED (test-writing) work described in the core body.
4. Run `deviate red post --task-id {TASK_ID}` after the tests are verified
   failing. The command stages the test files, verifies them failing, updates
   the task ledger, and commits. A mismatch with the resolved pending task
   exits `TASK_ID_MISMATCH` with no ledger write and no commit.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted. Follow the auto handover
semantics: `status: "PASS"` with an optional `failure_kind` discriminator.

```yaml
phase: "RED"
status: "PASS"
task_id: "{TASK_ID}"
# Add these only when the suite did not fail:
# failure_kind: already_satisfied | test_defect
# rationale: <why no implementation is needed / why the test cannot target the behavior>
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
### RED Checkpoint

When the suite passes, this phase completes with a warning advisory
(`RedHandoffAdvisory`) handed to GREEN; the warning does not block GREEN start.