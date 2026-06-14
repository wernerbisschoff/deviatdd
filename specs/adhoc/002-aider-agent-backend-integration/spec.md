# FEATURE_SPECIFICATION: specs/adhoc/002-aider-agent-backend-integration/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `adhoc`
- **Issue ID**: `ISS-ADH-002`
- **Issue Title**: `Aider Agent Backend Integration`
- **Coordinates With**: `ISS-001-004` (Micro-layer TDD Sandbox — agent backend abstraction)
- **Blocked By**: None
- **Workstation Paths**:
  - `src/deviate/core/agent.py` — Add `AiderBackend` subclass with aider-specific subprocess invocation and output parsing
  - `src/deviate/state/config.py` — Add `AiderConfig` Pydantic model, extend `AgentConfig.backend` Literal to include `"aider"`
  - `tests/test_core/test_agent.py` — Aider-specific unit tests (invocation, config, parsing)
  - `tests/test_integration/test_aider_backend.py` — Full aider invocation integration tests

## THE_PROBLEM_CONTRACT

As a developer using `aider` as my AI coding agent, I need the `deviate` CLI to support invoking aider as a subprocess in automated micro/meso/macro pipelines — with aider-specific prompt formatting (`--message`), flag handling (`--yes`, `--no-auto-commits`, `--file`, `--read`), and output parsing (chat-style instead of YAML manifests) — so that the full DeviaTDD workflow can run with aider as the code-generation backend alongside the existing opencode/claude/droid backends.

Aider has fundamentally different invocation semantics than opencode/claude/droid: no heredoc pipe (uses `--message` instead), interactive by default (requires `--yes` + `--no-suggest-shell-commands`), file context via `--file`/`--read` args, and chat-style output requiring custom parsing. This issue extends the existing `AgentBackend` abstraction from ISS-001-004 to support this fourth backend.

## SCOPE_BOUNDARIES

### Hard Inclusions

- **`AiderBackend` provider** in `src/deviate/core/agent.py`:
  - Extend `BACKEND_COMMANDS` map with `"aider": "aider"`
  - Build invocation command from `AiderConfig` + slim prompt: `aider --message "<prompt>" --yes --no-suggest-shell-commands --no-auto-commits --model <model> [--read files...] [--file paths...]`
  - Invoke via `subprocess.Popen()` with configured timeout and timeout retry
  - Capture stdout, check exit code
  - If aider binary not found on PATH, hard abort with `AIDER_NOT_FOUND` error and exit non-zero
  - Post-invocation: always run `mise run test` (or `mise run check` for full validation) regardless of aider's reported success/failure in output
  - Parse aider output for file modifications, test results, error messages
  - Map parsed data to `HandoverManifest` schema for phase sequencing
- **`AiderConfig` Pydantic model** in `src/deviate/state/config.py`:
  - `model: str = "claude-sonnet-4-20250514"` — Model selection
  - `auto_commits: bool = False` — Delegate all git operations to deviate CLI
  - `suggest_shell_commands: bool = False` — Prevent aider from suggesting shell commands
  - `yes_mode: bool = True` — Auto-confirm all aider actions (non-interactive)
  - `read_files: list[str] = Field(default_factory=lambda: ["specs/constitution.md", "CLAUDE.md"])` — Read-only context files
  - `extra = "forbid"` — Reject unknown config fields
- **Configuration wiring**:
  - `AgentConfig.backend` Literal extended to `Literal["opencode", "claude", "droid", "aider"]`
  - `AgentConfig.aider: AiderConfig = Field(default_factory=AiderConfig)` field added
  - Nested in `DeviateConfig.agent` → `.deviate/config.toml` round-trip
- **Constitution & CLAUDE.md injection** via `--read` flags:
  - If `specs/constitution.md` exists, add `--read specs/constitution.md` to invocation
  - If constitution is missing, **abort with error** (constitution is mandatory per architectural principles)
  - If `CLAUDE.md` exists, add `--read CLAUDE.md`
  - If CLAUDE.md is missing, skip silently
