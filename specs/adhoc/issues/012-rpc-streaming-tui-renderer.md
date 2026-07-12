---
title: "TUI Renderer Vertical Slice — C5→C6 Wire + AgentEvent Model (FLOW-04 end-to-end)"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-012
flow_refs: [FLOW-04]
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/012-rpc-streaming-tui-renderer.md`
- **Primary Architectural Workstation**:
  - `src/deviate/tui/__init__.py` (new — package init)
  - `src/deviate/tui/events.py` (new — `AgentEvent` dataclass + `TerminalKind` enum per `specs/_product/domain-model.md:58-83,93-98`)
  - `src/deviate/tui/renderer.py` (new — `Renderer(feed/flush_summary)` per `specs/_product/architecture.md:62-66`)
  - `src/deviate/ui/replay.py` (new — `python -m deviate.ui.replay --fixture <path>` JSONL harness so a developer sees the live 10-line region without spawning a real Pi/OMP binary; placed under `ui/` because it ships alongside `monitor.py`, `pipeline.py`, and `render.py` — it is a developer-facing entry point for the UI package, not a `tui` internal)
  - `src/deviate/ui/render.py` (existing — consume `stdout_lock` at `:26-30` and `is_interactive()` at `:40-46`)
  - `src/deviate/ui/monitor.py` (existing — `OrchestrationMonitor.push_event("agent_output", …)` at `:87-101` is the in-process wire upstream of `Renderer.feed`; the slice adds `OrchestrationMonitor.set_output_sink(callable | None)` as the injection point)
  - `tests/test_tui/__init__.py` (new — test package)
  - `tests/test_tui/conftest.py` (new — `captured_console` fixture built on `rich.console.Console(file=io.StringIO())`, plus an autouse `mock_tty` fixture that monkey-patches `os.isatty` to `True`)
  - `tests/test_tui/test_events.py` (new — `AgentEvent` validation + `TerminalKind` enum)
  - `tests/test_tui/test_renderer.py` (new — RED/GREEN regression suite covering AC-ADHOC-012-01, -02, -03, -04, -05, -06)
  - `tests/test_tui/test_monitor_wire.py` (new — wires `OrchestrationMonitor.set_output_sink(renderer.feed)` and asserts the renderer's ring buffer reflects the last N lines)
  - `tests/test_tui/test_replay.py` (new — replays `tests/fixtures/streaming/sample_agent_events.jsonl` end-to-end and asserts the captured console never exceeds 10 lines)
  - `tests/fixtures/streaming/sample_agent_events.jsonl` (new — ≥ 1,000 valid JSONL `AgentEvent` records for AC-ADHOC-012-06 regression)
  - `CHANGELOG.md` (existing — append `[Unreleased] → Added` bullet per AGENTS.md §CHANGELOG Discipline; the `9cccaaf` commit that birthed this issue forgot the bullet)

## The Problem Contract
Deliver the smallest **vertically-sliced** FLOW-04 capability: the `AgentEvent` model + `TerminalKind` enum (declared at `specs/_product/domain-model.md:58-83,93-98`), the `Renderer` class (contract pinned at `specs/_product/architecture.md:62-66`), an in-process C5→C6 wire (`OrchestrationMonitor.push_event("agent_output", …)` → `Renderer.feed` via a new `OrchestrationMonitor.set_output_sink(callable | None)` injection point), and a recorded-JSONL replay harness. When GREEN lands, a developer running `python -m deviate.ui.replay --fixture tests/fixtures/streaming/sample_agent_events.jsonl` observes the last 10 lines of normalized activity redraw in place on a TTY and persist a final summary on completion — i.e., they **see the RPC streaming**. Real Pi/OMP subprocess plumbing (C2/C3/C4 of `specs/_product/architecture.md:11-78`) is deferred to companion slices; the renderer's only contract is `feed(event)`, and `OrchestrationMonitor` already produces caller-side events today (`src/deviate/ui/monitor.py:87-94`, `agent_output` buffering at `:61`).

## Scope Boundaries
### Hard Inclusions
- Define `AgentEvent` dataclass at `src/deviate/tui/events.py` matching `specs/_product/domain-model.md:58-83`: `kind: Literal["text","tool_call","tool_result","thinking","delta","lifecycle","unknown"]`, `payload: dict[str, Any]`, `timestamp: datetime`.
- Define `TerminalKind` enum at `src/deviate/tui/events.py` (`TUI | PIPE`) per `specs/_product/domain-model.md:93-98`.
- Define `Renderer` class at `src/deviate/tui/renderer.py` matching the verbatim contract at `specs/_product/architecture.md:62-66`: `Renderer(max_lines: int = 10) -> Renderer`, `renderer.feed(event: AgentEvent) -> None`, `renderer.flush_summary(text: str) -> None`; validate `max_lines >= 1` in `__init__` (zero/negative raises `ValueError`).
- Implement in-place redraw of a fixed Rich region (capped at `max_lines`, default 10) using Rich terminal primitives already declared in `pyproject.toml:32` (`rich>=13.0`); exact class selection (`Live` / `Layout` / `Group`) is a RED/GREEN decision per `specs/_product/architecture.md:66`.
- Implement `flush_summary(text)` that clears the live region and prints `text` to stdout beneath the cleared cursor position (append, not in place — so subsequent `feed` calls redraw a new live region above the summary).
- Add `OrchestrationMonitor.set_output_sink(callable | None)` at `src/deviate/ui/monitor.py` and wire it into `push_event("agent_output", …)` so registered sinks receive `AgentEvent(kind="text", payload={"line": line})`. Default sink is `None` (current behaviour preserved); wire is one-direction (monitor → renderer); the renderer must never import `OrchestrationMonitor`. **Critical: the sink invocation MUST be inserted inside the existing early-return block at `src/deviate/ui/monitor.py:89-94`** — specifically between the `_agent_output_buffer.append(line)` call at `:93` and the `return` at `:94`. Calling the sink anywhere after the `return` makes the wire dead code in the default (non-verbose) mode, which is the only mode most callers use. Concretely, the modified block reads:
  ```
  if event_type == "agent_output" and not self._verbose:
      if self._agent_output_buffer is not None:
          line = data.get("line", "")
          if line:
              self._agent_output_buffer.append(line)
              if self._output_sink is not None:
                  try:
                      self._output_sink(AgentEvent(kind="text", payload={"line": line}))
                  except Exception as exc:
                      console.print(f"[yellow]WARN: output sink raised: {exc}[/]")
      return
  ```
  The `try/except` is mandatory — the sink must never propagate an exception into the orchestration loop (preserves the existing `agent_output` buffering invariant at `:89-94`). The default-mode cap on `_agent_output_buffer` is `deque(maxlen=5)` at `monitor.py:61`; **the renderer does not rely on that deque as its source of truth** (the renderer maintains its own `max_lines` ring independent of monitor's 5-line cap), so the two caps are independently controllable.
- Integrate with the existing `stdout_lock` at `src/deviate/ui/render.py:26-30` for thread-safe writes (line range verified against the file; the previous draft cited `:24-30`, which was off-by-2 — the module-level `_stdout_lock = threading.Lock()` is at `:26`).
- Gate live-region rendering on `is_interactive()` at `src/deviate/ui/render.py:40-46`; non-TTY or `CI=1` falls back to plain `print()` final summary only — no ANSI/redraw sequences reach stdout.
- Ship `python -m deviate.ui.replay --fixture <path>` at `src/deviate/ui/replay.py` (placed under `ui/` so the command name `deviate.ui.replay` resolves unambiguously; matches the existing `ui/` siblings — `monitor.py`, `pipeline.py`, `render.py`): a thin CLI that streams a JSONL `AgentEvent` fixture into `Renderer.feed` line-by-line, sleeping 5 ms between events so a developer watching the terminal can observe the live redraw without spawning a real Pi/OMP binary. The harness calls `Renderer.feed` directly — it does NOT go through `OrchestrationMonitor.push_event` — so the AC §6 regression exercises the renderer in isolation and is unaffected by the `_agent_output_buffer` deque's smaller cap (see Hard Inclusion note under `set_output_sink` below).
- Ship `tests/fixtures/streaming/sample_agent_events.jsonl` with ≥ 1,000 valid `AgentEvent` records for AC-ADHOC-012-06 regression.
- Ship the regression tests described under Multi-Tiered Verification Targets below.
- Append `[Unreleased] → Added` bullet to `CHANGELOG.md` per AGENTS.md §CHANGELOG Discipline (user-visible new component: `Renderer`, `AgentEvent`, `Monitor.set_output_sink`, `deviate.ui.replay`).

### Defensive Exclusions
- **No real subprocess spawn of Pi or OMP.** C2/C3/C4 of `specs/_product/architecture.md:11-78` are owned by companion slices. The renderer's only contract is `feed(event)`; events come from `OrchestrationMonitor.push_event("agent_output", …)` or the recorded JSONL replay.
- **No greenfield C5 `src/deviate/rpc/events.py` adapter.** That adapter (per `specs/_product/architecture.md:44-58`) lives in a companion slice. This slice uses the existing `OrchestrationMonitor` dispatch as the upstream of the wire.
- **No reconnect / retry policy.** ADHOC A04.2 owns that path.
- **No OMP-specific RPC flag mapping.** ADHOC A04.1 owns it.
- **No `--agent {pi,omp}` CLI flag.** Infra I04.1 owns that wiring.
- **No `[models]` config extension for RPC args.** Infra I04.2 owns it.
- **No replacement of the existing `src/deviate/ui/pipeline.py` widgets** (`PipelineBanner`, `RunBoard`, `TrainIndicator`, `PipelineSummary`). The new `Renderer` is a peer, not a refactor of those.
- **No modification to `src/deviate/core/agent.py` or `src/deviate/state/config.py`** beyond the scope of this issue.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-012`
- **Acceptance Criteria Tokens**: `AC-ADHOC-012-01`, `AC-ADHOC-012-02`, `AC-ADHOC-012-03`, `AC-ADHOC-012-04`, `AC-ADHOC-012-05`, `AC-ADHOC-012-06`
- **Data Model Entities**: `TuiRenderer` (`specs/_product/domain-model.md:85-92`), `Terminal` (`:93-98`), `AgentEvent` (`:58-83`)
- **Architecture Contract**: `Renderer(max_lines: int = 10) -> Renderer`, `renderer.feed(event: Event) -> None`, `renderer.flush_summary(text: str) -> None` (`specs/_product/architecture.md:62-66`)

