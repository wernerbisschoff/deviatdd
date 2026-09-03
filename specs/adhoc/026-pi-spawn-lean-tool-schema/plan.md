## Plan Summary
- **Issue**: ISS-ADH-026 — Constrain Spawned Pi to Lean Tools and Surface tool_count_limit
- **Implementation Strategy**: Append a lean Pi tool policy after the existing print-mode and RPC prefixes at `AgentBackend.invoke`. Abort the child on the first `tool_count_limit` or `unsupported_tool_schema` line and surface those tokens through `_invoke_agent` and `deviate micro run`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/026-pi-spawn-lean-tool-schema.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC live-stream into a 10-line TUI). This issue is orthogonal: it constrains `AgentBackend` Pi spawn tools and fail-fast schema rejection.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns `AgentBackend.invoke` argv and micro `_invoke_agent` error mapping)

## Acceptance Contract

**Scenario AC-PLAN-001: Append lean Pi flags after the existing transport prefix**
- **Source Outline**: `AO-026-01`
- **Upstream Traceability**: `US-026-01`, `FR-ADHOC-026`, `AC-ADHOC-026-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:BACKEND_COMMANDS`; `src/deviate/core/agent.py:PI_RPC_COMMAND`; `src/deviate/core/agent.py:AgentBackend.invoke`
- **Given**: `AgentBackend.invoke` builds print-mode argv from `BACKEND_COMMANDS["pi"]` (`pi -p`) or RPC argv from `PI_RPC_COMMAND` (`pi --mode rpc --no-session`) and does not add `--no-extensions`, `--tools`, `--no-skills`, or `--skill`.
- **When**: A test calls `invoke` for backend `pi` in print mode and again with `pi_rpc=True`, using a mocked `Popen`.
- **Then**: Both argv lists keep their transport prefix, include `--no-extensions` (or `-ne`) and `--no-skills` (or `-ns`), add `--skill` to `.pi/skills/deviatdd/SKILL.md` when that file exists, keep `--model` injection on the print-mode path, and leave `BACKEND_COMMANDS["pi"] == "pi -p"` plus RPC `--no-session` unchanged.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep the four coding tools on the Pi allowlist**
- **Source Outline**: `AO-026-02`
- **Upstream Traceability**: `US-026-02`, `FR-ADHOC-026`, `AC-ADHOC-026-02`
- **Current-Code Evidence**: `src/deviate/core/agent.py:AgentBackend.invoke`; `tests/unit/test_core/test_agent.py:test_agent_uses_pi_command_default`
- **Given**: The same mocked `invoke` path builds Pi argv for print mode and RPC, including a case where `.pi/skills/deviatdd/SKILL.md` is absent.
- **When**: The test inspects the argv passed to `Popen`.
- **Then**: Argv includes Pi `--tools` (or equivalent) listing `read`, `bash`, `edit`, and `write`, omits `--no-tools` and `--no-builtin-tools`, and still lists those four tools when the skill file is missing. Non-Pi backends stay on their current argv unless they share the Pi helper.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Abort the child on the first schema-rejection line**
- **Source Outline**: `AO-026-03`
- **Upstream Traceability**: `US-026-03`, `FR-ADHOC-026`, `AC-ADHOC-026-03`
- **Current-Code Evidence**: `src/deviate/core/agent.py:_invoke_streaming`; `src/deviate/core/agent.py:invoke`; `src/deviate/core/agent.py:EmptyOutputError`
- **Given**: A mocked child writes `400 tool_count_limit` or `unsupported_tool_schema` on stderr or stdout and then stays open with empty manifest output. The stall budget is patched short or unused.
- **When**: `AgentBackend.invoke` runs through `_invoke_streaming`, `_invoke_blocking`, or `_invoke_rpc_blocking`.
- **Then**: The helper kills the child on the first matching line, raises a harness-visible `AgentSubprocessError` (or a dedicated subclass) whose message contains `tool_count_limit` or `unsupported_tool_schema`, skips the 900s stall clock, skips the 30s timeout retry, and does not start the `EmptyOutputError` manifest retry.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Surface schema tokens from deviate micro run**
- **Source Outline**: `AO-026-03`
- **Upstream Traceability**: `US-026-03`, `FR-ADHOC-026`, `AC-ADHOC-026-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`; `src/deviate/cli/micro.py:_run_green_phase`; `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: `_invoke_agent` currently catches `AgentSubprocessError`, logs `AGENT_ERROR`, and returns `(None, "")`. GREEN then raises `PhaseFailedError` with only `agent returned no manifest`. GREEN also treats a truthy second tuple as timeout context.
- **When**: A `deviate micro run` (or `_invoke_agent`) test mocks `Popen` so the child emits `unsupported_tool_schema` / `tool_count_limit`, and mocks `deviate.cli.micro._run_pytest`.
- **Then**: The harness logs `AGENT_ERROR` containing those tokens and the operator-visible `PhaseFailedError` (or equivalent) includes `tool_count_limit` or `unsupported_tool_schema` instead of only `agent returned no manifest`. The test does not use a live `pi --mode rpc` pipe. API, architecture, and `CHANGELOG.md` `[Unreleased]` update in the same implementation commit.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: Own Pi spawn argv and schema-rejection fail-fast.
  - **Current State**: `invoke` copies `PI_RPC_COMMAND` or splits `BACKEND_COMMANDS["pi"]` (`pi -p`), then adds `--model` only on the print-mode path. `_invoke_streaming` captures stderr as diagnostics and does not inspect tokens. `_invoke_blocking` and `_invoke_rpc_blocking` wait on `communicate`. Empty stdout then retries once as `EmptyOutputError`.
  - **Changes Required**: After the existing prefix, append `--no-extensions`, `--tools read,bash,edit,write`, and `--no-skills`. Add `--skill` to `.pi/skills/deviatdd/SKILL.md` when that file exists under the invoke `cwd` (or `Path.cwd()`). Keep `BACKEND_COMMANDS["pi"] == "pi -p"` and RPC `--mode rpc --no-session`. On the first line that contains `tool_count_limit` or `unsupported_tool_schema`, kill the child and raise `AgentSubprocessError` or a subclass. Do not wait for `STREAM_STALL_TIMEOUT_SECONDS`. Do not treat those tokens as stall liveness. Do not retry them as a manifest parse. Leave `env=None` and non-Pi argv unchanged unless they share the helper.
  - **Integration Surface**: `AgentBackend.invoke`; `_dispatch_invocation`; `_invoke_streaming`; `_invoke_blocking`; `_invoke_rpc_blocking`; `AgentSubprocessError`; `EmptyOutputError`.

- **src/deviate/cli/micro.py**: Surface schema tokens to the operator.
  - **Current State**: `_invoke_agent` logs `AGENT_ERROR` for `AgentSubprocessError` and returns `(None, "")`. RED, GREEN, REFACTOR, JUDGE, and EXECUTE then raise `PhaseFailedError` with `agent returned no manifest`. GREEN treats a truthy second return value as timeout context.
  - **Changes Required**: After `AGENT_ERROR`, keep the tokens on the raised or returned error. Make `PhaseFailedError` from RED, GREEN, and REFACTOR include `tool_count_limit` or `unsupported_tool_schema`. Do not route a schema-limit failure through the GREEN timeout-summary path. Do not un-mock `_run_pytest`. Do not change `EXECUTE_STALL_TIMEOUT_SECONDS` (3600) or the ISS-ADH-025 stderr-not-liveness rule.
  - **Integration Surface**: `_invoke_agent`; `_run_red_phase`; `_run_green_phase`; `_run_refactor_phase`; `PhaseFailedError`.

- **src/deviate/cli/meso.py**: Compose only. TASKS already prints `AgentSubprocessError`.
  - **Current State**: `_invoke_agent_phase` catches `AgentSubprocessError`, prints `{phase}_FAILED {e}`, and exits 1.
  - **Changes Required**: No meso rewrite when the new error subclasses `AgentSubprocessError` and the message already carries the tokens. Touch this file only if TASKS still swallows the tokens.
  - **Integration Surface**: `_invoke_agent_phase`.

- **src/deviate/state/config.py**: Reference only.
  - **Current State**: `AgentConfig` keeps `pi_rpc=false` by default. `_invoke_agent` builds `AgentConfig(backend=backend_name)` and `invoke` still keys RPC on `pi_rpc`, not `transport`.
  - **Changes Required**: Do not revert operator-local `pi_rpc`, `transport`, `backend`, `timeout`, or `[models]`. Lean flags apply to whichever transport `invoke` builds.
  - **Integration Surface**: `AgentConfig.pi_rpc`; `AgentBackend.invoke`.

- **tests/unit/test_core/test_agent.py**: Pin print-mode argv, AC-009-07, and fail-fast.
  - **Current State**: `test_agent_uses_pi_command_default` asserts `pi -p` in the joined command. A nearby pin asserts `BACKEND_COMMANDS["pi"] == "pi -p"`. Streaming tests mock pipes and use a short stall budget.
  - **Changes Required**: Keep the `pi -p` prefix and AC-009-07 pin. Assert lean flags and the four coding tools. Add a patched-budget pin that a schema-rejection line raises immediately with the tokens and calls `kill`. Do not sleep 900s.
  - **Integration Surface**: `AgentBackend.invoke`; `_invoke_streaming`.

- **tests/unit/core/test_agent.py**: Pin RPC argv composition.
  - **Current State**: `TestPiRpcMode.test_pi_rpc_mode_opt_in` asserts `--mode rpc` and `--no-session` and forbids `-p`.
  - **Changes Required**: Keep those pins. Assert the same lean flags and coding-tool allowlist on the RPC argv.
  - **Integration Surface**: `PI_RPC_COMMAND`; `AgentConfig(pi_rpc=True)`.

- **tests/unit/test_cli/test_micro.py**: Pin harness-visible tokens.
  - **Current State**: Most tests mock `_invoke_agent`. No pin covers schema-limit `AGENT_ERROR` versus `agent returned no manifest`.
  - **Changes Required**: Add a `_invoke_agent` or `deviate micro run` pin with mocked `Popen` that emits `unsupported_tool_schema`. Assert `AGENT_ERROR` and the operator-visible error include the tokens. Mock `deviate.cli.micro._run_pytest`.
  - **Integration Surface**: `_invoke_agent`; `_run_green_phase`.

- **specs/DeviaTDD-api.md**: Document the lean spawn and fail-fast contract.
  - **Current State**: Agent Backend Hardening describes stall, manifest retry, and Pi `pi -p` / RPC prefixes. It does not name a lean tool policy or schema-token abort.
  - **Changes Required**: State the default Pi spawn adds `--no-extensions`, `--tools read,bash,edit,write`, `--no-skills`, and optional `--skill`. State that `tool_count_limit` / `unsupported_tool_schema` abort the child and surface as `AGENT_ERROR`. Same commit as the code.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` Pi backend section.

