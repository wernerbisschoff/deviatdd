---
title: "Run /deviate-refactor"
description: "How to clean up the GREEN implementation through behavior-preserving structural changes, verified by pre/post pytest comparison, so the task is marked COMPLETED."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-003
prev: yellow.md
next: false
---

This how-to covers the micro-layer `/deviate-refactor` phase: applying behavior-preserving structural improvements to the GREEN implementation and committing the cleanup so the task is marked `COMPLETED` and the session returns to `IDLE`. REFACTOR is the last phase of the cycle — the contract is invariance, and the post-script enforces it by diffing pytest output before and after the change.

## Prerequisites

- A `GREEN` ledger row for the active `TSK-NNN-NN` (REFACTOR refuses to run without it)
- Cwd inside the issue worktree created by `deviate feature start <ISS-XXX>`; the agent edits `src/**/*.py` only and MUST NOT touch `tests/**/test_*.py`
- `mise run test` and `mise run lint` available — the post-script runs both via pre-commit and diffs pytest stdout before vs after
- 180s timeout available — `deviate refactor post` runs the full test suite inside the hook chain

## Steps

### 1. Run the pre-script for the JSON contract

From inside the issue worktree, invoke the pre-script with the target task ID:

```bash
deviate refactor pre --task TSK-NNN-NN
```

Resolves the active task from `tasks.jsonl`, globs `src/**/*.py` via `_find_source_files`, and emits JSON with `task_id`, `task_entry`, and `files_to_refactor`.

### 2. Invoke `/deviate-refactor` in the agent

In the agent's chat on the feature branch, run:

```text
/deviate-refactor
```

The slash command loads `specs/constitution.md` plus the per-task `spec.md` / `data-model.md`, inspects the last two commits (`git log -2 --oneline --stat`), identifies code smells (duplication, complexity, contract violations, naming, coupling), and applies Extract Function, Rename, Move, Replace Conditional with Polymorphism, or Consolidate Duplicate Fragments.

### 3. Verify invariance with test and lint

Run the test and lint commands from the contract until both return `0`. If a test fails, revert and re-apply — never modify a test to make it pass in this phase.

### 4. Run the post-script to commit the cleanup

Run via the Bash tool — `git add` / `git commit` is not detected by the orchestrator:

```bash
deviate refactor post
```

It verifies the GREEN transition, appends `COMPLETED` to `tasks.jsonl`, snapshots pytest output, scans each changed `.py` via tree-sitter for return-type mismatches and complexity ≥ 10, then re-runs pytest. If output or returncode differs (or any type issue fires), it runs `git restore .` and exits `1`. On success it commits `refactor({scope}): REFACTOR phase — code cleanup` and force-transitions `.deviate/session.json` back to `IDLE`.

### 5. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
grep '"status": "COMPLETED"' specs/<epic>/<issue>/tasks.jsonl
```

Expected: latest commit starts with `refactor(<scope>): REFACTOR phase`, `current_phase` is `"IDLE"`, and `tasks.jsonl` for `TSK-NNN-NN` ends with `status: "COMPLETED"`.

## Troubleshooting

### `MISSING_GREEN_PHASE` from `deviate refactor post`

No `GREEN` transition exists for the active issue. Run `/deviate-green` for the same `TSK-NNN-NN`, confirm the GREEN commit landed and the ledger row carries `status: GREEN`, then re-invoke `deviate refactor post`.

### `RefactorRegressionError: Test regression detected after refactor`

Pre-commit pytest output (returncode or normalized stdout) differs from the snapshot taken before the change. The post-script has already run `git restore .` — inspect the diff to see which edits were discarded, re-apply a smaller change that preserves test output, then re-invoke `deviate refactor post`.

### `RefactorRegressionError: <type issue>` from tree-sitter check

A modified `.py` file has a literal return that does not match its annotated type, a duplicate ≥ 5-line block, dead code, or a function with cyclomatic complexity ≥ 10. The worktree has already been restored — fix the offending function (or revert that specific file with `git checkout -- <path>` if partial edits remain) and re-run the post-script.

### `COMMIT_FAILED` or pre-commit hook aborts

The hook chain (`mise run lint`, `mise run format-check`, `mise run test`) tripped before the REFACTOR commit landed. Fix the source file, re-run the commands from step 3 to confirm, then re-invoke `deviate refactor post`.

## Next Steps
- [How to run /deviate-refactor (next task's RED)](/how-to/tdd-micro-cycle/red) — start a fresh micro-cycle for the next `TSK-NNN-NN`
- [How to run /deviate-green](/how-to/tdd-micro-cycle/green) — re-implement if the post-script rolled back the cleanup
- [Reference: deviate refactor flags and contract fields](/reference/cli/refactor) — full flag list for `refactor pre` / `refactor post`
- [Why the REFACTOR phase is verified by pre/post test diffs](/explanation/micro-layer-purpose) — design rationale for behavior-invariance enforcement