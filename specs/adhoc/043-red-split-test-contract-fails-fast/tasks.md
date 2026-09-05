# Implementation Tasks: `feat/adhoc/043-red-split-test-contract-fails-fast`

## Phase 1: Fail Fast on Mixed-Layer Contracts
**Goal**: RED pre stops mixed unit plus integration contracts with a named split-task error before any agent spawn

### Tasks

- TSK-043-01: Detect multi-layer contract and stop RED pre before spawn
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_red_split_contract.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `US-043-01` demands refusal of mixed contracts at once (`AC-PLAN-001`); `US-043-02` demands the error name layers and the fix (`AC-PLAN-002`). The test file encodes the stop-before-spawn contract. `src/deviate/cli/micro.py` owns `_pre_layer_contract` and `_classify_suite_kind`, the only production code this behavior touches.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_red_split_contract.py` only — forbid `tests/test_integration/` and `tests/e2e/` in this RED. Assert a task declaring unit plus integration targets across row and card signals makes RED pre exit non-zero with a split-task error, spawns zero RED agents, and names each detected layer plus the split-into-one-task-per-layer action in the message.
    - **Green**: Implement concrete multi-layer detection in `src/deviate/cli/micro.py` (`_pre_layer_contract` plus a helper over task row and card signals), scoped to suite-dir file paths and layer-scoped commands in `verification`, `test_strategy`, and card text. Raise the split-task error through the existing `VerificationUnresolvedError`-style pre exit path before any agent spawn.
    - **Refactor**: Align the new helper with existing `_classify_suite_kind` naming and reuse `is_safe_test_command` filtering for declared commands.
    - **Edge Cases**: Handle a row `test_strategy` naming one layer losing to card files in two layers by firing; handle prose-only layer mentions with no concrete targets by not firing.
    - **Acceptance**: `mise unit` passes; mixed unit plus integration contract exits non-zero with zero agent attempts and a message naming both layers.

- TSK-043-02: Keep single-layer passthrough and keyword fallback intact
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_red_split_contract.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `US-043-01` requires single-layer tasks to pass untouched (`AC-PLAN-003`); `US-043-02` requires e2e-mixed tasks to stop while keyword-only cards keep fallback (`AC-PLAN-004`). Same two files as `TSK-043-01` because the check and its guard rails live in one function pair.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_red_split_contract.py` only — forbid `tests/test_integration/` and `tests/e2e/` in this RED. Assert a single-layer task passes the check with no split error, an e2e-plus-another-layer task raises the split error, and a card carrying only ambiguous keywords with no concrete multi-layer paths keeps the current fallback behavior.
    - **Green**: Extend the `src/deviate/cli/micro.py` detection so exactly one concrete layer continues to existing `_layer_contract_fields`, e2e mixed with any layer fires, and keyword-only signals without concrete suite-dir paths or layer-scoped commands fall through to the existing `ambiguous` path.
    - **Refactor**: Share the per-signal normalization between the fire path and the fallback path; no new dependencies.
    - **Edge Cases**: Handle a stray single concrete path plus keyword noise as single-layer; handle `execution_mode: E2E` stamping per existing `_classify_suite_kind` precedence.
    - **Acceptance**: `mise unit` passes; single-layer RED writes tests in the assigned layer dir and keyword-only cards behave exactly as before.
  - **Dependency**: `TSK-043-01`

- TSK-043-03: Regression sweep over unit plus integration rungs
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: integration
  - **Verification**: `mise unit && mise integration`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `tests/test_integration/test_meso_orchestration.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `FR-ADHOC-043` changes the shared RED pre path used by every micro task, so the closing sweep proves no single-layer regression across rungs. The integration file exercises the orchestration path; `src/deviate/cli/micro.py` is the changed production surface under verification.
  - **Details**:
    - **Implementation**: Run `mise unit` then `mise integration`; record any failure against `TSK-043-01` or `TSK-043-02` and fix there, keeping this task verification-only with no production edits.
    - **Refactor**: None; verification only.
    - **Edge Cases**: Handle pre-existing unrelated failures by confirming they fail on the base branch too before claiming pass.
    - **Acceptance**: `mise unit` and `mise integration` both exit 0, or every failure is shown pre-existing on base.
  - **Dependency**: `TSK-043-02`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 `TSK-043-01` -> `TSK-043-02` -> `TSK-043-03`

**Critical Dependency Chains**:
- `TSK-043-01` must precede `TSK-043-02` (detection core before guard rails)
- `TSK-043-02` must precede `TSK-043-03` (full behavior before sweep)

**Risk Hotspots**:
- Prose-only layer mentions cause false split errors; mitigated by firing only on concrete suite-dir paths and layer-scoped commands (`TSK-043-01`, `TSK-043-02`)
- Stray card paths block legitimate single-layer tasks; mitigated by the single-layer passthrough tests (`TSK-043-02`)

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_red_split_contract.py` (both TDD tasks append to the same new test file; land `TSK-043-01` first)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
