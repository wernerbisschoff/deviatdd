# Implementation Tasks: `feat/007-shared-phase-kernel/001-shared-phase-kernel`

## Phase 1: Kernel contracts and RED parity
**Goal**: Extract kernel types plus RED pre/post kernels with unified adjudication

### Tasks

- TSK-001-01: Kernel types, outcome token, and KernelError mapping
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_kernel_outcome.py`
  - **Rationale**: `src/deviate/cli/micro.py` hosts the new `KernelOutcome` and `KernelError` types for `US-007-01` plus `AC-PLAN-001` and `AC-PLAN-002`; the test file proves the token and exit mapping before GREEN.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a manual command prints the fixed status token verbatim with exit 0, and a `KernelError` with token plus detail maps to exit 1 on manual and per-step catch on auto.
    - **Green**: Implement `KernelOutcome`, `KernelError`, plus manual print and auto catch helpers in `src/deviate/cli/micro.py`, scoped to the outcome path only.
    - **Refactor**: Align dataclass shape with existing module idioms.
    - **Edge Cases**: Handle missing task id by failing with the token; handle empty detail without stack leak.
    - **Acceptance**: Token prints verbatim, manual error exits 1, auto catches per step.

- TSK-001-02: RED pre kernel with manual and auto contract parity
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_contract.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns the RED pre contract assembly for `US-007-01` plus `AC-PLAN-003` and `AC-PLAN-004`; the test file locks the five-key contract plus additive doctor fields on both surfaces.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `deviate red pre` stdout holds the five-key contract JSON plus mise doctor fields with no key removed, and `_red_pre_kernel` builds identical shared keys in-process.
    - **Green**: Implement `_red_pre_kernel` contract assembly in `src/deviate/cli/micro.py` and point manual `red pre` at it; keep literals and flags verbatim.
    - **Refactor**: Remove duplicated key assembly once both surfaces share the kernel.
    - **Edge Cases**: Handle pending task that fails to resolve by raising `KernelError`; handle doctored contract JSON as rejected input.
    - **Acceptance**: Both surfaces emit matching shared keys, additive doctor fields present.
  - **Dependency**: TSK-001-01

- TSK-001-03: RED post kernel with shared side effects
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_post.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns RED side effects for `US-007-01` plus `AC-PLAN-005`; the test file proves ledger, session, commit, and token parity.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert manual `red post` and auto `_run_red_phase` produce matching ledger rows, session transitions, and commits with `RED_POST_OK`.
    - **Green**: Implement `_red_post_kernel` in `src/deviate/cli/micro.py`; wire both surfaces to it.
    - **Refactor**: Keep commit subjects and flags verbatim from pre-change behavior.
    - **Edge Cases**: Handle guard rejection with no partial ledger write.
    - **Acceptance**: Side effects match on both surfaces, `RED_POST_OK` prints.
  - **Dependency**: TSK-001-02
  - **Rescope (2026-09-05)**: AC-PLAN-006 adjudication unification moved to TSK-001-09 after three JUDGE rejects — RED was unformulable while both adjudication variants already existed.

---

## Phase 2: GREEN and REFACTOR kernels
**Goal**: Unify GREEN post and REFACTOR pre/post side effects behind kernels

### Tasks

- TSK-001-04: GREEN post kernel with guard-failure safety
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_green_post.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns GREEN side effects for `US-007-01` plus `AC-PLAN-007` and `AC-PLAN-008`; the test file proves parity and guard atomicity.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert manual `green post` and auto `_run_green_phase` produce matching ledger rows, session transitions, and commits with `GREEN_POST_OK`, and a failed guard keeps current tokens and exit codes with zero ledger or session writes.
    - **Green**: Implement `_green_post_kernel` with guard check in `src/deviate/cli/micro.py`; wire both surfaces to it.
    - **Refactor**: Share the ledger plus session plus commit block between surfaces.
    - **Edge Cases**: Handle guard failure atomically with no partial write; handle missing active task via `KernelError`.
    - **Acceptance**: Side effects match, `GREEN_POST_OK` prints, guard failure writes nothing.
  - **Dependency**: TSK-001-01

- TSK-001-05: REFACTOR pre and post kernels with regression gate
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_refactor_kernel.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns REFACTOR contracts and side effects for `US-007-01` plus `AC-PLAN-009`, `AC-PLAN-010`, `AC-PLAN-011`, and `AC-PLAN-012`; the test file locks the eight-field contract, parity, and gate behavior.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `deviate refactor pre` stdout holds the eight-field contract JSON plus doctor fields, auto `_refactor_pre_kernel` builds identical shared keys, both post surfaces match side effects with `REFACTOR_POST_OK`, and a failed regression gate exits with the current code and appends no COMPLETED row.
    - **Green**: Implement `_refactor_pre_kernel` and `_refactor_post_kernel` with the regression gate in `src/deviate/cli/micro.py`; wire both surfaces to them.
    - **Refactor**: Share contract assembly and side-effect blocks; keep literals verbatim.
    - **Edge Cases**: Handle GREEN-passed precondition missing via `KernelError`; handle gate failure with zero COMPLETED append.
    - **Acceptance**: Contracts match, side effects match, gate failure writes no COMPLETED row.
  - **Dependency**: TSK-001-04

---

## Phase 3: Thin wrappers and auto delegation
**Goal**: Convert manual commands to single-kernel wrappers and delegate auto phases

### Tasks

- TSK-001-06: Eight thin manual wrappers with byte-identical pre commands
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_wrapper_dispatch.py`
  - **Rationale**: `src/deviate/cli/micro.py` holds the eight manual commands for `US-007-01` plus `AC-PLAN-013` and `AC-PLAN-014`; the test file proves one-kernel dispatch and pre-change byte identity.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert each manual command resolves the task, calls exactly one kernel, emits the pre-change output, and `green_pre` plus `judge_pre` emit no contract with byte-identical stdout and exit codes.
    - **Green**: Convert the eight commands in `src/deviate/cli/micro.py` to resolve-then-call-one-kernel wrappers; leave `green_pre` and `judge_pre` bodies byte-identical.
    - **Refactor**: Remove inline pre/post logic superseded by kernels.
    - **Edge Cases**: Handle wrapper called with unknown task id via `KernelError` token; handle double kernel call as test failure.
    - **Acceptance**: Exactly one kernel per command, `green_pre` and `judge_pre` bytes unchanged.
  - **Dependency**: TSK-001-05

