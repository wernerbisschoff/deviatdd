# Implementation Tasks: `feat/adhoc/059-judge-rollback-missing-red-boundary`

## Phase 1: Preserve rollback evidence at the boundary
**Goal**: Keep missing `revert_green` boundaries explicit and retain all available rollback evidence.

### Tasks

- TSK-059-01: Preserve rollback evidence when `revert_green` lacks a RED boundary
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/state/ledger.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
  - **Rationale**: User story `US-059-01` and `AC-PLAN-001` require `DEVIATDD_BUG` with preserved `head_sha` and `recovery_ref`.
    The rollback boundary helpers must retain nullable ledger evidence and keep the branch unchanged.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_rollback_safety.py`, add unit tests for available and empty evidence. Assert `DEVIATDD_BUG`, exact `head_sha` and `recovery_ref` fields, unchanged HEAD, and no `HEAD~1`; forbid integration and e2e tests.
    - **Green**: Update `_require_revert_green_boundary` and `_execute_rollback` in `src/deviate/cli/micro.py` to reject missing boundaries without inferred Git resets. Preserve `TaskRecord.head_sha` and `TaskRecord.recovery_ref` as explicit nullable evidence.
    - **Acceptance**: Valid rollback behavior remains unchanged when `session.red_commit_sha` exists.

  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-001, AC-PLAN-002, and AC-PLAN-003 require runner-level missing-boundary behavior.
    - Evidence: The current tests call _append_judge_revert_jsonl directly and do not exercise validation, rollback prevention, or JUDGE classification.
    - Correction: Replace the helper-only assertions in tests/unit/test_micro/test_rollback_safety.py with unit tests that invoke the real boundary and JUDGE handling paths for populated and empty evidence.
    - Verification: Run mise unit and confirm the tests fail before implementation, then assert DEVIATDD_BUG, preserved fields, unchanged HEAD, no HEAD~1, no retry, and no feedback commit.
    - Boundary: Keep the test strategy unit-only and preserve valid revert_green behavior when session.red_commit_sha exists.
- TSK-059-02: Stop JUDGE advancement after a missing rollback boundary
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_run.py`
  - **Rationale**: User story `US-059-01` and `AC-PLAN-002`/`AC-PLAN-003` require a fatal harness report and `/deviate-green` recovery route.
    The JUDGE handler must skip feedback advancement and retry after `ROLLBACK_BOUNDARY_MISSING`.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_run.py`, add unit coverage for `deviate micro run`. Assert `DEVIATDD_BUG`, explicit empty or available evidence, `/deviate-green`, no retry, and no `_commit_judge_feedback_and_advance`; forbid integration and e2e tests.
    - **Green**: Update `_is_fatal_missing_revert_green_boundary` and `_run_judge_phase` in `src/deviate/cli/micro.py` to classify the boundary error as a harness failure, report evidence, skip advancement, and return without retry.
    - **Edge Cases**: Keep empty `head_sha` and `recovery_ref` empty. Never infer `HEAD~1` or reset before reporting the failure.

## Phase 2: Verification
**Goal**: Confirm the rollback boundary change passes the repository test and quality checks.

### Tasks

- TSK-059-03: Verify rollback boundary handling and JUDGE recovery behavior
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit && mise integration && mise e2e && mise check`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
    - `tests/unit/test_micro/test_run.py`
  - **Rationale**: User story `US-059-01` and `AC-PLAN-001` through `AC-PLAN-003` require complete application verification.
    The focused rollback and JUDGE paths must pass the repository quality ladder.
  - **Details**:
    - **Implementation**: Run the full configured unit, integration, e2e, and check commands after both TDD tasks complete.
    - **Acceptance**: Record a clean exit from every configured verification command.

---

  - **Judge Feedback**: The next GREEN attempt must:
    - Requirement: TSK-059-03 requires clean exits from `mise unit`, `mise integration`, `mise e2e`, and `mise check`.
    - Evidence: The task ledger records TSK-059-03 as RED and provides no successful command results.
    - Correction: Run all four commands and record their clean exit results in the task evidence.
    - Verification: Confirm each command exits with code 0.
    - Boundary: Preserve the completed rollback implementation and existing tests. Do not expand the acceptance contract.
## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py`
