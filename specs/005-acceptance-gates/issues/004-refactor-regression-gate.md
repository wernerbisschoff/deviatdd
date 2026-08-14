---
title: "Blocking REFACTOR Regression Gate"
labels: [enhancement, vertical-slice, acceptance-gates, micro-layer]
source_file: "specs/005-acceptance-gates/issues/004-refactor-regression-gate.md"
blocked_by: ["005-003"]
coordinates_with: ["005-003"]
issue_id: 005-004
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/005-acceptance-gates/`
- **Local Issue File**: `specs/005-acceptance-gates/issues/004-refactor-regression-gate.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py:2448` — MODIFY: `_run_refactor_phase` inspects the `_run_test_cmd` returncode after the refactor agent run.
  - `src/deviate/cli/micro.py:2500` — MODIFY: the currently unchecked `_run_test_cmd(root)` call becomes a gate; a non-zero returncode raises `PhaseFailedError` and fails the task.
  - `src/deviate/cli/micro.py:2501` — REFERENCE: `_run_format_cmd(root)` runs only after the test gate passes.
  - `src/deviate/cli/micro.py:2505` — REFERENCE: on pass, `record.status = "COMPLETED"` and the `COMPLETED` transition row is appended (`_append_status_transition`, line 2427).
  - `src/deviate/cli/micro.py:2347` — REFERENCE: the `skip_refactor` path (phase = IDLE, mark COMPLETED) stays a separate decision; this gate applies only when REFACTOR actually runs.
  - `src/deviate/cli/micro.py:692` — REFERENCE: `_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "REFACTOR"}` unchanged.
  - `src/deviate/state/ledger.py:81-98` — REFERENCE: `TaskRecord` parse for the transition append; unchanged by this issue.
  - `tests/test_micro/test_refactor.py` — TARGET: extend with regression-gate behavior; mock `deviate.cli.micro._run_pytest`.
- **Upstream Evidence**:
  - `specs/005-acceptance-gates/prd.md:16` — Hard directive: `_run_refactor_phase` inspects `_run_test_cmd` returncode and raises `PhaseFailedError` on non-zero.
  - `specs/005-acceptance-gates/prd.md:151-162` — FR-005-05 acceptance outline: regression failure is terminal for the phase; zero proceeds to format, COMPLETED row, commit, session IDLE.
  - `specs/005-acceptance-gates/prd.md:195` — RESOLVED-Q-002: REFACTOR regression failure raises `PhaseFailedError`; no new retry threshold exists.
  - `specs/005-acceptance-gates/design.md` — REFERENCE: REFACTOR gate placement in the phase state machine.

## The Problem Contract

The REFACTOR phase polishes GREEN-verified code. Today the post-polish test run at `src/deviate/cli/micro.py:2500` is unchecked: its returncode is discarded, so a refactor that breaks tests can still record a pass. This issue makes the REFACTOR test run a blocking regression gate. A non-zero returncode raises `PhaseFailedError`; the task fails. A zero returncode proceeds to the format command, appends the `COMPLETED` transition, commits, and transitions the session to `IDLE`.

## Scope Boundaries

### Hard Inclusions

- `_run_refactor_phase` reads the `_run_test_cmd` returncode after the refactor agent run.
- A non-zero returncode raises `PhaseFailedError`; the phase fails.
- A zero returncode runs `_run_format_cmd`, appends the `COMPLETED` transition, commits, and transitions the session to `IDLE`.
- A `skip_refactor` decision bypasses the gate and keeps its existing completion path.
- Tests in `tests/test_micro/test_refactor.py` pin the pass and fail branches; CLI-reaching tests mock `deviate.cli.micro._run_pytest`.

### Defensive Exclusions

- No change to RED checkpoint behavior; that belongs to issue `005-003`.
- No change to GREEN failure routing; JUDGE `train_feedback` handling belongs to issue `005-003`.
- No new retry threshold, backoff, or checkpoint record (PRD RESOLVED-Q-002).
- No change to `src/deviate/core/validation.py` or `src/deviate/core/tasks_ledger.py`.
- No prompt template edits; alignment belongs to issue `005-005`.
- No change to `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, or `CHANGELOG.md`; spec alignment belongs to issue `005-005`.
- No new `TaskRecord.status` value; `FAILED` stays the terminal status for a phase failure.

