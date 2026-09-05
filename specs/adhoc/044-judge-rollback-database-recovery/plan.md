## Plan Summary
- **Issue**: ISS-ADH-044 — JUDGE rollback restores the isolated database or stops with a recovery action
- **Implementation Strategy**: Detect migration paths in the reverted diff inside `_execute_rollback`, then run a `[rollback]` hook from config or stop with a named error.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Migration-bearing revert runs the recovery hook**
- **Source Outline**: `AO-044-01`
- **Upstream Traceability**: `US-044-01`, `FR-ADHOC-044`, `AC-ADHOC-044-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A JUDGE rollback reverts commits that touch a migration path
- **When**: `_execute_rollback` completes the git reset and clean
- **Then**: The configured recovery hook runs and later test commands succeed
- **Verification Mode**: automated
**Scenario AC-PLAN-002: Missing hook stops with a named recovery error**
- **Source Outline**: `AO-044-01`
- **Upstream Traceability**: `US-044-02`, `FR-ADHOC-044`, `AC-ADHOC-044-01`
- **Current-Code Evidence**: `src/deviate/state/config.py:_load_deviate_config_toml`
- **Given**: A migration-bearing revert occurs with no recovery hook configured
- **When**: `_execute_rollback` detects migration files in the reverted diff
- **Then**: Rollback stops with an error naming the hook plus the manual recovery action at the rolled-back boundary
- **Verification Mode**: automated
**Scenario AC-PLAN-003: Hook failure stops with hook output attached**
- **Source Outline**: `AO-044-01`
- **Upstream Traceability**: `US-044-01`, `FR-ADHOC-044`, `AC-ADHOC-044-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A migration-bearing revert runs a configured recovery hook
- **When**: The hook exits non-zero or exceeds its timeout
- **Then**: Rollback raises with the hook output attached and never reports a silent pass
- **Verification Mode**: automated
**Scenario AC-PLAN-004: Non-migration revert skips recovery**
- **Source Outline**: `AO-044-02`
- **Upstream Traceability**: `US-044-01`, `FR-ADHOC-044`, `AC-ADHOC-044-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A rollback reverts commits with no migration-path files
- **When**: `_execute_rollback` completes the git reset and clean
- **Then**: No hook runs and the existing rollback trace returns unchanged
- **Verification Mode**: automated
**Scenario AC-PLAN-005: Existing rollback refusals keep their messages**
- **Source Outline**: `AO-044-02`
- **Upstream Traceability**: `US-044-02`, `FR-ADHOC-044`, `AC-ADHOC-044-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A rollback request with a missing or stale boundary SHA
- **When**: `_execute_rollback` validates the boundary
- **Then**: The current `ROLLBACK_*` refusal message returns unchanged
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: owns the rollback path where database recovery lands
  - **Current State**: `_execute_rollback` resets git, cleans, restores tasks.md, returns trace
  - **Changes Required**: Add migration-path constant, diff detection, hook invocation after clean before tasks.md restore
  - **Integration Surface**: `_RollbackTrace`, `_preserve_agent_work`, JUDGE callers, `PhaseFailedError`
- **src/deviate/state/config.py**: owns config loading for the recovery hook
  - **Current State**: Loads `[models]`, `[agent]`, timeout keys via `_load_deviate_config_toml`
  - **Changes Required**: Add `[rollback]` hook resolver returning command plus timeout
  - **Integration Surface**: `DeviateConfig`, `resolve_model_for_phase`, `.deviate/config.toml`
- **tests/unit/test_micro/test_rollback_database_recovery.py**: new unit sandbox for this issue
  - **Current State**: File does not exist yet
  - **Changes Required**: Add tests for hook trigger, skip, missing-hook error, hook failure output
  - **Integration Surface**: `_execute_rollback`, mocked hook subprocess, mocked `_run_pytest`

## Implementation Strategy
- **Phase 1**: Migration detection plus hook plumbing — deliverable is working recovery
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/state/config.py`
  - **Approach**: Add one migration-path constant, compute reverted diff via git, resolve hook from config, run hook with boundary SHA plus task id in environment and a timeout
  - **Verification**: New unit tests pass, existing rollback tests pass
- **Phase 2**: Error paths — deliverable is loud failure semantics
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Raise specific missing-hook error and hook-failure error with output attached before tasks.md restore
  - **Verification**: Negative unit tests assert error text and branch position

## Data Flow Analysis
- `_execute_rollback` receives boundary SHA, task id, attempt; it snapshots agent work, resets git, cleans untracked files, then computes the reverted file list from the pre-reset HEAD versus boundary; when a path matches the migration constant, it loads the `[rollback]` hook from config and runs it with boundary SHA plus task id in the environment; hook success continues to tasks.md restore and trace return, hook absence or failure raises before restore; non-migration sets skip the hook entirely.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hook runs too long and blocks JUDGE | Medium | Medium | Enforce a hook timeout and fail loudly on expiry |
| Pattern list misses a migration layout | Medium | Low | Keep patterns in one constant and cover all three listed prefixes with tests |
| Behavior change leaks into non-migration rollbacks | High | Low | Gate hook strictly on non-empty migration set; add skip-path regression test |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: Hook command injection via config value fails safely; missing hook never silently passes; hook timeout fails loudly with output attached
Constraints: Run hook via argument list without shell; pass boundary SHA plus task id via environment only; no Alembic-specific code in the runner; no new dependencies

## Integration Points
- **`.deviate/config.toml [rollback]`**: supplies the recovery hook command plus timeout; `_execute_rollback` reads it on migration-bearing rollbacks
- **`git reverted diff`**: supplies the file list that triggers recovery; detection runs after reset using pre-reset HEAD versus boundary SHA

## Constitutional Alignment
- **Architecture**: Fits the Micro layer; JUDGE rollback gains database recovery while Git reset, tasks.md preservation, and stale-boundary semantics stay unchanged
- **Testing**: pytest unit tests in `tests/unit/test_micro/test_rollback_database_recovery.py` with mocked subprocesses keep the suite under 30s; coverage target stays at or above 80 percent
- **Git Isolation**: All work stays on the dedicated issue branch; rollback commits follow existing phase-boundary conventions
- **User Scenarios**: `AC-PLAN-001` plus `AC-PLAN-003` encode `US-044-01`; `AC-PLAN-002` plus `AC-PLAN-005` encode `US-044-02`; RED turns each automated scenario into a failing test
