---
title: "Run /deviate-execute"
description: "How to execute a DIRECT-mode task via /deviate-execute, bypassing the RED/GREEN/REFACTOR cycle for trivial fixes, docs, or refactors with existing coverage."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: how-to/issue-execution/tasks.md
next: false
---

This how-to covers the micro-layer `/deviate-execute` phase: implementing one DIRECT-mode task end-to-end without the RED/GREEN/REFACTOR cycle, for `IMMEDIATE` / `DIRECT` slices in `tasks.md` (boilerplate, config, asset syncs, trivial fixes, refactors with existing coverage).

## Prerequisites

- A `tasks.md` blueprint with at least one `IMMEDIATE` / `DIRECT`-tagged task, on the issue's worktree (handled by `/deviate-tasks` and `/deviate-plan`)
- An agent runtime with the `deviate-execute` slash command installed (`deviate setup`)

## Steps

### 1. Enter the worktree and run the pre-script

From inside the issue's worktree, emit the JSON contract (pass `--task TSK-NNN-NN` to target a specific slice):

```bash
git worktree list --porcelain | awk '/^worktree /{print $2; exit}' | xargs -I{} bash -c "cd {} && deviate execute pre"
```

Capture `task_id` from the contract.

### 2. Run the slash command in your agent

In the agent's chat, run `/deviate-execute` (aliases: `/x`, `/spec.execute`). The slash command ingests the contract, reads the task fields from `<user_input>`, sanity-checks DIRECT execution is appropriate, and applies the minimal focused modifications.

### 3. Validate and commit

Run `mise run check` to validate (iterate until it passes), then invoke the post-script:

```bash
mise run check
deviate execute post
```

The post-script appends a `COMPLETED` transition to `tasks.jsonl`, stages tracked changes, runs pre-commit hooks (allocate ≥ 180s), and commits with `feat(<task_id>): execute result`. Override the subject positionally: `deviate execute post <TASK_ID> "<subject>" ["<body>"]`.

### 4. Verify the change

```bash
grep '"id": "TSK-[0-9]\{3\}-[0-9]\{2\}"' specs/**/tasks.jsonl | tail -1
git log --oneline -1
```

Expect the latest ledger row to read `status: COMPLETED` for the task ID and the commit subject to start with `feat(TSK-NNN-NN):`.

## Troubleshooting

### Pre-script returns an empty task_id

The session has no active task. Re-run `/deviate-tasks` to regenerate the blueprint, or pass `--task TSK-NNN-NN` to the pre-script explicitly.

### Task exceeds DIRECT tier

`mise run check` keeps failing because the change needs new test coverage. Halt DIRECT execution, write a failing test first, and use the TDD cycle (`/deviate-red`, `/deviate-green`, `/deviate-refactor`) instead.

### Post-script exits non-zero

Pre-commit hooks or the commit aborted. Read the hook output, fix the violation on the worktree, then re-run `deviate execute post`. As a last resort, fall back to a manual `git commit -m "<subject>" -m "Mode: DIRECT"`.

### Commit subject malformed

The agent passed a subject over 50 chars or missing the `<type>(<scope>):` prefix. Re-run: `deviate execute post <TASK_ID> "feat(<scope>): <subject>"`.

## Next Steps

- [How to run a TDD task through RED/GREEN/REFACTOR](/how-to/tdd-micro-cycle/red) — for tasks tagged `TDD` in `tasks.md`
- [Reference: deviate execute flags](/reference/cli/execute) — full flag list and pre-script JSON contract schema
- [Why DIRECT mode bypasses the RED boundary](/explanation/direct-mode-rationale) — design rationale for the IMMEDIATE execution tier