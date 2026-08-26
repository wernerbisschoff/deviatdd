# Implementation Tasks: `feat/adhoc/031-judge-revert-boundary-no-failing-test`

## Phase 1: Guard the already-exists `no_failing_test` pass route in `_apply_judge_verdict`
**Goal**: A `failure_kind == "no_failing_test"` already-exists `COMPLIANCE_PASS` completes via `skip_refactor` instead of being rewritten to `revert_to_red` and hard-crashing with `ROLLBACK_BOUNDARY_MISSING`.

### Tasks

- TSK-031-01: Guard the already-exists pass route so a `no_failing_test` `COMPLIANCE_PASS` completes via `skip_refactor` without `ROLLBACK_BOUNDARY_MISSING`
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_micro/test_judge.py -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_judge.py`
  - **Rationale**: Fixes the micro-judge routing crash described by `US-031-01` and `US-031-02`. `_apply_judge_verdict` (line 3217) calls `_rewrite_unmatched_tdd_pass` unconditionally, which rewrites a `no_failing_test` `COMPLIANCE_PASS` with partial AC evidence to `revert_to_red`; the subsequent `_require_revert_to_red_boundary` (line 3383) then raises `ROLLBACK_BOUNDARY_MISSING` because `session.red_commit_sha` is empty on the already-exists path. Implements `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-004`, `AC-PLAN-005`, `AC-PLAN-006`, and `AC-PLAN-007`; guards the fail-closed behavior of `AC-PLAN-003`. `tests/test_micro/test_judge.py` is the unit sandbox pinned by the issue's Multi-Tiered Verification Targets.
  - **Details**:
    - **Red**: Add unit tests in `tests/test_micro/test_judge.py` driving `_adjudicate_red_no_failing_test` / `_run_judge_phase` with `session.red_commit_sha == ""` and `session.failure_kind == "no_failing_test"`. Assert: (1) `AC-PLAN-001`/`AC-PLAN-002` — a `COMPLIANCE_PASS` with `next_action: skip_refactor` (and a bare PASS with no `next_action`) and evidence omitting one required `AC-PLAN-NNN` token appends exactly one COMPLETED ledger row, sets `pending_judge_action == "skip_refactor"`, keeps the declared regression-pin test file on disk, and raises no `PhaseFailedError` / `ROLLBACK_BOUNDARY_MISSING`; (2) `AC-PLAN-003` — a `skip_refactor` pass with an empty `files` set and no `test_file` raises `PhaseFailedError`, appends no COMPLETED row, and fails closed; (3) `AC-PLAN-004` — a genuine test-bearing RED with a non-empty `red_commit_sha` and partial evidence still rewrites to `revert_to_red` and `_require_revert_to_red_boundary` resolves the standing RED SHA; (4) `AC-PLAN-005` — a `COMPLIANCE_VIOLATION` / `next_action: revert_before` still forces `revert_before` via `_coerce_judge_action`, resets to the RED baseline, and re-dispatches RED; (5) `AC-PLAN-007` — invoking `_apply_judge_verdict` directly (the manual `judge post` path) on a `no_failing_test` session still completes a `skip_refactor` pass and still rolls back a `revert_to_red` with a standing RED SHA.
    - **Green**: In `_apply_judge_verdict` (`src/deviate/cli/micro.py`, line 3217), run `_rewrite_unmatched_tdd_pass` only when `session.failure_kind != "no_failing_test"`. Relax the COMPLETED-write AC-token citation check (`_require_tdd_completed_evidence`, invoked by `_append_status_transition`) for `failure_kind == "no_failing_test"` so partial AC evidence does not raise `COMPLETED_EVIDENCE_MISSING`, while retaining `_require_tdd_declared_regression_files` and the declared-path presence gate. Leave `_coerce_judge_action`, the genuine `revert_to_red` / `revert_before` routes, and the `_NO_FAILING_TEST_FORWARD_ROUTES` set unchanged.
    - **Refactor**: Keep the guard strictly scoped to `no_failing_test`; do not touch `test_defect` or `mechanical` evidence gating. Confirm the forward-route `COMPLETED` write from `_adjudicate_red_no_failing_test` (line 1803) and the `skip_refactor` write from `_apply_judge_verdict` (line 3524) tolerate a single COMPLETED ledger row per task.
    - **Edge Cases**: Handle the double-COMPLETED append risk by asserting the ledger keeps exactly one COMPLETED transition per task. Handle partial evidence without destroying the declared regression-pin tests. Handle `COMPLIANCE_VIOLATION` without completing with an empty test deliverable. Never invoke `_require_revert_to_red_boundary` on the already-exists pass path; keep it reachable only for a genuine `revert_to_red` with a real RED commit.
    - **Acceptance**: The full `tests/test_micro/test_judge.py` suite passes; the existing `test_already_exists_head_quotes_pass` (line 3315) and `test_already_exists_missing_test_file_fails` (line 3332) still pass unchanged; the new partial-evidence `no_failing_test` test completes with no `ROLLBACK_BOUNDARY_MISSING`; `ruff check tests/test_micro/test_judge.py src/deviate/cli/micro.py` is clean.

---

  - **Judge Feedback**: Guarded already-exists route: no_failing_test COMPLIANCE_PASS coerces to skip_refactor and never reaches _require_revert_to_red_boundary; COMPLIANCE_VIOLATION still routes revert_before. All 3 new tests pass; full suite 1600 passed, 3 skipped; ruff clean.
  - **Judge Feedback**: Guarded already-exists route verified: all 78 judge tests and the full suite pass; ruff clean.
## Phase 2: Integration reproduction of the `TSK-029-02` crash
**Goal**: Reproduce the user-facing `deviate micro run` crash end to end through the `_run_pytest`-mocked CLI path and prove the task COMPLETES with no `ROLLBACK_BOUNDARY_MISSING` traceback.

### Tasks

- TSK-031-02: Add a `_run_pytest`-mocked CLI test driving a `no_failing_test` already-exists task to COMPLETED
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_micro.py -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `tests/test_cli/test_micro.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: The issue's demonstration path runs `deviate micro run --task TSK-029-02`; `tests/test_cli/test_micro.py` is the integration sandbox that reproduces the crash (`US-031-01`, `US-031-02`). The existing `_run_pytest`-mocked CLI path (lines 1760-1816) covers judge routing and `ROLLBACK_BOUNDARY_MISSING`; the new test drives the `no_failing_test` already-exists shape end to end. Implements `AC-PLAN-001` and `AC-PLAN-006`. If the CLI wiring exposes a gap not covered by `TSK-031-01`, fix it in `src/deviate/cli/micro.py`.
  - **Details**:
    - **Red**: Add a test in `tests/test_cli/test_micro.py` that drives the `deviate micro run` surface (`_run_tdd_cycle` → `_run_red_phase` → `_adjudicate_red_no_failing_test` → `_run_judge_phase`) on a `TSK-029-02`-style task whose RED phase routes to `failure_kind == "no_failing_test"` with `session.red_commit_sha == ""`. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")` fixture and mock `_invoke_agent` to return a `COMPLIANCE_PASS` / `skip_refactor` manifest that declares a regression-pin `test_file`. Assert the task reaches a COMPLETED status, `pending_judge_action == "skip_refactor"`, the declared regression-pin test remains on disk, and no `ROLLBACK_BOUNDARY_MISSING` traceback appears in the captured output.
    - **Green**: Confirm the `_run_red_phase` → `_adjudicate_red_no_failing_test` → `_run_judge_phase` wiring drives the guarded `_apply_judge_verdict` forward route. If the integration path reveals a missing `declared_paths` or `red_baseline` thread, repair it in `src/deviate/cli/micro.py`; otherwise no production change is required beyond `TSK-031-01`.
    - **Refactor**: Reuse the existing `_run_pytest`-mock fixture and `SessionState.load(session_path)` setup already present in `tests/test_cli/test_micro.py`; do not duplicate the git-env helper — use `_git_env()` and `tmp_git_repo` from `tests/conftest.py` so no git command runs against the real repo.
    - **Edge Cases**: Assert the regression-pin test file survives the `_restore_worktree_to_baseline(..., keep_paths=declared)` restore. Assert the full suite stays under 30s because `_run_pytest` is mocked. Assert a `COMPLIANCE_VIOLATION` variant still routes to `revert_before` and never COMPLETES.
    - **Acceptance**: `pytest tests/test_cli/test_micro.py -v` passes; `ruff check tests/test_cli/test_micro.py` is clean; `pytest tests/ -v` completes under 30s with the mocked `_run_pytest`.
  - **Dependency**: TSK-031-01

