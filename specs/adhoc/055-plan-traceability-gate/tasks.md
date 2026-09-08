# Implementation Tasks: `feat/adhoc/055-plan-traceability-gate`

## Phase 1: Traceability Validator Plus Plan Gate
**Goal**: `plan pre` rejects untraceable issues with named gaps and passes traceable ones

### Tasks

- TSK-055-01: Add issue traceability validator with subset diagnostics
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/validation.py`
    - `tests/unit/test_core/test_validation.py`
  - **Rationale**: `US-055-01` plus `AC-PLAN-003` and `AC-PLAN-005` need a shared validator that names exactly the absent token family. `validation.py` owns reusable contract checks. The test file pins the validator shapes.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `validate_issue_traceability` returns NOT_READY naming only the missing family on a stories-only body, NOT_READY naming all missing fields on an empty body, and READY on a body with stories plus tracing plus AO-token outlines. Assert the diagnostic lists each missing field plus the repair step.
    - **Green**: Implement `validate_issue_traceability(body)` in `src/deviate/core/validation.py` with section plus AO-token checks that mirror the PRD FAIL-plus-detail shape. Keep scope to the validator and its helpers.
    - **Refactor**: Align naming and return shape with `validate_macro_contract`. Remove duplicate section-scan logic.
    - **Edge Cases**: Handle empty body by reporting all fields missing. Handle AO tokens present but outline section absent by naming the section gap.
    - **Acceptance**: Unit suite passes. Partial issue names only the absent family, not a blanket failure.

- TSK-055-02: Gate `plan pre` on the traceability validator
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_meso_contracts.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/unit/test_cli/test_meso_contracts.py`
  - **Rationale**: `US-055-01` plus `AC-PLAN-001` and `AC-PLAN-002` need `_plan_pre` to fail fast on untraceable issues. `meso.py` owns the `plan pre` gate. The contract test file pins READY and NOT_READY shapes.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_meso_contracts.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `plan pre` against an issue lacking stories, tracing, or outlines returns NOT_READY naming each missing field plus the repair step. Assert a traceable issue returns READY with resolved spec path and plan target. Include preservation assertions that ISSUE_NOT_FOUND still returns for a missing file and READY shape keeps existing keys.
    - **Green**: Implement the gate in `_plan_pre` in `src/deviate/cli/meso.py`: read the issue body via `_find_issue_file`, call `validate_issue_traceability`, emit NOT_READY with `missing_fields` plus `repair_hint` on failure. Keep scope to the gate wiring.
    - **Refactor**: Keep the gate call in one helper so `_tasks_pre` and `meso run` share the diagnostic path. Remove inline section checks.
    - **Edge Cases**: Handle path traversal in the issue source by failing closed with ISSUE_NOT_FOUND. Handle legacy `ISS-NNN` and epic-prefix ids identically.
    - **Acceptance**: Unit suite passes. `plan pre` on a legacy fixture names the gap. No change to READY consumers beyond the added gate.
  - **Dependency**: TSK-055-01

## Phase 2: Repair Path Plus Template Agreement
**Goal**: Legacy issues repair to READY and new shard and adhoc issues pass without repair

### Tasks

- TSK-055-03: Add repair helper that restores missing sections then re-passes the gate
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_meso.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/unit/test_cli/test_meso.py`
  - **Rationale**: `US-055-02` plus `AC-PLAN-004`, `AC-PLAN-005`, and `AC-PLAN-006` need a repair path that inserts absent sections without touching author content. `meso.py` owns the repair entry point. The test file pins repair-then-READY behavior.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_meso.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert the repair helper on a legacy body inserts stories, tracing, and outlines and a rerun of `plan pre` reports READY. Assert incomplete repair still reports NOT_READY naming the remaining gap. Assert a complete legacy issue reports READY without repair. Assert repair never edits present text, only inserts absent sections. Use the shared `tmp_git_repo` fixture for any git file writes.
    - **Green**: Implement the repair helper in `src/deviate/cli/meso.py` that inserts only absent sections into the issue file and revalidates via `validate_issue_traceability`. Refuse writes outside `specs/` workstation paths.
    - **Refactor**: Share section-name constants with the validator. Keep repair output deterministic in section order.
    - **Edge Cases**: Handle repair on an already-complete issue by writing nothing. Handle a still-incomplete repair by returning NOT_READY with the remaining gap named.
    - **Acceptance**: Unit suite passes. Legacy fixture flows NOT_READY to repair to READY. Complete legacy issues skip repair.
  - **Dependency**: TSK-055-02

- TSK-055-04: Align plan, shard, and adhoc templates plus specs and CHANGELOG
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run check`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/prompts/auto/plan.md`
    - `src/deviate/prompts/auto/shard.md`
    - `src/deviate/prompts/commands/deviate-adhoc.md`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `US-055-01` and `US-055-02` plus all six `AC-PLAN-NNN` need template wording that matches the gate section and token names, and spec plus CHANGELOG updates in the same commit per the plan strategy. No behavior change lives here, so IMMEDIATE fits.
  - **Details**:
    - **Implementation**: Document the NOT_READY diagnostic plus repair step in the pre-flight step of `plan.md`. Confirm `Upstream Requirement Tracing` tokens in `shard.md` and section names in `deviate-adhoc.md` match the gate checks, and change only drifting wording. Document gate status values, the repair command, and the template contract in both specs. Append one bullet under `[Unreleased]` in `CHANGELOG.md`.
    - **Refactor**: Keep template edits to identifier wording. Keep spec edits to gate and repair contract sections.
    - **Edge Cases**: Handle gate checks on section names only, not prose, so prose edits stay minimal and never widen the gate.
    - **Acceptance**: `mise run check` passes. New shard and adhoc issues pass the gate without repair. Commit contains code plus spec plus CHANGELOG.
  - **Dependency**: TSK-055-03

## Phase 3: Full Verification
**Goal**: Whole suite and checks pass on the issue branch

### Tasks

- TSK-055-05: Run full test plus check ladder and confirm gate end to end
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `specs/adhoc/055-plan-traceability-gate/plan.md`
    - `specs/adhoc/055-plan-traceability-gate/tasks.md`
  - **Rationale**: All `AC-PLAN-001` through `AC-PLAN-006` need a closing pass that proves the gate, repair, and templates hold together. This task verifies application behavior only and creates no tests, so it carries no Test Strategy.
  - **Details**:
    - **Implementation**: Run `mise run test` and `mise run check`. Run `plan pre` against a legacy fixture to confirm NOT_READY, then repair, then READY. Confirm no task touched files outside `meso.py`, `validation.py`, and prompt templates.
    - **Refactor**: Fix only regressions this verification exposes. Record any unrelated failure as pending work.
    - **Edge Cases**: Handle a full-suite failure by tracing it to the owning task phase before any fix.
    - **Acceptance**: Full suite exits 0. Checks pass. Gate plus repair confirmed end to end.
  - **Dependency**: TSK-055-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (gate before repair before docs and verification)

**Critical Dependency Chains**:
- TSK-055-01 must precede TSK-055-02 must precede TSK-055-03 must precede TSK-055-04 must precede TSK-055-05

**Risk Hotspots**:
- Gate rejects currently passing traceable issues; pin READY happy-path tests on the existing issue format first
- Repair helper overwrites author content; repair inserts absent sections only and never edits present text
- Scope creeps into Micro RED and GREEN behavior; reject changes outside `meso.py`, `validation.py`, and prompt templates

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/meso.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