- **Output parsing**:
  - Parse for test result indicators: `"All tests passed"`, `"N tests passed"`, `"N failed"`, `"FAILED"`
  - Parse for modified file paths from aider output log
  - Parse for error messages and stack traces
  - Map to `HandoverManifest` with `status: "PASS"` or `status: "FAIL"`, `files_touched`, `verification_result`

### Defensive Exclusions

- Interactive aider mode (chat, follow-up questions) — automated pipeline only supports single-shot `--message` mode.
- Aider configuration management beyond `.deviate/config.toml` — no `.aider.conf.yml` generation or management.
- Model API key management — delegated to aider's own environment/configuration.
- Aider version pinning — delegated to `mise.toml` or user environment.
- Fallback to alternative backend on aider failure — `AIDER_NOT_FOUND` is a hard abort.
- Tamper Guard implementation — already covered by ISS-001-004.

## PERFORMANCE_CONSTRAINTS

- `L_max <= 200ms` for aider output parsing and `HandoverManifest` construction.
- `L_max <= 500ms` for aider command building and pre-flight checks (binary existence, file existence).
- Aider subprocess time is excluded from constraint — governed by `AgentConfig.timeout` (default 600s).

## MULTI_TIERED_VERIFICATION_TARGETS

- **Unit Tests**:
  - `tests/test_core/test_agent.py` — Aider-specific invocation, config validation, output parsing, missing binary, missing constitution
- **Integration Tests**:
  - `tests/test_integration/test_aider_backend.py` — Full aider invocation in automated pipeline, Tamper Guard interaction, post-invocation `mise run test` guard

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-AIDER-BACKEND: AiderBackend implements AgentBackend interface with aider-specific subprocess invocation

* **Upstream Requirement Traceability**: FR-ADHOC-010-AIDER-BACKEND

1. **Given** `.deviate/config.toml` with `agent.backend = "aider"` and valid `agent.aider` config
   **When** the CLI invokes an agent for a RED phase task
   **Then** Aider is invoked via `aider --message "<prompt>" --yes --no-suggest-shell-commands --no-auto-commits --model <model> --read specs/constitution.md --read CLAUDE.md --file src/**/*.py`, its stdout is captured, and file/test results are parsed from aider's chat-style output.

2. **Given** the `aider` binary is not found on PATH
   **When** the CLI attempts to invoke the aider backend
   **Then** the CLI exits with `AIDER_NOT_FOUND` error and exits non-zero, with no fallback to another backend.

3. **Given** `AiderConfig` with `model = "deepseek"`
   **When** the aider backend builds the invocation command
   **Then** the `--model deepseek` flag is included in the subprocess call.

4. **Given** `AiderConfig` with `auto_commits = true`
   **When** the aider backend builds the invocation command
   **Then** the `--no-auto-commits` flag is omitted (allowing aider to auto-commit).

5. **Given** `AiderConfig` with `suggest_shell_commands = true`
   **When** the aider backend builds the invocation command
   **Then** the `--no-suggest-shell-commands` flag is omitted.

6. **Given** `AiderConfig` with `yes_mode = false`
   **When** the aider backend builds the invocation command
   **Then** the `--yes` flag is omitted (interactive mode — used for manual debug only).

### US-002-AIDER-CONFIG: AiderConfig model validates and serializes correctly

* **Upstream Requirement Traceability**: FR-ADHOC-010-AIDER-CONFIG

1. **Given** a valid `AiderConfig` with default values
   **When** validated with Pydantic
   **Then** `model` is `"claude-sonnet-4-20250514"`, `auto_commits` is `False`, `suggest_shell_commands` is `False`, `yes_mode` is `True`, and `read_files` contains `["specs/constitution.md", "CLAUDE.md"]`.

2. **Given** an `AiderConfig` with extra fields not in the schema
   **When** validated with Pydantic
   **Then** `ValidationError` is raised due to `extra = "forbid"`.

