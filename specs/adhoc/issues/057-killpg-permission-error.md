---
title: "Harden timeout cleanup against killpg PermissionError"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-057
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/057-killpg-permission-error.md`
- **Primary Architectural Workstation**: `src/deviate/cli/_safe_commands.py`, `tests/unit/test_cli/test_timeout_safe_command.py`

## The Problem Contract
Timed-out `deviate micro run` invocations crash with an uncaught `PermissionError` when `os.killpg` cannot signal the child process group. This issue makes cleanup treat EPERM as a terminal end-state so the runner returns exit code 124.

## Scope Boundaries
### Hard Inclusions
- Widen `_kill_process_group` in `src/deviate/cli/_safe_commands.py` to swallow `PermissionError` alongside `ProcessLookupError`
- Guard the unguarded timeout-branch SIGTERM/SIGKILL escalation calls at the same module
- Add unit coverage for the EPERM path in `tests/unit/test_cli/test_timeout_safe_command.py`

### Defensive Exclusions
- No diagnosis of the underlying integration timeout cause
- No change to test selection, reporting, or ledger behavior
- No new dependency, persistence, config key, or external integration

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-057`
- **Acceptance Criteria Tokens**: `AC-ADHOC-057-01`, `AC-ADHOC-057-02`
- **Data Model Entities**: CompletedProcess timeout result (returncode 124 plus partial output)

## User Stories Ledger
- **US-057-01**: As a CLI operator, I want timed-out runs to return exit code 124 even when the process group cannot be signaled so that the runner reports a timeout instead of crashing. *(Ref: FR-ADHOC-057)*

## Acceptance Outline
- **AO-057-01** *(Ref: AC-ADHOC-057-01, US-057-01)*: EPERM during timeout escalation yields a timeout result
  - **Happy Path**: `os.killpg` raises `PermissionError`, cleanup completes, caller receives returncode 124 with partial output
  - **Error Category**: Genuine spawn or wait failures outside cleanup keep the current error path
  - **Boundary Category**: EPERM on SIGTERM and EPERM on SIGKILL both resolve without raising
- **AO-057-02** *(Ref: AC-ADHOC-057-02, US-057-01)*: Existing cleanup behavior stays unchanged
  - **Happy Path**: ESRCH still swallows, invalid pids (None, 0, negative) still return early
  - **Error Category**: Non-cleanup errors propagate as before
  - **Boundary Category**: Sibling OSError branch keeps its current guard semantics

## Edge Cases and Boundaries
- Recycled process-group id owned by another user raises EPERM on signal
- Group already exited raises ESRCH and must keep swallowing
- `pid` of None, 0, or negative must return early without signaling the orchestrator group

## Performance Constraints
- L_max: 500ms for unit sandbox run of the timeout cleanup tests
- Throughput: single cleanup sequence per timeout (SIGTERM, grace sleep, SIGKILL)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_cli/test_timeout_safe_command.py` — EPERM swallowed by wrapper, timeout escalation with EPERM killpg returns 124, ESRCH coverage unchanged
- **Integration Sandbox Targets**: `mise unit` timeout-cleanup tests, `mise integration` smoke of a timed-out safe command

## Demonstration Path
```bash
uv run pytest tests/unit/test_cli/test_timeout_safe_command.py -v
```
