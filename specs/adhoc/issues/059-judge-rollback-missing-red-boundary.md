---
title: "Preserve rollback evidence when the RED boundary is missing"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-059
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/059-judge-rollback-missing-red-boundary.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/state/ledger.py`, `.deviate/` recovery logs, `tests/unit/test_micro/`

## The Problem Contract
A JUDGE `revert_green` request fails when `session.red_commit_sha` is missing. The runner must preserve `head_sha` and `recovery_ref`, report a harness failure, and prevent unsafe rollback.

## Scope Boundaries
### Hard Inclusions
- Validate the RED rollback boundary before `revert_green`.
- Preserve and report available `head_sha` and `recovery_ref` evidence.
- Classify the failure as `DEVIATDD_BUG` and recommend `/deviate-green` after evidence preservation.

### Defensive Exclusions
- Do not fall back to `HEAD~1`.
- Do not silently retry or discard recovery evidence.
- Do not change unrelated JUDGE actions, retry budgets, or model routing.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-059`
- **Acceptance Criteria Tokens**: `AC-ADHOC-059-01`, `AC-ADHOC-059-02`
- **Data Model Entities**: `SessionState.red_commit_sha`, `TaskRecord.head_sha`, `TaskRecord.recovery_ref`, rollback failure details

## User Stories Ledger
- **US-059-01**: As a DeviaTDD operator, I want missing RED rollback metadata reported as a harness bug with recovery evidence so I can restore the task safely. *(Ref: FR-ADHOC-059)*

## Acceptance Outline
- **AO-059-01** *(Ref: AC-ADHOC-059-01, US-059-01)*: A missing `red_commit_sha` on `revert_green` returns a distinct harness failure with available recovery evidence.
  - **Happy Path**: The failure includes `head_sha` and `recovery_ref` when those values exist.
  - **Error Category**: The runner returns a distinct rollback-boundary harness error.
  - **Boundary Category**: Empty evidence fields remain explicit and do not trigger an inferred Git boundary.
- **AO-059-02** *(Ref: AC-ADHOC-059-02, US-059-01)*: The failure preserves a safe operator retry path.
  - **Happy Path**: The skill emits `DEVIATDD_BUG` and recommends `/deviate-green` after preserving evidence.
  - **Error Category**: The runner does not silently retry.
  - **Boundary Category**: The runner never uses `HEAD~1` as an implicit rollback boundary.

## Edge Cases and Boundaries
- `red_commit_sha` is empty while `head_sha` and `recovery_ref` are present.
- All rollback metadata is empty.
- A recovery reference exists but does not identify a valid RED commit.
- The task remains blocked until an operator restores a valid boundary.

## Performance Constraints
- L_max: 200 ms per agent export
- Throughput: One rollback failure report per JUDGE action

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_rollback_safety.py` — missing RED boundary preserves evidence and rejects implicit fallback.
- **Integration Sandbox Targets**: `tests/unit/test_micro/test_run.py` — `deviate micro run` surfaces `DEVIATDD_BUG` with recovery details.

## Demonstration Path
```bash
uv run pytest tests/unit/test_micro/test_rollback_safety.py tests/unit/test_micro/test_run.py -q -k "rollback or recovery or red_commit_sha"
```

## Source Anchors
- `src/deviate/cli/micro.py`: `ROLLBACK_BOUNDARY_MISSING: refusing to roll back without an explicit boundary SHA. Do not infer a boundary from SessionState.red_commit_sha or HEAD~1.`
- `src/deviate/state/ledger.py`: `head_sha: str | None = None` and `recovery_ref: str | None = None`.
- `specs/constitution.md`: `GREEN phase writes only to src/ and permitted implementation paths.`
