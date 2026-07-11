## FLOW-04 Live-Stream Agent Progress via RPC

- Actor: Developer
- Domain: Agent Integration
- Status: Active
- Source: specs/_product/flows/flows-streaming.md

### Problem / job to be done
- Stream Pi/OMP agent progress (tool calls, thinking, edits) into a compact TUI that updates in place instead of scrolling a wall of text.

### Trigger
- A `deviate` meso or micro phase (e.g. `deviate run`) invokes Pi or OMP via RPC.

### Preconditions
- Pi or OMP exposes an RPC endpoint that emits streaming events.
- A local TUI renderer is available in the deviatdd workdir.

### Happy path (primary steps)
1. Developer runs a deviate phase that targets Pi or OMP.
2. Deviate opens an RPC channel to the chosen agent runtime.
3. Agent emits typed events: `tool_call`, `thinking`, `edit`, `message`.
4. Deviate forwards events into the local TUI renderer.
5. TUI renders the last 10 lines of activity in a fixed region.
6. TUI redraws the same region on each new event (no scroll, no append wall).
7. On phase completion, TUI clears the live region and prints the final summary.

### Alternate / error paths
- RPC channel drops mid-run → TUI shows `disconnected` status and offers reconnect.
- Agent emits an event type the TUI does not recognize → render as `…`.

### Success State
- TUI shows live progress without growing past 10 lines.
- Final summary persists after the live region clears.

### Metrics / Signals
- `tui_redraw_latency_ms` p95 ≤ 100.
- references FLOW-01.