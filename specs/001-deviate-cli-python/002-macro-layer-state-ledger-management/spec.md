# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/002-macro-layer-state-ledger-management/spec.md

## SYSTEM_TOPOLOGY_MAPPING
- **Epic Domain**: `001-deviate-cli-python`
- **Issue ID**: `ISS-001-002`
- **Layer**: Macro (feature scoping orchestration)
- **Primary Workstations**:
  - `src/deviate/cli/macro.py` — Macro-layer subcommand definitions (explore, research, prd, shard)
  - `src/deviate/state/ledger.py` — `IssueRecord` Pydantic model and `specs/issues.jsonl` append logic
  - `src/deviate/state/session.py` — Session state machine with transition enforcement
  - `tests/test_macro/` — Unit test suite for macro-layer commands
- **Upstream Dependencies**: `ISS-001-001` (`[FR-001]` Package Scaffold & Bootstrap) — provides `src/deviate/cli/__init__.py` Typer app mount point
- **Downstream Consumers**: Meso-layer (`/specify`, `/tasks`) consumes `shard` output (`IssueRecord` entries in `specs/issues.jsonl`)

## THE_PROBLEM_CONTRACT
As a feature architect, I need the CLI to orchestrate the `/explore`, `/research`, `/prd`, and `/shard` commands, managing session state transitions and appending to the global issue ledger, so that feature scoping is systematically tracked and downstream agents receive deterministic context packets.

The current codebase has the package scaffold (`ISS-001-001`) but lacks macro-layer orchestration. Without this, users cannot invoke `deviate explore`, `deviate research`, `deviate prd`, or `deviate shard`, and no session state or ledger tracking exists to coordinate the feature scoping workflow.

## SCOPE_BOUNDARIES
### Hard Inclusions
- Four Typer subcommands: `deviate explore`, `deviate research`, `deviate prd`, `deviate shard`
- Session state machine with strict sequential transitions: `IDLE` → `EXPLORE` → `RESEARCH` → `PRD` → `SHARD` → `IDLE`
- Upstream artifact validation before each phase (all-or-nothing: scans for all missing artifacts before erroring)
- `IssueRecord` Pydantic model (`id: UUID4`, `title: str`, `status: Literal["SHARDED"]`, `epic_slug: str`, `issue_slug: str`, `timestamp: datetime`)
- Idempotent `IssueRecord` append to `specs/issues.jsonl` (skip if `issue_slug` already exists)
- Session state persistence in `.deviate/session.json`
- Transition violation errors with non-zero exit codes

### Defensive Exclusions
- Task-level decomposition (`/specify`, `/tasks`) — belongs to Meso layer
- Actual code generation or test execution — belongs to Micro layer (TDD sandbox)
- OS-level file locking — simple atomic append sufficient per project constraints
- LLM invocation logic — macro-layer commands are deterministic scaffolding/dispatch only; LLM calls are downstream agent responsibilities
- Auto-bootstrapping of missing artifacts — no `--bootstrap` flag; missing artifacts halt the pipeline with diagnostic
- Branch management or git operations beyond read-only constitution verification

## PERFORMANCE_CONSTRAINTS
- **Session state read/write**: L_max <= 10ms per I/O cycle (single JSON file, <1KB)
- **Ledger append with idempotency check**: L_max <= 50ms (JSONL scan + atomic append)
- **Artifact validation scan**: L_max <= 20ms (filesystem stat on 2-3 known paths)
- **Command dispatch overhead**: L_max <= 5ms (Typer routing)

## MULTI_TIERED_VERIFICATION_TARGETS
- **Unit Tests**:
  - `tests/test_macro/test_explore.py` — Explore subcommand dispatch and session transition
  - `tests/test_macro/test_research.py` — Research subcommand dispatch and session transition
  - `tests/test_macro/test_prd.py` — PRD subcommand dispatch, artifact validation, session transition
  - `tests/test_macro/test_shard.py` — Shard subcommand dispatch, ledger append, idempotency, session reset
  - `tests/test_macro/test_session_state.py` — Session state machine transitions and violation detection
  - `tests/test_macro/test_ledger.py` — `IssueRecord` model validation, JSONL append, duplicate detection
- **Integration Tests**:
  - `tests/test_integration/test_macro_ledger_append.py` — Full `deviate shard` cycle writes to `specs/issues.jsonl`
  - `tests/test_integration/test_macro_full_cycle.py` — End-to-end IDLE → EXPLORE → RESEARCH → PRD → SHARD → IDLE
