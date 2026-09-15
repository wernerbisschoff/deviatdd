---
title: "Make JUDGE evaluate current diff and stop contradiction loops"
labels: [feature, bug]
source_file: "specs/010-filed-github-issues/issues/002-judge-current-diff.md"
blocked_by: ["010-001"]
coordinates_with: []
issue_id: "010-002"
---

## System Topology Mapping
- Epic domain: JUDGE compliance
- Local file: `src/deviate`
- `src/deviate/core/agent.py`
- `src/deviate/cli`
- git diff evaluation path
- `tests/`

## The Problem Contract
JUDGE can reject retained behavior absent from the current GREEN diff.
JUDGE can oscillate between incompatible requirement interpretations.
JUDGE must evaluate current required behavior and stop repeated contradiction loops.

## Scope Boundaries
- Include current-contract and current-diff evaluation.
- Include preservation checks only when the active contract requires them.
- Include stable contradiction handling for repeated incompatible interpretations.
- Include pass, retry, and contradiction outcomes.
- Exclude task-state recovery and GREEN metadata cleanup.
- Exclude new persistence storage and external integrations.

## Upstream Requirement Tracing
| Requirement | Included | Excluded |
|---|---|---|
| FR-001-STATE | — | Owned by `010-001`. |
| FR-002-GREEN | — | Owned by `010-001`. |
| FR-003-CLEAN | — | Owned by `010-001`. |
| FR-004-JUDGE | Current contract and diff evaluation. | — |
| FR-005-CONTRADICTION | Stable contradiction result. | — |

## User Stories Ledger
- US-010-02: A JUDGE evaluator gives a current-diff verdict and stops contradictory retries.

## Acceptance Outline
- AO-004: JUDGE returns a verdict based on the active contract and current GREEN diff.
- AO-005: JUDGE returns a stable contradiction result after repeated incompatible interpretations.

## Multi-Tiered Verification Targets
- AO-004: JUDGE does not reject absent behavior unless the active contract requires preservation.
  **Verification Command**: `uv run pytest tests/ -q -k judge_current_diff`
- AO-005: Repeated incompatible interpretations stop the oscillating retry cycle.
  **Verification Command**: `uv run pytest tests/ -q -k judge_contradiction`

## Demonstration Path
```bash
uv run pytest tests/ -q -k 'judge_current_diff or judge_contradiction'
```
