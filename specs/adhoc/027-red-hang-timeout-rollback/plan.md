## Plan Summary
- **Issue**: ISS-ADH-027 — Raise AGENT_TIMEOUT and roll back dirty RED when the agent never returns a manifest
- **Implementation Strategy**: Give `_invoke_streaming` a wall-clock deadline from `AgentConfig.timeout` (default 600s) so a post-write stdout trickle still raises `AgentTimeoutError` before an outer ~1800s bash kill. Make `_run_red_phase` treat that timeout like GREEN, log `AGENT_TIMEOUT`, and call existing `_restore_worktree_to_baseline` on `red_baseline`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/027-red-hang-timeout-rollback.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it fixes CLI `pi -p` RED hang plus dirty-tree rollback (`pi_rpc=false`).
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns `AgentBackend` streaming dispatch and `_run_red_phase`)

## Acceptance Contract

**Scenario AC-PLAN-001: Surface a RED harness timeout instead of a silent no-manifest wait**
- **Source Outline**: `AO-027-01`
- **Upstream Traceability**: `US-027-01`, `FR-ADHOC-027`, `AC-ADHOC-027-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`; `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: `_run_red_phase` has logged `PHASE_START`, captured `red_baseline`, and `_invoke_agent` raises `AgentTimeoutError` or returns `(None, timeout_tail)` after a child that never yields a handover manifest.
- **When**: The RED runner handles that invoke result inside a patched harness budget.
- **Then**: `_invoke_agent` logs `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=`, and `_run_red_phase` raises `PhaseFailedError` that names timeout rather than only `agent returned no manifest`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Bound a post-write stdout trickle by AgentConfig.timeout**
- **Source Outline**: `AO-027-01`
- **Upstream Traceability**: `US-027-01`, `FR-ADHOC-027`, `AC-ADHOC-027-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:_invoke_streaming`; `src/deviate/state/config.py:AgentConfig.timeout`
- **Given**: `_invoke_streaming` receives a patched `timeout_secs` from `AgentConfig.timeout` (default 600), the child already wrote stdout, and later stdout arrives often enough to keep the 900s stall clock warm while no handover manifest arrives.
- **When**: The streaming poll loop runs until that wall-clock budget elapses.
- **Then**: The call raises `AgentTimeoutError` inside the patched timeout plus poll slack, `invoke` does not sleep 30s for a second full budget, and the wait does not reach an outer ~1800s bash kill.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Restore hung-child RED diffs to red_baseline**
- **Source Outline**: `AO-027-02`
- **Upstream Traceability**: `US-027-02`, `FR-ADHOC-027`, `AC-ADHOC-027-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_restore_worktree_to_baseline`; `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: `red_baseline` was captured before invoke, and the hung RED child dirtied a tracked file or added an untracked file that was absent from that baseline.
- **When**: `_run_red_phase` fails the timeout path from `AC-PLAN-001`.
- **Then**: `_run_red_phase` calls `_restore_worktree_to_baseline(root, red_baseline)` and `git status --porcelain` matches `red_baseline`, including paths that were already dirty before invoke.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep a hung RED attempt retryable without a success row**
- **Source Outline**: `AO-027-02`
- **Upstream Traceability**: `US-027-02`, `FR-ADHOC-027`, `AC-ADHOC-027-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`; `src/deviate/cli/micro.py:append_task_transition`
- **Given**: The task ledger has no RED or COMPLETED row for this TSK on this issue, and `session.red_commit_sha` was cleared at RED start.
- **When**: The hung RED timeout path from `AC-PLAN-001` raises.
- **Then**: The runner writes no COMPLETED row, no successful RED transition, and no invented `red_commit_sha`, so a later `deviate micro run` of the same TSK on this issue may retry.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep ISS-ADH-025, ISS-ADH-023, and EXECUTE 3600s composed**
- **Source Outline**: `AO-027-03`
- **Upstream Traceability**: `US-027-03`, `FR-ADHOC-027`, `AC-ADHOC-027-03`
- **Current-Code Evidence**: `src/deviate/core/agent.py:capture_stderr_diagnostics`; `src/deviate/cli/micro.py:_find_task_record`; `src/deviate/cli/micro.py:EXECUTE_STALL_TIMEOUT_SECONDS`
- **Given**: Existing ISS-ADH-025 stderr-not-liveness pins, ISS-ADH-023 issue-scoped `_find_task_record` / `TASK_ALREADY_DONE` pins, and the EXECUTE `stall_timeout==3600` pin are in the suite.
- **When**: This slice lands the RED timeout and restore path.
- **Then**: Stderr-only noise still trips `STALL_DETECTED` without resetting the stall clock, a known active issue still ignores a sibling COMPLETED same-number TSK, `_run_execute_phase` still passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600), and `STREAM_STALL_TIMEOUT_SECONDS` stays 900.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Keep a healthy RED manifest on the existing commit path**
- **Source Outline**: `AO-027-01`
- **Upstream Traceability**: `US-027-01`, `FR-ADHOC-027`, `AC-ADHOC-027-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`; `src/deviate/core/agent.py:STREAM_STALL_TIMEOUT_SECONDS`
- **Given**: RED `_invoke_agent` returns a parseable handover manifest inside the harness budget, and the test command fails as a valid RED.
- **When**: `_run_red_phase` continues after that invoke.
- **Then**: The runner still formats, appends the RED ledger row, commits the failing test, and records `session.red_commit_sha`, and a few minutes of stdout silence inside the 900s stall budget does not kill that healthy invoke.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: Own the streaming wall-clock so a post-write hang still raises `AgentTimeoutError`.
  - **Current State**: `_invoke_streaming` exits the poll loop on schema rejection, stdout-done, hard stall, or smart stall. Periodic stdout calls `refresh_stall_deadline`. `timeout_secs` is used only on the post-loop `Thread.join`. A child that keeps emitting stdout never hits that join. `invoke` re-raises `STALL_DETECTED` / `SMART_STALL_DETECTED` and retries other `AgentTimeoutError` after `time.sleep(30)`. `_invoke_agent` builds `AgentConfig(backend=backend_name)` with default `timeout=600`.
  - **Changes Required**: Check a wall-clock deadline from `timeout_secs` inside the poll loop. Raise `AgentTimeoutError` with `partial_stdout` and `partial_stderr` when that deadline elapses. Re-raise that streaming wall-clock error from `invoke` with no 30s sleep and no second `Popen`. Keep stderr diagnostic. Keep `STREAM_STALL_TIMEOUT_SECONDS` at 900. Keep the 30s retry only for blocking `TimeoutExpired`. Do not thread `DeviateConfig.timeout` / `timeout_seconds` (operator-local 1800) into `AgentConfig`. Do not retune RPC blocking except to keep existing timeout raise.
  - **Integration Surface**: `_invoke_streaming`; `invoke`; `_is_streaming_stall`; `AgentTimeoutError`; `AgentConfig.timeout`.

