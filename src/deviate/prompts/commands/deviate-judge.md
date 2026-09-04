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
   reverts GREEN (or RED+GREEN) when the route requires it — after a
   TTY confirm, or immediately with `--yes` / `--revert`. It prints
   `head_sha`, `reset_to`, and `recovery_ref`
   (`tmp/deviate-agent-work/<task>/attempt-N`) so the operator can see
   the failing tree before any `git reset`. After revert, inspect the
   discarded commit with `git switch <recovery_ref>` (not `git stash`).
   It appends train feedback to the task card in `tasks.md` and commits
   that feedback. The agent does not `git reset` or edit `tasks.md`
   itself.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted. `evidence` is a list of objects
with `ac: "AC-PLAN-NNN"` (plan-owned Gherkin — not `AO-*`, not bare
`AC-NN`) plus `test_path` / `test_quote` / `impl_path` / `impl_quote`.
Do not emit string evidence items.

```yaml
phase: "JUDGE"
status: "PASS"
task_id: "{TASK_ID}"
next_phase: "IDLE"
next_action: "revert_red" | "revert_green" | "continue_refactor" | "skip_refactor" | "proceed_to_refactor_no_diff"
verdict: "COMPLIANCE_PASS" | "COMPLIANCE_VIOLATION"
evidence:
  - ac: "AC-PLAN-001"
    test_path: "tests/example.py"
    test_quote: "assert increment(2) == 3"
    impl_path: "src/example.py"
    impl_quote: "return n + 1"
summary: "One-sentence outcome"
violations:
  - category: "Spec Non-Compliance"
    file: "path/to/file.ext"
    detail: "Specific description of the violation, citing FR-NN / AC-PLAN-NNN"
    severity: "CRITICAL" | "HIGH" | "MEDIUM"
    recommendation: "How to resolve the violation"
train_feedback: |
  COMPLIANCE_VIOLATION: Instructions for the next-running agent.
  revert_green → "The next GREEN attempt must:" (keep RED and implement the required behavior).
  revert_red → "The next RED attempt must:" (author the required behavioral test).
  Use "REFACTOR NOTE:" only for optional COMPLIANCE_PASS advice for REFACTOR.

  COMPLIANCE_PASS: Optional informational REFACTOR NOTE: about non-blocking
  observations for the REFACTOR phase.
evaluation:
  spec_compliance: "PASS" | "FAIL"
  functional_invariance: "PASS" | "FAIL"
  test_integrity: "PASS" | "FAIL"
  security_governance: "PASS" | "FAIL"
  no_shortcuts: "PASS" | "FAIL"
  constitution_compliance: "PASS" | "FAIL"
  security_checks: pass | fail | warn
diff_summary:
  files_changed: 0
  files_modified: 0
  files_created: 0
  files_deleted: 0
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>