# Implementation Tasks: `feat/adhoc/052-e2e-task-preconditions-red-verification`

## Phase 1: Precondition declare and prepare before RED
**Goal**: E2E task cards declare a setup command that the verification path runs first

### Tasks

- TSK-052-01: Verification path prepares task-card preconditions before RED
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro_preconditions.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `_resolve_verification_rungs` plus the RED verification path cited by `AC-PLAN-001` and `AC-PLAN-002` (`US-052-01`, `AO-052-01`); the unit test file proves the prepare-before-RED contract in isolation.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro_preconditions.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert resolution reads optional `preconditions` setup command from the task card, the runner executes it before the verification rungs, and unprepared preconditions fail with the exact setup command named. Preserve existing `_resolve_verification_rungs` ladder behavior for cards without `preconditions`.
    - **Green**: Implement `preconditions` resolution plus a prepare step in `src/deviate/cli/micro.py` before RED verification; gate execution through `is_safe_test_command` plus the mise allowlist; on preparation failure raise a failure naming the exact setup command with exit output verbatim.
    - **Refactor**: Align new helpers with existing `_maybe_run_doctor` and `_run_test_cmd` structure; keep names explicit.
    - **Edge Cases**: Handle poisoned precondition strings by rejecting via the safe-command parser; handle failing setup command by carrying exit output verbatim; handle missing `preconditions` key by skipping preparation.
    - **Acceptance**: Setup command runs first and the RED test fails on its assertion per `AC-PLAN-001`; unprepared preconditions fail naming the setup command per `AC-PLAN-002`.

---

## Phase 2: Named precondition signal with non-error RED status
**Goal**: Missing infrastructure emits a named signal carrying the setup command and RED keeps a non-error status

### Tasks

- TSK-052-02: Named missing-infrastructure signal plus RED prompt rule
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro_precondition_signal.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `EnvNotReadyError` and `_execute_task_with_retry` cited by `AC-PLAN-004` and `AC-PLAN-005` (`US-052-02`, `AO-052-02`); the unit test file proves the named signal plus non-error RED status.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro_precondition_signal.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert missing infrastructure emits the named precondition signal carrying the required setup command plus probe detail, maps to a non-error RED status (not ERROR), and partially available infrastructure resolves to exactly one outcome of RED proof or named signal. Preserve `ENV_NOT_READY` as an accepted alias.
    - **Green**: Implement the named signal emission in `src/deviate/cli/micro.py` (keep `ENV_NOT_READY` alias) and map it to a non-error RED status in `_execute_task_with_retry`.
    - **Refactor**: Keep signal construction in one helper; no new dependencies; no secrets in signal output.
    - **Edge Cases**: Handle malformed env file by naming the file plus parse failure; handle partial infrastructure by emitting exactly one outcome; handle unknown signal names by leaving retry handling unchanged.
    - **Acceptance**: Missing infrastructure emits the named signal with setup command and non-error RED status per `AC-PLAN-004`; partial infrastructure yields exactly one outcome per `AC-PLAN-005`.
  - **Dependency**: TSK-052-01

- TSK-052-03: RED prompt orders named signal instead of ERROR for unavailable services
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run unit`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/auto/red.md`
    - `tests/unit/test_red_prompt_signal.py`
  - **Rationale**: `src/deviate/prompts/auto/red.md` currently orders ERROR status for unavailable services, which contradicts `AC-PLAN-004` (`US-052-02`, `AO-052-02`); the prompt test file locks the corrected rule without a RED cycle.
  - **Details**:
    - **Implementation**: Replace the unavailable-services ERROR rule in `src/deviate/prompts/auto/red.md` with the named precondition signal plus non-error RED status; state that the signal always names the setup command.
    - **Refactor**: Keep prompt wording short and consistent with existing handover manifest status values.
    - **Edge Cases**: Handle partially available infrastructure by requiring exactly one outcome; handle existing ERROR usages by leaving non-infrastructure errors unchanged.
    - **Acceptance**: Prompt rule test asserts non-error status plus setup-command naming per `AC-PLAN-004` and `AC-PLAN-005`.
  - **Dependency**: TSK-052-02

---

## Phase 3: Bounded RED verification for child-process E2E tests
**Goal**: Child-process E2E tests verify only the bounded subset within the task card timeout

### Tasks

- TSK-052-04: Bounded RED subset for child-process E2E verification
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro_bounded_red.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `_run_test_cmd` cited by `AC-PLAN-003` (`US-052-01`, `AO-052-01`); the unit test file proves RED runs only the bounded verification subset and never the full E2E ladder for child-process tests.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro_bounded_red.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert an E2E verification that starts a child API process selects only the bounded subset command within the task card timeout and never expands to the full E2E ladder. Preserve full-ladder behavior for non-RED phases.
    - **Green**: Implement bounded command selection for child-process E2E RED in `src/deviate/cli/micro.py` (`_run_test_cmd` or the RED verification caller), scoped to the card timeout.
    - **Refactor**: Keep detection logic beside `_resolve_verification_rungs`; avoid new config surface.
    - **Edge Cases**: Handle absent preconditions during bounded RED by emitting the named signal; handle timeout by stopping at the card limit; handle non-child-process E2E by leaving the ladder unchanged.
    - **Acceptance**: Bounded subset runs within the card timeout and never the full ladder per `AC-PLAN-003`.
  - **Dependency**: TSK-052-01

---

## Phase 4: Full ladder regression
**Goal**: Confirm the complete suite still passes after all slices land

### Tasks

- TSK-052-05: Full unit plus E2E regression check
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run unit`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/red.md`
  - **Rationale**: Touches no new behavior; re-runs the existing ladder to prove `AC-PLAN-001` through `AC-PLAN-005` land without regression (`US-052-01`, `US-052-02`).
  - **Details**:
    - **Implementation**: Run `mise run unit`; run `mise run test-e2e` when the environment supports it; record results.
    - **Refactor**: No production changes; fix only regressions introduced by TSK-052-01 through TSK-052-04.
    - **Edge Cases**: Handle missing E2E infrastructure by reporting the named signal with the setup command instead of a failure.
    - **Acceptance**: Unit suite passes; E2E passes or reports the named precondition signal; coverage stays above 80 percent.
  - **Dependency**: TSK-052-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 (logical dependency order)

**Critical Dependency Chains**:
- TSK-052-01 must precede TSK-052-02, TSK-052-04, and TSK-052-05
- TSK-052-02 must precede TSK-052-03
- TSK-052-04 must precede TSK-052-05

**Risk Hotspots**:
- Setup command runs untrusted strings — reuse `is_safe_test_command` plus mise allowlist gate before execution
- Bounded rule skips real coverage — bound only RED for child-process E2E; full ladder still runs after tasks complete
- Signal rename breaks retry handling — keep `ENV_NOT_READY` as alias alongside the new named signal

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