- **src/deviate/cli/micro.py**: Own RED timeout naming and dirty-tree rollback.
  - **Current State**: `_run_red_phase` captures `red_baseline`, then treats every `manifest is None` as `agent returned no manifest` with no restore. Ledger append and `force_transition_to("RED")` run only after tests fail. `_invoke_agent` already logs `AGENT_TIMEOUT` and returns `(None, partial_stdout)`. Empty `partial_stdout` is falsy, so GREEN's `timeout_ctx` check can miss a timeout. `_restore_worktree_to_baseline` already restores tracked files and cleans untracked files that are not in the baseline. `_run_execute_phase` already passes `stall_timeout=3600`. `_find_task_record` already skips `preferred` when `_resolve_known_active_issue_id` returns an id.
  - **Changes Required**: After RED `_invoke_agent`, treat timeout as timeout even when `partial_stdout` is empty. Log path stays `AGENT_TIMEOUT`. Call `_restore_worktree_to_baseline(root, red_baseline)` before raise. Raise `PhaseFailedError` that names timeout. Leave `red_commit_sha` empty. Write no RED-success or COMPLETED ledger row. Keep `_restore_worktree_to_baseline` as the only restore helper. Keep EXECUTE `stall_timeout=3600`. Do not reopen `_find_task_record` unless a known active issue still receives a sibling COMPLETED `preferred` hit on this hang path.
  - **Integration Surface**: `_run_red_phase`; `_invoke_agent`; `_restore_worktree_to_baseline`; `_worktree_status_paths`; `EXECUTE_STALL_TIMEOUT_SECONDS`; `_find_task_record`.

