# Implementation Tasks: feat/001-deviate-cli-python/003-meso-layer-specification-task-decomposition

## Phase 1: Domain Foundation — TaskRecord Model & Session Transitions
**Goal**: Establish the `TaskRecord` Pydantic model with append-only ledger writes, issue resolution lookup, and meso-layer session phase transitions (`SHARD` → `SPECIFY` → `TASKS` → `IDLE`).

### Tasks

- [x] T001: TaskRecord Pydantic Model + Ledger Read/Append Functions
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `pytest tests/test_state/test_ledger.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: `ledger.py` already contains `IssueRecord` and `append_issue_record()`. TaskRecord is the downstream counterpart needed for meso-layer task decomposition (FR-003-MESO). `test_ledger.py` already has the test pattern for IssueRecord — TaskRecord tests follow the same structure covering US-003-TASKS scenarios for Pydantic field validation and US-005-TASKS for `INVALID_ISSUE_ID` paths.
  - **Details**:
    - **Red**: Write `test_task_record_creation()` asserting default `status="PENDING"` and `execution_mode="TDD"`; `test_task_record_invalid_status()` asserting `ValidationError` for values outside the `Literal`; `test_task_record_extra_fields_forbidden()` asserting `extra="forbid"` blocks unknown keys; `test_task_record_uuid4_validation()` asserting invalid UUIDs are rejected.
    - **Green**: Implement `class TaskRecord(BaseModel)` in `ledger.py` with fields: `id: str` (UUID4 validated), `issue_id: str`, `description: str` (min_length=1), `status: Literal["PENDING","RED","GREEN","REFACTOR","COMPLETED"]` (default `PENDING`), `execution_mode: Literal["TDD","DIRECT","E2E"]` (default `TDD`), `created_at: datetime` (utcnow default). Add `@field_validator("id")` for UUID4 check. Add `model_config = {"extra": "forbid"}`.
    - **Red**: Write `test_append_task_record_new()` asserting a fresh `tasks.jsonl` gets one line with the record's JSON; `test_append_task_record_idempotent_skip()` asserting duplicate `task_id` returns `False` and only one line exists; `test_task_ledger_directory_creation()` asserting parent dirs are created.
    - **Green**: Implement `append_task_record(record: TaskRecord, ledger_path: Path) -> bool` in `ledger.py` — use `path.open("a+")`, seek to 0, scan existing lines for duplicate `id`, write JSONL line if unique, return `True`/`False`. Reuse existing fcntl locking pattern from `append_issue_record`.
    - **Red**: Write `test_read_issue_record_by_id()` asserting that given an `issues.jsonl` with a known `IssueRecord`, the function returns the matching record; `test_read_issue_record_not_found()` asserting `None` for missing `issue_id`.
    - **Green**: Implement `resolve_issue_record(issue_id: str, ledger_path: Path) -> IssueRecord | None` — read the ledger via `_read_ledger()`, find the last entry per issue_id (canonical state by sequential parse per append-only protocol), return `IssueRecord.model_validate(data)` or `None`.
    - **Refactor**: Ensure `_read_ledger()` is reused (not duplicated) across `append_issue_record`, `append_task_record`, and `resolve_issue_record`. Align error messages with existing `_validate_uuid4` pattern.
    - **Acceptance**: All new tests pass. TaskRecord model round-trips through JSON serialization. `resolve_issue_record` returns the canonical (last-written) state for a given id.

- [x] T002: SessionState Meso Phase Transition Map
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `pytest tests/test_state/test_config.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T001
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_state/test_config.py`
  - **Rationale**: `config.py` contains `SessionState` with `_TRANSITION_MAP` — currently a simple `dict[str, str]` covering only the macro linear chain (`IDLE→EXPLORE→RESEARCH→PRD→SHARD→IDLE`). Spec US-002-SPECIFY requires transitions `SHARD→SPECIFY→TASKS→IDLE`. This requires branching the FSM to support multiple valid next-states from a given current state.
  - **Details**:
    - **Red**: Write `test_transition_idle_to_specify()` asserting `SessionState(current_phase="IDLE").transition_to("SPECIFY")` succeeds with `current_phase="SPECIFY"`. Write `test_transition_specify_to_tasks()` and `test_transition_tasks_to_idle()`. Write `test_transition_idle_to_explore_still_works()` asserting the existing macro path is unbroken. Write `test_transition_specify_to_shard_rejected()` asserting invalid meso-to-macro jump raises `TransitionViolationError`.
    - **Green**: Refactor `_TRANSITION_MAP` from `dict[str, str]` to `dict[str, tuple[str, ...]]` with values: `"IDLE": ("EXPLORE", "SPECIFY")`, `"SPECIFY": ("TASKS",)`, `"TASKS": ("IDLE",)`, and existing entries wrapped in single-element tuples. Update `transition_to()` to check `if phase not in expected_next:` instead of `if phase != expected_next:`. Update `_REVERSE_MAP` construction to handle the branching map (generate a `dict[str, str]` where each phase appears as a value at most once — SPECIFY appears only as next from IDLE, TASKS only from SPECIFY, IDLE can come from multiple sources so pick the most relevant in error messages).
    - **Refactor**: Inline `_REVERSE_MAP` or replace with a helper that generates the error message from `_TRANSITION_MAP` directly. Ensure the `TransitionViolationError` message still names both the expected and actual phases clearly.
    - **Edge Cases**: Validate that `SHARD` → `IDLE` still works (existing macro `shard()` command). Validate that `EXPLORE→RESEARCH→PRD→SHARD→IDLE` full chain is unbroken.
    - **Acceptance**: All transition tests pass. Existing macro tests (`tests/test_macro/`) continue to pass unchanged. SPECIFY/TASKS/IDLE transitions behave correctly.

## Phase 2: Meso CLI Commands — Specify & Tasks
**Goal**: Implement the `deviate specify` and `deviate tasks` Typer subcommands registered on the meso layer, handling issue resolution, artifact scaffolding, task generation, and ledger append.

### Tasks

- [x] T003: `deviate specify` — Issue Record Resolution & Artifact Scaffolding
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_meso/test_specify.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: T002
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_meso/test_specify.py`
    - `tests/test_meso/__init__.py`
  - **Rationale**: `meso.py` is the new domain-driven sub-application per design.md. `__init__.py` registers the meso commands on the main Typer app (following the macro.py pattern at line 188-190). `test_specify.py` covers US-001-SPECIFY (issue resolution/validation) and US-002-SPECIFY (directory scaffolding, session state transition). The `tests/test_meso/__init__.py` makes the package importable.
  - **Details**:
    - **Red**: Write `test_specify_valid_issue()` — mock `specs/issues.jsonl` with a valid IssueRecord, invoke `specify(issue_id)`, assert exit 0 and directory `specs/{issue_slug}/` is created. Write `test_specify_invalid_issue_id()` — assert exit non-zero and stderr contains `INVALID_ISSUE_ID`. Write `test_specify_issue_regardless_of_status()` — IssueRecord with status `DRAFT` or `SPECIFIED` still resolves successfully. Write `test_specify_creates_spec_md_placeholder()` — assert an empty `spec.md` exists at `specs/{issue_slug}/spec.md` after successful specify. Write `test_specify_sets_session_to_specify()` — assert `SessionState.current_phase` transitions to `"SPECIFY"` and `active_issue_id` is set.
    - **Green**: Create `src/deviate/cli/meso.py` with Typer imports, `Console`, `Path`. Implement `specify(issue_id: str)` accepting an issue_id argument. Inside: resolve `issue_id` via `resolve_issue_record()` from ledger.py; if `None`, print `INVALID_ISSUE_ID` and `raise typer.Exit(code=1)`. Derive `issue_slug` from the resolved `IssueRecord.issue_slug`. Create directory `specs/{issue_slug}/` and empty `spec.md` placeholder. Load `SessionState`, transition to `"SPECIFY"`, set `active_issue_id`, save. Print success message via Rich Console. Register in `__init__.py`: `from deviate.cli.meso import specify, tasks` and `cli.command(name="specify")(specify)`.
    - **Green**: Create `specify` as a standalone function (matching the `macro.py` pattern — no class, just a Typer-registered function) to maintain consistency with `explore()`, `research()`, etc.
    - **Refactor**: Extract a shared `_resolve_and_validate_issue(issue_id: str) -> IssueRecord` helper in `meso.py` for reuse by both `specify` and `tasks`. Use `console.print` with Rich formatting (`[green]`/`[red]`) matching `macro.py` style.
    - **Edge Cases**: Handle `.deviate/` not found by emitting a clear error before resolving issues. Handle duplicate invocations — directory already exists → output skip message but still transition session.
    - **Acceptance**: All `test_specify.py` tests pass. CLI exits with proper codes. Session state is persisted correctly.

