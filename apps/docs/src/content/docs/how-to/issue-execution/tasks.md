---
title: "Decompose a spec into tasks.md"
description: "Run /deviate-tasks to break a spec-enriched issue into vertical 30-90 min slices with deterministic Verification commands."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-003
prev: false
next: false
---

After `/deviate-shard` produces a spec-enriched issue, the Tasks phase turns that spec into a `tasks.md` blueprint of vertical slices. Each slice is one autonomous Red-Green-Refactor unit (30-90 minutes) with a deterministic `Verification` command. This how-to covers the full pre → agent → post loop.

## Prerequisites

- A spec-enriched issue file under `specs/<epic>/<issue>/` (produced by `/deviate-shard`)
- A worktree claimed for the active issue (handled by `/deviate-plan` or the shard post-script)
- A DeviaTDD session whose phase is `SHARD`, `PLAN`, or `TASKS` (use `--force` to bypass)
- An agent runtime with the `deviate-tasks` slash command installed (`deviate setup`)

## Steps

### 1. Enter the worktree and run the pre-script

From inside the worktree (the pre-script detects it via `Path.cwd()`), emit the JSON contract:

```bash
git worktree list --porcelain | awk '/^worktree /{print $2; exit}' | xargs -I{} bash -c "cd {} && deviate tasks pre"
```

Capture `tasks_target` from the contract — that is where `/deviate-tasks` will write the file.

### 2. Run the slash command in your agent

In the agent's chat, run:

```
/deviate-tasks
```

The slash command reads the spec from `spec_path` (embedded `## User Stories Ledger` and `## ATDD Acceptance Criteria` sections in the issue file take precedence over a sibling `spec.md`), groups files into workstations, and writes the decomposed `tasks.md` directly to `tasks_target`. Each task carries `TSK-{NNN}-{NN}` IDs plus **Type**, **Mode** (TDD or IMMEDIATE), **Test Strategy**, **Verification**, **Files**, **Rationale**, and **Details** (Red / Green / Refactor for TDD; Implementation for IMMEDIATE).

### 3. Run the post-script to validate and commit

```bash
deviate tasks post
```

Validates required sections and the `TSK-###-##` id regex, runs pre-commit hooks (full test suite — allocate ≥ 180s), commits with `docs(<epic>-<issue>): create tasks.md`, appends a row to `tasks.jsonl`, and transitions the session to `IDLE`.

### 4. Verify the change

```bash
grep -cE '^### TSK-[0-9]{3}-[0-9]{2}' specs/*/*/tasks.md
git log --oneline -1
deviate status
```

Expect every `### TSK-NNN-NN` heading to be present, the latest commit to read `docs(<epic>-<issue>): create tasks.md`, and `deviate status` to report phase `IDLE` for the active issue.

## Troubleshooting

### STATUS: NOT_IN_WORKTREE

The pre-script refused to run because `Path.cwd()` is outside the issue's worktree. `cd` into the worktree from step 1 and re-run `deviate tasks pre`.

### STATUS: SPEC_NOT_FOUND or NO_ACTIVE_ISSUE

No spec-enriched issue exists for the session, or its embedded spec sections are absent. Run `/deviate-shard` first to produce a valid issue file; a sibling `spec.md` is a legacy fallback only.

### TASKS_EMPTY or post-script rejects output

The agent wrote an empty file, or task ids / required sections failed validation. Re-run `/deviate-tasks`: every TDD task needs **Red** and **Green** bullets, every IMMEDIATE task needs an **Implementation** bullet, and every task needs a non-empty **Verification** CLI command.

### Validation passes but no commit appears

Pre-commit hooks (lint + tests) failed and aborted the commit. Read the hook output, fix the violations on the worktree, then re-run `deviate tasks post` (or use `--force` with a documented justification).

## Next Steps

- [How to run a task through the TDD micro-cycle](/how-to/tdd-micro-cycle/red) — pick the first `TSK-NNN-NN` from `tasks.md` and execute it
- [Reference: deviate tasks flags and contract fields](/reference/cli/tasks) — full flag list and pre-script JSON schema
- [Why tasks.md and tasks.jsonl are separate ledgers](/explanation/dual-ledger-protocol) — design rationale for the two-file split
