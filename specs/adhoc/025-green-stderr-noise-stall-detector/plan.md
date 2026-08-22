## Plan Summary
- **Issue**: ISS-ADH-025 — Treat stderr as diagnostic so GREEN stall raises AGENT_TIMEOUT
- **Implementation Strategy**: Stop `_invoke_streaming` `read_stderr` from resetting `stall_deadline` or feeding `record_bytes`. Re-raise a stdout-silent `STALL_DETECTED` from `invoke` so `_invoke_agent` logs `AGENT_TIMEOUT` inside the 900s budget. Keep EXECUTE at 3600s and the GREEN default at 900s.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/025-green-stderr-noise-stall-detector.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it fixes CLI `pi -p` stall liveness (`pi_rpc=false`).
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns `AgentBackend` streaming dispatch)

## Acceptance Contract

**Scenario AC-PLAN-001: Trip STALL_DETECTED when only stderr keeps arriving**
- **Source Outline**: `AO-025-01`
- **Upstream Traceability**: `US-025-01`, `FR-ADHOC-025`, `AC-ADHOC-025-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:read_stderr`; `src/deviate/core/agent.py:stall_deadline`
- **Given**: `_invoke_streaming` uses a patched sub-second `stall_timeout`, stdout stays blocked or empty, and stderr emits diagnostic lines on an interval shorter than that budget.
- **When**: The streaming poll loop runs until the configured stall budget elapses.
- **Then**: The call raises `AgentTimeoutError` whose message matches `STALL_DETECTED` at that budget and does not run until an outer timeout.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep diagnostic lines on AgentTimeoutError.partial_stderr**
- **Source Outline**: `AO-025-01`
- **Upstream Traceability**: `US-025-01`, `FR-ADHOC-025`, `AC-ADHOC-025-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:AgentTimeoutError`; `src/deviate/core/agent.py:read_stderr`
- **Given**: The same stderr-only stall as `AC-PLAN-001` emits at least one diagnostic line such as `[codebase-index] Background reindex failed`.
- **When**: `_invoke_streaming` raises `AgentTimeoutError` for `STALL_DETECTED`.
- **Then**: `AgentTimeoutError.partial_stderr` contains those diagnostic lines and `partial_stdout` still holds any stdout seen.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Surface AGENT_TIMEOUT without a second full stall retry**
- **Source Outline**: `AO-025-02`
- **Upstream Traceability**: `US-025-02`, `FR-ADHOC-025`, `AC-ADHOC-025-02`
- **Current-Code Evidence**: `src/deviate/core/agent.py:invoke`; `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: GREEN `_invoke_agent` calls `AgentBackend.invoke` with an `output_callback`, so dispatch uses `_invoke_streaming`, and the first stream is stdout-silent through the stall budget.
- **When**: `_invoke_streaming` raises `AgentTimeoutError` matching `STALL_DETECTED`.
- **Then**: `invoke` re-raises that error without `time.sleep(30)` plus a second full stall budget, and `_invoke_agent` logs `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=` inside the interactive budget plus poll slack.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep EXECUTE stall_timeout at 3600 seconds**
- **Source Outline**: `AO-025-03`
- **Upstream Traceability**: `US-025-03`, `FR-ADHOC-025`, `AC-ADHOC-025-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:EXECUTE_STALL_TIMEOUT_SECONDS`; `src/deviate/cli/micro.py:_run_execute_phase`
- **Given**: `_run_execute_phase` invokes the agent for DIRECT EXECUTE.
- **When**: That call reaches `_invoke_agent`.
- **Then**: The call still passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600), and `test_streaming_agent_stall_timeout_override_is_honored` stays green.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep periodic stdout and 900s GREEN think time**
- **Source Outline**: `AO-025-03`
- **Upstream Traceability**: `US-025-03`, `FR-ADHOC-025`, `AC-ADHOC-025-03`
- **Current-Code Evidence**: `src/deviate/core/agent.py:STREAM_STALL_TIMEOUT_SECONDS`; `src/deviate/core/agent.py:read_stdout`
- **Given**: GREEN `_invoke_agent` omits `stall_timeout`, so the budget is `STREAM_STALL_TIMEOUT_SECONDS` (900), and a streaming invoke either emits periodic stdout or stays silent for only a few minutes inside that budget.
- **When**: `_invoke_streaming` runs with that default budget.
- **Then**: Periodic stdout completes without `STALL_DETECTED`, the default GREEN budget stays 900s, and a few minutes of stdout silence inside that budget does not trip the detector.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: Own stall liveness and the first-stall retry policy.
  - **Current State**: `read_stderr` appends lines, calls `record_bytes`, and resets `stall_deadline`. `read_stdout` does the same. `STREAM_STALL_TIMEOUT_SECONDS` is 900. `invoke` catches every `AgentTimeoutError`, sleeps 30s, and dispatches a second full stall. The blocking `communicate` path uses that retry for `TimeoutExpired`.
  - **Changes Required**: Treat stderr as diagnostic. Keep appending stderr into `stderr_lines` for `partial_stderr`. Do not reset `stall_deadline` on stderr. Do not call `record_bytes` on stderr. Keep stdout as the only hard-deadline reset. On `STALL_DETECTED` or `SMART_STALL_DETECTED`, re-raise from `invoke` with no 30s sleep and no second full stall. Keep the existing 30s retry for blocking `TimeoutExpired`. Do not change `STREAM_STALL_TIMEOUT_SECONDS`, `STREAM_STALL_WINDOW_SECONDS`, or `STREAM_STALL_MIN_BYTES_PER_SECOND`. Do not retune `_invoke_rpc_blocking`.
  - **Integration Surface**: `_invoke_streaming`; `invoke`; `_dispatch_invocation`; `AgentTimeoutError`.

- **src/deviate/cli/micro.py**: Keep GREEN `AGENT_TIMEOUT` logging and the EXECUTE override.
  - **Current State**: `_invoke_agent` already logs `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, and `partial_stdout=` on `AgentTimeoutError`. GREEN/RED/JUDGE/REFACTOR omit `stall_timeout`. `_run_execute_phase` passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600).
  - **Changes Required**: Do not swallow `AgentTimeoutError`. Do not pass a GREEN `stall_timeout` override. Do not fold EXECUTE back to 900s. Add a pin only if `invoke` no longer reaches this handler on first stall.
  - **Integration Surface**: `_invoke_agent`; `_run_execute_phase`; `EXECUTE_STALL_TIMEOUT_SECONDS`.

