# Plan — Task Acceptance Traceability via acceptance_criteria Links

## Plan Summary

- **Issue**: 005-002 — Task Acceptance Traceability via `acceptance_criteria` Links
- **Implementation Strategy**: This is a re-plan: prior `plan.md` was reviewed and refreshed against the completed issue `005-001`, whose `validate_acceptance_contract` (`src/deviate/core/validation.py:162`) now enforces one `**Verification Mode**` line per `AC-PLAN-NNN` scenario. Add a `CriterionLink` Pydantic model and an optional `acceptance_criteria: list[CriterionLink] | None` field to `TaskRecord` in `src/deviate/state/ledger.py`. Extend `generate_jsonl_from_md` and `_build_task_record` in `src/deviate/core/tasks_ledger.py` to parse per-task `**Acceptance Criteria**:` bullets from `tasks.md` and propagate the parsed links into each generated row. `CriterionLink` enforces the `AC-PLAN-\d{3}` id format, the three verification-mode literals, and the automated-link `test_ref` invariant, so malformed links fail generation with named errors. The field stays optional with default `None`, so legacy rows without the field parse under `model_config = {"extra": "forbid"}`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Product Layer Anchors

- **Flow References**: `[]`
- **Source**: `specs/005-acceptance-gates/issues/002-task-acceptance-traceability.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (live-stream agent progress via subprocess RPC and a Rich TUI renderer capped at 10 lines). This issue is orthogonal; it hardens meso task-generation traceability, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (the existing `deviate` CLI component; the `## Components` table C1 entry states it owns phase state, JSONL ledgers, and TOML config, which covers `src/deviate/state/ledger.py` and `src/deviate/core/tasks_ledger.py`)

## Acceptance Contract

**Scenario AC-PLAN-001: Tasks.md criterion references propagate into generated task rows as acceptance_criteria links**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-005-03`, `FR-005-02`, `AC-005-02-01`
- **Current-Code Evidence**: `src/deviate/core/tasks_ledger.py:15`
- **Given**: a `tasks.md` whose task `TSK-005-01` carries an `**Acceptance Criteria**:` bullet that declares `AC-PLAN-001 (automated, tests/unit/test_core/test_tasks_ledger.py)` and `AC-PLAN-002 (manual)`
- **When**: `generate_jsonl_from_md` runs on that `tasks.md`
- **Then**: the returned `TSK-005-01` `TaskRecord` carries an `acceptance_criteria` list whose two `CriterionLink` entries match the declared `criterion_id`, `verification_mode`, and `test_ref` values
- **Verification Mode**: automated

**Scenario AC-PLAN-002: A malformed criterion id or a missing test_ref on an automated link fails generation with a named error**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-005-03`, `FR-005-02`, `AC-005-02-01`
- **Current-Code Evidence**: `src/deviate/core/tasks_ledger.py:45`
- **Given**: a `tasks.md` whose task declares an `**Acceptance Criteria**:` bullet with a `criterion_id` outside the `AC-PLAN-\d{3}` pattern (for example `AC-PLAN-99`), or with an `automated` link whose `test_ref` is empty
- **When**: `generate_jsonl_from_md` runs on that `tasks.md`
- **Then**: generation raises a validation error whose message names the invalid `criterion_id` or the missing `test_ref`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: A legacy task row without the acceptance_criteria field parses with the field absent under extra="forbid"**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-005-04`, `FR-005-02`, `AC-005-02-01`
- **Current-Code Evidence**: `src/deviate/state/ledger.py:81`
- **Given**: a `tasks.jsonl` row written by an older CLI version that carries `id`, `issue_id`, `description`, `status`, `execution_mode`, and `created_at` but no `acceptance_criteria` field
- **When**: `TaskRecord.model_validate` parses that row
- **Then**: the record parses with `acceptance_criteria` equal to `None`, and a row that carries a genuinely unknown field still fails validation
- **Verification Mode**: automated

**Scenario AC-PLAN-004: A task with no criterion references carries a null acceptance_criteria field, never an empty list**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-005-03`, `FR-005-02`, `AC-005-02-01`
- **Current-Code Evidence**: `src/deviate/state/ledger.py:97`
- **Given**: a `tasks.md` whose task `TSK-005-04` contains no `**Acceptance Criteria**:` bullet while a sibling task declares one
- **When**: `generate_jsonl_from_md` runs on that `tasks.md` and serializes the returned records
- **Then**: the record for `TSK-005-04` serializes `acceptance_criteria` as `null`, never as an empty list
- **Verification Mode**: automated