3. **Given** an `AgentConfig` with `backend = "aider"` and custom `aider` config
   **When** serialized to TOML and deserialized back
   **Then** all fields round-trip correctly, including nested `aider` fields.

4. **Given** an `AgentConfig` with `backend = "aider"` but no `aider` sub-config
   **When** accessing `agent.aider`
   **Then** default `AiderConfig` values are used.

### US-003-AIDER-PARSE: Aider output parsing extracts file modifications and test results

* **Upstream Requirement Traceability**: FR-ADHOC-010-AIDER-PARSE

1. **Given** aider output containing `"All tests passed"` and modified file paths like `src/deviate/cli/micro.py`
   **When** `AiderBackend.parse_output()` parses the output
   **Then** an `AgentResult` is returned with `status = "PASS"`, `files_touched` containing the modified paths, and `verification_result = "PASS"`.

2. **Given** aider output containing `"1 failed"` or `"FAILED"` with error details
   **When** `AiderBackend.parse_output()` parses the output
   **Then** an `AgentResult` is returned with `status = "FAIL"`, `verification_result = "FAIL"`, and `error_details` containing the failure context.

3. **Given** aider output that does not contain explicit pass/fail indicators (ambiguous output)
   **When** `AiderBackend.parse_output()` parses the output
   **Then** an `AgentResult` is returned with `status = "PASS"` (optimistic default) but `verification_result = "UNKNOWN"`, and the post-invocation `mise run test` guard will independently verify.

4. **Given** aider output in an unexpected format that cannot be parsed
   **When** `AiderBackend.parse_output()` attempts to parse it
   **Then** an `AIDER_PARSE_ERROR` diagnostic is raised with the raw output included, but the pipeline does not hard-abort — falls through to post-invocation `mise run test` guard.

### US-004-AIDER-CONTEXT: Constitution and CLAUDE.md injected via aider's `--read` flag

* **Upstream Requirement Traceability**: FR-ADHOC-010-AIDER-CONTEXT

1. **Given** `specs/constitution.md` exists at the repository root
   **When** the aider backend builds the invocation command
   **Then** `--read specs/constitution.md` is included in the command arguments.

2. **Given** `specs/constitution.md` is missing or unreadable
   **When** the aider backend builds the invocation command
   **Then** the CLI aborts with a `CONSTITUTION_MISSING` error and exits non-zero.

3. **Given** `CLAUDE.md` exists at the repository root
   **When** the aider backend builds the invocation command
   **Then** `--read CLAUDE.md` is included in the command arguments.

4. **Given** `CLAUDE.md` is missing
   **When** the aider backend builds the invocation command
   **Then** no `--read` flag for CLAUDE.md is added to the command arguments (non-fatal skip).

### US-005-POST-GUARD: `mise run test` runs after every aider invocation regardless of output

* **Upstream Requirement Traceability**: FR-ADHOC-010-AIDER-BACKEND

1. **Given** aider exits with exit code 0 and its output claims `"All tests passed"`
   **When** the post-invocation guard runs `mise run test`
   **Then** `mise run test` is executed unconditionally; if tests actually fail, the phase is treated as failed with a `POST_GUARD_FAILED` error including the test output.

2. **Given** aider exits with exit code 0 but output is ambiguous (no pass/fail indicators)
   **When** the post-invocation guard runs `mise run test`
   **Then** the guard runs regardless and provides the definitive verification result.

3. **Given** aider exits non-zero
   **When** the CLI receives the non-zero exit code
   **Then** the phase aborts immediately without running the post-invocation guard, with aider's stderr surfaced as the error.

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|---|---|
| **STATUS** | SPECIFY |
| **EPIC_SLUG** | `adhoc` |
| **BRANCH_NAME** | `feat/adhoc/002-aider-agent-backend-integration` |
| **SPEC_PATH** | `specs/adhoc/002-aider-agent-backend-integration/spec.md` |
| **ISSUE_ID** | `ISS-ADH-002` |
| **NEXT_ACTION** | TASKS |