## User Stories Ledger

- **US-012-01**: As a developer, I want a fully-wired C5→C6 path so that running `deviate` (or `python -m deviate.ui.replay`) against an RPC-enabled agent shows live progress in a fixed 10-line region that redraws in place. *(Ref: FR-ADHOC-012)*
- **US-012-02**: As a developer running CI or piping output, I want the live region to be skipped automatically and only the final summary emitted so pipelines stay parseable. *(Ref: FR-ADHOC-012)*
- **US-012-03**: As a developer, I want the TUI renderer to accept `AgentEvent` instances through a typed `Renderer.feed()` API and a `Monitor.set_output_sink()` injection seam so future C5 adapter work has a minimal in-process hook. *(Ref: FR-ADHOC-012)*
- **US-012-04**: As a maintainer, I want a recorded-JSONL replay harness (`python -m deviate.ui.replay --fixture …`) so the AC §6 regression test exercises the C5→C6 path without subprocess overhead and the full suite stays < 30 s. *(Ref: FR-ADHOC-012)*

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

## Edge Cases and Boundaries

- **`max_lines == 0`** — `Renderer.__init__` raises `ValueError` (validate at construction; do not allow zero/negative).
- **`max_lines == 1`** — Region is exactly 1 line; every feed replaces the prior line in place.
- **Zero events fed before `flush_summary`** — no live region to clear; only the final summary prints, no preamble.
- **`AgentEvent(kind="unknown")`** — renders as the literal `…` without raising.
- **`AgentEvent` with empty `payload`** — renders the `kind` label only.
- **Feed after flush** — subsequent feeds redraw a new live region above the prior summary; a second `flush_summary` appends below the prior summary (not in place).
- **Concurrent `flush_summary` + `feed`** — serialized through `stdout_lock`; no partial clears.
- **Unicode content inside `payload["line"]`** — rendered as UTF-8 via Rich default; no encoding coercion.
- **Terminal resize between redraws** — Rich handles natively; no explicit handler needed for this slice.
- **Replay fixture missing or empty** — `replay.py` exits with code 2 and a clear stderr message; does not hang.
- **`set_output_sink(None)`** — restores pre-existing monitor behaviour (no sink dispatch); idempotent.
- **Sink raises** — `OrchestrationMonitor.push_event` swallows and logs the sink error rather than propagating (preserves current `agent_output` buffering invariant at `src/deviate/ui/monitor.py:89-94`).

