# Implementation Tasks: `feat/adhoc/025-green-stderr-noise-stall-detector`

## Phase 1: Stderr-Only Stall Trip
**Goal**: Periodic stderr noise does not reset the hard stall clock. Diagnostic lines stay on `partial_stderr`. Periodic stdout still completes. The GREEN default stays 900s.

### Tasks

- TSK-025-01: Trip `STALL_DETECTED` on stderr-only noise and keep diagnostics
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/core/test_smart_stall.py -q -k "stall"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: US-025-01 and `AC-PLAN-001` require `_invoke_streaming` to raise `AgentTimeoutError` matching `STALL_DETECTED` when stdout stays silent and stderr keeps arriving inside a patched sub-second `stall_timeout`. `AC-PLAN-002` requires those diagnostic lines on `AgentTimeoutError.partial_stderr` and any seen stdout on `partial_stdout`. `AC-PLAN-005` requires periodic stdout to complete without `STALL_DETECTED` and `STREAM_STALL_TIMEOUT_SECONDS == 900`. `src/deviate/core/agent.py` owns `read_stderr`, `read_stdout`, `stall_deadline`, and `record_bytes`. `tests/test_core/test_agent.py` owns the new stderr-only pin and keeps `test_streaming_agent_detects_stdout_stall` plus `test_streaming_agent_output_completes_without_stall`. Constitution §3 Testing Protocols: pytest under `tests/`, mocked `Popen` pipes, no live 900s sleep. Constitution §1 Micro-Layer Scope: GREEN writes `src/deviate/core/agent.py` only for this slice.
  - **Details**:
    - **Red**: In `tests/test_core/test_agent.py`, add `test_streaming_agent_stderr_only_noise_trips_stall`. Mock `Popen` with blocking or empty stdout and a kill-released stderr iterator that yields `[codebase-index] Background reindex failed` on an interval shorter than a patched sub-second `stall_timeout`. Assert `AgentTimeoutError` matches `STALL_DETECTED` at that budget (`AC-PLAN-001`). Assert `exc.partial_stderr` contains `[codebase-index] Background reindex failed` and `exc.partial_stdout` holds any stdout seen (`AC-PLAN-002`). Add `test_stream_stall_timeout_seconds_is_900` asserting `STREAM_STALL_TIMEOUT_SECONDS == 900` (`AC-PLAN-005`). Keep `test_streaming_agent_detects_stdout_stall` and `test_streaming_agent_output_completes_without_stall` green. Do not sleep 900s.
    - **Green**: In `_invoke_streaming` `read_stderr`, keep `stderr_lines.append`. Remove the `stall_deadline` reset. Remove the `record_bytes` call. Leave `read_stdout` as the only hard-deadline reset and `record_bytes` source. Leave `STREAM_STALL_TIMEOUT_SECONDS`, `STREAM_STALL_WINDOW_SECONDS`, and `STREAM_STALL_MIN_BYTES_PER_SECOND` unchanged. Do not retune `_invoke_rpc_blocking`.
    - **Refactor**: Keep stderr capture in one place so `partial_stderr` still joins `stderr_lines` on the stall raise.
    - **Edge Cases**: Empty stderr with silent stdout still trips the existing silent-stream pin. Sparse stderr must not feed the smart-stall byte window. Leave `tests/core/test_smart_stall.py` unchanged when `read_stderr` stops calling `record_bytes`. Kill the child so the stderr iterator can exit.
    - **Acceptance**: Stderr-only noise raises `STALL_DETECTED` at the patched budget. `partial_stderr` holds the diagnostic line. Periodic stdout still completes. Default GREEN budget stays 900s.

---

## Phase 2: First-Stall Harness Surface
**Goal**: A stdout-silent streaming stall re-raises from `invoke` with no 30s sleep and no second full stall. `_invoke_agent` logs `AGENT_TIMEOUT`. EXECUTE still passes 3600s.

### Tasks