- **tests/test_cli/test_micro.py**: Pin RED timeout surface, restore, and compose.
  - **Current State**: `TestGreenStallHarnessSurface` pins `_invoke_agent` `AGENT_TIMEOUT` and EXECUTE `stall_timeout==3600`. `TestRedPhaseFailureBoundaryIsolation` expects `agent returned no manifest` when invoke returns `(None, "403 RegionError")`. No pin restores `red_baseline` after a RED timeout.
  - **Changes Required**: Add a `_run_red_phase` pin that mocks timeout (`AgentTimeoutError` or `(None, timeout_tail)`), expects `AGENT_TIMEOUT`, a timeout-named `PhaseFailedError`, restore to `red_baseline`, and no RED/COMPLETED ledger row. Keep the 403 no-manifest pin on a non-timeout `None`. Keep ISS-ADH-025 and EXECUTE 3600 pins. Mock `deviate.cli.micro._run_pytest` if a CLI path would spawn it. Patch budgets. Do not sleep 900s or 1800s.
  - **Integration Surface**: `_run_red_phase`; `_invoke_agent`; `_restore_worktree_to_baseline`.

- **tests/test_core/test_agent.py**: Pin post-write wall-clock timeout.
  - **Current State**: Silent-stdout stall, stderr-not-liveness, stall-override, and `STREAM_STALL_TIMEOUT_SECONDS == 900` pins already exist. The poll loop has no pin that occasional stdout still dies at `timeout_secs`.
  - **Changes Required**: Keep those pins. Add a mocked-`Popen` pin: emit some stdout, then trickle more stdout inside the stall window, with a sub-second `timeout_secs`, and expect `AgentTimeoutError` at that wall clock with no `time.sleep(30)` retry. Do not sleep 900s.
  - **Integration Surface**: `_invoke_streaming`; `invoke`; `AgentTimeoutError`.

- **tests/test_micro/test_run.py** / **tests/test_micro/test_e2e.py**: Keep ISS-ADH-023 issue-scope pins.
  - **Current State**: Pinned `TSK-NNN-NN` already ignores sibling COMPLETED when this issue is known. `_find_task_record` returns `preferred` only when no active issue resolves.
  - **Changes Required**: Keep those pins green. Add a leftover-hole pin only if a known active issue still receives a sibling COMPLETED after a hung RED (IDLE session, no this-issue ledger row).
  - **Integration Surface**: `_find_task_record`; `_exit_if_already_done`.

- **specs/DeviaTDD-api.md**: Document RED `AGENT_TIMEOUT` plus dirty-tree rollback.
  - **Current State**: Agent Backend Hardening names stdout liveness, 900s stall, 3600s EXECUTE, and `AGENT_TIMEOUT` for hung GREEN. It does not name RED rollback on a never-returned manifest.
  - **Changes Required**: State that a RED child that never returns a manifest raises `AgentTimeoutError` / logs `AGENT_TIMEOUT` inside `AgentConfig.timeout` (default 600s). State `_run_red_phase` restores `red_baseline`. State the operator does not wait for an outer ~1800s bash kill. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` §10.0.

- **specs/DeviaTDD-architecture.md**: Align §10.0 with the RED hang contract.
  - **Current State**: §10.0 documents the stall watchdog and hung GREEN `AGENT_TIMEOUT`. It does not document streaming wall-clock or RED restore.
  - **Changes Required**: State the poll loop also honors `timeout_secs`. State RED restore uses `_restore_worktree_to_baseline`. Keep stderr diagnostic and EXECUTE 3600s. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` Agent Backend Hardening.

