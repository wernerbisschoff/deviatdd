---
title: Per-Task Security Profile + Structured JUDGE Security Checks
labels: ["feature", "ISS-004", "P1"]
source_file: specs/004-per-task-security-profile/prd.md
blocked_by: []
coordinates_with: []
issue_id: ISS-004-001
epic_id: ISS-004
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 004 — Per-Phase Security Hardening
- **Local Issue File**: `specs/004-per-task-security-profile/issues/001-security-profile-and-judge-checks.md`
- **Workstation Paths**:
  - `src/deviate/state/ledger.py` — MODIFY: add `SecurityProfile` Pydantic model + `TaskRecord.security_profile` field
  - `src/deviate/prompts/commands/deviate-plan.md` — MODIFY: add `## Security Profile` section template (prose-only, recommendation)
  - `src/deviate/prompts/auto/judge.md` — MODIFY: add `security_checks: {pass | fail | warn}` to the YAML manifest schema; instruct the agent to populate it as a *required* field based on the existing flat security scan plus any `security_profile.body` content
  - `tests/test_state/test_security_profile.py` — NEW: 5 ledger round-trip tests
  - `tests/test_micro/test_judge_prompt.py` — APPEND: 1 prompt-assembly test asserting `security_checks` is required + vocabulary pinned
  - `CHANGELOG.md` — MODIFY: Unreleased bullet

## [THE_PROBLEM_CONTRACT]

**User Journey**: A planner writes `plan.md` with a `## Security Profile` section describing the risk surfaces this task touches and the negative tests the planner expects RED to write. The planner (or a follow-up TASKS-phase emission) populates the optional `security_profile` field on the `TaskRecord`. When the JUDGE phase runs, the agent reads the `security_profile.body` as supplementary context and emits a structured `security_checks: {pass | fail | warn}` field on the verdict manifest. The `security_checks` field is mandatory — its absence on the manifest is a Judge rejection, not a soft warning.

**System Response**: `SecurityProfile` is a single-field Pydantic model (`body: str | None`) with `model_config = {"extra": "forbid"}` matching the existing ledger family pattern. `TaskRecord.security_profile: SecurityProfile | None = None` defaults to `None` for forward compatibility with existing `tasks.jsonl` records. The `deviate-plan.md` template adds a `## Security Profile` section as a recommendation (no enforcement). The `auto/judge.md` prompt instructs the agent to populate `security_checks` based on the existing flat security scan (secrets, injection, deserialization, path traversal, log leakage) and any `security_profile.body` content. The `security_checks` field is documented as a hard requirement on the manifest schema.

## [SCOPE_BOUNDARIES]

### Hard Inclusions

- `SecurityProfile` Pydantic model with `body: str | None = None` field
- `TaskRecord.security_profile: SecurityProfile | None = None` field
- `## Security Profile` plan template (prose-only, recommendation)
- `security_checks: {pass | fail | warn}` field on the JUDGE manifest schema
- Mandatory-instruction for the JUDGE agent to populate `security_checks`
- 6 tests covering ledger round-trip + prompt schema

### Hard Exclusions

- **No TASKS-phase emission** of `security_profile` from `plan.md` (LLM-inference reliability risk; deferred)
- **No structured fields** on `SecurityProfile` (`risk_surfaces`, `negative_tests`, `green_constraints`)
- **No Gate 2b** (`--security-sign-off`, `--accept-low-risk`)
- **No `PreconditionFailedError`** or micro pre-script `MISSING_SECURITY_PROFILE`
- **No `deviate review pre` cross-task aggregation**
- **No Constitution v0.8.0** amendment
- **No spec updates** to `DeviaTDD-api.md` or `DeviaTDD-architecture.md` (the JUDGE prompt change is internal to the auto-prompt template, not a public API change)
- **No `.mise.toml` wiring**
- **No migration story** — the field is optional, no existing plan breaks

### Out of Scope / Future Work

The following is **explicitly deferred** to follow-up PRs to preserve the simple-scope contract of this PR:

1. **TASKS-phase emission of `security_profile` from `plan.md`** — the LLM-inference reliability risk is load-bearing for the contract; deferring until the model is in place and the emission prompt can be tuned against actual planner output. The `security_profile` field is currently populated manually or via follow-up PR.
2. **Structured `SecurityProfile` fields** (`risk_surfaces: list[str]`, `negative_tests: list[str]`, `green_constraints: list[str]`) — the prose blob is documentation-grade; structured fields are contract-grade. Upgrade only when the JUDGE prompt can mechanically walk the structure.
3. **Gate 2b enforcement** (`--security-sign-off`, `--accept-low-risk` flags) — pre-script status hardening for the post-`deviate-plan` security review.
4. **`PreconditionFailedError(PhaseFailedError)`** — typed precondition failure for micro-layer pre-script checks.
5. **`deviate review pre` cross-task aggregation** — Domain 1 expansion to consume `security_profiles` from `tasks.jsonl` and surface cross-task risk surfaces, supply-chain audit, and random re-verification.
6. **Constitution v0.8.0 amendment** — codifying Gate 2b, the `SecurityProfile` field as append-only, and the review consumption pattern.
7. **Spec updates** to `DeviaTDD-api.md` and `DeviaTDD-architecture.md` — the manifest schema change is internal to the auto-prompt template; spec updates land when the public API changes (Gate 2b, emission contract, etc.).

