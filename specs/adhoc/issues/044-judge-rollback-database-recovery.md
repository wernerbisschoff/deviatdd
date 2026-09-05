---
title: "JUDGE rollback restores the isolated database or stops with a recovery action"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-044
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/044-judge-rollback-database-recovery.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/state/config.py`, `tests/unit/test_micro/`

## The Problem Contract
JUDGE rollback resets Git state but leaves the isolated database stamped at a discarded migration revision. Later test commands fail with missing-revision errors. This issue adds database recovery to the rollback path or a specific stop error.

## Scope Boundaries
### Hard Inclusions
- Detect migration files in the reverted diff inside `_execute_rollback` and trigger database recovery before returning
- Add a `[rollback]` recovery hook in `.deviate/config.toml` (config loader in `src/deviate/state/config.py`) that runs on migration-bearing rollbacks
- Stop with a specific error naming the hook plus the manual recovery action when recovery is unavailable

### Defensive Exclusions
- No change to Git reset, tasks.md preservation (ISS-ADH-040), or stale-boundary recovery (ISS-ADH-042) semantics
- No change to JUDGE verdict routing or GREEN/RED attempt budgets
- No Alembic-specific code in the runner; detection stays at migration-path patterns plus a generic hook

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-044`
- **Acceptance Criteria Tokens**: `AC-ADHOC-044-01`, `AC-ADHOC-044-02`
- **Data Model Entities**: SessionState (red_commit_sha), RollbackSnapshot

## User Stories Ledger
- **US-044-01**: As a developer on a repo with database migrations, I want JUDGE rollback to restore the isolated database so later test commands keep working after a revert. *(Ref: FR-ADHOC-044)*
- **US-044-02**: As an operator without a configured recovery hook, I want a specific error with the required recovery action so I fix the database instead of debugging phantom revision errors. *(Ref: FR-ADHOC-044)*

## Acceptance Outline
- **AO-044-01** *(Ref: AC-ADHOC-044-01, US-044-01)*: Reverted diff with migration files recovers the database or stops specifically
  - **Happy Path**: Migration-bearing revert runs the configured recovery hook and later test commands succeed
  - **Error Category**: No hook configured stops with a specific error naming the hook plus the manual recovery action; the branch stays at the rolled-back boundary
  - **Boundary Category**: Hook failure stops with the hook output attached, never a silent pass
- **AO-044-02** *(Ref: AC-ADHOC-044-02, US-044-02)*: Reverts without migration files behave exactly as today
  - **Happy Path**: Non-migration revert runs no hook and returns the existing rollback trace
  - **Error Category**: Existing `ROLLBACK_*` refusals keep their current messages
  - **Boundary Category**: Empty migration set never triggers recovery on RED-only or docs-only slices

## Edge Cases and Boundaries
- Reverted diff touches `alembic/versions/*`, `migrations/*`, or `db/migrate/*` paths (pattern list lives in one constant)
- Recovery hook runs after `git reset --hard` plus `git clean`, before tasks.md restore and feedback commit
- Hook receives the boundary SHA and task id via environment; hook timeout fails the rollback loudly
- Remote source: gh issue 198 (JUDGE rollback leaves Alembic database at discarded revision), deviate 2.27.1, TSK-001-01

## Performance Constraints
- L_max: 200ms per added rollback-gate check excluding hook runtime
- Throughput: full test suite under 30s (mock `_run_pytest` subprocess and hook subprocess in new tests per AGENTS.md)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_rollback_database_recovery.py` — migration diff triggers hook; non-migration diff skips hook; missing hook raises the specific error without moving past the boundary; hook failure surfaces hook output
- **Integration Sandbox Targets**: Revert on a fixture repo with a fake migration file plus hook script completes and the hook observes the boundary SHA

## Demonstration Path
```bash
mise run test -- tests/unit/test_micro/test_rollback_database_recovery.py
```
