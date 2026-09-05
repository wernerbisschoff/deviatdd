## Plan Summary
- **Issue**: ISS-ADH-041 — RED compile-error failures count as failing tests, TRAIN_EXHAUSTED fails clean
- **Implementation Strategy**: Add an explicit compile-error classifier to the RED gate in `src/deviate/cli/micro.py`, then make TRAIN_EXHAUSTED write a FAILED ledger row at the exhaustion site.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Compile-error RED output proceeds to GREEN**
- **Source Outline**: `AO-041-01`
- **Upstream Traceability**: `US-041-01`, `FR-ADHOC-041`, `AC-ADHOC-041-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: The RED gate sees a non-zero test result with compile-error markers and zero counted failures
- **When**: `_run_red_phase` classifies the result
- **Then**: The run commits a RED failing-test boundary and dispatches GREEN
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Genuine no-test output still routes to adjudication**
- **Source Outline**: `AO-041-01`
- **Upstream Traceability**: `US-041-01`, `FR-ADHOC-041`, `AC-ADHOC-041-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_is_no_tests_collected`
- **Given**: The test command exits 0, exits 5 with no-tests text, or exits 127 with no-command text
- **When**: `_run_red_phase` classifies the result
- **Then**: The run routes to `_adjudicate_red_no_failing_test` instead of GREEN
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Mixed compile-error and passing output counts as failing**
- **Source Outline**: `AO-041-01`
- **Upstream Traceability**: `US-041-01`, `FR-ADHOC-041`, `AC-ADHOC-041-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: The test output holds compile-error markers beside passing test results
- **When**: `_run_red_phase` classifies the result
- **Then**: The run commits a RED failing-test boundary and dispatches GREEN
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Exhaustion records a FAILED row and exits cleanly**
- **Source Outline**: `AO-041-02`
- **Upstream Traceability**: `US-041-02`, `FR-ADHOC-041`, `AC-ADHOC-041-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_raise_train_exhausted`
- **Given**: The session reaches 3 RED escalates
- **When**: The TRAIN budget exhausts
- **Then**: The ledger holds a FAILED task row with the TRAIN_EXHAUSTED reason and the run exits without an unhandled traceback
- **Verification Mode**: automated

**Scenario AC-PLAN-005: No-failing-test COMPLETE keeps evidence guardrails**
- **Source Outline**: `AO-041-02`
- **Upstream Traceability**: `US-041-02`, `FR-ADHOC-041`, `AC-ADHOC-041-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test`
- **Given**: JUDGE adjudicates a no-failing-test RED toward COMPLETE
- **When**: The forward route commits the COMPLETED row
- **Then**: The run rejects empty evidence quotes, docs-only diffs, and diffs without declared regression paths
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Owns the RED gate, the TRAIN budget, and the adjudication route
  - **Current State**: The gate checks returncode 0, exit 5, and exit 127 only; no compile-error pattern match exists; `_raise_train_exhausted` raises without a FAILED row
  - **Changes Required**: Add `_is_compile_error` output classifier; call it in `_run_red_phase` before adjudication; append a FAILED row at the exhaustion site
  - **Integration Surface**: `_run_test_cmd`, `_adjudicate_red_no_failing_test`, `_train_green_or_escalate`, `_execute_task_with_retry`, `append_task_transition`
- **tests/unit/test_micro/test_red_compile_error.py**: New regression tests for the classifier and the exhaustion path
  - **Current State**: File does not exist yet
  - **Changes Required**: Add cases for compile-error proceeds-to-GREEN, exit-0/5/127 adjudication, mixed output, and FAILED-row-on-exhaustion
  - **Integration Surface**: Mocks `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` fixtures

## Implementation Strategy
- **Phase 1**: RED compile-error classification — deliverable is failing-then-passing classifier tests plus the gate change
  - **Files**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_red_compile_error.py`
  - **Approach**: Add a language-agnostic `_is_compile_error` matcher over stdout plus stderr; check it in `_run_red_phase` so matches skip adjudication and commit RED
  - **Verification**: Run `mise run test -- tests/unit/test_micro/test_red_compile_error.py`
- **Phase 2**: TRAIN_EXHAUSTED clean failure — deliverable is a FAILED ledger row at exhaustion with no retry-loop rerun
  - **Files**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_red_compile_error.py`
  - **Approach**: Append the FAILED transition inside the exhaustion path; mark the error so `_execute_task_with_retry` does not rerun the task
  - **Verification**: Run the exhaustion test plus the full unit suite under 30s
- **Phase 3**: Evidence guardrail lock-in — deliverable is regression tests over the existing guards
  - **Files**: `tests/unit/test_micro/test_red_compile_error.py`
  - **Approach**: Keep current `_require_tdd_declared_regression_files` and `_require_tdd_completed_evidence` calls; add tests that pin empty-evidence and docs-only-diff rejection
  - **Verification**: Run the full unit suite plus `mise run check`

## Data Flow Analysis
- `_run_test_cmd` returns a `CompletedProcess` with returncode, stdout, and stderr. `_run_red_phase` feeds that result to the classifier chain: compile-error match, then exit-0/5/127 checks. A compile-error match flows to the RED commit and GREEN dispatch. Other no-failure results flow to JUDGE adjudication. On the third RED escalate, the TRAIN path appends a FAILED row to `tasks.jsonl` and raises a marked error that the outer retry loop honors without a rerun.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Classifier matches genuine pass output | High | Low | Anchor patterns to compile-error tokens plus non-zero exit; pin exit-0 behavior in tests |
| FAILED row duplicates the outer retry FAILED row | Medium | Medium | Mark the exhaustion error; skip the generic retry when the mark is present |
| ExUnit patterns drift from real mix output | Medium | Medium | Keep patterns output-based and broad; cover Python plus ExUnit samples in tests |

## Security Profile
Risk surfaces: file paths (test output paths in logs), subprocess (test command output parsing only, no new commands)
Negative tests: classifier rejects crafted output that mimics markers with exit 0; FAILED row write failure still surfaces a clear error
Constraints: No new dependencies; no change to GREEN or JUDGE verdict semantics; no change to 3-escalate budget caps

## Integration Points
- **`_run_test_cmd`**: Supplies the raw result; the classifier reads only, never alters commands
- **`_adjudicate_red_no_failing_test`**: Keeps ownership of genuine no-test output; the classifier runs before it
- **`_execute_task_with_retry`**: Honors the exhaustion mark and skips the blind whole-task retry
- **`tasks.jsonl`**: Receives the FAILED row via `append_task_transition` at exhaustion

## Constitutional Alignment
- **Architecture**: Micro-layer RED → GREEN → JUDGE → REFACTOR flow stays intact; the change only corrects RED classification and exhaustion accounting (constitution §1)
- **Testing**: pytest regression tests mock `_run_pytest` with `CompletedProcess` fixtures; full suite stays under 30s; `mise run check` gates merge (constitution §2, §3)
- **Git Isolation**: Work happens on `feat/adhoc/041-red-compile-error-no-failing-test`; commits land at phase boundaries (constitution §4)
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-003` encode `US-041-01`; `AC-PLAN-004` and `AC-PLAN-005` encode `US-041-02`; RED turns each automated scenario into a failing test