- **E2E Tests**:
  - `tests/test_e2e/test_macro_workflow.bats` — Bats-driven CLI invocation from user perspective

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001: Register macro-layer subcommands on the Typer CLI app
- **Upstream Requirement Traceability**: FR-002-
- **Description**: The four macro-layer commands (`explore`, `research`, `prd`, `shard`) must be registered as subcommands on the top-level `deviate` Typer application and dispatch correctly when invoked.

**Scenario: Explore subcommand is reachable**
- **Given** the `deviate` Typer app is initialized with macro-layer subcommands registered
- **When** the user invokes `deviate explore --help`
- **Then** the help text for the explore subcommand is displayed and exits with code `0`

**Scenario: Research subcommand is reachable**
- **Given** the `deviate` Typer app is initialized with macro-layer subcommands registered
- **When** the user invokes `deviate research --help`
- **Then** the help text for the research subcommand is displayed and exits with code `0`

**Scenario: PRD subcommand is reachable**
- **Given** the `deviate` Typer app is initialized with macro-layer subcommands registered
- **When** the user invokes `deviate prd --help`
- **Then** the help text for the prd subcommand is displayed and exits with code `0`

**Scenario: Shard subcommand is reachable**
- **Given** the `deviate` Typer app is initialized with macro-layer subcommands registered
- **When** the user invokes `deviate shard --help`
- **Then** the help text for the shard subcommand is displayed and exits with code `0`

---

### US-002: Enforce strict sequential session state transitions across macro phases
- **Upstream Requirement Traceability**: FR-002-
- **Description**: The session state machine must enforce strict sequential ordering. Each macro command can only execute when the session is in the correct predecessor state. Invalid transitions must be rejected with a clear error message and non-zero exit code.

**Scenario: Valid explore transition from IDLE**
- **Given** the session state is `IDLE` and a valid workspace exists
- **When** the user invokes `deviate explore`
- **Then** the session state transitions to `EXPLORE`, the state is persisted to `.deviate/session.json`, and the command exits with code `0`

**Scenario: Valid research transition from EXPLORE**
- **Given** the session state is `EXPLORE`
- **When** the user invokes `deviate research`
- **Then** the session state transitions to `RESEARCH`, the state is persisted, and the command exits with code `0`

**Scenario: Valid prd transition from RESEARCH**
- **Given** the session state is `RESEARCH`
- **When** the user invokes `deviate prd`
- **Then** the session state transitions to `PRD`, the state is persisted, and the command exits with code `0`

**Scenario: Valid shard transition from PRD**
- **Given** the session state is `PRD`
- **When** the user invokes `deviate shard`
- **Then** the session state transitions to `SHARD` then resets to `IDLE`, the state is persisted, and the command exits with code `0`

**Scenario: Transition violation — skipping a phase**
- **Given** the session state is `IDLE`
- **When** the user invokes `deviate prd`
- **Then** the command is rejected with error message `TRANSITION_VIOLATION: expected state EXPLORE, current state IDLE` and exits with non-zero code

**Scenario: Transition violation — duplicate invocation**
- **Given** the session state is `EXPLORE`
- **When** the user invokes `deviate explore`
- **Then** the command is rejected with error message `TRANSITION_VIOLATION: expected state IDLE, current state EXPLORE` and exits with non-zero code

**Scenario: Transition violation — backward movement**
- **Given** the session state is `PRD`
- **When** the user invokes `deviate research`
- **Then** the command is rejected with error message `TRANSITION_VIOLATION` and exits with non-zero code

---

### US-003: Validate all upstream artifact presence before each macro phase executes
- **Upstream Requirement Traceability**: FR-002-
- **Description**: Before executing a macro command, the system must scan for all required upstream artifacts. If any are missing, it must report all missing files in a single aggregated error message before exiting, rather than failing on the first missing file.

**Scenario: All artifacts present — prd proceeds**
- **Given** `specs/001-deviate-cli-python/explore.md` and `specs/001-deviate-cli-python/research.md` both exist
- **When** the user invokes `deviate prd`
- **Then** the artifact validation passes and the prd command proceeds to execution

**Scenario: Single artifact missing — prd halted with diagnostic**
- **Given** `specs/001-deviate-cli-python/explore.md` exists but `specs/001-deviate-cli-python/research.md` does not exist
- **When** the user invokes `deviate prd`
- **Then** the command outputs `PRD_HALTED: missing upstream artifacts` listing `[specs/001-deviate-cli-python/research.md]` and exits with non-zero code

