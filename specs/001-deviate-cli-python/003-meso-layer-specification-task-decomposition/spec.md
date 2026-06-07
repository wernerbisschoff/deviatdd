# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/spec.md`
- **Workstation Paths**:
  - `src/deviate/cli/meso.py` — Meso-layer Typer subcommand group (`specify`, `tasks`)
  - `src/deviate/cli/__init__.py` — Alternative integration point for meso subcommands
  - `src/deviate/state/ledger.py` — `TaskRecord` Pydantic model and append logic
  - `src/deviate/state/session.py` — `SessionState` phase transitions (`SHARD` → `SPECIFY` → `TASKS` → `IDLE`)
  - `specs/{issue_id}/tasks.jsonl` — Issue-specific task ledger (append-only)
  - `specs/issues.jsonl` — Global issue ledger (read-only during meso phase)
  - `tests/test_meso/test_specify.py` — Unit tests for `deviate specify`
  - `tests/test_meso/test_tasks.py` — Unit tests for `deviate tasks`
  - `tests/test_integration/test_meso_task_ledger.py` — Integration tests for meso task append cycle

## THE_PROBLEM_CONTRACT

As a task engineer working within the DeviaTDD workflow, I need the `deviate specify` and `deviate tasks` CLI commands to resolve an active `IssueRecord` from the global issue ledger, validate its presence and readiness, scaffold specification artifacts into the issue bucket directory, and generate a deterministic, TDD-ready `TaskRecord` sequence appended to the issue-specific task ledger (`specs/{issue_id}/tasks.jsonl`), so that the downstream Micro-layer receives self-contained, executable units without ambiguity or manual state wrangling.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `deviate specify` Typer subcommand: resolves target `issue_id` from `specs/issues.jsonl`, validates the `IssueRecord` exists, creates the issue bucket directory `specs/{issue_slug}/`, and scaffolds specification artifacts (`spec.md`) via the HITL gate workflow.
- `deviate tasks` Typer subcommand: resolves the active `IssueRecord` from `specs/issues.jsonl`, generates `TaskRecord` entries (soft target 3-10, not a hard constraint), validates each against the `TaskRecord` Pydantic schema, and appends them with status `PENDING` to `specs/{issue_id}/tasks.jsonl`.
- `TaskRecord` Pydantic model (`id: str` UUID4, `issue_id: str`, `description: str`, `status: Literal["PENDING", "RED", "GREEN", "REFACTOR", "COMPLETED"]`, `execution_mode: Literal["TDD", "DIRECT", "E2E"]`, `created_at: datetime`) with `extra="forbid"` validation.
- Session state phase transitions: `SHARD` → `SPECIFY` (on `deviate specify`) → `TASKS` (on `deviate tasks`) → `IDLE` (on completion).
- `INVALID_ISSUE_ID` error handling: if the provided `issue_id` is not found in `specs/issues.jsonl`, the CLI exits with a non-zero exit code and emits the structured error message `INVALID_ISSUE_ID`.
- Idempotent re-execution guard for `deviate tasks`: if `specs/{issue_id}/tasks.jsonl` already exists, output an idempotency skip message and exit 0 without mutation.
- Append-only ledger protocol: all `TaskRecord` writes append to `specs/{issue_id}/tasks.jsonl`; no existing line is ever modified or overwritten.

### Defensive Exclusions

- Macro-layer feature scoping logic (`explore`, `research`, `prd`, `shard`).
- Micro-layer TDD sandbox execution or Tamper Guard enforcement (`red`, `green`, `refactor`).
- OS-level file locking for tasks.jsonl (simple atomic append is sufficient; full locking is FR-005-STATE concern).
- Dynamic LLM-driven specification or task generation (the CLI orchestrates the workflow; actual LLM content generation is delegated to agent skills).
- Persistence of `spec.md` content — the `deviate specify` command ensures the artifact path exists; the content is produced by the HITL gate workflow (this phase).

## PERFORMANCE_CONSTRAINTS

