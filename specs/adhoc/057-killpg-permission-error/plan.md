## Plan Summary
- **Issue**: ISS-ADH-057 — Harden timeout cleanup against killpg PermissionError
- **Implementation Strategy**: Widen `_kill_process_group` to swallow `PermissionError` alongside `ProcessLookupError` so timeout escalation always returns 124.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Timeout escalation swallows EPERM and returns 124**
- **Source Outline**: `AO-057-01`
- **Upstream Traceability**: `US-057-01`, `FR-ADHOC-057`, `AC-ADHOC-057-01`
- **Current-Code Evidence**: `src/deviate/cli/_safe_commands.py:_kill_process_group`
- **Given**: Timeout fires and `os.killpg` raises `PermissionError` on SIGTERM and SIGKILL
- **When**: `run_safe_command` runs the timeout escalation path
- **Then**: Caller receives returncode 124 with partial output and no exception propagates
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Existing cleanup behavior stays unchanged**
- **Source Outline**: `AO-057-02`
- **Upstream Traceability**: `US-057-01`, `FR-ADHOC-057`, `AC-ADHOC-057-02`
- **Current-Code Evidence**: `src/deviate/cli/_safe_commands.py:_kill_process_group`
- **Given**: Cleanup faces ESRCH, invalid pids, or non-cleanup spawn failures
- **When**: `run_safe_command` executes the parse, spawn, and cleanup paths
- **Then**: ESRCH still swallows, invalid pids return early, and genuine spawn errors keep the 127 path
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/_safe_commands.py**: owns `_kill_process_group` and the timeout escalation branch
  - **Current State**: `_kill_process_group` swallows only `ProcessLookupError`; `PermissionError` propagates and crashes timed-out runs
  - **Changes Required**: catch `PermissionError` alongside `ProcessLookupError` in `_kill_process_group`; confirm timeout-branch SIGTERM/SIGKILL calls route through it
  - **Integration Surface**: `run_safe_command` timeout branch, `os.killpg`, `signal.SIGTERM`/`SIGKILL`
- **tests/unit/test_cli/test_timeout_safe_command.py**: holds timeout-path regression tests
  - **Current State**: covers ESRCH swallow but has no EPERM case
  - **Changes Required**: add EPERM-path unit tests for wrapper and timeout escalation
  - **Integration Surface**: `_FakePopenInstance` harness, `run_safe_command`, `TEST_TIMEOUT_EXIT_CODE`

## Implementation Strategy
- **Phase 1**: Widen cleanup guard and add EPERM coverage — deliverable
  - **Files**: `src/deviate/cli/_safe_commands.py`, `tests/unit/test_cli/test_timeout_safe_command.py`
  - **Approach**: Add `PermissionError` to the except clause in `_kill_process_group`; add unit tests for EPERM on SIGTERM, EPERM on SIGKILL, and 124 result preservation
  - **Verification**: Run `uv run pytest tests/unit/test_cli/test_timeout_safe_command.py -v`

## Data Flow Analysis
- `run_safe_command` launches the child with `start_new_session=True`, waits via `communicate(timeout=...)`, and on `TimeoutExpired` captures partial output, calls `_kill_process_group` with SIGTERM, sleeps the grace period, calls `_kill_process_group` with SIGKILL, drains remaining output, reaps the child, and returns a `CompletedProcess` with returncode 124 plus partial output. The fix changes only the guard inside `_kill_process_group`: EPERM becomes a terminal end-state like ESRCH.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Swallowing a real authorization failure hides a bug | Low | Low | EPERM only occurs during best-effort cleanup; the 124 result still reports the timeout |
| Over-broad except clause catches unrelated errors | Medium | Low | Catch exactly `PermissionError` next to `ProcessLookupError`, no bare `OSError` widening |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: untrusted command strings still reject with 127, path-qualified executables still reject
Constraints: no new dependencies, no shell execution, no change to the allowlist

## Integration Points
- **`run_safe_command` timeout branch**: calls `_kill_process_group` twice; contract is return 124 with partial output
- **`os.killpg` wrapper**: contract is swallow ESRCH and EPERM, return early on invalid pids

## Constitutional Alignment
- §1 Micro-Layer Scope: GREEN writes only to `src/` and permitted test paths
- §3 Testing Protocols: pytest regression gate with >= 80% coverage target
- §5 Definition of Done: tests pass, lint passes, JUDGE validates scope
