# Implementation Tasks: `feat/adhoc/058-converge-opt-in-pack`

## Phase 1: Optional Converge pack
**Goal**: Install Converge commands only when the operator selects the optional pack.

### Tasks

- TSK-058-01: Install the opt-in Converge command pack
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/core/commands.py`
    - `src/deviate/prompts/commands/deviate-converge.md`
  - **Rationale**: `US-058-01` and `AC-PLAN-001` require opt-in installation. `commands.py` owns pack resolution, and the prompt file supplies the installed command.
  - **Details**:
    - **Red**: Add unit cases in `tests/unit/test_cli/test_converge.py` only; forbid `tests/integration` and `tests/e2e`. Assert default stems exclude `deviate-converge`, selected `converge` includes it, and unknown packs fail closed.
    - **Green**: Register `converge` in `OPTIONAL_PACKS`, preserve default pack resolution, and add the bounded `/deviate-converge` prompt with its read, taxonomy, and append-only contract. GREEN cannot edit tests.
    - **Edge Cases**: Keep `deviate run` unchanged when the pack is not selected.
    - **Acceptance**: The installed prompt names only relative issue-scoped inputs and application paths.

## Phase 2: Readiness contract
**Goal**: Emit an issue-scoped Converge pre-contract and reject unavailable inputs.

### Tasks

- TSK-058-02: Emit the bounded Converge readiness contract
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/core/converge.py`
    - `src/deviate/cli/converge.py`
  - **Rationale**: `US-058-02` and `AC-PLAN-002` define the bounded pre-contract. These modules resolve issue artifacts and expose the JSON command.
  - **Details**:
    - **Red**: Extend the stamped unit file only; forbid `tests/integration` and `tests/e2e`. Assert `deviate converge pre` identifies the issue, brief, plan, tasks, filled constitution MUST, and relative in-scope paths while excluding epic artifacts.
    - **Green**: Implement `build_pre_contract` and the `pre` command to resolve this issue's artifacts, inspect task status, and emit the required JSON fields. GREEN cannot edit tests.
    - **Edge Cases**: Skip constitution checks when its template is unfilled and reject absolute paths in the emitted contract.
    - **Acceptance**: Contract generation meets the 500ms issue-level emission limit.

  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-002 requires a bounded readiness contract with repository-relative paths.
    - Evidence: The RED test adds relative-path assertions while the existing test still expects absolute paths.
    - Correction: Reconcile the test suite to one explicit path contract in tests/unit/test_cli/test_converge.py, then add a failing assertion for the selected contract.
    - Verification: Run mise unit; expect failure from the missing or incorrect behavior, not contradictory test expectations.
    - Boundary: Change tests only. Preserve the AC-PLAN-002 scope and do not edit production code.
- TSK-058-03: Reject Converge when prerequisites or Micro work are unavailable
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/cli/converge.py`
    - `src/deviate/core/converge.py`
  - **Rationale**: `US-058-02` and `AC-PLAN-003` require actionable readiness failures. The CLI and readiness core own missing-artifact and pending-task diagnostics.
  - **Details**:
    - **Red**: Extend the stamped unit file only; forbid `tests/integration` and `tests/e2e`. Assert missing brief, plan, or tasks and pending Micro records return non-zero output containing `CONVERGE_NOT_READY` and the missing or pending prerequisite.
    - **Green**: Add readiness validation to `pre` and return the named diagnostic before agent handoff or writes. GREEN cannot edit tests.
    - **Edge Cases**: Report one deterministic prerequisite diagnostic per unavailable condition and retain relative paths.

  - **Judge Feedback**: The next GREEN attempt must:
    - Requirement: AC-PLAN-003 requires readiness rejection for missing artifacts and pending Micro records.
    - Evidence: GREEN changed no implementation file; only the ledger transition changed.
    - Correction: Implement readiness validation in src/deviate/cli/converge.py and src/deviate/core/converge.py. Return one deterministic CONVERGE_NOT_READY diagnostic for each unavailable condition.
    - Verification: Run mise unit; expect the missing brief, plan, tasks, and pending queue tests to pass with non-zero results.
    - Boundary: Preserve the RED tests and restrict changes to the assigned implementation files.
  - **Judge Feedback**: The next GREEN attempt must:
    - Requirement: AC-PLAN-003 requires actionable readiness rejection.
    - Evidence: GREEN changed only the ledger transition and added no production implementation.
    - Correction: Add readiness validation to src/deviate/cli/converge.py and src/deviate/core/converge.py before agent handoff or writes.
    - Verification: Run mise unit; expect missing brief, plan, tasks, and pending queue tests to pass with non-zero results.
    - Boundary: Preserve the RED tests and restrict implementation changes to the assigned source files.
## Phase 3: Append-only findings
**Goal**: Classify findings and append Convergence tasks without changing prior state.

### Tasks

- TSK-058-04: Append classified Convergence tasks through the ledger
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/core/converge.py`
    - `src/deviate/state/ledger.py`
  - **Rationale**: `US-058-03` and `AC-PLAN-004` require append-only task creation. `apply_findings` must call `append_task_record` while preserving prior task text.
  - **Details**:
    - **Red**: Extend the stamped unit file only; forbid `tests/integration` and `tests/e2e`. Assert valid findings append one next-numbered `## Phase N: Convergence`, create PENDING `TSK-058-NN` records through `append_task_record`, preserve all prior bytes, and order critical findings first.
    - **Green**: Implement `apply_findings` to derive the next phase and task ids, append the markdown section, and use `append_task_record` for every pending task. Keep existing ledger rows and task text unchanged. GREEN cannot edit tests.
    - **Edge Cases**: Surface a named ledger append error and avoid hand-edited JSONL.
  - **Dependency**: TSK-058-03

