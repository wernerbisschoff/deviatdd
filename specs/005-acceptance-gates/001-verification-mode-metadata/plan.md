## Plan Summary

- **Issue**: 005-001 — Acceptance Contract Verification-Mode Metadata
- **Implementation Strategy**: Extend `validate_acceptance_contract` in `src/deviate/core/validation.py` so every `AC-PLAN-NNN` scenario body must carry exactly one `**Verification Mode**: <automated|manual|deferred>` line. The mode check runs in the existing single per-scenario pass, appends named errors with the scenario id prefix, and reuses the scenario extraction machinery unchanged. `deviate plan post`, `deviate meso tasks pre`, and `deviate meso run` resume already block on any error list from this function, so no CLI change is needed — the new errors flow through the existing gates.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-3 hours

## Product Layer Anchors

- **Flow References**: []
- **Source**: `specs/005-acceptance-gates/issues/001-verification-mode-metadata.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (subprocess RPC framing, event adapter, Rich TUI renderer capped at 10 lines). This issue is orthogonal: it hardens the meso contract gate, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (existing `deviate` CLI component — this issue extends its meso orchestration validation surface; the `## Components` table lists no component that owns `src/deviate/core/validation.py`)

## Acceptance Contract

**Scenario AC-PLAN-001: A valid verification-mode literal passes contract validation**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-005-01`, `US-005-02`, `FR-005-01`, `AC-005-01-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:112`
- **Given**: a `plan.md` whose `## Acceptance Contract` has one `AC-PLAN-NNN` scenario that carries a Verification Mode line with the value `automated` and all mandatory clauses
- **When**: `validate_acceptance_contract` runs on the content and `deviate meso tasks pre` runs afterward
- **Then**: the function returns an empty error list and `deviate meso tasks pre` reports `READY` without a validation error
- **Verification Mode**: automated

**Scenario AC-PLAN-002: A missing or illegal verification mode produces a named error and blocks tasks pre**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-005-02`, `FR-005-01`, `AC-005-01-01`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:1004`
- **Given**: a `plan.md` whose contract scenario omits the Verification Mode line, or carries a mode value outside `automated|manual|deferred`
- **When**: `deviate meso tasks pre` validates the contract
- **Then**: validation reports a named error prefixed with the scenario id and `deviate meso tasks pre` blocks with `PLAN_ACCEPTANCE_CONTRACT_INVALID`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Manual and deferred modes validate without a test_ref, matched case-insensitively**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-005-01`, `FR-005-01`, `AC-005-01-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:116`
- **Given**: a contract scenario that carries a mode line with the value `Deferred` (a case variant) or with the value `manual`, and no `test_ref` in the body
- **When**: `validate_acceptance_contract` runs on the content
- **Then**: both modes validate against the three literals without any `test_ref` requirement
- **Verification Mode**: automated

**Scenario AC-PLAN-004: A repeated verification-mode line produces a named error instead of silent overwrite**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-005-01`, `FR-005-01`, `AC-005-01-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:123`
- **Given**: a contract scenario whose body carries two Verification Mode lines with different values
- **When**: `validate_acceptance_contract` runs on the content
- **Then**: validation reports one named duplicate-mode error and never silently picks the first or last occurrence
- **Verification Mode**: automated

**Scenario AC-PLAN-005: A valid verification mode does not waive the mandatory clause set**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-005-01`, `FR-005-01`, `AC-005-01-02`
- **Current-Code Evidence**: `src/deviate/core/validation.py:127`
- **Given**: a contract scenario that carries a valid Verification Mode line with the value `automated` but omits one of Source Outline, Upstream Traceability, Current-Code Evidence, or Given/When/Then
- **When**: `validate_acceptance_contract` runs on the content
- **Then**: validation fails on the missing clause with or without the mode line present
- **Verification Mode**: automated

## Workstation Mapping

- **`src/deviate/core/validation.py:112`**: MODIFY — `validate_acceptance_contract` accepts one `**Verification Mode**: <automated|manual|deferred>` line per `AC-PLAN-NNN` scenario body and validates the mode literal.
  - **Current State**: The function extracts the `## Acceptance Contract` body via `extract_section_body` (line 64), iterates scenario matches from `contract_pattern` (lines 116-118), and per scenario checks Source Outline (line 127), Upstream Traceability (line 132), and Current-Code Evidence (line 134). `_validate_scenarios` (line 79) already enforces Given/When/Then. No mode awareness exists.
  - **Changes Required**: Add a module-level `_VERIFICATION_MODE_LITERALS` tuple (`"automated"`, `"manual"`, `"deferred"`) and a `_MODE_PATTERN` regex that captures the literal after `**Verification Mode**:`. Inside the existing per-scenario loop, collect mode-line captures from `scenario_body`; append `"{scenario_id}: missing Verification Mode"` when none, `"{scenario_id}: duplicate Verification Mode lines"` when more than one, and `"{scenario_id}: invalid Verification Mode '<value>'; expected one of automated|manual|deferred"` when the single captured literal (lowercased, whitespace-trimmed) is outside the tuple. Keep `validate_gherkin_syntax` mandatory and the existing clause checks untouched.
  - **Integration Surface**: Consumed by `deviate plan post` (`src/deviate/cli/meso.py:844`), `deviate meso tasks pre` (`src/deviate/cli/meso.py:1004`), and meso-run resume (`src/deviate/cli/meso.py:1533`). `specs/005-acceptance-gates/data-model.md:68` declares the `verification_mode` attribute invariant (one per scenario).

