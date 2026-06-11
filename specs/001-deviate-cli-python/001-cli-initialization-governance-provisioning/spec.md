# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/001-cli-initialization-governance-provisioning/spec.md

## SYSTEM_TOPOLOGY_MAPPING
- **Epic Domain**: `001-deviate-cli-python`
- **Issue ID**: `ISS-001-001`
- **Issue Slug**: `001-cli-initialization-governance-provisioning`
- **Upstream PRD**: `specs/001-deviate-cli-python/prd.md`
- **Branch**: `feat/001-deviate-cli-python/001-cli-initialization-governance-provisioning`
- **Primary Workstation Paths**:
  - `src/deviate/cli/__init__.py` — CLI command tree, `init` subcommand implementation
  - `src/deviate/main.py` — Runtime bootstrap entry point exposing the Typer app
  - `src/deviate/state/config.py` — `DeviateConfig` and `SessionState` Pydantic models
  - `src/deviate/prompts/constitution_seed.md` — Tokenized boilerplate constitution template
  - `tests/test_cli/test_init.py` — Unit tests for `init` subcommand
  - `tests/test_state/test_config.py` — Unit tests for Pydantic state models
  - `tests/test_integration/test_init_export_cycle.py` — Integration tests for full init cycle
- **Downstream Dependency Graph**:
  ```
  FR-005-STATE (Foundation — Pydantic models)
     └─► FR-001-INIT (Requires DeviateConfig / SessionState)
            └─► FR-002-MACRO (Requires initialized constitution & session)
  ```

## THE_PROBLEM_CONTRACT
As a developer setting up the DeviaTDD environment, I need the `deviate init` command to scaffold the `.deviate/` directory structure, provision default configuration and session state using strict Pydantic validation, and idempotently update project-level agent governance files (`CLAUDE.md`, `AGENTS.md`) and the `specs/constitution.md` boilerplate, so that the workspace is ready for Macro-layer operations without manual setup. The init command must handle partial or interrupted prior runs by detecting and completing missing scaffolding, and must never overwrite user-customized configuration files.

## SCOPE_BOUNDARIES
### Hard Inclusions
- `deviate init` Typer subcommand implementation as the primary CLI entry point for workspace initialization.
- Pydantic-based state models (`DeviateConfig`, `SessionState`) with `extra="forbid"` validation and typed field constraints.
- Scaffolding of `.deviate/config.toml` (TOML format) and `.deviate/session.json` (JSON format) with valid defaults.
- Idempotent provisioning of `specs/constitution.md` from the tokenized boilerplate template at `src/deviate/prompts/constitution_seed.md`.
- Idempotent append/write mechanics for `CLAUDE.md` and `AGENTS.md`: append the `## DeviaTDD Orchestration Rules` block at end-of-file if absent; overwrite only that block in-place if it already exists.
- Partial scaffold recovery: detect and complete only missing files in `.deviate/` when a previous `init` was interrupted.
- Filesystem-preservation rule: existing `.deviate/config.toml` and `.deviate/session.json` are never overwritten; only missing files are created.
- `--generate-constitution` flag to invoke LLM-driven constitution generation (offline template resolution is the default, non-flagged path).
- `--agent-export-mode` flag accepting `local` or `global` for agent governance file routing.

### Defensive Exclusions
- Execution of Macro, Meso, or Micro layer commands (out of scope for init phase).
- OS-level file locking for concurrency safety (delegated to FR-005-STATE).
- Dynamic LLM-driven constitution generation as the default path (offline template resolution only; `--generate-constitution` gates dynamic generation).
- Remote network calls during offline context resolution.
- Modification of existing `CLAUDE.md` or `AGENTS.md` content outside the `## DeviaTDD Orchestration Rules` block.

## PERFORMANCE_CONSTRAINTS
- **`L_max <= 500ms`** for `deviate init` command execution (wall-clock time from invocation to completion, excluding optional `--generate-constitution` LLM calls).
- **`L_max <= 50ms`** for offline tokenized placeholder resolution in constitution boilerplate.
- **`L_max <= 200ms`** per agent governance file export operation.
- Pydantic validation must be eager on write (fail-fast on invalid state) but may be lazy on read to meet performance targets.

