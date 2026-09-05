# Implementation Tasks: `feat/adhoc/044-judge-rollback-database-recovery`

## Phase 1: Migration recovery hook
**Goal**: JUDGE rollback detects migration-bearing reverts and runs the configured recovery hook, while non-migration reverts return the existing trace unchanged

### Tasks

- TSK-044-01: Migration-bearing revert runs the recovery hook, non-migration revert skips it
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_rollback_database_recovery.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/state/config.py`
    - `tests/unit/test_micro/test_rollback_database_recovery.py`
  - **Rationale**: `US-044-01` plus `AC-PLAN-001` require the hook to run after a migration-bearing reset; `AC-PLAN-004` requires non-migration resets to skip it. `micro.py` owns `_execute_rollback` where detection plus invocation land. `config.py` owns the `[rollback]` hook resolver that `_execute_rollback` reads.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert the hook subprocess runs with boundary SHA plus task id in the environment when the reverted diff touches a migration path, and assert the hook never runs when the reverted diff holds zero migration paths and the trace returns unchanged. Mock the hook subprocess and `_run_pytest`. Use the shared `tmp_git_repo` fixture for every git call.
    - **Green**: Implement the migration-path constant plus reverted-diff detection in `_execute_rollback`, add the `[rollback]` hook resolver in `config.py` returning command plus timeout, run the hook via argument list without shell after clean before `tasks.md` restore. GREEN edits zero test files.
    - **Refactor**: Keep patterns in one constant, keep hook invocation in one helper, match existing `_execute_rollback` error style
    - **Edge Cases**: Handle empty reverted diff by skipping the hook; handle hook timeout by failing loudly with output attached
    - **Acceptance**: Migration-bearing revert runs the hook and later test commands succeed; non-migration revert skips the hook with the trace unchanged

---

## Phase 2: Loud failure semantics
**Goal**: Missing hook, failing hook, and stale-boundary rollbacks all stop with named errors and never report a silent pass

### Tasks

- TSK-044-02: Missing hook, hook failure, and stale boundary keep loud named errors
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_rollback_database_recovery.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_database_recovery.py`
  - **Rationale**: `US-044-02` plus `AC-PLAN-002` require a named missing-hook error with the manual recovery action; `US-044-01` plus `AC-PLAN-003` require hook output attached on failure; `US-044-02` plus `AC-PLAN-005` require existing `ROLLBACK_*` refusals unchanged. All three behaviors live in `_execute_rollback` in `micro.py`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert rollback raises naming the hook plus the manual recovery action at the rolled-back boundary when zero hook is configured, assert rollback raises with hook output attached on non-zero exit or timeout, assert missing or stale boundary SHA returns the current `ROLLBACK_*` refusal text unchanged. Mock the hook subprocess and `_run_pytest`. Use the shared `tmp_git_repo` fixture for every git call.
    - **Green**: Raise the missing-hook error and the hook-failure error with output attached before `tasks.md` restore in `_execute_rollback`; leave boundary validation order untouched so `ROLLBACK_*` refusals fire first. GREEN edits zero test files.
    - **Refactor**: Reuse one error constructor for both new errors, keep messages naming the hook command and the boundary SHA
    - **Edge Cases**: Handle hook command injection via config value by running via argument list without shell; handle boundary SHA plus task id passed via environment only
    - **Acceptance**: Each failure raises with its named message and branch position stays at the rolled-back boundary; zero path reports a silent pass
  - **Dependency**: TSK-044-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (hook plumbing must exist before error semantics attach to it)

**Critical Dependency Chains**:
- TSK-044-01 must precede TSK-044-02

**Risk Hotspots**:
- Hook runs too long and blocks JUDGE — enforce hook timeout and fail loudly on expiry
- Pattern list misses a migration layout — keep patterns in one constant covered by tests
- Behavior change leaks into non-migration rollbacks — gate hook strictly on non-empty migration set

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_rollback_database_recovery.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
