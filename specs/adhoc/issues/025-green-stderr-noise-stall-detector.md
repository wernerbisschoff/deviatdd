---
title: "Treat stderr as diagnostic so GREEN stall raises AGENT_TIMEOUT"
labels: [bugfix, adhoc, vertical-slice, micro]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-025
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/025-green-stderr-noise-stall-detector.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/agent.py::_invoke_streaming` — TARGET: `read_stderr` currently resets `stall_deadline` (and feeds `record_bytes`) on every stderr line. Stderr is diagnostic, not liveness. Only stdout (or an explicitly documented liveness source) may reset the hard stall clock. Periodic Pi noise such as `[codebase-index] Background reindex failed` must not keep a hung GREEN alive.
  - `src/deviate/core/agent.py::STREAM_STALL_TIMEOUT_SECONDS` / `STREAM_STALL_WINDOW_SECONDS` / `STREAM_STALL_MIN_BYTES_PER_SECOND` — REFERENCE: keep the interactive 900s hard budget and the smart-stall window/floor. Do not drop GREEN to a few-minute kill. Do not change the constants solely to paper over stderr resets.
  - `src/deviate/core/agent.py::invoke` — TARGET: after a stdout-silent `AgentTimeoutError` / `STALL_DETECTED`, the 30s sleep + second full stall retry must not hide the first stall until an outer ~1800s bash timeout fires. The harness must be able to surface `AGENT_TIMEOUT` itself.
  - `src/deviate/cli/micro.py::_invoke_agent` — TARGET: keep logging `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, `partial_stdout=` on `AgentTimeoutError`. GREEN call sites must not swallow that event.
  - `src/deviate/cli/micro.py::EXECUTE_STALL_TIMEOUT_SECONDS` / `_run_execute_phase` `stall_timeout=3600` — REFERENCE: GH-53 one-hour EXECUTE allowance stays. Do not collapse EXECUTE back to 900s.
  - `src/deviate/cli/micro.py::_invoke_agent` GREEN path — REFERENCE: GREEN still uses the default 900s stall (no `stall_timeout` override today). Keep that unless a documented policy says otherwise.
  - `tests/test_core/test_agent.py` — TARGET: keep `test_streaming_agent_detects_stdout_stall` and `test_streaming_agent_stall_timeout_override_is_honored` (GH-53). Add a pin that periodic stderr-only lines do not prevent `STALL_DETECTED` at the configured budget, and that periodic stdout still completes without stall.
  - `tests/core/test_smart_stall.py` — TARGET only if smart-stall sampling still counts stderr bytes; stderr must not be enough to keep a silent-stdout stream below the trip path forever.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document that streaming liveness is stdout (not stderr), default stall is 900s, EXECUTE override is 3600s, and `AGENT_TIMEOUT` is the harness verdict for a hung GREEN. Replace the stale `STREAM_STALL_TIMEOUT_SECONDS = 60` wording if it is still present.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible hang fix.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - GitHub #61: `deviate micro run` GREEN (`pi -p`) hung 30–41+ minutes with zero events after `INVOKE_AGENT`. Direct `pi -p` of the same prompt finished in 4–12 minutes with a valid manifest. The 900s stall detector never fired `AGENT_TIMEOUT`.
  - `_invoke_streaming` `read_stderr` resets `stall_deadline[0] = time.monotonic() + stall_timeout_secs` on any stderr line.
  - Smart-stall `byte_rate_below_floor` requires `len(byte_samples) >= 3` inside `STREAM_STALL_WINDOW_SECONDS` (60s). One stderr line per ~75s never qualifies.
  - `invoke()` catches `AgentTimeoutError`, `time.sleep(30)`, then dispatches a full retry. 900 + 30 + 900 ≈ 1830s, matching a typical operator bash timeout of 1800s, so the outer kill wins.
  - GH-53 already raised EXECUTE stall to 3600s via per-invocation `stall_timeout`; that contract must remain.

## The Problem Contract

A hung GREEN `pi -p` child can emit occasional stderr diagnostics while producing no stdout progress. The streaming stall watchdog treats that noise as liveness, so the 900s hard deadline never expires and `_invoke_agent` never logs `AGENT_TIMEOUT`. Operators need the harness to declare the stall itself, without killing a healthy GREEN that is quiet for a few minutes of model think time, and without shrinking EXECUTE's one-hour silent-pipeline allowance.