## Upstream Requirement Tracing

- **FR-005-05**: Blocking REFACTOR Regression Gate
- **AC-005-05-01**: A refactor run that breaks a test raises `PhaseFailedError`; happy path appends the `COMPLETED` row; error category records the failure; boundary: unchanged passing tests pass the gate without side effects.

## User Stories Ledger

- **US-005-09** (parent FR-005-05): As a task runner, I fail the REFACTOR phase when the post-polish suite returns non-zero, so a regression never records a pass.
- **US-005-10** (parent FR-005-05): As a task runner, I complete the task when the post-polish suite passes, so the `COMPLETED` transition, commit, and `IDLE` transition follow the format run.

## Acceptance Outline

- **AO-005** / `AC-005-05-01` / US-005-09: A REFACTOR run whose post-polish test suite returns non-zero raises `PhaseFailedError`; the task records the failure; no `COMPLETED` row is appended.
- **AO-005** / `AC-005-05-01` / US-005-10: A REFACTOR run whose post-polish test suite returns zero runs the format command, appends the `COMPLETED` transition, commits, and transitions the session to `IDLE`.
- **AO-005** / `AC-005-05-01` / US-005-10: A REFACTOR run that changes no tests, with the suite passing, passes the gate with no side effects beyond the normal completion path.

## Edge Cases and Boundaries

- REFACTOR skipped (`skip_refactor`): the gate does not run; the existing completion path marks the task COMPLETED.
- REFACTOR already done (`_phase_already_done` on `COMPLETED`): the runner skips; no second gate run.
- Test command crashes (infrastructure error) after polish: non-zero returncode raises `PhaseFailedError`, same as a regression.
- Empty test selection at REFACTOR: a zero returncode from an empty run passes the gate; the suite content is not this issue's concern.
- Format command failure after a passing gate: existing error handling applies; the gate already passed.

## Performance Constraints

- Tests invoking CLI commands that reach `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture; the full suite stays under 30 seconds.
- CLI init stays at L_max ≤ 500ms; per-agent export ≤ 200ms.
- No persistent writes beyond the existing `COMPLETED`/`FAILED` transition rows in the append-only task ledger.
- No new external integration or database runtime.

## Multi-Tiered Verification Targets

- **Unit**: `tests/test_micro/test_refactor.py` — non-zero returncode raises `PhaseFailedError`; zero returncode appends `COMPLETED`; `skip_refactor` bypasses the gate; already-completed task skips.
- **Integration**: `deviate micro run <task_id>` in a temporary worktree with a mocked test command; assert the `COMPLETED` row on pass and the `FAILED` path on regression.

## Demonstration Path

```bash
# 1. Unit verification — REFACTOR regression gate behavior
#    (all CLI-reaching tests mock deviate.cli.micro._run_pytest)
uv run pytest tests/test_micro/test_refactor.py -v

# 2. Integration: regression fails the phase
#    (temporary worktree; task past GREEN/JUDGE; _run_pytest mocked to return
#     CompletedProcess(returncode=1, ...) on the REFACTOR attempt)
deviate micro run <task_id>
# expected: PhaseFailedError raised; task FAILED; no COMPLETED row appended

# 3. Integration: clean polish completes the task
#    (_run_pytest mocked to return CompletedProcess(returncode=0, ...))
deviate micro run <task_id>
# expected: format cmd runs; COMPLETED transition appended; commit lands;
#           session transitions to IDLE

# 4. Ledger audit — exactly one COMPLETED row on the pass path
grep -c '"status":"COMPLETED"' specs/{NNN}-{slug}/tasks.jsonl

# 5. Regression: full check bundle stays green
mise run check
```
