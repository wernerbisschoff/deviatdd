# DeviaTDD Domain Model

Version: 0.2.0
Scope: Cross-epic entities and relationships.
Corrected: 2026-07-11 — transport and event vocabulary aligned with pi/oh-my-pi RPC docs.

---

## Entities

### AgentRuntime
- Attributes:
  - `id`: enum(`"pi"`, `"omp"`)
  - `mode`: enum(`"rpc"`) — only RPC mode is in scope for FLOW-04
  - `state`: enum(`"spawning"`, `"streaming"`, `"disconnected"`, `"closed"`)
- Relationships:
  - has exactly one → `SubprocessHandle`
  - emits many → `AgentFrame`

### SubprocessHandle
- Attributes:
  - `agent_id`: enum(`"pi"`, `"omp"`) (FK → AgentRuntime.id)
  - `pid`: int
  - `stdin`, `stdout`, `stderr`: pipe handles
  - `state`: enum(`"open"`, `"closing"`, `"closed"`)
- Relationships:
  - belongs to → `AgentRuntime`
  - produces → `AgentFrame` (one per stdout line)
  - terminates on → stdin close, agent shutdown, or process exit

### AgentFrame
- Attributes:
  - `kind`: enum(`"response"`, `"event"`, `"extension_error"`, `"parse_error"`)
  - `payload`: dict
  - `received_at`: datetime
- Relationships:
  - emitted by → `SubprocessHandle`
  - routed to → `RpcResponse` or `AgentEvent` by JSONL framing layer (C3)

### RpcCommand
- Attributes:
  - `id`: string (e.g. `"req_1"`)
  - `method`: string
  - `params`: dict
- Relationships:
  - sent by → `deviate CLI`
  - correlated to → `RpcResponse`

### RpcResponse
- Attributes:
  - `id`: string (FK → RpcCommand.id)
  - `success`: bool
  - `error`: string (when `success: false`)
  - `command`: string
- Relationships:
  - replies to → `RpcCommand`

### AgentEvent (Product-layer normalized)
- Attributes:
  - `kind`: enum(
      `"agent_start"`, `"agent_end"`,
      `"turn_start"`, `"turn_end"`,
      `"message_start"`, `"message_update"`, `"message_end"`,
      `"tool_execution_start"`, `"tool_execution_update"`, `"tool_execution_end"`,
      `"auto_compaction_start"`, `"auto_compaction_end"`,
      `"auto_retry_start"`, `"auto_retry_end"`,
      `"ttsr_triggered"`,
      `"todo_reminder"`, `"todo_auto_clear"`,
      `"streaming_delta"`,
      `"unknown"`
    )
  - `payload`: dict (opaque past the adapter)
  - `received_at`: datetime
- Relationships:
  - normalized from → `AgentFrame` (kind=`event`) by Event Adapter (C5)
  - consumed by → `TuiRenderer`

### StreamingDelta
- Attributes:
  - `kind`: enum(`"text_delta"`, `"thinking_delta"`, `"toolcall_delta"`)
  - `delta`: string
- Relationships:
  - carried inside → `AgentEvent` (kind=`streaming_delta`, extracted from `message_update.assistantMessageEvent`)

### TuiRenderer
- Attributes:
  - `max_lines`: int (default 10)
  - `region`: terminal redraw region (Rich primitive, exact class TBD)
- Relationships:
  - consumes → `AgentEvent`
  - renders to → `Terminal`

### Terminal
- Attributes:
  - `kind`: enum(`"tty"`, `"pipe"`)
- Relationships:
  - owned by → `deviate CLI`
  - rendered to by → `TuiRenderer`

## Cross-Epic Integration Points

| Entity | Spans Epics |
|---|---|
| AgentRuntime | Meso (phase selection) + Micro (LLM execution) |
| SubprocessHandle | Meso (phase orchestration) + Micro (per-task invocation) |
| AgentFrame | Meso (phase progress) + Micro (loop progress) |
| AgentEvent | Meso (phase progress) + Micro (loop progress) |
| TuiRenderer | Meso + Micro (user-visible feedback) |