## Workstation Mapping

- **`src/deviate/state/ledger.py:81-98`**: MODIFY — add the optional `acceptance_criteria: list[CriterionLink] | None = None` field to `TaskRecord`.
  - **Current State**: `TaskRecord` (line 81) declares `id`, `issue_id`, `description`, `status` (seven-value `Literal`), `execution_mode`, `created_at`, and `security_profile`; `model_config = {"extra": "forbid"}` is at line 98. No `acceptance_criteria` field exists.
  - **Changes Required**: Insert `acceptance_criteria: list[CriterionLink] | None = None` after the `security_profile` field, before `model_config`. Preserve `model_config = {"extra": "forbid"}` and the seven-value `status` `Literal` unchanged (PRD `RESOLVED-Q-004`).
  - **Integration Surface**: `_build_task_record` (`src/deviate/core/tasks_ledger.py:45`) constructs the model; generated JSONL rows serialize via `append_task_record` (`src/deviate/state/ledger.py:181`); micro-phase runners parse rows via `TaskRecord.model_validate` (`src/deviate/cli/micro.py:1154,1259,1336,2524,3113,4437,4533,4806`).
- **`src/deviate/state/ledger.py`**: ADD — the `CriterionLink` Pydantic model.
  - **Current State**: No `CriterionLink` type exists anywhere in the ledger module; `CriterionLink` appears only in the PRD/data-model schemas.
  - **Changes Required**: Define `CriterionLink(BaseModel)` before `TaskRecord` with `criterion_id: str`, `verification_mode: Literal["automated", "manual", "deferred"]`, `test_ref: str | None = None`, and `model_config = {"extra": "forbid"}` (the ledger-family pattern; `SecurityProfile` at line 61-78 is the precedent). Add a `field_validator("criterion_id")` that rejects values that do not match `^AC-PLAN-\d{3}$`. Add a `model_validator(mode="after")` that raises when `verification_mode == "automated"` and `test_ref is None`. The data-model schema sketch (`specs/005-acceptance-gates/data-model.md:86-96`) shows the same field validator. `re` is already imported at line 4, so no new dependency is needed.
  - **Integration Surface**: Embedded in `TaskRecord.acceptance_criteria`; validated per-link at model construction and at row parse.
- **`src/deviate/core/tasks_ledger.py:15`**: MODIFY — `generate_jsonl_from_md` propagates task-to-criterion and criterion-to-test links from `tasks.md` into each generated `TaskRecord`.
  - **Current State**: The function scans task lines with `_TASK_LINE_PATTERN` (line 11), tracks `current_mode` from `**Mode**:` bullets, and appends `_build_task_record(current_id, issue_id, current_desc, current_mode)` per task. It has no awareness of criterion references.
  - **Changes Required**: Add a `_CRITERIA_LINE_PATTERN` that matches `- **Acceptance Criteria**: <entries>` inside a task block and a `_LINK_PATTERN` that parses each comma-separated entry of the form `AC-PLAN-NNN (mode[, test_ref])`. Track `current_criteria` per task, reset on each new task line, and pass the collected entries to `_build_task_record`. The parse stays linear over the line list and adds no new dependencies (stdlib `re` only).
  - **Integration Surface**: Consumed by `validate_tasks_jsonl` (`src/deviate/core/tasks_ledger.py:60`) and by the meso task-generation flow; the emitted rows serialize through `TaskRecord.model_dump_json`.
