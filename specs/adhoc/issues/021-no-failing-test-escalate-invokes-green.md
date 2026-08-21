---
title: "Escalate no_failing_test to RED; never GREEN without red_commit_sha"
labels: [bugfix, adhoc, vertical-slice, micro, train]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-021
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py::_run_tdd_cycle` — TARGET: after `pending_judge_action == "revert_before"` the loop calls `_escalate("no_failing_test_adjudicated")` then `continue`s into `_run_green_phase` unless a later gate still blocks GREEN. Observed log: `PHASE_DECISION CYCLE decision=escalate_to_red reason=no_failing_test_adjudicated` followed by `INVOKE_AGENT phase: GREEN`.
  - `src/deviate/cli/micro.py::_escalate_to_new_red` — TARGET: logs `escalate_to_red` *after* `_run_red_phase` and `_clear_judge_retry_gate`. Clearing the one-shot JUDGE action even when the new RED never landed a failing-test commit lets the loop treat the cycle as ready for GREEN.
  - `src/deviate/cli/micro.py::_clear_judge_retry_gate` — TARGET: zeros `pending_judge_action` / `judge_rejected`. Must not consume `revert_before` / `no_failing_test` until `session.red_commit_sha` is a real RED-phase commit (failing-test SHA), not empty and not a later `docs(feedback)` commit.
  - `src/deviate/cli/micro.py::_run_red_phase` — REFERENCE: clears `session.red_commit_sha = ""` at phase start; writes the boundary only after a failing test is committed. `_adjudicate_red_no_failing_test` never records a RED SHA (uncommitted passing test + JUDGE `revert_before`).
  - `src/deviate/cli/micro.py::_run_green_phase` — TARGET: refuse to invoke the GREEN agent when there is no committed failing test / no RED boundary SHA. Vacuous GREEN is how production code (`classify_http_outcome` / backoff in the payments log) landed without a RED contract.
  - `src/deviate/cli/micro.py::_run_judge_phase` — TARGET: `revert_to_red` already raises `ROLLBACK_BOUNDARY_MISSING` when `session.red_commit_sha` is empty, but the surrounding `except Exception` prints `ROLLBACK_FAILED` and still calls `_commit_judge_feedback_and_advance` + `force_transition_to("GREEN")`. That must fail the task (or re-dispatch RED), not train GREEN.
  - `src/deviate/cli/micro.py::_commit_judge_feedback_and_advance` — TARGET: must not stamp `session.red_commit_sha` onto a `docs(<task>): add judge feedback for retry` commit when no RED-phase failing-test commit exists (observed SHA `b11770f` in the payments log).
  - `tests/test_micro/test_orchestration.py` — TARGET: extend `test_micro_red_no_failing_test_routes_to_judge_skip_refactor`; add always-`revert_before` / `no_failing_test` stubs that assert the next `INVOKE_AGENT` is RED (or `TRAIN_EXHAUSTED` / `PhaseFailedError`), never GREEN.
  - `tests/test_micro/test_two_counter_retry.py` — TARGET: pin that `escalate_to_red` / `no_failing_test_adjudicated` does not fall through to GREEN when RED did not commit a SHA.
  - `tests/test_cli/test_micro.py` / `tests/test_micro/test_rollback_safety.py` — TARGET: `revert_to_red` with empty `red_commit_sha` must not log `ROLLBACK_FAILED` and proceed; it must not advance the boundary onto a feedback commit.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document the GREEN-entry invariant (committed failing test + RED SHA) and that missing-boundary `revert_to_red` is fatal, not swallowed.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible runner fix.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices; this slice does not change that classifier.
- **Upstream Evidence**:
  - Payments worktree `.deviate/logs/run_20260821T145217.log` (2026-08-21), `deviate 2.20.2`, task `TSK-002-01` / issue `001-002`.
  - `PHASE_DECISION JUDGE rejected reroute=RED action=revert_before reason=no_failing_test_test_defect`
  - `PHASE_DECISION CYCLE decision=escalate_to_red reason=no_failing_test_adjudicated red_attempts: 2`
  - `INVOKE_AGENT phase: GREEN` (should have been RED)
  - later `JUDGE_REJECTED action=revert_to_red` then `ROLLBACK_FAILED ROLLBACK_BOUNDARY_MISSING: revert_to_red for TSK-002-01 has no session.red_commit_sha`
  - Pytest exit 0 was a bad RED contract, not “already implemented”; GREEN invented missing production symbols.

## The Problem Contract

`deviate micro` can log `escalate_to_red` after JUDGE `revert_before` / `no_failing_test` and then invoke GREEN anyway. GREEN writes production code with no committed failing test. A later `revert_to_red` cannot roll back because `session.red_commit_sha` was never a RED-phase commit (cleared at RED start, never reset on the adjudication path, then overwritten by a docs-feedback commit). Operators need the cycle to re-author RED (or fail the task) until a real RED boundary exists, and they need missing-boundary `revert_to_red` to stop rather than train GREEN.

## Scope Boundaries

### Hard Inclusions

- After JUDGE `revert_before` / cycle `no_failing_test_adjudicated` / `escalate_to_red`, the next agent invoke is RED, or the task fails (`TRAIN_EXHAUSTED` / `PhaseFailedError`). Never GREEN.
- Do not enter GREEN without both (a) a committed failing test from this task's RED phase and (b) `session.red_commit_sha` pointing at that RED-phase commit (subject matches the RED-phase convention, not `docs(...): add judge feedback`).
- `revert_to_red` must not execute rollback-or-train when the RED boundary is missing. `ROLLBACK_BOUNDARY_MISSING` is fatal for that action: do not catch it, print `ROLLBACK_FAILED`, and proceed to `_commit_judge_feedback_and_advance`.
- `_clear_judge_retry_gate` must not erase `revert_before` in a way that lets the TDD loop fall through to GREEN when `red_commit_sha` is still empty.
- Keep JUDGE verb names and the `_coerce_judge_action` matrix (`test_defect` / `no_failing_test` on a violation → `revert_before`). Keep the 3/3 two-counter caps from ISS-ADH-017.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.

### Defensive Exclusions

- Do **not** fatten GREEN (no extra production files, no “implement anyway” path when tests already pass).
- Do **not** change how adhoc/plan picks TDD vs IMMEDIATE.
- Do **not** solve GitHub #65 or #63 in this slice.
- Do **not** rename JUDGE verbs or add a new `next_action` token.
- Do **not** change Product / Macro / Meso layers, flow authoring, or `specs/_product/`.
- Do **not** retarget EXECUTE-mode `max_judge_attempts` or the EXECUTE `pre_execute_sha` rollback path except where a shared helper would otherwise swallow `ROLLBACK_BOUNDARY_MISSING` for TDD `revert_to_red`.
- Do **not** revert operator-local `.deviate/config.toml` (backend=pi, transport=cli, pi_rpc=false, timeout=1800, models.default=grok-4.6).
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked (AGENTS.md suite-budget mandate).
- Do **not** treat a passing RED suite as “behavior already exists” without JUDGE `skip_refactor` / `COMPLIANCE_PASS` (the payments case was a bad test, not existing behavior).

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-021`
- **Acceptance Criteria Tokens**: `AC-ADHOC-021-01`, `AC-ADHOC-021-02`, `AC-ADHOC-021-03`
- **Data Model Entities**: `SessionState.red_commit_sha`, `SessionState.pending_judge_action`, `SessionState.failure_kind` (`no_failing_test`) — no new ledger rows
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` `_run_red_phase` (clears SHA at start; records SHA only after failing-test commit)
  - `src/deviate/cli/micro.py` `_adjudicate_red_no_failing_test` (RED → JUDGE; `revert_before` returns without a RED SHA)
  - `src/deviate/cli/micro.py` `_escalate_to_new_red` / `_clear_judge_retry_gate` / `_run_tdd_cycle` GREEN fall-through
  - `src/deviate/cli/micro.py` `_run_judge_phase` `except Exception` after `revert_to_red` missing SHA
  - `specs/constitution.md` §1 Git Isolation (commits at phase boundaries) and Micro-Layer Scope (GREEN writes `src/` only against a standing RED contract)

## User Stories Ledger

- **US-021-01**: As a DeviaTDD operator running `deviate micro`, I want a `no_failing_test` / `revert_before` adjudication to re-invoke RED (or fail the task) so GREEN cannot invent production code against a passing or missing test. *(Ref: FR-ADHOC-021)*
- **US-021-02**: As a DeviaTDD operator, I want GREEN to start only when this task has a committed failing test and a RED boundary SHA so TRAIN rollback has a real anchor. *(Ref: FR-ADHOC-021)*
- **US-021-03**: As a DeviaTDD operator, I want `revert_to_red` to refuse to run when `session.red_commit_sha` is missing so the runner does not log `ROLLBACK_FAILED` and then stamp the boundary onto a docs-feedback commit. *(Ref: FR-ADHOC-021)*

## Acceptance Outline

- **AO-021-01** *(Ref: AC-ADHOC-021-01, US-021-01)*: After JUDGE `revert_before` / cycle `no_failing_test_adjudicated`, the runner dispatches RED or fails; it never invokes GREEN.
  - **Happy Path**: Two (or more) RED_NO_FAILING_TEST adjudications with `revert_before` log `escalate_to_red` and the next `INVOKE_AGENT` phase is RED, until a failing test is committed or `red_attempts` hits the existing cap (`TRAIN_EXHAUSTED`).
  - **Error Category**: A stub JUDGE that always `revert_before`s on `no_failing_test` never produces `INVOKE_AGENT phase: GREEN` on that path.
  - **Boundary Category**: `_clear_judge_retry_gate` after `_escalate_to_new_red` does not authorize GREEN while `red_commit_sha` is empty.

- **AO-021-02** *(Ref: AC-ADHOC-021-02, US-021-02)*: GREEN requires a committed failing test and a RED-phase `red_commit_sha`.
  - **Happy Path**: After a genuine RED commit (test command non-zero, SHA recorded), GREEN may run and TRAIN (`revert_to_red`) keeps that RED contract.
  - **Error Category**: `_run_green_phase` / the TDD loop aborts or re-dispatches RED when `red_commit_sha` is empty or the worktree has no committed failing test for this task.
  - **Boundary Category**: A `docs(...): add judge feedback` SHA is not accepted as the RED boundary.

- **AO-021-03** *(Ref: AC-ADHOC-021-03, US-021-03)*: Missing-boundary `revert_to_red` is fatal, not swallowed.
  - **Happy Path**: With a real RED SHA, `revert_to_red` still rolls back to that SHA, advances past a feedback commit, and retries GREEN.
  - **Error Category**: Empty `red_commit_sha` raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING` and does not print `ROLLBACK_FAILED … proceeding with train feedback`.
  - **Boundary Category**: `_commit_judge_feedback_and_advance` does not run on that failure, so `red_commit_sha` is not rewritten to the feedback commit.

