## Plan Summary
- **Issue**: ISS-ADH-038 — Migrate test tree to tests/unit convention; fix integration/e2e stubs
- **Implementation Strategy**: Move real suites under `tests/unit/`, rewrite broken intra-suite imports, update stale doc paths, and point `mise` tasks at real suites.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Real unit suites run from tests/unit with no empty collection**
- **Source Outline**: `AO-038-01`
- **Upstream Traceability**: `US-038-01`, `FR-ADHOC-038`, `AC-ADHOC-038-01`
- **Current-Code Evidence**: `mise.toml:[tasks.unit]`
- **Given**: Real suites live under `tests/unit/` with resolved imports
- **When**: Developer runs `mise unit`
- **Then**: Pytest collects and runs the migrated suites with exit code 0 on pass
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Broken intra-suite import fails visibly after the move**
- **Source Outline**: `AO-038-01`
- **Upstream Traceability**: `US-038-01`, `FR-ADHOC-038`, `AC-ADHOC-038-01`
- **Current-Code Evidence**: `tests/unit/test_micro/test_judge_feedback_persist.py`
- **Given**: A migrated suite file holds a stale absolute import
- **When**: Developer runs `mise unit`
- **Then**: The suite reports a collection or import error, not exit 5
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Verification lines and docs resolve to the new layout**
- **Source Outline**: `AO-038-02`
- **Upstream Traceability**: `US-038-02`, `FR-ADHOC-038`, `AC-ADHOC-038-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_CONVENTIONAL_SUITE_DIRS`
- **Given**: Spec Verification lines and docs use the new `tests/unit/` paths
- **When**: Runner scopes a test command from a Verification line
- **Then**: The command resolves to an existing path under the new layout
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Integration and e2e tasks target real suites**
- **Source Outline**: `AO-038-02`
- **Upstream Traceability**: `US-038-02`, `FR-ADHOC-038`, `AC-ADHOC-038-02`
- **Current-Code Evidence**: `mise.toml:[tasks.e2e]`
- **Given**: `mise.toml` declares `integration` and `e2e` tasks
- **When**: Developer runs `mise integration` and `mise e2e`
- **Then**: Integration runs the real pytest suite and e2e delegates to `bats tests/e2e/` via `mise test-e2e`
- **Verification Mode**: automated

## Workstation Mapping
- **mise.toml**: Role in this issue — repoint `unit`, `integration`, `e2e` tasks at real suites
  - **Current State**: `unit` scans whole `tests/` with ignores; `integration` and `e2e` call pytest on empty dirs with exit-5 swallow
  - **Changes Required**: Point `unit` at `tests/unit`; point `integration` at real suites; point `e2e` at `bats tests/e2e/` via `test-e2e`
  - **Integration Surface**: Micro runner suite ladder (`src/deviate/cli/micro.py`), `_CONVENTIONAL_SUITE_DIRS`
- **tests/unit/**: Role in this issue — canonical home for migrated real suites
  - **Current State**: Empty stub directory
  - **Changes Required**: Move `tests/unit/test_cli`, `tests/unit/test_core`, `tests/unit/test_macro`, `tests/unit/test_meso`, `tests/unit/test_micro`, `tests/unit/test_state`, `tests/unit/test_ui`, `tests/unit/test_release`, `tests/unit/core` under it
  - **Integration Surface**: Pytest collection, `tests/conftest.py`, `tests/helpers/`
- **tests/unit/test_micro/test_*.py, tests/helpers/**: Role in this issue — intra-suite absolute imports that break on move
  - **Current State**: Absolute imports like `tests.test_micro.*` and `tests.conftest` resolve at old paths
  - **Changes Required**: Rewrite imports to the new `tests.unit.*` paths
  - **Integration Surface**: Pytest import system, conftest fixtures
- **specs/**: Role in this issue — Verification lines with hardcoded `tests/test_*` paths
  - **Current State**: Design, explore, api, architecture, and task files reference old paths
  - **Changes Required**: Update stale paths to the new layout
  - **Integration Surface**: Runner Verification-line parsing (`_is_partial_verification`)

## Implementation Strategy
- **Phase 1**: Move suites and fix imports — deliverable is green `mise unit`
  - **Files**: `tests/unit/`, `mise.toml`, intra-suite imports
  - **Approach**: Git-move suite dirs under `tests/unit/`, rewrite `tests.test_*` imports, repoint `[tasks.unit]`
  - **Verification**: Run `mise run unit` and confirm collection with no exit 5
- **Phase 2**: Fix integration/e2e tasks and stale doc paths — deliverable is real-suite integration and bats e2e
  - **Files**: `mise.toml`, `specs/` Verification lines and docs
  - **Approach**: Repoint `[tasks.integration]` and `[tasks.e2e]`; sed old `tests/test_*` paths in `specs/`
  - **Verification**: Run `mise run integration` and `mise run test-e2e`

## Data Flow Analysis
- Inputs are the existing suite dirs, `mise.toml` task definitions, and `specs/` Verification lines. Transformations are file moves, import rewrites, task repointing, and doc path updates. Outputs are collected pytest suites under `tests/unit/` and real-suite integration and bats e2e runs. Storage is the filesystem only; no ledger or config state changes.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Cross-import rewrites miss a stale path | High | Medium | Grep for `tests.test_` and `tests/` imports after move; run full unit suite |
| Doc path sweep misses a Verification line | Medium | Medium | Grep `specs/` for `tests/test_` and verify runner parsing |
| Suite move breaks conftest fixture resolution | Medium | Low | Keep `tests/conftest.py` in place; move only suite dirs |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: stale `tests/test_*` path resolves as missing, not silently skipped; empty-suite exit 5 never swallowed as pass
Constraints: GREEN writes only to `tests/`, `mise.toml`, `specs/` doc paths; no new dependencies; no runner strategy or JUDGE scope change

## Integration Points
- **Micro runner suite ladder**: `_CONVENTIONAL_SUITE_DIRS` already maps `unit` to `tests/unit`; ladder picks up `mise unit` once the task points there
- **`mise test-e2e` (bats)**: `e2e` task delegates to the existing bats runner over `tests/e2e/`

## Constitutional Alignment
- **Architecture**: Meso PLAN for a Micro TDD slice; auto-advances to TASKS with no Gate 2 block per constitution §1
- **Testing**: Pytest via `mise unit`, integration via `mise integration`, e2e via bats `mise test-e2e`; coverage target >= 80% per §3
- **Git Isolation**: Work happens on the dedicated issue worktree and branch; no main-branch mutation per §4
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `US-038-01` plus ATDD; `AC-PLAN-003` and `AC-PLAN-004` encode `US-038-02` plus ATDD; RED turns those into failing tests