- **tests/test_core/test_agent.py**: Pin stderr-only stall, first-stall surface, and existing GH-53 / stdout pins.
  - **Current State**: `test_streaming_agent_detects_stdout_stall` covers silent pipes. `test_streaming_agent_stall_timeout_override_is_honored` cites the per-invoke budget. `test_streaming_agent_output_completes_without_stall` covers stdout progress. `test_agent_timeout_retry` and `test_agent_timeout_retry_twice_then_raises` cover blocking `TimeoutExpired` plus the 30s sleep.
  - **Changes Required**: Keep those pins. Add a patched-budget pin: periodic stderr plus silent stdout raises `AgentTimeoutError` matching `STALL_DETECTED` and puts the diagnostic text on `partial_stderr`. Add an `invoke` pin: a streaming `STALL_DETECTED` re-raises without `time.sleep(30)` and without a second `_dispatch_invocation`. Pin `STREAM_STALL_TIMEOUT_SECONDS == 900`. Use mocked `Popen` pipes and sub-second budgets. Do not sleep 900s.
  - **Integration Surface**: `_invoke_streaming`; `invoke`; `AgentTimeoutError`.

- **tests/core/test_smart_stall.py**: Touch only if stderr bytes still feed the rate window.
  - **Current State**: Tests check constant sanity and offline byte-rate math. They do not drive `_invoke_streaming`.
  - **Changes Required**: Leave the file unchanged when `read_stderr` stops calling `record_bytes`. If GREEN still samples stderr bytes, add a pin that sparse stderr cannot suppress the hard `STALL_DETECTED` trip.
  - **Integration Surface**: `STREAM_STALL_MIN_BYTES_PER_SECOND`; `record_bytes`.

- **tests/test_cli/test_micro.py**: Optional harness-log pin.
  - **Current State**: No required GREEN stall pin lives here.
  - **Changes Required**: Add a pin only if needed to prove `_invoke_agent` logs `AGENT_TIMEOUT` when `invoke` raises `AgentTimeoutError`. Mock `AgentBackend.invoke` and `deviate.cli.micro._run_pytest`.
  - **Integration Surface**: `_invoke_agent`.