- TSK-025-02: Re-raise streaming stall without a second budget and keep EXECUTE at 3600s
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/test_cli/test_micro.py -q -k "stall or timeout or AGENT_TIMEOUT or EXECUTE_STALL"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/agent.py`
    - `src/deviate/cli/micro.py`
    - `tests/test_core/test_agent.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-025-02 and `AC-PLAN-003` require `AgentBackend.invoke` to re-raise a streaming `AgentTimeoutError` matching `STALL_DETECTED` without `time.sleep(30)` and without a second `_dispatch_invocation`. `_invoke_agent` must log `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=` inside the interactive budget plus poll slack. US-025-03 and `AC-PLAN-004` require `_run_execute_phase` to keep `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600) and keep `test_streaming_agent_stall_timeout_override_is_honored` green. `src/deviate/core/agent.py` owns `invoke`. `src/deviate/cli/micro.py` owns `_invoke_agent` and `EXECUTE_STALL_TIMEOUT_SECONDS`. Constitution §3: mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` on every CLI path. Constitution §1 Session Continuity: GREEN still omits a `stall_timeout` override.
  - **Details**:
    - **Red**: In `tests/test_core/test_agent.py`, add `test_invoke_streaming_stall_does_not_retry`. Call `invoke` with an `output_callback` so dispatch uses `_invoke_streaming`. Make the first stream raise `AgentTimeoutError` matching `STALL_DETECTED`. Assert `time.sleep` is not called. Assert `_dispatch_invocation` runs once. Keep `test_agent_timeout_retry` and `test_agent_timeout_retry_twice_then_raises` asserting `sleep(30)` on blocking `TimeoutExpired`. In `tests/test_cli/test_micro.py`, add `test_invoke_agent_logs_agent_timeout_on_stall`: mock `AgentBackend.invoke` to raise `AgentTimeoutError` with `partial_stderr` and `partial_stdout`; assert `_invoke_agent` logs `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=` (`AC-PLAN-003`). Add `test_execute_stall_timeout_seconds_is_3600` asserting `EXECUTE_STALL_TIMEOUT_SECONDS == 3600` and that `_run_execute_phase` still passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (`AC-PLAN-004`). Keep `test_streaming_agent_stall_timeout_override_is_honored` green. Mock `_run_pytest`. Do not sleep 900s.
    - **Green**: In `invoke`, when the caught `AgentTimeoutError` message contains `STALL_DETECTED` or `SMART_STALL_DETECTED`, re-raise with no `time.sleep` and no second `Popen`. Keep the 30s retry for blocking `TimeoutExpired`. Leave `_invoke_agent` `AGENT_TIMEOUT` logging in place. Do not swallow `AgentTimeoutError`. Do not pass a GREEN `stall_timeout` override. Do not change `EXECUTE_STALL_TIMEOUT_SECONDS` or fold EXECUTE to 900s.
    - **Refactor**: Limit the no-retry path to streaming stall tokens so the blocking timeout helper stays one retry.
    - **Edge Cases**: `SMART_STALL_DETECTED` also re-raises. A later documented retry is legal only if `AGENT_TIMEOUT` still lands inside the interactive budget plus poll slack. Do not retune `_invoke_rpc_blocking`. Do not mutate operator-local `.deviate/config.toml`.
    - **Acceptance**: Streaming `STALL_DETECTED` surfaces on the first stall. `_invoke_agent` logs `AGENT_TIMEOUT` with both partial streams. Blocking `TimeoutExpired` still sleeps 30s once. EXECUTE still passes 3600s.
  - **Dependency**: TSK-025-01

---

## Phase 3: Specs and Changelog
**Goal**: API and architecture name stdout liveness, the 900s GREEN default, the 3600s EXECUTE override, and harness `AGENT_TIMEOUT`. CHANGELOG records the hang fix.

### Tasks