- **`src/deviate/core/tasks_ledger.py:45`**: MODIFY — `_build_task_record` carries the parsed links into the record.
  - **Current State**: The helper builds `TaskRecord(id=..., issue_id=..., description=..., status="PENDING", execution_mode=...)` and returns it; no link handling exists.
  - **Changes Required**: Accept the collected criteria entries (default empty), parse each entry with `_LINK_PATTERN`, and construct `CriterionLink` instances. An entry that fails `_LINK_PATTERN` raises a `ValueError` that names the offending text and the task id. A `criterion_id` outside `AC-PLAN-\d{3}`, a `verification_mode` outside the three literals, or an `automated` link with a null `test_ref` raises a `pydantic.ValidationError` from the `CriterionLink` validators, with the offending id or mode in the message. Pass `None` to `TaskRecord` when no links exist so the field serializes as `null`, never as `[]`.
  - **Integration Surface**: `generate_jsonl_from_md` calls this helper once per task; `validate_tasks_jsonl` (line 60) stays the row-level validator and needs no structural change because `TaskRecord.model_validate` now owns the new field.
- **`src/deviate/core/tasks_ledger.py:60`**: REFERENCE — `validate_tasks_jsonl` stays the row-level validator.
  - **Current State**: The function runs `TaskRecord.model_validate` per row and formats `Record {i}: {loc}: {msg}` errors; existing tests cover valid rows, invalid ids, missing fields, invalid status, and extra fields.
  - **Changes Required**: None structurally. The new field flows through the existing validator because `TaskRecord` owns it; new tests assert that rows with valid links pass, rows with a malformed `criterion_id` or an `automated`-with-null-`test_ref` link produce errors whose `loc` names the link, and legacy rows pass unchanged.
  - **Integration Surface**: Called by meso task-validation flows; error strings feed task-ledger inspection.
- **`specs/005-acceptance-gates/002-task-acceptance-traceability/tasks.md`**: TARGET — per-task criterion references (input artifact).
  - **Current State**: The file does not exist yet; the tasks phase authors it. The sibling slice `specs/005-acceptance-gates/001-verification-mode-metadata/tasks.md` shows the bullet convention (per-task `**Mode**:`, `**Files**:`, `**Verification**:` bullets); no `tasks.md` anywhere in `specs/` carries an `**Acceptance Criteria**:` bullet today, so this plan pins the syntax.
  - **Changes Required**: Each task that implements or verifies an `AC-PLAN-NNN` scenario declares one `- **Acceptance Criteria**:` bullet with comma-separated entries of the form `AC-PLAN-NNN (mode[, test_ref])`, where `mode` is `automated`, `manual`, or `deferred`. An `automated` entry includes the test path as `test_ref` (for example `AC-PLAN-001 (automated, tests/unit/test_core/test_tasks_ledger.py)`). A task with no criterion references omits the bullet.
  - **Integration Surface**: Parsed by `generate_jsonl_from_md`; the ids name `AC-PLAN-NNN` scenarios in this plan's `## Acceptance Contract`.
- **`deviate meso tasks pre`** (`src/deviate/cli/meso.py:939-1037`): GATE — emits the traced rows through the generation path and blocks on invalid links.
  - **Current State**: `_tasks_pre` (line 939) validates the plan contract via `validate_acceptance_contract` at line 1004 (the 005-001 behavior, now at `src/deviate/core/validation.py:162`) and blocks on `PLAN_ACCEPTANCE_CONTRACT_INVALID` / `PLAN_ACCEPTANCE_CONTRACT_MISSING`; it does not itself rewrite rows. `_tasks_post` (line 1040) commits `tasks.md`. The meso flow consumes the generator in `src/deviate/core/tasks_ledger.py`.
  - **Changes Required**: None in this issue. The defensive exclusion in the issue scope (`005-002` §Defensive Exclusions) forbids gate-behavior work here; gate behavior belongs to issues `005-003` and `005-004`. Invalid links fail inside `CriterionLink` construction, so any consumer of `generate_jsonl_from_md` raises before a row is appended.
  - **Integration Surface**: The gate validates the contract whose ids `CriterionLink` references; the integration tier of this issue drives a fixture `tasks.md` through `generate_jsonl_from_md` and `validate_tasks_jsonl`, the exact code path `specs/005-acceptance-gates/data-model.md:190` documents (Flow: Acceptance Traceability, step 3).
