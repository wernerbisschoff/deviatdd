---
title: "JUDGE RPC infra failures carry pi-side diagnostics into a sidecar"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-046
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/046-judge-rpc-no-agent-end-sidecar.md`
- **Primary Architectural Workstation**: `src/deviate/core/agent.py`, `src/deviate/cli/micro.py`, `tests/unit/test_micro/`

## The Problem Contract
The JUDGE pi RPC subprocess fails on large injected diffs before emitting any `agent_end` event. The runner reports opaque `agent returned no manifest` with `AGENT_ERROR Not Found` and writes no sidecar. This issue carries the pi-side error into a sidecar and a specific failure message.

## Scope Boundaries
### Hard Inclusions
- Detect the no-`agent_end` RPC outcome in `_invoke_rpc_blocking` (`src/deviate/core/agent.py`) and surface the failed `prompt` response error text plus stderr instead of empty text
- Call `_write_invoke_sidecars` on the `EmptyOutputError`/`MalformedHandoverManifestError` path in `_invoke_agent` (`src/deviate/cli/micro.py`) so `.raw/judge-*.log` holds stderr plus the failed response error
- Emit a distinguishing `JUDGE_AGENT_NO_AGENT_END`-style event separating infra crashes from compliance rejections

### Defensive Exclusions
- No change to `_assemble_judge_injected_diff` size, truncation, or prompt assembly; no diff-shrinking work in this slice
- No change to pi backend, RPC protocol, or extension behavior; the pi-side crash itself stays external
- No change to JUDGE verdict routing, manifest schema validation (ISS-ADH-045), or RED/GREEN/REFACTOR invoke paths beyond the shared sidecar fix

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-046`
- **Acceptance Criteria Tokens**: `AC-ADHOC-046-01`, `AC-ADHOC-046-02`
- **Data Model Entities**: HandoverManifest (absent on this path), RunLogEvent (AGENT_ERROR, JUDGE_AGENT_NO_AGENT_END)

## User Stories Ledger
- **US-046-01**: As a developer triaging a JUDGE crash, I want the pi-side error text in the sidecar and the failure message so I see the real cause instead of `Not Found`. *(Ref: FR-ADHOC-046)*
- **US-046-02**: As an operator, I want infra-crash failures tagged distinctly from compliance rejections so I route them to tooling instead of the task author. *(Ref: FR-ADHOC-046)*

## Acceptance Outline
- **AO-046-01** *(Ref: AC-ADHOC-046-01, US-046-01)*: RPC run with no `agent_end` writes stderr plus the failed `response` error to `.raw/judge-*.log` and fails with the pi-side error text
  - **Happy Path**: Sidecar holds the pi extension error (e.g. `Cannot read properties of undefined`) plus stderr; the raised message carries that text
  - **Error Category**: Infra crash emits the distinguishing no-`agent_end` event, never a bare `agent returned no manifest`
  - **Boundary Category**: Empty stderr still writes the sidecar with the failed response error; nothing is dropped silently
- **AO-046-02** *(Ref: AC-ADHOC-046-02, US-046-02)*: A normal `agent_end` run behaves exactly as today
  - **Happy Path**: Valid manifest flows through JUDGE unchanged with existing events only
  - **Error Category**: Compliance rejections keep their current messages and events
  - **Boundary Category**: Non-JUDGE phases gain sidecar coverage only through the shared `_invoke_agent` path, with no phase-specific behavior change

## Edge Cases and Boundaries
- Exit code 0 with `success:false` prompt response and no `agent_end` is the trigger; nonzero exit keeps the existing `AgentSubprocessError` path
- Non-JSON stdout lines are skipped as today; only parsed `response`-type failure payloads contribute error text
- Large prompts still pass through `_truncate_prompt` unchanged; this slice diagnoses the crash, it never prevents it
- Remote source: gh issue 206 (JUDGE pi RPC no `agent_end` on large injected diff, TSK-001-02 on 001-001, deviate 2.27.1); sibling ISS-ADH-045 covers manifest consistency validation

## Performance Constraints
- L_max: 200ms per added RPC inspection gate excluding subprocess runtime
- Throughput: full test suite under 30s (mock RPC subprocess and `_run_pytest` in new tests per AGENTS.md)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_judge_rpc_no_agent_end.py` — no-`agent_end` stdout surfaces the failed response error; sidecar writer called on the empty-manifest path; distinguishing event logged; normal `agent_end` run unchanged
- **Integration Sandbox Targets**: JUDGE run against a stubbed RPC transcript with a failed `prompt` response exits with the pi-side text and a `.raw/judge-*.log` holding stderr plus the response error

## Demonstration Path
```bash
mise run test -- tests/unit/test_micro/test_judge_rpc_no_agent_end.py
```
