---
title: "Validate issue traceability before PLAN starts with legacy repair"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-055
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/055-plan-traceability-gate.md`
- **Primary Architectural Workstation**: `src/deviate/cli/meso.py`, `src/deviate/prompts/auto/plan.md`, `src/deviate/prompts/auto/shard.md`

## The Problem Contract
`plan pre` returns READY for issues that lack the traceability fields the PLAN prompt requires. This issue adds a fail-fast gate plus a legacy repair path so no agent invents identifiers.

## Scope Boundaries
### Hard Inclusions
- `plan pre` traceability gate over stories, tracing, and acceptance outlines with a named NOT_READY diagnostic
- Legacy issue repair path that restores the missing sections and re-passes the gate
- Shard and adhoc template agreement on the required identifiers
- Spec plus CHANGELOG updated in the same commit

### Defensive Exclusions
- No changes to Micro RED/GREEN/JUDGE behavior
- No product-pack artifacts or release scaffolding
- No backfill of shipped plans beyond the repair path

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-055`
- **Acceptance Criteria Tokens**: `AC-ADHOC-055-01`, `AC-ADHOC-055-02`
- **Data Model Entities**: Plan pre contract, traceability diagnostic, repair path
- **Origin**: GitHub issue 215 (`Validate issue traceability before PLAN starts and support legacy issue repair`)
- **Explore Context**: `specs/explore/gh-215-plan-traceability.md`

## User Stories Ledger
- **US-055-01**: As a plan agent, I want `plan pre` to fail fast on untraceable issues so that I never invent identifiers to satisfy the contract. *(Ref: FR-ADHOC-055)*
- **US-055-02**: As a maintainer, I want a legacy issue repair path so that old issues gain stories and tracing without hand edits. *(Ref: FR-ADHOC-055)*

## Acceptance Outline
- **AO-055-01** *(Ref: AC-ADHOC-055-01, US-055-01)*: `plan pre` returns NOT_READY with the missing fields named when the issue lacks stories, tracing, or acceptance outlines.
  - **Happy Path**: A traceable issue passes `plan pre` with a READY contract.
  - **Error Category**: An issue missing stories, tracing, or outlines fails with each missing field named plus the repair step.
  - **Boundary Category**: A partially traceable issue names exactly the missing subset, not a blanket failure.
- **AO-055-02** *(Ref: AC-ADHOC-055-02, US-055-02)*: A legacy issue follows the repair path and then passes `plan pre` with a READY contract.
  - **Happy Path**: The repaired issue carries stories, tracing, and outlines and passes the gate.
  - **Error Category**: A repair that skips a required section still fails the gate with the gap named.
  - **Boundary Category**: A legacy issue already carrying the sections passes without repair.

## Edge Cases and Boundaries
- PRD traceability validator `_validate_prd_traceability` stays the model: FAIL plus detail, not silent READY.
- Partial identifiers (US present, AC absent) fail with the absent token named.
- Repair path never edits Micro artifacts or product-pack files.

## Performance Constraints
- L_max: 500ms issue registration; gate check stays within the existing `plan pre` budget.
- Throughput: one gate behavior ships with its failing contract test first.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_meso/` contract tests pin READY and NOT_READY paths (exact cases defined at plan time).
- **Integration Sandbox Targets**: `plan pre` run against a legacy fixture confirms NOT_READY, then READY after repair.

## Demonstration Path
```bash
mise run test
```
