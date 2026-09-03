# Implementation Tasks: `feat/adhoc/035-gate3-walkthrough-map-and-review-comments`

## Phase 1: Remove forbidden reference and pin Gate 3 CLI contracts
**Goal**: Delete the `/deviate-pr-review` chain token and pin walkthrough four-look plus review comments-default behavior with CLI-output tests

### Tasks

- TSK-035-01: Remove `/deviate-pr-review` chain reference and pin optional-pack registry
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_review.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-e2e.md`
    - `tests/unit/test_cli/test_review.py`
  - **Rationale**: `US-035-03` plus `AC-PLAN-003` require no `pr-review` pack name and no `/deviate-pr-review` reference; the e2e prompt holds the stray token and the unit test pins the registry through CLI output and files
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `deviate-e2e.md` contains no `/deviate-pr-review` token, `OPTIONAL_PACKS` still maps `review` and `walkthrough` with no `pr-review` entry, and no `deviate-pr-review.md` file exists
    - **Green**: Edit `src/deviate/prompts/commands/deviate-e2e.md` line 32 to end the chain at an existing command (`/deviate-pr`) and delete the `/deviate-pr-review` token; change no other prompt text
    - **Refactor**: Keep the chain sentence short and reuse the existing command-token style
    - **Edge Cases**: Handle default-packs setup installing only macro, meso, and micro packs; handle a scan that finds zero new pack names
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_review.py -v` passes and `grep -rn "pr-review" src/` returns no rows outside historical CHANGELOG entries

- TSK-035-02: Pin walkthrough four-look map and empty-diff SKIP through CLI output
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_walkthrough.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/walkthrough.py`
    - `tests/unit/test_cli/test_walkthrough.py`
  - **Rationale**: `US-035-01` plus `AC-PLAN-001` require the brief path plus plan AC lines, test hunks, production hunks mapped to named checks, the check command, and empty-diff `SKIP: no changes since {base_branch}`; the `pre` contract in `walkthrough.py` supplies those fields and the unit test pins them
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `deviate walkthrough pre` emits `issue_brief_path`, `plan_path`, `test_files`, and `production_files`, and empty diff exits with exactly `SKIP: no changes since {base_branch}`; assert no test reads prompt-body substrings
    - **Green**: Change `src/deviate/cli/walkthrough.py` only where verification finds a gap against `AO-035-01`; keep `classify_changed_files` output shape unchanged when the contract already holds
    - **Refactor**: Align new assertions with the existing `pre`-contract test style in `test_walkthrough.py`
    - **Edge Cases**: Handle empty diff by exiting with the exact SKIP message; handle missing plan path without crashing the `pre` contract
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_walkthrough.py -v` passes and no added test asserts on prompt-body text

  - **Judge Feedback**: The next RED attempt must: isolate the empty-diff case into a distinguishable state from the JSON contract case. Either commit the seeded brief files or seed no brief before invoking walkthrough pre, so SKIP on empty diff and JSON contract with plan_path null hold in different trees per AO-035-01 and AC-PLAN-001. Keep all assertions on CLI output and files, never on prompt-body substrings. The prior RED suite was unsatisfiable: test_pre_plan_path_null_when_absent and test_pre_empty_diff_exits_with_skip build byte-identical repos but demand mutually exclusive outputs, so no production code in src/deviate/cli/walkthrough.py can satisfy both.
- TSK-035-03: Pin review comments-default, `--apply` CRITICAL-only, and `brief incomplete`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_review.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/review.py`
    - `tests/unit/test_cli/test_review.py`
  - **Rationale**: `US-035-02` plus `AC-PLAN-002` require default-path comments with no edits, no `git add`, no commit, never `REQUEST_CHANGES`, exactly `brief incomplete` on a check-less brief, and `--apply` landing CRITICAL findings with a concrete FIX only; `review.py` owns the `apply` default and the unit test pins the output
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert default `apply` is false with `apply_scope` CRITICAL, default path performs no edits and no commit, incomplete brief emits exactly `brief incomplete`, comments sort stably, and `--apply` never lands SUGGESTION or OPPORTUNITY
    - **Green**: Change `src/deviate/cli/review.py` only where verification finds a gap against `AO-035-02`; keep `_apply_enabled` semantics unchanged when the contract already holds
    - **Refactor**: Reuse the existing `tmp_git_repo` fixture for any git-touching test; pass `repo=tmp_git_repo` and never touch the real worktree
    - **Edge Cases**: Handle `--apply` with zero CRITICAL findings by committing nothing; handle incomplete brief by stopping before any edit
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_review.py -v` passes and no added test asserts on prompt-body text
  - **Dependency**: TSK-035-01

## Phase 2: Record the slice in specs and CHANGELOG
**Goal**: Reflect the rewritten Gate 3 contracts in the API spec, architecture spec, and changelog

### Tasks

- TSK-035-04: Update Gate 3 spec wording and append the CHANGELOG entry
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run ruff check src/deviate/cli/review.py src/deviate/cli/walkthrough.py`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `US-035-01` through `US-035-04` plus `AC-PLAN-001` through `AC-PLAN-004` require the specs to match the comments-default review and four-look walkthrough prompts and require one `[Unreleased]` bullet; touch-ups stay verbatim to prompt behavior
  - **Details**:
    - **Implementation**: Quote the prompt behavior verbatim and change spec wording only where it drifts; append one CHANGELOG bullet under `[Unreleased]` for the Gate 3 rewrite
    - **Refactor**: Keep spec edits to the Gate 3 command-contract sections; change no unrelated sections
    - **Edge Cases**: Handle the case where specs already match by leaving them untouched and still appending the CHANGELOG bullet
    - **Acceptance**: `CHANGELOG.md` holds one 035 bullet under `[Unreleased]` and `mise run check` stays green
  - **Dependency**: TSK-035-03

- TSK-035-05: [E2E] Verify the Gate 3 slice against the existing e2e ladder
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: e2e
  - **Verification**: `mise run test-e2e`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `tests/e2e/test_review_plan_ac_coverage.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: `US-035-01` plus `US-035-02` (walkthrough shows the four looks on the issue PR; review posts comments by default) require the existing application e2e surface to stay green after the chain-token removal; this task runs that surface and adds no files
  - **Details**:
    - **Implementation**: Run `mise run test-e2e` in the issue worktree; confirm the review-coverage and macro-workflow bats files pass; add no new e2e files and edit no test files
    - **Refactor**: No code changes in this task; report failures back to the owning unit task
    - **Edge Cases**: Handle the happy path (review then walkthrough chain completes) plus the critical failure (empty diff exits SKIP without review edits)
    - **Acceptance**: `mise run test-e2e` exits 0 with zero test files added or changed
  - **Dependency**: TSK-035-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (TSK-035-01 -> TSK-035-02 and TSK-035-03 -> TSK-035-04 -> TSK-035-05)

**Critical Dependency Chains**:
- TSK-035-01 must precede TSK-035-03 (both extend `test_review.py`)
- TSK-035-03 must precede TSK-035-04 (spec wording quotes the pinned behavior)
- TSK-035-04 must precede TSK-035-05 (e2e sweep runs last)

**Risk Hotspots**:
- Prompts may already satisfy the issue, so the value sits in the new CLI-output pins rather than production edits
- Added assertions may drift onto prompt-body substrings instead of CLI output and files

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_cli/test_review.py` (TSK-035-01, TSK-035-03)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
