# Implementation Tasks: `feat/010-filed-github-issues/001-task-state-recovery`

## Phase 1: Canonical task state recovery
**Goal**: Resolve one latest valid task transition for each issue and task.

### Tasks

- TSK-001-01: Resolve canonical task state across retries and sibling issues
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `src/deviate/cli/micro/surface.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-010-01 and AC-PLAN-001 require ordered canonical state; these files must isolate `(issue_id, id)` and preserve retry transitions.
  - **Details**:
    - **Red**: Add unit cases in `tests/unit/test_cli/test_micro.py` for repeated RED, GREEN, retry, and sibling issue rows. Assert exactly the latest valid row for each `(issue_id, id)` and forbid `tests/integration/` and `tests/e2e/`.
    - **Green**: Update `_collect_latest_task_records` and the ledger transition deduplication path. Key rows by issue and task, retain ordered records, and replace only a same-status latest row.
    - **Acceptance**: `mise unit` passes with canonical state selection and append-only transition behavior.
    - **Edge Cases**: Keep a retry transition visible when an earlier row has the same task ID but a different status.
  - **Dependency**: None

  - **Judge Feedback**: The next GREEN attempt must:
    - Requirement: AC-PLAN-001 requires issue-scoped canonical state and append-only retry transitions.
    - Evidence: The current GREEN change makes append_task_transition return True for a repeated RED transition after a sibling task row, failing tests/unit/test_state/test_task_retry_transitions.py.
    - Correction: Update src/deviate/state/ledger.py to key state by issue and task while preserving rejection of repeated same-status transitions across intervening sibling rows. Do not edit the retained RED tests.
    - Verification: Run mise unit; expect test_retry_records_red_and_green_after_rollback and the AC-PLAN-001 tests to pass.
    - Boundary: Preserve tests/unit/test_cli/test_micro.py and the existing append-only ledger interface. Do not expand the acceptance contract.
## Phase 2: GREEN recovery and cleanup
**Goal**: Permit GREEN only from the latest RED state and clear stale retry metadata after success.

### Tasks

- TSK-001-02: Guard GREEN post and clear successful retry metadata
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro/surface.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-010-01, AC-PLAN-002, AC-PLAN-003, and AC-PLAN-004 require RED-to-GREEN recovery and complete session cleanup in `_green_post_kernel`.
  - **Details**:
    - **Red**: Add focused unit cases in `tests/unit/test_cli/test_micro.py` for retry recovery, non-RED rejection, and cleanup. Assert one `GREEN` append with `GREEN_POST_OK`, stable `GREEN_GUARD_REJECTED` naming the current state, and cleared `judge_rejected`, `pending_judge_action`, `train_feedback`, `failure_kind`, and matching pending feedback. Use `tests/unit/` only; forbid `tests/integration/` and `tests/e2e/`.
    - **Green**: Update `_green_post_kernel` to resolve the latest task state before appending. Accept only `RED`, return the stable rejection for every other state, and clear all listed retry fields and matching pending judge feedback after successful GREEN.
    - **Acceptance**: GREEN writes one append-only transition and leaves no stale retry routing metadata.
    - **Edge Cases**: Keep the guard error state-specific and prevent cleanup when GREEN is rejected.
  - **Dependency**: TSK-001-01

## Phase 3: Regression verification
**Goal**: Run the repository unit suite after the recovery changes.

### Tasks

- TSK-001-03: Verify task state recovery and GREEN post regression coverage
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `src/deviate/cli/micro/surface.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-010-01 and AC-PLAN-001 through AC-PLAN-004 require a final application regression check across canonical state, GREEN guards, and cleanup.
  - **Details**:
    - **Implementation**: Run `mise unit` and confirm the focused recovery tests and existing unit tests pass.
    - **Acceptance**: The unit suite exits with status 0 and covers all four `AC-PLAN-NNN` scenarios.

---

## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- `src/deviate/cli/micro/surface.py`
- `tests/unit/test_cli/test_micro.py`