## Edge Cases and Boundaries

- First RED of a task that exits 0 still routes to JUDGE (`_adjudicate_red_no_failing_test`); `skip_refactor` / bare `COMPLIANCE_PASS` still completes without GREEN (existing already-satisfied path stays).
- `--no-judge` on a no-failing-test RED remains a hard `PhaseFailedError` (adjudication disabled).
- `TRAIN_EXHAUSTED` after three RED escalates still stops; this issue does not raise or lower the ISS-ADH-017 caps.
- Crash mid-escalate: resume must not invoke GREEN solely because `pending_judge_action` was cleared while `red_commit_sha` is empty.
- EXECUTE-mode rollback (`pre_execute_sha`) is out of contract unless a shared `except Exception` would otherwise swallow TDD `revert_to_red` missing-boundary errors — fix the TDD path without retargeting EXECUTE retry policy.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: ≤ 500ms CLI init; the GREEN-entry SHA check is in-process session/git rev-parse, ≤ 50ms on the hot TDD loop (no extra agent call).
- Throughput: no additional agent calls versus a correct RED retry; the change only blocks the illegal GREEN invoke. Full test suite remains < 30s; tests that would drive `_run_pytest` must mock `deviate.cli.micro._run_pytest`.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_micro/test_orchestration.py` — `test_no_failing_test_revert_before_invokes_red_not_green` (name may vary): after two `no_failing_test` / `revert_before` adjudications, agent phases contain RED and JUDGE only, never GREEN, until a failing test is committed or the task fails.
  - `tests/test_micro/test_two_counter_retry.py` — `test_escalate_to_red_does_not_dispatch_green_without_red_sha`.
  - `tests/test_cli/test_micro.py` / `tests/test_micro/test_rollback_safety.py` — `test_revert_to_red_missing_red_commit_sha_is_fatal` (no `ROLLBACK_FAILED` proceed; `red_commit_sha` unchanged / not a feedback commit).
  - `tests/test_micro/test_green.py` — GREEN entry refused when `session.red_commit_sha` is empty.
- **Integration Sandbox Targets**:
  - Stub-agent `_run_tdd_cycle` with patched `_run_red_phase` / `_run_green_phase` / `_run_judge_phase` and mocked `_run_pytest` / `_run_test_cmd`: RED exit 0 → JUDGE `revert_before` → escalate → assert next invoke is RED or `PhaseFailedError`, then `revert_to_red` with empty SHA raises rather than trains.

## Demonstration Path

```bash
# Mocked TDD-loop pins (no live agent, no un-mocked pytest)
uv run pytest tests/test_micro/test_orchestration.py tests/test_micro/test_two_counter_retry.py tests/test_micro/test_rollback_safety.py tests/test_cli/test_micro.py tests/test_micro/test_green.py -q -k "no_failing_test or revert_to_red or red_commit_sha or escalate"
```
