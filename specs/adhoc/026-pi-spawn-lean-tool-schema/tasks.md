# Implementation Tasks: `feat/adhoc/026-pi-spawn-lean-tool-schema`

## Phase 1: Lean Pi Spawn Argv
**Goal**: Print-mode and RPC Pi argv keep their transport prefix. They then add `--no-extensions`, `--no-skills`, optional `--skill`, and `--tools` listing `read`, `bash`, `edit`, and `write`.

### Tasks

- TSK-026-01: Append lean Pi flags and keep the four coding tools
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/core/test_agent.py -q -k "pi and (rpc or tool or lean or skill or invoke)"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
    - `tests/core/test_agent.py`
  - **Rationale**: US-026-01 and `AC-PLAN-001` require `AgentBackend.invoke` to keep `BACKEND_COMMANDS["pi"] == "pi -p"` and RPC `--mode rpc --no-session`, then append `--no-extensions` (or `-ne`) and `--no-skills` (or `-ns`). Add `--skill` to `.pi/skills/deviatdd/SKILL.md` when that file exists under invoke `cwd`. Keep print-mode `--model` injection. US-026-02 and `AC-PLAN-002` require `--tools` listing `read`, `bash`, `edit`, and `write`. Omit `--no-tools` and `--no-builtin-tools`. A missing skill file still lists those four tools. Non-Pi backends keep their current argv. `src/deviate/core/agent.py` owns `invoke` argv. `tests/test_core/test_agent.py` pins print-mode and AC-009-07. `tests/core/test_agent.py` pins RPC AC-009-10. Constitution §3 Testing Protocols: mocked `Popen`, no live `pi`. Constitution §1 Micro-Layer Scope: GREEN writes `src/deviate/core/agent.py` for this slice.
  - **Details**:
    - **Red**: In `tests/test_core/test_agent.py`, keep `test_agent_uses_pi_command_default` and `test_backend_commands_includes_pi`. Add `test_pi_print_mode_lean_spawn_flags` that calls `invoke` with mocked `Popen`. Assert argv starts from `pi -p`. Assert `--no-extensions` or `-ne`. Assert `--no-skills` or `-ns`. Assert `--tools` lists `read`, `bash`, `edit`, and `write`. Assert `--no-tools` and `--no-builtin-tools` are absent. When `.pi/skills/deviatdd/SKILL.md` exists under invoke `cwd`, assert `--skill` points at that path. Add `test_pi_lean_tools_remain_when_skill_missing` that still lists the four tools. Keep `test_pi_backend_model_flag_injected` green. In `tests/core/test_agent.py`, extend `TestPiRpcMode.test_pi_rpc_mode_opt_in` or add `test_pi_rpc_lean_spawn_flags`. Assert `--mode rpc` and `--no-session` stay. Assert `-p` stays absent. Assert the same lean flags and four tools. Pin a non-Pi backend argv that does not gain the Pi flags unless it shares the helper (`AC-PLAN-001`, `AC-PLAN-002`).
    - **Green**: In `AgentBackend.invoke`, after the copy of `PI_RPC_COMMAND` or the split of `BACKEND_COMMANDS["pi"]`, append `--no-extensions`, `--tools read,bash,edit,write`, and `--no-skills` for backend `pi` only. Resolve `.pi/skills/deviatdd/SKILL.md` from invoke `cwd` or `Path.cwd()`. Add `--skill` only when that file exists. Do not rewrite `BACKEND_COMMANDS["pi"]` or `PI_RPC_COMMAND`. Leave `env=None`. Leave OMP, claude, opencode, and droid argv unchanged.
    - **Refactor**: Keep lean-flag append in one helper so print mode and RPC share the same policy.
    - **Edge Cases**: Missing skill file still emits the four tools. Default argv never includes `--no-tools` or `--no-builtin-tools`. Operator-local `pi_rpc` stays unread as a flip. Do not write `.deviate/config.toml`.
    - **Acceptance**: Print-mode argv keeps `pi -p` plus `--model`. RPC argv keeps `--mode rpc --no-session`. Both lists carry lean flags and the four coding tools. AC-009-07 and AC-009-10 stay green.