- **CHANGELOG.md**: Record the user-visible hang and rollback fix.
  - **Current State**: `[Unreleased]` has the ISS-ADH-025 GREEN stall bullet and no ISS-ADH-027 RED hang/rollback bullet.
  - **Changes Required**: Append an `[Unreleased]` bullet: hung RED logs `AGENT_TIMEOUT` inside the harness budget and rolls the worktree back to `red_baseline`.
  - **Integration Surface**: constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: RED timeout, restore, and wall-clock pins
  - **Files**: `tests/test_cli/test_micro.py`, `tests/test_core/test_agent.py`
  - **Approach**: Add a `_run_red_phase` pin that dirties a tracked or untracked path after `red_baseline`, mocks a timeout invoke, and expects `AGENT_TIMEOUT`, restore, and no RED/COMPLETED row. Add a streaming pin that trickles stdout under a sub-second `timeout_secs` and expects `AgentTimeoutError` with no 30s retry. Keep ISS-ADH-025, ISS-ADH-023, and EXECUTE 3600 pins. Mock `_run_pytest` and `Popen`. Do not sleep 900s.
  - **Verification**: `uv run pytest tests/test_cli/test_micro.py tests/test_core/test_agent.py tests/test_micro/test_e2e.py -q -k "timeout or stall or find_task_record or already_done or red"` fails on the new pins.

- **Phase 2**: Streaming wall-clock deadline
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: In `_invoke_streaming`, track invoke start with `time.monotonic()`. When elapsed time reaches `timeout_secs`, kill the child and raise `AgentTimeoutError` with partial streams. Re-raise that streaming wall-clock error from `invoke` the same way stall is re-raised. Leave `STREAM_STALL_*` constants unchanged. Leave blocking `TimeoutExpired` on the 30s retry.
  - **Verification**: The new trickle-stdout pin raises at the patched `timeout_secs`. `test_streaming_agent_stderr_only_noise_trips_stall` and `test_stream_stall_timeout_seconds_is_900` stay green.

- **Phase 3**: RED timeout naming and baseline restore
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Distinguish RED timeout from `AGENT_NOT_AVAILABLE` and from a generic `None` skip. Treat empty `partial_stdout` as timeout when `_invoke_agent` logged `AGENT_TIMEOUT` or returned a timeout marker. Call `_restore_worktree_to_baseline(root, red_baseline)`. Raise a timeout-named `PhaseFailedError`. Do not append a success ledger row. Do not set `red_commit_sha`. Do not invent a second restore helper.
  - **Verification**: The new `_run_red_phase` pin passes. `TestRedPhaseFailureBoundaryIsolation` still matches `agent returned no manifest` for a non-timeout `None`.

- **Phase 4**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Document RED `AGENT_TIMEOUT`, streaming wall-clock via `AgentConfig.timeout` (default 600s), and `red_baseline` restore. Keep ISS-ADH-025 stdout-liveness and GH-53 EXECUTE 3600s. Append the `[Unreleased]` bullet in the same implementation commit.
  - **Verification**: Docs name the RED hang/rollback contract. `mise run check` stays green.

