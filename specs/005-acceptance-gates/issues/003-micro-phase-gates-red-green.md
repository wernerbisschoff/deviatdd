---
title: "Micro Phase Gates: Non-Blocking RED Checkpoint and Blocking GREEN Gate"
labels: [enhancement, vertical-slice, acceptance-gates, micro-layer]
source_file: "specs/005-acceptance-gates/issues/003-micro-phase-gates-red-green.md"
blocked_by: ["005-002"]
coordinates_with: ["005-002"]
issue_id: 005-003
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/005-acceptance-gates/`
- **Local Issue File**: `specs/005-acceptance-gates/issues/003-micro-phase-gates-red-green.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py:1122-1128` — MODIFY: `_run_red_phase` stops raising `PhaseFailedError` on `_run_test_cmd` returncode 0; it builds a `RedHandoffAdvisory` with `passes: True`, `severity: "warning"`, logs `RED_PASSED_WARNING`, and completes the phase.
  - `src/deviate/cli/micro.py:1062-1160` — MODIFY: `_run_red_phase` returns the advisory to the caller; the RED transition row is appended on every run; no persistent record of the advisory is written.
  - `src/deviate/cli/micro.py` — ADD: transient `RedHandoffAdvisory` Pydantic model (`task_id`, `phase = "RED"`, `passes`, `severity`) co-located with the phase runners; never serialized to `tasks.jsonl`, `.deviate/`, or any ledger.
  - `src/deviate/cli/micro.py:1298` — MODIFY: `_run_green_phase` requires `_run_test_cmd` returncode 0; on failure it sets `session.train_feedback` and routes to JUDGE (existing `train_feedback` retry path).
  - `src/deviate/cli/micro.py:1306` — REFERENCE: failure routing writes the feedback into `session.train_feedback` exactly as today; no new retry threshold is introduced.
  - `src/deviate/cli/micro.py:1391` — REFERENCE: `_MAX_JUDGE_FEEDBACK = 3` bounds JUDGE retries; unchanged.
  - `src/deviate/cli/micro.py:1290` — REFERENCE: `session.train_feedback = ""` clears feedback after a pass; unchanged.
  - `src/deviate/core/run_logger.py` — REFERENCE: `log_event` facility for the `RED_PASSED_WARNING` observability event.
  - `src/deviate/state/ledger.py:81-98` — REFERENCE: `TaskRecord` (with the optional `acceptance_criteria` field from issue `005-002`) drives `model_validate` in the runners; the advisory never becomes a status.
  - `tests/unit/test_micro/test_red.py` — TARGET: extend with advisory behavior; mock `deviate.cli.micro._run_pytest`.
  - `tests/unit/test_micro/test_green.py` — TARGET: extend with gate and JUDGE-routing behavior; mock `deviate.cli.micro._run_pytest`.
- **Upstream Evidence**:
  - `specs/005-acceptance-gates/prd.md:14` — Hard directive: replace RED pass-rejection with a non-blocking `RedHandoffAdvisory` carried in-memory to GREEN.
  - `specs/005-acceptance-gates/prd.md:15` — Hard directive: GREEN keeps `train_feedback` routing to JUDGE; no new retry mechanism.
  - `specs/005-acceptance-gates/prd.md:45-50` — `RedHandoffAdvisory` schema: transient; never serialized.
  - `specs/005-acceptance-gates/prd.md:123-149` — FR-005-03 and FR-005-04 acceptance outlines and state transitions.
  - `specs/005-acceptance-gates/prd.md:194-197` — RESOLVED-Q-001 (advisory is in-memory only) and RESOLVED-Q-002 (GREEN routes to JUDGE; REFACTOR raises).
  - `specs/005-acceptance-gates/prd.md:149` — Merge authorization: FR-005-04 "may merge with FR-005-03"; this slice merges them because the advisory contract spans both runners.

## The Problem Contract

The micro phase loop runs RED, GREEN, and JUDGE for each task. Today a RED run whose test suite passes raises `PhaseFailedError` — the loop treats a passing test as a RED violation. This issue makes RED a non-blocking checkpoint: RED always completes, records its transition, and hands an in-memory `RedHandoffAdvisory` to GREEN. A passing test produces a `warning` advisory; a failing test produces an `ok` advisory.

GREEN becomes the blocking gate: returncode 0 appends the GREEN transition; a non-zero returncode routes to JUDGE via `train_feedback`, bounded by `_MAX_JUDGE_FEEDBACK = 3`. The `warning` advisory never blocks GREEN start. Verification mode (issue `005-001`) never exempts the executable suite.

## Scope Boundaries

### Hard Inclusions

- `_run_red_phase` never raises `PhaseFailedError` on test returncode 0.
- `_run_red_phase` builds a `RedHandoffAdvisory` and returns it in-memory to the caller.
- A passing RED test logs `RED_PASSED_WARNING` via the existing `log_event` facilities.
- A crash discards the advisory; a RED restart re-derives it (no persisted state).
- RED appends its `RED` transition row on every completed run.
- `_run_green_phase` requires `_run_test_cmd` returncode 0; non-zero routes to JUDGE via `session.train_feedback`.
- JUDGE retry stays bounded by `_MAX_JUDGE_FEEDBACK = 3`; no new retry algorithm or backoff.
- Tests in `tests/unit/test_micro/test_red.py` and `tests/unit/test_micro/test_green.py` mock `deviate.cli.micro._run_pytest`.

### Defensive Exclusions

- No new `TaskRecord.status` value; the advisory never becomes a status (PRD RESOLVED-Q-004).
- No persistent record of the advisory in `tasks.jsonl`, `.deviate/`, or any ledger (PRD RESOLVED-Q-001).
- No REFACTOR behavior change; the REFACTOR regression gate belongs to issue `005-004`.
- No change to `src/deviate/core/validation.py` or `src/deviate/core/tasks_ledger.py`; contract and traceability belong to issues `005-001` and `005-002`.
- No prompt template edits; alignment belongs to issue `005-005`.
- No change to `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, or `CHANGELOG.md`; spec alignment belongs to issue `005-005`.
- No standalone acceptance-runner module (PRD Option D, rejected).