- **specs/DeviaTDD-architecture.md**: Align the Pi backend spawn table.
  - **Current State**: The Pi row documents `pi -p`, `--model`, and opt-in RPC `--no-session`. It does not constrain tools.
  - **Changes Required**: Document the lean default and the fail-fast schema-rejection path. Keep AC-009-07 / AC-009-10 prefix text. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` Agent Backend Hardening.

- **CHANGELOG.md**: Record the user-visible spawn and error change.
  - **Current State**: `[Unreleased]` has no ISS-ADH-026 lean-spawn bullet.
  - **Changes Required**: Append a `[Unreleased]` bullet: default Pi spawn is lean, and schema-limit tokens surface immediately on `deviate micro run`.
  - **Integration Surface**: constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: RED argv and fail-fast pins
  - **Files**: `tests/unit/test_core/test_agent.py`, `tests/unit/core/test_agent.py`, `tests/unit/test_cli/test_micro.py`
  - **Approach**: Keep `pi -p` and RPC `--no-session` pins. Add print-mode and RPC pins for `--no-extensions`, `--no-skills`, `--tools` listing `read`, `bash`, `edit`, and `write`, and `--skill` when the skill file exists. Add a missing-skill pin that still lists the four tools. Add a mocked-pipe pin that a schema-rejection line raises immediately. Add a micro pin that `_invoke_agent` / `deviate micro run` logs `AGENT_ERROR` and fails with those tokens. Mock `Popen` and `deviate.cli.micro._run_pytest`. Do not sleep the stall budget.
  - **Verification**: `uv run pytest tests/unit/test_core/test_agent.py tests/unit/core/test_agent.py tests/unit/test_cli/test_micro.py -q -k "pi and (rpc or tool or lean or schema or invoke)"` fails on the new pins.

- **Phase 2**: GREEN lean argv helper
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: After `invoke` copies `PI_RPC_COMMAND` or splits `BACKEND_COMMANDS["pi"]`, append the lean flags for backend `pi` only. Resolve the skill path from invoke `cwd` or `Path.cwd()`. Do not rewrite the constant strings. Do not add `--no-tools`. Leave OMP, claude, opencode, and droid argv unchanged unless they share the helper.
  - **Verification**: Print-mode and RPC argv pins pass. AC-009-07 and AC-009-10 stay green.

- **Phase 3**: GREEN schema-token abort
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: Scan each stderr and stdout line in `_invoke_streaming`, `_invoke_blocking`, and `_invoke_rpc_blocking`. On the first `tool_count_limit` or `unsupported_tool_schema` match, kill the child and raise `AgentSubprocessError` or a subclass whose message includes the tokens. Raise before `parse_output` so `EmptyOutputError` cannot retry. Do not refresh `stall_deadline` for those lines. Do not sleep 30s.
  - **Verification**: The fail-fast pin raises with the tokens and calls `kill`. Existing stall pins from ISS-ADH-025 stay green.

- **Phase 4**: GREEN harness-visible error
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Log `AGENT_ERROR` with the exception text. Re-raise the schema error or map it to `PhaseFailedError` so RED, GREEN, and REFACTOR include the tokens. Keep the GREEN timeout-summary path only for real timeout tails. Leave meso `_invoke_agent_phase` unchanged when it already prints `AgentSubprocessError`.
  - **Verification**: The micro pin shows `AGENT_ERROR` and a `PhaseFailedError` that contains the tokens, not only `agent returned no manifest`.

- **Phase 5**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Document the lean Pi spawn policy and the fail-fast schema-rejection contract. Append the `[Unreleased]` bullet in the same implementation commit.
  - **Verification**: Docs name `--no-extensions`, the four coding tools, and the token-bearing `AGENT_ERROR`. `mise run check` stays green.

## Data Flow Analysis
`AgentBackend.invoke` still starts from `BACKEND_COMMANDS["pi"]` or `PI_RPC_COMMAND`. It then appends the lean flags and optional `--skill`. `Popen` still inherits `env=None`.

The child writes provider errors on stderr or stdout. The invoke helper scans each line. A `tool_count_limit` or `unsupported_tool_schema` match kills the child and raises `AgentSubprocessError` (or subclass). `invoke` does not parse YAML and does not start a second `Popen`.

`_invoke_agent` logs `AGENT_ERROR` with that message. RED, GREEN, and REFACTOR raise `PhaseFailedError` that still contains the tokens. Meso TASKS already prints `AgentSubprocessError` and exits 1.

A healthy invoke with no such tokens still returns a parsed `HandoverManifest`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Lean flags break AC-009-07 / AC-009-10 prefix pins | High | Medium | Append flags after the existing prefix. Keep `BACKEND_COMMANDS["pi"] == "pi -p"` and RPC `--no-session` tests. |
| `--no-tools` or a missing skill strips coding tools | High | Medium | Allowlist `read`, `bash`, `edit`, `write`. Pin the missing-skill case. Never emit `--no-tools` or `--no-builtin-tools`. |
| GREEN treats schema-error text as timeout context | High | High | Do not return schema tokens only as the second `_invoke_agent` tuple. Re-raise or map to `PhaseFailedError` before the `timeout_ctx` branch. |
| Schema tokens reset the 900s stall clock (ISS-ADH-025) | High | Medium | Fail-fast kill is a separate path. Do not call `refresh_stall_deadline` for those lines. Keep stderr diagnostic for stall liveness. |
| EmptyOutputError retries the same oversized schema | High | High | Raise `AgentSubprocessError` before `parse_output`. Existing policy already skips manifest retry for subprocess errors. |
| Live `pi --mode rpc` used as the acceptance path | Medium | Low | Tests mock `Popen`. Do not add a live RPC pipe test. |
| Un-mocked `_run_pytest` blows the 30s suite budget | High | Medium | Mock `deviate.cli.micro._run_pytest` on any CLI path that can reach it. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess, file paths
Negative tests: missing `.pi/skills/deviatdd/SKILL.md` still keeps `read`, `bash`, `edit`, and `write`; default argv never includes `--no-tools` or `--no-builtin-tools`; first schema-rejection line kills the child and does not wait for 900s; `EmptyOutputError` does not retry a `tool_count_limit` failure; non-Pi backends keep their current argv
Constraints: no new dependencies; no hardcoded secrets; keep `env=None` inheritance; do not write operator-local `.deviate/config.toml`; resolve the skill path only as a local file check under invoke `cwd`

## Integration Points
- **Pi print-mode spawn**: `BACKEND_COMMANDS["pi"]` stays `pi -p`. Lean flags follow that prefix. `--model` injection stays on this path.
- **Pi RPC spawn**: `PI_RPC_COMMAND` stays `pi --mode rpc --no-session`. Lean flags follow that prefix.
- **Micro harness**: `_invoke_agent` logs `AGENT_ERROR`. RED, GREEN, and REFACTOR raise a token-bearing `PhaseFailedError`.
- **Meso TASKS**: `_invoke_agent_phase` already prints `AgentSubprocessError` and exits 1.
- **ISS-ADH-025 stall detector**: stderr stays diagnostic. Schema-token abort does not become a new liveness channel.
- **GH-53 EXECUTE budget**: `EXECUTE_STALL_TIMEOUT_SECONDS` stays 3600.

## Constitutional Alignment
- **Architecture**: This work stays in the Micro invoke path inside `C1`. It does not skip a layer and does not add a ledger row type. It implements constitution §1 Micro-Layer Scope and §2 Agent Backend subprocess isolation.
- **Testing**: RED writes pytest pins with mocked `Popen`. GREEN makes those pins pass. Coverage follows constitution §3 (`pytest tests/ -v`, suite under 30s).
- **Git Isolation**: Work stays on the preconfigured issue worktree. Commits happen at phase boundaries. This plan does not delete a branch.
- **Product Layer**: `flow_refs` is `[]`. This plan does not author or sync flows. The behavior serves the Pi spawn used by micro and meso agents, not FLOW-04 TUI streaming.
