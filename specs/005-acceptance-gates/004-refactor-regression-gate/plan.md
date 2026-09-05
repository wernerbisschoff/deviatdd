## Plan Summary
- **Issue**: 005-004 — Blocking REFACTOR Regression Gate
- **Implementation Strategy**: Inspect the `_run_test_cmd` returncode inside `_run_refactor_phase`; raise `PhaseFailedError` on non-zero, else run format, append `COMPLETED`, commit, and transition to `IDLE`.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Refactor regression raises PhaseFailedError**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-005-09`, `FR-005-05`, `AC-005-05-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_refactor_phase`
- **Given**: A task past GREEN/JUDGE runs REFACTOR with the post-polish suite returning non-zero
- **When**: `_run_refactor_phase` inspects the `_run_test_cmd` returncode
- **Then**: The phase raises `PhaseFailedError`, records FAILED, and appends no `COMPLETED` row
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Clean polish completes the task**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-005-10`, `FR-005-05`, `AC-005-05-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_refactor_phase`
- **Given**: A REFACTOR run finishes with the post-polish suite returning zero
- **When**: The gate checks the `_run_test_cmd` returncode
- **Then**: The runner executes `_run_format_cmd`, appends the `COMPLETED` transition, commits, and transitions the session to `IDLE`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Unchanged passing tests pass the gate**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-005-10`, `FR-005-05`, `AC-005-05-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_test_cmd`
- **Given**: A REFACTOR run changes no tests and the suite returns zero
- **When**: The regression gate evaluates the result
- **Then**: The gate passes with only the normal completion path and no extra side effects
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Skipped refactor bypasses the gate**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-005-10`, `FR-005-05`, `AC-005-05-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_phase_already_done`
- **Given**: A task carries a `skip_refactor` decision or an existing `COMPLETED` row
- **When**: The runner reaches the REFACTOR step
- **Then**: The gate does not run and the existing completion or skip path marks the task COMPLETED
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: role in this issue — inspect `_run_test_cmd` returncode in `_run_refactor_phase` and raise `PhaseFailedError` on non-zero
  - **Current State**: `_run_refactor_phase` calls `_run_test_cmd(root, task)` and discards the result, then unconditionally runs `_run_format_cmd`
  - **Changes Required**: Bind the test result, check `returncode != 0`, raise `PhaseFailedError` with task id and output tail; keep format, `COMPLETED` append, commit, and `IDLE` transition on the zero path only
  - **Integration Surface**: `_run_test_cmd`, `_run_format_cmd`, `_append_status_transition`, `_commit_phase`, `_phase_already_done`, `SessionState`
- **tests/unit/test_micro/test_refactor.py**: role in this issue — pin pass and fail branches of the gate
  - **Current State**: Covers refactor pre/post contracts and rollback; no returncode gate assertions
  - **Changes Required**: Add tests for non-zero raising `PhaseFailedError` with no `COMPLETED` row, zero appending `COMPLETED`, `skip_refactor` bypass, and already-completed skip; mock `deviate.cli.micro._run_pytest`
  - **Integration Surface**: `deviate.cli.micro._run_refactor_phase`, `deviate.cli.micro._run_pytest`

## Implementation Strategy
- **Phase 1**: Make the REFACTOR test run a blocking gate — deliverable
  - **Files**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_refactor.py`
  - **Approach**: Capture `_run_test_cmd` return value in `_run_refactor_phase`; on non-zero raise `PhaseFailedError` before format or ledger writes; on zero keep the existing format, `COMPLETED` append, commit, and `IDLE` sequence unchanged
  - **Verification**: Run `uv run pytest tests/unit/test_micro/test_refactor.py -v` with `_run_pytest` mocked; confirm `mise run check` stays green

## Data Flow Analysis
- Input: REFACTOR agent manifest plus post-polish suite result from `_run_test_cmd`. Transform: returncode check branches to failure (`PhaseFailedError`, FAILED record) or success (format run, `COMPLETED` row, commit, session `IDLE`). Output: terminal ledger row and clean worktree. Storage: append-only `tasks.jsonl` transition rows only.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gate masks agent failure diagnostics | Medium | Low | Include test output tail in the `PhaseFailedError` message |
| Format failure after passing gate confuses the outcome | Low | Low | Keep existing error handling; gate already passed before format runs |
| Empty test selection passes vacuously | Low | Medium | Accept per scope; suite content is not this issue's concern |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: test-command crash (non-zero) raises `PhaseFailedError`; no `COMPLETED` row appears on the fail path; format runs only after a zero returncode
Constraints: no new dependencies; no prompt template edits; no changes outside `src/deviate/cli/micro.py` plus the target test file

## Integration Points
- **`_run_test_cmd`**: supplies the `CompletedProcess` whose returncode the gate inspects
- **`_run_format_cmd`**: runs only after a zero returncode on the REFACTOR path
- **Task ledger append**: `COMPLETED` row appended on pass; FAILED path on regression with no `COMPLETED` row

## Constitutional Alignment
- **Architecture**: Implements the Micro REFACTOR regression gate in the three-layer model; constitution §1 session continuity and append-only ledger rules hold
- **Testing**: pytest pins both gate branches per constitution §3; CLI-reaching tests mock `deviate.cli.micro._run_pytest` to keep the suite under 30s; coverage target stays >= 80%
- **Git Isolation**: Work happens on the dedicated issue branch; commits land only at the existing phase boundary
- **User Scenarios**: `AC-PLAN-001` encodes `US-005-09` (fail on regression); `AC-PLAN-002` through `AC-PLAN-004` encode `US-005-10` (complete on clean polish); RED turns those scenarios into failing tests
