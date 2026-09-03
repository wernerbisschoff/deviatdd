---
title: "Migrate test tree to tests/unit convention; fix integration/e2e stubs"
labels: [chore, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-038
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/038-test-tree-unit-convention.md`
- **Primary Architectural Workstation**: `mise.toml`, `src/deviate/cli/micro.py`, `tests/unit/`, `tests/integration/`, `tests/e2e/`
- **Upstream GH Issue**: `205` (close after local registration)

## The Problem Contract
`mise unit` pointed at the empty `tests/unit/` stub, so the micro runner collected zero tests and RED looped into TRAIN_EXHAUSTED. This issue migrates the real suites under `tests/unit/` and fixes the integration/e2e stub tasks.

## Scope Boundaries
### Hard Inclusions
- Move real suites (`tests/unit/test_cli`, `test_core`, `test_macro`, `test_meso`, `test_micro`, `test_state`, `test_ui`, `test_release`, `tests/unit/core`) under `tests/unit/` per `_CONVENTIONAL_SUITE_DIRS`
- Rewrite intra-suite absolute imports broken by the move
- Update hardcoded `tests/test_*` paths in `specs/` Verification lines and DeviaTDD docs
- Point `mise integration` and `mise e2e` at real suites (bats for e2e)

### Defensive Exclusions
- No runner strategy or JUDGE scope change beyond path updates
- No suite-budget enforcement (111s over 30s budget is noted, not fixed here)
- No new test markers or suite splitting unless needed for the move

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-038`
- **Acceptance Criteria Tokens**: `AC-ADHOC-038-01`, `AC-ADHOC-038-02`
- **Data Model Entities**: none

## User Stories Ledger
- **US-038-01**: As a developer running the micro loop, I want `mise unit` to collect the real unit suites under `tests/unit/` so RED does not loop into TRAIN_EXHAUSTED on exit 5. *(Ref: FR-ADHOC-038)*
- **US-038-02**: As a developer, I want `mise integration` and `mise e2e` to target real suites (bats for e2e) so stub rot does not hide failures. *(Ref: FR-ADHOC-038)*

## Acceptance Outline
- **AO-038-01** *(Ref: AC-ADHOC-038-01, US-038-01)*: Real suites run from `tests/unit/` with imports resolved and no exit-5 empty collection
  - **Happy Path**: `mise unit` collects and runs the migrated suites
  - **Error Category**: Broken intra-suite import fails the suite visibly, not as empty collection
  - **Boundary Category**: Empty `tests/unit/` stub no longer masks missing suites
- **AO-038-02** *(Ref: AC-ADHOC-038-02, US-038-02)*: Spec Verification lines and docs resolve to the new layout; integration/e2e tasks target real suites
  - **Happy Path**: Runner parses Verification lines against the new paths
  - **Error Category**: Stale `tests/test_*` path is caught as missing, not silently skipped
  - **Boundary Category**: `mise e2e` delegates to `bats tests/e2e/` via `mise test-e2e`

## Edge Cases and Boundaries
- Intra-suite cross-imports (e.g. `tests.test_micro.test_judge_feedback_persist` importing from `test_judge_refactor_note_routing`) break on move and need rewrites
- `specs/` Verification lines parsed by the runner to scope test commands go stale on move
- `mise run unit` takes ~111s for 1910 tests, over the 30s suite budget in `AGENTS.md`

## Performance Constraints
- L_max: 30000ms full-suite budget per `AGENTS.md` (currently exceeded at ~111s; noted, not enforced here)
- Throughput: `mise unit` collects all migrated suites in one run

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/` migrated suites; `mise run unit`
- **Integration Sandbox Targets**: `mise run integration`; `mise run test-e2e` (`bats tests/e2e/`)

## Demonstration Path
```bash
mise run unit
mise run integration
mise run test-e2e
```