- TSK-001-07: Auto phase delegation with single agent call and cycle parity
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_auto_delegation.py`
  - **Rationale**: `src/deviate/cli/micro.py` holds the three auto runners for `US-007-01` plus `AC-PLAN-015` and `AC-PLAN-016`; the test file proves cycle parity and the agent-call contract.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a full auto TDD cycle keeps commits, ledger rows, and session transitions equal to pre-change behavior, each phase calls `_invoke_agent` once, and no kernel reaches `_invoke_agent`.
    - **Green**: Delegate `_run_red_phase`, `_run_green_phase`, and `_run_refactor_phase` in `src/deviate/cli/micro.py` to pre/post kernels around one `_invoke_agent` call each; keep JUDGE path unchanged.
    - **Refactor**: Remove duplicated side-effect code from auto runners.
    - **Edge Cases**: Handle agent failure without kernel side-effect write; handle kernel `KernelError` caught per step.
    - **Acceptance**: Cycle parity holds, one agent call per phase, zero agent calls from kernels.
  - **Dependency**: TSK-001-06

---

## Phase 4: Regression guards and release note
**Goal**: Lock tokens, keys, literals, and retry contracts with a CHANGELOG bullet

### Tasks

- TSK-001-08: Status-token regression suite plus CHANGELOG adjudication bullet
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_output_filter.py`
    - `CHANGELOG.md`
  - **Rationale**: `tests/unit/test_micro/test_output_filter.py` locks contract keys, tokens, and commit literals for `US-007-01` plus `AC-PLAN-017` and `AC-PLAN-018`; `CHANGELOG.md` records the user-visible unified no-failing-test adjudication bullet.
  - **Details**:
    - **Implementation**: Add token, key-set, commit-literal, and prompt-retry regression tests covering both manual and auto surfaces; append one `[Unreleased]` bullet for the manual RED adjudication change.
    - **Refactor**: Keep new assertions consistent with existing regression style.
    - **Edge Cases**: Handle key-set drift as explicit failure; handle missing `[Unreleased]` section by creating it.
    - **Acceptance**: `pytest tests/unit/test_micro/ -v` passes, retry contracts hold on either surface, `CHANGELOG.md` carries the bullet.
  - **Dependency**: TSK-001-07

- TSK-001-09: Unified no-failing-test adjudication behind shared helper
  - **Type**: Refactor_Batch
  - **Mode**: DIRECT
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_red_post.py tests/unit/test_micro/test_red.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_red_post.py`
  - **Rationale**: Manual `red post` adjudicates inline (`RedMustPassError`) while auto `_run_red_phase` routes through `_adjudicate_red_no_failing_test`; AC-PLAN-006 needs one shared path.
  - **Details**:
    - **Implementation**: Route the manual `red post` zero-failing-test path through `_adjudicate_red_no_failing_test`; keep exit codes and user-visible tokens byte-identical; extend `test_red_post.py` parity tests to spy the shared helper on both surfaces.
    - **Refactor**: Keep commit subjects and flags verbatim.
    - **Edge Cases**: Handle guard rejection with no partial ledger write.
    - **Acceptance**: Both surfaces call the shared helper, tokens and exit codes unchanged, parity tests pass.
  - **Dependency**: TSK-001-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 (kernels before wrappers before delegation before guards)

**Critical Dependency Chains**:
- TSK-001-01 must precede TSK-001-02
- TSK-001-02 must precede TSK-001-03
- TSK-001-03 must precede TSK-001-09
- TSK-001-05 must precede TSK-001-06
- TSK-001-06 must precede TSK-001-07
- TSK-001-07 must precede TSK-001-08

**Risk Hotspots**:
- Contract key drift between surfaces — shared kernel builds both contracts, key-set test locks parity
- Commit literal drift — literals stay verbatim in kernels, literal test asserts subjects
- Kernel calling the agent directly — delegation test asserts zero `_invoke_agent` calls from kernels

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
