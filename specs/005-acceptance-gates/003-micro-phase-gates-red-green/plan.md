## Plan Summary
- **Issue**: 005-003 — Micro Phase Gates: Non-Blocking RED Checkpoint and Blocking GREEN Gate
- **Implementation Strategy**: Make `_run_red_phase` non-blocking with an in-memory `RedHandoffAdvisory`, and keep `_run_green_phase` as the blocking gate that routes failures to JUDGE via `train_feedback`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: RED run with passing suite completes with warning advisory**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-005-05`, `FR-005-03`, `AC-005-03-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: A task run where the RED agent returns a success manifest and the test command exits 0
- **When**: The runner executes the RED phase
- **Then**: The phase completes without `PhaseFailedError`, appends the `RED` transition, builds a `RedHandoffAdvisory` with `passes True` and `severity warning`, and hands it to GREEN in memory
- **Verification Mode**: automated

**Scenario AC-PLAN-002: RED pass logs RED_PASSED_WARNING observability event**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-005-06`, `FR-005-03`, `AC-005-03-01`
- **Current-Code Evidence**: `src/deviate/core/run_logger.py:log_event`
- **Given**: A RED run whose test suite returns 0
- **When**: The runner records the warning advisory
- **Then**: The runner logs `RED_PASSED_WARNING` through the existing `log_event` facility with the task id
- **Verification Mode**: automated

**Scenario AC-PLAN-003: RED infrastructure failure and absent test file keep current routing**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-005-05`, `FR-005-03`, `AC-005-03-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_test_cmd`
- **Given**: A RED run where the test command itself errors or no test file exists
- **When**: The runner evaluates the test result
- **Then**: An infrastructure error surfaces as a phase error with no advisory persisted, and an absent test file skips the checkpoint with no advisory
- **Verification Mode**: automated

**Scenario AC-PLAN-004: RED run with failing suite completes with ok advisory**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-005-05`, `FR-005-03`, `AC-005-03-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: A task run where the RED agent returns a success manifest and the test command exits non-zero from test failures
- **When**: The runner executes the RED phase
- **Then**: The phase completes, appends the `RED` transition, builds an advisory with `passes False` and `severity ok`, and hands control to GREEN
- **Verification Mode**: automated

