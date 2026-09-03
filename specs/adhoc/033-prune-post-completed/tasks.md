# Implementation Tasks: `feat/adhoc/033-prune-post-completed`

## Phase 1: Honeycomb classification engine

**Goal**: Pin and close gaps in mark-first classification and untagged body heuristics.

### Tasks

- TSK-033-01: Classify tagged tests keep/drop and untagged tests from the body
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_prune.py -q -k "classify"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/prune.py`
    - `tests/unit/test_core/test_prune.py`
  - **Rationale**: `US-033-01` with `AC-PLAN-001` and `AC-PLAN-002` live in `classify_test` and `_classify_body`. The test file pins the contract. Production code changes only where pins fail.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_prune.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert keep for behavioral/ac marks and name tags, drop for spy/impl marks and name tags, keep-wins on mixed tags, and untagged bodies: drop on spy asserts/private state/private patch/sibling mocks, keep on AC tokens and public input-to-output asserts, drop on empty or bare bodies.
    - **Green**: Implement the minimum in `classify_test`, `_classify_body`, `_name_tags`, and the tag regexes in `src/deviate/core/prune.py`, scoped to the workstation files for these scenarios. GREEN cannot edit tests.
    - **Refactor**: Align new branches with existing regex-table style. Remove no existing pin.
    - **Edge Cases**: Handle empty body by drop. Handle unknown mark strings by falling through to body heuristics, never auto-keep.
    - **Acceptance**: Scoped verification passes. `AC-PLAN-001` and `AC-PLAN-002` behaviors hold. No ledger or spec file is touched by this slice.

- TSK-033-02: Thin in-flight issues and keep every spec file
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_prune.py tests/unit/test_cli/test_prune.py -q -k "in_flight or spec or unmatched or ready"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/prune.py`
    - `tests/unit/test_core/test_prune.py`
    - `tests/unit/test_cli/test_prune.py`
  - **Rationale**: `US-033-01` with `AC-PLAN-003` lives in `build_prune_plan` (IN_FLIGHT branch, `spec_deletes` always empty) and `apply_prune`/`_thin_tests`. Core pins live in `test_core`; the `pre` in-flight contract pin lives in `test_cli`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_prune.py` and `tests/unit/test_cli/test_prune.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert non-COMPLETED status yields IN_FLIGHT with thinning lists populated, `spec_deletes` empty, `plan.md` and `tasks.md` present after apply, unmatched plan ACs surfaced without blocking, and empty-file unlink limited to test files with zero surviving tests.
    - **Green**: Implement the minimum in `build_prune_plan`, `apply_prune`, `_thin_tests`, `_protected_keeps`, and `_unmatched_acs` in `src/deviate/core/prune.py`. GREEN cannot edit tests.
    - **Refactor**: Keep `spec_deletes` construction empty by construction, not by post-filter. Keep helper style consistent.
    - **Edge Cases**: Handle missing `plan.md` by empty token list, not failure. Handle unknown issue id by FAILURE with zero writes. Handle second issue id in intent by ONE_ISSUE_ONLY with zero writes.
    - **Acceptance**: Scoped verification passes. `AC-PLAN-003` holds. `git diff` shows engine plus pins only.
  - **Dependency**: TSK-033-01

## Phase 2: Ledger and cycle-markdown protection

**Goal**: Prove prune never writes ledgers, rejects rewrite intent, and skips a missing optional flows ledger.

### Tasks

- TSK-033-03: Keep ledgers byte-identical, reject rewrite intent, skip missing flows ledger
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_prune.py tests/unit/test_cli/test_prune.py -q -k "ledger or rewrite or flows or compaction or cycle_markdown"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/prune.py`
    - `src/deviate/cli/prune.py`
    - `tests/unit/test_cli/test_prune.py`
  - **Rationale**: `US-033-02` with `AC-PLAN-004`, `AC-PLAN-005`, and `AC-PLAN-006` live in `apply_prune` (ledger-free write path), `is_ledger_rewrite_request` plus the `LEDGER_REWRITE_REJECTED` early return, and `ledger_paths`/`snapshot_ledgers`. `src/deviate/cli/prune.py` carries the `post` zero-write gate. CLI pins live in `test_cli`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_prune.py` (plus `tests/unit/test_core/test_prune.py` for engine helpers) only — forbid `tests/integration` and `tests/e2e` in this RED. Assert pre/post snapshots of `specs/issues.jsonl` and `specs/**/tasks.jsonl` match after apply, cycle markdown (`plan.md`, `tasks.md`) still exists, compact/squash/rewrite intent returns LEDGER_REWRITE_REJECTED with zero writes, missing `specs/_product/flows.jsonl` is skipped without creation, and `ledger_paths` returns only existing ledgers.
    - **Green**: Implement the minimum in `apply_prune`, `is_ledger_rewrite_request`, `ledger_paths`, `snapshot_ledgers` in `src/deviate/core/prune.py` and the `post` rejection gate in `src/deviate/cli/prune.py`. GREEN cannot edit tests.
    - **Refactor**: Keep the write path limited to test files named in the drop list. Add no new dependency.
    - **Edge Cases**: Handle absent ledgers by empty snapshot, not error. Handle rewrite intent with mixed case. Handle `post` on rejected statuses with non-zero exit and zero writes.
    - **Acceptance**: Scoped verification passes. `AC-PLAN-004`, `AC-PLAN-005`, and `AC-PLAN-006` hold. No task in this slice writes a real-repo ledger — all fixtures use `tmp_path`.
  - **Dependency**: TSK-033-02

