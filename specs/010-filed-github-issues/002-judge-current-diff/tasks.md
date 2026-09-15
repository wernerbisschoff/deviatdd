# Implementation Tasks: `feat/010-filed-github-issues/002-judge-current-diff`

## Phase 1: Stable contradiction detection
**Goal**: Stop JUDGE retry selection after repeated incompatible requirement interpretations.

### Tasks

- TSK-002-01: Return one stable contradiction result for incompatible JUDGE requirements
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/core/judge_contradiction.py`
    - `tests/unit/test_core/test_judge_contradiction.py`
  - **Rationale**: US-010-02 and AC-PLAN-003 require stable handling of incompatible JUDGE interpretations; the detector must distinguish conflict, ABA oscillation, and compatible refinement.
  - **Details**:
    - **Red**: Add focused tests in `tests/unit/test_core/test_judge_contradiction.py`. Assert explicit incompatible requirements and A→B→A feedback return contradiction, compatible refinement continues, and empty history returns no contradiction. Use `tests/unit/` only; forbid `tests/integration/` and `tests/e2e/`.
    - **Green**: Update `detect_judge_requirement_contradiction` to compare requirement identity and polarity, detect ABA oscillation, preserve compatible refinements, and return `JUDGE_REQUIREMENT_CONTRADICTION` for repeated incompatible requirements.
    - **Acceptance**: Existing compatible requirement behavior remains accepted by the detector.
    - **Edge Cases**: Treat empty and single-entry histories as non-contradictory.
  - **Dependency**: None

## Phase 2: Current-contract JUDGE evaluation
**Goal**: Evaluate the active contract against the current RED-to-HEAD diff and preserve behavior only when required.

### Tasks

- TSK-002-02: Apply current-diff verdicts and route stable contradiction halts
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/cli/micro/surface.py`
    - `src/deviate/prompts/auto/judge.md`
    - `tests/unit/test_micro/test_judge.py`
  - **Rationale**: US-010-02 and AC-PLAN-001 through AC-PLAN-003 require JUDGE to use the active contract and current diff; these files assemble evidence, state evaluation rules, and verify verdict routing.
  - **Details**:
    - **Red**: Add focused tests in `tests/unit/test_micro/test_judge.py`. Assert the injected RED-to-HEAD and dirty diff reaches JUDGE with the active contract, absent unrequired behavior does not reject, required preservation absence rejects, and repeated incompatible feedback returns `JUDGE_REQUIREMENT_CONTRADICTION` without another retry interpretation. Use `tests/unit/` only; forbid `tests/integration/` and `tests/e2e/`.
    - **Green**: Update `_assemble_judge_injected_diff`, `_run_judge_phase`, and `_apply_judge_verdict` to evaluate current diff evidence against the active contract, apply preservation checks only for explicit contract requirements, and stop retry routing on contradiction. Update `STEP_1` and `STEP_3` in `judge.md` to state the same current-contract and current-diff rule.
    - **Acceptance**: JUDGE returns pass or actionable retry for valid current-diff outcomes and one stable contradiction halt for incompatible feedback.
    - **Edge Cases**: Keep relative diff paths and preserve existing pass, retry, and required-preservation outcomes.
  - **Dependency**: TSK-002-01

## Phase 3: Regression verification
**Goal**: Run the application unit suite after JUDGE changes.

### Tasks

- TSK-002-03: Verify current-diff JUDGE and contradiction regression coverage
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Files**:
    - `src/deviate/core/judge_contradiction.py`
    - `src/deviate/cli/micro/surface.py`
    - `tests/unit/test_core/test_judge_contradiction.py`
    - `tests/unit/test_micro/test_judge.py`
  - **Rationale**: US-010-02 and AC-PLAN-001 through AC-PLAN-003 require a final application regression check for current-diff verdicts, preservation rules, and contradiction halts.
  - **Details**:
    - **Implementation**: Run `mise unit` and confirm the contradiction and current-diff JUDGE tests pass.
    - **Acceptance**: The unit suite exits with status 0 and covers all three `AC-PLAN-NNN` scenarios.

---

## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- `src/deviate/cli/micro/surface.py`
- `tests/unit/test_micro/test_judge.py`
