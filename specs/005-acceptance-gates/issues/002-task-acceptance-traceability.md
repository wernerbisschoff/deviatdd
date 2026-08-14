---
title: "Task Acceptance Traceability via acceptance_criteria Links"
labels: [enhancement, vertical-slice, acceptance-gates, meso-layer]
source_file: "specs/005-acceptance-gates/issues/002-task-acceptance-traceability.md"
blocked_by: ["005-001"]
coordinates_with: ["005-001"]
issue_id: 005-002
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/005-acceptance-gates/`
- **Local Issue File**: `specs/005-acceptance-gates/issues/002-task-acceptance-traceability.md`
- **Primary Architectural Workstations**:
  - `src/deviate/state/ledger.py:81-98` — MODIFY: add the optional `acceptance_criteria: list[CriterionLink] | None = None` field to `TaskRecord`, preserving `model_config = {"extra": "forbid"}`.
  - `src/deviate/state/ledger.py` — ADD: the `CriterionLink` Pydantic model with `criterion_id: str`, `verification_mode: Literal["automated", "manual", "deferred"]`, and `test_ref: str | None = None`.
  - `src/deviate/core/tasks_ledger.py:15` — MODIFY: `generate_jsonl_from_md` propagates task-to-criterion and criterion-to-test links from `tasks.md` into each generated `TaskRecord` row.
  - `src/deviate/core/tasks_ledger.py:45` — MODIFY: `_build_task_record` carries the parsed links into the record; malformed `criterion_id` or an `automated` link with null `test_ref` raises a validation error.
  - `src/deviate/core/tasks_ledger.py:60` — REFERENCE: `validate_tasks_jsonl` stays the row-level validator.
  - `specs/{NNN}-{slug}/tasks.md` — TARGET: per-task criterion references (input artifact).
  - `specs/{NNN}-{slug}/tasks.jsonl` — OUTPUT: rows carry `acceptance_criteria` links.
  - `deviate meso tasks pre` — GATE: emits the traced rows; blocks on invalid links.
  - `tests/test_core/test_tasks_ledger.py` — TARGET: extend generation tests with link propagation.
  - `tests/test_state/test_ledger.py` — TARGET: extend `TaskRecord` parse tests; legacy rows without the field still parse.
- **Upstream Evidence**:
  - `specs/005-acceptance-gates/prd.md:13` — Hard directive: optional `acceptance_criteria: list[CriterionLink] | None` on `TaskRecord`, propagated by `generate_jsonl_from_md`.
  - `specs/005-acceptance-gates/prd.md:28-49` — Data contract: `CriterionLink` and `TaskRecord` schemas with `model_config = {"extra": "forbid"}`.
  - `specs/005-acceptance-gates/prd.md:52-56` — Invariants: field optional with default `None`; `criterion_id` matches `AC-PLAN-\d{3}`; automated links carry non-null `test_ref`.
  - `specs/005-acceptance-gates/prd.md:115` — Exception strategy: invalid `criterion_id` or null `test_ref` on an automated link fails generation.
  - `specs/005-acceptance-gates/data-model.md` — REFERENCE: `CriterionLink`, `TaskRecord`, and the append-only tasks ledger schema.

## The Problem Contract

Task generation reads `tasks.md` and the validated `## Acceptance Contract` from `plan.md`. Each task row in `specs/**/tasks.jsonl` gains optional traceability links: which `AC-PLAN-NNN` criteria the task satisfies, the verification mode of each criterion, and the test that verifies an automated criterion.

The field is additive and optional. JSONL rows written by older CLI versions carry no field; they must parse under `model_config = {"extra": "forbid"}` with the field absent. Invalid links fail generation so the ledger never carries dangling references.

## Scope Boundaries

### Hard Inclusions

- `CriterionLink` model with `criterion_id`, `verification_mode`, and optional `test_ref`.
- `TaskRecord.acceptance_criteria: list[CriterionLink] | None = None` with `model_config = {"extra": "forbid"}` intact.
- `generate_jsonl_from_md` propagates the links into each generated row.
- An invalid `criterion_id` (not `AC-PLAN-\d{3}`) fails generation.
- A link with `verification_mode == "automated"` and null `test_ref` fails generation.
- Legacy rows without the field parse successfully.

### Defensive Exclusions