- **`src/deviate/core/validation.py:116-118`**: REFERENCE — `contract_pattern` extracts each `AC-PLAN-NNN` scenario header; the mode check reuses the same per-scenario span between consecutive headers.
  - **Current State**: `contract_pattern` compiles inside `validate_acceptance_contract`; the loop already computes `start`/`end` boundaries per scenario.
  - **Changes Required**: None — reuse the existing iteration for the mode check so the pass stays linear over the scenario list.
  - **Integration Surface**: Same `scenario_body` span feeds the clause checks and the new mode check.

- **`src/deviate/core/validation.py:79`** (`_validate_scenarios`) and **`:93-97`** (`validate_gherkin_syntax`): REFERENCE — the extraction machinery and the Given/When/Then gate stay mandatory.
  - **Current State**: `_validate_scenarios` appends `"{label}: missing '{clause}'"` per missing Gherkin clause; `validate_gherkin_syntax` delegates to it.
  - **Changes Required**: None. The mode check adds to the existing validation, never replaces it.
  - **Integration Surface**: Error-list aggregation order stays deterministic — Gherkin clause errors then per-scenario metadata errors.

- **`src/deviate/cli/meso.py:939,1004`**: GATE — `_tasks_pre` blocks on any validation error emitted by `validate_acceptance_contract` (via `deviate meso tasks pre`).
  - **Current State**: Line 1004 calls `validate_acceptance_contract` on `plan.md` content; any non-empty error list maps to status `PLAN_ACCEPTANCE_CONTRACT_MISSING` (exact single error) or `PLAN_ACCEPTANCE_CONTRACT_INVALID` and prints the errors.
  - **Changes Required**: None — new mode errors surface automatically through the existing block.
  - **Integration Surface**: `_plan_post` (line 844) and `_resolve_meso_resume_state` (line 1533, status `MESO_PLAN_INVALID`) call the same function and need no change.

- **`specs/005-acceptance-gates/001-verification-mode-metadata/plan.md`**: TARGET — this plan's `## Acceptance Contract` scenarios carry `**Verification Mode**: automated` lines, so the contract stays valid under the new validator when meso gates re-run.
  - **Current State**: New file; no prior contract exists in-repo (no existing `plan.md` carries an `## Acceptance Contract` section — a grep across `specs/` confirms).
  - **Changes Required**: The five `AC-PLAN-NNN` scenarios above each carry exactly one mode line.
  - **Integration Surface**: Validated by `deviate plan post` and `deviate meso tasks pre`; consumed by `deviate meso tasks` for task generation.

- **`tests/test_core/test_validation.py`**: TARGET — extend the acceptance-contract tests with Verification Mode acceptance, rejection, and boundary cases.
  - **Current State**: `TestAcceptanceOwnershipValidation` (line 125) covers the mandatory clause set: missing `When` (line 147), missing Source Outline (line 162), missing Upstream/Evidence (line 177).
  - **Changes Required**: Add a `TestVerificationModeValidation` class covering: accept each literal, accept case variants and surrounding whitespace, accept an all-`deferred` contract, reject a missing mode, reject an illegal value, reject an empty value, reject duplicate mode lines, reject a dropped clause despite a valid mode, validate mixed modes independently, and keep the zero-scenario missing-contract error unchanged.
  - **Integration Surface**: The function under test is the same `validate_acceptance_contract` the meso gates consume.

