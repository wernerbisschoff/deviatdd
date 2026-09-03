# Implementation Tasks: `feat/adhoc/021-no-failing-test-escalate-invokes-green`

## Phase 1: Keep RED After `no_failing_test` / `revert_before`
**Goal**: After JUDGE `revert_before` on `failure_kind` `no_failing_test`, the TDD loop re-invokes RED (or fails at the existing cap) and never calls GREEN.

### Tasks

- TSK-021-01: Dispatch RED after `no_failing_test` / `revert_before`, never GREEN
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_two_counter_retry.py -q -k "no_failing_test_revert_before or escalate_to_red_does_not_dispatch or skip_refactor"`
  - **Estimated Time**: 90 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_orchestration.py`
    - `tests/unit/test_micro/test_two_counter_retry.py`
  - **Rationale**: US-021-01 and `AC-PLAN-001` require the cycle after `no_failing_test_adjudicated` to stay on RED. `_run_tdd_cycle` at `src/deviate/cli/micro.py` calls `_escalate("no_failing_test_adjudicated")` on `pending_judge_action == "revert_before"` then `continue`s. `_escalate_to_new_red` always runs `_clear_judge_retry_gate` after `_run_red_phase`, so a retry RED that records no `red_commit_sha` still zeros the gate and the next iteration treats GREEN as ready. Tests in `tests/unit/test_micro/test_orchestration.py` and `tests/unit/test_micro/test_two_counter_retry.py` pin agent phases. Constitution §1 Micro-Layer Scope: GREEN writes `src/` only against a standing RED contract.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_orchestration.py` add `test_no_failing_test_revert_before_invokes_red_not_green`. Stub JUDGE to always return `revert_before` on `failure_kind` `no_failing_test`. Stub agents. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess`. After two (or more) adjudications, assert recorded `INVOKE_AGENT` phases contain RED and JUDGE only, never GREEN, until a failing test is committed or the task raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. Keep `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` passing. In `tests/unit/test_micro/test_two_counter_retry.py` add `test_escalate_to_red_does_not_dispatch_green_without_red_sha`. Patch `_run_red_phase` so it returns with empty `session.red_commit_sha` and `pending_judge_action == "revert_before"`. Patch `_run_green_phase` as a counter. Mock `_run_pytest`. Drive `_run_tdd_cycle`. Assert `_run_green_phase` is never called. Assert `_MAX_RED_ATTEMPTS` stays 3 and `_account_red_escalate` still stops the loop.
    - **Green**: In `_escalate_to_new_red`, call `_clear_judge_retry_gate` only when `session.red_commit_sha` is a RED-phase failing-test commit. Keep `revert_before` when the SHA is empty so the loop stays on RED. In `_run_tdd_cycle`, after escalate and before GREEN, require that SHA. If the SHA is empty or pending action is still `revert_before`, escalate again or fail at `red_attempts >= 3`. Do not call `_run_green_phase` on that path. Keep `_NO_FAILING_TEST_FORWARD_ROUTES` as the complete-without-GREEN exit. Keep `_coerce_judge_action` mapping `test_defect` / `no_failing_test` to `revert_before`.
    - **Refactor**: Prefer one ownership site for the empty-SHA gate (caller `_escalate_to_new_red`, or `_clear_judge_retry_gate`) so resume cannot GREEN solely because the gate was cleared. Keep `_account_red_escalate` at the start of `_escalate_to_new_red`.
    - **Edge Cases**: Crash mid-escalate: resume GREEN only when `red_commit_sha` is a RED-phase commit; empty SHA re-enters RED or fails. `skip_refactor` / bare `COMPLIANCE_PASS` on first passing RED still completes without GREEN. `--no-judge` on a no-failing-test RED stays a hard `PhaseFailedError`. Do not invoke un-mocked `_run_pytest`.
    - **Acceptance**: Always-`revert_before` on `no_failing_test` never produces `INVOKE_AGENT phase: GREEN`. Next invoke is RED, or `TRAIN_EXHAUSTED` / `PhaseFailedError`. Caps stay 3. Forward-route skip_refactor pin still passes.

---

## Phase 2: GREEN Entry Requires a RED-Phase SHA
**Goal**: `_run_green_phase` invokes the GREEN agent only when `session.red_commit_sha` is this task's RED-phase failing-test commit.

### Tasks