- TSK-058-05: Preserve clean and failed Converge writes
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/core/converge.py`
    - `src/deviate/cli/converge.py`
  - **Rationale**: `US-058-04` and `AC-PLAN-005` require clean no-op and failure preservation. Findings parsing and post diagnostics own these observable results.
  - **Details**:
    - **Red**: Extend the stamped unit file only; forbid `tests/integration` and `tests/e2e`. Assert empty findings leave `tasks.md` byte-unchanged and report `CONVERGED`; invalid taxonomies fail; `unrequested` creates review/justify/remove work; failed writes leave task text unchanged.
    - **Green**: Implement `parse_findings_payload` validation and transactional post behavior for empty, invalid, critical, and `unrequested` findings. GREEN cannot edit tests.
    - **Edge Cases**: Allow only `missing`, `partial`, `contradicts`, and `unrequested`; require source references and never delete application code.
  - **Dependency**: TSK-058-04

## Phase 4: Optional runner handoff
**Goal**: Re-enter Micro for appended Convergence tasks and stop before walkthrough and review.

### Tasks

- TSK-058-06: Re-enter Micro through the optional Converge loop
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/cli/__init__.py`
    - `src/deviate/core/converge.py`
  - **Rationale**: `US-058-05` and `AC-PLAN-006` define the opt-in loop. `run_command` owns the Micro handoff and Converge availability gate.
  - **Details**:
    - **Red**: Extend the stamped unit file only; forbid `tests/integration` and `tests/e2e`. Assert a selected or installed pack hands off after Micro drain, repeats Micro after appended tasks until clean, and then reaches walkthrough, review, and PR without placing those phases inside the loop.
    - **Green**: Register the Converge Typer app and add the opt-in runner tail using `converge_pack_available`; preserve the default runner path and stop the loop on clean findings. GREEN cannot edit tests.
    - **Edge Cases**: Report not-ready state before a Micro drain and never make Converge a mandatory Gate 3 prerequisite.
  - **Dependency**: TSK-058-05

  - **Judge Feedback**: The next RED attempt must:
    - Requirement: AC-PLAN-006 requires the optional Converge loop after Micro drain and before walkthrough, review, and PR.
    - Evidence: The diff contains no RED-authored tests for runner handoff, repeated Micro drain, clean termination, or phase ordering.
    - Correction: Add sociable unit tests in tests/unit/test_cli/test_converge.py that exercise run_command and assert selected or installed Converge handoff, repeated Micro execution after appended tasks, clean-loop termination, and walkthrough/review/PR execution outside the loop.
    - Verification: Run the stamped unit file and confirm the new tests fail because the required runner behavior is absent, not because of collection or syntax errors.
    - Boundary: Change tests only. Keep the scope limited to tests/unit/test_cli/test_converge.py.
## Phase 5: Full application verification
**Goal**: Verify the complete Converge application surface after all slices pass.

### Tasks

- TSK-058-07: Verify the complete Converge workflow
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_cli/test_converge.py`
    - `src/deviate/cli/converge.py`
    - `src/deviate/cli/__init__.py`
    - `src/deviate/core/converge.py`
    - `src/deviate/core/commands.py`
  - **Rationale**: `US-058-01` through `US-058-05` and `AC-PLAN-001` through `AC-PLAN-006` require one final application verification pass across pack, contracts, ledger, and runner boundaries.
  - **Details**:
    - **Implementation**: Run the existing unit suite and confirm the focused Converge tests cover pack selection, readiness, append ordering, clean no-op, diagnostics, and loop handoff.
    - **Acceptance**: All existing tests pass with no test-layer or scope violations.

## Implementation Strategy (Merge Conflict Boundaries only — Execution Order, Dependency Chains, and Risk Hotspots duplicate task Dependencies and the plan Risk Assessment)
**Merge Conflict Boundaries**:
- `tests/unit/test_cli/test_converge.py`
- `src/deviate/core/converge.py`
- `src/deviate/cli/converge.py`

---
