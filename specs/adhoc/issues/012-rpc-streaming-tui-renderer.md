---
title: "TUI Renderer Component — Fixed-Region RPC Streaming Display (C6)"
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
  - `src/deviate/tui/renderer.py` (new — C6 TUI renderer)
  - `src/deviate/ui/render.py` (existing — consume `stdout_lock` for thread-safe redraw)
  - `src/deviate/ui/monitor.py` (existing — C5→C6 integration seam)
  - `tests/test_tui/test_renderer.py` (new — regression suite for AC §4 redraw budget)

## The Problem Contract
Deliver component C6 of FLOW-04: a Rich-based TUI renderer (`src/deviate/tui/renderer.py`) that renders the last N lines of normalized `AgentEvent` activity into a fixed terminal region and redraws in place on each event, capped at 10 lines max. On phase completion, the live region clears and a final summary persists. This is the smallest independently shippable slice of FLOW-04 — no subprocess plumbing, no RPC framing, no event adapter — just the typed `Renderer` contract consuming `Event` instances produced by a test harness or the future C5 adapter.

## Scope Boundaries
### Hard Inclusions
- Define `Renderer` class at `src/deviate/tui/renderer.py` with `__init__(max_lines: int = 10)`, `feed(event: Event) -> None`, and `flush_summary(text: str) -> None` matching the contract at `specs/_product/architecture.md:62-66`.
- Implement in-place redraw of a fixed Rich region (max 10 lines) on each `feed()` call, using Rich terminal primitives already declared in `pyproject.toml:32` (`rich>=13.0`).
- Implement `flush_summary(text)` that clears the live region and prints the final summary to stdout.
- Integrate with the existing `stdout_lock` at `src/deviate/ui/render.py:24-30` for thread-safe writes.
- Gate live-region rendering on `is_interactive()` (`src/deviate/ui/render.py:40-46`) — fall back to final-summary-only when stdout is not a TTY or `CI` env var is set.
- Ship a regression test at `tests/test_tui/test_renderer.py` that asserts the rendered region never exceeds 10 lines across 1,000 simulated events (release-next AC §4).
- Add `[Unreleased] → Added` bullet to `CHANGELOG.md` for the new TUI renderer.

