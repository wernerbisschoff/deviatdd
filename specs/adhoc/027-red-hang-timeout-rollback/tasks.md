# Implementation Tasks: `feat/adhoc/027-red-hang-timeout-rollback`

## Phase 1: Streaming Wall-Clock Deadline
**Goal**: A child that already wrote stdout and then trickles more stdout still raises `AgentTimeoutError` at `AgentConfig.timeout`. `invoke` does not sleep 30s. Default stall stays 900s.

### Tasks

- TSK-027-01: Bound a post-write stdout trickle by `AgentConfig.timeout`
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_core/test_agent.py -q -k "timeout or stall"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/unit/test_core/test_agent.py`
  - **Rationale**: US-027-01 and `AC-PLAN-002` require `_invoke_streaming` to raise `AgentTimeoutError` when elapsed time reaches `timeout_secs` even if periodic stdout keeps the 900s stall clock warm. `invoke` must re-raise that wall-clock error with no `time.sleep(30)` and no second `Popen`. `AC-PLAN-005` requires `test_streaming_agent_stderr_only_noise_trips_stall` and `test_stream_stall_timeout_seconds_is_900` to stay green. `src/deviate/core/agent.py` owns the poll loop, `invoke` retry, and `AgentTimeoutError`. `tests/unit/test_core/test_agent.py` owns the trickle-stdout pin. Constitution §3 Testing Protocols: mocked `Popen`, patched sub-second `timeout_secs`, no 900s or 1800s sleep. Constitution §1 Model Tiering / Session Continuity: do not thread `DeviateConfig.timeout` / `timeout_seconds` (1800) into `AgentConfig`.
  - **Details**:
    - **Red**: In `tests/unit/test_core/test_agent.py`, add `test_invoke_streaming_wall_clock_timeout_on_stdout_trickle`. Mock `Popen` so stdout emits an early chunk, then later chunks on an interval shorter than 900s stall and longer than a patched sub-second `timeout_secs`. Do not yield a handover manifest. Call `_invoke_streaming` or `invoke` with `output_callback` set so dispatch uses streaming. Assert `AgentTimeoutError` inside that patched timeout plus poll slack. Assert `exc.partial_stdout` holds the emitted chunks. Assert `time.sleep` is not called with 30. Assert `_dispatch_invocation` / `Popen` runs once (`AC-PLAN-002`). Keep `test_invoke_streaming_stall_does_not_retry`, `test_agent_timeout_retry`, `test_streaming_agent_stderr_only_noise_trips_stall`, and `test_stream_stall_timeout_seconds_is_900` green (`AC-PLAN-005`). Do not sleep 900s.
    - **Green**: In `_invoke_streaming`, record invoke start with `time.monotonic()`. When elapsed time reaches `timeout_secs`, kill the child and raise `AgentTimeoutError` with `partial_stdout` and `partial_stderr`. In `invoke`, re-raise that streaming wall-clock `AgentTimeoutError` the same way `_is_streaming_stall` re-raises. Leave `STREAM_STALL_TIMEOUT_SECONDS` at 900. Leave blocking `TimeoutExpired` on the 30s retry. Do not pass operator-local 1800 into `AgentConfig`.
    - **Refactor**: Share one wall-clock check in the poll loop so hard stall, smart stall, and schema-rejection stay separate exits.
    - **Edge Cases**: Periodic stdout still refreshes only the stall clock. Stderr-only noise still trips `STALL_DETECTED` without resetting stall. A healthy stream that returns a manifest before `timeout_secs` still completes. Do not retune `_invoke_rpc_blocking` except to keep an existing timeout raise. Do not reopen ISS-ADH-026 schema-rejection.
    - **Acceptance**: Trickle stdout raises `AgentTimeoutError` at the patched `timeout_secs`. `invoke` does not sleep 30s and does not start a second child. `STREAM_STALL_TIMEOUT_SECONDS` stays 900. ISS-ADH-025 stderr-not-liveness pins stay green.

---

## Phase 2: RED Timeout Naming and Baseline Restore
**Goal**: Hung RED logs `AGENT_TIMEOUT`, restores `red_baseline`, and stays retryable. A non-timeout `None` still matches `agent returned no manifest`. A healthy RED still commits.

### Tasks

- TSK-027-02: Surface RED timeout, restore `red_baseline`, and keep the TSK retryable
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_micro.py tests/unit/test_micro/test_e2e.py tests/unit/test_micro/test_run.py -q -k "timeout or stall or find_task_record or already_done or red"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-027-01 and `AC-PLAN-001` require `_run_red_phase` to raise a timeout-named `PhaseFailedError` after `_invoke_agent` logs `AGENT_TIMEOUT`, not only `agent returned no manifest`. US-027-02 and `AC-PLAN-003` require `_restore_worktree_to_baseline(root, red_baseline)` so porcelain matches the pre-invoke baseline. `AC-PLAN-004` forbids a COMPLETED row, a successful RED transition, and an invented `red_commit_sha`. `AC-PLAN-006` keeps the healthy-manifest commit path. US-027-03 and `AC-PLAN-005` keep EXECUTE 3600s and ISS-ADH-023 issue-scoped lookup. `src/deviate/cli/micro.py` owns `_run_red_phase`, `_invoke_agent`, and `_restore_worktree_to_baseline`. `tests/unit/test_cli/test_micro.py` owns the new RED timeout pin. Constitution §1 Git Isolation and Append-Only Ledger: restore post-baseline paths only; write no success row. Constitution §3: mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess`.
  - **Details**:
    - **Red**: In `tests/unit/test_cli/test_micro.py`, add `test_run_red_phase_timeout_restores_baseline_and_names_timeout`. Use `tmp_git_repo` plus `_git_env()`. Capture `red_baseline` via `_worktree_status_paths`. Mock `_invoke_agent` so it logs `AGENT_TIMEOUT` and returns `(None, "")` or raises `AgentTimeoutError` after dirtying a tracked file and adding an untracked file that was absent from the baseline. Assert console or run log contains `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=` (`AC-PLAN-001`). Assert `PhaseFailedError` matches timeout and does not match only `agent returned no manifest`. Assert `_restore_worktree_to_baseline` ran and `git status --porcelain` matches `red_baseline`, including paths that were already dirty (`AC-PLAN-003`). Assert the ledger has no COMPLETED row and no successful RED transition, and `session.red_commit_sha` stays empty (`AC-PLAN-004`). Keep `TestRedPhaseFailureBoundaryIsolation` matching `agent returned no manifest` for `(None, "403 RegionError")`. Keep `test_invoke_agent_logs_agent_timeout_on_stall` and `test_execute_stall_timeout_seconds_is_3600` green (`AC-PLAN-005`). Add or keep a healthy-manifest pin that still formats, appends the RED row, commits the failing test, and records `red_commit_sha` (`AC-PLAN-006`). Mock `_run_pytest`. Do not sleep 900s.
    - **Green**: After RED `_invoke_agent`, treat timeout as timeout even when `partial_stdout` is empty. Use a dedicated timeout marker or re-raise; do not rely on a truthy tail alone. Call `_restore_worktree_to_baseline(root, red_baseline)` before raise. Raise `PhaseFailedError` that names timeout. Leave `red_commit_sha` empty. Write no RED-success or COMPLETED ledger row. Keep `_restore_worktree_to_baseline` as the only restore helper. Keep `EXECUTE_STALL_TIMEOUT_SECONDS` at 3600. Do not reopen `_find_task_record` unless a known active issue still receives a sibling COMPLETED `preferred` hit.
    - **Refactor**: Share one timeout-detection site so GREEN `timeout_ctx` and RED timeout naming do not drift on empty `partial_stdout`.
    - **Edge Cases**: `AGENT_NOT_AVAILABLE` and a generic non-timeout `None` still raise `agent returned no manifest` without restore of pre-baseline dirt. Files already dirty in `red_baseline` stay untouched. A later `deviate micro run` of the same TSK on this issue may retry. Do not invent a SHA. Do not delete branches. Do not mutate operator-local `.deviate/config.toml`.
    - **Acceptance**: Hung RED logs `AGENT_TIMEOUT` and raises a timeout-named `PhaseFailedError`. Porcelain matches `red_baseline`. The TSK stays retryable. Healthy RED still commits. EXECUTE stays 3600s. ISS-ADH-023 pins stay green.
  - **Dependency**: TSK-027-01