## Performance Constraints

- `tui_redraw_latency_ms` p95 ≤ 100 per FLOW-04 metrics (`specs/_product/flows/flows-streaming.md`)
- Rendered region: max `max_lines` lines (default 10), in-place redraw only — never append, never grow
- Full `mise run test` suite stays < 30 s (AGENTS.md); the new `tests/test_tui/` package must complete in < 5 s because the harness feeds events directly to `Renderer.feed` (no subprocess, no blocking `Live.start()` on the test thread)
- `python -m deviate.ui.replay` on the 1,000-event fixture finishes in < 6 s wall time (5 ms × 1,000 events sleep budget + render overhead)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/test_tui/test_events.py::test_agent_event_kind_literal_validates`
  - `tests/test_tui/test_events.py::test_agent_event_payload_defaults_to_empty_dict`
  - `tests/test_tui/test_events.py::test_terminal_kind_enum_values`
  - `tests/test_tui/test_renderer.py::test_renderer_accepts_event_15_renders_last_10`
  - `tests/test_tui/test_renderer.py::test_renderer_flush_summary_clears`
  - `tests/test_tui/test_renderer.py::test_renderer_non_tty_skips_live_region`
  - `tests/test_tui/test_renderer.py::test_renderer_unknown_event_renders_ellipsis`
  - `tests/test_tui/test_renderer.py::test_renderer_max_lines_zero_raises`
  - `tests/test_tui/test_renderer.py::test_renderer_max_lines_one_replaces_in_place`
  - `tests/test_tui/test_monitor_wire.py::test_monitor_set_output_sink_receives_agent_output_lines`
  - `tests/test_tui/test_monitor_wire.py::test_monitor_25_agent_output_calls_keep_last_max_lines`
- **Integration Sandbox Targets**:
  - `tests/test_tui/test_renderer.py::test_renderer_threads_serialize_through_stdout_lock`
  - `tests/test_tui/test_replay.py::test_replay_fixture_ingests_1000_events_into_10_line_region`
  - `tests/test_tui/test_replay.py::test_replay_writes_final_summary_after_clear`

## Demonstration Path
```bash
# Verify the AgentEvent + Renderer RED/GREEN suite and the monitor wire
uv run pytest tests/test_tui/ -v

# Replay the recorded JSONL stream and observe the 10-line TUI region redrawing in place
python -m deviate.ui.replay --fixture tests/fixtures/streaming/sample_agent_events.jsonl

# Same replay in CI mode — only the final summary prints, no ANSI escapes
CI=1 python -m deviate.ui.replay --fixture tests/fixtures/streaming/sample_agent_events.jsonl

# Full suite regression (must stay < 30s per AGENTS.md)
mise run test

# Lint check passes on all new code
mise run lint
```