## Upstream Requirement Tracing

- **FR-005-03**: Non-Blocking RED Checkpoint
- **FR-005-04**: Blocking GREEN Gate with JUDGE Routing
- **AC-005-03-01**: A RED run whose test suite passes completes the phase and emits a `warning` advisory; no `PhaseFailedError`; advisory reaches GREEN; test-infrastructure failure still surfaces as a phase error; no test file detected skips the checkpoint.
- **AC-005-03-02**: A RED run whose test suite fails completes with an `ok` advisory; RED transition row appended; GREEN starts.
- **AC-005-04-01**: GREEN with returncode 0 appends the GREEN transition; non-zero returncode routes to JUDGE via `train_feedback`; a `warning` RED advisory does not block GREEN start.

## User Stories Ledger

- **US-005-05** (parent FR-005-03): As a task runner, I complete the RED phase even when the test suite passes, so the loop records the checkpoint and proceeds with a warning advisory instead of aborting.
- **US-005-06** (parent FR-005-03): As an operator, I see a `RED_PASSED_WARNING` log event when a RED run passes, so I can audit the unexpected pass without a crash.
- **US-005-07** (parent FR-005-04): As a task runner, I block GREEN on a failing suite and route to JUDGE via `train_feedback`, so a broken implementation never records a GREEN pass.
- **US-005-08** (parent FR-005-04): As a task runner, I start GREEN normally after a `warning` RED advisory, so the advisory informs without gating.

## Acceptance Outline