- TSK-021-02: Refuse GREEN without a RED-phase failing-test SHA
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_green.py -q -k "red_commit_sha or judge_feedback"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_green.py`
  - **Rationale**: US-021-02, `AC-PLAN-002`, and `AC-PLAN-003` require GREEN to start only with a committed failing test and a RED-phase `red_commit_sha`. `_run_green_phase` at `src/deviate/cli/micro.py:1407` logs `PHASE_START` GREEN and invokes the agent with no SHA check. `_commit_judge_feedback_and_advance` can stamp `session.red_commit_sha` onto `docs({tid}): add judge feedback for retry`. `_run_red_phase` already clears the SHA at start and records HEAD only after `test({scope}): RED phase - failing test`. Tests in `tests/unit/test_micro/test_green.py` pin the entry gate. Constitution §1 Micro-Layer Scope and Git Isolation: GREEN writes `src/` against a standing RED commit boundary.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_green.py` add a pin that empty `session.red_commit_sha` raises `PhaseFailedError` or returns without `_invoke_agent`. Add a pin that a HEAD / SHA whose subject is `docs(...): add judge feedback for retry` is refused the same way. Add a happy-path pin: after RED committed a failing test and `session.red_commit_sha` is that RED-phase commit (subject matches `test(...): RED phase`), `_run_green_phase` does invoke the GREEN agent. Mock `deviate.cli.micro._run_pytest` on every path that would hit it. Keep existing feedback-injection and pass-through pins.
    - **Green**: In `_run_green_phase`, before `_invoke_agent`, require a non-empty `session.red_commit_sha` whose subject matches the RED-phase convention (`test(...): RED phase`), not `docs(...): add judge feedback`. Raise `PhaseFailedError` or return control for RED re-dispatch. Reuse `_PRE_RED_SHA_PARENT_RE` / the RED-phase subject. Do not add production-file writes. Do not treat a passing suite as already-implemented. Do not fatten GREEN.
    - **Refactor**: Keep the SHA check next to the existing `PHASE_START` GREEN log so every call site (`_run_tdd_cycle` and direct tests) shares one gate. Do not add a `SessionState` field.
    - **Edge Cases**: Resume GREEN only when the SHA is a RED-phase commit. Empty SHA must not invoke the agent. A docs-feedback SHA must not invoke the agent. Genuine RED SHA still trains later via `revert_to_red`.
    - **Acceptance**: Empty SHA and docs-feedback SHA never call `_invoke_agent` for GREEN. Genuine RED-phase SHA still enters GREEN. No new dependencies. Constitution §3 suite budget stays under 30 seconds via the mock.
  - **Dependency**: TSK-021-01

---

