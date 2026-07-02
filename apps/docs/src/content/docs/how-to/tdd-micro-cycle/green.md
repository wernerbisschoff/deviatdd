---
title: "Run /deviate-green"
description: "How to implement the minimum production code that makes the failing /deviate-red test pass and commit the GREEN phase so /deviate-judge can verify the contract."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: [ISS-001-003]
prev: red.md
next: false
---

This how-to covers the micro-layer `/deviate-green` phase: writing the minimum production code that flips the failing test from `/deviate-red` to green, then handing off via `deviate green post` so the session transitions to `GREEN` and the task is ready for `/deviate-judge`. GREEN is a tight loop — read the assertion, implement minimally, verify, commit.

## Prerequisites

- A failed RED commit on the feature branch — `/deviate-red` completed for the active `TSK-NNN-NN` (latest ledger row carries `status: RED`)
- Cwd inside the issue worktree created by `deviate feature start <ISS-XXX>`
- `src/` writable; the GREEN pre-script globs `src/**/*.py` for implementation targets
- `mise run test` and `mise run lint` available — the post-script enforces both via pre-commit
- 180s timeout available — `deviate green post` runs the full test suite inside the hook chain

## Steps

### 1. Run the pre-script for the JSON contract

From inside the issue worktree, invoke the pre-script with the target task ID:

```bash
deviate green pre --task TSK-001-03
```

It resolves the active task from `tasks.jsonl`, finds the failing test path globbed by RED, and emits a JSON contract with `task_id`, `task_entry`, `test_file`, and `implementation_targets` (all `src/**/*.py`).

### 2. Invoke `/deviate-green` in the agent

In the agent's chat on the feature branch, run:

```text
/deviate-green
```

The slash command reads the contract plus any RED handover manifest, pulls `## Acceptance` bullets from `tasks.md` (including **Judge Feedback** injected as `<train_feedback>`), and writes the minimum production change under `src/` that satisfies the failing assertion — never edits `tests/**/test_*.py`.

### 3. Verify with the test and lint commands

Run the test and lint commands from the contract until both return `0`; if either fails, fix the implementation (never the test) and re-run. Stop only when both pass on the same diff.

### 4. Run the post-script to commit the GREEN phase

Run via the Bash tool — `git add` / `git commit` is not detected by the orchestrator:

```bash
deviate green post
```

It resolves the latest RED task, evaluates `TamperGuard` in `GREEN_IMPLEMENTATION` context, appends a `GREEN` transition to `tasks.jsonl`, force-transitions `.deviate/session.json` to `GREEN`, and commits with `feat({scope}): GREEN phase - implementation passes tests`. Output `GREEN_POST_OK` confirms success; `YELLOW_TRIGGERED` means TamperGuard auto-routed the task to `/deviate-yellow`.

### 5. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
grep '"status": "GREEN"' specs/<epic>/<issue>/tasks.jsonl
```

Expected: latest commit starts with `feat(<scope>): GREEN phase`, `current_phase` reads `"GREEN"`, and the `tasks.jsonl` row for `TSK-NNN-NN` ends with `status: "GREEN"`.

## Troubleshooting

### `MISSING_RED_PHASE` from `deviate green post`

No `RED` transition exists for the active issue. Run `/deviate-red` for the same `TSK-NNN-NN`, confirm the failing test landed and the row carries `status: RED`, then re-invoke `deviate green post`.

### `YELLOW_TRIGGERED` after `deviate green post`

`TamperGuard` modified a protected path during GREEN and the post-script auto-routed the task to `YELLOW`. Run `/deviate-yellow --rejected` to restore the working tree to the RED commit, or `--approved` to keep the amendments.

### `COMMIT_FAILED` or pre-commit hook aborts

The hook chain (`mise run lint`, `mise run format-check`, `mise run test`) tripped before the GREEN commit landed. Fix the source file, re-run the commands from step 3 to confirm, then re-invoke `deviate green post`.

## Next Steps

- [How to run /deviate-judge](/how-to/tdd-micro-cycle/judge) — verify the GREEN implementation against the spec contract
- [How to run /deviate-yellow](/how-to/tdd-micro-cycle/yellow) — review TamperGuard-flagged amendments when GREEN triggers YELLOW
- [Reference: deviate green flags and contract fields](/reference/cli/green) — full flag list for `green pre` / `green post`

