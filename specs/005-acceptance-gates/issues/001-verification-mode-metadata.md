---
title: "Acceptance Contract Verification-Mode Metadata"
labels: [enhancement, vertical-slice, acceptance-gates, meso-layer]
source_file: "specs/005-acceptance-gates/issues/001-verification-mode-metadata.md"
blocked_by: []
coordinates_with: []
issue_id: 005-001
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/005-acceptance-gates/`
- **Local Issue File**: `specs/005-acceptance-gates/issues/001-verification-mode-metadata.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/validation.py:112` — MODIFY: `validate_acceptance_contract` accepts one `**Verification Mode**: <automated|manual|deferred>` line per `AC-PLAN-NNN` scenario body and validates the mode literal.
  - `src/deviate/core/validation.py:117` — REFERENCE: the scenario pattern `r"\*\*(?P<label>Scenario (?P<id>AC-PLAN-\d{3})):.*?\*\*"` that extracts each `AC-PLAN-NNN` scenario; reuse it to locate each scenario body.
  - `src/deviate/core/validation.py:74-91` — REFERENCE: `extract_section_body` and `_validate_scenarios` stay the extraction machinery for the `## Acceptance Contract` section.
  - `src/deviate/core/validation.py:93-97` — REFERENCE: `validate_gherkin_syntax` stays mandatory; the mode check adds to it, never replaces it.
  - `specs/{NNN}-{slug}/plan.md` — TARGET: each `## Acceptance Contract` scenario body in a slice's `plan.md` carries the Verification Mode line.
  - `src/deviate/cli/meso.py:939` — GATE: `_tasks_pre` blocks on any validation error emitted by `validate_acceptance_contract` (via `deviate meso tasks pre`).
  - `tests/test_core/test_validation.py` — TARGET: extend the acceptance-contract tests with Verification Mode acceptance, rejection, and boundary cases.
- **Upstream Evidence**:
  - `specs/005-acceptance-gates/prd.md:12` — Hard directive: add `**Verification Mode**: <automated|manual|deferred>` metadata validated by `validate_acceptance_contract`.
  - `specs/005-acceptance-gates/prd.md:96-108` — FR-005-01 acceptance outline: mode present and legal passes; mode missing or illegal blocks `deviate meso tasks pre`.
  - `specs/005-acceptance-gates/prd.md:196` — RESOLVED-Q-003: each scenario carries exactly one Verification Mode line in its body.
  - `specs/005-acceptance-gates/data-model.md` — REFERENCE: `AcceptanceContract` schema and the mandatory clause set (Source Outline, Upstream Traceability, Current-Code Evidence, Given/When/Then).

## The Problem Contract

The plan phase produces `plan.md` with an `## Acceptance Contract` section. Each scenario has an `AC-PLAN-NNN` id and a body that states the source outline, upstream traceability, current-code evidence, and Given/When/Then clauses.

The feature adds a verification-mode declaration to each scenario body. The mode states how the criterion is verified: `automated`, `manual`, or `deferred`. The validation gate checks the mode at plan post and at tasks pre. A scenario without a mode line, or with a mode outside the three literals, fails validation and blocks the meso pipeline.

This issue ships only the contract validation. The propagation of the mode into task rows, the RED/GREEN/REFACTOR gate behavior, and the prompt/spec alignment land in later issues.

## Scope Boundaries

### Hard Inclusions

- `validate_acceptance_contract` validates the Verification Mode literal on every `AC-PLAN-NNN` scenario.
- A scenario with mode `automated`, `manual`, or `deferred` passes the mode check.
- A scenario with a missing mode line or an illegal value produces a named validation error.
- The existing mandatory clauses stay enforced: Source Outline, Upstream Traceability, Current-Code Evidence, and Given/When/Then.
- `deviate meso tasks pre` blocks on any validation error.
- Tests in `tests/test_core/test_validation.py` pin the accept/reject/boundary behavior.

### Defensive Exclusions

