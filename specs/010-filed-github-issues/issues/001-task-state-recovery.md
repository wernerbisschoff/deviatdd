---
title: "Stabilize task state recovery and GREEN post"
labels: [feature, bug]
source_file: "specs/010-filed-github-issues/issues/001-task-state-recovery.md"
blocked_by: []
coordinates_with: ["010-002"]
issue_id: "010-001"
---

## System Topology Mapping
- Epic domain: task-runner recovery
- Local file: `src/deviate`
- `src/deviate/cli`
- `src/deviate/core/agent.py`
- task ledger transition path
- `tests/`

## The Problem Contract
Repeated RED/PENDING transitions can cause GREEN to select stale state.
Successful GREEN post can retain rejection and retraining metadata.
The task runner must derive one current state and record a clean GREEN result.

## Scope Boundaries
- Include ordered canonical-state selection.
- Include task-and-phase transition deduplication.
- Include `RED → GREEN` eligibility.
- Include clearing stale GREEN rejection metadata.
- Exclude JUDGE contradiction interpretation.
- Exclude new persistence storage and metrics.

## Upstream Requirement Tracing
| Requirement | Included | Excluded |
|---|---|---|
| FR-001-STATE | Canonical task state before transitions. | — |
| FR-002-GREEN | GREEN accepts latest RED state. | — |
| FR-003-CLEAN | GREEN success clears stale metadata. | — |
| FR-004-JUDGE | — | Owned by `010-002`. |
| FR-005-CONTRADICTION | — | Owned by `010-002`. |

## User Stories Ledger
- US-010-01: A task runner recovers the latest RED state and records clean GREEN completion.

## Acceptance Outline
- AO-001: The runner derives one current task state from ordered ledger entries.
- AO-002: GREEN accepts a task whose latest state is RED after retry cycles.
- AO-003: Successful GREEN post contains no stale rejection or retraining markers.

## Multi-Tiered Verification Targets
- AO-001: The latest valid transition determines the effective task state.
  **Verification Command**: `uv run pytest tests/ -q -k canonical_task_state`
- AO-002: A non-RED latest state returns a stable GREEN phase error.
  **Verification Command**: `uv run pytest tests/ -q -k green_retry_recovery`
- AO-003: Successful GREEN post clears all stale rejection fields.
  **Verification Command**: `uv run pytest tests/ -q -k green_post_cleanup`

## Demonstration Path
```bash
uv run pytest tests/ -q -k 'canonical_task_state or green_retry_recovery or green_post_cleanup'
```