## MULTI_TIERED_VERIFICATION_TARGETS
- **Unit Tests (Pydantic Models)**: `tests/test_state/test_config.py` — validates `DeviateConfig` and `SessionState` schemas, field constraints, `extra="forbid"` enforcement, and IO round-trip cycles.
- **Unit Tests (Init Command)**: `tests/test_cli/test_init.py` — validates directory scaffolding, file creation, idempotency behavior, governance block placement, partial recovery, and error paths.
- **Integration Tests**: `tests/test_integration/test_init_export_cycle.py` — validates full end-to-end `deviate init` cycle completes within `L_max <= 500ms` and all output files are structurally valid.
- **Demonstration Path**:
  ```bash
  pytest tests/test_cli/test_init.py -v
  pytest tests/test_state/test_config.py -v
  pytest tests/test_integration/test_init_export_cycle.py -v
  ```

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-SCAF: Directory & File Scaffolding
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: The `deviate init` command creates the `.deviate/` directory and populates it with a valid `config.toml` and `session.json` when none exist.
* **Scenario — Clean Repository Initialization**:
  - **Given**: A repository root with no `.deviate/` directory.
  - **When**: The user executes `deviate init`.
  - **Then**: `.deviate/config.toml` exists with valid TOML structure matching the `DeviateConfig` schema, `.deviate/session.json` exists with valid JSON matching the `SessionState` schema, and the CLI exits with code `0`.
* **Scenario — Idempotent Re-run on Complete Scaffold**:
  - **Given**: `.deviate/config.toml` and `.deviate/session.json` already exist and are valid.
  - **When**: The user executes `deviate init`.
  - **Then**: No files are overwritten, the CLI outputs an idempotency skip message for each file, and exits with code `0`.

### US-002-CONF: Configuration & Session State Validation
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: The written `config.toml` and `session.json` files conform to strict Pydantic schemas with `extra="forbid"`, valid field types, and enforced constraints.
* **Scenario — Valid Default Configuration Write**:
  - **Given**: A clean repository root.
  - **When**: The user executes `deviate init`.
  - **Then**: `.deviate/config.toml` contains exactly the fields defined in `DeviateConfig` (`profile`, `llm_backend`, `timeout_seconds`, `agent_export_mode`) with their documented defaults, and no extra keys.
* **Scenario — Session State Default Write**:
  - **Given**: A clean repository root.
  - **When**: The user executes `deviate init`.
  - **Then**: `.deviate/session.json` contains `current_phase` set to `"IDLE"`, `active_issue_id` set to `null`, `last_command` set to `""`, and a valid ISO-8601 `timestamp`. No extra keys are present.
* **Scenario — Invalid Config Rejected on Load**:
  - **Given**: `.deviate/config.toml` exists but `timeout_seconds` is `-1` (violating the `gt=0` constraint).
  - **When**: The CLI loads the configuration.
  - **Then**: Pydantic raises a `ValidationError`, the CLI outputs a structured error message detailing the `gt=0` invariant violation, and exits with a non-zero code.
* **Scenario — Config with Extra Forbidden Keys Rejected**:
  - **Given**: `.deviate/config.toml` exists but contains a key not declared in `DeviateConfig` (e.g., `debug_mode = true`).
  - **When**: The CLI loads the configuration.
  - **Then**: Pydantic raises a `ValidationError` due to `extra="forbid"`, and the CLI outputs a structured error.

### US-003-CONS: Constitution Boilerplate Provisioning
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: The `deviate init` command creates `specs/constitution.md` from the tokenized boilerplate template at `src/deviate/prompts/constitution_seed.md` with offline `${VARIABLE}` placeholder resolution.
* **Scenario — Constitution Creation on Clean Repo**:
  - **Given**: A repository root with no `specs/constitution.md`.
  - **When**: The user executes `deviate init`.
  - **Then**: `specs/constitution.md` is created from the boilerplate template, all `${VARIABLE}` placeholders are resolved via regex-based project file scanning, and the file contains valid Markdown.
* **Scenario — Idempotent Skip When Constitution Exists**:
  - **Given**: `specs/constitution.md` already exists.
  - **When**: The user executes `deviate init`.
  - **Then**: The file is not modified, the CLI outputs an idempotency skip message, and exits with code `0`.
* **Scenario — `--generate-constitution` Flag Behavior**:
  - **Given**: A clean repository root with no `specs/constitution.md` and a configured LLM backend.
  - **When**: The user executes `deviate init --generate-constitution`.
  - **Then**: The CLI invokes the configured LLM runner for deeper analysis-based constitution generation instead of the offline boilerplate template, and the resulting `specs/constitution.md` contains LLM-generated content.

