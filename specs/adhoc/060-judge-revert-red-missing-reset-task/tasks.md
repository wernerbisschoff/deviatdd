# Implementation Tasks: `feat/adhoc/060-judge-revert-red-missing-reset-task`

## Phase 1: Revert-red rollback ordering and ENV gating

**Goal**: Complete git reset before env reset and report missing reset as gated ENV precondition

### Tasks

- TSK-060-01: Reorder revert_red to land git reset first and preserve RED evidence
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
  - **Rationale**: Serves US-060-01 via AC-PLAN-001 and AC-PLAN-003. `_execute_rollback` must reset HEAD before the env hook runs.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_micro/test_rollback_safety.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert HEAD resets to `reset_to` with no `[tasks.reset]` entry and orphan RED commit stays reachable via `recovery_ref`.
    - **Green**: Reorder `revert_red` in `_execute_rollback` to capture rollback trace and land git reset before `_maybe_reset_isolated_env`; convert missing-reset `EnvNotReadyError` into gated ENV report carrying `head_sha`, `reset_to`, `recovery_ref`.
    - **Edge Cases**: Handle nonzero-exit reset as `ENV_NOT_READY` with detail; never delete RED evidence on missing reset.
    - **Acceptance**: Unit task rollback skips `mise run reset` with no ENV error.

- TSK-060-02: Surface missing-reset ENV precondition with recovery details on micro run
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_run.py`
  - **Rationale**: Serves US-060-01 via AC-PLAN-002 and AC-PLAN-004. `_apply_judge_verdict` must surface the gated ENV report.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_micro/test_run.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert `deviate micro run` surfaces missing-reset ENV precondition with `head_sha`, `reset_to`, `recovery_ref`, and nonzero-exit reset still raises `ENV_NOT_READY`.
    - **Green**: Implement verdict reporting in `_apply_judge_verdict` to persist RED ledger row and gate next RED/GREEN until a `reset` task exists; keep unit/unstamped `test_strategy` path skipping the reset hook.
    - **Edge Cases**: Handle existing `[tasks.reset]` with nonzero exit as blocking `ENV_NOT_READY`; keep `revert_green` path unchanged.
  - **Dependency**: TSK-060-01

- TSK-060-03: [VERIFY] Full regression across unit, integration, and E2E
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_micro/test_rollback_safety.py`
    - `tests/unit/test_micro/test_run.py`
  - **Rationale**: Serves US-060-01 via AC-PLAN-001 through AC-PLAN-004. Confirms no regression in rollback paths.
  - **Details**:
    - **Implementation**: Run `mise unit`, then `mise integration` and `mise e2e` when available; confirm revert_green path intact and RED evidence preserved.
  - **Dependency**: TSK-060-02

---

## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`
