## Plan Summary
- **Issue**: ISS-ADH-021 — Escalate no_failing_test to RED; never GREEN without red_commit_sha
- **Implementation Strategy**: Keep `no_failing_test` / `revert_before` on the RED escalate path until a RED-phase failing-test commit exists. Refuse GREEN when `session.red_commit_sha` is empty or a `docs(...): add judge feedback` SHA. Make missing-boundary `revert_to_red` raise `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING` instead of catching it and training GREEN.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it hardens C1 TDD GREEN entry, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase state and the TDD runner)

## Acceptance Contract

**Scenario AC-PLAN-001: Dispatch RED after `no_failing_test` / `revert_before`, never GREEN**
- **Source Outline**: `AO-021-01`
- **Upstream Traceability**: `US-021-01`, `FR-ADHOC-021`, `AC-ADHOC-021-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_tdd_cycle` (pending `revert_before` calls `_escalate("no_failing_test_adjudicated")` then `continue`); `src/deviate/cli/micro.py:_escalate_to_new_red` (calls `_clear_judge_retry_gate` after `_run_red_phase`)
- **Given**: JUDGE returns `revert_before` on `failure_kind` `no_failing_test` and the retry RED still records no `red_commit_sha`.
- **When**: `_run_tdd_cycle` escalates with reason `no_failing_test_adjudicated` and `_clear_judge_retry_gate` runs.
- **Then**: the next `INVOKE_AGENT` phase is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`, and GREEN is never invoked.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Refuse GREEN without a RED-phase failing-test SHA**
- **Source Outline**: `AO-021-02`
- **Upstream Traceability**: `US-021-02`, `FR-ADHOC-021`, `AC-ADHOC-021-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_green_phase` (no SHA gate today); `src/deviate/cli/micro.py:_commit_judge_feedback_and_advance` (writes `docs({tid}): add judge feedback for retry` and stamps `session.red_commit_sha`)
- **Given**: `session.red_commit_sha` is empty or the HEAD subject is `docs(...): add judge feedback for retry`.
- **When**: `_run_tdd_cycle` reaches GREEN entry or `_run_green_phase` starts.
- **Then**: the runner aborts or re-dispatches RED and does not invoke the GREEN agent.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Enter GREEN after a genuine RED failing-test commit**
- **Source Outline**: `AO-021-02`
- **Upstream Traceability**: `US-021-02`, `FR-ADHOC-021`, `AC-ADHOC-021-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase` (clears `session.red_commit_sha` at start; records HEAD after `test({scope}): RED phase - failing test`)
- **Given**: RED committed a failing test and `session.red_commit_sha` is that RED-phase commit.
- **When**: `_run_tdd_cycle` enters GREEN.
- **Then**: `_run_green_phase` invokes the GREEN agent against that standing RED contract.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Fail `revert_to_red` when the RED boundary is missing**
- **Source Outline**: `AO-021-03`
- **Upstream Traceability**: `US-021-03`, `FR-ADHOC-021`, `AC-ADHOC-021-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase` (`revert_to_red` raises `ROLLBACK_BOUNDARY_MISSING` when SHA is empty, then `except Exception` prints `ROLLBACK_FAILED` and calls `_commit_judge_feedback_and_advance`)
- **Given**: JUDGE returns `revert_to_red` and `session.red_commit_sha` is empty.
- **When**: `_run_judge_phase` runs the `revert_to_red` rollback branch.
- **Then**: the runner raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING`, skips `ROLLBACK_FAILED … proceeding with train feedback`, and leaves `red_commit_sha` unstamped by the feedback commit.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep `revert_to_red` TRAIN when a real RED SHA exists**
- **Source Outline**: `AO-021-03`
- **Upstream Traceability**: `US-021-03`, `FR-ADHOC-021`, `AC-ADHOC-021-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase` (`_execute_rollback(boundary_sha=session.red_commit_sha)` then `_commit_judge_feedback_and_advance`); `tests/test_cli/test_micro.py:test_judge_revert_to_red_advances_red_commit_sha`
- **Given**: `session.red_commit_sha` is a RED-phase failing-test commit.
- **When**: JUDGE returns `revert_to_red`.
- **Then**: the runner rolls back to that SHA, advances the boundary past the feedback commit, and retries GREEN.
- **Verification Mode**: automated