## Phase 3: Fatal Missing-Boundary `revert_to_red`
**Goal**: `revert_to_red` with empty `session.red_commit_sha` raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING`. A real RED SHA still trains GREEN.

### Tasks

1. In `src/deviate/cli/micro.py::_is_red_phase_failing_test_sha`, refuse every empty / whitespace SHA. Delete `return not (root / ".git").exists()`.
2. Refuse `docs(...): add judge feedback for retry` unless `_feedback_sha_rests_on_red_phase` finds a `_PRE_RED_SHA_PARENT_RE` ancestor. Do not accept an orphan docs-feedback SHA.
3. Accept GREEN only when the SHA subject matches `_PRE_RED_SHA_PARENT_RE` (`test(...): RED phase`) or is a docs-feedback SHA that rests on that RED ancestor (TRAIN). Do not `return True` for every other non-empty SHA.
4. Keep raising `PhaseFailedError` with `GREEN_ENTRY_REFUSED` before `_invoke_agent` when the gate fails so `test_green_refuses_empty_red_commit_sha_without_invoke` stays at invoke_count 0.
5. Keep `test_green_invokes_agent_with_red_phase_red_commit_sha` passing (AC-PLAN-003).
6. Seed `session.red_commit_sha` with a RED-phase failing-test commit in `_setup_session_and_task` and `_capture_green_prompt` so `TestGreenDiagnosticSurface` and the judge-feedback prompt pins still enter GREEN. Do not change those tests' assertions. Do not weaken `TestGreenRedCommitShaGate`.
  - **Judge Feedback**: COMPLIANCE_VIOLATION: `_is_red_phase_failing_test_sha` treats an empty SHA as a valid GREEN boundary when `.git` is missing, and it aborts existing `TestGreenDiagnosticSurface` / prompt-assembly callers that use `tmp_git_repo` with empty `red_commit_sha`. AC-PLAN-002 forbids invoking GREEN without a RED-phase failing-test SHA. AC-PLAN-003 still requires a genuine RED SHA to enter GREEN. The next GREEN attempt must:
  - **Judge Feedback**: COMPLIANCE_VIOLATION: `_is_red_phase_failing_test_sha` returns False for every non-empty SHA that is not a `_PRE_RED_SHA_PARENT_RE` subject and not a `docs(...): add judge feedback for retry` commit with a RED ancestor. `_run_red_phase` still sets `session.red_commit_sha` to `git rev-parse HEAD` after `_commit_phase` returns True. Runner tests mock `_commit_phase`, so HEAD stays `initial` or `chore: seed` and GREEN_ENTRY_REFUSED fires (AC-PLAN-003). AC-PLAN-002 Given only refuses an empty SHA or a docs-feedback SHA. The next GREEN attempt must:
1. In `src/deviate/cli/micro.py::_is_red_phase_failing_test_sha`, keep refusing empty / whitespace SHA (`return False` with no `.git` missing bypass).
2. Keep refusing `docs(...): add judge feedback for retry` unless `_feedback_sha_rests_on_red_phase` finds a `_PRE_RED_SHA_PARENT_RE` ancestor.
3. Keep accepting a SHA whose subject matches `_PRE_RED_SHA_PARENT_RE`.
4. Accept any other resolvable non-empty SHA (including `initial` / `chore: seed` HEAD that `_run_red_phase` records after a failing test). Do not `return False` solely because the subject is not `test(...): RED phase`.
5. Keep raising `PhaseFailedError` with `GREEN_ENTRY_REFUSED` before `_invoke_agent` when the gate fails so `test_green_refuses_empty_red_commit_sha_without_invoke` and `test_green_refuses_docs_judge_feedback_red_commit_sha_without_invoke` stay at invoke_count 0.
6. Keep `test_green_invokes_agent_with_red_phase_red_commit_sha` passing (AC-PLAN-003).
7. Do not weaken `TestGreenRedCommitShaGate`. Do not edit tests outside `tests/unit/test_micro/test_green.py`.
- TSK-021-03: Fail `revert_to_red` when the RED boundary is missing
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_rollback_safety.py tests/unit/test_cli/test_micro.py -q -k "revert_to_red"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_rollback_safety.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-021-03, `AC-PLAN-004`, and `AC-PLAN-005` require missing-boundary `revert_to_red` to be fatal and real-SHA TRAIN to stay. `_run_judge_phase` already raises `ROLLBACK_BOUNDARY_MISSING` when SHA is empty, then `except Exception` prints `ROLLBACK_FAILED` and calls `_commit_judge_feedback_and_advance`, which stamps `session.red_commit_sha = fb_head`. `test_judge_revert_to_red_advances_red_commit_sha` in `tests/unit/test_cli/test_micro.py` pins the real-SHA path. Constitution §1 Git Isolation: rollback uses an explicit SHA, never `HEAD~1`.
  - **Details**:
    - **Red**: Add `test_revert_to_red_missing_red_commit_sha_is_fatal` in `tests/unit/test_micro/test_rollback_safety.py` or `tests/unit/test_cli/test_micro.py`. Seed `session.red_commit_sha = ""`. Stub JUDGE `next_action` to `revert_to_red`. Mock `deviate.cli.micro._run_pytest`. Assert `_run_judge_phase` raises `PhaseFailedError` whose message contains `ROLLBACK_BOUNDARY_MISSING`. Assert stdout does not contain `ROLLBACK_FAILED` followed by proceeding with train feedback. Assert `red_commit_sha` stays empty and is not a `docs(...): add judge feedback` SHA. Keep `test_judge_revert_to_red_advances_red_commit_sha` passing: with a RED-phase failing-test SHA, the runner rolls back to that SHA, advances past the feedback commit, and retries GREEN.
    - **Green**: In `_run_judge_phase`, re-raise `PhaseFailedError` whose message contains `ROLLBACK_BOUNDARY_MISSING` for TDD `revert_to_red`. Do not print `ROLLBACK_FAILED … proceeding with train feedback` on that path. Do not call `_commit_judge_feedback_and_advance` on that failure. In `_commit_judge_feedback_and_advance`, advance `red_commit_sha` onto the feedback commit only when the pre-call SHA is already a RED-phase failing-test commit. If the SHA is empty, leave it empty. Narrow the shared `except Exception` so EXECUTE `pre_execute_sha` retry is unchanged except that it no longer swallows this TDD error. Do not rename JUDGE verbs. Do not add a `next_action` token. Do not retarget EXECUTE `max_judge_attempts`.
    - **Refactor**: Keep `_execute_rollback` requiring an explicit `boundary_sha`. Share no new helper unless the re-raise and the empty-SHA stamp guard would otherwise duplicate the RED-phase subject check from TSK-021-02.
    - **Edge Cases**: Real RED SHA still trains GREEN (`AC-PLAN-005`). Empty SHA must not overwrite the boundary with a docs-feedback commit. EXECUTE-mode rollback stays on `pre_execute_sha`. `revert_before` missing-boundary behavior stays out of this slice except where the shared `except` would swallow the TDD error.
    - **Acceptance**: Empty-SHA `revert_to_red` raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING` and does not train GREEN. Real-SHA `revert_to_red` still rolls back, advances, and retries GREEN. `_run_pytest` stays mocked on CLI paths that would hit it.
  - **Dependency**: TSK-021-02

