## Plan Summary
- **Issue**: ISS-ADH-046 — JUDGE RPC infra failures carry pi-side diagnostics into a sidecar
- **Implementation Strategy**: Capture the failed `prompt` response error in `_invoke_rpc_blocking`, raise it with stderr on the no-`agent_end` path, and write sidecars plus a distinguishing event on the empty-manifest path in `_invoke_agent`.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Surface pi-side response error on no-agent_end RPC run**
- **Source Outline**: `AO-046-01`
- **Upstream Traceability**: `US-046-01`, `FR-ADHOC-046`, `AC-ADHOC-046-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:_invoke_rpc_blocking`
- **Given**: RPC stdout holds a failed `prompt` response and no `agent_end` event with exit code 0
- **When**: `_invoke_rpc_blocking` processes the transcript
- **Then**: It raises `EmptyOutputError` carrying the response error text plus stderr
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Write judge sidecar and distinguishing event on empty-manifest path**
- **Source Outline**: `AO-046-01`
- **Upstream Traceability**: `US-046-01`, `FR-ADHOC-046`, `AC-ADHOC-046-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: JUDGE invoke returns no manifest via the no-`agent_end` path
- **When**: `_invoke_agent` handles `EmptyOutputError`/`MalformedHandoverManifestError`
- **Then**: It calls `_write_invoke_sidecars` with stderr plus response error, logs `JUDGE_AGENT_NO_AGENT_END`, and the JUDGE failure message carries the pi-side text
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Write sidecar when stderr is empty**
- **Source Outline**: `AO-046-01`
- **Upstream Traceability**: `US-046-01`, `FR-ADHOC-046`, `AC-ADHOC-046-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_write_invoke_sidecars`
- **Given**: No-`agent_end` transcript carries a failed response error with empty stderr
- **When**: The empty-manifest path writes `.raw/judge-*.log`
- **Then**: The sidecar holds the response error text and nothing drops silently
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep normal agent_end run unchanged**
- **Source Outline**: `AO-046-02`
- **Upstream Traceability**: `US-046-02`, `FR-ADHOC-046`, `AC-ADHOC-046-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: RPC transcript holds a valid `agent_end` manifest
- **When**: JUDGE invokes the agent
- **Then**: The manifest flows through with existing events only and compliance rejections keep current messages
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: detect no-`agent_end` and surface failed response error
  - **Current State**: `_invoke_rpc_blocking` returns empty `manifest_text` and drops failed `prompt` response payloads
  - **Changes Required**: Track failed `response`-type payload error text while scanning lines; on missing `agent_end` with exit 0 raise `EmptyOutputError` with response error plus stderr
  - **Integration Surface**: `AgentBackend.invoke`, `_dispatch_invocation`, `EmptyOutputError`, `_abort_on_schema_rejection`
- **src/deviate/cli/micro.py**: sidecar plus distinguishing event on empty-manifest path
  - **Current State**: `_invoke_agent` returns `(None, "")` on `EmptyOutputError` without sidecars; JUDGE raises bare `agent returned no manifest`
  - **Changes Required**: Call `_write_invoke_sidecars` on the `EmptyOutputError`/`MalformedHandoverManifestError` path with partial output; log `JUDGE_AGENT_NO_AGENT_END` for JUDGE phase; surface `exc` text in JUDGE `PhaseFailedError`
  - **Integration Surface**: `_write_invoke_sidecars`, `_log_run`, `_run_judge_phase`, `write_raw_sidecar`
- **tests/unit/test_micro/test_judge_rpc_no_agent_end.py**: new unit coverage for this slice
  - **Current State**: File does not exist
  - **Changes Required**: Mock RPC subprocess transcripts for no-`agent_end`, empty-stderr, and valid-`agent_end` cases; mock `_run_pytest` per repo policy
  - **Integration Surface**: `_invoke_rpc_blocking`, `_invoke_agent`, `_write_invoke_sidecars`

## Implementation Strategy
- **Phase 1**: RPC no-`agent_end` diagnostics in `agent.py`
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: Capture `error`/`message` from parsed `response`-type events with `success:false`; skip non-JSON lines as today; raise `EmptyOutputError` with combined response error plus stderr when `manifest_text` stays empty
  - **Verification**: Unit test feeds failed-`prompt`-response transcript and asserts raised text
- **Phase 2**: Sidecar plus event in `micro.py`
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Write sidecars on the shared empty-manifest except path; add JUDGE-scoped distinguishing log event; thread `exc` text into JUDGE `PhaseFailedError`
  - **Verification**: Unit test asserts sidecar writer call, event fields, and unchanged valid-run path

## Data Flow Analysis
- RPC stdout lines enter `_invoke_rpc_blocking`; parsed JSON events split into `agent_end` content versus failed `response` error text; stderr joins as fallback context. The combined diagnostic flows as `EmptyOutputError` into `_invoke_agent`, which writes stdout plus prompt to `.raw/judge-*.log` via `_write_invoke_sidecars` and logs `JUDGE_AGENT_NO_AGENT_END`; the JUDGE runner surfaces the text in `PhaseFailedError`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Response payload shape varies across pi versions | Medium | Medium | Parse defensively, keep stderr fallback, never drop the sidecar |
| Shared `_invoke_agent` path changes non-JUDGE phases | Medium | Low | Gate the distinguishing event on phase JUDGE, keep sidecar write generic |
| Nonzero-exit path regresses | Low | Low | Keep `AgentSubprocessError` branch first, add test pins |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: nonzero exit still raises AgentSubprocessError without response-error parsing; malformed JSON lines never crash the scanner
Constraints: no new dependencies, no prompt assembly or truncation changes, no pi backend or RPC protocol changes

## Integration Points
- **pi RPC transcript**: `agent_end` message content versus failed `prompt` response payload shape
- **`.raw/judge-*.log` sidecar**: `write_raw_sidecar` via `_write_invoke_sidecars`
- **Run log events**: `AGENT_ERROR` plus new `JUDGE_AGENT_NO_AGENT_END` consumed by triage tooling

## Constitutional Alignment
- **Architecture**: Meso PLAN authors the authoritative Gherkin contract for ISS-ADH-046; Tasks maps it; RED encodes user scenarios as failing tests per §1
- **Testing**: pytest unit sandbox at `tests/unit/test_micro/test_judge_rpc_no_agent_end.py` with mocked RPC subprocess; full suite under 30s per §3
- **Git Isolation**: Work happens on the dedicated issue worktree branch; orchestrator commits at phase boundary per §4
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-003` encode `US-046-01` plus ATDD outline `AO-046-01`; `AC-PLAN-004` encodes `US-046-02` plus `AO-046-02`; RED turns them into failing tests