---

## Phase 3: Specs and Changelog
**Goal**: API and architecture name RED `AGENT_TIMEOUT`, the `AgentConfig.timeout` wall-clock (default 600s), and `red_baseline` restore. CHANGELOG records the hang and rollback fix.

### Tasks

- TSK-027-03: Document RED `AGENT_TIMEOUT` and dirty-tree rollback
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_core/test_agent.py tests/unit/test_cli/test_micro.py tests/unit/test_micro/test_e2e.py -q -k "timeout or stall or find_task_record or already_done or red"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-001` through `AC-PLAN-006` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md` Agent Backend Hardening, `specs/DeviaTDD-architecture.md` §10.0, and `CHANGELOG.md` `[Unreleased]` in the same change as the hang and rollback fix. US-027-01 is the harness timeout verdict. US-027-02 is `red_baseline` restore. US-027-03 keeps ISS-ADH-025 stdout-liveness and GH-53 EXECUTE 3600s. AGENTS.md Spec Alignment requires both spec files. Constitution §1 Four-Layer Architecture: this slice stays in C1 and does not author Product-layer flows.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md` Agent Backend Hardening, state that a RED child that never returns a manifest raises `AgentTimeoutError` and logs `AGENT_TIMEOUT` inside `AgentConfig.timeout` (default 600s). State `_run_red_phase` restores `red_baseline`. State the operator does not wait for an outer ~1800s bash kill. Keep stdout-liveness, 900s stall, and EXECUTE 3600s.
    - **Implementation**: In `specs/DeviaTDD-architecture.md` §10.0, state the poll loop honors `timeout_secs` beside the stall detector. State RED restore uses `_restore_worktree_to_baseline`. Keep stderr diagnostic and EXECUTE 3600s.
    - **Implementation**: Append one `[Unreleased]` bullet in `CHANGELOG.md`: hung RED logs `AGENT_TIMEOUT` inside the harness budget and rolls the worktree back to `red_baseline`.
    - **Implementation**: Re-run the Phase 1 and Phase 2 pins. Do not author or sync Product-layer flows. Do not change TSK id format.
    - **Refactor**: Reuse the existing Agent Backend Hardening and §10.0 wording. Do not add a second restore helper or a second timeout constant.
    - **Edge Cases**: Docs still say periodic stdout keeps the stall watchdog warm. Docs still say GREEN/RED default stall is 900s. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture name RED `AGENT_TIMEOUT`, the 600s `AgentConfig.timeout` wall-clock, and `red_baseline` restore. CHANGELOG `[Unreleased]` has the ISS-ADH-027 bullet. Timeout, stall, and RED pins stay green.
  - **Dependency**: TSK-027-02

---

## Phase 4: CLI E2E
**Goal**: The installed `deviate` package times out a post-write hang inside `AgentConfig.timeout` and keeps the 900s / 3600s stall budgets.

### Tasks

- TSK-027-04: [E2E] Verify installed RED hang surfaces `AGENT_TIMEOUT` before bash
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_red_hang_timeout_rollback.bats`
    - `tests/e2e/test_green_stderr_stall.bats`
  - **Rationale**: US-027-01 and `AC-PLAN-002` are the user-visible happy-failure path: a `pi -p` child that writes stdout and never yields a handover manifest must raise `AgentTimeoutError` at `AgentConfig.timeout` (default 600s), not at an outer ~1800s bash kill. US-027-02 and `AC-PLAN-001` require that failure to name timeout. US-027-03 and `AC-PLAN-005` keep `STREAM_STALL_TIMEOUT_SECONDS == 900` and `EXECUTE_STALL_TIMEOUT_SECONDS == 3600`. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_red_hang_timeout_rollback.bats`. Happy path: `python -c` against the installed package asserts `AgentConfig().timeout == 600`, `STREAM_STALL_TIMEOUT_SECONDS == 900`, and `EXECUTE_STALL_TIMEOUT_SECONDS == 3600`. `deviate micro --help` exits 0 (`AC-PLAN-005`, `AC-PLAN-006`).
    - **Implementation**: Critical-failure path in the same bats file: mock `Popen` pipes so stdout emits an early chunk then trickles more chunks with no handover manifest. Call `_invoke_streaming` or `invoke` with a sub-second `timeout_secs`. Assert `AgentTimeoutError` inside that budget plus poll slack and that `time.sleep(30)` does not run (`AC-PLAN-001`, `AC-PLAN-002`). Do not sleep 900s. Do not start a live `pi -p` child.
    - **Implementation**: Keep `tests/e2e/test_green_stderr_stall.bats` as the ISS-ADH-025 compose suite. Do not call un-mocked `_run_pytest`.
    - **Refactor**: Reuse the bats tmpdir setup/teardown and `_installed_python` helper from `tests/e2e/test_green_stderr_stall.bats`.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` is unused. Do not delete branches in the host repo.
    - **Acceptance**: `bats tests/e2e/` exits 0. Installed `AgentConfig.timeout` stays 600. Installed stall budgets stay 900 / 3600. Trickle stdout raises `AgentTimeoutError` at the patched wall-clock.
  - **Dependency**: TSK-027-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

**Critical Dependency Chains**:
- TSK-027-01 must precede TSK-027-02
- TSK-027-02 must precede TSK-027-03
- TSK-027-03 must precede TSK-027-04

**Risk Hotspots**:
- Post-write stdout keeps the 900s stall warm and the poll loop never checks `timeout_secs`
- Empty `partial_stdout` makes RED treat timeout as `agent returned no manifest`
- Hung-child diffs stay dirty because restore runs only on no-failing-test adjudication
- `invoke` sleeps 30s and starts a second hanging child
- Default RED/GREEN stall drops below 900s or EXECUTE collapses to 900s
- Operator-local `timeout=1800` is copied onto `AgentConfig` and races bash
- Live 900s or 1800s sleeps, or un-mocked `_run_pytest`, blow the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none for production. Phase 1 owns `src/deviate/core/agent.py`. Phase 2 owns `src/deviate/cli/micro.py`. Phase 3 owns specs and CHANGELOG. Phase 4 owns `tests/e2e/`.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/027-red-hang-timeout-rollback/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3). Timeout and stall pins MUST patch budgets and mock `Popen` / `_invoke_agent`. Do not sleep 900s or 1800s.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
