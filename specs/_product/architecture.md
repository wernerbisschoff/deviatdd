# DeviaTDD Product Architecture

Version: 0.2.0
Scope: Cross-epic integration contracts for `deviate` flows.
Owner: Product layer (FLOW-02).
Corrected: 2026-07-11 — transport framing and event vocabulary aligned with pi/oh-my-pi RPC docs.

---

## Components

### C1 — `deviate` CLI (existing)
- Responsibility: Orchestrates Macro, Meso, and Micro phase workflows.
- Implementation: Python 3.13 + Typer (entry points) + Rich (terminal I/O), per `specs/constitution.md:23`.
- Owns: phase state, JSONL ledgers, TOML config.
- References: FLOW-01, FLOW-02, FLOW-03.

### C2 — Subprocess Adapter (new — `src/deviate/rpc/subprocess.py`)
- Responsibility: Spawns and supervises the chosen agent runtime as a child process in RPC mode.
- Contract surface:
  - `spawn(agent: Literal["pi","omp"], args: list[str]) -> Popen`
  - `args` includes `--mode rpc` and any provider/model flags forwarded verbatim from `.deviate/config.toml`.
  - Returns a live `Popen` with `stdin`, `stdout`, `stderr` wired for JSONL framing.
- Owns: child process lifecycle, exit-code propagation, signal handling.
- Termination model: closes on `stdin` close, agent-side RPC shutdown, or process exit.
- References: FLOW-04.

### C3 — JSONL Framing Layer (new — `src/deviate/rpc/framing.py`)
- Responsibility: Reads/writes strict LF-delimited JSON records. Splits on `\n` only; strips trailing `\r` defensively; rejects Unicode line separators.
- Contract surface:
  - `iter_frames(stream) -> Iterator[dict]`
  - `write_frame(stream, payload: dict) -> None`
- Owns: byte-level transport integrity. Pure function of the wire — no semantic interpretation.
- References: FLOW-04.

### C4 — RPC Command Sender (new — `src/deviate/rpc/commands.py`)
- Responsibility: Sends typed `RpcCommand` envelopes on stdin and correlates responses by generated `id`.
- Contract surface:
  - `send(command: RpcCommand) -> Future[RpcResponse]`
  - Generates `req_<n>` ids; awaits matching `{type: "response", id, success, ...}` frames.
- Owns: request/response correlation, in-flight command registry, timeout policy.
- References: FLOW-04.

### C5 — Event Adapter (new — `src/deviate/rpc/events.py`)
- Responsibility: Normalizes `AgentSessionEvent` frames from Pi/OMP into a Product-layer `Event` discriminated union consumed by the TUI renderer.
- Contract surface:
  - `normalize(raw: dict) -> Event`
  - Maps `message_update.assistantMessageEvent` deltas (`text_delta`, `thinking_delta`, `toolcall_delta`) into streaming sub-events.
  - Renders unknown `type` values as the literal `…`.
- Owns: the canonical event vocabulary that crosses the RPC boundary.
- Source vocabulary (from `pi/oh-my-pi` docs):
  - Lifecycle: `agent_start`, `agent_end`, `turn_start`, `turn_end`
  - Message: `message_start`, `message_update`, `message_end`
  - Tool: `tool_execution_start`, `tool_execution_update`, `tool_execution_end`
  - System: `auto_compaction_start/end`, `auto_retry_start/end`, `ttsr_triggered`, `todo_reminder`, `todo_auto_clear`
  - Failure: `extension_error` (separate envelope with `extensionPath`, `event`, `error`)
- References: FLOW-04.

### C6 — TUI Renderer (new — `src/deviate/tui/renderer.py`)
- Responsibility: Renders the last N lines of normalized activity into a fixed terminal region and redraws in place on each event.
- Contract surface:
  - `Renderer(max_lines: int = 10) -> Renderer`
  - `renderer.feed(event: Event) -> None`
  - `renderer.flush_summary(text: str) -> None`