## Data Flow Analysis
- **Input**: A RED `pi -p` child (`pi_rpc=false`) with stdout and stderr pipes. The child may write tests or other files and then emit occasional stdout without a handover manifest.
- **Capture**: `_run_red_phase` clears `session.red_commit_sha`, logs `PHASE_START`, and stores `red_baseline` from `_worktree_status_paths`.
- **Transform**: `_invoke_agent` builds `AgentConfig(backend=...)` with default `timeout=600`. `_invoke_streaming` resets the 900s stall clock on stdout only. The new wall-clock uses `timeout_secs`. A hang raises `AgentTimeoutError` with `partial_stdout` and `partial_stderr`.
- **Harness**: `invoke` re-raises the streaming timeout. `_invoke_agent` logs `AGENT_TIMEOUT` with `error=` and the partial streams. `_run_red_phase` restores `red_baseline` and raises a timeout-named `PhaseFailedError`.
- **Storage**: No new ledger row types. Hung RED writes no RED-success or COMPLETED row. `red_commit_sha` stays empty so GREEN stays closed and the TSK stays retryable.
- **Compose**: EXECUTE still passes `stall_timeout=3600`. Stderr stays diagnostic. Pinned `TSK-NNN-NN` lookup stays issue-scoped.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Post-write stdout keeps the 900s stall warm and the poll loop never checks `timeout_secs` | High | High | Add a wall-clock check in `_invoke_streaming`. Pin trickle-stdout against a sub-second `timeout_secs`. |
| Empty `partial_stdout` makes RED treat timeout as `agent returned no manifest` | High | High | Use a dedicated timeout marker or re-raise. Do not rely on a truthy tail alone. |
| Hung-child diffs stay dirty because restore runs only on no-failing-test adjudication | High | High | Call `_restore_worktree_to_baseline` on the RED timeout path. Pin porcelain equality with `red_baseline`. |
| `invoke` sleeps 30s and starts a second hanging child | High | Medium | Re-raise streaming wall-clock timeout like stall. Keep the 30s retry only for blocking `TimeoutExpired`. |
| Default RED/GREEN stall drops below 900s and kills healthy think time | High | Low | Do not change `STREAM_STALL_TIMEOUT_SECONDS`. Keep the `== 900` pin. |
| EXECUTE collapses to 900s | High | Low | Do not change `EXECUTE_STALL_TIMEOUT_SECONDS`. Keep the 3600 pin. |
| Operator-local `.deviate/config.toml` `timeout=1800` is copied onto `AgentConfig` and races bash | High | Medium | Keep `_invoke_agent` on default `AgentConfig.timeout=600`. Do not thread `timeout_seconds`. |
| ISS-ADH-023 is reopened and `preferred` breaks unscoped unit tests | Medium | Low | Touch `_find_task_record` only if a known active issue still hits sibling COMPLETED. Keep existing pins. |
| Live 900s or 1800s sleeps blow the 30s suite budget | High | Medium | Patch budgets. Mock `Popen` and `_invoke_agent`. Mock `deviate.cli.micro._run_pytest`. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (`Popen` pipes, `proc.kill` on wall-clock timeout), file paths (`git restore` / `git clean -fd` on paths that appeared after `red_baseline`)
Negative tests: post-write stdout trickle still raises `AgentTimeoutError` inside the patched `timeout_secs`; RED timeout does not leave dirty tracked or untracked files; hung RED writes no COMPLETED or RED-success row; empty `partial_stdout` still names timeout; stderr-only noise still trips `STALL_DETECTED`; EXECUTE still passes 3600; default stall stays 900; sibling COMPLETED still does not print `TASK_ALREADY_DONE` for a known active issue
Constraints: no new dependencies; no hardcoded secrets; no un-mocked `_run_pytest`; no branch deletion; no operator-local `.deviate/config.toml` mutation; no second restore helper; no Product-layer flow authoring; do not reopen ISS-ADH-026 schema-rejection

## Integration Points
- **`_invoke_streaming` poll loop**: Adds the `timeout_secs` wall-clock beside the existing stall detector.
- **`AgentBackend.invoke`**: Re-raises streaming wall-clock timeout. Keeps the 30s blocking-timeout retry.
- **`_invoke_agent`**: Existing `AGENT_TIMEOUT` log is the operator-visible harness verdict for hung RED and hung GREEN.
- **`_run_red_phase`**: Distinguishes timeout from generic `None`. Restores `red_baseline`. Raises a timeout-named `PhaseFailedError`.
- **`_restore_worktree_to_baseline`**: Single restore helper for hung RED and for no-failing-test adjudication.
- **`_run_execute_phase`**: Still passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600). GH-53 stays composed.
- **`_find_task_record` / `_exit_if_already_done`**: Stay issue-scoped (ISS-ADH-023). `preferred` remains legal only when no active issue resolves.
- **API / architecture §10.0**: Same-commit contract for RED `AGENT_TIMEOUT` and dirty-tree rollback.

## Constitutional Alignment
- **Architecture**: The change stays in Micro-layer C1 dispatch and RED phase control. It does not skip a layer. It adds no ledger row types. Session Continuity is unchanged. Constitution §1 Git Isolation holds: hung RED restores the worktree and does not invent a RED SHA.
- **Testing**: pytest pins under `tests/test_cli/test_micro.py` and `tests/test_core/test_agent.py`. RED writes failing pins first. GREEN writes `src/` plus the listed spec and changelog files. Coverage target remains >= 80% (constitution §3).
- **Git Isolation**: Work stays on the pre-configured issue worktree. Micro agents do not run branch-mutating git. The slice never deletes a branch. Restore uses `git restore` and `git clean -fd` only on post-baseline paths.
- **Product Layer**: `flow_refs` stays `[]`. FLOW-04 remains RPC TUI live-stream, not RED hang/rollback policy. This slice does not author or index Product-layer flows.
- **Definition of Done**: The hang and rollback fix is user-visible, so `CHANGELOG.md` `[Unreleased]` updates in the same implementation commit (constitution §5).