- **`tests/unit/test_core/test_tasks_ledger.py`**: TARGET — extend generation tests with link propagation and rejection.
  - **Current State**: `TestGenerateJsonlFromMd` covers basic parsing (ids, issue ids, descriptions, modes, empty files); `TestValidateTasksJsonl` covers row-level rejections including the `extra="forbid"` case.
  - **Changes Required**: Add propagation cases (single link, multiple links, mixed modes, `manual` without `test_ref`, `automated` with `test_ref`, a task without a bullet), rejection cases (malformed `criterion_id`, `automated` link with null `test_ref`, a `verification_mode` outside the literals, an unparseable entry), and the null-never-empty-list assertion. Extend `TestValidateTasksJsonl` with a valid-links row, a malformed-link row, and a legacy row without the field.
  - **Integration Surface**: The functions under test are the same generator and row validator the meso flow consumes.
- **`tests/unit/test_state/test_ledger.py`**: TARGET — extend `TaskRecord` parse tests; legacy rows without the field still parse.
  - **Current State**: `TestTaskRecord` (line 150) covers creation, explicit status/mode, invalid status/mode, extra-field rejection, id format, empty description, and serialization round-trip; `TestAppendTaskRecord` covers append behavior.
  - **Changes Required**: Add a round-trip test with a populated `acceptance_criteria` list, a legacy-row parse test (dict without the field yields `None`), a `CriterionLink` accept/reject set, and an `extra="forbid"` regression that a genuinely unknown field still fails. Keep append-only semantics intact (no rewrite of existing rows).
  - **Integration Surface**: The model under test is the same `TaskRecord` the micro phase runners validate at `src/deviate/cli/micro.py:1154` and later.

## Implementation Strategy

- **Phase 1**: `CriterionLink` model and the additive `TaskRecord` field
  - **Files**: `src/deviate/state/ledger.py`, `tests/unit/test_state/test_ledger.py`
  - **Approach**: Add `CriterionLink(BaseModel)` before `TaskRecord` with `criterion_id`, `verification_mode: Literal["automated", "manual", "deferred"]`, `test_ref: str | None = None`, and `model_config = {"extra": "forbid"}`. Add a `field_validator("criterion_id")` matching `^AC-PLAN-\d{3}$` and a `model_validator(mode="after")` rejecting an `automated` link with a null `test_ref`. Add `acceptance_criteria: list[CriterionLink] | None = None` to `TaskRecord` after `security_profile`, before `model_config`. RED writes the round-trip, legacy-parse, extra-forbid, and `CriterionLink` accept/reject tests first.
  - **Verification**: `uv run pytest tests/unit/test_state/test_ledger.py -v`
- **Phase 2**: Link parsing and propagation in the generator
  - **Files**: `src/deviate/core/tasks_ledger.py`, `tests/unit/test_core/test_tasks_ledger.py`
  - **Approach**: Add `_CRITERIA_LINE_PATTERN` for the `**Acceptance Criteria**:` bullet and `_LINK_PATTERN` for `AC-PLAN-NNN (mode[, test_ref])` entries. Track `current_criteria` inside `generate_jsonl_from_md`, reset per task, and pass it to `_build_task_record`. In `_build_task_record`, parse entries into `CriterionLink` instances; raise a named `ValueError` for unparseable entries and let the `CriterionLink` validators raise `pydantic.ValidationError` for malformed ids, illegal modes, and automated links without `test_ref`. Pass `None` when no links exist. RED writes the propagation and rejection tests first.
  - **Verification**: `uv run pytest tests/unit/test_core/test_tasks_ledger.py -v`
