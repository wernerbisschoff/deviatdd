## Plan Summary
- **Issue**: ISS-ADH-052 — Clarify E2E task preconditions and RED verification responsibilities
- **Implementation Strategy**: Add a task-card `preconditions` hook that the verification path prepares before RED, emit a named missing-infrastructure signal carrying the setup command, and bound RED E2E verification for child-process tests.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Verification path prepares E2E preconditions before RED runs**
- **Source Outline**: `AO-052-01`
- **Upstream Traceability**: `US-052-01`, `FR-ADHOC-052`, `AC-ADHOC-052-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_verification_rungs`
- **Given**: An E2E task declares a setup command in its `preconditions` field
- **When**: The RED verification path runs for the task
- **Then**: The runner executes the setup command first and the RED test fails on its assertion
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Unprepared preconditions fail with explicit setup command**
- **Source Outline**: `AO-052-01`
- **Upstream Traceability**: `US-052-01`, `FR-ADHOC-052`, `AC-ADHOC-052-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_maybe_run_doctor`
- **Given**: An E2E task declares preconditions that the runner did not prepare
- **When**: The verification path executes without prepared preconditions
- **Then**: Verification fails and names the exact setup command to run
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Child-process E2E test follows bounded RED verification rule**
- **Source Outline**: `AO-052-01`
- **Upstream Traceability**: `US-052-01`, `FR-ADHOC-052`, `AC-ADHOC-052-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_test_cmd`
- **Given**: An E2E test starts a child API process
- **When**: RED verifies the failing test
- **Then**: RED runs only the bounded verification subset within the task card timeout and never the full E2E ladder
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Missing infrastructure emits named signal and RED keeps non-error status**
- **Source Outline**: `AO-052-02`
- **Upstream Traceability**: `US-052-02`, `FR-ADHOC-052`, `AC-ADHOC-052-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:EnvNotReadyError`
- **Given**: Required infrastructure is unavailable for a RED task
- **When**: RED detects the missing infrastructure
- **Then**: RED emits the named precondition signal with the required setup command and reports a non-error RED status
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Partial infrastructure resolves to exactly one RED outcome**
- **Source Outline**: `AO-052-02`
- **Upstream Traceability**: `US-052-02`, `FR-ADHOC-052`, `AC-ADHOC-052-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/red.md:unavailable services`
- **Given**: Infrastructure is partially available for a RED task
- **When**: RED evaluates the environment
- **Then**: RED produces exactly one outcome of RED proof or named signal, and the signal always names the setup command
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: owns the verification ladder and precondition hook
  - **Current State**: Ladder builds unit to e2e rungs with doctor preflight only; no per-task precondition declare or prepare step
  - **Changes Required**: Add `preconditions` resolution, prepare step before RED verification, named signal carrying setup command, bounded E2E rule for child-process tests
  - **Integration Surface**: `_resolve_verification_rungs`, `_maybe_run_doctor`, `_run_test_cmd`, `_execute_task_with_retry`, `EnvNotReadyError`
- **src/deviate/prompts/auto/red.md**: orders ERROR status for unavailable services
  - **Current State**: Missing services count as agent error with no named signal
  - **Changes Required**: Replace error rule with named precondition signal plus non-error RED status
  - **Integration Surface**: RED handover manifest status values consumed by `_execute_task_with_retry`
- **mise.toml**: defines setup and e2e tasks available as precondition commands
  - **Current State**: `setup`, `test-e2e`, `e2e` tasks exist with no precondition wiring
  - **Changes Required**: Document the setup command contract used by task-card preconditions
  - **Integration Surface**: `_mise_defined_tasks`, `_mise_allowlisted_tasks`

## Implementation Strategy
- **Phase 1**: Precondition declare and prepare in verification path — deliverable
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Resolve optional `preconditions` setup command from task card, run it before RED verification, fail with explicit setup command when preparation fails
  - **Verification**: Unit tests for resolution plus prepare step; E2E dry-run confirms setup command runs first
- **Phase 2**: Named signal with non-error RED status — deliverable
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/red.md`
  - **Approach**: Emit named precondition signal carrying setup command and probe detail, map it to non-error RED status instead of ERROR
  - **Verification**: Unit tests assert signal name plus setup command; prompt rule test asserts non-error status
- **Phase 3**: Bounded RED rule for child-process E2E tests — deliverable
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Detect child-process E2E verification and run only the bounded subset within the card timeout
  - **Verification**: Unit test asserts bounded command selection; E2E dry-run with absent preconditions confirms named signal

## Data Flow Analysis
- Task card supplies `verification` plus new `preconditions` setup command; the verification path resolves the setup command, runs preparation, then runs the bounded verification rungs; preparation failure or missing infrastructure produces the named signal with the setup command; RED writes the failing test and returns a non-error status tied to the signal.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Setup command runs untrusted strings | High | Low | Reuse `is_safe_test_command` plus mise allowlist gate before execution |
| Bounded rule skips real coverage | Medium | Medium | Bound only RED for child-process E2E; full ladder still runs after tasks complete |
| Signal rename breaks retry handling | Medium | Low | Keep `ENV_NOT_READY` as alias; add new named signal alongside it |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: poisoned preconditions string rejected by safe-command parser, malformed env file names the file plus parse failure, failing setup command carries exit output verbatim
Constraints: run only allowlisted mise tasks or safe commands as preconditions, no new dependencies, no secrets in signal output

## Integration Points
- **Task card `verification` plus `preconditions`**: RED reads both; preparation precedes verification rungs
- **`mise doctor` preflight**: remains the live-environment gate; precondition signal supplements it with the setup command
- **RED handover manifest**: carries named signal status readable by `_execute_task_with_retry`

## Constitutional Alignment
- **Architecture**: Implements Micro-layer RED verification boundary; no Macro or Meso layer skipped
- **Testing**: pytest unit suite for precondition check plus signal emission; E2E RED dry-run for missing preconditions; coverage stays above 80 percent
- **Git Isolation**: Work happens on the issue worktree branch; commits occur at phase boundaries only
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-003` encode `US-052-01` plus ATDD `AO-052-01`; `AC-PLAN-004` plus `AC-PLAN-005` encode `US-052-02` plus ATDD `AO-052-02`; RED turns each scenario into a failing test