- **AO-003** / `AC-005-03-01` / US-005-05, US-005-06: A RED run whose test suite returns 0 completes the phase, appends the `RED` transition, emits a `warning` advisory, and logs `RED_PASSED_WARNING`; no `PhaseFailedError` is raised; the advisory reaches the GREEN runner in-memory.
- **AO-003** / `AC-005-03-01` / US-005-05: A test-infrastructure failure (the test command itself errors) still raises a phase error; an absent test file skips the checkpoint with no advisory.
- **AO-003** / `AC-005-03-02` / US-005-05: A RED run whose test suite fails completes with an `ok` advisory, appends the `RED` transition, and hands control to GREEN.
- **AO-004** / `AC-005-04-01` / US-005-07, US-005-08: GREEN with test returncode 0 appends the `GREEN` transition and clears `session.train_feedback`; a non-zero returncode sets `session.train_feedback` and routes to JUDGE; JUDGE retries stay bounded by `_MAX_JUDGE_FEEDBACK = 3`; a `warning` advisory does not block GREEN start.

## Edge Cases and Boundaries

- RED test suite passes with an empty test selection: same warning path as any pass; the checkpoint never aborts.
- RED test command crashes (non-zero from infrastructure, not from tests): phase error surfaces; advisory discarded; restart re-derives.
- RED restart after a crash: `_phase_already_done` skips a completed RED run; a fresh advisory is built on the next run.
- GREEN failure with `train_feedback` already populated: the feedback is overwritten with the new rationale (existing behavior).
- JUDGE exhausts `_MAX_JUDGE_FEEDBACK = 3`: existing terminal routing applies; no new threshold introduced.
- GREEN pass after a `warning` advisory: transition appended; advisory does not influence the verdict.
- GREEN failure after an `ok` advisory: identical JUDGE routing; advisory severity never gates the suite.

## Performance Constraints

- Tests invoking CLI commands that reach `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture; the full suite stays under 30 seconds.
- CLI init stays at L_max ≤ 500ms; per-agent export ≤ 200ms.
- No persistent writes beyond the existing `RED`/`GREEN` transition rows in the append-only task ledger.
- No new external integration or database runtime.

## Multi-Tiered Verification Targets

- **Unit**: `tests/unit/test_micro/test_red.py` — advisory on pass (severity `warning`), advisory on fail (severity `ok`), no `PhaseFailedError` on pass, `RED_PASSED_WARNING` log, crash discards advisory, absent test file skips.
- **Unit**: `tests/unit/test_micro/test_green.py` — GREEN pass appends transition; GREEN failure routes to JUDGE with `train_feedback`; warning advisory does not block start; `_MAX_JUDGE_FEEDBACK` bound intact.
- **Integration**: `deviate micro run <task_id>` in a temporary worktree with a mocked test command; assert the RED and GREEN transition rows and the advisory handoff.

## Demonstration Path

```bash
# 1. Unit verification — RED checkpoint and GREEN gate behavior
#    (all CLI-reaching tests mock deviate.cli.micro._run_pytest)
uv run pytest tests/unit/test_micro/test_red.py tests/unit/test_micro/test_green.py -v

# 2. Integration: a RED run with a passing suite completes with a warning
#    (temporary worktree; task in PENDING; _run_pytest mocked to return
#     CompletedProcess(returncode=0, ...))
deviate micro run <task_id>
# expected: phase completes; no PhaseFailedError; ledger shows RED row;
#           log carries RED_PASSED_WARNING; advisory severity "warning"

# 3. Integration: GREEN failure routes to JUDGE via train_feedback
#    (_run_pytest mocked to return CompletedProcess(returncode=1, ...) on the
#     GREEN attempt)
deviate micro run <task_id>
# expected: GREEN transition absent; session.train_feedback populated;
#           JUDGE invoked; retries bounded by _MAX_JUDGE_FEEDBACK = 3

# 4. Ledger audit — RED row appended, no advisory record persisted
grep -c '"status":"RED"' specs/{NNN}-{slug}/tasks.jsonl
grep -c 'RedHandoffAdvisory' specs/{NNN}-{slug}/tasks.jsonl   # expected: 0

# 5. Regression: full check bundle stays green
mise run check
```
