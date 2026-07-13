---
title: "RPC Streaming TUI Renderer — Pi/OMP backends on full JSON-RPC, streaming tool_call / tool_result / thinking / delta / lifecycle into a fixed 10-line live region (FLOW-04 end-to-end)"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-012
flow_refs: [FLOW-04]
---

> **Decisions taken (correctable in one reply):**
> 1. **Backend matrix = Pi AND OMP**, both wired end-to-end in this issue.
> 2. **C5 RPC adapter is in scope** — the backends switch from subprocess/CLI to JSON-RPC and emit `AgentEvent` onto the wire. The renderer alone is no longer the deliverable; the full C5→C6 vertical must land.
> 3. **Recorded capture regression** — `src/deviate/rpc/captures/{pi_run,omp_run}.jsonl` (≥ 1,000 frames each) drive the C5 side. No live Pi/OMP server required in CI.
> 4. **JSONL replay harness** — `python -m deviate.ui.replay --fixture <path>` remains the AC regression for the renderer side and the human-observable demo path.

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/012-rpc-streaming-tui-renderer.md`
- **Primary Architectural Workstation**:
  **C5 — RPC adapter (NEW, in scope):**
  - `src/deviate/rpc/__init__.py` (new — package init, exports `connect`, `RpcStream`, `parse_line`)
  - `src/deviate/rpc/client.py` (new — JSON-RPC 2.0 client: `connect(uri) -> RpcStream`; `RpcStream.events() -> Iterator[AgentEvent]`; handles line-delimited JSON over stdin/stdout subprocess today, with a transport seam that admits Unix-socket and stdio-tty variants later)
  - `src/deviate/rpc/protocol.py` (new — wire schema for the seven `AgentEvent.kind` literals, JSON-RPC 2.0 request/notification envelopes, `parse_line(raw: str) -> AgentEvent` decoder with explicit error mapping for malformed frames)
  - `src/deviate/rpc/captures/pi_run.jsonl` (new — recorded RPC capture, ≥ 1,000 frames, captured against the Pi binary during slice acceptance)
  - `src/deviate/rpc/captures/omp_run.jsonl` (new — recorded RPC capture, ≥ 1,000 frames, captured against the OMP binary during slice acceptance)
  - `src/deviate/rpc/captures/CAPTURE_README.md` (new — capture procedure: how to regenerate each fixture against a live backend, expected frame schema, gitignore rules)
  **Backend substitution (NEW, in scope):**
  - `src/deviate/core/agent.py` (existing — `Agent.invoke` / `invoke_streaming`. The slice routes through `rpc.connect(...)` when the backend declares `transport = "rpc"` in `[models]`, falling back to the existing CLI path otherwise. Both Pi and OMP go through the same adapter.)
  - `src/deviate/state/config.py` (existing — `[models]` schema gains `transport: Literal["rpc", "cli"]` (default `"rpc"` for Pi, `"rpc"` for OMP); a `legacy_cli_fallback: bool = True` flag preserves the current subprocess path so non-RPC agents keep working)
  **C6 — Renderer (was the previous slice):**
  - `src/deviate/tui/__init__.py` (new — package init)
  - `src/deviate/tui/events.py` (new — `AgentEvent` dataclass + `TerminalKind` enum per `specs/_product/domain-model.md:58-83,93-98`)
  - `src/deviate/tui/renderer.py` (new — `Renderer(feed/flush_summary)` per `specs/_product/architecture.md:62-66`)
  - `src/deviate/ui/replay.py` (new — `python -m deviate.ui.replay --fixture <path>` JSONL harness)
  - `src/deviate/ui/render.py` (existing — consume `stdout_lock` at `:26-30` and `is_interactive()` at `:40-46`)
  - `src/deviate/ui/monitor.py` (existing — `OrchestrationMonitor.push_event("agent_output", …)` at `:87-101`; the slice adds `OrchestrationMonitor.set_output_sink(callable | None)` as the injection point)
  **Test surface (C5 + C6):**
  - `tests/test_tui/__init__.py` (new — test package)
  - `tests/test_tui/conftest.py` (new — `captured_console` fixture built on `rich.console.Console(file=io.StringIO())`, autouse `mock_tty` that monkey-patches `os.isatty` to `True`, plus a `recorded_rpc_stream` fixture that yields `RpcStream.events()` from `src/deviate/rpc/captures/*.jsonl`)
  - `tests/test_tui/test_events.py` (new — `AgentEvent` validation + `TerminalKind` enum)
  - `tests/test_tui/test_protocol.py` (new — JSON-RPC 2.0 envelope parsing, `parse_line` round-trips for every `kind` literal, malformed-frame error mapping)
  - `tests/test_tui/test_renderer.py` (new — RED/GREEN regression suite covering AC-ADHOC-012-01, -02, -03, -04, -05, -06)
  - `tests/test_tui/test_monitor_wire.py` (new — wires `OrchestrationMonitor.set_output_sink(renderer.feed)` and asserts the renderer's ring buffer reflects the last N lines)
  - `tests/test_tui/test_replay.py` (new — replays `tests/fixtures/streaming/sample_agent_events.jsonl` end-to-end and asserts the captured console never exceeds 10 lines)
  - `tests/test_tui/test_rpc_wire.py` (new — drives `RpcStream.events()` from the recorded capture and asserts: (a) all seven `kind` literals round-trip through `AgentEvent`, (b) the resulting stream feeds a `Renderer` and the captured console shows tool_call / tool_result / thinking / delta / lifecycle events correctly, (c) thread-safety holds across the RPC→Renderer boundary, (d) end-to-end with both Pi and OMP captures)
  - `tests/test_tui/test_backend_substitution.py` (new — asserts `[models]` parses `transport = "rpc"` for both Pi and OMP, and that the legacy CLI path is preserved when `legacy_cli_fallback = True`)
  - `tests/fixtures/streaming/sample_agent_events.jsonl` (new — ≥ 1,000 valid JSONL `AgentEvent` records for AC-ADHOC-012-06 regression)
  - `CHANGELOG.md` (existing — append `[Unreleased] → Added` bullet per AGENTS.md §CHANGELOG Discipline; the `9cccaaf` commit that birthed this issue forgot the bullet)

## The Problem Contract
Deliver the **full** FLOW-04 vertical slice, end to end:

1. **C5 — Replace subprocess/CLI with JSON-RPC.** Both the Pi and OMP agent backends stop spawning their respective binaries through stdout subprocess and `subprocess.run(...)`. Instead, they speak JSON-RPC 2.0 over the existing transport (stdin/stdio for now; the seam is shaped so a future Unix-socket transport can drop in). Each backend emits the seven `AgentEvent.kind` literals (`text`, `tool_call`, `tool_result`, `thinking`, `delta`, `lifecycle`, `unknown`) as it runs.
2. **C5→C6 wire — `RpcStream.events()` → `OrchestrationMonitor.set_output_sink(renderer.feed)`.** The adapter yields parsed `AgentEvent` instances into the existing `OrchestrationMonitor.dispatch` path. The renderer is unchanged in contract: `Renderer(max_lines: int = 10)`, `renderer.feed(event: AgentEvent) -> None`, `renderer.flush_summary(text: str) -> None`.
3. **C6 — Live 10-line region.** On a TTY, the renderer redraws a fixed Rich region in place; on non-TTY / `CI=1`, it falls back to plain `print()` and emits only the final summary.
4. **Recorded capture regression.** The RPC adapter is verified against recorded captures (`src/deviate/rpc/captures/pi_run.jsonl`, `src/deviate/rpc/captures/omp_run.jsonl`) so no live Pi/OMP server is needed in CI. The renderer side also has its own JSONL replay harness for fast iteration.
5. **PR-observable end state.** When this slice ships, running `deviate run` (or `python -m deviate.ui.replay`) with either backend configured in `[models]` shows a live, in-place 10-line window of normalized Pi/OMP progress — tool calls mid-flight, tool results landing, reasoning chunks, lifecycle transitions — instead of a flood of plain stdout text.

## Scope Boundaries
### Hard Inclusions
- **C5 — RPC package + protocol** (`src/deviate/rpc/{__init__,client,protocol}.py`):
  - `connect(uri: str) -> RpcStream` opens a JSON-RPC 2.0 stream; transport defaults to stdio subprocess (the only transport shipped now), but the seam (a `Transport` protocol class) admits Unix-socket / WS later.
  - `RpcStream.events()` returns a blocking iterator of `AgentEvent` parsed from line-delimited JSON frames. Generator raises `RpcProtocolError` on malformed frames and `RpcConnectionError` on EOF with no graceful close.
  - `parse_line(raw: str) -> AgentEvent` decodes a single JSON-RPC `notification` (no `id`) into an `AgentEvent`. Each of the seven `kind` literals must have a matching payload schema documented inline; anything else maps to `kind="unknown"`.
  - Frames the protocol does not yet understand map to `kind="unknown"` with the raw JSON in `payload["raw"]`. The wire is forward-compatible.
  - `AgentEvent` carries `timestamp: datetime` (UTC, ISO-8601) so a recorded capture can be replayed deterministically.
- **C5 — Recorded captures** (`src/deviate/rpc/captures/`):
  - `pi_run.jsonl` and `omp_run.jsonl`, ≥ 1,000 frames each, captured against a real backend during slice acceptance. Schemas pinned in `CAPTURE_README.md`. Files checked into git (small JSONL, no PII).
  - Regeneration procedure documented: `python -m deviate.tools.recapture --backend pi` (or `omp`) requires the relevant CLI on `$PATH` and writes a fresh JSONL plus a SHA-256 checksum; the test fixture loader asserts the checksum matches the recorded one so accidental regression is caught.
- **Backend substitution** (`src/deviate/core/agent.py`, `src/deviate/state/config.py`):
  - `[models]` accepts `transport: Literal["rpc", "cli"]` (default `"rpc"` for Pi and OMP) and `rpc_uri: Optional[str]`. When `transport == "rpc"`, the agent routes through `rpc.connect(rpc_uri or default_uri(backend))`.
  - `legacy_cli_fallback: bool = True` keeps the existing subprocess path alive so any agent backend that hasn't been ported to RPC keeps working. Default behavior with no `[models]` section unchanged.
  - Both Pi and OMP route through the same `RpcStream` abstraction; per-backend differences (CLI flags, env, default URI) live in `state/config.py`, not in the RPC layer.
- **C6 — Renderer** (`src/deviate/tui/{events,renderer}.py`, `src/deviate/ui/{monitor,replay}.py`):
  - `AgentEvent` dataclass with `kind: Literal["text","tool_call","tool_result","thinking","delta","lifecycle","unknown"]`, `payload: dict[str, Any]`, `timestamp: datetime`.
  - `TerminalKind` enum (`TUI | PIPE`) per `specs/_product/domain-model.md:93-98`.
  - `Renderer(max_lines: int = 10)` constructor; `renderer.feed(event: AgentEvent) -> None`; `renderer.flush_summary(text: str) -> None`; validates `max_lines >= 1` (zero/negative raises `ValueError`).
  - In-place redraw of a fixed Rich region, capped at `max_lines`, default 10. Uses Rich primitives already declared in `pyproject.toml:32` (`rich>=13.0`). Class selection (`Live` / `Layout` / `Group`) is a RED/GREEN decision.
  - `flush_summary(text)` clears the live region and prints `text` to stdout beneath the cleared cursor position.
  - `OrchestrationMonitor.set_output_sink(callable | None)`. The sink invocation is inserted **inside** the existing early-return block at `src/deviate/ui/monitor.py:89-94` (between `_agent_output_buffer.append(line)` at `:93` and `return` at `:94`). Wire is one-direction (monitor → renderer); the renderer never imports `OrchestrationMonitor`. Sink is wrapped in `try/except` so it can never propagate into the orchestration loop. Default sink is `None`; existing behavior preserved.
  - Replay harness `python -m deviate.ui.replay --fixture <path>` streams a JSONL `AgentEvent` fixture into `Renderer.feed` directly (not via `OrchestrationMonitor`) sleeping 5 ms between events so a developer watching the terminal sees the live redraw.
- **Test surface**:
  - `tests/test_tui/test_protocol.py` covers the wire schema, `parse_line` round-trips for every `kind` literal, and malformed-frame error mapping.
  - `tests/test_tui/test_rpc_wire.py` drives the recorded captures end-to-end through `RpcStream.events()` → `Renderer.feed` and asserts correct rendering of every event kind.
  - `tests/test_tui/test_backend_substitution.py` exercises the `[models] transport = ...` parse and the legacy fallback.
  - Renderer suite, monitor-wire suite, replay suite as in the previous slice.
- **`tests/fixtures/streaming/sample_agent_events.jsonl`** with ≥ 1,000 valid `AgentEvent` records for AC-ADHOC-012-06 regression. Renderer-side corpus, separate from the two backend captures in `src/deviate/rpc/captures/`.
- **Append `[Unreleased] → Added` bullet to `CHANGELOG.md`** per AGENTS.md §CHANGELOG Discipline. User-visible new components: `Renderer`, `AgentEvent`, `Monitor.set_output_sink`, `deviate.ui.replay`, `deviate.rpc.{client,protocol,connect}`, `RpcStream`, `[models] transport` field, Pi and OMP transport = `"rpc"` by default.

### Defensive Exclusions
- **No live Pi/OMP servers in CI.** All RPC verification goes through recorded captures. The recapture tool is shipped but never invoked in CI.
- **No TCP/WS transport.** Only stdio today; the `Transport` protocol seam is in place but no implementation other than stdio ships.
- **No reconnect / retry policy for an RPC session.** First `RpcConnectionError` propagates to the caller. Reconnection is a separate slice.
- **No OMP-specific RPC flag mapping.** Both backends go through the same `RpcStream`; per-backend tuning lives in `state/config.py` and is not part of this issue.
- **No new `--agent {pi,omp}` CLI flag.** The existing resolution path continues; `transport` switches occur in config.
- **No replacement of the existing `src/deviate/ui/pipeline.py` widgets** (`PipelineBanner`, `RunBoard`, `TrainIndicator`, `PipelineSummary`). The new `Renderer` is a peer, not a refactor.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-012`
- **Acceptance Criteria Tokens**: `AC-ADHOC-012-01`, `AC-ADHOC-012-02`, `AC-ADHOC-012-03`, `AC-ADHOC-012-04`, `AC-ADHOC-012-05`, `AC-ADHOC-012-06`, `AC-ADHOC-012-07`, `AC-ADHOC-012-08`, `AC-ADHOC-012-09`
- **Data Model Entities**: `TuiRenderer` (`specs/_product/domain-model.md:85-92`), `Terminal` (`:93-98`), `AgentEvent` (`:58-83`)
- **Architecture Contract**: `Renderer(max_lines: int = 10) -> Renderer`, `renderer.feed(event: Event) -> None`, `renderer.flush_summary(text: str) -> None` (`specs/_product/architecture.md:62-66`)

## User Stories Ledger

- **US-012-01**: As a developer running `deviate run` against the Pi backend, I want Pi's tool calls, tool results, reasoning, and lifecycle events to stream into a fixed 10-line live region that redraws in place, so I can watch progress without scrolling. *(Ref: FR-ADHOC-012)*
- **US-012-02**: As a developer running `deviate run` against the OMP backend, I want the same live-region behavior, so the TUI experience is identical across backends. *(Ref: FR-ADHOC-012)*
- **US-012-03**: As a developer running CI or piping output, I want the live region to be skipped automatically and only the final summary emitted, so pipelines stay parseable. *(Ref: FR-ADHOC-012)*
- **US-012-04**: As a maintainer, I want the RPC adapter to run against recorded captures (not live servers), so the test suite stays < 30 s and CI never needs network access to Pi/OMP. *(Ref: FR-ADHOC-012)*
- **US-012-05**: As a developer, I want the TUI renderer to accept `AgentEvent` instances through a typed `Renderer.feed()` API and a `Monitor.set_output_sink()` injection seam, so the C5→C6 boundary is testable in isolation. *(Ref: FR-ADHOC-012)*
- **US-012-06**: As a maintainer, I want a recorded-JSONL replay harness (`python -m deviate.ui.replay --fixture …`), so the AC regression exercises the renderer without subprocess overhead and humans can see the live redraw during development. *(Ref: FR-ADHOC-012)*
- **US-012-07**: As a user, I want the legacy subprocess path to keep working when I set `transport = "cli"` in `[models]`, so backends that haven't been ported to RPC are not silently broken. *(Ref: FR-ADHOC-012)*

## ATDD Acceptance Criteria

**Scenario 012-01: Live region renders last N events in fixed region**
**Given** a `Renderer(max_lines=10)` constructed with a captured Rich `Console`
**When** 15 `AgentEvent` instances are fed sequentially via `renderer.feed(event)`
**Then** the final captured render contains exactly the last 10 events; region height never exceeds 10 lines across the 15 captures

**Scenario 012-02: Region clears and summary prints on flush**
**Given** a `Renderer` that has received 5 events on a captured `Console`
**When** `renderer.flush_summary("Final report")` is called
**Then** the captured stream contains a clear-region sequence followed by the literal `Final report`

**Scenario 012-03: Non-TTY output skips live region**
**Given** stdout is not a TTY or `CI=1` is set
**When** `renderer.feed(event)` is called repeatedly and then `flush_summary("done")` is called
**Then** the captured stdout contains no Rich-region escape sequences; only the final summary line is written

**Scenario 012-04: Thread safety through stdout_lock**
**Given** two threads concurrently calling `renderer.feed(event)` 500 times each
**When** both threads join
**Then** all writes serialize through `stdout_lock`; the captured `Console.get()` output contains 1,000 well-formed event lines with no interleaved bytes

**Scenario 012-05: OrchestrationMonitor → Renderer.feed wire**
**Given** an `OrchestrationMonitor` whose `set_output_sink(renderer.feed)` has been wired
**When** `monitor.push_event("agent_output", line=f"step {i}")` runs for `i in range(25)`
**Then** `renderer._buffer` length is `min(25, max_lines)` and the retained items are `["step 15", …, "step 24"]` in order

**Scenario 012-06: Redraw budget — 1,000 events within 10-line cap (release-next AC §4)**
**Given** `Renderer(max_lines=10)` and the recorded fixture at `tests/fixtures/streaming/sample_agent_events.jsonl` (≥ 1,000 valid `AgentEvent` lines)
**When** the RED/GREEN replay test feeds the full fixture into `renderer.feed`
**Then** the rendered region never exceeds 10 lines; the suite remains < 30 s (mocked at the `Renderer.feed` boundary, no subprocess)

**Scenario 012-07: RPC adapter parses all seven AgentEvent kinds from a Pi capture**  *(NEW, C5)*
**Given** `src/deviate/rpc/captures/pi_run.jsonl` (≥ 1,000 frames covering every `kind` literal at least once)
**When** a `RpcStream.events()` iterator is driven through `parse_line` for every line
**Then** every frame decodes to a valid `AgentEvent` with a non-empty payload, every `kind` literal appears at least once in the resulting sequence, and timestamps are monotonically non-decreasing

**Scenario 012-08: RPC adapter parses all seven AgentEvent kinds from an OMP capture**  *(NEW, C5)*
**Given** `src/deviate/rpc/captures/omp_run.jsonl` (≥ 1,000 frames covering every `kind` literal at least once)
**When** a `RpcStream.events()` iterator is driven through `parse_line` for every line
**Then** the same invariants as Scenario 012-07 hold for the OMP capture

**Scenario 012-09: End-to-end RPC → Renderer live region**  *(NEW, C5→C6)*
**Given** a captured `RpcStream.events()` for both Pi and OMP, wired through `OrchestrationMonitor.set_output_sink(renderer.feed)` with `Renderer(max_lines=10)`
**When** the stream is consumed to completion on a captured `Console`
**Then** the captured output shows at least one of each `kind` literal rendered in region, the region never exceeds 10 lines, and `renderer.flush_summary("done")` clears the region and appends `done`

## Edge Cases and Boundaries

- **`max_lines == 0`** — `Renderer.__init__` raises `ValueError`.
- **`max_lines == 1`** — Region is exactly 1 line; every feed replaces the prior line in place.
- **Zero events fed before `flush_summary`** — no live region to clear; only the final summary prints, no preamble.
- **`AgentEvent(kind="unknown")`** — renders as the literal `…` without raising.
- **`AgentEvent` with empty `payload`** — renders the `kind` label only.
- **Feed after flush** — subsequent feeds redraw a new live region above the prior summary; a second `flush_summary` appends below the prior summary.
- **Concurrent `flush_summary` + `feed`** — serialized through `stdout_lock`; no partial clears.
- **Unicode content inside `payload["line"]`** — rendered as UTF-8 via Rich default; no encoding coercion.
- **Terminal resize between redraws** — Rich handles natively.
- **Replay fixture missing or empty** — `replay.py` exits with code 2 and a clear stderr message; does not hang.
- **`set_output_sink(None)`** — restores pre-existing monitor behavior (no sink dispatch); idempotent.
- **Sink raises** — `OrchestrationMonitor.push_event` swallows and logs the sink error rather than propagating.
- **Malformed JSON-RPC frame** — `parse_line` raises `RpcProtocolError` with a useful message; the test suite asserts this for both `"not json"` and `{"valid json but wrong shape"}`.
- **RPC subprocess EOF with no notification** — `RpcStream.events()` raises `RpcConnectionError`; the monitor's existing error path logs and continues.
- **`transport = "cli"` set in `[models]`** — the agent takes the legacy subprocess path; no `rpc.connect` call; pre-012 behavior preserved byte-for-byte.
- **Backend not in `[models]`** — defaults to `"rpc"` for Pi and OMP (existing resolution rules apply).

## Performance Constraints

- `tui_redraw_latency_ms` p95 ≤ 100 per FLOW-04 metrics (`specs/_product/flows/flows-streaming.md`)
- Rendered region: max `max_lines` lines (default 10), in-place redraw only — never append, never grow
- Full `mise run test` suite stays < 30 s (AGENTS.md). Budgets:
  - `tests/test_tui/test_renderer.py` < 2 s
  - `tests/test_tui/test_protocol.py` < 1 s
  - `tests/test_tui/test_rpc_wire.py` < 5 s (drives 1,000-frame captures)
  - `tests/test_tui/test_replay.py` < 4 s (1,000-event fixture, mocked at `Renderer.feed`)
  - Remaining new tests < 2 s combined
- `python -m deviate.ui.replay` on the 1,000-event fixture finishes in < 6 s wall time
- `RpcStream` consumer adds < 1 ms p95 per frame relative to subprocess stdout (the wire is `readline` + `json.loads`); measured with a synthetic producer in a test, not against a live backend

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/test_tui/test_events.py::test_agent_event_kind_literal_validates`
  - `tests/test_tui/test_events.py::test_agent_event_payload_defaults_to_empty_dict`
  - `tests/test_tui/test_events.py::test_terminal_kind_enum_values`
  - `tests/test_tui/test_protocol.py::test_parse_line_round_trips_every_kind_literal`
  - `tests/test_tui/test_protocol.py::test_parse_line_unknown_kind_maps_to_unknown`
  - `tests/test_tui/test_protocol.py::test_parse_line_malformed_frame_raises`
  - `tests/test_tui/test_renderer.py::test_renderer_accepts_event_15_renders_last_10`
  - `tests/test_tui/test_renderer.py::test_renderer_flush_summary_clears`
  - `tests/test_tui/test_renderer.py::test_renderer_non_tty_skips_live_region`
  - `tests/test_tui/test_renderer.py::test_renderer_unknown_event_renders_ellipsis`
  - `tests/test_tui/test_renderer.py::test_renderer_max_lines_zero_raises`
  - `tests/test_tui/test_renderer.py::test_renderer_max_lines_one_replaces_in_place`
  - `tests/test_tui/test_monitor_wire.py::test_monitor_set_output_sink_receives_agent_output_lines`
  - `tests/test_tui/test_monitor_wire.py::test_monitor_25_agent_output_calls_keep_last_max_lines`
  - `tests/test_tui/test_backend_substitution.py::test_models_section_parses_transport_field`
  - `tests/test_tui/test_backend_substitution.py::test_legacy_cli_fallback_preserves_subprocess_path`
- **Integration Sandbox Targets**:
  - `tests/test_tui/test_renderer.py::test_renderer_threads_serialize_through_stdout_lock`
  - `tests/test_tui/test_replay.py::test_replay_fixture_ingests_1000_events_into_10_line_region`
  - `tests/test_tui/test_replay.py::test_replay_writes_final_summary_after_clear`
  - `tests/test_tui/test_rpc_wire.py::test_pi_capture_round_trips_through_agent_event`
  - `tests/test_tui/test_rpc_wire.py::test_omp_capture_round_trips_through_agent_event`
  - `tests/test_tui/test_rpc_wire.py::test_pi_capture_drives_renderer_live_region_end_to_end`
  - `tests/test_tui/test_rpc_wire.py::test_omp_capture_drives_renderer_live_region_end_to_end`
  - `tests/test_tui/test_rpc_wire.py::test_rpc_to_renderer_threads_serialize`

## Demonstration Path
```bash
# Verify the full C5 + C6 RED/GREEN suite (RPC protocol, renderer, monitor wire, replay, end-to-end)
uv run pytest tests/test_tui/ -v

# Replay the recorded renderer-side JSONL stream; observe the 10-line region redrawing in place
python -m deviate.ui.replay --fixture tests/fixtures/streaming/sample_agent_events.jsonl

# Same replay in CI mode — only the final summary prints, no ANSI escapes
CI=1 python -m deviate.ui.replay --fixture tests/fixtures/streaming/sample_agent_events.jsonl

# Verify the [models] transport field parses for both backends
uv run pytest tests/test_tui/test_backend_substitution.py -v

# Full suite regression (must stay < 30s per AGENTS.md)
mise run test

# Lint check passes on all new code
mise run lint
```

## Out-of-Slice Notes
- The recapture tool (`python -m deviate.tools.recapture`) is sketched in `CAPTURE_README.md` but is **not** part of this issue. Once a maintainer needs to refresh a capture, they invoke the documented procedure manually.
- The `transport = "cli"` fallback path is verified by `test_legacy_cli_fallback_preserves_subprocess_path` (a direct test against the agent without an RPC loop), not by running the CI suite against live subprocesses.