## Workstation Mapping
- **`src/deviate/cli/micro.py:_run_tdd_cycle`**: TARGET — stop GREEN fall-through after `no_failing_test_adjudicated`.
  - **Current State**: After `pending_judge_action == "revert_before"`, the loop calls `_escalate("no_failing_test_adjudicated")` and `continue`s. The next iteration treats an empty pending action as GREEN-ready.
  - **Changes Required**: After escalate (and before GREEN), require a RED-phase `session.red_commit_sha`. If the SHA is empty or pending action is still `revert_before`, escalate again or fail at the existing `red_attempts` cap. Do not call `_run_green_phase` on that path.
  - **Integration Surface**: `_escalate_to_new_red`, `_run_green_phase`, `_clear_judge_retry_gate`, `_NO_FAILING_TEST_FORWARD_ROUTES`.

- **`src/deviate/cli/micro.py:_escalate_to_new_red`**: TARGET — do not consume `revert_before` until RED lands a SHA.
  - **Current State**: It runs `_run_red_phase`, then `_clear_judge_retry_gate`, then logs `escalate_to_red`. A retry RED that re-adjudicates `no_failing_test` returns with empty SHA and `pending_judge_action == "revert_before"`. The clear then authorizes GREEN.
  - **Changes Required**: Call `_clear_judge_retry_gate` only when `session.red_commit_sha` is a real RED-phase failing-test commit. Keep `revert_before` when the SHA is still empty so the loop stays on RED.
  - **Integration Surface**: `_run_red_phase`, `_adjudicate_red_no_failing_test`, `_account_red_escalate` (keep the ISS-ADH-017 3-escalate cap).

- **`src/deviate/cli/micro.py:_clear_judge_retry_gate`**: TARGET — do not erase `revert_before` while the RED boundary is missing.
  - **Current State**: It always sets `pending_judge_action = ""` and `judge_rejected = False`.
  - **Changes Required**: Leave `revert_before` in place when `red_commit_sha` is empty, or move the empty-SHA check to the sole caller `_escalate_to_new_red` and keep this helper a pure consume. Prefer one ownership site so resume cannot GREEN solely because the gate was cleared.
  - **Integration Surface**: `_escalate_to_new_red`, `_raise_train_exhausted`, `_idle_after_tdd`.

- **`src/deviate/cli/micro.py:_run_green_phase`**: TARGET — refuse GREEN without a RED-phase SHA.
  - **Current State**: The function logs `PHASE_START` GREEN and invokes the agent with no SHA check.
  - **Changes Required**: Before `_invoke_agent`, require a non-empty `session.red_commit_sha` whose subject matches the RED-phase convention (`test(...): RED phase`), not `docs(...): add judge feedback`. Raise `PhaseFailedError` or return control for RED re-dispatch. Do not add production-file writes. Do not treat a passing suite as already-implemented.
  - **Integration Surface**: `_run_tdd_cycle` GREEN call site; `SessionState.red_commit_sha`.

- **`src/deviate/cli/micro.py:_run_red_phase`**: REFERENCE — SHA lifecycle stays as-is.
  - **Current State**: It sets `session.red_commit_sha = ""` at start. It records HEAD only after a failing-test commit. Passing / no-tests routes to `_adjudicate_red_no_failing_test` and never records a SHA.
  - **Changes Required**: None to the commit boundary. Keep `--no-judge` as a hard `PhaseFailedError`. Keep `skip_refactor` / bare `COMPLIANCE_PASS` completing without GREEN.
  - **Integration Surface**: `_adjudicate_red_no_failing_test`, `_commit_phase`.

- **`src/deviate/cli/micro.py:_run_judge_phase`**: TARGET — missing-boundary `revert_to_red` is fatal.
  - **Current State**: Empty SHA raises `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING: revert_to_red ...")`. The surrounding `except Exception` prints `ROLLBACK_FAILED` and still runs `_commit_judge_feedback_and_advance` plus `force_transition_to("GREEN")`.
  - **Changes Required**: Re-raise `PhaseFailedError` whose message contains `ROLLBACK_BOUNDARY_MISSING` for TDD `revert_to_red`. Do not print `ROLLBACK_FAILED … proceeding with train feedback` on that path. Do not call `_commit_judge_feedback_and_advance`. Do not retarget EXECUTE `pre_execute_sha` retry policy except to stop a shared `except Exception` from swallowing this TDD error.
  - **Integration Surface**: `_execute_rollback`, `_commit_judge_feedback_and_advance`, `_coerce_judge_action` (keep `test_defect` / `no_failing_test` → `revert_before`).