- **`tests/test_cli/test_meso_contracts.py`** and **`tests/test_meso/test_meso_resume.py`**: TARGET — extend gate-level integration coverage with a fixture `plan.md` that carries an invalid mode.
  - **Current State**: `test_tasks_pre_contract_has_required_fields` (line 105) pins the `tasks_pre` contract shape; `test_invalid_existing_plan_stops_without_overwrite` (line 80) asserts `MESO_PLAN_INVALID` for a contract-less plan.
  - **Changes Required**: Add one test that writes a fixture `plan.md` whose scenario omits the mode line (or uses an illegal literal) and asserts `_tasks_pre` reports `PLAN_ACCEPTANCE_CONTRACT_INVALID` with the named error; extend the resume test to assert `MESO_PLAN_INVALID` for a mode-less contract.
  - **Integration Surface**: `_tasks_pre` and `_resolve_meso_resume_state` — the same gate functions operators invoke.

## Implementation Strategy

- **Phase 1**: Mode-validation logic in `validate_acceptance_contract`
  - **Files**: `src/deviate/core/validation.py`
  - **Approach**: Add `_VERIFICATION_MODE_LITERALS = ("automated", "manual", "deferred")` and `_MODE_PATTERN = re.compile(r"\*\*Verification Mode\*\*:\s*([A-Za-z]+)")` at module level. In the existing per-scenario loop, call `_MODE_PATTERN.findall(scenario_body)`; enforce exactly one capture; compare the lowercased literal against the tuple. Run the check in the same single pass so the function stays linear over the scenario list.
  - **Verification**: `uv run pytest tests/test_core/test_validation.py -v` — existing clause tests still pass; new mode tests pass.

- **Phase 2**: Unit tests for accept, reject, and boundary behavior
  - **Files**: `tests/test_core/test_validation.py`
  - **Approach**: Add `TestVerificationModeValidation` with the cases listed in the Workstation Mapping entry: per-literal acceptance, case-insensitive and whitespace-tolerant matching, all-`deferred` contract passes, missing/illegal/empty value rejection, duplicate-line rejection, mandatory-clause enforcement with a valid mode, mixed-mode independence, and unchanged zero-scenario behavior. Pin the named error strings in the reject assertions so the error contract is explicit.
  - **Verification**: `uv run pytest tests/test_core/test_validation.py -v`

- **Phase 3**: Gate integration regression and full check bundle
  - **Files**: `tests/test_cli/test_meso_contracts.py`, `tests/test_meso/test_meso_resume.py`
  - **Approach**: Extend `_tasks_pre` and meso-run resume tests with fixture contracts that omit the mode line or use an illegal literal; assert the named status (`PLAN_ACCEPTANCE_CONTRACT_INVALID` / `MESO_PLAN_INVALID`) and error text. Confirm no `src/deviate/cli/meso.py` change is required — the existing gates already block on any non-empty error list. Mock `deviate.cli.micro._run_pytest` where any test path reaches it to keep the suite under 30 seconds.
  - **Verification**: `uv run pytest tests/test_cli/test_meso_contracts.py tests/test_meso/test_meso_resume.py -v`, then `mise run check` (lint, format-check, types, full suite).

## Data Flow Analysis

