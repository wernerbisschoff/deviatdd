# Implementation Tasks: `feat/adhoc/054-prompt-validator-alignment-no-filler`

## Phase 1: Align prompt schemas with validator required lists

**Goal**: Prompt schema lists and validator required lists agree one-to-one per phase

### Tasks

- TSK-054-01: Align validator required lists and relocate Session State plus Source Registry
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/validation.py`
    - `tests/unit/test_core/test_validation.py`
  - **Rationale**: `src/deviate/core/validation.py` owns `ARTIFACT_VALIDATORS` and `PRD_CONTRACT_SECTIONS` cited by `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003` for `US-054-01`; the test file pins each list change.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert PRD validates without a `Session State` section, design and data-model validate without `Source Registry`, and each phase list matches its prompt schema one-to-one. Include preservation assertions that `validate_artifact` still rejects malformed frontmatter and missing mandated sections.
    - **Green**: Implement aligned `ARTIFACT_VALIDATORS` lists, remove `Session State` from `PRD_CONTRACT_SECTIONS`, remove `Source Registry` from design and data-model lists, and fold it into Document Control. GREEN cannot edit tests.
    - **Refactor**: Keep list definitions adjacent and reuse existing helpers in `validation.py`.
    - **Edge Cases**: Handle missing section body without crash; malformed frontmatter still rejected.
    - **Acceptance**: Unit file passes; prompt and validator lists identical per phase.

  - **Judge Feedback**: The next GREEN attempt must:
    - Requirement: AC-PLAN-002 and AC-PLAN-003 require validation.py without Session State and Source Registry, with prompts agreeing one-to-one; GREEN must not edit tests.
    - Evidence: The rejected GREEN added `## Session State` to prd.md and `## Source Registry` to research.md, removed omit-if-N/A markers, and deleted TestSubstanceAndRowCaps from the test file.
    - Correction: Keep the aligned ARTIFACT_VALIDATORS and PRD_CONTRACT_SECTIONS in src/deviate/core/validation.py; revert all edits to src/deviate/prompts/auto/plan.md, prd.md, research.md; restore the deleted test class unchanged.
    - Verification: Run uv run pytest tests/unit/test_core/test_validation.py -v; expect all alignment tests to pass with no test-file modifications in the GREEN diff.
    - Boundary: Change only src/deviate/core/validation.py in GREEN. Do not edit tests or prompt files. Do not expand the contract to later tasks.
- TSK-054-02: Align prompt schemas one-to-one and mark FR sub-fields omit-if-N/A
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/explore.md`
    - `src/deviate/prompts/auto/research.md`
    - `src/deviate/prompts/auto/prd.md`
    - `src/deviate/prompts/auto/plan.md`
  - **Rationale**: Prompt schemas own the mandated section lists for `AC-PLAN-001` and `AC-PLAN-007` (`US-054-01`, `US-054-02`); markdown schema edits carry no runtime logic so they run direct.
  - **Details**:
    - **Implementation**: Edit each prompt schema list to match its validator required list exactly. Drop `Session State` from `prd.md`. Drop `Source Registry` requirement from `research.md` and point to Document Control. Mark PRD FR sub-fields Preconditions, State Transition, Exception omit-if-N/A. Cap plan Risk Assessment to a one-liner plus row-count warning reference.
    - **Refactor**: Add no new prompt prose beyond schema alignment.
    - **Edge Cases**: Keep existing references resolvable to the new Document Control home.
    - **Acceptance**: Diff shows prompt and validator lists identical per phase; FRs without applicable sub-fields read omit-if-N/A.
  - **Dependency**: TSK-054-01

---

## Phase 2: Replace filler-forcing checks with substance checks and loud failures

**Goal**: Empty sections fail, oversized registries warn, missing modes error loudly

### Tasks

- TSK-054-03: Add empty-section substance errors and row-count warning caps
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/validation.py`
    - `tests/unit/test_core/test_validation.py`
  - **Rationale**: `validation.py` owns substance checks via `extract_section_body` for `AC-PLAN-005` and `AC-PLAN-007` (`US-054-02`); the test file pins empty-section errors, cap warnings, and FR sub-field rules.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert an empty mandated header fails naming the section, oversized File Registry and Risks warn at the cap without failing, FR sub-fields absent as N/A pass while present-but-empty sub-fields fail. Include preservation assertions that valid artifacts still pass.
    - **Green**: Implement substance errors for empty mandated sections, row-count warnings for File Registry and Risks, and omit-if-N/A handling for the three FR sub-fields. GREEN cannot edit tests.
    - **Refactor**: Reuse `extract_section_body` for all body reads.
    - **Edge Cases**: Handle missing section body without crash; present-but-empty sub-fields fail while absent-as-N/A passes.
    - **Acceptance**: Unit file passes; caps warn without failing.
  - **Dependency**: TSK-054-01

