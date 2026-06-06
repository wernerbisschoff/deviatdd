# Implementation Tasks: feat/001-deviate-cli-python/002-macro-layer-state-ledger-management

## Phase 1: Domain Foundation — Models & State
**Goal**: Deliver the IssueRecord Pydantic model with JSONL ledger persistence and the session state transition machine with strict sequential enforcement.

### Tasks

- [x] T001: IssueRecord model and JSONL ledger operations with idempotency
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_ledger.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: Implements US-004 ledger domain. IssueRecord is the core data entity consumed by the shard command and downstream meso-layer. JSONL operations (append, idempotency check, read) are the write-side of the append-only ledger protocol. These files are new — no prior IssueRecord model exists.
  - **Details**:
    - **Red**: Write `test_issue_record_creation()` asserting valid IssueRecord with UUID4 id, title, status SHARDED, epic_slug, issue_slug, and timestamp; `test_issue_record_invalid_status()` asserting ValidationError for non-SHARDED status; `test_issue_record_missing_id()` asserting ValidationError; `test_issue_record_serialization()` asserting JSON round-trip preserves all fields.
    - **Green**: Implement `IssueRecord(BaseModel)` in `src/deviate/state/ledger.py` with fields: `id: str` (UUID4 validation), `title: str` (min_length=1), `status: Literal["SHARDED"]`, `epic_slug: str`, `issue_slug: str`, `timestamp: datetime` (UTC-aware default factory).
    - **Red**: Write `test_append_new_record()` asserting a new IssueRecord is appended to an empty `specs/issues.jsonl`; `test_idempotent_skip_existing_slug()` asserting duplicate append for same issue_slug is skipped with notification; `test_ledger_file_created_when_missing()` asserting issues.jsonl is created if absent.
    - **Green**: Implement `append_issue_record(record: IssueRecord, ledger_path: Path) -> bool` that reads existing JSONL, checks for duplicate by `issue_slug`; if found, returns False (idempotent skip); otherwise appends newline-delimited JSON and returns True.
    - **Refactor**: Extract JSONL reading into `_read_ledger(path: Path) -> list[dict]` helper. Ensure consistent newline handling and UTF-8 encoding.
    - **Edge Cases**: Handle empty/missing ledger file gracefully (treat as empty list). Handle malformed JSON lines by skipping with warning rather than crashing. Validate UUID4 format on id field via Pydantic validator.
    - **Acceptance**: `IssueRecord` model passes all Pydantic validation tests. `append_issue_record` correctly handles first-write, duplicate-skip, and file-creation scenarios with deterministic return values.

- [x] T002: Session state machine transition enforcement
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_session.py -v`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_state/test_session.py`
  - **Rationale**: Implements US-002 session state transitions. The `SessionState` Pydantic model already exists in `config.py` with `current_phase` validation but lacks transition enforcement logic. This task adds a `transition_to()` method that enforces the strict `IDLE → EXPLORE → RESEARCH → PRD → SHARD` sequence and handles the `SHARD → IDLE` auto-reset.
  - **Details**:
    - **Red**: Write `test_valid_explore_from_idle()` asserting transition from IDLE to EXPLORE succeeds; `test_valid_research_from_explore()` asserting EXPLORE→RESEARCH; `test_valid_prd_from_research()` asserting RESEARCH→PRD; `test_valid_shard_from_prd()` asserting PRD→SHARD; `test_shard_resets_to_idle()` asserting SHARD auto-resets to IDLE; `test_transition_violation_skip_phase()` asserting IDLE→PRD raises TransitionViolationError; `test_transition_violation_duplicate()` asserting EXPLORE→EXPLORE raises error; `test_transition_violation_backwards()` asserting PRD→RESEARCH raises error.
    - **Green**: Add `TransitionViolationError(Exception)` exception class. Implement `SessionState.transition_to(phase: str) -> SessionState` method: validates phase against `_TRANSITION_MAP = {"IDLE": "EXPLORE", "EXPLORE": "RESEARCH", "RESEARCH": "PRD", "PRD": "SHARD", "SHARD": "IDLE"}`, raises `TransitionViolationError(f"expected {expected}, current {self.current_phase}")` on mismatch, returns new SessionState instance with updated phase and timestamp.
    - **Red**: Write `test_session_persistence()` asserting session state serializes to `.deviate/session.json` correctly; `test_session_persistence_missing_dir()` asserting session write creates `.deviate/` directory if absent.
    - **Green**: Add `SessionState.save(path: Path) -> None` method and `SessionState.load(path: Path) -> SessionState` classmethod for JSON round-trip persistence. `save()` creates parent dirs if needed.
    - **Refactor**: Ensure `model_dump_json(indent=2)` for human-readable session files. Use `model_validate` for deserialization.
    - **Edge Cases**: Handle corrupted session.json by raising clear error (not silent default). Handle missing session.json on load by returning default IDLE state. Handle `current_phase` outside macro-only phases gracefully (transition map covers macro phases; micro phases pass through without enforcement).
    - **Acceptance**: All transition scenarios from US-002 pass. `TransitionViolationError` messages include both expected and current state. Session persistence round-trips all fields correctly.