- **Phase 3**: Row-validator coverage and full check bundle
  - **Files**: `tests/unit/test_core/test_tasks_ledger.py`, `tests/unit/test_state/test_ledger.py`
  - **Approach**: Extend `TestValidateTasksJsonl` with valid-link, malformed-link, and legacy-row cases so `validate_tasks_jsonl` behavior is pinned without any structural change to it. Confirm the change touches only `ledger.py`, `tasks_ledger.py`, and their tests; run the full bundle. No CLI command in the new tests hits `_run_pytest`, so no `subprocess.CompletedProcess` mock is needed and the suite stays under 30 seconds.
  - **Verification**: `uv run pytest tests/unit/test_core/test_tasks_ledger.py tests/unit/test_state/test_ledger.py -v`, then `mise run check`

## Data Flow Analysis

1. **Input**: `tasks.md` content is read by `generate_jsonl_from_md` (`src/deviate/core/tasks_ledger.py:16` via `Path.read_text`).
2. **Extraction**: The scanner splits the content into lines; `_TASK_LINE_PATTERN` recognizes `TSK-\d{3}-\d{2}` task bullets; per-task `**Mode**:` and `**Acceptance Criteria**:` bullets accumulate on the current task.
3. **Transformation**: `_build_task_record` converts each `**Acceptance Criteria**:` entry into a `CriterionLink` (`criterion_id`, `verification_mode`, optional `test_ref`) and constructs the `TaskRecord`; invalid entries raise `ValueError` or `pydantic.ValidationError` before any row is produced.
4. **Output**: `TaskRecord.model_dump_json` serializes rows that carry `acceptance_criteria` when links exist and `"acceptance_criteria": null` when they do not; `append_task_record` (`src/deviate/state/ledger.py:181`) appends rows to `specs/**/tasks.jsonl` per the append-only protocol (`specs/constitution.md` §1).
5. **Storage and consumption**: Micro-phase runners parse rows with `TaskRecord.model_validate` (`src/deviate/cli/micro.py:1154,1259,1336,2524,3113,4437,4533,4806`); rows without the field default to `None`, so mixed-version ledgers parse fully. `_read_ledger` (`src/deviate/state/ledger.py:41`) guards malformed JSONL lines with a warning instead of a crash.
6. **Upstream constraint**: The `AC-PLAN-NNN` ids in `tasks.md` name scenarios in the owning slice's validated plan contract (`src/deviate/core/validation.py:162` `validate_acceptance_contract`, mode-enforced by `_validate_verification_mode` at `validation.py:139`); `deviate meso tasks pre` validates that contract at `src/deviate/cli/meso.py:1004` before generation, and this issue consumes the validated contract without re-checking (defensive exclusion).

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `extra="forbid"` rejects older JSONL rows that lack the new field | High | Medium | Declare the field optional with default `None`; pin a legacy-row parse test; the design register mirrors this as `RSK-001` (`specs/005-acceptance-gates/design.md:63`). |
| Ambiguous or drifted `tasks.md` criterion syntax silently drops links | Medium | Medium | Pin the `**Acceptance Criteria**: AC-PLAN-NNN (mode[, test_ref])` syntax in this plan; the generator raises on unparseable entries instead of skipping them. |
| A `criterion_id` that matches `AC-PLAN-\d{3}` but names a criterion absent from the owning plan's contract escapes generation | Medium | Low | Documented boundary: `CriterionLink` validates the id pattern only; contract-level verification belongs to issue `005-001` and the micro/gate issues `005-003`/`005-004` (issue scope §Defensive Exclusions). No plan.md cross-check is added to the generator. |
| Generation-time error messages omit the offending link details | Low | Medium | Pydantic field/model validators pin named messages that include `criterion_id` and mode; tests assert the message substrings. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (reads `tasks.md` via `Path.read_text` — local read only), deserialization (`json.loads` on ledger rows in `_read_ledger`, already guarded by a try/except with a warning), and string fields (`criterion_id` and `test_ref` are plain strings; `test_ref` is never resolved or executed — existence checks are explicitly out of scope per the issue's Edge Cases).

Negative tests: a row with a genuinely unknown field still fails under `extra="forbid"`; a legacy row without the field parses with `acceptance_criteria` equal to `None`; an `automated` link without a `test_ref` fails generation; a `verification_mode` outside the three literals fails generation; an unparseable `**Acceptance Criteria**:` entry fails generation with a named error; a malformed JSONL line is skipped with a warning, never a crash.

Constraints: no new dependencies (stdlib `re` only); no hardcoded secrets; no changes to `src/deviate/core/validation.py`, `src/deviate/cli/micro.py`, `src/deviate/prompts/`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, or `CHANGELOG.md` (defensive exclusions); no subprocess in the new tests; the full suite stays under 30 seconds.

## Integration Points

- **`src/deviate/cli/meso.py:1004`** (`_tasks_pre` contract gate): validates the plan `## Acceptance Contract` via `validate_acceptance_contract` (`src/deviate/core/validation.py:162`) before task generation; the `AC-PLAN-NNN` ids this issue propagates refer to that contract. No change here (gate behavior belongs to issues `005-003`/`005-004`).
- **`src/deviate/cli/micro.py` phase runners** (`TaskRecord.model_validate` at lines 1154, 1259, 1336, 2524, 3113, 4437, 4533, 4806): parse new and legacy task rows; the additive field must not break any runner. `src/deviate/prompts/auto/red.md:64` already instructs RED to trace `{TASK_ID}` to its `AC-PLAN-NNN` references in `tasks.md`.
- **`src/deviate/cli/inspect.py:244`**: reads `tasks.jsonl` for task inspection; rows carrying the new field render without a schema change.
- **`src/deviate/core/validation.py:166`** (`contract_pattern`, `AC-PLAN-\d{3}`) and **`:162`** (`validate_acceptance_contract`): provide and enforce the id vocabulary `CriterionLink` references; this issue consumes the validated contract and does not modify it (defensive exclusion).
- **`specs/005-acceptance-gates/data-model.md`** (`TaskRecord` and `CriterionLink` entity tables, lines 84-110): the authoritative schema this issue implements; `acceptance_criteria` is additive with default `None` and `CriterionLink` embeds per the relationship table (line 77).
- **`src/deviate/prompts/commands/deviate-tasks.md:47`** and **`src/deviate/prompts/auto/tasks.md:70`**: tasks-phase prompts require every task to cite its `AC-PLAN-NNN` scenarios; the new bullet syntax aligns with that requirement (prompt-template alignment itself belongs to issue `005-005`).

## Constitutional Alignment

- **Architecture**: The change sits in the Meso layer (task generation carries criteria traceability into `specs/**/tasks.jsonl` rows) and feeds the Micro layer (phase runners parse the additive field). It implements the `acceptance_criteria` field and `CriterionLink` schema from `specs/005-acceptance-gates/data-model.md` and satisfies the append-only ledger protocol of `specs/constitution.md` §1 — the field is additive, and no existing JSONL line is ever modified.
- **Testing**: pytest unit tests in `tests/unit/test_core/test_tasks_ledger.py` and `tests/unit/test_state/test_ledger.py`; coverage target stays at or above 80%; the new tests are pure unit tests that make no CLI and no git calls, so the full suite stays under the 30-second contract (`AGENTS.md` test-performance pointer). `mise run check` (lint, format-check, types, full suite) is the final gate.
- **Git Isolation**: The orchestrator commits at phase boundaries; this plan's tests use only `tmp_path` fixtures and make zero branch-mutating or `git` calls, so the git-isolation invariants and the append-only ledger protocol remain intact.
- **Product Layer**: `flow_refs` is `[]` per the issue frontmatter, mirrored verbatim in `## Product Layer Anchors`; the release Goal (FLOW-04, subprocess RPC/TUI) is orthogonal and untouched. This plan adds no Product-layer, DeviaTDD setup, skill, flow-authoring, or workflow-ledger work; it only hardens the requested application behavior (task-to-criterion and criterion-to-test traceability) that the meso generation path delivers.