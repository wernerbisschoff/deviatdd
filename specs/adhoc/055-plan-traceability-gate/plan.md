## Plan Summary
- **Issue**: ISS-ADH-055 — Validate issue traceability before PLAN starts with legacy repair
- **Implementation Strategy**: Add a fail-fast traceability gate to `_plan_pre` in `meso.py`, backed by a shared validator in `validation.py`, plus a repair helper that restores missing sections; align shard and adhoc templates on the required identifiers.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Reject untraceable issue with named missing fields**
- **Source Outline**: `AO-055-01`
- **Upstream Traceability**: `US-055-01`, `FR-ADHOC-055`, `AC-ADHOC-055-01`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_plan_pre`
- **Given**: An issue file lacks stories, tracing, or acceptance outlines
- **When**: The operator runs `plan pre` against that issue
- **Then**: The contract reports NOT_READY and names each missing field plus the repair step
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Pass traceable issue with READY contract**
- **Source Outline**: `AO-055-01`
- **Upstream Traceability**: `US-055-01`, `FR-ADHOC-055`, `AC-ADHOC-055-01`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_plan_pre`
- **Given**: An issue file carries stories, tracing, and acceptance outlines with AO tokens
- **When**: The operator runs `plan pre` against that issue
- **Then**: The contract reports READY with the resolved spec path and plan target
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Name exactly the missing subset on partial issues**
- **Source Outline**: `AO-055-01`
- **Upstream Traceability**: `US-055-01`, `FR-ADHOC-055`, `AC-ADHOC-055-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:validate_macro_contract`
- **Given**: An issue file carries stories but omits acceptance criteria tokens
- **When**: The operator runs `plan pre` against that issue
- **Then**: The diagnostic names only the absent token family, not a blanket failure
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Repair legacy issue then pass the gate**
- **Source Outline**: `AO-055-02`
- **Upstream Traceability**: `US-055-02`, `FR-ADHOC-055`, `AC-ADHOC-055-02`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_plan_pre`
- **Given**: A legacy issue file lacks the traceability sections
- **When**: The operator runs the repair path then reruns `plan pre`
- **Then**: The repaired issue carries stories, tracing, and outlines and the contract reports READY
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Reject incomplete repair with the gap named**
- **Source Outline**: `AO-055-02`
- **Upstream Traceability**: `US-055-02`, `FR-ADHOC-055`, `AC-ADHOC-055-02`
- **Current-Code Evidence**: `src/deviate/core/validation.py:validate_macro_contract`
- **Given**: A repaired issue still skips one required section
- **When**: The operator reruns `plan pre` against that issue
- **Then**: The contract reports NOT_READY and names the remaining gap
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Pass complete legacy issue without repair**
- **Source Outline**: `AO-055-02`
- **Upstream Traceability**: `US-055-02`, `FR-ADHOC-055`, `AC-ADHOC-055-02`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_plan_pre`
- **Given**: A legacy issue already carries stories, tracing, and outlines
- **When**: The operator runs `plan pre` against that issue
- **Then**: The contract reports READY without requiring the repair path
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/meso.py**: Owns the `plan pre` gate — add the traceability check and repair entry point
  - **Current State**: `_plan_pre` resolves the issue file and emits READY or ISSUE_NOT_FOUND with no traceability validation
  - **Changes Required**: Call a shared traceability validator on the issue body; return NOT_READY naming missing fields plus the repair step; expose the repair path
  - **Integration Surface**: `_find_issue_file`, `validate_acceptance_contract`, `_tasks_pre` plan prerequisite, `deviate meso run` orchestration
- **src/deviate/core/validation.py**: Owns reusable contract validation — add the issue traceability validator
  - **Current State**: `validate_macro_contract` checks PRD/shard sections; `_validate_prd_traceability` lives in `meso.py` as a PRD-only helper
  - **Changes Required**: Add `validate_issue_traceability` checking stories, tracing, and outline sections plus AO tokens; mirror the PRD FAIL-plus-detail shape
  - **Integration Surface**: Called by `_plan_pre`; unit-tested in `tests/unit/test_core/test_validation.py`
- **src/deviate/prompts/auto/plan.md**: Declares the PLAN contract inputs — document the gate diagnostic
  - **Current State**: Lists contract context fields with no NOT_READY diagnostic description
  - **Changes Required**: Name the NOT_READY diagnostic and the repair step in the pre-flight step
  - **Integration Surface**: Read by the PLAN agent; no code callers