---

## Phase 2: CLI Layer — Macro Subcommand Registration
**Goal**: Wire all four macro subcommands (explore, research, prd, shard) onto the Typer CLI with integrated session state enforcement and upstream artifact validation.

### Tasks

- [x] T003: Macro CLI subcommands with artifact validation
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_macro/test_explore.py tests/test_macro/test_research.py tests/test_macro/test_prd.py tests/test_macro/test_shard.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T001 T002
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_macro/test_explore.py`
    - `tests/test_macro/test_research.py`
    - `tests/test_macro/test_prd.py`
    - `tests/test_macro/test_shard.py`
    - `tests/test_macro/__init__.py`
  - **Rationale**: Implements US-001 (subcommand registration) and US-003 (artifact validation) by creating the `src/deviate/cli/macro.py` module with all four Typer commands. Integrates with session state from T002 and artifact path checking. `cli/__init__.py` is modified to register macro commands onto the existing Typer app. This is the primary user-facing interface for the macro layer.
  - **Details**:
    - **Red**: Write `test_explore_help()` asserting `deviate cli explore --help` returns exit 0 with help text; `test_explore_transitions_to_explore()` asserting session state advances from IDLE to EXPLORE after invoke; `test_explore_rejects_if_not_idle()` asserting error when current_phase is not IDLE. Mirror for research, prd, shard commands with similar structure.
    - **Green**: Create `src/deviate/cli/macro.py` with a `macro_cli = typer.Typer()` instance. Define `@macro_cli.command() def explore()`, `def research()`, `def prd()`, `def shard()` that each: (1) load session from `.deviate/session.json`, (2) call `transition_to()` to enforce state machine, (3) run artifact validation (prd validates explore.md + research.md exist; research validates explore.md; shard validates prd.md), (4) save session, (5) print success via `console`.
    - **Green**: In `src/deviate/cli/__init__.py`, import `macro_cli` from `.macro` and call `cli.add_typer(macro_cli)` to register subcommands onto the existing Typer app.
    - **Red**: Write `test_prd_missing_explore_and_research()` asserting when both explore.md and research.md are absent, prd exits non-zero and output lists both files; `test_prd_missing_research_only()` asserting when only research.md is absent, prd lists only research.md; `test_research_missing_explore()` asserting research exits non-zero listing explore.md; `test_shard_missing_prd()` asserting shard exits non-zero listing prd.md.
    - **Green**: Implement `_validate_artifacts(required: list[Path]) -> list[Path]` helper in `macro.py` that checks each path exists, collects missing paths, and returns the list. Each command calls this with its required upstream artifacts, then formats a `{PHASE}_HALTED: missing upstream artifacts` error listing all missing paths if any.
    - **Refactor**: Extract artifact path definitions as module-level constants (e.g., `_EXPLORE_MD`, `_RESEARCH_MD`, `_PRD_MD`) using `Path("specs") / epic_slug / filename.md`. Use `console.print` for consistent Rich output styling matching existing `cli/__init__.py` patterns.
    - **Edge Cases**: Handle missing `.deviate/session.json` by initializing a default IDLE session. Handle missing `.deviate/` directory entirely with clear error message. Handle `epic_slug` resolution from active session or environment.
    - **Acceptance**: All four subcommands respond to `--help`. State transitions are enforced per US-002. Artifact validation aggregates all missing files per US-003. All error messages follow `{PHASE}_HALTED` convention with full path lists.

---

## Phase 3: Integration — Full-Cycle and E2E Verification
**Goal**: Verify the complete macro-layer pipeline works end-to-end from IDLE through SHARD with ledger append.

### Tasks

- [/] T004: Full-cycle integration test
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_integration/test_macro_full_cycle.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T001 T002 T003
  - **Files**:
    - `tests/test_integration/test_macro_full_cycle.py`
  - **Rationale**: Implements US-005 full-cycle verification. Validates that the complete pipeline (explore→research→prd→shard) functions as an integrated whole with correct state transitions, artifact validation, and ledger append. This integration test exercises all components together on a real filesystem.
  - **Details**:
    - **Red**: Write `test_full_idle_to_shard_cycle()` using CliRunner isolated filesystem: (1) scaffold `.deviate/session.json` with IDLE state, (2) create mock `explore.md`, `research.md`, `prd.md` artifacts in `specs/001-deviate-cli-python/`, (3) invoke `explore`, `research`, `prd`, `shard` sequentially, (4) assert each exits 0, (5) assert final session state is IDLE, (6) assert `specs/issues.jsonl` contains one IssueRecord with status SHARDED.
    - **Red**: Write `test_cycle_resets_for_second_run()` asserting after full cycle completes and session is IDLE, invoking `explore` again transitions to EXPLORE without residual state.
    - **Red**: Write `test_cycle_breaks_on_missing_artifact()` asserting when `explore.md` is missing, `prd` invocation fails mid-cycle with PRD_HALTED and session remains at RESEARCH (not advanced).
    - **Green**: No new production code needed — this task validates the integration of code delivered in T001-T003. Test failures here would drive fixes in `macro.py`, `ledger.py`, or `config.py`.
    - **Refactor**: Ensure test helpers (session setup, artifact scaffolding) are extracted into a `conftest.py` fixture for reuse across integration tests.
    - **Edge Cases**: Test with missing `.deviate/` directory (should be created by first command). Test with empty `specs/issues.jsonl` (ledger creation). Test idempotent re-run of shard (skip ledger append on second invocation).
    - **Acceptance**: Full cycle passes with correct state progression. Ledger contains exactly one record after first cycle. Second shard invocation idempotently skips. Mid-cycle failure preserves session state at the correct phase.

- [ ] T005: E2E bats workflow verification
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/test_e2e/test_macro_workflow.bats`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T004
  - **Files**:
    - `tests/test_e2e/test_macro_workflow.bats`
  - **Rationale**: Terminal verification task providing user-perspective E2E coverage. Tests the actual `deviate` CLI binary invocation (not via CliRunner) to catch issues with entry point wiring, subprocess behavior, and real filesystem state. This is the final gate before merge per the DeviaTDD terminal e2e pattern.
  - **Details**:
    - **Red**: Write `@test "deviate explore accepts --help"` asserting `deviate cli explore --help` exits 0. `@test "explore transitions state to EXPLORE"` running `deviate cli explore` and verifying `.deviate/session.json` contains `current_phase: EXPLORE`. `@test "prd with missing research.md fails with HALTED"` asserting `deviate cli prd` exits non-zero and output contains `PRD_HALTED` and lists the missing file. `@test "full cycle produces ledger entry"` running explore→research→prd→shard sequentially (with mocked artifacts) and asserting `specs/issues.jsonl` has one line with `SHARDED`.
    - **Green**: Implement bats test script at `tests/test_e2e/test_macro_workflow.bats` with setup/teardown helpers: `setup()` creates temp workspace with `.deviate/` and mock artifacts; `teardown()` cleans up. Use `run` for command execution and `[ "$status" -eq 0 ]` / `[ "$status" -ne 0 ]` for exit code assertions.
    - **Red**: Write `@test "session state survives across CLI invocations"` asserting explore sets EXPLORE, then research (after explore.md placement) transitions to RESEARCH — verifying state persistence between separate process invocations.
    - **Green**: Add assertion helpers: `assert_session_phase()` reads `.deviate/session.json` with `jq`; `assert_ledger_count()` counts lines in `specs/issues.jsonl`. Add `@test "shard idempotently skips duplicate"` asserting second shard run exits 0 and ledger still has 1 line.
    - **Refactor**: Ensure bats setup uses `mktemp -d` for isolated test workspaces. Use `bats_load_library bats-assert` if available for richer assertions, otherwise stick to plain `[ ]` checks for portability.
    - **Edge Cases**: Test with `DEVIATE_CONFIG` environment variable unset (defaults). Test with non-ASCII characters in project path. Test with no `.deviate/` directory at start (commands should handle gracefully).
    - **Acceptance**: All bats tests pass. CLI behaves correctly from real shell invocation. State persists across process boundaries. Exit codes match spec: 0 for success, non-zero for violations and missing artifacts.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (T001 → T002) — Domain models must exist before CLI can consume them