---

## Phase 2: Schema-Rejection Fail-Fast
**Goal**: The first `tool_count_limit` or `unsupported_tool_schema` line kills the child. `AgentSubprocessError` carries those tokens. The 900s stall clock and `EmptyOutputError` retry stay unused.

### Tasks

  - **Judge Feedback**: JUDGE evidence is missing, empty, or partial for injected acceptance tokens: AC-PLAN-003, AC-PLAN-004
- TSK-026-02: Abort the child on the first schema-rejection line
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/core/test_agent.py -q -k "schema or tool_count or unsupported_tool"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
    - `tests/core/test_agent.py`
  - **Rationale**: US-026-03 and `AC-PLAN-003` require `_invoke_streaming`, `_invoke_blocking`, and `_invoke_rpc_blocking` to kill the child on the first stderr or stdout line that contains `tool_count_limit` or `unsupported_tool_schema`. Raise `AgentSubprocessError` or a subclass whose message contains those tokens. Skip `STREAM_STALL_TIMEOUT_SECONDS` (900s). Skip the 30s timeout retry. Do not start the `EmptyOutputError` manifest retry. Do not treat those tokens as stall liveness. `src/deviate/core/agent.py` owns the invoke helpers. `tests/test_core/test_agent.py` owns the streaming and blocking pins. `tests/core/test_agent.py` owns the RPC blocking pin. Constitution §3: mocked pipes, patched short stall budget, no 900s sleep. ISS-ADH-025 stays composed: stderr remains diagnostic for stall liveness.
  - **Details**:
    - **Red**: In `tests/test_core/test_agent.py`, add `test_invoke_aborts_on_tool_count_limit_line`. Mock `Popen` so the child writes `400 tool_count_limit` or `unsupported_tool_schema` on stderr or stdout, then stays open with empty manifest output. Patch the stall budget short or unused. Assert `AgentSubprocessError` (or subclass) matches `tool_count_limit` or `unsupported_tool_schema`. Assert `kill` is called. Assert `time.sleep` is not called with 30. Assert `EmptyOutputError` retry does not start. Cover `_invoke_streaming` and `_invoke_blocking`. In `tests/core/test_agent.py`, add a RPC pin through `_invoke_rpc_blocking` with the same tokens (`AC-PLAN-003`). Keep `test_streaming_agent_stderr_only_noise_trips_stall` and `test_invoke_streaming_stall_does_not_retry` green. Do not sleep 900s.
    - **Green**: Scan each stderr and stdout line in `_invoke_streaming`, `_invoke_blocking`, and `_invoke_rpc_blocking`. On the first `tool_count_limit` or `unsupported_tool_schema` match, kill the child and raise `AgentSubprocessError` or a subclass whose message includes the tokens. Raise before `parse_output`. Do not call `refresh_stall_deadline` for those lines. Do not treat the tokens as stall liveness. Do not start a second `Popen`.
    - **Refactor**: Share one token matcher so all three invoke helpers raise the same error text.
    - **Edge Cases**: Tokens on stdout also abort. A healthy invoke with no such tokens still parses a YAML `HandoverManifest`. `EmptyOutputError` still retries genuine empty YAML. ISS-ADH-025 stderr-only stall pins stay green. GH-53 `EXECUTE_STALL_TIMEOUT_SECONDS` stays 3600.
    - **Acceptance**: The first matching line kills the child. The raised error contains `tool_count_limit` or `unsupported_tool_schema`. The 900s stall clock and the 30s retry stay unused.
  - **Dependency**: TSK-026-01

---

## Phase 3: Harness-Visible Schema Tokens
**Goal**: `_invoke_agent` logs `AGENT_ERROR` with the schema tokens. RED, GREEN, and REFACTOR raise `PhaseFailedError` that still contains those tokens.

### Tasks

