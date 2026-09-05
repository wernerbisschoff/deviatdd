## Plan Summary
- **Issue**: ISS-ADH-048 — Remove Pi RPC mode; print mode is the only Pi transport
- **Implementation Strategy**: Delete the RPC branch and its config keys, then retarget tests to print-mode-only behavior.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Pi invoke always spawns print mode without RPC tokens**
- **Source Outline**: `AO-048-01`
- **Upstream Traceability**: `US-048-01`, `FR-ADHOC-048`, `AC-ADHOC-048-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:_invoke_rpc_blocking`
- **Given**: The agent backend is `pi` with any legacy RPC config present
- **When**: The caller invokes the agent
- **Then**: The process spawns `pi -p` and no RPC token remains in source or tests
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Legacy RPC config keys fail validation or drop on rewrite**
- **Source Outline**: `AO-048-01`
- **Upstream Traceability**: `US-048-02`, `FR-ADHOC-048`, `AC-ADHOC-048-01`
- **Current-Code Evidence**: `src/deviate/state/config.py:_normalize_transport`
- **Given**: An `AgentConfig` carries legacy `pi_rpc` input or a stored config holds legacy keys
- **When**: The config loads or setup rewrites the file
- **Then**: Validation rejects `pi_rpc` input and the rewrite drops legacy keys while it keeps the backend
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Full unit suite passes and checks stay clean**
- **Source Outline**: `AO-048-02`
- **Upstream Traceability**: `US-048-01`, `FR-ADHOC-048`, `AC-ADHOC-048-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:transport`
- **Given**: The removal lands with retargeted tests in place
- **When**: The runner executes the full unit suite and `mise run check`
- **Then**: All tests pass, lint plus format plus types stay clean, and frozen specs stay untouched
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: owns the Pi dispatch branch — remove `PI_RPC_COMMAND`, `_invoke_rpc_blocking`, and the `use_rpc` branch
  - **Current State**: Two Pi paths exist; RPC path never executes against the installed binary
  - **Changes Required**: Delete `PI_RPC_COMMAND`, `_invoke_rpc_blocking`, and `use_rpc` dispatch; keep `_invoke_streaming` print path
  - **Integration Surface**: `AgentConfig` from `src/deviate/state/config.py`; subprocess spawn of `pi -p`
- **src/deviate/state/config.py**: owns RPC config keys — remove `pi_rpc`, `transport`, `rpc_uri`, `_normalize_transport`, `resolve_transport`, `resolve_legacy_cli_fallback`
  - **Current State**: `AgentConfig` carries `pi_rpc`, `transport`, `rpc_uri` plus normalizers and resolvers
  - **Changes Required**: Delete the three fields, the normalizer, and the two resolver functions; keep `resolve_phase_model` intact
  - **Integration Surface**: `AgentConfig` consumers in `core/agent.py` and setup writers in `cli/__init__.py`
- **src/deviate/cli/__init__.py**: owns setup config writes — strip `transport` writes and legacy-key preservation
  - **Current State**: Setup writers emit `transport` and preserve legacy keys on rewrite
  - **Changes Required**: Remove `transport` table writes and drop legacy keys on rewrite
  - **Integration Surface**: `.deviate/config.toml` file format; `AgentConfig` schema
- **specs/DeviaTDD-api.md, specs/DeviaTDD-architecture.md, CHANGELOG.md**: docs follow code in the same commit
  - **Current State**: Docs describe the RPC transport and its config keys
  - **Changes Required**: Remove RPC transport references; add one `[Unreleased]` CHANGELOG bullet
  - **Integration Surface**: None; prose only
- **tests/unit/core/test_agent.py, tests/unit/test_core/test_agent.py, tests/unit/test_cli/test_setup.py**: retarget RPC tests to print-mode-only assertions
  - **Current State**: Tests cover RPC dispatch and transport resolution
  - **Changes Required**: Replace RPC expectations with print-mode-only assertions plus token-scan and legacy-key-drop checks
  - **Integration Surface**: `AgentConfig`, agent invoke, setup writers

## Implementation Strategy
- **Phase 1**: Remove RPC source and config keys
  - **Files**: `src/deviate/core/agent.py`, `src/deviate/state/config.py`, `src/deviate/cli/__init__.py`
  - **Approach**: Delete the listed symbols and branches; keep `_invoke_streaming`, stall handling, and non-Pi backends unchanged
  - **Verification**: Run `rg -n "PI_RPC_COMMAND|_invoke_rpc_blocking|pi_rpc|resolve_transport|rpc_uri" src/ tests/` and expect zero hits
- **Phase 2**: Retarget tests and update docs
  - **Files**: `tests/unit/core/test_agent.py`, `tests/unit/test_core/test_agent.py`, `tests/unit/test_cli/test_setup.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Rewrite RPC tests to assert print-mode-only behavior; strip RPC prose from specs; add CHANGELOG bullet
  - **Verification**: Run `mise run test` for the touched test files, then `mise run check`

## Data Flow Analysis
- Input: caller invokes the agent with backend `pi` plus `reasoning_effort`. The loader builds `AgentConfig` without RPC keys. The agent spawns `pi -p` directly. Setup rewrite drops legacy keys and keeps the backend. Output: printed model response. Storage: `.deviate/config.toml` without `transport` lines.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Stale local config keeps an inert `transport` line | Low | High | Accept the inert line until the next setup rewrite strips it |
| Hidden import of a removed resolver breaks a caller | Medium | Low | Run the token scan plus the full unit suite before commit |
| Test exceeds 30s budget via real pytest subprocess | Medium | Low | Keep `deviate.cli.micro._run_pytest` mocked per `AGENTS.md` |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: legacy `pi_rpc` input fails validation; token scan fails on any leftover RPC reference
Constraints: no new dependencies, no new transport, no changes to non-Pi backends

## Integration Points
- **`pi -p` subprocess spawn**: the single Pi transport contract after removal
- **`.deviate/config.toml` schema**: `AgentConfig` keeps `backend` plus `reasoning_effort`; legacy keys drop on rewrite
- **`resolve_phase_model`**: stays intact; removal touches transport resolvers only

## Constitutional Alignment
- **Architecture**: This plan follows the three-layer model (§1). Plan authors the Gherkin contract here. Tasks maps it. Micro encodes it as tests.
- **Testing**: pytest owns the contract (§3). RED encodes `AC-PLAN-001` through `AC-PLAN-003` as failing tests. GREEN passes them. Coverage target stays at 80 percent or more.
- **Git Isolation**: Work happens on the dedicated issue branch inside its worktree (§1, §4). Commits use the `<type>(<scope>):` format with the task id.
- **User Scenarios**: `AC-PLAN-001` encodes `US-048-01` (one Pi spawn path). `AC-PLAN-002` encodes `US-048-02` (legacy config keeps working). RED turns those scenarios into failing tests.
