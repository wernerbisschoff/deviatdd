# Implementation Tasks: feat/005-acceptance-gates/001-verification-mode-metadata

## Phase 1: Verification-Mode Contract Gate
**Goal**: `validate_acceptance_contract` enforces exactly one `**Verification Mode**: <automated|manual|deferred>` line per `AC-PLAN-NNN` scenario body. The unit-level contract pins accept, reject, and boundary behavior.

### Tasks

- TSK-005-01: Mode-literal validation in `validate_acceptance_contract` plus unit tests
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_validation.py -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/validation.py`
    - `tests/unit/test_core/test_validation.py`
  - **Rationale**: `validate_acceptance_contract` (validation.py:112) is the single contract gate consumed by `deviate plan post`, `deviate meso tasks pre`, and meso-run resume. US-005-01 requires one Verification Mode per scenario; US-005-02 requires a named error when the mode is missing or illegal. The task implements AC-PLAN-001 (valid literal passes), AC-PLAN-002 (missing/illegal mode produces a named error), AC-PLAN-003 (manual/deferred validate without `test_ref`, case-insensitively), AC-PLAN-004 (duplicate mode lines produce a named error), and AC-PLAN-005 (a valid mode never waives the mandatory clause set). `tests/unit/test_core/test_validation.py` is the unit-level contract for the same function the meso gates consume.
  - **Details**:
    - **Red**: Add `TestVerificationModeValidation` to `tests/unit/test_core/test_validation.py`. Build a shared helper that renders a minimal valid scenario (`Source Outline`, `Upstream Traceability`, `Current-Code Evidence`, `Given`/`When`/`Then`) and injects zero, one, or more mode lines. Cover: accept each literal (`automated`, `manual`, `deferred`); accept a case/whitespace variant (`Deferred`, `  manual  `); accept an all-`deferred` contract; reject a missing mode with `AC-PLAN-001: missing Verification Mode`; reject an illegal literal with `AC-PLAN-001: invalid Verification Mode 'soon'; expected one of automated|manual|deferred`; reject an empty mode value; reject duplicate lines with `AC-PLAN-001: duplicate Verification Mode lines`; fail a dropped mandatory clause even with a valid mode; validate mixed modes across scenarios independently; keep the zero-scenario error `Acceptance Contract must contain at least one AC-PLAN-NNN scenario`. Also retrofit the three existing `TestAcceptanceOwnershipValidation` fixtures (lines 148, 163, 178) with `- **Verification Mode**: automated` so their exact-equality assertions survive the new mandatory check. Run the file: the new mode tests fail.
    - **Green**: In `src/deviate/core/validation.py`, add module-level `_VERIFICATION_MODE_LITERALS = ("automated", "manual", "deferred")` and `_MODE_PATTERN = re.compile(r"\*\*Verification Mode\*\*:\s*([A-Za-z]+)")`. Inside the existing per-scenario loop of `validate_acceptance_contract` (after the Current-Code Evidence check), call `_MODE_PATTERN.findall(scenario_body)`. Append `f"{scenario_id}: missing Verification Mode"` when the list is empty, `f"{scenario_id}: duplicate Verification Mode lines"` when it holds more than one entry, and `f"{scenario_id}: invalid Verification Mode '{value}'; expected one of automated|manual|deferred"` when the single entry, lowercased and whitespace-trimmed, is outside the tuple. Reuse the already-computed `scenario_id`; leave `_validate_scenarios`, `validate_gherkin_syntax`, and the Source Outline / Upstream Traceability / Current-Code Evidence checks untouched.
    - **Refactor**: Run the mode check in the same single per-scenario pass so the function stays linear over the scenario list. Add no new dependencies (stdlib `re` only). Preserve the deterministic error order: Gherkin clause errors first, then per-scenario metadata errors.
    - **Edge Cases**: An empty value (`**Verification Mode**:` with no token) yields no capture and reports the missing-mode error. A non-alphabetic value (`**Verification Mode**: 42`) yields no capture and reports the missing-mode error. A case variant outside the three literals (`AUTOMATEDx`) is rejected. Duplicate identical lines are rejected. A `**Verification Mode**` string inside a quoted example is pinned by an adversarial unit body; the alphabetic capture restricts the match.
    - **Acceptance**: `uv run pytest tests/unit/test_core/test_validation.py -v` passes with the named error strings pinned verbatim in the reject assertions. Existing clause tests still pass. `validate_gherkin_syntax` remains mandatory.

## Phase 2: Meso Fixture Migration
**Goal**: Existing meso test fixtures that feed contracts to the gates adopt the mode line, so the full suite stays green after the mandatory check lands.

### Tasks

- TSK-005-02: Add the Verification Mode line to seeded meso plan fixtures
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_meso/test_meso_orchestration.py tests/unit/test_meso/test_meso_resume.py tests/unit/test_meso/test_plan_structure_injection.py -v`
  - **Estimated Time**: 45 minutes
  - **Flow References**: []
  - **Dependency**: TSK-005-01
  - **Files**:
    - `tests/unit/test_meso/test_meso_orchestration.py`
    - `tests/unit/test_meso/test_meso_resume.py`
    - `tests/unit/test_meso/test_plan_structure_injection.py`
  - **Rationale**: After TSK-005-01, every contract without a mode line fails validation. Three fixture sites would break the suite. `_setup_minimal_workspace` in test_meso_orchestration.py seeds a plan (line 75) that `_resolve_meso_resume_state` validates under `no_setup=True`; without the mode line, `test_no_setup_skips_specify_pre` and `test_no_setup_banner_omits_specify` fail with `MESO_PLAN_INVALID`. `VALID_PLAN` in test_meso_resume.py feeds the same resume path. The fixture plan in test_plan_structure_injection.py (line 253) drives `deviate tasks pre`; without the mode line it fails the `status == "READY"` assertion. All three fixtures are valid-contract fixtures, so they map to AC-PLAN-001 and AC-PLAN-003 (valid contracts with a legal mode pass the gate).
  - **Details**:
    - **Implementation**: Insert `**Verification Mode**: automated` after the `**Current-Code Evidence**: ...` line in each of the three fixture contracts: the seeded plan inside `_setup_minimal_workspace` (test_meso_orchestration.py, after `"**Current-Code Evidence**: `src/example.py:run`\n"`), `VALID_PLAN` (test_meso_resume.py, after `**Current-Code Evidence**: `src/example.py:run``), and the fixture plan in test_plan_structure_injection.py (after `- **Current-Code Evidence**: src/demo.py:run`). Keep the literal lowercase `automated` in every fixture. Do not change any assertion.
    - **Edge Cases**: Do not touch the three `TestAcceptanceOwnershipValidation` fixtures in test_validation.py — TSK-005-01 already retrofits them. Do not touch test_cli/test_meso_contracts.py — its existing `tasks pre` tests write no `plan.md` or write `# Plan` without a contract, which stays on the existing `PLAN_ACCEPTANCE_CONTRACT_MISSING` path with exit code 0.
    - **Acceptance**: All three test files pass unchanged in behavior. The suite stays green under `mise run check` after this phase.