- Owns: terminal cursor state, the fixed redraw region, the final-summary region.
- Implementation: Rich terminal primitives (already mandated by `specs/constitution.md:23`); exact class selection deferred to RED/GREEN since Rich is not available in libref for verification.
- References: FLOW-04.

## Integration Contracts

| From → To | Protocol | Payload | Trigger |
|---|---|---|---|
| C1 → C2 | subprocess | argv + env | Meso/micro/run phase invokes Pi or OMP |
| C2 → C3 | stdin/stdout pipes | raw UTF-8 bytes | Always open while session is alive |
| C3 ↔ C4 | JSONL frames | `RpcCommand` / `RpcResponse` | Per command or per event |
| C3 → C5 | JSONL frames | `AgentSessionEvent` (raw) | Each stdout frame |
| C5 → C6 | in-process call | `Event` (normalized) | Each normalized event |
| C6 → terminal | ANSI / Rich | redraw of fixed region | Each event or final summary |
| C2 → C1 | exit code + stderr | process result | Process termination (stdin close or explicit shutdown) |

## Data Ownership Boundaries

- `deviate` owns phase state, JSONL ledgers, and the TUI renderer's terminal region.
- The agent runtime (Pi or OMP) owns the LLM session, tool execution, and any agent-local context.
- The boundary is one-way for streaming events (agent → deviate over stdout JSONL) and bidirectional for control (deviate → agent via stdin JSONL commands).
- C5 (Event Adapter) is the single translation surface — no other component may inspect raw agent frames.
- Stdout JSONL and stdin JSONL are byte-level shared resources; only C3 reads/writes them.

## Dependency Graph

```
C1 deviate CLI
 ├─► C2 Subprocess Adapter ──► C3 JSONL Framing ──┬──► C4 RPC Command Sender
 │                                                │
 │                                                └──► C5 Event Adapter ──► C6 TUI Renderer
 │                                                                              │
 └──────────────────────────────────────────────────────────────────────────────┴──► terminal
```

C3 splits stdout into C4-bound responses and C5-bound events. C4 writes to stdin; C3 reads from stdin for fire-and-forget commands. No back-edges. C1 can run without C2–C6 (legacy logging path preserved).

## Flow → Component Map

| Flow ID | Components |
|---|---|
| FLOW-01 | C1 |
| FLOW-02 | C1 |
| FLOW-03 | C1 |
| FLOW-04 | C1, C2, C3, C4, C5, C6 |

## Architectural Decision Records

### Spawn Pi or OMP as a subprocess rather than link in-process
- Context: FLOW-04 calls for `deviate` to drive an agent runtime. Both pi and oh-my-pi offer an in-process `AgentSession` SDK and a subprocess `--mode rpc` mode (`pi` SDK docs: "RPC mode is preferred when: You're integrating from another language, You want process isolation").
- Decision: Spawn the chosen agent as a subprocess and speak JSONL over stdio.
- Rationale: Satisfies all three ADR criteria — (a) hard to reverse because swapping transport later means redoing C2/C3/C4 framing, (b) surprising without context because Python developers default to in-process SDKs, (c) real tradeoff between process isolation/language-agnosticism and tighter in-process integration. Python-side integration is explicitly listed as a reason to prefer RPC in the pi SDK docs, so the decision is grounded, not speculative.

### Build a JSONL framing layer dedicated to strict-LF semantics
- Context: Pi RPC docs explicitly warn that "Node `readline` is not protocol-compliant for RPC mode" and that clients must "Split records on `\n` only" and "Accept optional `\r\n` input by stripping a trailing `\r`."
- Decision: C3 implements strict-LF JSONL framing in isolation from any higher-level concerns.
- Rationale: A future maintainer reusing `csv`, `readline`, or generic line splitters will silently corrupt messages because the protocol deliberately excludes Unicode line separators as record delimiters. Isolating framing makes the invariant explicit and testable. ADR criteria: (a) hard to reverse because changing framing later breaks wire compatibility, (b) surprising without the doc warning, (c) real tradeoff between reusing stdlib and writing a 20-line dedicated splitter.