**Scenario: Multiple artifacts missing — all reported**
- **Given** neither `specs/001-deviate-cli-python/explore.md` nor `specs/001-deviate-cli-python/research.md` exist
- **When** the user invokes `deviate prd`
- **Then** the command outputs `PRD_HALTED: missing upstream artifacts` listing both `[specs/001-deviate-cli-python/explore.md, specs/001-deviate-cli-python/research.md]` and exits with non-zero code

**Scenario: Artifact validation before research — explore.md required**
- **Given** `specs/001-deviate-cli-python/explore.md` does not exist
- **When** the user invokes `deviate research`
- **Then** the command outputs `RESEARCH_HALTED: missing upstream artifacts` listing `[specs/001-deviate-cli-python/explore.md]` and exits with non-zero code

**Scenario: Artifact validation before shard — prd.md required**
- **Given** `specs/001-deviate-cli-python/prd.md` does not exist
- **When** the user invokes `deviate shard`
- **Then** the command outputs `SHARD_HALTED: missing upstream artifacts` listing `[specs/001-deviate-cli-python/prd.md]` and exits with non-zero code

---

### US-004: Append shard output to the issue ledger with idempotency
- **Upstream Requirement Traceability**: FR-002-
- **Description**: When `deviate shard` completes successfully, an `IssueRecord` with status `SHARDED` must be appended to `specs/issues.jsonl`. If an `IssueRecord` with the same `issue_slug` already exists in the ledger, the append must be skipped with a clear notification.

**Scenario: First shard run — IssueRecord appended**
- **Given** `specs/issues.jsonl` is empty or does not contain a record for `issue_slug` `002-macro-layer-state-ledger-management`
- **When** the user invokes `deviate shard` successfully
- **Then** an `IssueRecord` with valid `UUID4` `id`, `status` `SHARDED`, and `issue_slug` `002-macro-layer-state-ledger-management` is appended to `specs/issues.jsonl`

**Scenario: Duplicate shard run — append skipped**
- **Given** `specs/issues.jsonl` already contains an `IssueRecord` with `issue_slug` `002-macro-layer-state-ledger-management`
- **When** the user invokes `deviate shard`
- **Then** the append is skipped, the output includes `LEDGER_IDEMPOTENT: record for 002-macro-layer-state-ledger-management already exists`, and the command exits with code `0`

**Scenario: IssueRecord model validation — invalid status rejected**
- **Given** an `IssueRecord` is constructed with `status` `PENDING` (not `SHARDED`)
- **When** the record is validated
- **Then** Pydantic raises a `ValidationError` because only `SHARDED` is permitted

**Scenario: IssueRecord model validation — missing required fields**
- **Given** an `IssueRecord` is constructed without an `id` field
- **When** the record is validated
- **Then** Pydantic raises a `ValidationError`

**Scenario: Empty workspace — ledger creation**
- **Given** `specs/issues.jsonl` does not exist
- **When** `deviate shard` runs and appends an `IssueRecord`
- **Then** `specs/issues.jsonl` is created with the new record as its first line

---

### US-005: End-to-end macro-layer full cycle integration
- **Upstream Requirement Traceability**: FR-002-
- **Description**: The complete macro-layer pipeline from `IDLE` through `SHARD` back to `IDLE` must execute without errors, with state transitions, artifact validation, and ledger append all functioning correctly as an integrated whole.

**Scenario: Full IDLE → SHARD → IDLE cycle**
- **Given** a valid workspace with `specs/constitution.md` present and all required upstream artifacts mock-present
- **When** the user invokes `deviate explore`, then `deviate research`, then `deviate prd`, then `deviate shard` in sequence
- **Then** each command exits with code `0`, session state follows `IDLE → EXPLORE → RESEARCH → PRD → SHARD → IDLE`, and `specs/issues.jsonl` contains one new `IssueRecord` with `status` `SHARDED`

**Scenario: Cycle resets correctly for subsequent runs**
- **Given** a full cycle has completed and session state is `IDLE`
- **When** the user invokes `deviate explore` again
- **Then** the session transitions to `EXPLORE` and the cycle restarts without residual state from the prior run

---

## SYSTEM_STATUS_SUMMARY
| Parameter | Value |
|---|---|
| STATUS | READY |
| EPIC_SLUG | 001-deviate-cli-python |
| BRANCH_NAME | feat/001-deviate-cli-python/002-macro-layer-state-ledger-management |
| SPEC_PATH | specs/001-deviate-cli-python/002-macro-layer-state-ledger-management/spec.md |
| ISSUE_ID | ISS-001-002 |
| NEXT_ACTION | Run `/deviate-tasks` to decompose this spec into TDD-cycle tasks |
