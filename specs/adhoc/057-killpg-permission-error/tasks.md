# Implementation Tasks: `feat/adhoc/057-killpg-permission-error`

## Phase 1: EPERM-safe timeout cleanup
**Goal**: Timeout escalation swallows `PermissionError` and returns 124 with partial output.

### Tasks

- TSK-057-01: Widen `_kill_process_group` to swallow EPERM on timeout path
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/_safe_commands.py`
    - `tests/unit/test_cli/test_timeout_safe_command.py`
  - **Rationale**: `_safe_commands.py` owns `_kill_process_group` and the timeout escalation branch (US-057-01, AC-PLAN-001); the test file holds the timeout-path regression harness covering ESRCH today and needs the EPERM case (US-057-01, AC-PLAN-001, AC-PLAN-002 preservation).
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_cli/test_timeout_safe_command.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert `_kill_process_group` swallows `PermissionError` on SIGTERM and SIGKILL, and `run_safe_command` returns returncode 124 with partial output and no exception when `os.killpg` raises `PermissionError`; assert existing ESRCH swallow, invalid-pid early return, and 127 spawn-error path still hold.
    - **Green**: Implement `_kill_process_group()` in `src/deviate/cli/_safe_commands.py` to catch `PermissionError` alongside `ProcessLookupError`; confirm timeout-branch SIGTERM/SIGKILL calls route through it.
    - **Refactor**: Keep the except clause narrow (`ProcessLookupError`, `PermissionError` only), no bare `OSError` widening.
    - **Edge Cases**: Handle EPERM on SIGTERM alone, EPERM on SIGKILL alone, EPERM on both; invalid pids return early; genuine spawn errors keep the 127 path.
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_timeout_safe_command.py -v` passes; caller receives 124 with partial output on EPERM.

- TSK-057-02: Closing verification batch for timeout cleanup
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/cli/_safe_commands.py`
    - `tests/unit/test_cli/test_timeout_safe_command.py`
  - **Rationale**: Re-runs the application timeout-cleanup surface to confirm AC-PLAN-001 (EPERM returns 124) and AC-PLAN-002 (ESRCH/invalid-pid/127 behavior unchanged) hold together on US-057-01; no new tests, verification only.
  - **Details**:
    - **Implementation**: Run `mise unit` scoped to the timeout test file, then `mise lint` on touched files.
    - **Refactor**: No production code changes; fix only test pollution found by the run.
    - **Edge Cases**: Confirm untrusted command strings still reject with 127 and path-qualified executables still reject.
    - **Acceptance**: Full `mise unit` passes; EPERM timeout returns 124, ESRCH/invalid-pid/127 paths unchanged.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> done (TSK-057-01 -> TSK-057-02)

**Critical Dependency Chains**:
- TSK-057-01 must precede TSK-057-02

**Risk Hotspots**:
- Over-broad except clause catches unrelated errors; catch exactly `PermissionError` next to `ProcessLookupError`.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none (single phase).

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
