# Implementation Tasks: `feat/009-god-files-strangler/001-micro-extraction`

## Phase 1: Characterization lock
**Goal**: Lock micro public behavior with failing-first tests before the move

### Tasks

- TSK-001-01: Characterization tests for micro public surface
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro -q`
  - **Files**:
    - `tests/unit/test_micro/test_micro_parity.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-009-01` plus `AC-PLAN-002` and `AC-PLAN-005`. Touches the new parity file (locks `_run_all`, app objects, `_find_all_pending_tasks`, `existing_verification_suites`, `deviate --help` snapshot) and reads `micro.py` as the characterization source.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_micro/test_micro_parity.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert public names import from `deviate.cli.micro` (`micro_app`, `red_app`, `green_app`, `judge_app`, `refactor_app`, `e2e_app`, `execute_app`, `hotfix_app`, `_run_all`, `_find_all_pending_tasks`, `existing_verification_suites`), each Typer app exposes its commands, and the `deviate --help` snapshot matches the recorded baseline.
    - **Green**: Implement no production code — characterization target already exists; make the new tests pass against current `src/deviate/cli/micro.py` unchanged.
    - **Edge Cases**: Handle snapshot drift by recording the exact pre-move help text as the baseline artifact.
    - **Acceptance**: Tests land in their own commit before any move commit with zero production edits in that commit.

---

## Phase 2: Verbatim package extraction
**Goal**: Move micro logic into a package behind a re-export shim with zero behavior change

### Tasks

- TSK-001-02: Verbatim move of micro.py into micro package plus re-export shim
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_micro -q`
  - **Files**:
    - `src/deviate/cli/micro/__init__.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-009-01` and `US-009-02` plus `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-004`, `AC-PLAN-005`. Creates the package (verbatim-moved logic, same public names) and shrinks `micro.py` to a re-export-only shim under 100 lines.
  - **Details**:
    - **Implementation**: Move `src/deviate/cli/micro.py` verbatim into `src/deviate/cli/micro/__init__.py` (byte-identical logic, no renames, no behavior edits). Replace `src/deviate/cli/micro.py` with re-exports only of every public name consumed by `cli/__init__.py`, `core/converge.py`, and `cli/meso.py` — zero logic, under 100 lines. Keep `__init__.py` imports unchanged. Verify no submodule imports the shim path and TSK-001-01 tests pass unchanged.
    - **Acceptance**: `wc -l src/deviate/cli/micro.py` reports under 100 lines; grep finds zero `from deviate.cli.micro import` inside `src/deviate/cli/micro/`; no behavior edit shares the move commit.
  - **Dependency**: `TSK-001-01`

- TSK-001-03: Re-point direct callers to micro submodules
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro -q`
  - **Files**:
    - `tests/unit/test_micro/test_micro_import_targets.py`
    - `src/deviate/cli/__init__.py`
    - `src/deviate/core/converge.py`
    - `src/deviate/cli/meso.py`
  - **Rationale**: Serves `US-009-03` plus `AC-PLAN-006`. Touches the new import-target test (locks direct-submodule resolution) and the three caller files that switch off the shim.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_micro/test_micro_import_targets.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert `_run_all` and app objects import from `deviate.cli.micro` submodules, `converge.py` resolves `_find_all_pending_tasks` without the shim module, and `meso.py` resolves `existing_verification_suites` without the shim module.
    - **Green**: Update imports in `src/deviate/cli/__init__.py`, `src/deviate/core/converge.py`, and `src/deviate/cli/meso.py` to import directly from `src/deviate/cli/micro/` submodules. GREEN cannot edit tests.
    - **Edge Cases**: Handle lazy/function-local imports in `converge.py` and `meso.py` by updating them in place to the submodule path.
    - **Acceptance**: Zero remaining `from deviate.cli.micro import` references outside the shim itself.
  - **Dependency**: `TSK-001-02`

---

## Phase 3: Parity gate and shim deletion
**Goal**: Prove post-move parity and remove the shim in its own commit

### Tasks

- TSK-001-04: [E2E] Parity gate, quality gate, and shim deletion
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test && mise run lint && mise run format-check && mise run test-e2e`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_micro_parity.py`
  - **Rationale**: Serves `US-009-01` and `US-009-03` plus `AC-PLAN-002`, `AC-PLAN-003`, `AC-PLAN-006`. Deletes the shim (only after TSK-001-03 leaves zero shim imports) and re-runs parity plus quality gates.
  - **Details**:
    - **Implementation**: Confirm zero shim imports remain via grep. Delete `src/deviate/cli/micro.py` in its own commit. Re-run the full suite, `ruff check`, `ruff format --check`, the `--help` snapshot comparison, and `bats tests/e2e/`. Restore on any failure.
    - **Acceptance**: Shim file is gone, all imports resolve to submodules, parity re-passes, and lint plus format checks exit zero.
  - **Dependency**: `TSK-001-03`

---

## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_micro_parity.py`
