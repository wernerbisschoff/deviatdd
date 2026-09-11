---
title: "Complete JUDGE revert_red rollback when the mise reset task is missing"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-060
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/060-judge-revert-red-missing-reset-task.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/cli/init.py`, `.deviate/` recovery logs, `tests/unit/test_micro/`

## The Problem Contract
A JUDGE `revert_red` rollback crashes with `EnvNotReadyError` when the project defines no `mise run reset` task. The orphan RED commit stays recoverable, but the rollback aborts mid-path and the ledger loses the RED row. The runner must finish the git rollback first and report the missing hook as a distinct ENV precondition.

## Scope Boundaries
### Hard Inclusions
- Complete the git reset to `reset_to` before any isolated-env reset attempt on the `revert_red` path.
- Preserve the orphan RED commit evidence (`head_sha`, `reset_to`, `recovery_ref`) and keep the RED ledger row.
- Report a missing `mise run reset` task as a distinct ENV precondition that gates the next RED/GREEN until the hook exists.

### Defensive Exclusions
- Do not change the `revert_green` rollback path (covered by `ISS-ADH-059`).
- Do not silently skip the isolated-env reset for integration/e2e tasks without reporting it.
- Do not overwrite a consumer-defined `[tasks.reset]` entry; stub insertion stays merge-if-missing.
- Do not change JUDGE verdict semantics, retry budgets, or model routing.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-060`
- **Acceptance Criteria Tokens**: `AC-ADHOC-060-01`, `AC-ADHOC-060-02`
- **Data Model Entities**: `SessionState.red_commit_sha`, `TaskRecord.head_sha`, `TaskRecord.recovery_ref`, `EnvNotReadyError`, `[tasks.reset]`

## User Stories Ledger
- **US-060-01**: As a DeviaTDD operator, I want a JUDGE revert_red rollback to finish and keep RED evidence even when my project has no reset task so a missing hook does not lose work. *(Ref: FR-ADHOC-060)*

## Acceptance Outline
- **AO-060-01** *(Ref: AC-ADHOC-060-01, US-060-01)*: A `revert_red` rollback with no `mise run reset` task completes without crashing mid-rollback.
  - **Happy Path**: The git reset to `reset_to` completes and the orphan RED commit stays reachable via `recovery_ref`.
  - **Error Category**: The runner returns a distinct missing-reset ENV precondition instead of an unhandled mid-rollback crash.
  - **Boundary Category**: Unit and unstamped `test_strategy` tasks keep skipping the reset hook with no behavior change.
- **AO-060-02** *(Ref: AC-ADHOC-060-02, US-060-01)*: The missing hook blocks re-entry without losing state.
  - **Happy Path**: The report carries `head_sha`, `reset_to`, and `recovery_ref`, and the RED ledger row is preserved.
  - **Error Category**: The next RED/GREEN for the task stays gated until a `reset` task exists.
  - **Boundary Category**: A failing (nonzero-exit) `mise run reset` keeps its current `ENV_NOT_READY` failure semantics.

## Edge Cases and Boundaries
- Integration/e2e task with no `[tasks.reset]` entry and a valid orphan RED commit.
- `revert_red` on a unit-strategy task never reaches the reset hook.
- `mise run reset` exists but exits nonzero — existing failure semantics apply.
- `recovery_ref` is present but the RED commit is unreachable.
- Related boundary: GH issue 228 covers the missing `red_commit_sha` path on `revert_green` (`ISS-ADH-059`).

## Performance Constraints
- L_max: 200 ms per agent export
- Throughput: One rollback report per JUDGE action

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_rollback_safety.py` — `revert_red` without a reset task completes the git reset and preserves RED evidence.
- **Integration Sandbox Targets**: `tests/unit/test_micro/test_run.py` — `deviate micro run` surfaces the missing-reset ENV precondition with recovery details.

## Demonstration Path
```bash
# Exact, copy-pasteable verification command
mise run test -- tests/unit/test_micro/test_rollback_safety.py -v
```
