# Implementation Tasks: `feat/005-acceptance-gates/005-prompt-spec-alignment`

## Phase 1: Align prompt templates and pin with tests
**Goal**: RED, GREEN, and REFACTOR templates state the checkpoint and gate semantics, with content tests that fail on stale wording.

### Tasks

- TSK-005-01: State RED checkpoint completion with warning advisory in templates
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-red.md`
    - `src/deviate/prompts/auto/red.md`
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Rationale**: AC-PLAN-001 (`US-005-11`, `FR-005-06`) requires both RED templates to state checkpoint completion with a warning advisory and carry no rejection statement; the test file pins that wording against regressions.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_meso/test_auto_prompt_templates.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `deviate-red.md` and `auto/red.md` content states completion with a warning advisory handed to GREEN, and assert no rejection statement survives in either template.
    - **Green**: Edit `src/deviate/prompts/commands/deviate-red.md` and `src/deviate/prompts/auto/red.md` with the checkpoint-completion and handoff-advisory wording; remove any rejection statement. Touch only these two templates. GREEN cannot edit tests.
    - **Refactor**: Align phrasing between the two RED templates and the existing `RedHandoffAdvisory` terms; keep edits to wording only, no runner changes.
    - **Edge Cases**: Handle a template that already carries partial checkpoint wording by completing it; handle stale rejection phrases by deleting every occurrence.
    - **Acceptance**: `mise unit` passes; grep finds checkpoint and advisory text in both templates and no rejection statement.

- TSK-005-02: State GREEN blocking gate and REFACTOR regression gate in templates
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/green.md`
    - `src/deviate/prompts/auto/refactor.md`
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Rationale**: AC-PLAN-002 and AC-PLAN-003 (`US-005-11`, `FR-005-06`) require the GREEN template to describe the blocking gate with JUDGE routing and the REFACTOR template to describe the regression gate; the test file pins both wordings.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_meso/test_auto_prompt_templates.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `auto/green.md` states a failing suite routes to JUDGE via train feedback and the RED warning does not block start; assert `auto/refactor.md` states a non-zero post-polish test result fails the phase.
    - **Green**: Edit `src/deviate/prompts/auto/green.md` with the blocking-gate and JUDGE-routing wording; edit `src/deviate/prompts/auto/refactor.md` with the regression-gate wording. Touch only these two templates. GREEN cannot edit tests.
    - **Refactor**: Keep gate wording consistent with the micro runner terms in `src/deviate/cli/micro.py`; wording only, no runner changes.
    - **Edge Cases**: Handle existing train-feedback text in `green.md` by extending it, not replacing it; handle the test-modification invariant in `refactor.md` by keeping it intact beside the new gate text.
    - **Acceptance**: `mise unit` passes; grep finds gate text in both templates and the RED-warning non-blocking statement in `green.md`.
  - **Dependency**: `TSK-005-01`

## Phase 2: Align specs and changelog
**Goal**: Spec documents record the verification-mode contract and gate semantics without contradiction; the changelog carries the user-visible bullet.

### Tasks

- TSK-005-03: Document contracts and gates in specs plus changelog bullet
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: AC-PLAN-004 (`US-005-12`, `FR-005-06`) requires both specs to document the verification-mode contract line, acceptance criteria traceability, handoff advisory, and gate semantics; AC-PLAN-005 (`US-005-13`) requires the `[Unreleased]` changelog bullet for the user-visible gate change.
  - **Details**:
    - **Implementation**: Edit `specs/DeviaTDD-api.md` with the verification-mode contract line, the task record acceptance criteria field, the handoff advisory, and the GREEN/REFACTOR gates; edit `specs/DeviaTDD-architecture.md` with the RED checkpoint, GREEN gate with JUDGE routing, and REFACTOR regression gate; append one bullet under `[Unreleased]` in `CHANGELOG.md` describing the gate behavior changes.
    - **Refactor**: Keep spec wording consistent with the template terms from TSK-005-01 and TSK-005-02; remove or fix any contradicting section in either spec.
    - **Edge Cases**: Handle a missing `[Unreleased]` section by creating it; handle contradicting legacy gate text by updating it to the checkpoint and gate semantics.
    - **Acceptance**: Grep finds the contract line in the API spec, the gate terms in the architecture spec with no contradicting section, and the bullet under `[Unreleased]`; `mise run check` passes.
  - **Dependency**: `TSK-005-02`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (Template wording and its pinning tests first, then spec and changelog prose)

**Critical Dependency Chains**:
- TSK-005-01 must precede TSK-005-02
- TSK-005-02 must precede TSK-005-03

**Risk Hotspots**:
- Stale rejection phrase survives in a template — content tests plus grep scans fail on forbidden phrases
- Spec wording contradicts runner behavior — each spec claim traces to the micro runner code with no runner change
- Shared test file touched by two tasks — run sequentially, never in parallel

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_meso/test_auto_prompt_templates.py` (TSK-005-01, TSK-005-02)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
