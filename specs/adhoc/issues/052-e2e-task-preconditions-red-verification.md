---
title: "Clarify E2E task preconditions and RED verification responsibilities"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-052
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/052-e2e-task-preconditions-red-verification.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/red.md`, `mise.toml`

## The Problem Contract
E2E tasks stall in RED when the verification command needs local infrastructure the runner never prepared. This issue defines who prepares preconditions, what RED must run, and how missing infrastructure reports without blaming the agent.

## Scope Boundaries
### Hard Inclusions
- Responsibility boundary between DeviaTDD task phases and project setup tasks for E2E preconditions
- RED behavior for E2E tests that start a child API process, including the bounded verification rule
- Named precondition signal with the explicit setup command when infrastructure is missing
- Regression test or prompt rule covering E2E tasks with infrastructure prerequisites

### Defensive Exclusions
- No changes to product test logic or API startup behavior outside the precondition boundary
- No new E2E infrastructure provisioning beyond documenting and wiring the setup command
- No changes to non-E2E task strategies or verification ladders

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-052`
- **Acceptance Criteria Tokens**: `AC-ADHOC-052-01`, `AC-ADHOC-052-02`
- **Data Model Entities**: Task card (`verification`, preconditions), RED handover manifest
- **Origin**: GitHub issue 212 (`bug: clarify E2E task preconditions and RED verification responsibilities`)

## User Stories Ledger
- **US-052-01**: As a task author, I want the verification path to prepare E2E preconditions so that RED agents never stall on missing environment files. *(Ref: FR-ADHOC-052)*
- **US-052-02**: As a RED agent, I want missing infrastructure reported as a named precondition signal so that a valid RED phase never counts as my error. *(Ref: FR-ADHOC-052)*

## Acceptance Outline
- **AO-052-01** *(Ref: AC-ADHOC-052-01, US-052-01)*: RED writes the E2E failing test and the documented verification path prepares preconditions or fails with the explicit setup command.
  - **Happy Path**: E2E preconditions prepared, RED test written, verification runs and fails on the assertion.
  - **Error Category**: Verification path without prepared preconditions fails with the explicit setup command named.
  - **Boundary Category**: E2E test that starts a child API process follows the bounded RED verification rule.
- **AO-052-02** *(Ref: AC-ADHOC-052-02, US-052-02)*: Unavailable infrastructure emits a named signal with the required setup command and the RED phase keeps a non-error status.
  - **Happy Path**: Missing infrastructure produces the named signal plus the exact setup command to run.
  - **Error Category**: Signal without the setup command named counts as a defect in the signal.
  - **Boundary Category**: Partially available infrastructure still resolves to exactly one outcome: RED proof or named signal.

## Edge Cases and Boundaries
- Child API process starts but probes time out: signal names the probe target and timeout, still non-error for RED.
- Environment file present but malformed: signal names the file and the parse failure.
- Setup command itself fails: signal carries the setup exit output verbatim.
- Verification command declares no preconditions: RED runs it as-is with no signal path.

## Performance Constraints
- L_max: 500ms issue registration; verification bounds follow the task card timeout.
- Throughput: one RED attempt per task loop; no retry storms on missing infrastructure.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` unit suite covering the precondition check and signal emission (exact paths defined at plan time).
- **Integration Sandbox Targets**: E2E RED dry-run with preconditions absent confirms the named signal and setup command.

## Demonstration Path
```bash
mise run test
```