- `L_max <= 500ms` for `deviate specify` and `deviate tasks` command execution (excluding LLM agent wall-clock time for content generation).
- Append operations to `specs/{issue_id}/tasks.jsonl` must complete within `L_max <= 50ms`.
- Pydantic `TaskRecord` validation must complete within `L_max <= 10ms` per record.

## MULTI_TIERED_VERIFICATION_TARGETS

| Tier | Target | Description |
|------|--------|-------------|
| Unit | `tests/test_meso/test_specify.py` | `deviate specify` issue resolution, state transitions, error paths |
| Unit | `tests/test_meso/test_tasks.py` | `deviate tasks` TaskRecord generation, append, idempotency, schema validation |
| Unit | `tests/test_state/test_ledger.py` | `TaskRecord` Pydantic model field validation |
| Integration | `tests/test_integration/test_meso_task_ledger.py` | Full specify → tasks append cycle with real JSONL files |

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-SPECIFY: Issue Record Resolution & Input Validation for `deviate specify`

- **Upstream Requirement Traceability**: FR-003-MESO
- **Description**: The `deviate specify` command accepts an `issue_id` parameter, resolves the corresponding `IssueRecord` from `specs/issues.jsonl`, and validates its existence before proceeding with specification artifact scaffolding.

**Scenario 1: Valid issue_id resolves to existing IssueRecord**

- **Given**: `specs/issues.jsonl` contains an `IssueRecord` with `id` matching the provided `issue_id`
- **When**: The user executes `deviate specify <issue_id>`
- **Then**: The `IssueRecord` is resolved from the ledger, and the command proceeds to scaffold the specification artifact directory

**Scenario 2: Invalid or non-existent issue_id triggers INVALID_ISSUE_ID**

- **Given**: `specs/issues.jsonl` does NOT contain an `IssueRecord` with `id` matching the provided `issue_id`
- **When**: The user executes `deviate specify <invalid_issue_id>`
- **Then**: The CLI exits with a non-zero exit code and outputs the structured error message `INVALID_ISSUE_ID`

**Scenario 3: Valid issue_id regardless of IssueRecord status**

- **Given**: `specs/issues.jsonl` contains an `IssueRecord` with `id` matching the provided `issue_id`, but its `status` is `DRAFT`, `SPECIFIED`, or `COMPLETED` (not `SHARDED`)
- **When**: The user executes `deviate specify <issue_id>`
- **Then**: The `IssueRecord` is still resolved successfully, and the command proceeds; status is not a blocking precondition

### US-002-SPECIFY: Specification Artifact Scaffolding & State Transition

- **Upstream Requirement Traceability**: FR-003-MESO
- **Description**: After resolving a valid `IssueRecord`, `deviate specify` creates the issue bucket directory `specs/{issue_slug}/`, transitions `SessionState.current_phase` to `SPECIFY`, and initializes the `spec.md` artifact at the target path. The actual spec content is produced by the downstream HITL gate workflow occupying this phase.

**Scenario 1: Issue bucket directory and spec.md scaffolding**

- **Given**: A valid `IssueRecord` has been resolved from the ledger and the directory `specs/{issue_slug}/` does not exist
- **When**: The user executes `deviate specify <issue_id>`
- **Then**: The directory `specs/{issue_slug}/` is created, and an empty `spec.md` placeholder is provisioned at `specs/{issue_slug}/spec.md`

**Scenario 2: SessionState phase transition to SPECIFY**

- **Given**: `SessionState.current_phase` is `SHARD` (or any valid prior phase) and a valid `IssueRecord` is resolved
- **When**: `deviate specify <issue_id>` executes successfully
- **Then**: `SessionState.current_phase` is updated to `SPECIFY`, `active_issue_id` is set to the resolved issue ID, and the session is persisted to `.deviate/session.json`

### US-003-TASKS: TaskRecord Generation & Append-Only Ledger Write

