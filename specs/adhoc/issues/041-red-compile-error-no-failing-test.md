---
title: "RED compile-error failures count as failing tests, TRAIN_EXHAUSTED fails clean"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-041
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/041-red-compile-error-no-failing-test.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/`

## The Problem Contract
Remote gh issue 179 reports RED compile errors misroute to no-failing-test adjudication. The runner loops to TRAIN_EXHAUSTED and crashes with a traceback. This issue fixes the classification and the failure path.

## Scope Boundaries
### Hard Inclusions
- Detect compile-error output in `_run_red_phase` test result and treat it as a failing RED that proceeds to GREEN
- Make TRAIN_EXHAUSTED record a clean `FAILED` task row and exit without an unhandled traceback
- Guard the no-failing-test COMPLETE route against empty evidence rows

### Defensive Exclusions
- No change to GREEN implementation logic or JUDGE verdict semantics
- No change to the 3-escalate budget caps
- No Elixir/Phoenix-specific runner; detection stays output-pattern based and language-agnostic

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-041`
- **Acceptance Criteria Tokens**: `AC-ADHOC-041-01`, `AC-ADHOC-041-02`
- **Data Model Entities**: TaskRecord (RED/FAILED/COMPLETED transitions)

## User Stories Ledger
- **US-041-01**: As a developer on a compiled-language repo, I want a RED test that fails to compile to count as a failing test so GREEN implements the missing module. *(Ref: FR-ADHOC-041)*
- **US-041-02**: As an operator, I want TRAIN_EXHAUSTED to record a clean task failure so I get an actionable result instead of a traceback. *(Ref: FR-ADHOC-041)*

## Acceptance Outline
- **AO-041-01** *(Ref: AC-ADHOC-041-01, US-041-01)*: RED with compile errors proceeds to GREEN
  - **Happy Path**: Non-zero exit with compile-error markers and zero counted test failures commits a RED failing-test boundary and dispatches GREEN
  - **Error Category**: Genuine no-test output (exit 0, pytest exit 5, exit 127) still routes to no-failing-test adjudication
  - **Boundary Category**: Mixed output with both compile errors and passing tests counts as failing
- **AO-041-02** *(Ref: AC-ADHOC-041-02, US-041-02)*: Exhaustion and evidence guardrails hold
  - **Happy Path**: Three RED escalates append a `FAILED` task row with the TRAIN_EXHAUSTED reason and exit cleanly
  - **Error Category**: No COMPLETED row ships with empty evidence quotes or a docs-only diff
  - **Boundary Category**: Already-satisfied COMPLETE route still requires declared regression paths in the diff

## Edge Cases and Boundaries
- ExUnit compile failure text (`Compilation failed`, `is not available`, `undefined function`) with exit non-zero and zero test failures
- Python traceback at import/collection time (e.g. ModuleNotFoundError during collection) counts as failing, not empty collection
- True empty collection (pytest exit 5 with "no tests ran") keeps current adjudication behavior
- Remote source: gh issue 179 (`RED compile-error failures count as 'no failing test'`), deviate 2.26.0, MeepleInn TSK-002-01/02

## Performance Constraints
- L_max: 200ms per added classification check inside the RED gate
- Throughput: full test suite under 30s (mock `_run_pytest` subprocess in new tests per AGENTS.md)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_red_compile_error.py` — compile-error output proceeds to GREEN; exit-0/exit-5/exit-127 still adjudicate; TRAIN_EXHAUSTED writes FAILED row without raising past the cycle
- **Integration Sandbox Targets**: task ledger transitions RED then FAILED across three escalates on a fixture repo

## Demonstration Path
```bash
mise run test -- tests/unit/test_micro/test_red_compile_error.py
```