- **specs/DeviaTDD-api.md**: Document stdout liveness, 900s default, 3600s EXECUTE, and `AGENT_TIMEOUT`.
  - **Current State**: Agent Backend Hardening still says `STREAM_STALL_TIMEOUT_SECONDS = 60` and "no agent output".
  - **Changes Required**: State that streaming liveness is stdout, not stderr. State the default stall is 900s. State EXECUTE passes 3600s. State `_invoke_agent` logs `AGENT_TIMEOUT` for a hung GREEN. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` §10.0.

- **specs/DeviaTDD-architecture.md**: Align §10.0 stall watchdog with the same contract.
  - **Current State**: §10.0 still says `STREAM_STALL_TIMEOUT_SECONDS = 60` (≤ 120 by spec) and that periodic stdout keeps the watchdog warm.
  - **Changes Required**: Replace the stale 60s wording. State stderr is diagnostic. Keep the periodic-stdout rule. Name the 900s default and the 3600s EXECUTE override. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` Agent Backend Hardening.

- **CHANGELOG.md**: Record the user-visible hang fix.
  - **Current State**: `[Unreleased]` has no ISS-ADH-025 / GH-61 stall-noise bullet.
  - **Changes Required**: Append an `[Unreleased]` bullet: stderr no longer resets the stall clock, and a hung GREEN logs `AGENT_TIMEOUT` inside the 900s budget.
  - **Integration Surface**: constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: RED stall and retry pins
  - **Files**: `tests/test_core/test_agent.py`, `tests/test_cli/test_micro.py`
  - **Approach**: Keep the silent-stream pin, the GH-53 override pin, and the stdout-completes pin. Add a sub-second stderr-only stall that expects `STALL_DETECTED` plus `partial_stderr`. Add an `invoke` pin that a streaming stall does not sleep 30s or retry a second full budget. Keep the blocking `TimeoutExpired` 30s retry pins. Mock pipes. Do not sleep 900s. Mock `_run_pytest` if a CLI pin is added.
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/core/test_smart_stall.py -q -k "stall"` fails on the new stderr-only and first-stall pins.

- **Phase 2**: GREEN stdout-only hard deadline
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: In `read_stderr`, keep `stderr_lines.append`. Remove the `stall_deadline` reset. Remove the `record_bytes` call. Leave `read_stdout` as the liveness source. Leave the three `STREAM_STALL_*` constants unchanged.
  - **Verification**: The stderr-only pin raises `STALL_DETECTED` at the patched budget. `partial_stderr` still holds the diagnostic line. `test_streaming_agent_output_completes_without_stall` stays green.

- **Phase 3**: GREEN first-stall surface
  - **Files**: `src/deviate/core/agent.py`, `src/deviate/cli/micro.py`
  - **Approach**: In `invoke`, re-raise `AgentTimeoutError` when the message contains `STALL_DETECTED` or `SMART_STALL_DETECTED`. Do not sleep. Do not start a second `Popen` for that case. Keep the 30s retry for blocking `TimeoutExpired`. Leave `_invoke_agent` `AGENT_TIMEOUT` logging in place. Leave EXECUTE `stall_timeout=3600`.
  - **Verification**: The new `invoke` pin passes. `test_agent_timeout_retry` still sees `sleep(30)`. `_invoke_agent` still logs `AGENT_TIMEOUT` when the error reaches it.

- **Phase 4**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Replace stale `STREAM_STALL_TIMEOUT_SECONDS = 60` wording. Document stdout liveness, 900s default, 3600s EXECUTE, and harness `AGENT_TIMEOUT`. Append the `[Unreleased]` bullet in the same implementation commit.
  - **Verification**: Docs no longer claim a 60s stall. `mise run check` stays green.

## Data Flow Analysis
- **Input**: A `pi -p` child (`pi_rpc=false`) with stdout and stderr pipes. GREEN supplies `output_callback` and no `stall_timeout`. EXECUTE supplies `stall_timeout=3600`.
- **Transform**: `_invoke_streaming` starts `read_stdout` and `read_stderr`. Stdout lines reset `stall_deadline` and feed `record_bytes`. Stderr lines only append to `stderr_lines`. The poll loop sleeps 0.05s and trips when `stall_deadline` expires.
- **Output**: A healthy stream returns `(stdout, stderr)`. A stdout-silent stall raises `AgentTimeoutError` with `STALL_DETECTED`, `partial_stdout`, and `partial_stderr`.
- **Harness**: `invoke` re-raises that stall. `_invoke_agent` logs `AGENT_TIMEOUT` with `error=` and the partial streams. The operator sees the harness verdict inside 900s plus poll slack, not at an outer ~1800s bash kill.
- **Storage**: No new ledger row types. `AgentTimeoutError.partial_stdout` and `partial_stderr` stay in-memory fields.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Periodic stderr still resets `stall_deadline`, so CI hangs until an outer timeout | High | High | Use a sub-second `stall_timeout` and a kill-released stderr iterator. Fail the pin if `STALL_DETECTED` does not arrive at that budget. |
| `invoke` still sleeps 30s and retries a second 900s stall | High | High | Re-raise on `STALL_DETECTED` / `SMART_STALL_DETECTED`. Pin that `time.sleep` is not called and a second `_dispatch_invocation` does not run. |
| Blocking `TimeoutExpired` retry is removed by accident | Medium | Medium | Keep `test_agent_timeout_retry` and `test_agent_timeout_retry_twice_then_raises`. Limit the no-retry path to streaming stall tokens. |
| EXECUTE collapses to 900s or GREEN drops below think-safe 900s | High | Low | Do not change `EXECUTE_STALL_TIMEOUT_SECONDS` or `STREAM_STALL_TIMEOUT_SECONDS`. Keep the GH-53 override pin and a `== 900` default pin. |
| Smart-stall still counts stderr bytes and masks a later rate trip | Medium | Low | Stop `record_bytes` on stderr. Rely on the hard deadline for sparse noise. Do not require smart-stall to fire on one line per ~75s. |
| Live 900s sleeps blow the 30s suite budget | High | Medium | Patch budgets to milliseconds or sub-seconds. Mock `Popen` pipes. Mock `deviate.cli.micro._run_pytest` on any CLI path. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (`Popen` pipes, `proc.kill` on stall)
Negative tests: stderr-only noise still trips `STALL_DETECTED`; streaming stall does not take the 30s-plus-second-budget retry; blocking `TimeoutExpired` still retries once; EXECUTE still passes 3600; default GREEN budget stays 900
Constraints: no new dependencies; no hardcoded secrets; no un-mocked `_run_pytest`; no branch deletion; no operator-local `.deviate/config.toml` mutation; no RPC / `pi_rpc=true` retune; no Product-layer flow authoring

## Integration Points
- **`_invoke_streaming` / `read_stdout`**: Sole hard-deadline reset and `record_bytes` source after this slice.
- **`_invoke_streaming` / `read_stderr`**: Diagnostic capture only. Feeds `stderr_lines` → `AgentTimeoutError.partial_stderr`.
- **`AgentBackend.invoke`**: Re-raises streaming stall. Keeps the 30s blocking-timeout retry.
- **`_invoke_agent`**: Existing `AGENT_TIMEOUT` log is the operator-visible harness verdict for hung GREEN.
- **`_run_execute_phase`**: Still passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600). GH-53 stays composed.
- **API / architecture §10.0**: Same-commit contract that liveness is stdout, default stall is 900s, EXECUTE override is 3600s, and `AGENT_TIMEOUT` is the harness verdict.

## Constitutional Alignment
- **Architecture**: The change stays in Micro-layer agent dispatch inside C1. It does not skip a layer. It does not add ledger row types. Session Continuity is unchanged.
- **Testing**: pytest pins under `tests/test_core/test_agent.py` (and optional CLI). RED writes failing pins first. GREEN writes `src/` plus the listed spec and changelog files. Coverage target remains >= 80% (constitution §3).
- **Git Isolation**: Work stays on the pre-configured issue worktree. Micro agents do not run branch-mutating git. The slice never deletes a branch.
- **Product Layer**: `flow_refs` stays `[]`. FLOW-04 remains RPC TUI live-stream, not stall-clock policy. This slice does not author or index Product-layer flows.
- **Definition of Done**: The hang fix is user-visible, so `CHANGELOG.md` `[Unreleased]` updates in the same implementation commit (constitution §5).