**Scenario AC-PLAN-005: GREEN pass appends transition and clears feedback**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-005-07`, `FR-005-04`, `AC-005-04-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_green_phase`
- **Given**: A GREEN run whose test command returns 0
- **When**: The runner evaluates the GREEN test result
- **Then**: The runner appends the `GREEN` transition and clears `session.train_feedback`
- **Verification Mode**: automated

**Scenario AC-PLAN-006: GREEN failure routes to JUDGE bounded by retry limit**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-005-07`, `FR-005-04`, `AC-005-04-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_MAX_JUDGE_FEEDBACK`
- **Given**: A GREEN run whose test command returns non-zero
- **When**: The runner evaluates the GREEN test result
- **Then**: The runner sets `session.train_feedback` with the failure output, routes to JUDGE, and keeps JUDGE retries bounded by `_MAX_JUDGE_FEEDBACK = 3`
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Warning advisory does not block GREEN start**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-005-08`, `FR-005-04`, `AC-005-04-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_green_phase`
- **Given**: A GREEN run reached after a RED `warning` advisory
- **When**: The runner starts the GREEN phase
- **Then**: GREEN starts normally and the advisory severity never changes the suite verdict
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: role in this issue — hosts `_run_red_phase`, the new `RedHandoffAdvisory` model, and the GREEN gate
  - **Current State**: RED routes a passing suite to JUDGE adjudication via `_adjudicate_red_no_failing_test`; GREEN already sets `train_feedback` on test failure
  - **Changes Required**: RED stops raising on returncode 0, builds and returns the advisory, logs `RED_PASSED_WARNING`, appends the RED transition; GREEN keeps the returncode 0 requirement and JUDGE routing
  - **Integration Surface**: `_run_test_cmd`, `_run_pytest`, `append_task_transition`, `SessionState.train_feedback`, `_MAX_JUDGE_FEEDBACK`, `log_event`
- **src/deviate/core/run_logger.py**: role in this issue — observability sink for the warning event
  - **Current State**: `log_event` facility exists and RED already emits run events
  - **Changes Required**: No code change; RED calls it with `RED_PASSED_WARNING`
  - **Integration Surface**: `log_event(event, **kwargs)`
- **src/deviate/state/ledger.py**: role in this issue — transition persistence reference
  - **Current State**: `TaskRecord` with optional `acceptance_criteria` drives `model_validate`; `append_task_transition` appends rows
  - **Changes Required**: No code change; RED and GREEN append their transition rows through it
  - **Integration Surface**: `TaskRecord`, `append_task_transition`
- **tests/test_micro/test_red.py**: role in this issue — unit target for the RED checkpoint
  - **Current State**: Covers RED adjudication paths with mocked `_run_pytest`
  - **Changes Required**: Add advisory on pass (`warning`), advisory on fail (`ok`), no `PhaseFailedError` on pass, warning log, crash discards advisory, absent file skips
  - **Integration Surface**: `deviate.cli.micro._run_pytest` mock with `CompletedProcess` fixtures
- **tests/test_micro/test_green.py**: role in this issue — unit target for the GREEN gate
  - **Current State**: Covers GREEN phase behavior with mocked `_run_pytest`
  - **Changes Required**: Add pass appends transition, failure routes to JUDGE with `train_feedback`, warning advisory does not block, retry bound intact
  - **Integration Surface**: `deviate.cli.micro._run_pytest` mock with `CompletedProcess` fixtures

## Implementation Strategy
- **Phase 1**: Add transient `RedHandoffAdvisory` and make RED non-blocking
  - **Files**: `src/deviate/cli/micro.py`, `tests/test_micro/test_red.py`
  - **Approach**: Add the Pydantic model co-located with the phase runners, change `_run_red_phase` to return the advisory instead of raising or routing to JUDGE on returncode 0, log `RED_PASSED_WARNING`, append the RED transition on every completed run
  - **Verification**: Run `uv run pytest tests/test_micro/test_red.py -v` with mocked `_run_pytest`
- **Phase 2**: Confirm GREEN as the blocking gate with JUDGE routing
  - **Files**: `src/deviate/cli/micro.py`, `tests/test_micro/test_green.py`
  - **Approach**: Keep the returncode 0 requirement, keep `train_feedback` routing on failure, keep `_MAX_JUDGE_FEEDBACK = 3`, verify the warning advisory never gates GREEN start
  - **Verification**: Run `uv run pytest tests/test_micro/test_green.py -v` with mocked `_run_pytest`

## Data Flow Analysis
- RED agent manifest plus `_run_test_cmd` result enter `_run_red_phase`; the runner builds a `RedHandoffAdvisory` (`task_id`, `passes`, `severity`) in memory and returns it to the caller. The RED transition row goes to the append-only task ledger. The advisory never serializes to `tasks.jsonl` or `.deviate/`. GREEN consumes the test result: returncode 0 appends the GREEN transition and clears `session.train_feedback`; non-zero writes failure output into `session.train_feedback` and routes to JUDGE. A crash discards the advisory; a restart re-derives it.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Removing the JUDGE adjudication path breaks existing no-failing-test tests | High | Medium | Update `test_red.py` expectations in the same change and run the full micro suite |
| Advisory accidentally persisted to a ledger | Medium | Low | Keep the model out of `TaskRecord` and assert zero `RedHandoffAdvisory` rows in ledger audits |
| GREEN retry bound changes by accident | Medium | Low | Keep `_MAX_JUDGE_FEEDBACK = 3` untouched and add a bound assertion test |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: test command crash surfaces as phase error with no persisted advisory; ledger audit finds zero advisory records; GREEN failure never records a GREEN pass
Constraints: mock `deviate.cli.micro._run_pytest` in all CLI-reaching tests; no new dependencies; no persistent writes beyond RED and GREEN transition rows

## Integration Points
- **`_run_test_cmd` / `_run_pytest`**: RED and GREEN read returncode 0 as pass, pytest exit 5 as no-tests-collected, 127 as no-test-command; tests mock `_run_pytest` with `CompletedProcess` fixtures
- **Task ledger `append_task_transition`**: RED and GREEN append their transition rows; the advisory never becomes a status value
- **`SessionState.train_feedback`**: GREEN failure writes failure output here for JUDGE; GREEN pass clears it; RED pass never writes it

## Constitutional Alignment
- **Architecture**: Implements the Micro layer (RED, GREEN, JUDGE) of the three-layer architecture; RED encodes the issue user stories as tests and GREEN gates on them; no Product layer artifact added
- **Testing**: pytest unit targets in `tests/test_micro/test_red.py` and `tests/test_micro/test_green.py` with mocked `_run_pytest` keep the suite under 30s; coverage target stays at 80 percent or more
- **Git Isolation**: All work happens on the dedicated issue worktree branch; commits land at phase boundaries through the orchestrator
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-004` encode `US-005-05` and `US-005-06` (RED checkpoint plus warning log); `AC-PLAN-005` through `AC-PLAN-007` encode `US-005-07` and `US-005-08` (GREEN gate plus non-blocking advisory); RED turns those scenarios into failing-then-passing tests
