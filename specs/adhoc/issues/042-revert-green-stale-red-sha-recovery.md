---
title: "revert_green recovers from a stale RED boundary instead of raising ROLLBACK_STALE_RED_SHA"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-042
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/042-revert-green-stale-red-sha-recovery.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/`

## The Problem Contract
Remote gh issue 207 reports a repeated GREEN/JUDGE train that ends in `ROLLBACK_STALE_RED_SHA` after 6 judge reroutes. The stored `red_commit_sha` no longer sits on the branch, and `_require_revert_green_boundary` refuses to reset. This issue makes that path recover instead of stop.

## Scope Boundaries
### Hard Inclusions
- Resolve a stale stored RED SHA on `revert_green` to a safe on-branch boundary (rewritten RED by subject, current-train pre-GREEN, or tasks.md-safe fallback) and continue the task
- Log the remap (`RED_SHA_REWRITTEN` or equivalent) so triage keeps the old and new SHA
- Keep the tasks.md preservation guarantee from ISS-ADH-040 on the recovery path

### Defensive Exclusions
- No change to `revert_red` boundary resolution or its already-reverted no-op
- No change to JUDGE verdict semantics or the GREEN/RED attempt budgets
- No silent reset to an unrelated commit; refusal with a plain error stays when no safe boundary exists

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-042`
- **Acceptance Criteria Tokens**: `AC-ADHOC-042-01`, `AC-ADHOC-042-02`
- **Data Model Entities**: SessionState (red_commit_sha), TaskRecord (GREEN/JUDGE transitions)

## User Stories Ledger
- **US-042-01**: As an operator retrying a task after repeated JUDGE reroutes, I want revert_green to survive a moved RED boundary so the task keeps training instead of dying with ROLLBACK_STALE_RED_SHA. *(Ref: FR-ADHOC-042)*

## Acceptance Outline
- **AO-042-01** *(Ref: AC-ADHOC-042-01, US-042-01)*: Stale stored RED SHA recovers and the task continues
  - **Happy Path**: Stored RED SHA off-branch with a rewritten RED on the train remaps and resets GREEN work only
  - **Error Category**: Stored RED SHA with no on-branch match and no safe fallback refuses with a plain error and leaves the branch unchanged
  - **Boundary Category**: Stored RED SHA still an ancestor of HEAD keeps current behavior exactly
- **AO-042-02** *(Ref: AC-ADHOC-042-02, US-042-02)*: Recovery never loses task state
  - **Happy Path**: `tasks.md` at its latest committed state stays on the branch after recovery plus feedback commit
  - **Error Category**: Unresolvable boundary raises no traceback past the cycle; the task records the failure
  - **Boundary Category**: Six-reroute train from gh issue 207 completes rollback instead of stopping

## Edge Cases and Boundaries
- Stored SHA dangling after `reset --hard` with a same-subject RED on the train remaps by subject
- Stored SHA whose parent still sits on HEAD (discarded RED beside a feedback commit) resolves without reset past tasks.md
- Empty `red_commit_sha` keeps the `ROLLBACK_BOUNDARY_MISSING` refusal
- Remote source: gh issue 207 (`revert_green fails with ROLLBACK_STALE_RED_SHA after repeated judge reroutes`), deviate 2.27.3, TSK-002-01

## Performance Constraints
- L_max: 200ms per added classification check inside the rollback gate
- Throughput: full test suite under 30s (mock `_run_pytest` subprocess in new tests per AGENTS.md)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_revert_green_stale_sha.py` — stale SHA with rewritten RED remaps and resets; unresolvable SHA refuses without moving HEAD; current SHA keeps exact behavior; tasks.md survives recovery
- **Integration Sandbox Targets**: GREEN/JUDGE train with a rebased RED boundary completes revert_green on a fixture repo

## Demonstration Path
```bash
mise run test -- tests/unit/test_micro/test_revert_green_stale_sha.py
```
