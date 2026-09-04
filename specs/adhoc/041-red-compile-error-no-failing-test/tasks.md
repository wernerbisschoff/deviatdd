# Implementation Tasks: `feat/adhoc/041-red-compile-error-no-failing-test`

## Phase 1: RED compile-error classification
**Goal**: Compile-error RED output commits a failing-test boundary and dispatches GREEN, while genuine no-test output still adjudicates

### Tasks

- TSK-041-01: Classify compile-error output as failing RED
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test -- tests/unit/test_micro/test_red_compile_error.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_compile_error.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `_run_red_phase`, whose gate checks only returncode 0, exit 5, and exit 127 with no compile-error awareness (`US-041-01`, `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003`); the new test file pins the classifier contract
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` fixtures. Assert a Python collection traceback (exit 2, `ModuleNotFoundError`) proceeds to GREEN; assert ExUnit markers (`Compilation failed`, `undefined function`) proceed to GREEN; assert exit 0, exit 5 with no-tests text, and exit 127 still route to adjudication; assert mixed compile-error plus passing output proceeds to GREEN
    - **Green**: Implement `_is_compile_error(proc)` with language-agnostic output patterns gated on non-zero returncode; call it in `_run_red_phase` before the adjudication branch so matches fall through to the RED commit and GREEN dispatch
    - **Refactor**: Align pattern constants with neighboring `_is_no_tests_collected` style; keep the check under the 200ms L_max budget
    - **Edge Cases**: Exit 0 output that mentions compile tokens still adjudicates; empty stdout plus stderr with markers and non-zero exit counts as failing
    - **Acceptance**: All new tests pass; exit-0/5/127 routing unchanged; full unit suite stays under 30s

---

## Phase 2: TRAIN_EXHAUSTED clean failure
**Goal**: Budget exhaustion records a FAILED ledger row and exits without an unhandled traceback or blind whole-task retry

### Tasks

- TSK-041-02: Record FAILED row at TRAIN exhaustion
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test -- tests/unit/test_micro/test_red_compile_error.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_compile_error.py`
  - **Rationale**: `_raise_train_exhausted` in `src/deviate/cli/micro.py` raises `PhaseFailedError` with no FAILED ledger row, so the generic retry wrapper reruns the whole task and prints a traceback-style failure (`US-041-02`, `AC-PLAN-004`); tests pin the clean-failure contract
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Drive three RED escalates on a `tmp_git_repo` fixture repo. Assert a FAILED task row with the TRAIN_EXHAUSTED reason lands in `tasks.jsonl`; assert no unhandled traceback escapes the cycle; assert the outer retry loop does not rerun the task
    - **Green**: Append the FAILED transition via `_append_status_transition` at the exhaustion site; mark the raised error so `_execute_task_with_retry` honors it without a rerun
    - **Refactor**: Keep the 3-escalate budget caps untouched; reuse existing ledger helpers, add no new ones
    - **Edge Cases**: Ledger append failure still surfaces a clear error; exhaustion on a non-TDD mode task changes nothing
    - **Acceptance**: FAILED row present with reason; single clean exit; no duplicate FAILED rows from the retry wrapper
  - **Dependency**: TSK-041-01

---

## Phase 3: Evidence guardrail lock-in
**Goal**: The no-failing-test COMPLETE route keeps rejecting empty evidence and docs-only diffs

### Tasks

- TSK-041-03: Pin no-failing-test COMPLETE evidence guards
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test -- tests/unit/test_micro/test_red_compile_error.py`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_compile_error.py`
  - **Rationale**: `_adjudicate_red_no_failing_test` in `src/deviate/cli/micro.py` already calls `_require_tdd_declared_regression_files` on the forward route, but no regression test pins that behavior (`US-041-02`, `AC-PLAN-005`); this task locks it in
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a COMPLETE route with empty evidence quotes is rejected; assert a docs-only diff is rejected; assert a COMPLETE route missing declared regression paths in the diff is rejected
    - **Green**: Keep the existing `_require_tdd_declared_regression_files` and `_require_tdd_completed_evidence` calls; extend only where a test exposes a gap, with minimum code
    - **Refactor**: No production-code churn beyond gap fixes; keep guard messages verbatim for operator greppability
    - **Edge Cases**: Already-satisfied COMPLETE with partial AC evidence stays legal per the existing relaxation; named test_path presence still enforced
    - **Acceptance**: All guard tests pass; no change to GREEN or JUDGE verdict semantics
  - **Dependency**: TSK-041-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (each phase extends the same test file and workstation)

**Critical Dependency Chains**:
- TSK-041-01 must precede TSK-041-02
- TSK-041-02 must precede TSK-041-03

**Risk Hotspots**:
- Classifier over-matching genuine pass output — mitigated by non-zero-exit gating plus exit-0 pin tests
- Duplicate FAILED rows from the outer retry wrapper — mitigated by the exhaustion mark

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_red_compile_error.py` (sequential execution avoids conflicts)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