- **src/deviate/prompts/auto/shard.md**: Authors shard issues — align required identifiers with the gate
  - **Current State**: Requires `User Stories Ledger` plus `Acceptance Outline` with AO tokens per issue
  - **Changes Required**: Confirm the `Upstream Requirement Tracing` section tokens the gate checks; change only wording that drifts from the gate
  - **Integration Surface**: Read by the SHARD agent; validated by `validate_macro_contract`
- **src/deviate/prompts/commands/deviate-adhoc.md**: Authors adhoc issues — align required identifiers with the gate
  - **Current State**: Requires stories, outlines, edge cases, and performance sections in shard canonical order
  - **Changes Required**: Confirm the same section and token names the gate checks; change only wording that drifts
  - **Integration Surface**: Read by the adhoc flow; shares the gate validator

## Implementation Strategy
- **Phase 1**: Gate plus validator with failing contract tests
  - **Files**: `src/deviate/core/validation.py`, `src/deviate/cli/meso.py`, `tests/unit/test_core/test_validation.py`, `tests/unit/test_cli/test_meso_contracts.py`
  - **Approach**: Write failing tests for READY, NOT_READY, and partial-subset paths first; implement `validate_issue_traceability`; wire it into `_plan_pre` to emit NOT_READY with missing fields and the repair step
  - **Verification**: Run `mise run test` for the touched suites; run `plan pre` against a legacy fixture to confirm NOT_READY names the gap
- **Phase 2**: Repair path plus template agreement
  - **Files**: `src/deviate/cli/meso.py`, `src/deviate/prompts/auto/shard.md`, `src/deviate/prompts/commands/deviate-adhoc.md`, `src/deviate/prompts/auto/plan.md`
  - **Approach**: Implement the repair helper that restores missing sections and re-passes the gate; adjust template wording only where identifiers drift
  - **Verification**: Run `plan pre` against a legacy fixture to confirm NOT_READY, repair, then READY; run template validation tests
- **Phase 3**: Spec plus CHANGELOG in the same commit
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Document the gate status values, the repair command, and the template contract in both specs; append one CHANGELOG bullet under `[Unreleased]`
  - **Verification**: Confirm `mise run check` passes and the commit contains code plus spec plus CHANGELOG

## Data Flow Analysis
- `plan pre` reads the issue file body from the path resolved by `_find_issue_file`. The body passes through `validate_issue_traceability`, which extracts the stories, tracing, and outline sections plus AO tokens. The validator returns a READY contract or a NOT_READY diagnostic listing each missing field and the repair step. The repair helper writes the missing sections back to the issue file. A rerun of `plan pre` revalidates the restored body and emits READY with spec path and plan target.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gate rejects currently passing traceable issues | High | Medium | Pin READY happy-path tests on the existing issue format first |
| Repair helper overwrites author content | High | Low | Repair only inserts absent sections, never edits present text |
| Template wording drifts from gate checks | Medium | Medium | Gate checks section names only, not prose; keep template edits minimal |
| Scope creeps into Micro RED/GREEN behavior | Medium | Low | Reject any change outside `meso.py`, `validation.py`, and prompt templates |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: Path traversal in issue source_file fails closed with ISSUE_NOT_FOUND; repair refuses to write outside `specs/` workstation paths
Constraints: No new dependencies; repair writes application issue files only, never Micro artifacts or product-pack files

## Integration Points
- **`plan pre` contract**: Adds a `NOT_READY` status with `missing_fields` plus `repair_hint`; existing READY consumers keep their shape
- **`tasks pre` plan prerequisite**: Reuses the same validator indirectly since it already gates on `plan.md` acceptance contract validity
- **`deviate meso run` orchestration**: Surfaces the NOT_READY diagnostic instead of launching PLAN on untraceable issues
- **Shard and adhoc templates**: Emit the section names and token families the gate checks, so new issues pass without repair

## Constitutional Alignment
- **Architecture**: Implements the Meso Plan gate in the three-layer model (§1); fail-fast before PLAN keeps Micro RED honest about user scenarios
- **Testing**: Follows §3 pytest protocol with failing contract tests first; `tests/unit/test_core/test_validation.py` and `tests/unit/test_cli/test_meso_contracts.py` pin READY and NOT_READY paths; keeps the full suite under 30s per AGENTS.md
- **Git Isolation**: All work stays on the issue worktree branch; commits reference the task ID per §4
- **User Scenarios**: Each `AC-PLAN-NNN` maps to the issue `AO-055-0N` outline and its `US-055-0N` story; RED encodes these scenarios as failing tests and GREEN cannot edit them