1. **Input**: `plan.md` content is read by `_plan_post` (`src/deviate/cli/meso.py:840`), `_tasks_pre` (`src/deviate/cli/meso.py:1004`), and `_resolve_meso_resume_state` (`src/deviate/cli/meso.py:1531`).
2. **Extraction**: `validate_acceptance_contract` (validation.py:112) calls `extract_section_body` (validation.py:64) to isolate the `## Acceptance Contract` section; a missing section returns the single error `PLAN_ACCEPTANCE_CONTRACT_MISSING`.
3. **Scenario split**: `contract_pattern` (validation.py:116) finds `AC-PLAN-NNN` headers; each scenario body is the span from one header's closing `**` to the next header's start.
4. **Per-scenario checks**: `_validate_scenarios` enforces Given/When/Then; the loop enforces Source Outline, Upstream Traceability, and Current-Code Evidence; the new check enforces exactly one case-insensitive Verification Mode literal. Errors accumulate with the scenario id prefix.
5. **Gate routing**: A non-empty error list maps to `PLAN_ACCEPTANCE_CONTRACT_INVALID` in `_plan_post` and `_tasks_pre`, and to `MESO_PLAN_INVALID` in meso-run resume; both print the joined errors and block. An empty list lets `_plan_post` commit `plan.md` and transition the session PLAN → TASKS, and lets `_tasks_pre` proceed to task generation.
6. **No persistence**: The mode lives only in the `plan.md` text; no ledger row, no `.deviate/` store, and no network call carries it in this issue.

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |
| Existing contracts without a mode line now fail validation | Medium | Low | The mode line is intentionally mandatory; no in-repo `plan.md` carries an `## Acceptance Contract` today (verified by grep), so nothing existing breaks. This plan and the unit fixtures adopt the mode line in the same commit. |
| Regex captures a non-mode occurrence of `**Verification Mode**` in a quoted example | Low | Medium | The capture restricts to an alphabetic literal token; unit tests feed adversarial bodies (quoted examples, inline code) to pin the behavior. |
| Duplicate mode lines resolved nondeterministically | Low | Low | Fixed rule: more than one mode line in a body yields a single named duplicate error; the validator never silently picks an occurrence. |
| `_plan_post` and `_tasks_pre` diverge on validation | Medium | Low | Both gates and meso-run resume call the same `validate_acceptance_contract`; the function is the single source of truth for contract errors. |
| Performance regression in the validation pass | Low | Low | The mode check reuses the existing single per-scenario loop; no new dependencies and no second content scan. |

## Security Profile

Risk surfaces: file paths (reads `plan.md` from the worktree), regex processing of untrusted markdown content. No auth, secrets, PII, outbound HTTP, deserialization, subprocess, SQL/ORM, or eval surfaces — the change is a pure string-validation extension over the existing contract gate.

Negative tests: an illegal mode literal (e.g. `soon`) is rejected with a named error; an empty mode value is rejected; a missing mode line is rejected; duplicate mode lines are rejected; a case variant outside the three literals is rejected; a scenario with a valid mode but a dropped mandatory clause still fails; a contract with zero scenarios keeps the existing missing-contract error; mixed modes across scenarios validate independently.

Constraints: no new dependencies (stdlib `re` only); no hardcoded secrets; no ledger writes, no `.deviate/` store, no network calls; `validate_gherkin_syntax` stays mandatory; the validation pass stays linear over the scenario list.

## Integration Points

- **`validate_acceptance_contract`** (`src/deviate/core/validation.py:112`): the shared contract gate. `_plan_post` (`src/deviate/cli/meso.py:844`), `_tasks_pre` (`src/deviate/cli/meso.py:1004`), and `_resolve_meso_resume_state` (`src/deviate/cli/meso.py:1533`) consume its error list and block on any non-empty result — no signature change.
- **`contract_pattern`** (`src/deviate/core/validation.py:116`): the scenario-boundary machinery; the mode check operates on the same per-scenario span as the existing clause checks.
- **`_validate_scenarios` / `validate_gherkin_syntax`** (`src/deviate/core/validation.py:79,93`): unchanged Gherkin gate; the mode check is additive.
- **`specs/005-acceptance-gates/data-model.md:68`**: documents the `verification_mode` attribute invariant (one per scenario) that this issue makes enforceable.
- **`tests/test_core/test_validation.py`**: the unit-level contract that pins accept, reject, and boundary behavior; the same fixtures later feed issue 005-002's `CriterionLink` propagation.

## Constitutional Alignment

- **Architecture**: Aligns with the three-layer model — the change lives entirely in the meso validation layer that owns the `plan.md` acceptance contract. Macro artifacts (PRD, data-model) declared the mode field; this issue makes the contract gate enforce it. No layer is skipped, and no Product-layer work is introduced.
- **Testing**: pytest unit tests in `tests/test_core/test_validation.py` plus gate integration tests in `tests/test_cli/test_meso_contracts.py` and `tests/test_meso/test_meso_resume.py`. Coverage target stays ≥ 80%; the full suite stays under 30 seconds; any test path reaching `deviate.cli.micro._run_pytest` mocks it per the execution contract.
- **Git Isolation**: `validate_acceptance_contract` is pure and read-only — no ledger writes, no `.deviate/` session mutation, no branch or worktree mutation. Changes commit through the standard phase-commit cycle with the `TSK-005-01`-scoped conventional message format.
- **Product Layer**: `flow_refs` is empty, so no user-visible flow is referenced or altered. The mode metadata strengthens the `plan.md` contract that downstream meso and micro phases consume, preserving the existing workflow behavior named in the release context (FLOW-04 RPC streaming) untouched. This section is traceability context only.
