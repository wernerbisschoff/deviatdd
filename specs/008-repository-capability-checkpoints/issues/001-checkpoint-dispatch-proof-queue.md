---
title: "Checkpoint dispatch, proof validation, and queue state control"
labels: ["epic:008-repository-capability-checkpoints", "layer:micro"]
source_file: "specs/008-repository-capability-checkpoints/issues/001-checkpoint-dispatch-proof-queue.md"
blocked_by: []
coordinates_with: []
issue_id: "008-001"
---

## System Topology Mapping

- **Epic Domain**: `008-repository-capability-checkpoints`
- **Local File Path**: `specs/008-repository-capability-checkpoints/issues/001-checkpoint-dispatch-proof-queue.md`
- **Workstation Paths**:
  - `src/deviate/cli/micro.py` (checkpoint claim, dispatch, handover validation, queue halt)
  - `src/deviate/state/` (TaskRecord extensions: `task_type`, `CHECKPOINT_STARTED`, `CHECKPOINT_FAILED`)
  - `src/deviate/prompts/auto/checkpoint.md` (dedicated checkpoint prompt resource)
  - `src/deviate/core/agent.py::AgentBackend` (checkpoint invocation substrate)
  - `tests/` (checkpoint dispatch, proof validation, queue transition coverage)
- **Application Layers Touched**: parsing (type preservation), orchestration (Micro dispatch plus queue control), contract assembly (handover plus evidence bundle), persistence (append-only ledger rows). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run a `Verification_Batch` task so the checkpoint claims it, invokes the agent with full verification context, validates the reported proof, and advances or halts the queue with typed evidence.

## Scope Boundaries

- **Hard Inclusions**:
  - Parser preserves `Type: Verification_Batch` on the task record and forces `IMMEDIATE` execution mode.
  - Micro resolves batch type before mode dispatch and appends `CHECKPOINT_STARTED` under task/worktree isolation.
  - Dedicated checkpoint invocation passes task, issue, contract, declared commands, worktree, documentation, and capabilities through `src/deviate/prompts/auto/checkpoint.md` via `AgentBackend`, routed as `checkpoint` through existing config routing.
  - Runtime validates task identity, `CHECKPOINT` phase, `PASS`/`FAIL` status, full command coverage, full criterion coverage, exit code 0 on `PASS`, and nonempty evidence.
  - `PASS` appends `COMPLETED` with `TaskEvidenceBundle` and continues the queue; any failure appends `CHECKPOINT_FAILED` with classification plus rationale, halts the queue, and preserves completed predecessors.
- **Defensive Exclusions**:
  - Repository capability discovery logic (belongs to `008-002`).
  - Checkpoint placement and closing-batch authoring rules (belongs to `008-002`).
  - Read-only prompt role wording and prompt-file alignment (belongs to `008-003`).
  - User documentation and specification updates (belongs to `008-003`).
  - Checkpoint-specific sandboxing and write monitoring.
  - Automatic repair-task synthesis and checkpoint replay.

## Upstream Requirement Tracing

- **FR-001-CHECKPOINT-IDENTITY**: parser preserves batch type; dispatch uses preserved type (`AO-001`).
- **FR-004-CHECKPOINT-EXECUTION**: dedicated prompt invocation with full context and config-routed model (`AO-006`, `AO-007`).
- **FR-006-CHECKPOINT-PROOF**: identity, coverage, and evidence validation with diagnostic classification (`AO-009`, `AO-010`).
- **FR-007-CHECKPOINT-STATE**: typed terminal evidence, queue advance on pass, halt with predecessors preserved on fail (`AO-011`, `AO-012`).
- **Source**: `specs/008-repository-capability-checkpoints/prd.md` (`FR-001`, `FR-004`, `FR-006`, `FR-007`; `AO-001`, `AO-006`, `AO-007`, `AO-009` … `AO-012`).

## User Stories Ledger

- `US-008-01`: As an operator, I declare a `Verification_Batch` block so its type persists on the task record and dispatches through checkpoint handling.
- `US-008-02`: As an operator, I run a ready checkpoint so the agent receives task, contract, commands, worktree, and capabilities in one invocation.
- `US-008-03`: As an operator, I receive a checkpoint verdict so passing proof advances the queue and failing proof halts it with completed work preserved.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-001` (`FR-001`): a `Verification_Batch` block persists its type on the task record and dispatches through checkpoint handling with `IMMEDIATE` mode retained. Result: zero batches lose identity in parsing or dispatch.
- `AO-006` (`FR-004`): checkpoint invocation delivers task, issue, contract, declared commands, worktree, documentation, and capabilities to the agent. Result: the agent holds full verification context.
- `AO-007` (`FR-004`): the checkpoint resolves its phase model through existing config routing without a hard-coded tier. Result: `checkpoint` follows phase-key, default-key, then backend-native fallback.
- `AO-009` (`FR-006`): completion requires every declared command reported, every declared criterion covered, exit code 0 on `PASS`, and nonempty evidence including observed behavior for runtime proof. Result: partial proof never marks completion.
- `AO-010` (`FR-006`): every failure carries a diagnostic classification and rationale, including preflight failures with empty result lists. Result: operators can direct repair work from the recorded evidence.
- `AO-011` (`FR-007`): a passing checkpoint appends `COMPLETED` with typed evidence and advances the queue. Result: downstream tasks start only after recorded proof.
- `AO-012` (`FR-007`): a failing checkpoint appends `CHECKPOINT_FAILED`, halts the queue, and preserves completed predecessors. Result: zero completed implementation rows reset on failure.

## Multi-Tiered Verification Targets

- **Unit Tests**: parser type preservation, Micro type-before-mode dispatch, handover validation (identity, command coverage, criterion coverage, evidence), queue halt and predecessor preservation.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k checkpoint`
- **Verification Command**: `mise run check`

## Demonstration Path

```bash
# Declare a Verification_Batch task, then run the checkpoint
deviate micro run --task-id 008-001-TASK
# Inspect the appended CHECKPOINT_STARTED then COMPLETED rows
grep 008-001-TASK specs/008-repository-capability-checkpoints/tasks.jsonl
# Force a failing proof and confirm the queue halts with predecessors intact
pytest tests/ -v -k checkpoint
mise run check
```