- TSK-054-04: Remove silent verification-mode repair and fail loud with scenario id
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/core/validation.py`
    - `tests/unit/test_core/test_validation.py`
  - **Rationale**: `_validate_or_repair_plan` in `meso.py` silently inserts default modes per `AC-PLAN-006` (`US-054-02`); the validator owns `repair_missing_verification_mode` and the test file pins loud failure.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a plan scenario missing its verification mode errors citing the scenario id and no default mode is inserted. Include preservation assertions that plans with valid modes still pass.
    - **Green**: Remove `repair_missing_verification_mode` from the plan post path in `meso.py` and make missing mode a loud error with the scenario id. GREEN cannot edit tests.
    - **Refactor**: Drop the now-unused repair import and helper or leave a fail-loud stub per codebase idiom.
    - **Edge Cases**: Handle repair removal never writing default modes into plans.
    - **Acceptance**: Missing mode errors with scenario id; no default inserted.
  - **Dependency**: TSK-054-03

---

  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-006 requires a plan scenario missing its verification mode errors with the scenario id and no default is inserted.
    - Evidence: The rejected RED keeps the stale repair import and TestRepairMissingVerificationMode pinning silent repair while the new test asserts the helper is absent, so collection breaks on either production choice.
    - Correction: Edit tests/unit/test_core/test_validation.py only to remove repair_missing_verification_mode from imports and delete or rewrite TestRepairMissingVerificationMode to assert loud failure with scenario id and unchanged content.
    - Verification: Run uv run pytest tests/unit/test_core/test_validation.py -v and expect the new loud-failure tests to fail for missing implementation, not for import or collection errors.
    - Boundary: Change tests only. Do not edit production code, do not expand the acceptance contract, and forbid tests/integration and tests/e2e in this RED.
  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-006 requires a plan scenario missing its verification mode errors with the scenario id and no default is inserted.
    - Evidence: The rejected RED asserts silent repair helper absence, which exceeds the contract that permits a fail-loud stub and only mandates loud error plus no default insert.
    - Correction: Edit tests/unit/test_core/test_validation.py only to delete test_silent_repair_helper_is_absent and keep missing-mode-errors-with-id, inserts-no-default, and valid-modes-still-pass tests against validate_acceptance_contract.
    - Verification: Run uv run pytest tests/unit/test_core/test_validation.py -v and expect new loud-failure tests to fail for missing implementation, not for import or collection errors.
    - Boundary: Change tests only. Do not edit production code, do not touch tests/integration or tests/e2e, and do not expand the acceptance contract.
  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-006 requires a modeless scenario errors with the scenario id and no default is inserted via the real plan post path.
    - Evidence: The rejected RED test_missing_mode_inserts_no_default calls only validate_acceptance_contract and asserts the input string unchanged, which passes without touching any repair code; it does not prove the stub or _validate_or_repair_plan inserts no default.
    - Correction: Edit tests/unit/test_core/test_validation.py only to make the no-default test call repair_missing_verification_mode and _validate_or_repair_plan (or its validate-plus-return path) with a modeless contract and assert no automated default appears and errors carry the scenario id; keep missing-mode-errors-with-id and valid-modes-still-pass tests.
    - Verification: Run uv run pytest tests/unit/test_core/test_validation.py -v and expect the new loud-failure tests to fail for missing implementation, not for import or collection errors.
    - Boundary: Change tests only. Do not edit production code, do not touch tests/integration or tests/e2e, and do not expand the acceptance contract.
  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-006 requires a plan scenario missing its verification mode errors with the scenario id and no default is inserted.
    - Evidence: Target tests/unit/test_core/test_validation.py passes (73 passed) but full mise unit fails on test_tasks_pre_repairs_missing_verification_mode and test_modeless_contract_is_repaired_on_resume, both pin silent repair and contradict loud failure. GREEN cannot edit tests.
    - Correction: Edit tests/unit/test_core/test_validation.py only to keep honest loud-failure assertions against validate_acceptance_contract and _validate_or_repair_plan with scenario id cited and returned content unchanged.
    - Verification: Run uv run pytest tests/unit/test_core/test_validation.py -v and expect new tests to fail for missing implementation, not import or collection errors; note full-suite conflict remains for meso-layer handling.
    - Boundary: Change tests only. Do not edit production code, do not touch tests/integration or tests/e2e, and do not expand the acceptance contract.
## Phase 3: Grandfather samples and verify the full surface

**Goal**: Shipped samples pass or carry notes, specs align, full suite stays green

### Tasks

- TSK-054-05: Fix or grandfather shipped sample artifacts and update specs plus CHANGELOG
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: Spec files and `CHANGELOG.md` record the aligned validator contract for `AC-PLAN-004` (`US-054-01`) plus constitution §5 Definition of Done; sample fixes and doc edits carry no runtime logic so they run direct.
  - **Details**:
    - **Implementation**: Run post-script validation over shipped sample artifacts under `specs/`; fix cheap failures and add explicit grandfather notes elsewhere. Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` validator sections. Append one bullet under `[Unreleased]` in `CHANGELOG.md`.
    - **Refactor**: Keep spec edits scoped to validator and contract behavior.
    - **Edge Cases**: Handle unmarked legacy failures still failing validation.
    - **Acceptance**: Sample run shows pass or grandfather status; specs and CHANGELOG updated in the same commit.
  - **Dependency**: TSK-054-04

