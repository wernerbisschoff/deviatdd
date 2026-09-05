# Implementation Tasks: `feat/adhoc/042-revert-green-stale-red-sha-recovery`

## Phase 1: Revert-green stale SHA recovery

**Goal**: JUDGE `revert_green` recovers from a stale stored RED SHA to a safe on-branch boundary and refuses only when nothing safe resolves.

### Tasks

- TSK-042-01: Stale rewritten RED remaps, current SHA passes through, empty SHA refuses
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test -- tests/unit/test_micro/test_revert_green_stale_sha.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_revert_green_stale_sha.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `_require_revert_green_boundary` for `US-042-01` with `AC-PLAN-001` (rewritten remap plus reset), `AC-PLAN-002` (ancestor passthrough), and `AC-PLAN-006` (empty SHA refusal); the new unit file encodes those three contracts as failing tests first.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_revert_green_stale_sha.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert rewritten stale SHA remaps to same-subject on-branch RED with `RED_SHA_REWRITTEN` log of old and new SHA; ancestor SHA returns unchanged with no remap log; empty SHA raises `ROLLBACK_BOUNDARY_MISSING`. Build fixture repos with `tmp_git_repo` plus `_git_env` and mock `deviate.cli.micro._run_pytest`.
    - **Green**: Implement recovery in `_require_revert_green_boundary` scoped to `src/deviate/cli/micro.py`: keep `current` passthrough; remap `rewritten` kind via `_resolve_rewritten_sha` with old/new SHA log; raise `ROLLBACK_BOUNDARY_MISSING` on empty SHA. Leave `_resolve_revert_red_boundary` untouched. GREEN edits no tests.
    - **Refactor**: Reuse cached git captures and existing `_git_env` helpers; keep refusal errors plain with no traceback past the cycle.
    - **Edge Cases**: Handle exact subject match only for remap; handle missing git object without shell interpolation of SHAs.
    - **Acceptance**: The three RED cases pass; existing `test_rebase_red_sha.py` still passes.

- TSK-042-02: Already-reverted and tasks.md-safe fallback resolve, unresolvable refuses without HEAD move, tasks.md survives
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run test -- tests/unit/test_micro/test_revert_green_stale_sha.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_revert_green_stale_sha.py`
  - **Rationale**: `src/deviate/cli/micro.py` extends the same resolver for `US-042-01` with `AC-PLAN-003` (unresolvable plain refusal, HEAD unchanged), `AC-PLAN-004` (discarded RED beside feedback resolves without reset past tasks.md-safe commit), `AC-PLAN-005` (recovery keeps latest committed tasks.md plus feedback commit), and `AC-PLAN-007` (reroute train completes rollback); the unit file encodes those four contracts as failing tests first.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_revert_green_stale_sha.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert discarded RED beside a judge feedback commit resolves to the current-train boundary at or after the tasks.md-safe SHA; dangling SHA with no match raises a plain refusal with HEAD byte-identical before and after; recovery reset plus feedback commit leaves latest committed tasks.md content intact; a rerouted train fixture completes rollback to the remapped boundary. Use `tmp_git_repo` plus `_git_env` and mock `deviate.cli.micro._run_pytest`.
    - **Green**: Implement in `_require_revert_green_boundary` scoped to `src/deviate/cli/micro.py`: resolve `already_reverted` to current HEAD or pre-GREEN train boundary never older than the tasks.md-safe SHA; fall back to latest tasks.md-safe boundary only when it is an ancestor of HEAD; else raise the plain refusal with no reset; route recovery through `_execute_rollback` tasks.md restore. GREEN edits no tests.
    - **Refactor**: Keep `revert_red` resolver and JUDGE verdict semantics unchanged; keep resolver to a fixed small set of rev-parse calls.
    - **Edge Cases**: Handle resolver never resetting to a non-ancestor of HEAD; handle tasks.md absent from branch by refusing rather than guessing.
    - **Acceptance**: The four RED cases pass; existing `test_rollback_safety.py` still passes; full unit file passes under `mise run test`.
  - **Dependency**: `TSK-042-01`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 TSK-042-01 -> TSK-042-02 (resolver core first, fallback matrix second)

**Critical Dependency Chains**:
- TSK-042-01 must precede TSK-042-02

**Risk Hotspots**:
- Weak subject match resets to an unrelated commit — accept exact subject match only and refuse when no safe boundary resolves
- Recovery reset drops tasks.md — route through `_execute_rollback` tasks.md restore and keep the survival test

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_revert_green_stale_sha.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
