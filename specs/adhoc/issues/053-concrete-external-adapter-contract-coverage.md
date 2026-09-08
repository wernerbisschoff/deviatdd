---
title: "Require concrete external adapter contract coverage"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-053
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/053-concrete-external-adapter-contract-coverage.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/auto/plan.md`, `src/deviate/prompts/auto/tasks.md`, `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/auto/red.md`

## The Problem Contract
Tasks that claim real provider integration pass with fake port tests while the concrete SDK adapter stays incompatible with the installed dependency. This issue splits adapter transport from port behavior and makes JUDGE reject fake-only coverage.

## Scope Boundaries
### Hard Inclusions
- Plan/task rule: split port and service behavior from concrete adapter transport work when the plan names an external SDK or provider adapter
- Acceptance criteria and tests for the concrete adapter contract: dependency signature, authentication, request identity preservation, response lookup
- Agent prompt rule to inspect the installed dependency signature and behavior
- JUDGE rule to reject fake-only coverage when the task claims real provider integration
- Import boundary and deferred credential and client construction checks

### Defensive Exclusions
- No changes to any specific provider SDK or adapter implementation
- No live-credential integration runs; dependency signature checks stay offline and deterministic
- No changes to non-adapter task splitting or verification ladders

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-053`
- **Acceptance Criteria Tokens**: `AC-ADHOC-053-01`, `AC-ADHOC-053-02`
- **Data Model Entities**: Task card (Test Strategy, acceptance criteria), JUDGE verdict with `train_feedback`
- **Origin**: GitHub issue 213 (`enhancement: require concrete external adapter contract coverage`)

## User Stories Ledger
- **US-053-01**: As a plan author, I want adapter transport work split from port behavior so that the concrete SDK contract gets its own acceptance criteria. *(Ref: FR-ADHOC-053)*
- **US-053-02**: As an operator, I want JUDGE to reject fake-only coverage for provider integration tasks so that SDK mismatches surface in the original task. *(Ref: FR-ADHOC-053)*

## Acceptance Outline
- **AO-053-01** *(Ref: AC-ADHOC-053-01, US-053-01)*: A plan naming an external adapter carries separate acceptance criteria and tests for the concrete adapter transport, including dependency signature, authentication, and response handling.
  - **Happy Path**: Adapter task ships with concrete contract tests that exercise the installed dependency surface.
  - **Error Category**: Missing authentication or unsupported fields fail the adapter tests with the dependency evidence named.
  - **Boundary Category**: Import-time side effects and deferred client construction stay covered by the adapter contract.
- **AO-053-02** *(Ref: AC-ADHOC-053-02, US-053-02)*: JUDGE rejects a provider-integration task whose tests exercise only the fake port, with feedback naming the missing concrete contract evidence.
  - **Happy Path**: Fake-only coverage for a claimed integration yields rejection plus a correction contract for the concrete tests.
  - **Error Category**: Rejection feedback without the missing evidence named counts as a defect in the feedback.
  - **Boundary Category**: Pure port-behavior tasks with no integration claim keep fake coverage valid.

## Edge Cases and Boundaries
- Installed dependency absent at task time: adapter tests pin the declared version and fail with the missing-dependency signal.
- Provider credentials unavailable: tests cover construction deferral and auth wiring without live calls.
- Adapter wraps multiple provider methods: each method gets its own contract row or its own split task.
- Fake port shared across tasks: port-behavior tests stay valid; only the integration claim triggers the concrete rule.

## Performance Constraints
- L_max: 500ms issue registration; adapter signature checks run offline with no network wait.
- Throughput: one adapter contract per task; no duplicate concrete coverage across split tasks.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` unit suite covering the split rule and the JUDGE fake-only rejection (exact paths defined at plan time).
- **Integration Sandbox Targets**: Prompt-level check that an adapter task card carries concrete contract criteria before dispatch.

## Demonstration Path
```bash
mise run test
```
