# Implementation Tasks: `feat/005-acceptance-gates/003-micro-phase-gates-red-green`

## Phase 1: RED Non-Blocking Checkpoint With Warning Advisory
**Goal**: RED run completes on pass and fail, returns an in-memory advisory, logs the warning event

### Tasks

- TSK-003-01: RED checkpoint returns in-memory advisory and never blocks GREEN
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/test_micro/test_red.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_red.py`
  - **Rationale**: `src/deviate/cli/micro.py` hosts `_run_red_phase` and the new `RedHandoffAdvisory` model; `tests/test_micro/test_red.py` is the unit target. Serves `US-005-05` and `US-005-06` via `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003`, `AC-PLAN-004`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/test_micro/test_red.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Mock `deviate.cli.micro._run_pytest` with `CompletedProcess` fixtures. Assert pass run returns advisory with `passes True` and `severity warning` and no `PhaseFailedError`; assert fail run returns advisory with `passes False` and `severity ok`; assert `RED_PASSED_WARNING` logged via `log_event` with task id; assert crash surfaces as phase error with no advisory; assert absent test file skips checkpoint with no advisory
    - **Green**: Implement `RedHandoffAdvisory` Pydantic model (`task_id`, `passes`, `severity`) co-located with phase runners in `src/deviate/cli/micro.py`. Change `_run_red_phase` to append the `RED` transition on every completed run, build and return the advisory in memory instead of raising or routing to JUDGE on returncode 0, call `log_event` with `RED_PASSED_WARNING` on pass. Keep crash and absent-file routing unchanged. GREEN cannot edit tests
    - **Refactor**: Keep the advisory out of `TaskRecord` and `tasks.jsonl`; keep `_adjudicate_red_no_failing_test` removal clean with no dead callers
    - **Edge Cases**: Handle test-command crash by surfacing a phase error and discarding the advisory; handle absent test file by skipping the checkpoint; handle pytest exit 5 as no-tests-collected per existing `_run_test_cmd` semantics
    - **Acceptance**: `AC-PLAN-001` through `AC-PLAN-004` pass; advisory never serializes to any ledger; `uv run pytest tests/test_micro/test_red.py -v` exits 0

---

  - **Judge Feedback**: COMPLIANCE_VIOLATION: The next GREEN attempt must: keep RedHandoffAdvisory in memory only, restore _run_red_phase compatibility so every caller unpacks correctly, restore or replace _adjudicate_red_no_failing_test routing for returncode 0 and exit 5 and absent test file, emit RED_PASSED_WARNING only on pass, surface crash as PhaseFailedError, and keep advisory out of TaskRecord and tasks.jsonl. Verify with uv run pytest tests/test_micro/test_red.py -v plus the orchestration and two-counter suites before commit.
  - **Judge Feedback**: The next GREEN attempt must: keep the passing RED tests unchanged and fix the GREEN implementation around them. Migrate every _run_red_phase caller to the new two-value return, including the phase dispatch table entry for RED. Preserve pass advisory with passes True and severity warning plus RED_PASSED_WARNING log, fail advisory with passes False and severity ok, crash surfacing as phase error with no advisory, and absent test file skipping with no advisory. Preserve pytest exit 5 no-tests-collected semantics from _run_test_cmd. Prove with uv run pytest tests/test_micro/test_red.py -v plus the previously failing cycle and orchestration suites.
  - **Judge Feedback**: The next GREEN attempt must: keep the RedHandoffAdvisory contract from AC-PLAN-001 through AC-PLAN-004 (passes True with severity warning on returncode 0, passes False with severity ok on failure, RED_PASSED_WARNING via log_event with task id, crash surfaces PhaseFailedError with no advisory, absent test file skips with no advisory, advisory never persists to any ledger) and also keep the full suite green. Fix every in-repo unpack site of _run_red_phase so _run_tdd_cycle and _escalate_to_new_red accept the tuple return without ValueError. Resolve the obsolete blocking-RED expectations (passing suite raising PhaseFailedError, adjudication routing to JUDGE) so they assert the new non-blocking advisory behavior. Prove with uv run pytest tests/test_micro/test_red.py -v exiting 0 and the previously failing loop tests passing.
## Phase 2: GREEN Blocking Gate With JUDGE Routing
**Goal**: GREEN pass appends transition and clears feedback; GREEN failure routes to JUDGE bounded by retry limit; warning advisory never blocks GREEN

### Tasks

- TSK-003-02: GREEN gate enforces returncode 0 and routes failures to JUDGE
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/test_micro/test_green.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_green.py`
  - **Rationale**: `src/deviate/cli/micro.py` hosts `_run_green_phase`, `train_feedback` routing, and `_MAX_JUDGE_FEEDBACK`; `tests/test_micro/test_green.py` is the unit target. Serves `US-005-07` and `US-005-08` via `AC-PLAN-005`, `AC-PLAN-006`, `AC-PLAN-007`.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/test_micro/test_green.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Mock `deviate.cli.micro._run_pytest` with `CompletedProcess` fixtures. Assert pass appends the `GREEN` transition and clears `session.train_feedback`; assert failure sets `session.train_feedback` with failure output and routes to JUDGE; assert `_MAX_JUDGE_FEEDBACK = 3` bound holds; assert a run reached after a RED `warning` advisory starts GREEN normally and advisory severity never changes the suite verdict
    - **Green**: Keep returncode 0 requirement in `_run_green_phase` in `src/deviate/cli/micro.py`. Keep failure path writing output into `session.train_feedback` and routing to JUDGE. Keep `_MAX_JUDGE_FEEDBACK = 3` untouched. Ignore advisory severity at GREEN start. GREEN cannot edit tests
    - **Refactor**: Align GREEN branch structure with RED checkpoint style; no new dependencies; no persistent writes beyond the GREEN transition row
    - **Edge Cases**: Handle GREEN failure output truncation for `train_feedback`; handle retry bound exhaustion without changing the bound value; handle GREEN pass after warning advisory clearing stale feedback
    - **Acceptance**: `AC-PLAN-005` through `AC-PLAN-007` pass; GREEN failure never records a GREEN pass; `uv run pytest tests/test_micro/test_green.py -v` exits 0
  - **Dependency**: `TSK-003-01`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (GREEN gate tests assume the RED advisory shape from Phase 1)

**Critical Dependency Chains**:
- TSK-003-01 must precede TSK-003-02

**Risk Hotspots**:
- Removing the JUDGE adjudication path breaks existing no-failing-test tests; update `test_red.py` expectations in the same change and run the full micro suite
- Advisory accidentally persisted to a ledger; keep the model out of `TaskRecord` and assert zero advisory rows in ledger audits

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

## Verification Inference Note

- No `mise unit`, `mise integration`, or `mise e2e` tasks exist in `mise.toml` (only `test` full-suite and `test-e2e` bats). Per edge-case handling, Verification is inferred from repo convention as scoped `uv run pytest <task-test-file> -v` with mocked `deviate.cli.micro._run_pytest`. No closing sweep emitted: the issue touches CLI-runner internals only, with no user-facing workflow and no `integration` suite in scope.