---

## Phase 3: Align specs and changelog with the guarded routing
**Goal**: Reflect the guarded already-exists COMPLETE route and the retained fail-closed regression-files gate in the authoritative specs and the changelog.

### Tasks

- TSK-031-03: Update the `no_failing_test` adjudication contract in the specs and add a changelog entry
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run check`
  - **Estimated Time**: 30 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: The constitution (§5 Definition of Done) and `AGENTS.md` require user-visible behavior changes to update the authoritative `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit, and to append a `CHANGELOG.md` `[Unreleased]` bullet. The hard-crash fix is a user-visible behavior change (`US-031-01`). Documents `AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003`, and `AC-PLAN-006`.
  - **Details**:
    - **Red**: N/A (IMMEDIATE — docs-only).
    - **Green**: N/A (IMMEDIATE — docs-only).
    - **Implementation**: In `specs/DeviaTDD-api.md` (line 595-604), state that a `COMPLIANCE_PASS` already-exists pass on `failure_kind == "no_failing_test"` completes via `skip_refactor` even with partial AC evidence, and that `ROLLBACK_BOUNDARY_MISSING` applies only to a genuine `revert_to_red` with a real RED commit. In `specs/DeviaTDD-architecture.md` §3 (line 288), describe the guarded already-exists COMPLETE route, the relaxed AC-token citation check, and the retained `_require_tdd_declared_regression_files` fail-closed gate. Append a bullet under `CHANGELOG.md` `[Unreleased]` `### Fixed` describing the user-visible hard-crash fix.
    - **Refactor**: Keep terminology consistent with the existing spec wording (`no_failing_test`, `skip_refactor`, `ROLLBACK_BOUNDARY_MISSING`, `_require_tdd_declared_regression_files`); do not rename existing tokens.
    - **Edge Cases**: Verify the architecture §3 note still records that a genuine `revert_to_red` with an empty SHA is fatal, so the docs do not overstate the relaxation.
    - **Acceptance**: `mise run check` exits 0; `grep` confirms the `no_failing_test` adjudication contract and the `### Fixed` changelog bullet are present.
  - **Dependency**: TSK-031-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-031-01) -> Phase 2 (TSK-031-02) -> Phase 3 (TSK-031-03)

