# Implementation Tasks: `feat/adhoc/048-remove-pi-rpc-mode`

## Phase 1: Remove Pi RPC dispatch and legacy config keys
**Goal**: Make `pi -p` print mode the only Pi transport and drop legacy RPC config keys

### Tasks

- TSK-048-01: Remove Pi RPC dispatch so invoke always spawns print mode
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/unit/test_core/test_agent.py`
  - **Rationale**: `US-048-01` plus `AC-PLAN-001` require one Pi spawn path. `src/deviate/core/agent.py` owns the dispatch branch (`PI_RPC_COMMAND`, `_invoke_rpc_blocking`, `use_rpc`). `tests/unit/test_core/test_agent.py` is the focused verification file that encodes the print-mode-only contract.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_core/test_agent.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert invoke with backend `pi` spawns `pi -p`, assert no `PI_RPC_COMMAND` or `_invoke_rpc_blocking` reference remains importable, assert a source token scan finds zero RPC tokens. Include a preservation assertion that non-Pi backends and stall handling still dispatch unchanged.
    - **Green**: Implement the removal in `src/deviate/core/agent.py`: delete `PI_RPC_COMMAND`, delete `_invoke_rpc_blocking`, delete the `use_rpc` branch so the Pi path always calls `_invoke_streaming`. GREEN cannot edit tests.
    - **Refactor**: Remove dead imports and helpers left orphaned by the RPC branch. Keep names and style consistent with the file.
    - **Edge Cases**: Handle callers that pass legacy `pi_rpc=True` by ignoring the flag at this layer (validation lives in TSK-048-02). Handle missing `pi` binary with the existing spawn error path.
    - **Acceptance**: `rg -n "PI_RPC_COMMAND|_invoke_rpc_blocking" src/` returns zero hits. `mise run unit` passes for the touched file.
  - **Dependency**: TSK-048-02

  - **Judge Feedback**: The next RED attempt must: retarget the stale RPC tests in tests/unit/core/test_agent.py to assert print-mode-only behavior, keep the new TestPiPrintModeOnly assertions in tests/unit/test_core/test_agent.py, and prove the full unit suite passes with zero RPC tokens.
- TSK-048-02: Drop legacy RPC config keys and fail their validation
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `src/deviate/cli/__init__.py`
    - `tests/unit/test_cli/test_setup.py`
  - **Rationale**: `US-048-02` plus `AC-PLAN-002` require legacy config to keep working by rejection plus drop-on-rewrite. `src/deviate/state/config.py` owns `pi_rpc`, `transport`, `rpc_uri`, `_normalize_transport`, `resolve_transport`, `resolve_legacy_cli_fallback`. `src/deviate/cli/__init__.py` owns setup writes that emit `transport` and preserve legacy keys. `tests/unit/test_cli/test_setup.py` is the focused verification file.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_setup.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `AgentConfig` with `pi_rpc` input fails validation, assert setup rewrite drops `transport`, `pi_rpc`, `rpc_uri` while it keeps `backend`, assert `resolve_phase_model` still resolves per-phase models. Include a preservation assertion that non-Pi backend config writes stay unchanged.
    - **Green**: Implement the removal: delete `pi_rpc`, `transport`, `rpc_uri` fields, `_normalize_transport`, `resolve_transport`, `resolve_legacy_cli_fallback` from `src/deviate/state/config.py`; strip `transport` table writes and legacy-key preservation from `src/deviate/cli/__init__.py`. Keep `resolve_phase_model` intact. GREEN cannot edit tests.
    - **Refactor**: Remove dead imports and the `transport` help-text entry left orphaned. Keep field order and style consistent.
    - **Edge Cases**: Handle a stored config file that still holds legacy keys by dropping them on rewrite and accepting the file until rewrite. Handle unknown `transport` values by rejection, not silent default.
    - **Acceptance**: `rg -n "pi_rpc|resolve_transport|rpc_uri|_normalize_transport|resolve_legacy_cli_fallback" src/ tests/` returns zero hits except the new rejection assertions. `mise run unit` passes for the touched file.

  - **Judge Feedback**: The next RED attempt must: retarget or remove the stale pi transport expectation so setup for pi asserts backend-only writes, add failing assertions that AgentConfig rejects pi_rpc plus transport plus rpc_uri input, add a rewrite assertion that legacy keys drop while backend stays, keep resolve_phase_model coverage, and rerun the focused unit file before handing off.
  - **Judge Feedback**: The next RED attempt must: retarget or remove the stale pi transport expectation so setup for pi asserts backend-only writes, remove pi_rpc accepted-behavior assertions in tests/unit/core/test_agent.py and tests/unit/test_core/test_agent.py and replace them with rejection plus print-mode-only assertions, add failing assertions that AgentConfig rejects pi_rpc plus transport plus rpc_uri input, add a rewrite assertion that legacy keys drop while backend stays, keep resolve_phase_model coverage, and rerun the focused unit file before handing off. Production removal is complete but stale RED tests contradict AC-PLAN-002: TestSetupConfigAllowlist::test_pi_writes_transport_not_pi_rpc asserts transport equals rpc, test_agent files assert pi_rpc accepted and transport equals cli, while AO-048-01 requires rejection plus drop-on-rewrite with zero token hits.
- TSK-048-03: Retarget leftover RPC tests, strip RPC docs, verify full suite
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: integration
  - **Verification**: `mise run unit && mise run integration && mise run check`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/core/test_agent.py`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-003` requires the full unit suite plus checks to stay clean with frozen specs untouched. `tests/unit/core/test_agent.py` holds leftover RPC expectations that TSK-048-01 did not retarget. The two spec files plus `CHANGELOG.md` carry the user-visible RPC prose and the required `[Unreleased]` bullet.
  - **Details**:
    - **Implementation**: Rewrite remaining RPC expectations in `tests/unit/core/test_agent.py` to print-mode-only assertions plus a token-scan check. Remove RPC transport prose from `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md`. Add one `[Unreleased]` bullet to `CHANGELOG.md` that names the Pi RPC removal. Run `mise run unit`, then `mise run integration`, then `mise run check`.
    - **Refactor**: Keep doc edits to RPC lines only. Leave unrelated spec prose untouched.
    - **Edge Cases**: Handle a stale local `transport` line by leaving it inert until the next setup rewrite. Handle hidden imports of removed resolvers by fixing the caller, not by restoring a shim.
    - **Acceptance**: Full unit suite passes. Lint plus format-check stay clean. Frozen specs stay untouched. Token scan across `src/` plus `tests/` finds zero RPC references except the new rejection assertions.
  - **Dependency**: TSK-048-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> TSK-048-02 -> TSK-048-01 -> TSK-048-03 (config first so agent tests build on the final schema, then leftover retarget plus docs)

**Critical Dependency Chains**:
- TSK-048-02 must precede TSK-048-01
- TSK-048-01 must precede TSK-048-03

**Risk Hotspots**:
- Stale local config keeps an inert `transport` line until the next setup rewrite strips it
- Hidden import of a removed resolver breaks a caller; the token scan plus the full unit suite catches it
- Real pytest subprocess in micro tests exceeds the 30s budget; keep `deviate.cli.micro._run_pytest` mocked per `AGENTS.md`

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none; each source file has exactly one owning task

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
