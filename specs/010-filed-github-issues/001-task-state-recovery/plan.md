## Plan Summary
- **Issue**: 010-001 — Stabilize task state recovery and GREEN post
- **Implementation Strategy**: Make task lookup derive one latest valid row per issue and task from ordered append-only entries. Keep GREEN guarded by that state, then clear all stale retry metadata after successful GREEN post.

## Acceptance Contract
**Scenario AC-PLAN-001: Derive the latest valid task state from ordered ledger entries**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-010-01`, `FR-001-STATE`, `AC-010-001-01`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_collect_latest_task_records`
- **Given**: A task ledger contains repeated RED, GREEN, and retry transitions for one issue and task
- **When**: The runner resolves the task state
- **Then**: The runner returns exactly the latest valid transition for that issue and task
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Accept GREEN only when the latest task state is RED**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-010-01`, `FR-002-GREEN`, `AC-010-001-02`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_green_post_kernel`
- **Given**: A task has completed one or more retry cycles and its latest state is RED
- **When**: The runner executes GREEN post
- **Then**: The runner appends one GREEN transition and returns `GREEN_POST_OK`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Reject GREEN when the latest task state is not RED**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-010-01`, `FR-002-GREEN`, `AC-010-001-02`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_green_post_kernel`
- **Given**: A task has a latest valid state other than RED
- **When**: The runner executes GREEN post
- **Then**: The runner returns a stable `GREEN_GUARD_REJECTED` error that names the current state
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Clear stale rejection and retraining metadata after GREEN success**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-010-01`, `FR-003-CLEAN`, `AC-010-001-03`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_green_post_kernel`
- **Given**: A successful GREEN post follows a rejected or retrained task attempt
- **When**: The runner records GREEN completion
- **Then**: The session clears `judge_rejected`, `pending_judge_action`, `train_feedback`, `failure_kind`, and matching pending judge feedback
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/state/ledger.py**: Keep append-only task transition deduplication keyed by the latest `(id, status)` state and expose ordered records for canonical resolution + evidence: `append_task_transition`, `_append_with_compound_key` + Integrates: `TaskRecord`, `src/deviate/cli/micro/surface.py`
- **src/deviate/cli/micro/surface.py**: Resolve one current task row per `(issue_id, id)`, enforce RED-to-GREEN eligibility, and clear stale GREEN retry metadata + evidence: `_collect_latest_task_records`, `_green_post_kernel` + Integrates: `SessionState`, `append_task_transition`
- **tests/unit/test_cli/test_micro.py**: Add regression coverage for canonical state selection, retry GREEN recovery, stable non-RED rejection, and GREEN metadata cleanup + evidence: `TestFindTaskRecord`, `_green_post_kernel` tests + Integrates: `src/deviate/cli/micro/surface.py`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A sibling issue shadows the active task row | High | Medium | Key canonical rows by both `issue_id` and task ID |
| A repeated transition hides a retry transition | High | Medium | Deduplicate only when the latest row has the same status |
| GREEN success leaves stale retry routing active | High | Medium | Clear every retry field after the matching GREEN post |
| A non-RED task bypasses the phase guard | High | Low | Validate the resolved latest status before appending GREEN |

## Security Profile
Risk surfaces: append-only ledger ordering, session retry flags, git phase commit
Negative tests: sibling issue rows stay isolated, non-RED GREEN post fails, stale retry fields clear
Constraints: preserve append-only writes, modify only application paths and tests, add no dependencies
## Constitutional Alignment
- **Constitution**: §1, §2, §3 — canonical append-only state, micro-layer scope, pytest regression coverage