## Scope Boundaries

### Hard Inclusions

- Stderr lines collected by `_invoke_streaming` must not reset the hard `stall_deadline`. Treat stderr as diagnostic unless a later, documented policy explicitly opts a stream into liveness.
- A streaming GREEN invoke with no meaningful stdout for the configured stall budget (default 900s; tests may patch a short budget) must raise `AgentTimeoutError` whose message includes `STALL_DETECTED` (or the existing stall token) and must cause `_invoke_agent` to log `AGENT_TIMEOUT`.
- After a stdout-silent stall, the harness must surface that `AGENT_TIMEOUT` without waiting for an outer ~1800s bash timeout. A second full 900s stall retry plus 30s sleep must not be what decides the operator-visible outcome.
- Periodic stdout still resets the hard deadline so a healthy GREEN that emits progress, or that is silent for only a few minutes of think time inside the 900s budget, is not killed.
- EXECUTE continues to pass `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600). Do not reopen GH-53 except to compose.
- `partial_stderr` / `partial_stdout` on `AgentTimeoutError` still capture whatever was seen (including diagnostic stderr).
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests stay fast: patch `STREAM_STALL_TIMEOUT_SECONDS` / pass a tiny `stall_timeout` as existing stall tests do. Do not sleep 900s in CI.

### Defensive Exclusions

- Do **not** reopen GitHub #53 except to compose: EXECUTE stall stays 3600s; do not fold EXECUTE back to 900s.
- Do **not** reopen GitHub #54 / #62 / #63 / #65 / #74 (session re-key, JUDGE evidence, RED SHA / GREEN-entry, already_satisfied files) except to compose.
- Do **not** make the interactive stall so aggressive that a healthy GREEN quiet for a few minutes of model think time is killed. Do not drop the default GREEN budget from 900s to a multi-minute think-unsafe value.
- Do **not** treat stderr as a second liveness channel, a TUI event stream, or RPC progress. This slice is the CLI `pi -p` streaming watchdog (`pi_rpc=false`).
- Do **not** author, repair, or index Product-layer flows (`flow_refs: []`). FLOW-04 is RPC TUI live-stream, not stall-clock policy.
- Do **not** delete branches, mutate operator-local `.deviate/config.toml` (`backend=pi`, `transport=cli`, `pi_rpc=false`, `timeout=1800`, `models.default=grok-4.6`, `timeout_seconds=1800`), or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** change TSK id format, ledger append-only rules, or invent a second issue-id series.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-025`
- **Acceptance Criteria Tokens**: `AC-ADHOC-025-01`, `AC-ADHOC-025-02`, `AC-ADHOC-025-03`
- **Data Model Entities**: `AgentTimeoutError.partial_stdout`, `AgentTimeoutError.partial_stderr` — no new ledger row types
- **Spec Source Anchors**:
  - `src/deviate/core/agent.py` `_invoke_streaming` / `invoke` / `STREAM_STALL_TIMEOUT_SECONDS`
  - `src/deviate/cli/micro.py` `_invoke_agent` (`AGENT_TIMEOUT`) / `EXECUTE_STALL_TIMEOUT_SECONDS`
  - `specs/constitution.md` §3 Testing Protocols; §5 Definition of Done (CHANGELOG for user-visible bug fix)
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` Agent Backend Hardening / Streaming stall watchdog (currently still say `60` in places)

## User Stories Ledger

- **US-025-01**: As a DeviaTDD operator running GREEN via `pi -p`, I want periodic stderr noise not to keep the stall clock alive so a hung agent cannot run indefinitely. *(Ref: FR-ADHOC-025)*
- **US-025-02**: As a DeviaTDD operator, I want a hung GREEN to log `AGENT_TIMEOUT` from the harness so I do not wait for an outer bash kill. *(Ref: FR-ADHOC-025)*
- **US-025-03**: As a DeviaTDD operator, I want EXECUTE to keep its one-hour stall allowance and a healthy GREEN that is quiet while the model thinks for a few minutes to survive. *(Ref: FR-ADHOC-025)*

## Acceptance Outline

- **AO-025-01** *(Ref: AC-ADHOC-025-01, US-025-01)*: Stderr is not liveness for the hard stall clock.
  - **Happy Path**: `_invoke_streaming` with a patched short `stall_timeout`, blocking/empty stdout, and stderr lines arriving on an interval shorter than that budget still raises `AgentTimeoutError` matching `STALL_DETECTED` at the configured budget.
  - **Error Category**: Resetting `stall_deadline` on those stderr lines so the invoke runs until an outer timeout is a failure of this slice.
  - **Boundary Category**: Captured `partial_stderr` still contains the diagnostic lines. Smart-stall must not treat sparse stderr as enough activity to suppress the hard-deadline trip forever.

- **AO-025-02** *(Ref: AC-ADHOC-025-02, US-025-02)*: The harness owns the hung-GREEN verdict.
  - **Happy Path**: GREEN `_invoke_agent` / `AgentBackend.invoke` on a stdout-silent stall logs `AGENT_TIMEOUT` (with `error=` and partial streams) without needing an outer ~1800s bash timeout to fire first.
  - **Error Category**: Sleeping 30s and retrying a second full 900s stall so the operator only sees a bash kill is a failure.
  - **Boundary Category**: A later documented retry remains legal only if the operator-visible `AGENT_TIMEOUT` still occurs inside the interactive stall budget plus small in-process slack, well under 1800s.

- **AO-025-03** *(Ref: AC-ADHOC-025-03, US-025-03)*: EXECUTE 3600s and think-time GREEN stay composed.
  - **Happy Path**: EXECUTE still passes `stall_timeout=3600`. A streaming invoke that emits periodic stdout within the 900s GREEN budget completes without `STALL_DETECTED`. A few minutes of stdout silence inside that 900s budget does not trip the detector.
  - **Error Category**: Collapsing EXECUTE to 900s, or lowering the default GREEN budget so multi-minute think time dies, is a failure.
  - **Boundary Category**: API / architecture / CHANGELOG update in the same implementation commit. Existing GH-53 override pin remains green.

## Edge Cases and Boundaries

- Pi stderr of the form `[codebase-index] Background reindex failed` (and similar index/heartbeat noise) is the motivating diagnostic class; the rule is stream-based (stderr vs stdout), not a denylist of message strings.
- Empty stderr with silent stdout still trips the existing stall pin.
- Smart-stall (`>=3` samples / 60s / 50 B/s) stays a secondary gate; this slice does not require making smart-stall fire on sparse stderr.
- RPC / `pi_rpc=true` dispatch is out of this slice; do not retune `_invoke_rpc_blocking` unless it shares the stderr-reset bug and blocking the CLI path requires the same helper.
- Operator-local `.deviate/config.toml` timeout 1800s is context for the race, not a value this slice should rewrite.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: stall trip must occur at the configured `stall_timeout` plus small poll slack (`_invoke_streaming` sleeps 0.05s per loop), not at 1830s+ and not at an outer bash deadline.
- Throughput: no extra agent calls on the healthy path. Full test suite remains < 30s; stall tests use patched millisecond-to-sub-second budgets, never a live 900s wait. Mock `deviate.cli.micro._run_pytest` if a CLI path would spawn it.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_core/test_agent.py::test_streaming_agent_detects_stdout_stall` — keep the silent-stream pin.
  - `tests/test_core/test_agent.py::test_streaming_agent_stall_timeout_override_is_honored` — keep the GH-53 override pin (message cites the per-invoke budget, not the module constant).
  - `tests/test_core/test_agent.py` — new pin: stderr-only periodic lines + silent stdout → `AgentTimeoutError` / `STALL_DETECTED` at the patched budget (deadline must not refresh on stderr).
  - `tests/test_core/test_agent.py::test_streaming_agent_output_completes_without_stall` — keep: stdout progress still completes.
  - Optional: `tests/test_cli/test_micro.py` or `tests/test_core/test_agent.py` — stdout-silent stall through `invoke` / `_invoke_agent` records `AGENT_TIMEOUT` without a second full stall budget.
- **Integration Sandbox Targets**:
  - Not a live `pi -p` hang. Mocked `Popen` pipes are sufficient. If a micro CLI test is added, mock the agent backend and `deviate.cli.micro._run_pytest` so the suite stays under 30s.

## Demonstration Path

```bash
# Mocked streaming stall pins (no live agent, no 900s sleep)
uv run pytest tests/test_core/test_agent.py tests/core/test_smart_stall.py -q -k "stall"
```
