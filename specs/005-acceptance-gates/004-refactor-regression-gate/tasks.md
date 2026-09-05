# Implementation Tasks: `feat/005-acceptance-gates/004-refactor-regression-gate`

## Phase 1: Blocking REFACTOR regression gate
**Goal**: Make the post-polish test run in REFACTOR block completion on regression

### Tasks

- TSK-004-01: Blocking REFACTOR regression gate on `_run_test_cmd` returncode
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_refactor.py`
  - **Rationale**: `src/deviate/cli/micro.py` holds `_run_refactor_phase`, the gate site for `US-005-09`/`US-005-10` via `AC-PLAN-001` through `AC-PLAN-004`; `tests/unit/test_micro/test_refactor.py` pins the fail and pass branches of that gate.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_refactor.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert non-zero `_run_test_cmd` result raises `PhaseFailedError` with output tail and appends no `COMPLETED` row (`AC-PLAN-001`); assert zero result runs `_run_format_cmd`, appends `COMPLETED`, and transitions to `IDLE` (`AC-PLAN-002`); assert unchanged passing suite passes with no extra side effects (`AC-PLAN-003`); assert `skip_refactor` and already-`COMPLETED` bypass the gate (`AC-PLAN-004`). Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture. Add preservation assertions that the existing refactor pre/post contracts and rollback behavior still hold.
    - **Green**: Implement the gate in `_run_refactor_phase` in `src/deviate/cli/micro.py`: bind `_run_test_cmd` return value, check `returncode != 0`, raise `PhaseFailedError` with task id and output tail before format or ledger writes; on zero keep the existing format, `COMPLETED` append, commit, and `IDLE` sequence unchanged. GREEN cannot edit tests.
    - **Refactor**: Align error message and branch structure with surrounding phase code idioms; keep the failure path free of format, ledger, and commit side effects.
    - **Edge Cases**: Handle test-command crash (non-zero with empty output) by raising `PhaseFailedError` without a `COMPLETED` row; handle format failure after a passing gate via existing error handling.
    - **Acceptance**: `uv run pytest tests/unit/test_micro/test_refactor.py -v` passes with `_run_pytest` mocked; `mise run check` stays green; no files changed outside the two listed.

---

  - **Judge Feedback**: The next GREEN attempt must: preserve the non-zero raise with output tail before format and ledger writes, add a no-test-command guard using _is_no_test_command that skips the gate like the RED phase does, keep zero-result format plus COMPLETED plus IDLE path unchanged, and prove no regression by running tests/unit/test_micro/test_run.py plus tests/unit/test_micro/test_refactor.py with _run_pytest mocked.
## Implementation Strategy
**Execution Order**:
1. Phase 1 standalone (single task, no dependencies)

**Critical Dependency Chains**:
- None — single task delivers the full gate

**Risk Hotspots**:
- Gate masking agent failure diagnostics — include test output tail in the `PhaseFailedError` message

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
