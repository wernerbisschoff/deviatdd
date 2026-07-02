---
title: "Run /deviate-red"
description: "How to write a failing test for an active TDD task so /deviate-green can drive the implementation through the assertion it pins down."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-003
prev: false
next: false
---

This how-to covers the micro-layer `/deviate-red` phase: writing a single failing test that pins the behavior of the active `TSK-NNN-NN` row in `specs/**/tasks.jsonl`. The failing test is the contract for `/deviate-green`; once it commits and the session transitions to `RED`, you are ready to hand off to implementation.

## Prerequisites

- An active TDD task with `status: PENDING` in `specs/**/tasks.jsonl` (from `/deviate-tasks`)
- Cwd inside the issue worktree created by `deviate feature start <ISS-XXX>`; the RED post-script globs `tests/**/test_*.py`
- `mise run test` available (the canonical `test_command` from the pre-script contract)

## Steps

### 1. Run the pre-script for the JSON contract

From inside the issue worktree, invoke the pre-script with the target task ID:

```bash
deviate red pre --task TSK-001-03
```

It resolves the row from `tasks.jsonl` and emits a JSON contract with `task_id`, `test_command`, `lint_command`, and `spec_dir`. Capture `spec_dir` so the agent can read the per-task acceptance criteria before authoring tests.

### 2. Invoke `/deviate-red` in the agent

In the agent's chat on the feature branch, run:

```text
/deviate-red
```

The slash command reads the contract, pulls the `## Acceptance` bullets for `TSK-NNN-NN` from `tasks.md`, and writes ONE failing test under `tests/` using the canonical mise commands. Functional requirements (`FR-NNN`) and acceptance bounds (`AC-NN`) translate to `Given/When/Then` assertions; mocks are restricted to non-deterministic external networks or volatile system attributes.

### 3. Run the post-script to validate and commit

```bash
deviate red post
```

It re-runs `mise run test` and refuses to commit if the new test passes (`RedMustPassError`) or is missing (`TEST_NOT_FOUND`). On success it appends a `RED` transition to `tasks.jsonl`, force-transitions `.deviate/session.json` to phase `RED`, and commits with `test({scope}): RED phase - failing test` (`--no-verify` is passed).

### 4. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
grep '"status": "RED"' specs/<epic>/<issue>/tasks.jsonl
```

Expected: the latest commit message starts with `test(<scope>): RED phase`, `current_phase` reads `"RED"`, and the `tasks.jsonl` row for `TSK-NNN-NN` now ends with a `RED` status entry.

## Troubleshooting

### `RedMustPassError: Test passed, expected a failing test`

The new test asserts on behaviour the implementation already satisfies. Tighten the assertion to pin a behaviour the production code does NOT yet implement, or split off a new sub-requirement, then re-run `deviate red post`.

### `NO_PENDING_TASKS` from `deviate red post`

The active issue has no `PENDING` task row left. Re-run `deviate tasks pre` to inspect the ledger; either pick the next `TSK-NNN-NN` (`--task`) or run `/deviate-tasks` to decompose the issue further.

### `TEST_NOT_FOUND`

`tests/**/test_*.py` came back empty after the agent's edit — the slash command finished without writing a test file. Re-run `/deviate-red`; if the agent exits mid-flight, inspect `tests/` for partial files and complete them, then call `deviate red post`.



## Next Steps

- [How to run /deviate-green](/how-to/tdd-micro-cycle/green) — implement against the failing test to advance the task to `GREEN`
- [Reference: deviate red flags and contract fields](/reference/cli/red) — full flag list for `red pre` / `red post`
- [Why the RED phase tests behavior rather than implementation](/explanation/micro-layer-purpose) — design rationale for sociable over solitary tests
