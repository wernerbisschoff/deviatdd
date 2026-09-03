# Implementation Tasks: `feat/adhoc/038-test-tree-unit-convention`

## Phase 1: Move suites and fix imports

**Goal**: Real suites run from `tests/unit/` via `mise unit` with no empty collection

### Tasks

- TSK-038-01: Move real suites under tests/unit and fix intra-suite imports
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `mise.toml`
    - `tests/unit/test_cli/`
    - `tests/unit/test_micro/`
    - `tests/unit/test_micro/test_judge_feedback_persist.py`
    - `tests/helpers/cycle_driver.py`
  - **Rationale**: `US-038-01` with `AC-PLAN-001` needs suites collected from `tests/unit/`; `AC-PLAN-002` needs stale absolute imports to fail visibly. `mise.toml` repoints `[tasks.unit]`; suite dirs move; import files rewrite `tests.test_*` paths.
  - **Details**:
    - **Implementation**: Git-move `tests/unit/test_cli`, `tests/unit/test_core`, `tests/unit/test_macro`, `tests/unit/test_meso`, `tests/unit/test_micro`, `tests/unit/test_state`, `tests/unit/test_ui`, `tests/unit/test_release`, `tests/unit/core` under `tests/unit/`; keep `tests/conftest.py` in place
    - **Implementation**: Rewrite absolute imports (`tests.test_micro.*`, `tests.conftest`, `tests.helpers.*`) to `tests.unit.*` paths in moved files
    - **Implementation**: Repoint `[tasks.unit]` to `uv run pytest tests/unit`
    - **Refactor**: Remove moved empty source dirs; keep import style consistent with repo
    - **Edge Cases**: Handle missed stale path by grepping `tests.test_` after move; collection error surfaces, never exit 5
    - **Acceptance**: `mise run unit` collects and runs migrated suites with exit 0 on pass; stale import reports collection error

## Phase 2: Fix integration/e2e tasks and stale doc paths

**Goal**: Integration and e2e tasks target real suites; docs resolve to the new layout

### Tasks

- TSK-038-02: Repoint integration and e2e tasks at real suites
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run integration`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `mise.toml`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: `US-038-02` with `AC-PLAN-004` needs `integration` on the real pytest suite and `e2e` on bats. `mise.toml` declares both tasks; bats file proves the e2e target exists.
  - **Details**:
    - **Implementation**: Point `[tasks.integration]` at the real pytest suite path; drop the exit-5 swallow
    - **Implementation**: Point `[tasks.e2e]` at `mise run test-e2e` (`bats tests/e2e/`); drop the pytest-on-empty-dir stub
    - **Refactor**: Keep task descriptions accurate and short
    - **Edge Cases**: Handle empty `tests/integration/` by running the real suite path, never swallowing exit 5 as pass
    - **Acceptance**: `mise run integration` runs the real pytest suite; `mise run test-e2e` runs bats over `tests/e2e/`

- TSK-038-03: Update stale Verification lines and doc paths to tests/unit
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run unit`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `specs/adhoc/038-test-tree-unit-convention/plan.md`
    - `specs/adhoc/038-test-tree-unit-convention/tasks.md`
  - **Rationale**: `US-038-02` with `AC-PLAN-003` needs every Verification line to resolve under the new layout. Spec files hold the hardcoded `tests/test_*` paths the runner scopes from.
  - **Details**:
    - **Implementation**: Sed old `tests/test_*` paths in `specs/` to the new `tests/unit/*` layout
    - **Implementation**: Verify each Verification line scopes to an existing path via runner parsing (`_is_partial_verification`)
    - **Refactor**: Keep surrounding doc prose unchanged; touch paths only
    - **Edge Cases**: Handle stale path resolving as missing file, not silently skipped
    - **Acceptance**: Grep `specs/` for `tests/test_` returns no stale Verification line; scoped command resolves to an existing path

---

  - **Judge Feedback**: The next RED attempt must: author a failing test for AC-PLAN-003 that (1) greps specs/ Verification lines for stale tests/test_* paths and fails when any remain, and (2) checks runner scoping (_is_partial_verification or equivalent) resolves each Verification command to an existing path under tests/unit/. Then the next GREEN attempt must sed all stale specs/ paths to tests/unit/* so the test passes. Keep surrounding doc prose unchanged; touch paths only.
## Implementation Strategy

**Execution Order**:
1. Phase 1 -> Phase 2 (suite move first; task repointing and doc sweep follow)

**Critical Dependency Chains**:
- TSK-038-02 must precede TSK-038-03
- TSK-038-01 must precede TSK-038-02

**Risk Hotspots**:
- Cross-import rewrites miss a stale path; grep `tests.test_` and run full unit suite after move
- Doc path sweep misses a Verification line; grep `specs/` for `tests/test_` and verify runner parsing
- Suite move breaks conftest fixture resolution; keep `tests/conftest.py` in place

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `mise.toml`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
