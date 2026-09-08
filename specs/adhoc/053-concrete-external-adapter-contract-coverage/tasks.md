# Implementation Tasks: `feat/adhoc/053-concrete-external-adapter-contract-coverage`

## Phase 1: Prompt split rules for adapter transport
**Goal**: Plan and tasks prompts split concrete adapter criteria from port behavior criteria

### Tasks

- TSK-053-01: Add adapter split rule to plan and tasks prompts
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_meso/test_adapter_split.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/plan.md`
    - `src/deviate/prompts/auto/tasks.md`
    - `tests/unit/test_meso/test_adapter_split.py`
  - **Rationale**: `US-053-01` plus `AC-PLAN-001` needs the plan split rule in `plan.md`; `US-053-01` plus `AC-PLAN-002` needs the adapter contract card rule in `tasks.md`; the test file proves both rules fire on adapter naming and stay silent otherwise
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_meso/test_adapter_split.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert plan prompt text contains an adapter-split directive keyed on external SDK naming; assert tasks prompt text contains a concrete contract row rule (signature, auth, request identity, response lookup); assert both stay absent before the change
    - **Green**: Implement split directive in `plan.md` execution sequence plus concrete contract checklist; implement adapter split directive plus per-method contract row rule in `tasks.md` construction step; scope GREEN to the two prompt files only
    - **Refactor**: Align wording with existing prompt style; keep directives short and keyed on explicit SDK naming
    - **Edge Cases**: Handle non-adapter plans by keeping the rule silent unless an external SDK is named
    - **Acceptance**: Unit test passes; plan names adapter and emits separate criteria; adapter task cards carry the four contract rows

## Phase 2: Red inspection and judge fake-only rejection rules
**Goal**: RED inspects installed signatures offline and JUDGE rejects fake-only integration claims

### Tasks

- TSK-053-02: Add offline signature inspection and import-boundary rules to red prompt
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_adapter_red.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/red.md`
    - `tests/unit/test_micro/test_adapter_red.py`
    - `tests/conftest.py`
  - **Rationale**: `US-053-01` plus `AC-PLAN-003` needs import-safety and deferred-construction test rules in `red.md`; `US-053-01` plus `AC-PLAN-006` needs the offline signature inspection directive in `red.md`; `conftest.py` reuse keeps git isolation for any repo-touching fixture
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_adapter_red.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert red prompt text contains an offline-only signature inspection directive with version pinning; assert it contains import-boundary plus auth-negative test directives naming dependency evidence
    - **Green**: Implement offline inspect directive plus import-boundary and auth negative test rules in `red.md` traceability and test-writing steps; no production code outside the prompt file
    - **Refactor**: Keep directives conditional on named installed dependency; forbid network-call language
    - **Edge Cases**: Handle missing dependency by pinning the declared version; handle missing auth by failing with dependency evidence and no live calls
    - **Acceptance**: Unit test passes; RED authors import-safety plus deferred-construction tests with offline inspection
  - **Dependency**: TSK-053-01

- TSK-053-03: Add fake-only rejection and port-behavior exemption to judge prompt
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_adapter_judge.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/judge.md`
    - `tests/unit/test_micro/test_adapter_judge.py`
  - **Rationale**: `US-053-02` plus `AC-PLAN-004` needs the fake-only `COMPLIANCE_VIOLATION` category in `judge.md`; `US-053-02` plus `AC-PLAN-005` needs the pure port-behavior exemption in `judge.md`; the test file proves rejection fires on integration claims with fake-only evidence and passes otherwise
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_adapter_judge.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert judge prompt text contains a fake-only violation category with evidence-naming repair; assert it contains the no-integration-claim exemption for pure port-behavior tasks
    - **Green**: Implement fake-only rejection category plus correction contract in `judge.md` evaluation steps; implement exemption clause for tasks with no integration claim; scope GREEN to the judge prompt file only
    - **Refactor**: Match existing verdict manifest wording; name missing concrete evidence in feedback contract
    - **Edge Cases**: Handle pure port-behavior tasks by passing fake coverage without demanding adapter evidence
    - **Acceptance**: Unit test passes; fake-only integration claim fails with named missing evidence; pure port task passes
  - **Dependency**: TSK-053-02

- TSK-053-04: Run full unit regression and prompt consistency check
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/auto/plan.md`
    - `src/deviate/prompts/auto/tasks.md`
    - `src/deviate/prompts/auto/red.md`
    - `src/deviate/prompts/auto/judge.md`
  - **Rationale**: Verifies the full `US-053-01` plus `US-053-02` prompt chain (`AC-PLAN-001` through `AC-PLAN-006`) stays consistent with no regressions in the existing unit suite
  - **Details**:
    - **Implementation**: Run `uv run pytest tests/unit -v`; confirm the three new test files pass alongside the existing suite; read the four prompt files and confirm split, contract, inspection, rejection, and exemption rules agree
    - **Refactor**: Fix only regressions caused by TSK-053-01 through TSK-053-03; make no new behavior changes
    - **Edge Cases**: Handle pre-existing failures by reporting them without masking new results
    - **Acceptance**: Full unit suite passes; the four prompt rules read consistently end to end
  - **Dependency**: TSK-053-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Verification batch

**Critical Dependency Chains**:
- TSK-053-01 must precede TSK-053-02
- TSK-053-02 must precede TSK-053-03
- TSK-053-03 must precede TSK-053-04

**Risk Hotspots**:
- Split rule fires on non-adapter tasks; key on explicit external SDK naming only
- Judge rejects valid fake port tests; exemption clause covers no-integration-claim tasks
- Signature checks hit network; red directive states offline-only inspection

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none; each prompt file is touched by exactly one TDD task

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
