# Implementation Tasks: `feat/008-repository-capability-checkpoints/001-checkpoint-dispatch-proof-queue`

## Phase 1: Checkpoint identity and dispatch

**Goal**: Carry `Verification_Batch` identity end to end and invoke the checkpoint agent with config-routed model.

### Tasks

- TSK-001-01: Preserve Verification_Batch type with IMMEDIATE dispatch
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_micro/test_checkpoint_identity.py`
    - `src/deviate/core/tasks_ledger.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-008-01` plus `AC-PLAN-001`. Parser and Micro pending-task resolution are the cause of dropped batch identity.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert a `Type: Verification_Batch` card parses to `task_type Verification_Batch` with mode `IMMEDIATE`, and Micro pending resolution routes it to checkpoint handling, not RED.
    - **Green**: Implement `task_type` retention in `parse`/`resolve_execution_mode` plus Micro `_task_type_from_card` dispatch gate on preserved `task_type` only.
    - **Edge Cases**: Handle missing `Type` field by existing default mode; never default to checkpoint handling.
    - **Acceptance**: Parser round-trip keeps `Verification_Batch`; Micro skips RED/GREEN for it.

- TSK-001-02: Invoke checkpoint agent with full verification context
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_micro/test_checkpoint_dispatch.py`
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/checkpoint.md`
  - **Rationale**: Serves `US-008-02` plus `AC-PLAN-002`. Micro dispatch plus the new prompt resource plus `AgentBackend` reuse carry the verification context.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert one `AgentBackend` invocation via `checkpoint.md` receives task, issue, contract, commands, worktree, docs, and capabilities; assert existing RED/GREEN entrypoints stay wired via preservation assertions.
    - **Green**: Implement `CHECKPOINT_STARTED` append plus single `AgentBackend` call rendering `src/deviate/prompts/auto/checkpoint.md` with the full context packet.
    - **Edge Cases**: Handle agent invocation failure by recording `CHECKPOINT_FAILED` with classification, never `COMPLETED`.
    - **Acceptance**: Exactly one agent call per checkpoint task; context packet holds all seven fields.
  - **Dependency**: TSK-001-01

- TSK-001-03: Route checkpoint model through existing config
  - **Type**: Config
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_state/test_checkpoint_model.py`
    - `src/deviate/state/config.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-008-02` plus `AC-PLAN-003`. `resolve_phase_model` plus the Micro call site are the cause of unrouted checkpoint models.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert phase `checkpoint` returns the `checkpoint` key when present, else `default`, else no model flag; assert Micro passes that value to the checkpoint invocation.
    - **Green**: Implement `resolve_phase_model("checkpoint", models)` call at the checkpoint dispatch site with no new config schema.
    - **Edge Cases**: Handle empty `[models]` by sending no model flag; `claude` backend ignores it silently.
    - **Acceptance**: No new backend or config key; resolution order is checkpoint key, then default, then absent.
  - **Dependency**: TSK-001-02

## Phase 2: Proof validation and queue state

**Goal**: Reject partial checkpoint proof, classify failures, and advance or halt the queue with typed terminal rows.

### Tasks

- TSK-001-04: Reject incomplete checkpoint proof
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_micro/test_checkpoint_proof.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-008-03` plus `AC-PLAN-004`. The handover validator in Micro dispatch is the cause of lax proof acceptance.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert validation fails for each defect: missing command report, missing criterion, nonzero exit on PASS, empty evidence; assert no `COMPLETED` row appends on any defect.
    - **Green**: Implement `validate_checkpoint_proof(handover)` requiring command plus criterion plus exit-zero-on-PASS plus non-empty evidence, gating the `COMPLETED` append.
    - **Edge Cases**: Handle preflight with empty results as failure, not vacuous pass.
    - **Acceptance**: Partial proof never completes; each defect maps to one failed validation.
  - **Dependency**: TSK-001-02

- TSK-001-05: Classify every checkpoint failure with rationale
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_state/test_checkpoint_status.py`
    - `src/deviate/state/ledger.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-008-03` plus `AC-PLAN-005`. `TaskRecord` status literal plus the Micro verdict recorder are the cause of untyped failure rows.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert `TaskRecord` accepts `CHECKPOINT_STARTED` and `CHECKPOINT_FAILED`, and a failing handover appends `CHECKPOINT_FAILED` carrying a diagnostic classification plus a rationale.
    - **Green**: Implement `task_type` field plus extended status literal on `TaskRecord` and the `CHECKPOINT_FAILED` append path with classification and rationale.
    - **Edge Cases**: Handle preflight-empty-results failure with its own classification code.
    - **Acceptance**: Every failure row carries classification plus rationale; append-only order holds.
  - **Dependency**: TSK-001-04

- TSK-001-06: Complete passing checkpoint and halt queue on failure
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Files**:
    - `tests/unit/test_micro/test_checkpoint_queue.py`
    - `src/deviate/cli/micro.py`
    - `src/deviate/state/ledger.py`
  - **Rationale**: Serves `US-008-03` plus `AC-PLAN-006` and `AC-PLAN-007`. The Micro queue loop plus terminal-row writer are the cause of lost advance/halt behavior.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/` only — forbid `tests/integration/` and `tests/e2e/`. Assert a passing handover appends `COMPLETED` with a typed `TaskEvidenceBundle` and starts the next queued task; assert a failing handover appends `CHECKPOINT_FAILED`, starts no further task, and keeps predecessor `COMPLETED` rows intact.
    - **Green**: Implement close-checkpoint path (`COMPLETED` plus evidence bundle plus advance) and halt path (stop advance, never rewrite rows); extend `_TERMINAL_STATUSES` with `CHECKPOINT_FAILED`.
    - **Edge Cases**: Handle failure on the first queued task by halting with zero tasks started after it.
    - **Acceptance**: Pass advances the queue; fail halts it; predecessors stay intact.
  - **Dependency**: TSK-001-05

- TSK-001-07: Verify checkpoint queue end to end
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit && mise e2e`
  - **Files**:
    - `tests/e2e/checkpoint-queue.bats`
    - `src/deviate/cli/micro.py`
  - **Rationale**: Serves `US-008-01` through `US-008-03` plus `AC-PLAN-001` through `AC-PLAN-007`. The consumer E2E surface is the cause of unverified queue behavior.
  - **Details**:
    - **Implementation**: Run the existing unit ladder plus the consumer E2E suite against a checkpoint queue fixture; record pass/fail per `AC-PLAN-001` through `AC-PLAN-007` without creating new test files beyond the E2E check.
    - **Acceptance**: Full ladder passes; every `AC-PLAN-NNN` maps to a green check.
  - **Dependency**: TSK-001-06

---

## Implementation Strategy
**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `src/deviate/state/ledger.py`