- TSK-026-03: Surface schema tokens from `deviate micro run`
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_cli/test_micro.py -q -k "schema or tool_count or unsupported_tool or AGENT_ERROR"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-026-03 and `AC-PLAN-004` require `_invoke_agent` to log `AGENT_ERROR` containing `tool_count_limit` or `unsupported_tool_schema`. RED, GREEN, and REFACTOR must raise `PhaseFailedError` that includes those tokens instead of only `agent returned no manifest`. Do not route a schema-limit failure through the GREEN `timeout_ctx` summary path. `src/deviate/cli/micro.py` owns `_invoke_agent`, `_run_red_phase`, `_run_green_phase`, and `_run_refactor_phase`. `tests/test_cli/test_micro.py` owns the harness pin. Constitution §3 and AGENTS.md: mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess`. Do not use a live `pi --mode rpc` pipe. Meso `_invoke_agent_phase` already prints `AgentSubprocessError`; leave `src/deviate/cli/meso.py` unchanged when the message already carries the tokens.
  - **Details**:
    - **Red**: In `tests/test_cli/test_micro.py`, add `test_invoke_agent_logs_schema_limit_tokens` and a `deviate micro run` or `_run_green_phase` pin. Mock `Popen` so the child emits `unsupported_tool_schema` or `tool_count_limit`, or mock `AgentBackend.invoke` to raise `AgentSubprocessError` with those tokens. Assert the console or log contains `AGENT_ERROR` plus the tokens. Assert the operator-visible `PhaseFailedError` contains `tool_count_limit` or `unsupported_tool_schema`. Assert the message is not only `agent returned no manifest`. Cover RED and REFACTOR mapping when those helpers collapse a `None` manifest. Mock `deviate.cli.micro._run_pytest`. Do not start a live Pi child (`AC-PLAN-004`).
    - **Green**: After `_invoke_agent` logs `AGENT_ERROR`, keep the tokens on the raised or returned error. Map the schema error to `PhaseFailedError` for RED, GREEN, and REFACTOR so the tokens remain. Do not return schema tokens only as the second `_invoke_agent` tuple. Keep the GREEN timeout-summary path only for real timeout tails. Do not change `EXECUTE_STALL_TIMEOUT_SECONDS` (3600).
    - **Refactor**: Keep one mapping from `AgentSubprocessError` text into `PhaseFailedError` so RED, GREEN, and REFACTOR share the same token-bearing message.
    - **Edge Cases**: A truthy second tuple must not become timeout context for a schema-limit failure. Meso TASKS still prints `AgentSubprocessError` and exits 1. Do not un-mock `_run_pytest`.
    - **Acceptance**: `AGENT_ERROR` contains the tokens. Operator-visible `PhaseFailedError` contains the tokens. GREEN does not summarize the failure as a timeout.
  - **Dependency**: TSK-026-02

---

## Phase 4: Specs and Changelog
**Goal**: API and architecture name the lean Pi spawn policy and the fail-fast schema-rejection path. CHANGELOG records the user-visible spawn and error change.

### Tasks

- TSK-026-04: Document lean Pi spawn and token-bearing `AGENT_ERROR`
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_core/test_agent.py tests/core/test_agent.py tests/test_cli/test_micro.py -q -k "pi and (rpc or tool or lean or schema or invoke or skill or AGENT_ERROR)"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-004` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` for this user-visible spawn and error change. US-026-01 is the lean default. US-026-02 is the four coding tools. US-026-03 is the token-bearing `AGENT_ERROR`. AGENTS.md Spec Alignment requires both spec files in the same change as the implementation. Constitution §1 Four-Layer Architecture: this slice stays in `C1` and does not author Product-layer flows.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md` Agent Backend Hardening, state that default Pi spawn adds `--no-extensions`, `--tools read,bash,edit,write`, `--no-skills`, and optional `--skill` to `.pi/skills/deviatdd/SKILL.md`. State that `tool_count_limit` / `unsupported_tool_schema` abort the child and surface as `AGENT_ERROR`. Keep AC-009-07 / AC-009-10 prefix text.
    - **Implementation**: In `specs/DeviaTDD-architecture.md` Pi backend section, document the lean default and the fail-fast schema-rejection path. Keep `pi -p`, `--model`, and RPC `--no-session` wording.
    - **Implementation**: Append one `[Unreleased]` bullet in `CHANGELOG.md`: default Pi spawn is lean, and schema-limit tokens surface immediately on `deviate micro run`.
    - **Implementation**: Re-run the Phase 1 through Phase 3 pins. Do not author or sync Product-layer flows. Do not change TSK id format.
    - **Refactor**: Reuse the existing Agent Backend Hardening and Pi backend wording. Do not add a second spawn constant or a second retry contract.
    - **Edge Cases**: Docs still say stderr is not stall liveness. Docs still say EXECUTE stall stays 3600s. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture name `--no-extensions`, the four coding tools, and token-bearing `AGENT_ERROR`. CHANGELOG `[Unreleased]` has the ISS-ADH-026 bullet. Existing pins stay green.
  - **Dependency**: TSK-026-03