- **`src/deviate/cli/micro.py:_commit_judge_feedback_and_advance`**: TARGET — do not stamp a docs-feedback SHA as the RED boundary when none exists.
  - **Current State**: After `docs({tid}): add judge feedback for retry`, it sets `session.red_commit_sha = fb_head` whenever `fb_head` is non-empty.
  - **Changes Required**: Advance `red_commit_sha` onto the feedback commit only when the pre-call SHA is already a RED-phase failing-test commit. If the SHA is empty, leave it empty (or raise) so TRAIN cannot roll back to a docs commit.
  - **Integration Surface**: `_run_judge_phase` `revert_to_red` success path; `_resume_pending_judge_feedback`.

- **`tests/test_micro/test_orchestration.py`**: TARGET — pin `revert_before` / `no_failing_test` never GREEN.
  - **Current State**: `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` covers the already-satisfied `skip_refactor` path only.
  - **Changes Required**: Add a stub-JUDGE always-`revert_before` case (name may be `test_no_failing_test_revert_before_invokes_red_not_green`). After two adjudications, agent phases contain RED and JUDGE only, never GREEN, until a failing test is committed or the task fails. Keep `_run_pytest` mocked.
  - **Integration Surface**: `_run_tdd_cycle` / `deviate micro run` with patched `_invoke_agent` / `_run_test_cmd`.

- **`tests/test_micro/test_two_counter_retry.py`**: TARGET — pin escalate does not dispatch GREEN without a SHA.
  - **Current State**: File pins ISS-ADH-017 3/3 caps and the coerce matrix. It does not pin empty-SHA GREEN fall-through.
  - **Changes Required**: Add `test_escalate_to_red_does_not_dispatch_green_without_red_sha`. Keep `_MAX_RED_ATTEMPTS` / `_MAX_GREEN_ATTEMPTS` at 3. Keep `_coerce_judge_action` mapping. Mock `_run_pytest`.
  - **Integration Surface**: `_run_tdd_cycle` with patched `_run_red_phase` / `_run_green_phase` / `_run_judge_phase`.

- **`tests/test_micro/test_green.py`**: TARGET — GREEN entry refused when SHA is empty.
  - **Current State**: Direct `_run_green_phase` tests cover feedback injection and pass-through. They assume GREEN may start.
  - **Changes Required**: Add a pin that empty `session.red_commit_sha` raises or returns without `_invoke_agent`.
  - **Integration Surface**: `_run_green_phase`.

- **`tests/test_micro/test_rollback_safety.py` / `tests/test_cli/test_micro.py`**: TARGET — missing-boundary `revert_to_red` is fatal; real SHA still trains.
  - **Current State**: Rollback-safety pins `_execute_rollback` missing `boundary_sha`. CLI tests pin `revert_to_red` advancing SHA past feedback when a real RED SHA exists.
  - **Changes Required**: Add `test_revert_to_red_missing_red_commit_sha_is_fatal` (no `ROLLBACK_FAILED` proceed; SHA not rewritten to a feedback commit). Keep `test_judge_revert_to_red_advances_red_commit_sha` passing. Mock `_run_pytest` on CLI paths that would hit it.
  - **Integration Surface**: `_run_judge_phase`, `_commit_judge_feedback_and_advance`.

- **`specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md`**: TARGET — document the GREEN-entry invariant.
  - **Current State**: Specs describe RED no-failing-test adjudication and `ROLLBACK_BOUNDARY_MISSING` inside `_execute_rollback`. They do not state that GREEN requires a committed failing test plus a RED-phase SHA, or that swallowed `revert_to_red` missing-boundary errors are forbidden.
  - **Changes Required**: Document GREEN-entry (committed failing test + RED-phase `red_commit_sha`). Document that TDD `revert_to_red` with empty SHA is fatal and must not train GREEN. Same commit as the code change.
  - **Integration Surface**: Spec-alignment mandate.

