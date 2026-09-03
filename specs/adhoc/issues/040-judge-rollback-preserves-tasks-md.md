---
title: "JUDGE rollback must never remove tasks.md from the feature branch"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-040
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/040-judge-rollback-preserves-tasks-md.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py` (`_execute_rollback`, `_planned_revert_anchor`, `_resolve_revert_red_boundary`, rollback boundary resolution)

## The Problem Contract
A Micro JUDGE rollback reset the feature branch to a baseline that predates the Tasks commit. The feedback commit then parented onto that truncated tree, so `tasks.md` vanished from the branch while task work remained. Rollback must preserve the latest committed `tasks.md`.

## Scope Boundaries
### Hard Inclusions
- Resolve the JUDGE rollback boundary at or after the commit that created `tasks.md` on the active branch
- Refuse rollback with a plain error and leave the branch unchanged when no safe boundary resolves
- Keep per-attempt recovery refs and rollback snapshots working as before

### Defensive Exclusions
- No change to RED, GREEN, or REFACTOR phase behavior
- No change to Gate 3 audit or the squash-merge flow
- No new ledger event types; reuse existing rollback snapshot records

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-040`
- **Acceptance Criteria Tokens**: `AC-ADHOC-040-01`, `AC-ADHOC-040-02`
- **Data Model Entities**: RollbackSnapshot
- **Remote Source**: `https://github.com/wernerbisschoff/deviatdd/issues/201` (gh issue 201, repo `wallet-service`, version 2.27.1, task `TSK-001-01`, issue `001-001`)

## User Stories Ledger
- **US-040-01**: As an operator retrying a task after JUDGE feedback, I want `tasks.md` intact on the branch so the human-authored task queue is never lost. *(Ref: FR-ADHOC-040)*

## Acceptance Outline
- **AO-040-01** *(Ref: AC-ADHOC-040-01, US-040-01)*: Rollback keeps `tasks.md` on the active branch
  - **Happy Path**: After rollback plus feedback commit, `git ls-tree -r HEAD --name-only` still lists `tasks.md`
  - **Error Category**: GREEN work resets to the RED boundary; `tasks.md` stays at its latest committed state
  - **Boundary Category**: `meso run` after rollback sees the existing Tasks and does not regenerate them
- **AO-040-02** *(Ref: AC-ADHOC-040-02, US-040-01)*: Unsafe rollback refuses cleanly
  - **Happy Path**: Boundary predating `tasks.md` raises a plain error before any reset runs
  - **Error Category**: Branch, index, and untracked files stay unchanged on refusal
  - **Boundary Category**: Recovery refs from prior attempts stay reachable

## Edge Cases and Boundaries
- `tasks.md` uncommitted or absent from the branch: rollback follows the existing boundary path unchanged
- Amended or rebased history where the boundary is not an ancestor: existing `ROLLBACK_STALE_BOUNDARY` refusal stays
- Multiple rollbacks in one JUDGE call keep distinct per-attempt recovery refs

## Performance Constraints
- L_max: 5000ms rollback overhead beyond the git commands themselves
- Throughput: single rollback evaluation per JUDGE verdict, no retry loop

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/` rollback boundary tests (new cases: boundary predating `tasks.md` refused; `tasks.md` present after rollback)
- **Integration Sandbox Targets**: `deviate micro run` on a fixture repo with committed `tasks.md` plus JUDGE revert verdict; `git ls-tree HEAD` lists `tasks.md` after the run

## Demonstration Path
```bash
mise run check
```