- No change to the verification-mode validation in `src/deviate/core/validation.py`; that belongs to issue `005-001` (this issue consumes the validated contract).
- No change to `src/deviate/cli/micro.py` phase runners; gate behavior belongs to issues `005-003` and `005-004`.
- No new `TaskRecord.status` value (PRD RESOLVED-Q-004); status stays the existing seven-value Literal.
- No persistent checkpoint record in `.deviate/` or the task ledger.
- No change to `src/deviate/prompts/`; prompt alignment belongs to issue `005-005`.
- No change to `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, or `CHANGELOG.md`; spec alignment belongs to issue `005-005`.

## Upstream Requirement Tracing

- **FR-005-02**: Task Acceptance Traceability
- **AC-005-02-01**: Generated task rows carry the `acceptance_criteria` links from `tasks.md`; happy path emits rows with valid links via `deviate meso tasks pre`; malformed criterion id or missing `test_ref` on an automated link fails generation; legacy rows without the field still parse under `extra="forbid"`.

## User Stories Ledger

- **US-005-03** (parent FR-005-02): As a task generator, I emit each task row with its `acceptance_criteria` links so the task points at the criteria it satisfies and the tests that verify them.
- **US-005-04** (parent FR-005-02): As a consumer of legacy ledgers, I parse task rows written by older CLI versions without the new field, so mixed-version JSONL stays valid.

## Acceptance Outline

- **AO-002** / `AC-005-02-01` / US-005-03: `deviate meso tasks pre` emits `specs/**/tasks.jsonl` rows whose `acceptance_criteria` arrays match the links declared in `tasks.md`; each `criterion_id` matches `AC-PLAN-\d{3}`; each automated link carries a non-null `test_ref`.
- **AO-002** / `AC-005-02-01` / US-005-03: A `tasks.md` link with a malformed `criterion_id` fails generation with a named error; an automated link with a missing `test_ref` fails generation with a named error.
- **AO-002** / `AC-005-02-01` / US-005-04: A legacy `TaskRecord` JSONL row without `acceptance_criteria` parses with the field absent; `model_config = {"extra": "forbid"}` rejects only genuinely unknown fields.

## Edge Cases and Boundaries

- A task with no criterion references: the field is `null`, never an empty list that implies zero criteria.
- A `criterion_id` that matches `AC-PLAN-\d{3}` but names a criterion absent from the owning slice's `plan.md`: fail generation (dangling reference).
- A `verification_mode` value outside the three literals: fail generation at model validation.
- An automated link whose `test_ref` names a file that does not exist: the link still generates; existence checks are not part of this issue.
- A `deferred` or `manual` link with a `test_ref` present: allowed; `test_ref` is required only for `automated`.
- Mixed-version ledgers: a file with some rows carrying the field and some without parses fully.

## Performance Constraints

- `generate_jsonl_from_md` stays linear in the number of tasks and links; no new dependencies.
- Full test suite stays under 30 seconds (project execution contract).
- CLI init stays at L_max ≤ 500ms; per-agent export ≤ 200ms.
- No new external integration, database runtime, or slice-level file format.

## Multi-Tiered Verification Targets

- **Unit**: `tests/test_core/test_tasks_ledger.py` — link propagation, malformed id rejection, null `test_ref` rejection, absent-field default.
- **Unit**: `tests/test_state/test_ledger.py` — `TaskRecord` round-trip with `acceptance_criteria`; legacy row parse without the field.
- **Integration**: fixture `tasks.md` with criterion references runs through `deviate meso tasks pre`; inspect emitted `tasks.jsonl` rows for `acceptance_criteria`.

## Demonstration Path

```bash
# 1. Unit verification — link propagation and rejection cases
uv run pytest tests/test_core/test_tasks_ledger.py tests/test_state/test_ledger.py -v

# 2. Integration: tasks rows carry acceptance_criteria links
#    (run inside a fixture epic whose plan.md contract is valid and whose
#     tasks.md declares per-task criterion references)
deviate meso tasks pre
# expected: specs/{NNN}-{slug}/tasks.jsonl rows include
#           "acceptance_criteria": [{"criterion_id": "AC-PLAN-001",
#             "verification_mode": "automated", "test_ref": "tests/..."}]

# 3. Integration: invalid link blocks generation
#    (point one criterion_id at an id outside AC-PLAN-\d{3}, or drop the
#     test_ref of an automated link)
deviate meso tasks pre
# expected: exit non-zero; stderr names the invalid criterion_id / missing test_ref

# 4. Legacy parse check — a row without the field still parses
uv run pytest tests/test_state/test_ledger.py -v -k "legacy or extra_forbid or acceptance"

# 5. Regression: full check bundle stays green
mise run check
```