---

## Phase 4: Spec and Changelog Alignment
**Goal**: Document the GREEN-entry invariant and fatal missing-boundary `revert_to_red`. Append one `[Unreleased]` bullet.

### Tasks

- TSK-021-04: Align API, architecture, and CHANGELOG with the GREEN-entry invariant
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run check`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: Spec-alignment mandate and constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same implementation change as the runner fix. US-021-01, US-021-02, US-021-03 and `AC-PLAN-001` through `AC-PLAN-005` are the user-visible runner contract: `no_failing_test` / `revert_before` re-invokes RED (or fails) and never GREEN without a RED-phase SHA; missing-boundary `revert_to_red` is fatal.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, state that GREEN entry requires a committed failing test plus a RED-phase `red_commit_sha` (subject matches `test(...): RED phase`, not `docs(...): add judge feedback`). State that after `no_failing_test` / `revert_before` / `no_failing_test_adjudicated` the next `INVOKE_AGENT` is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. State that TDD `revert_to_red` with empty SHA raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING` and must not print `ROLLBACK_FAILED` and proceed. In `specs/DeviaTDD-architecture.md`, document the same GREEN-entry invariant and the fatal missing-boundary path on C1 (`deviate` CLI). Keep `_coerce_judge_action` and the 3/3 caps from ISS-ADH-017. Append one bullet under `CHANGELOG.md` `[Unreleased]`: `no_failing_test` / `revert_before` re-invokes RED (or fails) and never GREEN without a RED-phase SHA; missing-boundary `revert_to_red` is fatal.
    - **Refactor**: Reuse existing Micro-layer / TRAIN wording. Do not add a new JUDGE verb in the specs. Do not author or sync Product-layer flows.
    - **Edge Cases**: Do not retarget EXECUTE `pre_execute_sha` or `max_judge_attempts` in the specs. Keep `skip_refactor` / `COMPLIANCE_PASS` as the complete-without-GREEN exit. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture text state the GREEN-entry SHA rule and fatal missing-boundary `revert_to_red`. CHANGELOG `[Unreleased]` has the user-visible bullet. `mise run check` exits 0. Product / Macro / Meso files stay unmodified.
  - **Dependency**: TSK-021-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

**Critical Dependency Chains**:
- TSK-021-01 must precede TSK-021-02
- TSK-021-02 must precede TSK-021-03
- TSK-021-03 must precede TSK-021-04

**Risk Hotspots**:
- `skip_refactor` / bare `COMPLIANCE_PASS` on first passing RED fails if `_NO_FAILING_TEST_FORWARD_ROUTES` is broken
- Real `revert_to_red` TRAIN breaks if SHA advance requires a RED-phase subject too strictly
- Shared `except Exception` change swallows or retargets EXECUTE `pre_execute_sha` retry
- Clearing the gate too late loops RED without counting `red_attempts`
- Crash mid-escalate resumes GREEN because the gate was already cleared
- Un-mocked `_run_pytest` blows the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/021-no-failing-test-escalate-invokes-green/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
