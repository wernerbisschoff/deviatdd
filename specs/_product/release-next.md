# DeviaTDD Next Release

Version: 0.1.0
Status: Active
Goal anchor: FLOW-04 (Live-Stream Agent Progress via RPC)
Architecture anchor: specs/_product/architecture.md (v0.2.0)
Domain model anchor: specs/_product/domain-model.md (v0.2.0)

---

## Goal

Enable `deviate` meso and micro phases to drive Pi or OMP agent runtimes through their RPC mode and stream live progress (tool calls, thinking, edits) into a compact TUI that updates the same region in place rather than scrolling a wall of text. Ship one coherent slice: subprocess-based RPC with strict-LF JSONL framing, an event adapter that normalizes `AgentSessionEvent` frames, and a Rich-based TUI renderer capped at 10 lines.

## Constraints

- **Tech stack** (per `specs/constitution.md:23`): Python 3.13 + Typer + Rich only. No new CLI frameworks, no frontend.
- **Transport** (per `specs/_product/architecture.md` C3): JSONL over stdio, strict-LF framing, no Unicode line separators. Subprocess isolation only — no in-process agent linking.
- **Event vocabulary** (per `specs/_product/architecture.md` C5): `AgentSessionEvent` taxonomy as documented in `pi/oh-my-pi` (`agent_*`, `turn_*`, `message_*`, `tool_execution_*`, `auto_compaction_*`, `auto_retry_*`, `ttsr_triggered`, `todo_reminder`, `todo_auto_clear`); `message_update.assistantMessageEvent` deltas for streaming text/thinking/toolcall.
- **TUI budget** (per FLOW-04 Metrics at `specs/_product/flows/flows-streaming.md`): fixed region, max 10 lines, in-place redraw only — never append, never grow.
- **Backwards compatibility** (per architecture invariant): legacy logging path preserved when C2–C6 are absent.
- **Product-layer scope**: this release introduces no new cross-epic architecture; all six components C2–C6 are documented at FLOW-04 scope and surface as one epic plus enabling infra.

## Included Flows

| Flow ID | Name | Why in this release |
|---|---|---|
| FLOW-04 | Live-Stream Agent Progress via RPC | Primary capability — entire release exists to ship this flow |

## Included Work

| ID | Title | Type | Flow Refs |
|---|---|---|---|
| E04.1 | RPC subprocess + JSONL framing (C2, C3) | Epic | FLOW-04 |
| E04.2 | RPC command sender + Event Adapter (C4, C5) | Epic | FLOW-04 |
| E04.3 | TUI renderer + final-summary region (C6) | Epic | FLOW-04 |
| A04.1 | OMP transport parity — confirm `--mode rpc` flags match Pi and add an OMP-specific flag-mapping table | ADHOC | FLOW-04 |
| A04.2 | Reconnect strategy — define behavior when `SubprocessHandle` transitions to `disconnected` (reconnect, prompt user, or abort) | ADHOC | FLOW-04 |
| I04.1 | Wire `--agent {pi,omp}` flag into `deviate meso run` and `deviate micro run --all` (argv pass-through to C2) | Infra | none |
| I04.2 | Extend `.deviate/config.toml` `[models]` to declare RPC-mode args per agent id | Infra | none |

## Deferred Epics

N/A

## Acceptance Criteria

- [ ] `mise run setup` (or `deviate setup`) installs `src/deviate/rpc/{subprocess,framing,commands,events}.py` and `src/deviate/tui/renderer.py` under the existing CLI package.
- [ ] `deviate meso run --agent omp` spawns `omp --mode rpc` as a subprocess and exits non-zero if the binary is missing on PATH.
- [ ] `deviate micro run --all --agent pi` spawns `pi --mode rpc` and streams events into the TUI region.
- [ ] The TUI region redraws in place; `mise run check` includes a regression test that asserts the rendered region never exceeds 10 lines across 1,000 simulated events.
- [ ] JSONL framing passes a test that feeds it records containing Unicode line separators (`\u2028`, `\u2029`) and asserts the splitter does NOT treat them as record terminators (per `pi` rpc.md framing warning).
- [ ] Event Adapter maps every `AgentSessionEvent` type listed in `specs/_product/architecture.md` C5 to the Product-layer `Event` union; unknown types render as `…` rather than raising.
- [ ] `message_update.assistantMessageEvent` deltas (`text_delta`, `thinking_delta`, `toolcall_delta`) surface as `streaming_delta` sub-events in the TUI without buffering past the 10-line cap.
- [ ] Reconnect ADHOC A04.2 ships a documented policy; behavior is asserted by a test that simulates a mid-run stdout close and verifies the chosen policy fires.
- [ ] `mise run check` exits 0 (lint + format-check + types + tests) with the new code in place.
- [ ] CHANGELOG.md `[Unreleased] → Added` lists the new `--agent` flag and the TUI renderer as user-visible capabilities.
- [ ] Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries (`flow_refs: [FLOW-04]`).