---

## Phase 5: CLI E2E
**Goal**: The installed `deviate` package appends lean Pi flags and fails fast on schema-rejection tokens.

### Tasks

- TSK-026-05: [E2E] Verify installed Pi spawn is lean and schema tokens abort
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_pi_spawn_lean_tool_schema.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: US-026-01 and `AC-PLAN-001` are the happy path: installed `AgentBackend.invoke` argv stays lean. US-026-02 and `AC-PLAN-002` keep `read`, `bash`, `edit`, and `write`. US-026-03 and `AC-PLAN-003` / `AC-PLAN-004` are the critical-failure path: a mocked child that emits `unsupported_tool_schema` raises a token-bearing `AgentSubprocessError` without a 900s wait. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_pi_spawn_lean_tool_schema.bats`. Happy path: a short Python snippet against the installed package mocks `Popen`, calls `AgentBackend.invoke` for print mode, and asserts argv contains `pi`, `-p`, `--no-extensions` or `-ne`, `--no-skills` or `-ns`, and `--tools` listing `read`, `bash`, `edit`, and `write`. Assert `--no-tools` is absent. `deviate micro --help` exits 0.
    - **Implementation**: Critical-failure path in the same bats file: mock `Popen` pipes so stderr yields `400 tool_count_limit` / `unsupported_tool_schema`, keep stdout empty, and call `invoke`. Assert `AgentSubprocessError` (or subclass) matches those tokens and that `kill` runs. Do not sleep 900s. Do not start a live `pi --mode rpc` child.
    - **Implementation**: Keep `tests/e2e/test_macro_workflow.bats` as the existing CLI smoke suite. Do not call un-mocked `_run_pytest`.
    - **Refactor**: Reuse the bats tmpdir setup/teardown pattern from `tests/e2e/test_green_stderr_stall.bats`.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` is unused. Do not delete branches in the host repo.
    - **Acceptance**: `bats tests/e2e/` exits 0. Installed print-mode argv is lean. Installed invoke aborts on the first schema-rejection line.
  - **Dependency**: TSK-026-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5

**Critical Dependency Chains**:
- TSK-026-01 must precede TSK-026-02
- TSK-026-02 must precede TSK-026-03
- TSK-026-03 must precede TSK-026-04
- TSK-026-04 must precede TSK-026-05

**Risk Hotspots**:
- Lean flags rewrite `BACKEND_COMMANDS["pi"]` and break AC-009-07 / AC-009-10
- `--no-tools` or a missing skill strips `read`, `bash`, `edit`, or `write`
- GREEN treats schema-error text as `timeout_ctx` and hides the tokens
- Schema tokens reset the 900s stall clock from ISS-ADH-025
- `EmptyOutputError` retries the same oversized schema
- Live `pi --mode rpc` used as the acceptance path
- Un-mocked `_run_pytest` blows the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/agent.py`, `tests/test_core/test_agent.py`, `tests/core/test_agent.py`. Phase 1 owns lean argv. Phase 2 owns schema-token abort. Phase 3 owns `src/deviate/cli/micro.py`. Phase 4 owns specs and CHANGELOG only.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/026-pi-spawn-lean-tool-schema/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