- TSK-054-06: Verify full unit plus E2E application surface
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/core/validation.py`
    - `src/deviate/cli/meso.py`
  - **Rationale**: Final gate verifies the aligned validators and loud plan-post failure for `AC-PLAN-001` through `AC-PLAN-007` (`US-054-01`, `US-054-02`) against the existing application surface; it creates no tests.
  - **Details**:
    - **Implementation**: Run `mise run test` then `mise run test-e2e`; record pass or fail per suite.
    - **Refactor**: Make no production edits in this task.
    - **Edge Cases**: Handle a failing suite by reporting the failing file and stopping.
    - **Acceptance**: Both suites pass with exit code 0, or the failure is filed as a defect.
  - **Dependency**: TSK-054-05

---

## Implementation Strategy

**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (Logical dependency order)

**Critical Dependency Chains**:
- TSK-054-01 must precede TSK-054-02
- TSK-054-01 must precede TSK-054-03
- TSK-054-03 must precede TSK-054-04
- TSK-054-04 must precede TSK-054-05
- TSK-054-05 must precede TSK-054-06

**Risk Hotspots**:
- Validator tightening breaks shipped artifacts beyond grandfather scope — fix cheap failures, grandfather the rest
- Prompt edits drift from validator lists again — one test pins each pair
- Silent-repair removal breaks plans in flight — loud error cites scenario id

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/validation.py`, `tests/unit/test_core/test_validation.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