- **`CHANGELOG.md`**: TARGET — `[Unreleased]` bullet for the runner fix.
  - **Current State**: Unreleased already notes RED no-failing-test routing to JUDGE and two-counter retry.
  - **Changes Required**: Add a user-visible bullet: `no_failing_test` / `revert_before` re-invokes RED (or fails) and never GREEN without a RED-phase SHA; missing-boundary `revert_to_red` is fatal.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: RED tests that pin illegal GREEN and fatal missing-boundary rollback
  - **Files**: `tests/test_micro/test_orchestration.py`, `tests/test_micro/test_two_counter_retry.py`, `tests/test_micro/test_green.py`, `tests/test_micro/test_rollback_safety.py`, `tests/test_cli/test_micro.py`
  - **Approach**: Stub agents and mock `deviate.cli.micro._run_pytest` / `_run_test_cmd`. Drive always-`revert_before` on `no_failing_test`. Assert agent phases exclude GREEN. Assert empty SHA refuses GREEN. Assert `revert_to_red` with empty SHA raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING`. Keep the existing real-SHA TRAIN pins green.
  - **Verification**: `uv run pytest tests/test_micro/test_orchestration.py tests/test_micro/test_two_counter_retry.py tests/test_micro/test_rollback_safety.py tests/test_cli/test_micro.py tests/test_micro/test_green.py -q -k "no_failing_test or revert_to_red or red_commit_sha or escalate"` fails on the new pins.

- **Phase 2**: Close the escalate fall-through and the GREEN SHA gate
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: After `_escalate_to_new_red`, consume `revert_before` only when `red_commit_sha` is a RED-phase failing-test commit. In `_run_tdd_cycle`, skip `_run_green_phase` while that SHA is missing. In `_run_green_phase`, refuse `_invoke_agent` without that SHA. Keep `_coerce_judge_action` and the 3/3 caps unchanged. Keep `skip_refactor` / `COMPLIANCE_PASS` completing without GREEN.
  - **Verification**: AC-PLAN-001, AC-PLAN-002, and AC-PLAN-003 pins pass.

- **Phase 3**: Make missing-boundary `revert_to_red` fatal
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Stop catching `ROLLBACK_BOUNDARY_MISSING` in `_run_judge_phase`. Do not print `ROLLBACK_FAILED` and proceed. Do not call `_commit_judge_feedback_and_advance` on that failure. Guard that helper so an empty SHA is not overwritten by `docs(...): add judge feedback for retry`. Leave EXECUTE `pre_execute_sha` policy in place.
  - **Verification**: AC-PLAN-004 and AC-PLAN-005 pins pass.

- **Phase 4**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: State the GREEN-entry invariant and fatal missing-boundary `revert_to_red` in the same commit as the runner change. Append one `[Unreleased]` bullet.
  - **Verification**: `mise run check` (ruff, format-check, types, pytest) exits 0.

## Data Flow Analysis
- **Input**: `SessionState.pending_judge_action` (`revert_before` / `revert_to_red`), `SessionState.failure_kind` (`no_failing_test`), `SessionState.red_commit_sha`, JUDGE `next_action`.
- **Transformation**: `_adjudicate_red_no_failing_test` routes a passing RED to JUDGE with no SHA. `_run_tdd_cycle` must escalate to `_run_red_phase` (or fail at `red_attempts >= 3`) until RED commits `test({scope}): RED phase - failing test` and stores that HEAD in `red_commit_sha`. `_clear_judge_retry_gate` consumes `revert_before` only after that SHA exists. `_run_green_phase` reads the SHA before `_invoke_agent`. `revert_to_red` threads the SHA into `_execute_rollback`; empty SHA raises `PhaseFailedError` and skips the docs-feedback stamp.
- **Output**: Next `INVOKE_AGENT` is RED or GREEN under a standing RED contract, or `PhaseFailedError` (`TRAIN_EXHAUSTED` / `ROLLBACK_BOUNDARY_MISSING`). Session JSON keeps an empty SHA rather than a docs-feedback SHA.
- **Storage**: `.deviate/session.json` fields `red_commit_sha`, `pending_judge_action`, `failure_kind`, `red_attempts`. No new ledger rows.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `skip_refactor` / bare `COMPLIANCE_PASS` on first passing RED now fails | High | Medium | Keep `_NO_FAILING_TEST_FORWARD_ROUTES` as the complete-without-GREEN exit. Pin `test_micro_red_no_failing_test_routes_to_judge_skip_refactor`. |
| Real `revert_to_red` TRAIN breaks because SHA advance is too strict | High | Medium | Advance onto the feedback commit only when the pre-call SHA already matches the RED-phase subject. Keep `test_judge_revert_to_red_advances_red_commit_sha`. |
| Shared `except Exception` change alters EXECUTE `pre_execute_sha` retry | Medium | Low | Narrow the re-raise to TDD `revert_to_red` `ROLLBACK_BOUNDARY_MISSING`. Do not retarget EXECUTE `max_judge_attempts`. |
| Clearing the gate too late loops RED without counting `red_attempts` | Medium | Medium | Keep `_account_red_escalate` at the start of `_escalate_to_new_red`. Stop at `_MAX_RED_ATTEMPTS` (3) with `TRAIN_EXHAUSTED`. |
| Crash mid-escalate resumes GREEN because the gate was already cleared | High | Medium | Resume GREEN only when `red_commit_sha` is a RED-phase commit. Empty SHA re-enters RED or fails. |
| Un-mocked `_run_pytest` blows the suite budget | Medium | Low | Every new test that would hit `_run_pytest` mocks `deviate.cli.micro._run_pytest`. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (`git reset --hard`, `git rev-parse`, `git log`, `git commit`), file paths (worktree rollback / `git clean -fd`), session JSON persistence
Negative tests: GREEN agent is not invoked when `red_commit_sha` is empty; GREEN agent is not invoked when HEAD is a `docs(...): add judge feedback` SHA; `revert_to_red` with empty SHA does not print `ROLLBACK_FAILED` and proceed; `_commit_judge_feedback_and_advance` does not write a docs SHA into an empty `red_commit_sha`; always-`revert_before` `no_failing_test` never produces `INVOKE_AGENT phase: GREEN`
Constraints: no new dependencies; no hardcoded secrets; do not fatten GREEN; do not rename JUDGE verbs; do not add a new `next_action` token; do not invoke un-mocked `_run_pytest`; do not retarget EXECUTE rollback except to stop swallowing TDD `ROLLBACK_BOUNDARY_MISSING`

## Integration Points
- **`_coerce_judge_action`**: Keep `test_defect` / `no_failing_test` on a violation mapped to `revert_before`. Do not add a verb.
- **`_MAX_RED_ATTEMPTS` / `_MAX_GREEN_ATTEMPTS`**: Stay at 3 from ISS-ADH-017. `TRAIN_EXHAUSTED` still stops the loop.
- **`_execute_rollback`**: Still requires an explicit `boundary_sha`. Empty SHA already raises `ROLLBACK_BOUNDARY_MISSING`; the JUDGE caller must not swallow that error on TDD `revert_to_red`.
- **`_PRE_RED_SHA_PARENT_RE` / RED-phase subject**: Reuse the RED-phase convention (`test(...): RED phase`) to reject a docs-feedback SHA as a GREEN-entry boundary.
- **`SessionState`**: Reuse `red_commit_sha`, `pending_judge_action`, `failure_kind`. No new fields.

## Constitutional Alignment
- **Architecture**: This work stays in the Micro layer (RED → GREEN → JUDGE). It restores the fail-to-pass contract so GREEN writes `src/` only against a standing RED test (constitution §1 Micro-Layer Scope). Meso and Product layers stay untouched.
- **Testing**: pytest unit pins with mocked `_run_pytest` (constitution §3). Coverage targets the TDD loop, GREEN entry, and JUDGE rollback. Full suite stays under 30s.
- **Git Isolation**: Phase commits remain automatic at RED/GREEN/JUDGE boundaries. This issue does not add branch-mutating git in micro-layer agents. Rollback still uses an explicit SHA, never `HEAD~1`.
- **Product Layer**: `flow_refs` is empty. The runner fix preserves C1 TDD behavior and does not author or sync Product-layer flows.
