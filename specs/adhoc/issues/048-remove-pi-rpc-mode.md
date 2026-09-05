---
title: "Remove Pi RPC mode; print mode is the only Pi transport"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-048
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/048-remove-pi-rpc-mode.md`
- **Primary Architectural Workstation**: `src/deviate/core/agent.py`, `src/deviate/state/config.py`, `src/deviate/cli/__init__.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`

## The Problem Contract
Pi RPC mode never executes and its JSONL framing fails against the installed pi binary. The dead branch and its config keys mislead every reader of the agent layer. Removal leaves `pi -p` as the single Pi transport.

## Scope Boundaries
### Hard Inclusions
- Delete `PI_RPC_COMMAND`, `AgentBackend._invoke_rpc_blocking`, and the `use_rpc` dispatch branch in `src/deviate/core/agent.py`
- Delete `pi_rpc`, `transport`, `rpc_uri`, `_normalize_transport`, `resolve_transport`, `resolve_legacy_cli_fallback` in `src/deviate/state/config.py`
- Strip `transport` writes and legacy-key preservation in `src/deviate/cli/__init__.py` setup writers
- Update `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` in the same commit
- Retarget RPC-mode tests to assert print-mode-only behavior

### Defensive Exclusions
- No new transport, no streaming replacement, no pi protocol research
- No changes to `_invoke_streaming`, stall handling, lean `--tools` policy, or non-Pi backends
- No edits to frozen historical specs (`specs/006-*`, `specs/adhoc/*` requirement ledger entries)

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-048`
- **Acceptance Criteria Tokens**: `AC-ADHOC-048-01`, `AC-ADHOC-048-02`
- **Data Model Entities**: `AgentConfig`

## User Stories Ledger
- **US-048-01**: As a developer reading the agent layer, I want one Pi spawn path so I stop tracing a dispatch branch that never executes. *(Ref: FR-ADHOC-048)*
- **US-048-02**: As an operator with `transport = "rpc"` in config, I want setup runs to keep working and strip the dead key so my workflow never breaks. *(Ref: FR-ADHOC-048)*

## Acceptance Outline
- **AO-048-01** *(Ref: AC-ADHOC-048-01, US-048-01)*: No `PI_RPC_COMMAND`, `_invoke_rpc_blocking`, `pi_rpc`, `transport`, `rpc_uri`, or `resolve_transport` token remains in source or tests
  - **Happy Path**: Pi invoke always spawns `pi -p` without `--mode`
  - **Error Category**: `AgentConfig` with legacy `pi_rpc` input fails validation
  - **Boundary Category**: Rewrite over a config holding legacy keys drops them and keeps the backend
- **AO-048-02** *(Ref: AC-ADHOC-048-02, US-048-02)*: Full unit suite passes and `mise run check` is clean
  - **Happy Path**: All retargeted tests assert print-mode-only behavior
  - **Error Category**: Any leftover RPC reference fails the token scan
  - **Boundary Category**: Historical frozen specs stay untouched

## Edge Cases and Boundaries
- Caller-constructed `AgentConfig` objects pass only `backend` plus `reasoning_effort`, so strict removal breaks no file-load path
- The gitignored local `.deviate/config.toml` keeps an inert `transport` line until the next setup rewrite strips it
- Empty `src/deviate/rpc/` directory goes away with the removal

## Performance Constraints
- L_max: no runtime change; removal only deletes a branch that never executes
- Throughput: full unit suite stays under 30s (`deviate.cli.micro._run_pytest` stays mocked per `AGENTS.md`)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/core/test_agent.py::TestPiPrintMode`, `tests/unit/test_core/test_agent.py::TestPiBackendRegistration`, `tests/unit/test_cli/test_setup.py::TestSetupConfigAllowlist`
- **Integration Sandbox Targets**: `mise run check` (lint plus format plus types)

## Demonstration Path
```bash
mise run test -- tests/unit/core/test_agent.py tests/unit/test_cli/test_setup.py -q
rg -n "PI_RPC_COMMAND|_invoke_rpc_blocking|pi_rpc|resolve_transport|rpc_uri" src/ tests/ | wc -l
```