### Defensive Exclusions
- **No subprocess spawn, no RPC framing, no JSONL parsing.** C2/C3/C4/C5 are owned by companion slices (`specs/explore/rpc-streaming.md`). The renderer receives `Event` instances only — the caller is responsible for producing them.
- **No Rich primitive selection lock-in.** The exact Rich class (`Live`, `Layout`, `Group`, etc.) is deferred to RED/GREEN per `specs/_product/architecture.md:66`.
- **No reconnect policy.** ADHOC A04.2 owns the `disconnected` path.
- **No OMP-specific wiring.** ADHOC A04.1 owns OMP transport parity.
- **No `--agent {pi,omp}` CLI flag.** Infra I04.1 owns that wiring.
- **No `[models]` config extension for RPC args.** Infra I04.2 owns that.
- **No modification to `src/deviate/core/agent.py` or `src/deviate/state/config.py`** beyond the scope of this issue.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-012`
- **Acceptance Criteria Tokens**: `AC-ADHOC-012-01`, `AC-ADHOC-012-02`, `AC-ADHOC-012-03`, `AC-ADHOC-012-04`, `AC-ADHOC-012-05`, `AC-ADHOC-012-06`
- **Data Model Entities**: `TuiRenderer`, `Terminal`, `AgentEvent` (all declared at `specs/_product/domain-model.md`)

## User Stories Ledger

- **US-012-01**: As a developer running `deviate` with Pi or OMP via RPC, I want agent progress (tool calls, thinking, edits) rendered in a compact 10-line TUI region that redraws in place so I can monitor live progress without scrolling a wall of text. *(Ref: FR-ADHOC-012)*
- **US-012-02**: As a developer on CI or piping output, I want the live TUI region to be skipped automatically so the final summary is the only output and pipelines are not corrupted by ANSI/resize sequences. *(Ref: FR-ADHOC-012)*
- **US-012-03**: As a developer, I want the TUI renderer to accept `Event` instances through a typed `Renderer.feed()` API so future C5 integration and unit tests have a minimal seam. *(Ref: FR-ADHOC-012)*

## ATDD Acceptance Criteria

**Scenario 012-01: Live region renders last N events in fixed region**
**Given** a `Renderer(max_lines=10)` instance
**When** 15 `AgentEvent` instances are fed sequentially via `renderer.feed(event)`
**Then** the rendered terminal region contains exactly the last 10 events; the region height never changes

**Scenario 012-02: Region clears and summary prints on flush**
**Given** a `Renderer` that has received 5 events
**When** `renderer.flush_summary("Final report")` is called
**Then** the live region is cleared and "Final report" is written to stdout after the cleared region

**Scenario 012-03: Non-TTY output skips live region**
**Given** stdout is not a TTY (piped or CI env var set)
**When** `renderer.feed(event)` is called
**Then** no Rich region is rendered; no ANSI/redraw sequences are emitted

**Scenario 012-04: Thread safety through stdout_lock**
**Given** two threads concurrently calling `renderer.feed(event)`
**When** both threads execute
**Then** all writes are serialized through the existing `stdout_lock`; no interleaved output

**Scenario 012-05: Unknown event kinds are renderable**
**Given** a `Renderer` instance
**When** an `AgentEvent` with `kind="unknown"` is fed
**Then** the event is rendered as the literal `…` without raising

**Scenario 012-06: Redraw budget — 1,000 events within 10-line cap**
**Given** a `Renderer(max_lines=10)` instance
**When** 1,000 simulated `AgentEvent` instances are fed in sequence
**Then** the rendered region never exceeds 10 lines (release-next AC §4 regression)

## Edge Cases and Boundaries

- **Zero events fed, then flush_summary called** — no live region to clear; final summary prints without preamble.
- **Single event fed, max_lines=1** — region is exactly 1 line; every feed replaces it.
- **max_lines=0** — `Renderer.__init__` raises `ValueError`; validate at construction.
- **Feed after flush** — subsequent `feed()` calls redraw a new live region; second `flush_summary()` appends below the previous summary.
- **Event with empty payload** — renders the event kind label with no extra detail.
- **Terminal resize between redraws** — Rich handles terminal resize natively; no explicit handler needed for this slice.
- **Unicode content inside event payload** — rendered as-is; no encoding assumption beyond UTF-8.

## Performance Constraints

- L_max: `tui_redraw_latency_ms` p95 ≤ 100 per FLOW-04 metrics (`specs/_product/flows/flows-streaming.md`)
- Rendered region: max 10 lines, in-place redraw only — never append, never grow
- Full test suite remains < 30s (per AGENTS.md); new test suite at `tests/test_tui/test_renderer.py` must complete in < 5s by feeding events directly to `Renderer.feed()` without subprocess overhead

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/test_tui/test_renderer.py::test_renderer_accepts_event`
  - `tests/test_tui/test_renderer.py::test_renderer_region_capped_at_max_lines`
  - `tests/test_tui/test_renderer.py::test_renderer_flush_summary_clears`
  - `tests/test_tui/test_renderer.py::test_renderer_non_tty_skips_live_region`
  - `tests/test_tui/test_renderer.py::test_renderer_unknown_event_renders_ellipsis`
  - `tests/test_tui/test_renderer.py::test_renderer_1000_events_never_exceeds_10_lines`
- **Integration Sandbox Targets**:
  - `tests/test_tui/test_renderer.py::test_renderer_stdout_lock_serialization`

## Demonstration Path
```bash
# Run the new TUI renderer regression suite
uv run pytest tests/test_tui/test_renderer.py -v

# Full suite regression (all tests pass, suite < 30s)
mise run test

# Lint check passes on all new code
mise run lint
```