## Phase 3: Gate Integration Regression
**Goal**: The CLI gates block on the new mode errors, and the block is pinned at the integration level.

### Tasks

- TSK-005-03: Gate-level regression tests for mode-less and illegal-mode contracts
  - **Type**: Verification_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `uv run pytest tests/unit/test_cli/test_meso_contracts.py tests/unit/test_meso/test_meso_resume.py -v` then `mise run check`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Dependency**: TSK-005-02
  - **Files**:
    - `tests/unit/test_cli/test_meso_contracts.py`
    - `tests/unit/test_meso/test_meso_resume.py`
  - **Rationale**: US-005-02 requires the operator to see `deviate meso tasks pre` fail with a named error when a scenario lacks a mode or carries an illegal mode. AC-PLAN-002 pins the block at the gate level: status `PLAN_ACCEPTANCE_CONTRACT_INVALID` for `_tasks_pre` and `MESO_PLAN_INVALID` for meso-run resume. AC-PLAN-001 pins the ready path. `test_meso_contracts.py` hosts the `_tasks_pre` contract tests; `test_meso_resume.py` hosts the resume-state tests. No production file changes — `_tasks_pre` (meso.py:1004) and `_resolve_meso_resume_state` (meso.py:1533) already block on any non-empty error list from `validate_acceptance_contract`.
  - **Details**:
    - **Red**: In `tests/unit/test_cli/test_meso_contracts.py`, add `test_tasks_pre_blocks_on_missing_verification_mode`: build the minimal env (session phase `SPECIFY`, issue record with `source_file` `specs/test-epic/issues/ISS-TEST-003.md`), write `specs/test-epic/ISS-TEST-003/plan.md` with one `AC-PLAN-001` scenario that omits the mode line, invoke `runner.invoke(cli, ["tasks", "pre"])`, and assert the extracted contract `status == "PLAN_ACCEPTANCE_CONTRACT_INVALID"` and `missing Verification Mode` in the output. Add a variant with `- **Verification Mode**: soon` asserting `invalid Verification Mode 'soon'; expected one of automated|manual|deferred` in the output. In `tests/unit/test_meso/test_meso_resume.py`, add `test_mode_less_plan_stops_without_overwrite`: build the mode-less plan from `VALID_PLAN` via `VALID_PLAN.replace("**Verification Mode**: automated\n", "")`, run `_meso_run(issue_id="ISS-001-001", no_setup=True)` under `pytest.raises(typer.Exit)`, and assert the plan file is unchanged, `mock_invoke.assert_not_called()`, and `MESO_PLAN_INVALID` plus `missing Verification Mode` appear in `capsys.readouterr().out`.
    - **Green**: No production change. The Phase-1 mode check already emits the named errors, and the existing gates already block on any non-empty error list. Run the two new tests to confirm they pass against the committed validator. Confirm `git status` shows no modification to `src/deviate/cli/meso.py`.
    - **Refactor**: Reuse the existing `_setup_git_repo` and `_setup_minimal_env` helpers in test_meso_contracts.py. Keep the fixture plan minimal. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture wherever a test path reaches it, to keep the suite under 30 seconds.
    - **Edge Cases**: `_tasks_pre` prints the invalid status and embeds it in the JSON contract but does not raise; assert the contract `status` field and the error text, not the exit code. Assert the exact status tokens `PLAN_ACCEPTANCE_CONTRACT_INVALID` and `MESO_PLAN_INVALID` and the exact named error substrings so the error contract stays pinned.
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_meso_contracts.py tests/unit/test_meso/test_meso_resume.py -v` passes. `mise run check` (lint, format-check, types, full suite) exits 0. `src/deviate/cli/meso.py` carries no diff.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (logical dependency order)

**Critical Dependency Chains**:
- TSK-005-01 must precede TSK-005-02 (the fixture migration exists only because the Phase-1 gate makes the mode line mandatory)
- TSK-005-02 must precede TSK-005-03 (TSK-005-03 derives its mode-less resume fixture from the migrated `VALID_PLAN` and both tasks edit test_meso_resume.py)

**Risk Hotspots**:
- The plan's Workstation Mapping does not list `tests/unit/test_meso/test_meso_orchestration.py` or `tests/unit/test_meso/test_plan_structure_injection.py`, yet both seed contracts that fail validation after the gate lands. TSK-005-02 covers this gap; without it, `mise run check` fails.
- `_tasks_pre` does not raise on an invalid contract status; it prints the status and embeds it in the JSON contract with exit code 0. Integration tests must assert the contract `status` field, not the process exit code.
- The three existing exact-equality assertions in `TestAcceptanceOwnershipValidation` break unless their fixtures gain the mode line in the same commit as the validator — TSK-005-01 bundles both.
- The regex may capture a non-mode occurrence of `**Verification Mode**` in a quoted example; the alphabetic literal capture and adversarial unit bodies pin the behavior.

**Merge Conflict Boundaries**:
- `tests/unit/test_meso/test_meso_resume.py` is touched by TSK-005-02 (edits `VALID_PLAN`) and TSK-005-03 (adds a new test method). The edits do not overlap; the tasks run sequentially.
- `tests/unit/test_core/test_validation.py` is touched only by TSK-005-01.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/005-acceptance-gates/001-verification-mode-metadata/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