## [ACCEPTANCE_CRITERIA]

### Ledger Model (5 tests)

1. `test_security_profile_default_construction` — `SecurityProfile()` with no args yields `body=None`.
2. `test_security_profile_round_trip_with_body` — construct with a body string, serialize via `.model_dump_json()`, deserialize via `SecurityProfile.model_validate_json()`, assert equality.
3. `test_task_record_parses_legacy_row_without_security_profile` — parse a JSON dict representing a pre-PR-1 task record (no `security_profile` field). Asserts `task_record.security_profile is None`.
4. `test_task_record_round_trips_with_security_profile` — construct `TaskRecord` with `security_profile=SecurityProfile(body="...")`, serialize, deserialize, assert the body survives.
5. `test_security_profile_follows_ledger_extra_forbid_contract` — assert `SecurityProfile.model_config["extra"] == "forbid"`. Pins the sibling-models contract (IssueRecord, FlowRecord, FlowEvent, FlowCoverage, RollbackSnapshot, LedgerFilter, AdhocRecord, FlowConfirmationResult all use `extra="forbid"`).

### JUDGE Prompt (1 test)

6. `test_judge_prompt_declares_security_checks_as_required_field` — call `_build_auto_prompt("judge", task, root)` directly with a fixture task. Parse the rendered prompt for the manifest schema block. Assert:
   - The schema block names `security_checks` as a field
   - The schema block enumerates allowed values explicitly as `pass | fail | warn` (not `true | false`, not `ok | warn`, not `green | red`)
   - The instruction block tells the agent that `security_checks` is mandatory — absence on the manifest is a rejection, not a soft warning

### CHANGELOG

- One bullet under `[Unreleased]` summarizing the addition.

## [DESIGN_DECISIONS]

### Why a single-field `body: str | None` instead of structured fields

The structured `risk_surfaces` / `negative_tests` / `green_constraints` shape is contract-grade; the prose `body` is documentation-grade. The user asked for "simple changes." The minimal contract is the `security_checks` manifest field on the JUDGE output. The `security_profile.body` is supplementary context for the JUDGE agent to read. The structured fields are a future PR when the JUDGE prompt can mechanically walk the structure.

### Why no TASKS-phase emission

If the LLM mis-emits `security_profile` (e.g., malformed `risk_surfaces` if the field were structured), Pydantic validation fails at `TaskRecord.model_validate()` time. The TASKS phase would reject the task record. The mitigation is prompt-instruction clarity + `--force`, which is the canonical TDD anti-pattern: shipping a feature whose primary failure mode is "you can't use it without bypassing validation." Defer the emission until the prompt can be tuned against actual planner output.

### Why no Constitution v0.8.0

The field is optional; the prompt template is internal; the public API doesn't change. No governance section is modified. Constitution bump lands with Gate 2b in a follow-up PR.

### Why no spec updates

`DeviaTDD-api.md` and `DeviaTDD-architecture.md` describe the public API (CLI commands, manifest schemas, hitl gates). The new `security_checks` field is an internal change to the auto-prompt template's YAML schema. Spec updates land when the public API changes (Gate 2b, emission contract, etc.).

## [TASK_BREAKDOWN]

### TSK-004-001-01 — RED: 6 failing tests

Create `tests/test_state/test_security_profile.py` with 5 tests; append `test_judge_prompt_declares_security_checks_as_required_field` to `tests/test_micro/test_judge_prompt.py`. Tests run → all 6 fail with concrete errors (`ImportError: cannot import name 'SecurityProfile'`, `KeyError: 'security_checks'` in the rendered prompt).

### TSK-004-001-01 — GREEN: ledger model + field

Add `SecurityProfile` Pydantic model and `TaskRecord.security_profile` field to `src/deviate/state/ledger.py`. Tests 1–5 pass.

### TSK-004-001-02 — RED: prompt-assembly test

Already in TSK-004-001-01's RED commit. After GREEN-1, only test 6 still fails.

### TSK-004-001-02 — GREEN: JUDGE prompt changes

Modify `src/deviate/prompts/auto/judge.md` to add `security_checks: {pass | fail | warn}` to the manifest schema, with instruction that the field is mandatory. Test 6 passes.

### TSK-004-001-03 — Plan template

Modify `src/deviate/prompts/commands/deviate-plan.md` to add the `## Security Profile` section template. No test required (template is guidance, not contract).

### TSK-004-001-04 — CHANGELOG

Add one bullet under `[Unreleased]`.

### REFACTOR

None — the changes are small enough that no refactor is needed.

## [MIGRATION_NOTE]

None required. The `security_profile` field defaults to `None` for backward compatibility. Existing `tasks.jsonl` records parse cleanly. The JUDGE prompt's existing flat security scan is unchanged. The `security_checks` field is additive on the manifest schema.

## [OUT_OF_BAND_DEPENDENCIES]

None. No external libraries, no infrastructure changes, no schema migrations.

## [RELATED_DOCS]

- `specs/DeviaTDD-api.md` — not updated in this PR (deferred)
- `specs/DeviaTDD-architecture.md` — not updated in this PR (deferred)
- `specs/constitution.md` — not updated in this PR (deferred)
- `CHANGELOG.md` — updated with one Unreleased bullet