- No change to `src/deviate/state/ledger.py` `TaskRecord` or any ledger model; the `acceptance_criteria` field belongs to issue `005-002`.
- No change to `src/deviate/cli/micro.py` phase runners; RED/GREEN/REFACTOR gates belong to issues `005-003` and `005-004`.
- No change to `src/deviate/prompts/`; prompt-template alignment belongs to issue `005-005`.
- No change to `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, or `CHANGELOG.md`; spec alignment belongs to issue `005-005`.
- No new `acceptance.md` slice artifact or generation scaffolding (PRD Option B, rejected).
- No new `TaskRecord.status` value or persistent checkpoint record (PRD RESOLVED-Q-004).

## Upstream Requirement Tracing

- **FR-005-01**: Acceptance Contract Verification-Mode Metadata
- **AC-005-01-01**: `validate_acceptance_contract` accepts a scenario with `**Verification Mode**: automated`; happy path passes plan post and tasks pre; missing or illegal mode blocks tasks pre with a named error; `manual`/`deferred` validate without a `test_ref` in the contract body.
- **AC-005-01-02**: Validation keeps requiring Source Outline, Upstream Traceability, Current-Code Evidence, and Given/When/Then; removing any clause still fails validation.

## User Stories Ledger

- **US-005-01** (parent FR-005-01): As a feature planner, I record one Verification Mode on each `AC-PLAN-NNN` scenario body in `plan.md` so the mode travels with the criterion it describes.
- **US-005-02** (parent FR-005-01): As an operator, I see `deviate meso tasks pre` fail with a named validation error when a scenario lacks a mode or carries an illegal mode, so I fix the contract before task generation.

## Acceptance Outline

- **AO-001** / `AC-005-01-01` / US-005-01, US-005-02: A scenario with `**Verification Mode**: automated` passes `validate_acceptance_contract`; `deviate plan post` and `deviate meso tasks pre` proceed. A scenario with a missing mode line or a mode outside `automated|manual|deferred` produces a named validation error; `deviate meso tasks pre` blocks. A scenario with mode `manual` or `deferred` passes without any `test_ref` in the contract body.
- **AO-001** / `AC-005-01-02` / US-005-01: A scenario that omits any one of Source Outline, Upstream Traceability, Current-Code Evidence, or Given/When/Then still fails validation, with or without a valid mode line.

## Edge Cases and Boundaries

- A `## Acceptance Contract` section with zero scenarios: validation reports the missing-contract error (existing behavior, unchanged).
- A scenario with a mode line that repeats: the first or last occurrence rule must be deterministic; report a named error rather than silent overwrite.
- A mode line with surrounding whitespace or differing case: case-insensitive match on the three literals only; anything else is illegal.
- A contract where all scenarios are `deferred`: validation passes; mode never exempts the executable test suite.
- A contract body that carries a mode line but drops an existing mandatory clause: validation fails on the missing clause.
- Mixed modes across scenarios in one contract: each scenario validates independently.

## Performance Constraints

- `validate_acceptance_contract` runs in linear time over the scenario list; no new dependencies.
- Full test suite stays under 30 seconds (project execution contract).
- CLI init stays at L_max ≤ 500ms; per-agent export ≤ 200ms.
- No persistent state, no ledger writes, no network calls introduced by this issue.

## Multi-Tiered Verification Targets

- **Unit**: `tests/test_core/test_validation.py` — extend with: mode accepted per literal; missing mode rejected; illegal mode rejected; mandatory clauses still enforced; boundary cases above.
- **Integration**: fixture `plan.md` with a valid contract runs through `deviate plan post` and `deviate meso tasks pre` without error; a contract with a missing mode blocks `deviate meso tasks pre` with a named error.

## Demonstration Path

```bash
# 1. Unit verification — mode validation behavior
uv run pytest tests/test_core/test_validation.py -v

# 2. Integration: valid contract passes the meso gates
#    (run inside a fixture epic with a plan.md whose scenarios carry
#     `**Verification Mode**: automated|manual|deferred`)
deviate plan post
deviate meso tasks pre

# 3. Integration: invalid contract blocks tasks pre with a named error
#    (remove the Verification Mode line from one scenario, or set an
#     illegal value such as `**Verification Mode**: soon`)
deviate meso tasks pre
# expected: exit non-zero; stderr names the validation error

# 4. Regression: full check bundle stays green
mise run check
```