**Critical Dependency Chains**:
- TSK-031-02 depends on TSK-031-01 (the CLI integration test requires the guarded routing)
- TSK-031-03 depends on TSK-031-01 (the specs and changelog document the final behavior)

**Risk Hotspots**:
- Guarding on `failure_kind == "no_failing_test"` must not skip the evidence gate for `test_defect` or `mechanical` routes — restrict the guard strictly to `no_failing_test`.
- Relaxing the COMPLETED-write evidence check must not weaken fail-closed on missing regression files — keep `_require_tdd_declared_regression_files` and the declared-path presence gate intact.
- The shared `_apply_judge_verdict` must not regress the manual `judge post` path — the guard keys on `session.failure_kind`, which both auto and manual paths set (AC-PLAN-007).
- Double COMPLETED append on the `no_failing_test` forward route — verify a single COMPLETED transition per task in the tests.
- No existing flow mapping is available — preserve the empty `flow_refs` and do not create Product-layer or DeviaTDD-setup work.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py` (TSK-031-01, TSK-031-02).

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/031-judge-revert-boundary-no-failing-test/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

**E2E Scope Note**: No `[E2E]` bats task is emitted. The plan scopes testing to the unit sandbox (`tests/test_micro/test_judge.py`) and the `_run_pytest`-mocked integration sandbox (`tests/test_cli/test_micro.py`), which reproduces the user-facing `deviate micro run` surface deterministically while keeping the full suite under 30s per constitution §3. A real-agent bats E2E is non-deterministic and would exceed the test-performance budget.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
