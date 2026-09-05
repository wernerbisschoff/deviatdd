---
title: "RED fails fast on split unit-plus-integration test contracts"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-043
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/043-red-split-test-contract-fails-fast.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/red.md`

## The Problem Contract
A task whose contract declares both unit and integration test targets loops through doomed RED retries on one layer. JUDGE rejects the absent layer each time. The run ends at TRAIN_EXHAUSTED with no useful work.

## Scope Boundaries
### Hard Inclusions
- Detect a multi-layer test contract at RED pre from the task row plus task card (`test_strategy`, test file paths, test commands spanning two or more of unit, integration, e2e)
- Stop RED pre with a specific split-task error that names the detected layers and the required planner action (split into one task per layer)
- Keep single-layer tasks on the current path with zero behavior change

### Defensive Exclusions
- No automatic task splitting or ledger rewrite; the planner performs the split
- No change to the RED layer-lock rule in `src/deviate/prompts/auto/red.md` (one layer per RED stays)
- No change to JUDGE compliance checks or GREEN behavior
- No consumer-repo, wallet-service, or Alembic-specific logic

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-043`
- **Acceptance Criteria Tokens**: `AC-ADHOC-043-01`, `AC-ADHOC-043-02`
- **Data Model Entities**: TaskRecord (`test_strategy`), task card Test Strategy line

## User Stories Ledger
- **US-043-01**: As a developer with a split unit plus integration task, I want RED to refuse the mixed contract at once so I split the task instead of watching three doomed RED retries. *(Ref: FR-ADHOC-043)*
- **US-043-02**: As an operator, I want the split-task error to name the detected layers and the required fix so I act without reading runner internals. *(Ref: FR-ADHOC-043)*

## Acceptance Outline
- **AO-043-01** *(Ref: AC-ADHOC-043-01, US-043-01)*: A task declaring unit plus integration test targets stops at RED pre with a split-task error; zero RED agent attempts run.
  - **Happy Path**: RED pre reports the two detected layers and the split action; the task ends clean with no escalate counted.
  - **Error Category**: Mixed contract detected from any two signals (card paths, declared commands, declared strategy plus card paths).
  - **Boundary Category**: Single-layer contracts pass the check untouched.
- **AO-043-02** *(Ref: AC-ADHOC-043-02, US-043-02)*: A unit-only or integration-only task runs RED exactly as before.
  - **Happy Path**: No split-task error fires; RED writes tests in the assigned layer dir.
  - **Error Category**: Ambiguous keyword-only cards without concrete multi-layer paths keep current fallback behavior.
  - **Boundary Category**: e2e mixed with any other layer also triggers the split-task error.

## Edge Cases and Boundaries
- Card mentions both layers in prose but declares concrete targets in only one layer: no split error; concrete targets decide.
- Legacy unstamped card with no paths and no strategy: current keyword fallback applies, no new error.
- Task row `test_strategy` names one layer while the card lists files in two: split error fires; files win over the single stamp.

## Performance Constraints
- L_max: 200ms per RED pre check addition
- Throughput: full test suite under 30s (mock `_run_pytest` in new tests per repo rule)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` micro RED-pre split detection (mixed unit plus integration contract raises split-task error; unit-only contract passes through)
- **Integration Sandbox Targets**: `deviate micro run` on a fixture task with a split contract stops before the first agent spawn

## Demonstration Path
```bash
uv run pytest tests/ -k "split" -v
```
