---
title: "Constrain Spawned Pi to Lean Tools and Surface tool_count_limit"
labels: [bugfix, adhoc, vertical-slice, agent]
blocked_by: []
coordinates_with: [ISS-ADH-025]
issue_id: ISS-ADH-026
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/026-pi-spawn-lean-tool-schema.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/agent.py::AgentBackend.invoke` — TARGET: print-mode argv is `BACKEND_COMMANDS["pi"]` (`pi -p`) plus optional `--model`. RPC argv is `PI_RPC_COMMAND` (`pi --mode rpc --no-session`). Neither path currently passes `--no-extensions`, `--tools`, `--no-skills`, or `--skill`, so the child inherits the operator's global extension/MCP/tool stack. Append a lean Pi tool policy at invoke time; do not rewrite `BACKEND_COMMANDS["pi"] == "pi -p"` (AC-009-07) or drop `--mode rpc --no-session`.
  - `src/deviate/core/agent.py::PI_RPC_COMMAND` / `BACKEND_COMMANDS` — REFERENCE: keep the existing constants as the transport prefix. Lean flags are added after that prefix for both transports.
  - `src/deviate/core/agent.py::_invoke_streaming` / `_invoke_blocking` / `_invoke_rpc_blocking` — TARGET: if stderr or stdout contains `tool_count_limit` or `unsupported_tool_schema`, abort the child immediately and raise a harness-visible agent error (existing `AgentSubprocessError` or a dedicated subclass). Do not wait for the 900s stall clock or a second manifest retry. Compose with ISS-ADH-025: stderr remains diagnostic for stall liveness; schema-rejection tokens are a separate fail-fast path.
  - `src/deviate/cli/micro.py::_invoke_agent` — TARGET: log `AGENT_ERROR` with the provider tokens. GREEN/RED/REFACTOR/TASKS callers must not collapse this into a generic `agent returned no manifest` after a long silent wait. The operator-visible `PhaseFailedError` (or equivalent) must include `tool_count_limit` or `unsupported_tool_schema`.
  - `src/deviate/cli/micro.py::_run_green_phase` / RED / REFACTOR / TASKS invoke sites — TARGET: when `_invoke_agent` returns a schema-limit failure, surface those tokens. Do not require a live `pi --mode rpc` pipe to reproduce.
  - `src/deviate/state/config.py::AgentConfig` — REFERENCE: do not revert operator-local `pi_rpc=false`, `transport=cli`, `backend=pi`, `timeout=1800`, or `models.default=grok-4.6`. Lean flags apply to whichever transport `invoke` actually builds.
  - `tests/unit/test_core/test_agent.py` / `tests/unit/core/test_agent.py` — TARGET: pin print-mode and RPC argv. Keep AC-009-07 / AC-009-10 transport pins.
  - `tests/unit/test_cli/test_micro.py` — TARGET: `_invoke_agent` / `deviate micro run` (mocked Popen) surfaces schema-limit as `AGENT_ERROR`, not "no manifest". Mock `deviate.cli.micro._run_pytest` if the CLI path would spawn it.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document the default lean Pi spawn policy and the fail-fast schema-rejection contract.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible spawn/error-behavior change.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - `deviate micro run` GREEN of TSK-005-01 hit `400 tool_count_limit` (`unsupported_tool_schema`) twice; TASKS hit it once. When it did not fire, GREEN ran 50+ minutes with no handover manifest.
  - Pi help documents `--no-extensions` / `-ne`, `--tools` / `-t`, `--no-skills` / `-ns`, `--skill <path>`, and built-in tools `read`, `bash`, `edit`, `write`.
  - `AgentBackend.invoke` inherits `env=None` (full parent environment) and does not constrain tools. `_invoke_agent` builds `AgentConfig(backend=backend_name)` and maps subprocess/empty/malformed failures to `None`, after which GREEN raises `agent returned no manifest`.
  - Manual `pi --mode rpc` pipes produce a different error than the harness `deviate micro run` path; validation must go through `_invoke_agent` / `micro run`.

## The Problem Contract

A spawned Pi child currently advertises the operator's full global tool stack (extensions, codebase-index, MCP servers). Providers that enforce `tool_count_limit` reject that schema with `unsupported_tool_schema`. The harness then either hangs with no manifest or later reports only a generic agent error. Operators need a default lean spawn (coding tools + `deviatdd` skill) and an immediate, token-bearing failure when the provider still rejects the schema.

## Scope Boundaries

### Hard Inclusions

- Default Pi spawn for `deviate micro run` (print mode `pi -p` and RPC `pi --mode rpc --no-session`) must disable extension/MCP discovery (`--no-extensions` or equivalent) and must not load the operator's full global tool stack.
- The child must keep built-in coding tools `read`, `bash`, `edit`, and `write` (Pi `--tools` allowlist or equivalent) so RED/GREEN/REFACTOR can still inspect, edit, and run commands.
- The project-local `deviatdd` skill must remain available (explicit `--skill` to `.pi/skills/deviatdd/SKILL.md` when present, plus `--no-skills` so global/unrelated skills are not discovered). Missing skill file must not strip the coding tools.
- Lean flags apply at `AgentBackend.invoke` for both transports. Existing `BACKEND_COMMANDS["pi"] == "pi -p"` and RPC `--no-session` pins stay composed.
- When child stderr or stdout contains `tool_count_limit` or `unsupported_tool_schema`, kill the child promptly and raise a harness-visible error. `_invoke_agent` logs `AGENT_ERROR` with those tokens. Phase failure text from `deviate micro run` must include the tokens instead of only `agent returned no manifest`.
- Do not wait for `STREAM_STALL_TIMEOUT_SECONDS` (900s), the 30s + retry path, or an outer ~1800s bash timeout to discover a schema rejection.
- Tests go through `AgentBackend.invoke` and `_invoke_agent` / `deviate micro run` with mocked `Popen`. Do not treat a manual `pi --mode rpc` pipe as the acceptance path.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.

### Defensive Exclusions

- Do **not** reopen GitHub #61 / ISS-ADH-025 except to compose: stderr is still not stall liveness. Schema-token fail-fast is not a new liveness channel and must not reset the 900s clock.
- Do **not** reopen GitHub #53 except to compose: EXECUTE stall stays 3600s.
- Do **not** revert operator-local `.deviate/config.toml` (`backend=pi`, `transport=cli`, `pi_rpc=false`, `timeout=1800`, `models.default=grok-4.6`, `timeout_seconds=1800`).
- Do **not** disable `read`/`bash`/`edit`/`write`. Do not use `--no-tools` / `--no-builtin-tools` as the default policy.
- Do **not** inherit or re-enable the operator's global MCP/extension stack by default. An explicit future opt-in is out of this slice.
- Do **not** change OMP/claude/opencode/droid spawn argv except where they share the Pi helper and a change is required to keep Pi lean.
- Do **not** author, repair, or index Product-layer flows (`flow_refs: []`). FLOW-04 is RPC TUI live-stream, not tool-schema policy.
- Do **not** delete branches, mutate operator-local config, or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** change TSK id format, ledger append-only rules, or invent a second issue-id series.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-026`
- **Acceptance Criteria Tokens**: `AC-ADHOC-026-01`, `AC-ADHOC-026-02`, `AC-ADHOC-026-03`
- **Data Model Entities**: none new — reuse `AgentSubprocessError` / `HandoverManifest`; no new ledger row types
- **Spec Source Anchors**:
  - `src/deviate/core/agent.py` `invoke` / `BACKEND_COMMANDS` / `PI_RPC_COMMAND`
  - `src/deviate/cli/micro.py` `_invoke_agent` and GREEN/RED/REFACTOR "no manifest" mapping
  - `specs/constitution.md` §3 Testing Protocols; §5 Definition of Done (CHANGELOG for user-visible bug fix)
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` Agent Backend / Pi spawn

## User Stories Ledger

- **US-026-01**: As a DeviaTDD operator, I want the spawned Pi child to load only built-in coding tools plus the `deviatdd` skill so the provider does not reject the tool schema. *(Ref: FR-ADHOC-026)*
- **US-026-02**: As a DeviaTDD operator running RED/GREEN/REFACTOR, I want the child to keep `read`, `bash`, `edit`, and `write` so the TDD loop can still edit and verify code. *(Ref: FR-ADHOC-026)*
- **US-026-03**: As a DeviaTDD operator, I want `tool_count_limit` / `unsupported_tool_schema` to appear as a harness-visible agent error from `deviate micro run` so I do not wait 50+ minutes for a missing manifest. *(Ref: FR-ADHOC-026)*

## Acceptance Outline

- **AO-026-01** *(Ref: AC-ADHOC-026-01, US-026-01)*: Default Pi spawn is lean.
  - **Happy Path**: `AgentBackend.invoke` for backend `pi` (print mode and `pi_rpc=True`) produces argv that include `--no-extensions` (or `-ne`) and do not rely on the operator's global extension/MCP discovery. The `deviatdd` skill is requested via `--skill` when `.pi/skills/deviatdd/SKILL.md` exists; `--no-skills` prevents global skill discovery.
  - **Error Category**: Spawning bare `pi -p` or `pi --mode rpc --no-session` with the full operator tool stack is a failure of this slice.
  - **Boundary Category**: `BACKEND_COMMANDS["pi"]` remains `"pi -p"`. RPC still includes `--mode rpc` and `--no-session`. `--model` injection stays. Operator-local `pi_rpc=false` is not flipped.

- **AO-026-02** *(Ref: AC-ADHOC-026-02, US-026-02)*: Coding tools remain available.
  - **Happy Path**: The same argv allowlist includes `read`, `bash`, `edit`, and `write` (Pi `--tools read,bash,edit,write` or equivalent). RED/GREEN/REFACTOR can still read, edit, write, and run shell commands.
  - **Error Category**: Defaulting to `--no-tools` or `--no-builtin-tools`, or omitting any of the four coding tools, is a failure.
  - **Boundary Category**: A missing project-local skill file does not remove the four coding tools. Non-Pi backends stay unchanged unless they share the helper.

- **AO-026-03** *(Ref: AC-ADHOC-026-03, US-026-03)*: Schema rejection is harness-visible on `deviate micro run`.
  - **Happy Path**: A mocked child that writes `400 tool_count_limit` / `unsupported_tool_schema` to stderr (or stdout) causes `_invoke_agent` to log `AGENT_ERROR` containing those tokens and causes `deviate micro run` to fail with those tokens in the operator-visible error. The child is killed without waiting for the 900s stall or an outer ~1800s bash timeout.
  - **Error Category**: Swallowing the tokens and later raising only `agent returned no manifest`, or retrying the same oversized schema as a manifest-parse retry, is a failure.
  - **Boundary Category**: Validation is the harness path (`_invoke_agent` / `deviate micro run` with mocked `Popen`), not a manual `pi --mode rpc` pipe. ISS-ADH-025 stderr-not-liveness and GH-53 EXECUTE 3600s stay composed. API / architecture / CHANGELOG update in the same implementation commit.

## Edge Cases and Boundaries

- Intermittent provider rejection is the motivating failure mode; the lean default exists so the schema stays under the limit even when the operator has a large personal MCP/extension stack.
- Schema-rejection tokens may appear while the child is still running (empty stdout, no manifest). Fail-fast on the first matching line; do not require a non-zero exit first.
- A healthy invoke with no such tokens still completes and parses a YAML handover manifest as today.
- `EmptyOutputError` manifest retry remains for genuine empty/malformed YAML; it must not retry a known `tool_count_limit` failure.
- `env=None` inheritance (API keys, `PI_MODEL`) stays; this slice constrains tools, not environment forwarding.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: schema-rejection abort on the first matching stderr/stdout line plus small poll slack (`_invoke_streaming` sleeps 0.05s per loop), not at 900s / 1830s / outer 1800s.
- Throughput: no extra live agent calls on the healthy path. Argv construction is in-process. Full test suite remains < 30s; mock `Popen` and `deviate.cli.micro._run_pytest`. Never sleep the stall budget in CI.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_core/test_agent.py::test_agent_uses_pi_command_default` — keep `pi -p` as prefix; assert lean flags are appended.
  - `tests/unit/test_core/test_agent.py` AC-009-07 pin — `BACKEND_COMMANDS["pi"] == "pi -p"` remains true.
  - `tests/unit/core/test_agent.py::TestPiRpcMode::test_pi_rpc_mode_opt_in` — RPC argv still has `--mode rpc` and `--no-session`, plus lean flags.
  - `tests/unit/test_core/test_agent.py` / `tests/unit/core/test_agent.py` — new pin: print-mode and RPC argv include `--no-extensions` (or `-ne`) and `--tools` listing `read`, `bash`, `edit`, `write`.
  - `tests/unit/test_core/test_agent.py` — new pin: stderr containing `tool_count_limit` / `unsupported_tool_schema` raises a harness-visible agent error immediately (patched short/no stall wait).
- **Integration Sandbox Targets**:
  - `tests/unit/test_cli/test_micro.py` — `_invoke_agent` or `deviate micro run` with a mocked Pi child that emits `unsupported_tool_schema` logs `AGENT_ERROR` and fails with those tokens, not only `agent returned no manifest`. Mock `deviate.cli.micro._run_pytest`. Not a live `pi --mode rpc` pipe.

## Demonstration Path

```bash
# Mocked Pi spawn + schema-error pins (no live agent)
uv run pytest tests/unit/test_core/test_agent.py tests/unit/core/test_agent.py tests/unit/test_cli/test_micro.py -q -k "pi and (rpc or tool or lean or schema or invoke)"
```