- [x] T004: `deviate tasks` — TaskRecord Generation, Append & Idempotency Guard
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_meso/test_tasks.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: T001
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_meso/test_tasks.py`
  - **Rationale**: `meso.py` is extended with the `tasks()` command. This covers US-003-TASKS (TaskRecord generation and append, PENDING status), US-004-TASKS (idempotent re-execution guard), and US-005-TASKS (INVALID_ISSUE_ID error path for tasks). The validation of each TaskRecord via Pydantic is inherently tested via the model's strict schema in T001.
  - **Details**:
    - **Red**: Write `test_tasks_appends_pending_records()` — set up a valid IssueRecord in `issues.jsonl`, invoke `tasks(issue_id)`, assert `tasks.jsonl` exists with ≥1 line, each parsed record has `status: "PENDING"` and `execution_mode: "TDD"`. Write `test_tasks_invalid_issue_id()` — assert exit non-zero and `INVALID_ISSUE_ID`. Write `test_tasks_idempotent_skip_existing()` — create `tasks.jsonl` beforehand, invoke `tasks(issue_id)`, assert exit 0, stdout contains skip message (e.g., "already provisioned"), file content unchanged. Write `test_tasks_idempotent_skip_no_new_file()` — assert `tasks.jsonl` line count is identical before and after re-run. Write `test_tasks_sets_session_transition()` — assert session goes `SPECIFY` → `TASKS` → `IDLE`.
    - **Green**: Implement `tasks(issue_id: str)` in `meso.py`. Resolve issue via shared `_resolve_and_validate_issue()` helper from T003. Check idempotency: if `specs/{issue_slug}/tasks.jsonl` already exists, print skip message and exit 0. Generate `TaskRecord` list: generate a UUID4 id, set `issue_id` to the resolved issue's id, set `description` to a task name derived from the issue title, set `status="PENDING"`, `execution_mode="TDD"`. Append each via `append_task_record()` to `specs/{issue_slug}/tasks.jsonl`. Transition session: load, transition to `TASKS`, save, then transition to `IDLE`, save. Print success with record count.
    - **Green**: The generated TaskRecord description should be derived from the issue's title — e.g., `f"Implement {issue_record.title}"`. The number of records can be 1 (minimum viable); the soft 3-10 target is documented as a comment guideline, not a hard constraint at this layer.
    - **Refactor**: Ensure `_resolve_and_validate_issue()` is called consistently by both commands. Align Rich console output style with `macro.py` (`[green]TASKS[/]` for success, `[yellow]SKIP[/]` for idempotent, `[red]INVALID_ISSUE_ID[/]` for errors).
    - **Edge Cases**: Handle empty `.deviate/` — fail before ledger operations. Handle JSONL with malformed lines (existing `_read_ledger` already warns and skips). Handle race between idempotency check and append (limited by fcntl in append function, but the check is best-effort).
    - **Acceptance**: All `test_tasks.py` tests pass. Idempotency guard correctly detects existing `tasks.jsonl`. Generated TaskRecords pass Pydantic validation. Session transitions complete cleanly.

## Phase 3: Integration Verification
**Goal**: Validate the full meso-layer specify → tasks cycle end-to-end with real file I/O, ensuring the append-only ledger invariants hold and state transitions are correctly sequenced.

### Tasks

- [ ] T005: End-to-End Meso Specify→Tasks Cycle Integration Test
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_integration/test_meso_task_ledger.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T003 T004
  - **Files**:
    - `tests/test_integration/test_meso_task_ledger.py`
    - `tests/test_integration/conftest.py`
  - **Rationale**: `test_meso_task_ledger.py` is the new integration test file specified in the spec's `MULTI_TIERED_VERIFICATION_TARGETS`. `conftest.py` is extended with shared fixtures (tmp_path with `.deviate/` scaffold, issue ledger pre-population) needed by the integration test. Together they verify the complete cycle from US-001 through US-005 across real filesystem boundaries.
  - **Details**:
    - **Red**: Write `test_full_specify_tasks_cycle(tmp_path)` — scaffold `.deviate/` with a valid `session.json` (IDLE) and `specs/issues.jsonl` containing a known IssueRecord. Run `specify(issue_id)` via `CliRunner`, assert directory `specs/{issue_slug}/` and `spec.md` placeholder exist. Run `tasks(issue_id)` via `CliRunner`, assert `tasks.jsonl` exists with valid JSONL content. Verify each `TaskRecord` line is parseable and validates against the Pydantic model. Assert session phase ends at IDLE.
    - **Red**: Write `test_tasks_idempotency_full_cycle(tmp_path)` — complete the full cycle once, then re-run `tasks(issue_id)`. Assert exit 0, idempotency skip output, `tasks.jsonl` line count unchanged.
    - **Red**: Write `test_invalid_issue_id_rejected(tmp_path)` — with no matching IssueRecord, invoke `specify("NONEXISTENT")` via CliRunner. Assert exit code 1, stderr contains `INVALID_ISSUE_ID`.
    - **Green**: The integration test passes when both T003 and T004 are complete — no new production code needed in this task. The fixtures in `conftest.py` may need a `meso_workspace` fixture that creates `.deviate/session.json` (IDLE phase) and `specs/issues.jsonl` with a test IssueRecord.
    - **Refactor**: Ensure `conftest.py` fixtures use `tmp_path` isolated directories. Align fixture naming with existing integration conftest patterns.
    - **Edge Cases**: Test with empty `issues.jsonl`, test with malformed JSONL lines mixed into valid data, test with `.deviate/` absent (verify graceful error).
    - **Acceptance**: All three integration scenarios pass. Ledger invariants hold: append-only, no line overwritten. Session state transitions are correctly sequenced.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (T001 → T002) — Domain model and state machine foundation
2. Phase 2 (T003, T004) — CLI commands, can be parallel after Phase 1
3. Phase 3 (T005) — Integration tests requiring both commands

**Critical Dependency Chains**:
- T001 (TaskRecord model + ledgers) is prerequisite for T004 (tasks command uses `append_task_record`)
- T002 (session transitions) is prerequisite for T003 (specify command transitions session)
- T003 and T004 both required before T005 (integration tests the full cycle)

**Risk Hotspots**:
- `src/deviate/state/config.py` — `_TRANSITION_MAP` refactoring from flat `dict[str, str]` to branching `dict[str, tuple[str, ...]]` must preserve backward compatibility with all existing macro-layer transitions. Existing macro tests in `tests/test_macro/` must continue to pass.
- `src/deviate/cli/meso.py` — new file; must match the function-signature and Console-output conventions established in `src/deviate/cli/macro.py`.
- `src/deviate/cli/__init__.py` — registration of meso commands must follow the existing pattern (line 188-190) and must not break the existing `deviate init` or macro commands.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/meso.py` (T003, T004), `src/deviate/cli/__init__.py` (T003)
- No files span across Phases 1 and 2 — merge conflicts are contained within Phase 2 (linear edits to the same new file)

**Test Coverage Target**: >= 80% per constitution. Target test files:
- `tests/test_state/test_ledger.py` — TaskRecord model (+6 tests)
- `tests/test_state/test_config.py` — meso transitions (+4 tests)
- `tests/test_meso/test_specify.py` — specify command (+5 tests)
- `tests/test_meso/test_tasks.py` — tasks command (+5 tests)
- `tests/test_integration/test_meso_task_ledger.py` — full cycle (+3 tests)