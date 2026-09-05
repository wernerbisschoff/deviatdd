## Plan Summary
- **Issue**: ISS-043 — RED fails fast on split unit-plus-integration test contracts
- **Implementation Strategy**: Add a multi-layer contract check at RED pre in `src/deviate/cli/micro.py` that stops with a named split-task error before any agent spawn; single-layer tasks keep the current path.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Mixed unit plus integration contract stops at RED pre with zero agent attempts**
- **Source Outline**: `AO-043-01`
- **Upstream Traceability**: `US-043-01`, `FR-ADHOC-043`, `AC-ADHOC-043-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:red_pre`
- **Given**: A task declares unit plus integration test targets across its row and card signals
- **When**: The operator runs RED pre for that task
- **Then**: RED pre exits non-zero with a split-task error and spawns zero RED agents
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Split-task error names detected layers and required planner action**
- **Source Outline**: `AO-043-01`
- **Upstream Traceability**: `US-043-02`, `FR-ADHOC-043`, `AC-ADHOC-043-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_pre_layer_contract`
- **Given**: A mixed-layer contract detected from any two signals among card paths, declared commands, and declared strategy plus card paths
- **When**: RED pre reports the split-task error
- **Then**: The message names each detected layer and directs the planner to split into one task per layer
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Single-layer contract passes the check untouched**
- **Source Outline**: `AO-043-02`
- **Upstream Traceability**: `US-043-01`, `FR-ADHOC-043`, `AC-ADHOC-043-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_classify_suite_kind`
- **Given**: A task declares test targets in exactly one layer
- **When**: The operator runs RED pre for that task
- **Then**: No split-task error fires and RED writes tests in the assigned layer dir
- **Verification Mode**: automated

**Scenario AC-PLAN-004: e2e mixed with any layer triggers the error while keyword-only cards keep fallback**
- **Source Outline**: `AO-043-02`
- **Upstream Traceability**: `US-043-02`, `FR-ADHOC-043`, `AC-ADHOC-043-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_classify_suite_kind`
- **Given**: One task mixes e2e with another layer and a second card carries only ambiguous keywords with no concrete multi-layer paths
- **When**: The operator runs RED pre for each task
- **Then**: The e2e-mixed task stops with the split-task error and the keyword-only task keeps current fallback behavior
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: owns RED pre contract resolution and the new split check
  - **Current State**: `_pre_layer_contract` resolves one layer via `_classify_suite_kind`; mixed contracts fall through to `ambiguous` full-suite fallback and loop through doomed RED retries
  - **Changes Required**: Add concrete multi-layer detection over task row plus card signals; raise a named split-task error from `_pre_layer_contract` before any agent spawn
  - **Integration Surface**: `red_pre`, `_extract_test_strategy`, `_task_card_text`, `_task_verification_command`, `_classify_suite_kind`
- **src/deviate/prompts/auto/red.md**: documents the one-layer-per-RED lock
  - **Current State**: Layer lock already states two layers need two tasks
  - **Changes Required**: None; keep the rule unchanged per defensive exclusion
  - **Integration Surface**: None beyond prose reference in the error message

## Implementation Strategy
- **Phase 1**: Detect concrete multi-layer targets and fail fast at RED pre
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Scan declared verification commands and concrete test file paths in the task row plus card for hits in two or more of unit, integration, e2e suite dirs; a row `test_strategy` naming one layer loses to card files in two layers; prose-only mentions without concrete targets do not fire; raise a split-task error naming detected layers and the split action through the existing `VerificationUnresolvedError`-style pre exit path
  - **Verification**: `uv run pytest tests/ -k "split" -v` plus full `mise run test` under 30s with `_run_pytest` mocked per repo rule

## Data Flow Analysis
- Inputs: task row (`test_strategy`, `verification`), task card text (`Test Strategy` line, `Verification` line, file paths), declared test commands. Transform: normalize each signal to layer hits among unit, integration, e2e; count distinct layers with concrete targets. Outputs: single layer continues to existing `_layer_contract_fields`; two or more layers raise the split-task error naming layers and the planner split action. Storage: no ledger writes; the error surfaces on stdout and a non-zero pre exit.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Prose-only layer mentions trigger false split errors | Medium | Medium | Fire only on concrete targets: suite-dir file paths and layer-scoped commands; keyword fallback stays for unstamped cards |
| Legitimate single-layer task blocked by stray path in card | Medium | Low | Concrete targets decide per edge case; document that cards list only the assigned layer's files |
| Error message leaks internals instead of the fix | Low | Low | Template the message as detected layers plus split-into-one-task-per-layer action; cover with a unit assert on message content |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: poisoned verification string never executes at pre; split check reads only allowlisted card text
Constraints: reuse `is_safe_test_command` filtering for declared commands; no new dependencies; no ledger or branch mutation from the check

## Integration Points
- **`deviate micro red pre` contract JSON**: emits `status READY` today; on split contract it exits non-zero with the split-task error instead of emitting a layer contract
- **`deviate micro run` RED loop**: calls the same pre path; the split error stops the task before the first agent spawn so no escalate counts toward TRAIN_EXHAUSTED
- **JUDGE compliance checks**: unchanged; single-layer RED output still passes the existing layer audit

## Constitutional Alignment
- **Architecture**: Micro-layer RED hardening only; Macro intent flows through the issue AO outlines into this plan contract; no layer skipped, no Gate 2 reintroduced (constitution §1)
- **Testing**: pytest per §3; new unit tests for split detection plus an integration stop-before-spawn test; suite stays under 30s; RED still writes failing tests first and GREEN still cannot edit tests
- **Git Isolation**: Work happens on the dedicated issue worktree branch; phase commits stay with the orchestrator (constitution §1, §4)
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-003` encode `US-043-01` (refuse mixed contract at once); `AC-PLAN-002` and `AC-PLAN-004` encode `US-043-02` (error names layers and fix); RED turns these into failing tests in `tests/`
