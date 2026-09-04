# Implementation Tasks: `feat/adhoc/040-judge-rollback-preserves-tasks-md`

## Phase 1: Clamp Rollback Boundary at tasks.md Commit
**Goal**: JUDGE rollback never removes committed `tasks.md`; unsafe resets are refused.

### Tasks

- TSK-040-01: Clamp rollback boundary to tasks.md commit
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_rollback_safety.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
  - **Rationale**: `US-040-01` with `AC-PLAN-001` and `AC-PLAN-003` require the reset to land at or after the commit that created `tasks.md`; `micro.py` owns `_execute_rollback` and the test file pins the contract.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_rollback_safety.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Build a fixture repo with committed `tasks.md` plus RED and GREEN commits, run `_execute_rollback` with a boundary predating the `tasks.md` commit, assert `git ls-tree -r HEAD --name-only` still lists `tasks.md` at its latest committed state.
    - **Green**: Implement a helper in `src/deviate/cli/micro.py` that resolves the `tasks.md`-creating commit on the active branch via `git log` and advances any older boundary to it; leave the uncommitted-or-absent `tasks.md` path on existing behavior. GREEN cannot edit tests.
    - **Refactor**: Align the helper with existing boundary-resolver naming and keep one log query per rollback with no retry loop.
    - **Edge Cases**: Handle amended or rebased history by keeping the existing `ROLLBACK_STALE_BOUNDARY` ancestry refusal when the safe commit is not an ancestor.
    - **Acceptance**: New unit cases pass, `mise run check` passes, and meso run after rollback reuses existing Tasks without regeneration (`AC-PLAN-001`, `AC-PLAN-003`).

  - **Judge Feedback**: The next GREEN attempt must: keep the new TestRollbackPreservesTasksMd behavior for stale JUDGE boundaries that predate tasks.md creation, but must not disable GREEN discard.
1. Reproduce both regressions first: run tests/unit/test_cli/test_micro.py::TestJudgeTrainRollback::test_judge_revert_green_advances_red_commit_sha and tests/unit/test_micro/test_green_budget.py::TestResolvePreRedWalksPastDocsFeedback::test_resolve_pre_red_sha_returns_parent_of_red_not_docs and confirm they pass.
2. Fix src/deviate/cli/micro.py _execute_rollback: when safe_sha postdates RED/GREEN, do not set boundary_sha = safe_sha with no reset. Instead reset to the intended boundary then restore tasks.md content from safe_sha (git checkout safe_sha -- tasks.md path or equivalent), or only clamp when safe_sha is an ancestor of the RED commit.
3. Keep single git log query, no retry loop, keep ROLLBACK_STALE_BOUNDARY refusal when safe commit is not an ancestor of HEAD, and keep uncommitted-or-absent tasks.md on existing behavior.
4. Verify: uv run pytest tests/unit/test_micro/test_rollback_safety.py tests/unit/test_cli/test_micro.py::TestJudgeTrainRollback tests/unit/test_micro/test_green_budget.py -v passes.
- TSK-040-02: Refuse unsafe rollback and preserve recovery refs
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_rollback_safety.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
  - **Rationale**: `US-040-01` with `AC-PLAN-002` and `AC-PLAN-004` require refusal before any reset plus reachable per-attempt recovery refs; both behaviors live in `_execute_rollback` and `_preserve_agent_work` in `micro.py`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_rollback_safety.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a boundary predating the `tasks.md` commit raises a plain `PhaseFailedError` before any reset with branch, index, and untracked files unchanged, and assert all prior recovery refs stay resolvable with no ref overwritten after a later rollback or refusal.
    - **Green**: Raise a plain `PhaseFailedError` in `src/deviate/cli/micro.py` before any reset when no safe boundary resolves; keep recovery-ref and snapshot behavior unchanged. GREEN cannot edit tests.
    - **Refactor**: Reuse the existing feedback-commit step unchanged after the clamped reset; keep `RollbackSnapshot` record shape and ordering.
    - **Edge Cases**: Handle refusal with dirty index and untracked files present by leaving them untouched; handle repeated JUDGE attempts by never overwriting an existing recovery ref.
    - **Acceptance**: New unit cases pass, `mise run check` passes, and no `tasks.md` state is lost on any refusal path (`AC-PLAN-002`, `AC-PLAN-004`).
  - **Dependency**: `TSK-040-01`

---

  - **Judge Feedback**: RED tests for TSK-040-02 contradict the committed AC-PLAN-001 contract. Both the old TestRollbackPreservesTasksMd tests and the new TestRefuseUnsafeRollback tests use a baseline boundary predating the tasks.md commit with a resolvable tasks.md commit, but expect opposite outcomes (restore versus refusal), so both suites cannot pass. Plan Workstation Mapping and Implementation Strategy require: resolve the tasks.md-creating commit, advance or restore when it resolves, and refuse only when no safe boundary resolves. The TSK-040-01 judge feedback also mandates keeping TestRollbackPreservesTasksMd behavior while still discarding GREEN. Next RED must: keep test_stale_boundary_keeps_tasks_md_listed and test_stale_boundary_keeps_tasks_md_content passing, and rewrite the two TestRefuseUnsafeRollback cases to target the genuine no-safe-boundary path (safe commit empty or not an ancestor of HEAD, e.g. amended or rebased history), asserting PhaseFailedError before any reset with branch, index, untracked files, and prior recovery refs unchanged. Next GREEN must: refuse only on that path, and otherwise reset to the intended boundary then restore tasks.md from the safe commit.
## Implementation Strategy
**Execution Order**:
1. Phase 1 task TSK-040-01 -> TSK-040-02 (refusal builds on the clamp helper)

**Critical Dependency Chains**:
- TSK-040-01 must precede TSK-040-02

**Risk Hotspots**:
- Boundary clamp misresolves on amended or rebased history; mitigated by the existing ancestry refusal.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_rollback_safety.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
