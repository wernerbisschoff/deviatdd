# Implementation Tasks: `feat/adhoc/039-merge-push-gate-language-agnostic`

## Phase 1: Language-agnostic push gate
**Goal**: Every non-empty push runs repo `mise` checks and blocks on failure, with hook and prompt copies byte-equivalent

### Tasks

- TSK-039-01: Rewrite pre-push hook to run mise checks on every non-empty push
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `.githooks/pre-push`
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Rationale**: `US-039-01` via `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003` — the hook is the gate itself; the test file carries the `TestMergePromptPushGate` pins that must assert the new mise-task behavior and the gone `*.py` filter.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/` only — forbid `tests/integration` and `tests/e2e` in this RED. Extend `TestMergePromptPushGate` with pins asserting `mise run format-check`, `mise run lint`, `mise run test-affected` / `mise run test` strings exist in the hook, the `*.py` filter and empty-changed early exit are gone, `HEAD~1` fallback and empty-diff exit 0 remain, and missing `.testmondata` falls back to `mise run test` never a silent pass.
    - **Green**: Rewrite `.githooks/pre-push` — keep upstream merge-base else `HEAD~1` base resolution plus empty-diff exit 0, drop the `*.py` diff filter and vacuous pass, run `mise run format-check`, `mise run lint`, then `mise run test-affected` when `.testmondata` is non-empty else `mise run test` with a plain notice; GREEN cannot edit tests.
    - **Refactor**: Keep single-pass sequential checks, no retry loop, bash 3.2 portable syntax.
    - **Edge Cases**: Handle missing mise task by plain error never exit 0; failing check surfaces tool stderr verbatim; no upstream and no parent exits 0.
    - **Acceptance**: Push with zero Python changes runs all three checks and blocks on failure; `mise unit` passes.

- TSK-039-02: Mirror new hook body into deviate-merge prompt and update pins
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-merge.md`
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Rationale**: `US-039-01` via `AC-PLAN-004` — the prompt inlines the gate body verbatim; the drift test is the contract that hook and prompt stay byte-equivalent with updated pins.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/` only — forbid `tests/integration` and `tests/e2e` in this RED. Update `TestMergePromptPushGate` pins to assert the prompt gate body contains the new mise-task lines, asserts the old `*.py` filter is absent, and keeps the hook/prompt line-set equality invariant.
    - **Green**: Replace the fenced gate block in `deviate-merge.md` byte for byte with the new `.githooks/pre-push` body; update surrounding prose that names Python-only behavior (`ruff check`, selective pytest on Python files); GREEN cannot edit tests.
    - **Refactor**: Keep `Failure_State: Push_Gate_Failed` contract text unchanged; touch only the gate fence plus the Python-only prose lines.
    - **Edge Cases**: Handle prompt fence extraction markers (`**Run the push gate**` heading, ```bash fences) staying parseable by the drift test.
    - **Acceptance**: `TestMergePromptPushGate` passes, hook and prompt agree on gate body, `mise unit` passes.
  - **Dependency**: TSK-039-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 sequential: TSK-039-01 -> TSK-039-02 (prompt mirror needs the final hook body)

**Critical Dependency Chains**:
- TSK-039-01 must precede TSK-039-02

**Risk Hotspots**:
- Hook/prompt drift — both bodies updated in one commit, line-set equality test guards it
- Non-Python repos lacking `test-affected` task — probe with `mise tasks ls`, fall back to `mise run test` with plain notice

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_meso/test_auto_prompt_templates.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