### US-004-GOV: Agent Governance File Management
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: The `deviate init` command idempotently manages `CLAUDE.md` and `AGENTS.md` at the repository root: appends the `## DeviaTDD Orchestration Rules` block at end-of-file if absent, overwrites only that specific block in-place if it already exists.
* **Scenario — Governance Block Append to Empty File**:
  - **Given**: `CLAUDE.md` does not exist or is empty.
  - **When**: The user executes `deviate init`.
  - **Then**: `CLAUDE.md` is created containing the `## DeviaTDD Orchestration Rules` block from the governance seed prompt (`src/deviate/prompts/governance/claudemd_seed.md`).
* **Scenario — Governance Block Append to Existing File (No Existing Block)**:
  - **Given**: `CLAUDE.md` exists with pre-existing content but does NOT contain the section `## DeviaTDD Orchestration Rules`.
  - **When**: The user executes `deviate init`.
  - **Then**: The `## DeviaTDD Orchestration Rules` block is appended to the end of `CLAUDE.md`. Pre-existing content above the block is preserved untouched.
* **Scenario — Governance Block Overwrite When Block Already Exists**:
  - **Given**: `CLAUDE.md` already contains a `## DeviaTDD Orchestration Rules` section with stale content.
  - **When**: The user executes `deviate init`.
  - **Then**: Only the `## DeviaTDD Orchestration Rules` section is replaced with the current authoritative block from the governance seed prompt. All content outside that section is preserved untouched.
* **Scenario — AGENTS.md Managed Identically**:
  - **Given**: The same conditions as any `CLAUDE.md` scenario above.
  - **When**: The user executes `deviate init`.
  - **Then**: `AGENTS.md` receives the same governance block append/overwrite treatment as `CLAUDE.md`, using the `agents_seed.md` governance source.

### US-005-RECOV: Partial Scaffold Recovery
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: When a previous `deviate init` was interrupted (e.g., process killed between file writes), re-running `deviate init` detects missing files and completes the scaffold without overwriting already-written valid files.
* **Scenario — Recovery After Interrupted Init (Config Exists, Session Missing)**:
  - **Given**: `.deviate/config.toml` exists and is valid, but `.deviate/session.json` is missing (simulating an interrupted previous run).
  - **When**: The user executes `deviate init`.
  - **Then**: `.deviate/config.toml` is NOT overwritten (skip message emitted), `.deviate/session.json` is created with valid defaults, and the CLI exits with code `0`.
* **Scenario — Recovery After Interrupted Init (Session Exists, Config Missing)**:
  - **Given**: `.deviate/session.json` exists and is valid, but `.deviate/config.toml` is missing.
  - **When**: The user executes `deviate init`.
  - **Then**: `.deviate/session.json` is NOT overwritten, `.deviate/config.toml` is created with valid defaults, and the CLI exits with code `0`.
* **Scenario — Full Recovery With All Governance Files Missing**:
  - **Given**: `.deviate/` is fully scaffolded, but `specs/constitution.md`, `CLAUDE.md`, and `AGENTS.md` are all missing.
  - **When**: The user executes `deviate init`.
  - **Then**: All three governance files are created, `.deviate/` files are NOT overwritten, and the CLI exits with code `0`.

### US-006-PERF: Performance Compliance
* **Upstream Requirement Traceability**: FR-001-INIT
* **Description**: The `deviate init` command completes its execution within the `L_max <= 500ms` performance constraint, excluding optional LLM-driven constitution generation.
* **Scenario — Init Under 500ms on Clean Repo**:
  - **Given**: A clean repository root with no `.deviate/` directory or governance files.
  - **When**: The user executes `deviate init` without the `--generate-constitution` flag.
  - **Then**: All scaffolding completes, and total wall-clock time does not exceed 500ms.
* **Scenario — Init Under 500ms With Partial Scaffold**:
  - **Given**: A repository root with an existing `.deviate/config.toml` but missing `session.json` and governance files.
  - **When**: The user executes `deviate init`.
  - **Then**: Missing files are created, existing files are skipped, and total wall-clock time does not exceed 500ms.

## SYSTEM_STATUS_SUMMARY
| Parameter | Value |
|-----------|-------|
| STATUS | SPECIFIED |
| EPIC_SLUG | 001-deviate-cli-python |
| BRANCH_NAME | feat/001-deviate-cli-python/001-cli-initialization-governance-provisioning |
| SPEC_PATH | specs/001-deviate-cli-python/001-cli-initialization-governance-provisioning/spec.md |
| ISSUE_ID | ISS-001-001 |
| NEXT_ACTION | Run post-script to validate, commit, and transition to TASKS phase |
