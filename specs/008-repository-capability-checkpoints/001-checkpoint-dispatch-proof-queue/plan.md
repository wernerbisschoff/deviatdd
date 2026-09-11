## Plan Summary
- **Issue**: 008-001 — Checkpoint dispatch, proof validation, and queue state control
- **Implementation Strategy**: Extend the parser, ledger, and Micro dispatch to carry `Verification_Batch` identity end to end, add a config-routed checkpoint invocation with strict proof validation, and close the loop with typed terminal rows plus queue advance/halt.

## Acceptance Contract
**Scenario AC-PLAN-001: Preserve Verification_Batch type with IMMEDIATE mode**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-008-01`, `FR-001-CHECKPOINT-IDENTITY`, `AC-008-001-01`
- **Current-Code Evidence**: `src/deviate/core/tasks_ledger.py:resolve_execution_mode`
- **Given**: A task card declares `Type: Verification_Batch`
- **When**: The parser builds the task record and Micro resolves the pending task
- **Then**: The record keeps `task_type Verification_Batch` with mode `IMMEDIATE` and dispatches into checkpoint handling
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Invoke checkpoint agent with full verification context**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-008-02`, `FR-004-CHECKPOINT-EXECUTION`, `AC-008-002-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:AgentBackend`
- **Given**: A ready checkpoint task with contract, declared commands, worktree, docs, and capabilities
- **When**: Micro dispatches the checkpoint through the dedicated prompt resource
- **Then**: One agent invocation receives task, issue, contract, commands, worktree, documentation, and capabilities via `src/deviate/prompts/auto/checkpoint.md`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Route checkpoint model through existing config**
- **Source Outline**: `AO-007`
- **Upstream Traceability**: `US-008-02`, `FR-004-CHECKPOINT-EXECUTION`, `AC-008-002-02`
- **Current-Code Evidence**: `src/deviate/state/config.py:resolve_phase_model`
- **Given**: A `[models]` config with phase keys plus a default key
- **When**: Micro resolves the model for phase `checkpoint`
- **Then**: The call returns the `checkpoint` key when present, else the `default` key, else no model flag
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Reject incomplete checkpoint proof**
- **Source Outline**: `AO-009`
- **Upstream Traceability**: `US-008-03`, `FR-006-CHECKPOINT-PROOF`, `AC-008-003-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_append_status_transition`
- **Given**: A checkpoint handover missing a command report, a criterion, a nonzero exit on PASS, or empty evidence
- **When**: The runtime validates the reported proof
- **Then**: Validation fails and the task never appends `COMPLETED`
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Classify every checkpoint failure with rationale**
- **Source Outline**: `AO-010`
- **Upstream Traceability**: `US-008-03`, `FR-006-CHECKPOINT-PROOF`, `AC-008-003-02`
- **Current-Code Evidence**: `src/deviate/state/ledger.py:TaskRecord`
- **Given**: A checkpoint handover reporting failure including preflight with empty results
- **When**: The runtime records the verdict
- **Then**: The appended `CHECKPOINT_FAILED` row carries a diagnostic classification plus a rationale
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Complete passing checkpoint and advance queue**
- **Source Outline**: `AO-011`
- **Upstream Traceability**: `US-008-03`, `FR-007-CHECKPOINT-STATE`, `AC-008-004-01`
- **Current-Code Evidence**: `src/deviate/state/ledger.py:TaskEvidenceBundle`
- **Given**: A checkpoint handover passing full validation
- **When**: The runtime closes the checkpoint
- **Then**: The ledger appends `COMPLETED` with a typed `TaskEvidenceBundle` and the next queued task starts
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Halt queue on failing checkpoint and preserve predecessors**
- **Source Outline**: `AO-012`
- **Upstream Traceability**: `US-008-03`, `FR-007-CHECKPOINT-STATE`, `AC-008-004-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_TERMINAL_STATUSES`
- **Given**: A checkpoint handover failing validation with earlier tasks already completed
- **When**: The runtime records `CHECKPOINT_FAILED`
- **Then**: The queue halts, no further task starts, and completed predecessor rows stay intact
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/tasks_ledger.py**: keep `Type: Verification_Batch` on the record and lock mode to `IMMEDIATE` + `Integrates: src/deviate/cli/micro.py pending resolution`
- **src/deviate/cli/micro.py**: resolve batch type before mode dispatch, append `CHECKPOINT_STARTED`, invoke checkpoint, validate handover, close queue + `Integrates: AgentBackend, TaskRecord, tasks.jsonl`
- **src/deviate/state/ledger.py**: extend `TaskRecord` with `task_type` plus `CHECKPOINT_STARTED` and `CHECKPOINT_FAILED` statuses + `Integrates: TaskEvidenceBundle`
- **src/deviate/prompts/auto/checkpoint.md**: add dedicated checkpoint prompt resource carrying full verification context + `Integrates: AgentBackend invocation`
- **src/deviate/core/agent.py**: reuse `AgentBackend` as checkpoint invocation substrate + `Integrates: config model routing`
- **src/deviate/state/config.py**: route `checkpoint` phase through existing `resolve_phase_model` + `Integrates: micro dispatch`
- **tests/**: add checkpoint dispatch, proof validation, and queue transition coverage + `Integrates: pytest -k checkpoint, mise run check`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| TaskRecord status enum rejects new checkpoint rows | High | Medium | Extend literal plus append-only writer in one change |
| Checkpoint dispatch bypasses RED/GREEN unintentionally | High | Low | Gate dispatch on preserved task_type only |
| Proof validator too lax lets partial proof complete | High | Medium | Require command plus criterion plus exit plus evidence checks |
| Queue halt drops predecessor COMPLETED rows | Medium | Low | Halt by stopping advance, never rewriting rows |

## Security Profile
Risk surfaces: subprocess agent invocation, worktree paths, ledger writes
Negative tests: partial proof never completes, preflight failure carries classification, halt preserves predecessors
Constraints: GREEN-scope allow-list unchanged, no new dependencies, no secrets in ledger rows
## Constitutional Alignment
- **Constitution**: §1, §3 — three-layer gates with append-only ledger plus pytest coverage and JUDGE scope check
