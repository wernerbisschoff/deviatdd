---
title: "Run /deviate-judge"
description: "How to evaluate the /deviate-green implementation against the spec contract for correctness, completeness, and integrity so the task can advance to REFACTOR (PASS) or retry GREEN with feedback (FAILURE)."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-003
prev: yellow.md
next: refactor.md
---

This how-to covers the micro-layer `/deviate-judge` phase: evaluating the GREEN implementation against `spec.md` for correctness, completeness, and integrity. JUDGE is the compliance gate before REFACTOR. On `COMPLIANCE_PASS` the task advances; on `COMPLIANCE_VIOLATION` the implementation rolls back to the RED boundary and the loop re-runs GREEN with `<train_feedback>` injected.

## Prerequisites

- A `GREEN` ledger row for the active `TSK-NNN-NN`; the diff spans the RED→GREEN commits stored in `session.red_commit_sha`
- Cwd inside the issue worktree created by `deviate feature start <ISS-XXX>`; `git status --porcelain` is clean
- The agent backend dispatched in **isolated V4 Pro mode** — JUDGE runs in a fresh session with no shared RED/GREEN context, by design, to preserve compliance integrity
- `deviate-judge` prompt installed under `.claude/commands/`, `.opencode/commands/`, `.factory/commands/`, or `.pi/prompts/` (run `deviate setup` if absent)

## Steps

### 1. Run the pre-script for the compliance check

From inside the issue worktree, invoke the pre-script:

```bash
deviate judge pre
```

It detects uncommitted changes via `git status --porcelain`, finds protected modules declared with `Module:` lines in `specs/**/issues/*.md`, and emits a JSON contract with `verdict` (`COMPLIANCE_VIOLATION` or `COMPLIANCE_PASS`) and a `details` list. A `COMPLIANCE_VIOLATION` here surfaces a protected-module tampering attempt before the agent runs.

### 2. Invoke `/deviate-judge` in the agent

In the agent's chat on the feature branch, run:

```text
/deviate-judge
```

The slash command runs in an isolated V4 Pro session. It reads `spec.md` for the active feature, the `constitution.md` invariants, the `<diff>` block (RED→GREEN), and any `<test_feedback>` from GREEN. The agent classifies changed files by domain, checks spec compliance (FR-NN / AC-NN), looks for shortcuts, security/governance issues, tamper evidence, and flow alignment — then emits a YAML verdict.

### 3. Interpret the verdict

The YAML block carries `verdict` plus `train_feedback` and `violations`:

- `COMPLIANCE_PASS` — every FR/AC satisfied, no tamper or flow gaps. Refactor opportunities surface as `REFACTOR NOTE:` entries in `train_feedback` (informational, not blocking).
- `COMPLIANCE_VIOLATION` — `_execute_rollback` resets the working tree to the RED boundary (`git reset --hard <red_sha>`), the verdict's feedback is appended under `**Judge Feedback**:` in `tasks.md`, the session is force-transitioned back to `GREEN`, and `<train_feedback>` is injected into the next GREEN prompt (up to `max_train_attempts = 3`).

### 4. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
grep '"status": "JUDGE"\|"status": "GREEN"' specs/<epic>/<issue>/tasks.jsonl
git status --porcelain
```

Expected on PASS: latest commit message starts with `feat(<scope>)` or a JUDGE marker, `current_phase` reads `"JUDGE"`, the `tasks.jsonl` row ends with `status: "JUDGE"`, and the worktree is clean. On FAILURE inside `deviate run`: the GREEN commit is gone, the worktree matches RED, and `current_phase` reads `"GREEN"`.

## Troubleshooting

### `JUDGE_AGENT_NO_FEEDBACK` from the orchestrator

The agent returned `COMPLIANCE_VIOLATION` but populated no `train_feedback`, `violations`, `rationale`, or `summary` — nothing concrete to train against. Re-invoke `/deviate-judge` with the GREEN diff visible (`git diff <red_sha>^..HEAD`); if the verdict stays empty, escalate manually since the pipeline cannot loop without actionable feedback.

### Rejection loops hit `max_train_attempts = 3`

GREEN keeps failing the same compliance criterion across all 3 retries. The `<train_feedback>` text in `tasks.md` shows the recurring gap. Inspect `spec.md` to confirm the requirement wording — either amend via `/deviate-research` or hand the implementation off to `/deviate-execute` with a tighter scope.

### `TASKS_MD_NO_MATCH` after a rejection

The `tasks.md` lacks a line for the active `TSK-NNN-NN` so the Judge Feedback bullet could not be appended. Open `specs/<epic>/<issue>/tasks.md`, add a `- [ ] TSK-NNN-NN: <description>` line, then re-run `/deviate-judge` so the rollback + feedback path can persist the next attempt's notes.

### Refactoring flagged as `COMPLIANCE_VIOLATION`

The judge agent miscategorized a structural improvement as a compliance gap. Refactor opportunities belong in `train_feedback` prefixed `REFACTOR NOTE:` on PASS, never as blocking violations. If the agent persists, edit `spec.md` so the requirement is unambiguous.

## Next Steps

- [How to run /deviate-refactor](/how-to/tdd-micro-cycle/refactor) — apply the structural cleanup JUDGE surfaced
- [How to run /deviate-green](/how-to/tdd-micro-cycle/green) — re-run GREEN after a rejection to satisfy the feedback
- [Reference: deviate judge flags and contract fields](/reference/cli/judge) — full flag list for `judge pre`
- [Why JUDGE runs in an isolated V4 Pro session](/explanation/micro-layer-purpose) — design rationale for the cache-sacrifice compliance gate