- **Upstream Requirement Traceability**: FR-003-MESO
- **Description**: The `deviate tasks` command resolves the active `IssueRecord` from the global ledger, generates a sequence of `TaskRecord` entries (soft target 3-10 tasks), validates each against the `TaskRecord` Pydantic schema, and appends them with status `PENDING` to the issue-specific task ledger `specs/{issue_id}/tasks.jsonl`. A terminal `E2E`-mode task is recommended but not mandatory when the issue modifies user-facing behavior.

**Scenario 1: Valid IssueRecord produces at least one PENDING TaskRecord**

- **Given**: A valid `IssueRecord` is resolved from `specs/issues.jsonl` and `specs/{issue_id}/tasks.jsonl` does not exist
- **When**: The user executes `deviate tasks <issue_id>`
- **Then**: At least one `TaskRecord` with `status: "PENDING"` and `execution_mode: "TDD"` is appended to `specs/{issue_id}/tasks.jsonl`

**Scenario 2: TaskRecord entries match Pydantic schema**

- **Given**: The `deviate tasks` command has generated `TaskRecord` entries
- **When**: Each entry is appended to the task ledger
- **Then**: Every `TaskRecord` validates successfully against the Pydantic `TaskRecord` model with `extra="forbid"`, all required fields (`id`, `issue_id`, `description`, `status`, `execution_mode`, `created_at`) are present with valid values, and `id` is a valid UUID4

**Scenario 3: SessionState transitions through TASKS and back to IDLE**

- **Given**: `SessionState.current_phase` is `SPECIFY` after a successful `deviate specify`
- **When**: `deviate tasks <issue_id>` executes successfully and appends all `TaskRecord` entries
- **Then**: `SessionState.current_phase` transitions to `TASKS` during execution, then to `IDLE` upon completion, and the updated session is persisted

### US-004-TASKS: Idempotent Re-execution Guard

- **Upstream Requirement Traceability**: FR-003-MESO
- **Description**: If `specs/{issue_id}/tasks.jsonl` already exists when `deviate tasks` is invoked, the command detects the pre-existing task ledger and performs a no-op, outputting an idempotency skip message and exiting with code 0.

**Scenario 1: Pre-existing tasks.jsonl triggers idempotent skip**

- **Given**: `specs/{issue_id}/tasks.jsonl` already exists with valid `TaskRecord` entries
- **When**: The user executes `deviate tasks <issue_id>`
- **Then**: The CLI outputs a message indicating the task ledger already exists (e.g., `Task ledger for <issue_id> already provisioned — skipping`), exits with code 0, and makes no modifications to `specs/{issue_id}/tasks.jsonl`

**Scenario 2: Non-existent tasks.jsonl proceeds normally**

- **Given**: `specs/{issue_id}/tasks.jsonl` does not exist
- **When**: The user executes `deviate tasks <issue_id>`
- **Then**: The command proceeds to generate and append `TaskRecord` entries as normal (no skip message emitted)

### US-005-TASKS: Input Validation Error Path for `deviate tasks`

- **Upstream Requirement Traceability**: FR-003-MESO
- **Description**: `deviate tasks` reuses the same issue resolution logic as `deviate specify`. An invalid or non-existent `issue_id` results in the `INVALID_ISSUE_ID` error.

**Scenario 1: Invalid issue_id for `deviate tasks` triggers INVALID_ISSUE_ID**

- **Given**: `specs/issues.jsonl` does NOT contain an `IssueRecord` with `id` matching the provided `issue_id`
- **When**: The user executes `deviate tasks <invalid_issue_id>`
- **Then**: The CLI exits with a non-zero exit code and outputs the structured error message `INVALID_ISSUE_ID`

## SYSTEM_STATUS_SUMMARY

| Parameter | Value |
|-----------|-------|
| STATUS | SPECIFIED |
| EPIC_SLUG | 001-deviate-cli-python |
| BRANCH_NAME | feat/001-deviate-cli-python/003-meso-layer-specification-task-decomposition |
| SPEC_PATH | specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/spec.md |
| ISSUE_ID | ISS-003 |
| NEXT_ACTION | Run `/deviate-tasks` to decompose this spec into TDD-cycle tasks |