## Phase 3: Prompt, skill, and spec prose alignment

**Goal**: Align every prose mirror to manual honeycomb thinning with RED mark stamping and no auto-hook.

### Tasks

- TSK-033-04: Align prune prompts, RED stamping rule, skill guards, README, specs, and changelog
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_cli/test_prune.py -q -k "prompt or skill or readme or red or manual or auto_invoke" && uv run ruff check src/deviate/core/prune.py src/deviate/cli/prune.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-prune.md`
    - `src/deviate/prompts/auto/red.md`
    - `src/deviate/prompts/commands/deviate-red.md`
    - `src/deviate/prompts/skills/deviatdd/SKILL.md`
    - `README.md`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
    - `tests/unit/test_cli/test_prune.py`
  - **Rationale**: `US-033-03` with `AC-PLAN-007` and `AC-PLAN-008` lives in the RED core and overlay (`auto/red.md`, `deviate-red.md`), the single manual surface (`deviate-prune.md`), and the skill guards (`SKILL.md`). `README.md`, `specs/DeviaTDD-api.md`, and `specs/DeviaTDD-architecture.md` mirror that contract. `CHANGELOG.md` carries the `[Unreleased]` bullet. The pin file asserts the wording.
  - **Details**:
    - **Implementation**: Edit only passages that contradict manual honeycomb thinning. Keep one surface and existing aliases. Keep Rule 6 in `auto/red.md` (exactly one behavioral/spy/impl mark per new test, most read behavioral). Keep skill guards that forbid prune from the success loop, COMPLETED, and `--all`. Update stale spec passages in the same commit. Append one `[Unreleased]` bullet to `CHANGELOG.md`.
    - **Refactor**: Match surrounding prose tone. Add no new surface, skill, alias, or gate.
    - **Edge Cases**: Handle wording that still describes spec-delete-on-COMPLETED — rewrite it to keep. Handle drift between mirrors by updating all mirrors in this one task.
    - **Acceptance**: Scoped verification passes. Prompt pins for manual-only, no-spec-delete, RED stamping, and no-auto-hook all pass. `git diff` shows prose plus changelog only. No production code changes in this task.
  - **Dependency**: TSK-033-03

## Phase 4: Closing application verification

**Goal**: Prove the operator-facing prune flow end to end on the consumer CLI surface.

### Tasks

- TSK-033-05: [E2E] Verify manual prune on a fixture issue via the CLI
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: e2e
  - **Verification**: `mise run test && mise run test-e2e`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/e2e/test_prune_manual.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: `US-033-01` with `AC-PLAN-001` gives the happy path (spy/impl thinned, behavioral stays). `US-033-02` with `AC-PLAN-005` gives the critical-failure path (ledger-compaction intent rejected, zero writes). The new bats file encodes both. The existing macro workflow bats file anchors the bats pattern and regression sweep.
  - **Details**:
    - **Implementation**: Author `tests/e2e/test_prune_manual.bats` with two cases only: happy path (fixture issue with spy, behavioral, and untagged tests plus cycle markdown; run `deviate prune pre` then `post`; assert spies gone, public tests and `plan.md`/`tasks.md`/ledger bytes intact) and critical failure (compaction intent; assert LEDGER_REWRITE_REJECTED, non-zero exit, zero writes). Mirror the setup/teardown idiom of `tests/e2e/test_macro_workflow.bats`. Run the full ladder.
    - **Refactor**: Keep the bats file to the two cases. Add no helper library.
    - **Edge Cases**: Handle fixture isolation by operating in a temp dir, never the real repo. Handle missing `bats` binary by failing loud, not skipping silently.
    - **Acceptance**: `mise run test` and `mise run test-e2e` both pass. No empty e2e file is emitted. This task is last and has no forward dependency.
  - **Dependency**: TSK-033-04

---

## Implementation Strategy

**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 (TSK-033-01 -> TSK-033-02 -> TSK-033-03 -> TSK-033-04 -> TSK-033-05)

**Critical Dependency Chains**:
- TSK-033-01 must precede TSK-033-02 (both edit `src/deviate/core/prune.py` classification paths; ordering avoids conflicts)
- TSK-033-02 must precede TSK-033-03 (thinning behavior is the precondition for ledger-protection pins)
- TSK-033-03 must precede TSK-033-04 (engine truth is fixed before prose mirrors it)
- TSK-033-04 must precede TSK-033-05 (the closing E2E asserts the final wording plus engine)

**Risk Hotspots**:
- Body heuristic drops a public behavioral test — keep-wins on AC tokens and public input-to-output asserts, pinned in TSK-033-01
- Empty-file unlink removes an unexpected file — unlink limited to test files with zero surviving tests, pinned in TSK-033-02
- Prior ADH-033 commits already cover the behavior — each TDD task changes production code only where its pins fail
- Prose drift reintroduces spec-delete language — prompt pins plus single-commit mirror update in TSK-033-04

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/prune.py` (TSK-033-01, TSK-033-02, TSK-033-03 — serialized by dependency chain), `tests/unit/test_cli/test_prune.py` (TSK-033-02, TSK-033-03, TSK-033-04 — append-only new test functions, distinct `-k` filters)

**Verification Inference**:
- No `mise unit` or `mise integration` task exists in `mise.toml`. Unit tasks verify with scoped `uv run pytest <files> -q -k "<filter>"`. The closing task runs the full ladder `mise run test && mise run test-e2e`.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
