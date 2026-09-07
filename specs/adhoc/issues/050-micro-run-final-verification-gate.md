---
title: "Verify full test suites at end of micro run before reporting success"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-050
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/050-micro-run-final-verification-gate.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `mise.toml`

## The Problem Contract
The micro run reports success when the task queue drains. No final check confirms the full tree stays green. This issue adds one final verification gate after the last task.

## Scope Boundaries
### Hard Inclusions
- Final gate after NO_PENDING_TASKS runs unit suite (`mise run unit` or equivalent pytest invocation)
- Final gate runs integration suite (`mise run integration` or equivalent)
- Final gate runs `mise doctor` and runs e2e (`mise run e2e`) only when doctor passes
- Gate failure blocks success reporting with a named signal (tests vs ENV_NOT_READY)

### Defensive Exclusions
- No change to per-task RED/GREEN/JUDGE/REFACTOR flow
- No change to `e2e pre` per-issue completeness semantics
- No new test runners beyond the rungs already defined in `mise.toml`
- No bypass of the final gate via flags in this issue

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-050`
- **Acceptance Criteria Tokens**: `AC-ADHOC-050-01`, `AC-ADHOC-050-02`
- **Data Model Entities**: TaskRecord (COMPLETED status), MicroRunGateResult

## User Stories Ledger
- **US-050-01**: As an operator finishing `deviate micro run`, I want one final full-suite check after the last task so merged work never hides a cross-task regression. *(Ref: FR-ADHOC-050)*
- **US-050-02**: As a developer with a broken local environment, I want e2e to skip when `mise doctor` fails so I get a clear ENV_NOT_READY signal instead of noisy e2e failures. *(Ref: FR-ADHOC-050)*

## Acceptance Outline
- **AO-050-01** *(Ref: AC-ADHOC-050-01, US-050-01)*: After the queue drains to NO_PENDING_TASKS, the run executes unit and integration suites and reports success only when both pass.
  - **Happy Path**: All tasks COMPLETED plus unit plus integration pass; run exits 0 with a final-gate summary.
  - **Error Category**: Unit or integration failure fails the run with the failing suite named in output.
  - **Boundary Category**: Empty queue on entry still runs the gate once rather than exiting silently.
- **AO-050-02** *(Ref: AC-ADHOC-050-02, US-050-02)*: Doctor gates e2e; e2e runs only on doctor success.
  - **Happy Path**: Doctor passes; e2e runs and its result decides the final gate.
  - **Error Category**: Doctor failure reports ENV_NOT_READY and skips e2e.
  - **Boundary Category**: E2e failure after passing doctor fails the run with the e2e suite named.

## Edge Cases and Boundaries
- Queue drains with zero tasks ever run: gate still executes once.
- Unit passes but integration fails: run fails; report names integration.
- Doctor binary or rung missing: treat as ENV_NOT_READY with a clear message, never silently skip e2e as passed.
- E2e suite empty or absent: report skip explicitly; do not claim e2e passed.

## Performance Constraints
- L_max: final gate adds no more than one sequential pass over unit, integration, doctor, e2e
- Throughput: single micro run executes the gate exactly once per drain

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_micro.py` — drained queue triggers unit plus integration invocations; doctor failure skips e2e; gate failure exits nonzero
- **Integration Sandbox Targets**: drained `micro run --all` on a fixture issue exercises the gate against `mise.toml` rungs

## Demonstration Path
```bash
mise run unit && mise run integration && mise run doctor && mise run e2e
```