2. Phase 2 (T003) — CLI layer builds on domain models
3. Phase 3 (T004 → T005) — Integration and E2E verify assembled system

**Critical Dependency Chains**:
- T001 (IssueRecord) must precede T003 (shard uses ledger append)
- T002 (session state machine) must precede T003 (all commands use transition_to)
- T003 (macro CLI) must precede T004 (integration tests invoke commands)
- T004 (integration) must precede T005 (E2E gates on integration passing)

**Risk Hotspots**:
- `src/deviate/main.py` currently wraps `cli` as a sub-typer (`app.add_typer(cli, name="cli")`) — CLI invocations use `deviate cli <subcommand>` prefix. T003 adds `macro_cli` as sub-typer of `cli`, resulting in `deviate cli explore` etc. This is consistent with ISS-001's architecture but may require eventual refactoring in a future issue.
- Session state file locking: no OS-level locking as per defensive exclusions. Concurrent invocations may race. Risk is documented (RSK-001) but not addressed in this issue.
- Test isolation: T003 tests using CliRunner must mock or pre-create session state and artifacts on the isolated filesystem. Ensure `tmp_path` or `isolated_filesystem` is used consistently.

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` — modified in T003 (adds macro_cli import and add_typer call). Conflicts with any other issue adding subcommands to the same Typer app.
- `src/deviate/state/config.py` — modified in T002 (adds transition_to method to SessionState). Conflicts with any other issue modifying SessionState model.