- TSK-025-03: Document stdout-only stall liveness and the 900s / 3600s budgets
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/test_cli/test_micro.py tests/core/test_smart_stall.py -q -k "stall or timeout or AGENT_TIMEOUT or EXECUTE_STALL"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-001` through `AC-PLAN-005` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md` Agent Backend Hardening, `specs/DeviaTDD-architecture.md` §10.0, and `CHANGELOG.md` `[Unreleased]` in the same change as the hang fix. US-025-01 is the stderr-diagnostic rule. US-025-02 is the harness `AGENT_TIMEOUT` verdict. US-025-03 is EXECUTE 3600s plus think-safe GREEN 900s. AGENTS.md Spec Alignment requires both spec files. Constitution §1 Four-Layer Architecture: this slice stays in C1 and does not author Product-layer flows.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md` Agent Backend Hardening, replace `STREAM_STALL_TIMEOUT_SECONDS = 60`. State streaming liveness is stdout, not stderr. State the default stall is 900s. State EXECUTE passes 3600s. State `_invoke_agent` logs `AGENT_TIMEOUT` for a hung GREEN.
    - **Implementation**: In `specs/DeviaTDD-architecture.md` §10.0, replace the stale 60s wording. State stderr is diagnostic. Keep the periodic-stdout rule. Name the 900s default and the 3600s EXECUTE override.
    - **Implementation**: Append one `[Unreleased]` bullet in `CHANGELOG.md`: stderr no longer resets the stall clock, and a hung GREEN logs `AGENT_TIMEOUT` inside the 900s budget.
    - **Implementation**: Re-run the Phase 1 and Phase 2 pins. Do not author or sync Product-layer flows. Do not change TSK id format.
    - **Refactor**: Reuse the existing Agent Backend Hardening and §10.0 wording. Do not add a second stall constant or a second retry contract.
    - **Edge Cases**: Docs still say periodic stdout keeps the watchdog warm. Docs still say GREEN omits `stall_timeout`. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture no longer claim a 60s stall. CHANGELOG `[Unreleased]` has the ISS-ADH-025 / GH-61 hang-fix bullet. Stall pins stay green.
  - **Dependency**: TSK-025-02

---

## Phase 4: CLI E2E
**Goal**: The installed `deviate` package trips `STALL_DETECTED` on stderr-only noise and keeps the 900s / 3600s budgets.

### Tasks

- TSK-025-04: [E2E] Verify installed GREEN stall surfaces `STALL_DETECTED` on stderr noise
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_green_stderr_stall.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: US-025-01 and `AC-PLAN-001` are the user-visible happy-failure path: a hung GREEN with only stderr noise must raise `STALL_DETECTED` at the configured budget. US-025-02 and `AC-PLAN-003` are the critical harness path: that error must reach the installed package without a second full stall. US-025-03 keeps `STREAM_STALL_TIMEOUT_SECONDS == 900` and `EXECUTE_STALL_TIMEOUT_SECONDS == 3600`. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_green_stderr_stall.bats`. Happy path: `python -c` against the installed package asserts `STREAM_STALL_TIMEOUT_SECONDS == 900` and `EXECUTE_STALL_TIMEOUT_SECONDS == 3600`. `deviate micro --help` exits 0.
    - **Implementation**: Critical-failure path in the same bats file: run a short Python snippet that mocks `Popen` pipes, feeds `[codebase-index] Background reindex failed` on stderr, keeps stdout silent, and calls `_invoke_streaming` with a sub-second `stall_timeout`. Assert the process raises `AgentTimeoutError` matching `STALL_DETECTED` and that `partial_stderr` contains the diagnostic line. Do not sleep 900s. Do not start a live `pi -p` child.
    - **Implementation**: Keep `tests/e2e/test_macro_workflow.bats` as the existing CLI smoke suite. Do not call un-mocked `_run_pytest`.
    - **Refactor**: Reuse the existing bats tmpdir setup/teardown pattern from `tests/e2e/test_macro_workflow.bats`.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` is unused. Do not delete branches in the host repo.
    - **Acceptance**: `bats tests/e2e/` exits 0. Installed default GREEN budget stays 900s. Installed EXECUTE budget stays 3600s. Stderr-only noise raises `STALL_DETECTED` at the patched budget.
  - **Dependency**: TSK-025-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

**Critical Dependency Chains**:
- TSK-025-01 must precede TSK-025-02
- TSK-025-02 must precede TSK-025-03
- TSK-025-03 must precede TSK-025-04

**Risk Hotspots**:
- Periodic stderr still resets `stall_deadline`, so CI hangs until an outer timeout
- `invoke` still sleeps 30s and retries a second 900s stall
- Blocking `TimeoutExpired` retry is removed by accident
- EXECUTE collapses to 900s or GREEN drops below think-safe 900s
- Live 900s sleeps blow the 30s suite budget
- Un-mocked `_run_pytest` blows the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/agent.py`, `tests/test_core/test_agent.py`. Phase 1 owns `read_stderr`. Phase 2 owns `invoke` retry. Phase 3 owns specs and CHANGELOG only.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/025-green-stderr-noise-stall-detector/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
