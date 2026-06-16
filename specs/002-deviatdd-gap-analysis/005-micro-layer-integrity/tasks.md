# Implementation Tasks: feat/002-deviatdd-gap-analysis/005-micro-layer-integrity

## Phase 1: Core Status Model Expansion
**Goal**: Expand `TaskRecord.status` Literal to include `YELLOW_APPROVED` and `YELLOW_REJECTED` so the ledger can record the outcome of YELLOW phase decisions

### Tasks

- TSK-005-01: Expand TaskRecord.status Literal for YELLOW decision outcomes
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_ledger.py::TestTaskRecord -v --no-header -q`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: US-008-JUDSKILL Scenario 5 (TaskRecord.status accepts YELLOW/JUDGE) and US-009-STALE (ledger integrity) require `YELLOW_APPROVED` and `YELLOW_REJECTED` as valid status values. `ledger.py` line 64 defines the `status` Literal — must expand to include these values. Test file must validate the new values pass schema validation.
  - **Details**:
    - **Red**: Write failing tests: `test_task_record_status_includes_yellow_approved()` and `test_task_record_status_includes_yellow_rejected()` asserting `TaskRecord(status="YELLOW_APPROVED")` and `TaskRecord(status="YELLOW_REJECTED")` pass validation without error
    - **Green**: Expand `status: Literal[...]` in `ledger.py:63-65` from `"PENDING" | "RED" | "GREEN" | "YELLOW" | "JUDGE" | "REFACTOR" | "COMPLETED" | "FAILED"` to include `"YELLOW_APPROVED" | "YELLOW_REJECTED"`
    - **Refactor**: Ensure status Literal order is alphabetically consistent across all references
    - **Edge Cases**: Verify model rejects invalid status values even after expansion — `test_extra_fields_forbidden` and `test_invalid_status` must still pass
    - **Acceptance**: `TaskRecord(id="TSK-005-01", issue_id="ISS-002-005", description="test", status="YELLOW_APPROVED")` and `status="YELLOW_REJECTED"` both construct without error; existing `TaskRecord(status="PENDING")` still works

---

## Phase 2: CacheDiscipline Enforcement Module
**Goal**: Create `CacheDiscipline` class with 4 validation rules and hook it into `_run_tdd_cycle()` at phase boundaries (US-001-CACHE)

### Tasks

- TSK-005-02: Create CacheDiscipline class with phase-boundary validation
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_cache_discipline.py -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Dependency**: (none)
  - **Files**:
    - `src/deviate/core/cache_discipline.py`
    - `src/deviate/cli/micro.py`
    - `tests/test_core/test_cache_discipline.py`
  - **Rationale**: US-001-CACHE (FR-007) defines 4 cache discipline rules plus hook at every phase boundary. `cache_discipline.py` is the NEW file for the `CacheDiscipline` class. `micro.py` is where `_run_tdd_cycle()` phase boundaries are wired. Test file covers all 4 scenarios with performance constraint L_max <= 5ms.
  - **Details**:
    - **Red**: Write `test_cache_discipline_model_switch()` asserting `CacheDisciplineViolation` raised when model changes between RED and GREEN; `test_cache_discipline_tool_change()` for tool def changes; `test_cache_discipline_no_change_passes()` for no-change case; `test_cache_discipline_phase_boundary()` asserting validate() is called after each phase in `_run_tdd_cycle`
    - **Green**: Implement `CacheDiscipline` class with `validate(phase, model, previous_model, ...)` static method and a `CacheStore` dataclass tracking `model`, `tool_definitions`, `system_prompt`, `test_files`; raise `CacheDisciplineViolation` (custom Exception subclass) when any of the 4 rules is violated. Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` after each phase call.
    - **Refactor**: Ensure `CacheDiscipline.validate()` runs in O(1) — dict comparison, no iteration
    - **Edge Cases**: First phase call (no previous state) must pass validation; concurrent phase transitions must not share staled cache state
    - **Acceptance**: All 4 US-001-CACHE scenarios pass; `CacheDiscipline.validate()` completes in L_max <= 5ms; hook present in `_run_tdd_cycle` body

---

## Phase 3: StubAgentBackend for Deterministic Testing
**Goal**: Add `StubAgentBackend` that returns a valid `HandoverManifest` without spawning a subprocess, enabling contract-based test assertions (US-006-MOCK)

### Tasks

- TSK-005-03: Implement StubAgentBackend and register "stub" backend
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_agent.py -v --no-header -q`
  - **Estimated Time**: 45 minutes
  - **Dependency**: (none)
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: US-006-MOCK Scenario 1 and Scenario 3 (FR-017) require a `StubAgentBackend` that returns valid `HandoverManifest` without subprocess. `agent.py` is the sole host — add class and register in `BACKEND_COMMANDS`. Test coverage validates contract compliance and no-subprocess guarantee.
  - **Details**:
    - **Red**: Write `test_stub_backend_returns_valid_manifest()` asserting `StubAgentBackend().invoke("test")` returns `HandoverManifest(phase="RED", status="success")` without side-effects; `test_stub_backend_no_subprocess()` asserting no `subprocess.Popen` call is made during invocation
    - **Green**: Implement `StubAgentBackend` class with `invoke(prompt, ...)` method returning `HandoverManifest(phase="RED", status="success")`. Add `"stub": "stub"` entry to `BACKEND_COMMANDS`. Add an internal flag `_invoked = True` for subprocess-free assertion.
    - **Refactor**: Ensure `StubAgentBackend.invoke()` signature matches `AgentBackend.invoke()` exactly (same return type, same parameter shape)
    - **Edge Cases**: `StubAgentBackend` must handle `output_callback` parameter (fire callback with prompt text even though no subprocess); must accept and ignore `timeout` parameter
    - **Acceptance**: `StubAgentBackend().invoke("test prompt")` returns `HandoverManifest(phase="RED", status="success")`; zero subprocess calls during invocation; `BACKEND_COMMANDS["stub"]` resolves without error

---

## Phase 4: YELLOW Handoff Contract — Manual & Auto Cycle
**Goal**: Fix `green_post` to transition to YELLOW on tamper detection, fix `yellow_post --approved` to transition to JUDGE, restructure `_PHASE_MAP` to exclude YELLOW, and add TamperGuard gate in `_run_tdd_cycle` body (US-002-YELMAN, US-003-YELAUTO)

### Tasks

- TSK-005-04: Implement YELLOW handoff contract in green_post, yellow_post, and _run_tdd_cycle
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_green.py tests/test_cli/test_yellow.py tests/test_micro/test_orchestration.py -v --no-header -q`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-005-01 (needs YELLOW_APPROVED/YELLOW_REJECTED status values)
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_cli/test_green.py`
    - `tests/test_cli/test_yellow.py`
    - `tests/test_micro/test_orchestration.py`
  - **Rationale**: US-002-YELMAN (FR-018, FR-008) covers 5 scenarios for manual green_post/YELLOW handoff — all currently broken in micro.py. `green_post` at line 1767 detects tamper but does NOT append YELLOW to ledger or transition session. `yellow_post --approved` at line 1884 transitions to GREEN (should be JUDGE). US-003-YELAUTO (FR-018) covers 7 scenarios for auto cycle — YELLOW must be removed from `_PHASE_MAP` (currently at line 998) and TamperGuard gate added to `_run_tdd_cycle` loop body.
  - **Details**:
    - **Red**: Write `test_green_post_tamper_detected_transitions_to_yellow()` asserting session transitions to YELLOW and ledger appends GREEN+YELLOW on TAMPER_DETECTED; `test_green_post_tamper_pass_stays_green()` asserting no YELLOW transition; `test_green_post_yellow_triggered_by_tamper_not_commit()` asserting YELLOW_TRIGGERED driven by TamperGuard verdict, not `_commit_phase` return value; `test_yellow_post_approved_transitions_to_judge()` asserting session=JUDGE and ledger=YELLOW_APPROVED; `test_yellow_post_rejected_transitions_to_green()` asserting session=GREEN and ledger=YELLOW_REJECTED; `test_yellow_not_in_phase_map()` asserting `"YELLOW" not in _PHASE_MAP`; `test_tdd_cycle_inlines_yellow_gate()` asserting TamperGuard gate between GREEN and JUDGE calls in cycle loop; `test_tdd_cycle_yellow_approved_continues_to_judge()`; `test_tdd_cycle_yellow_rejected_re_runs_green()`; `test_run_yellow_phase_helper_returns_decision()` asserting (session, decision) tuple return
    - **Green**: In `green_post()` at `micro.py:1767`: on `tamper_verdict == TAMPER_DETECTED`, call `_append_status_transition(task, "YELLOW", ledger_path)` and `session = session.force_transition_to("YELLOW")`. In `yellow_post()` at `micro.py:1882` (`--approved`): change `force_transition_to("GREEN")` to `force_transition_to("JUDGE")`, append `YELLOW_APPROVED`. In `yellow_post()` at `micro.py:1888` (`--rejected`): append `YELLOW_REJECTED`. In `_PHASE_MAP` at `micro.py:995-1001`: remove `"YELLOW": _run_yellow_phase`. In `_run_tdd_cycle()` at `micro.py:1004`: add `TamperGuard.evaluate(GREEN_IMPLEMENTATION)` check in loop body between `_run_green_phase` and `_run_judge_phase`. Ensure `_run_yellow_phase()` is called from cycle body (not map) and returns `(session, decision)`.
    - **Refactor**: Extract tamper-aware YELLOW routing into `_should_route_to_yellow(session) -> bool` helper for clarity; add `start_phase` parameter to `_run_tdd_cycle` signature
    - **Edge Cases**: When YELLOW is triggered but session is already at YELLOW, do not double-trigger; when `_commit_phase` returns `False` (tree clean), verify `YELLOW_TRIGGERED` is NOT emitted unless TamperGuard verdict is `TAMPER_DETECTED`
    - **Acceptance**: All 12 scenarios from US-002-YELMAN and US-003-YELAUTO pass; `_PHASE_MAP` does NOT contain `"YELLOW"`; `_run_yellow_phase` is called from `_run_tdd_cycle` loop body, not from map; `yellow_post --approved` leaves session in JUDGE; `yellow_post --rejected` leaves session in GREEN

---

## Phase 5: Train Rollback — git revert with RED Boundary
**Goal**: Replace `git reset --hard HEAD~1` in `_run_judge_phase` with `git revert --no-edit <red_sha>..HEAD`, persist `RollbackSnapshot`, and track RED commit boundary (US-004-ROLLBACK, US-010-HITL)

### Tasks

- TSK-005-05: Implement JUDGE train rollback with RED-boundary git revert and RollbackSnapshot persistence
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_micro.py::test_judge_train_rollback_all_commits_since_red tests/test_cli/test_micro.py::test_judge_rollback_preserves_red tests/test_cli/test_micro.py::test_judge_no_violation_proceeds tests/test_state/test_ledger.py::test_rollback_snapshot_model tests/test_state/test_ledger.py::test_rollback_snapshot_sha_validation tests/test_state/test_ledger.py::test_rollback_snapshot_tracks_red_boundary -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Dependency**: (none)
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/state/ledger.py`
    - `tests/test_cli/test_micro.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: US-004-ROLLBACK (FR-008) Scenario 1 and US-010-HITL (FR-008, FR-019) require train rollback to use `git revert --no-edit <red_sha>..HEAD` instead of `git reset --hard HEAD~1`. `micro.py` line 864 currently uses `git reset --hard HEAD~1`. `ledger.py` already has `RollbackSnapshot` (line 252) but needs `red_sha` field and the snapshot isn't persisted in `_run_judge_phase`. Also `_run_judge_phase` line 864 (execute) path also needs the same fix.
  - **Details**:
    - **Red**: Write `test_judge_train_rollback_all_commits_since_red()` asserting `git revert --no-edit <red_sha>..HEAD` is called on COMPLIANCE_VIOLATION; `test_judge_rollback_preserves_red()` asserting RED commit(s) remain in history after revert; `test_judge_no_violation_proceeds()` asserting no revert and no snapshot on clean pass; `test_rollback_snapshot_tracks_red_boundary()` asserting `RollbackSnapshot(red_sha=...)` stores and validates RED SHA; existing `test_rollback_snapshot_model()` and `test_rollback_snapshot_sha_validation()` must still pass
    - **Green**: In `micro.py` `_run_judge_phase()` rejection branch (lines 864-869): replace `["git", "reset", "--hard", "HEAD~1"]` with `["git", "rev-list", "--max-parents=0", "HEAD"]` to find root commit → `["git", "revert", "--no-edit", f"{red_sha}..HEAD"]`. Persist `RollbackSnapshot(phase="JUDGE", branch=branch, commit_sha=red_sha, red_sha=red_sha, reason=feedback)`. In `ledger.py`: add `red_sha: str = Field(pattern=r"^[a-f0-9]{40}$")` to `RollbackSnapshot` model. Apply same change to EXECUTE phase JUDGE rejection at line 1255.
    - **Refactor**: Extract `_find_red_boundary_sha(root) -> str` and `_execute_rollback_revert(root, red_sha)` helper functions from `_run_judge_phase` to avoid duplication between JUDGE and EXECUTE paths
    - **Edge Cases**: When REPO has only 1 commit (RED is the initial commit), revert range must handle gracefully; when red_sha is `None` (no RED commit found), fall back to `git reset --hard HEAD~1` with a warning log
    - **Acceptance**: `git revert --no-edit <red_sha>..HEAD` is invoked on violation; RED commits are preserved; `RollbackSnapshot(red_sha=...)` validates correctly with SHA pattern; execution re-routed to GREEN after revert

---

## Phase 6: Tasks Ledger Separation — Proposal Pattern
**Goal**: Create `tasks_ledger.py` with `generate_jsonl_from_md()` and `validate_tasks_jsonl()`, and wire `tasks post` to use `.jsonl.proposal` + `--confirm` pattern (US-005-SKILLS)

### Tasks

- TSK-005-06: Implement tasks.jsonl proposal pattern with generate_jsonl_from_md and --confirm
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_core/test_tasks_ledger.py tests/test_cli/test_meso.py -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Dependency**: (none)
  - **Files**:
    - `src/deviate/core/tasks_ledger.py`
    - `src/deviate/cli/meso.py`
    - `tests/test_core/test_tasks_ledger.py`
    - `tests/test_cli/test_meso.py`
  - **Rationale**: US-005-SKILLS Scenario 3 and 4 (FR-013) require `tasks post` to create `.jsonl.proposal` without `--confirm` and only append to `tasks.jsonl` when `--confirm` is passed. `tasks_ledger.py` is NEW — holds `generate_jsonl_from_md()` (parses tasks.md into JSONL) and `validate_tasks_jsonl()` (schema validation). `meso.py` is where `tasks post` CLI handler lives and needs the proposal/write pattern.
  - **Details**:
    - **Red**: Write `test_generate_jsonl_from_md()` asserting task lines from tasks.md parse into valid JSONL objects with `id`, `issue_id`, `description`, `status: "PENDING"`, `execution_mode`; `test_validate_tasks_jsonl()` asserting schema validation against TaskRecord model; `test_tasks_post_proposal()` asserting non-confirm run creates `.jsonl.proposal` but does NOT touch `tasks.jsonl`; `test_tasks_post_confirm()` asserting confirm run appends proposal content to `tasks.jsonl` and removes proposal file
    - **Green**: Implement `generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[dict]` that reads tasks.md, parses `TSK-NNN-NN:` lines with mode metadata, and outputs clean JSONL records. Implement `validate_tasks_jsonl(records: list[dict]) -> list[str]` that validates each record against `TaskRecord` schema and returns error messages. In `meso.py` `tasks post` handler: write proposal to `.jsonl.proposal`; if `--confirm` flag present, pipe proposal content through `validate_tasks_jsonl()`, then append to `tasks.jsonl` using `append_task_record`, then remove proposal file.
    - **Refactor**: Ensure `append_task_record` idempotency (skip duplicate IDs) is preserved in the confirm path — use `_append_record` via `append_task_record`
    - **Edge Cases**: Empty tasks.md produces empty proposal; malformed task IDs in tasks.md are skipped with warning; duplicate IDs in proposal are deduplicated at confirm time; missing `.jsonl.proposal` at confirm time raises clear error
    - **Acceptance**: `tasks post` without `--confirm` creates `.jsonl.proposal` only; `tasks post --confirm` appends and removes proposal; `generate_jsonl_from_md()` handles Mode: TDD/IMMEDIATE metadata fields; `validate_tasks_jsonl()` catches malformed task IDs

---

## Phase 7: Session Resume + Stale PENDING Resolution
**Goal**: Add `start_phase` parameter to `_run_tdd_cycle`, implement session-phase resume in `_run_single`, and verify `_find_task_record` returns latest status record (US-003-YELAUTO Scenarios 5-6, US-009-STALE)

### Tasks

- TSK-005-07: Implement session-phase resume in _run_single and add start_phase to _run_tdd_cycle
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_run.py tests/test_cli/test_micro.py -v --no-header -q`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-005-04 (needs YELLOW handoff contract for phase routing)
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_run.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-003-YELAUTO (FR-018) Scenarios 5-6 require `_run_tdd_cycle` to accept `start_phase` parameter and `_run_single` to resume from `session.current_phase`. US-009-STALE (FR-019 ledger integrity) requires `_find_task_record` to return the latest (last) matching record — `_collect_latest_task_records` (line 452) already returns latest per task, but `_run_single` line 1332 only checks `COMPLETED`/`REFACTOR` terminal statuses and doesn't consult `session.current_phase`. Add `YELLOW`/`JUDGE` as resume-eligible phases.
  - **Details**:
    - **Red**: Write `test_run_resumes_from_session_phase()` asserting that when `session.current_phase="JUDGE"`, `_run_single` dispatches to JUDGE without re-running RED/GREEN; `test_run_resumes_from_yellow()` same for YELLOW; `test_run_resumes_from_judge()` same for JUDGE; `test_find_task_record_returns_latest_status()` asserting that with records `[PENDING, RED, GREEN, JUDGE]`, `_find_task_record` returns the JUDGE record; `test_find_task_record_multiple_entries_returns_last()` asserting ordering correctness; `test_task_already_done_triggers_for_re_run_tasks()` asserting existing guard extends to YELLOW/JUDGE terminal records
    - **Green**: In `_run_tdd_cycle()` at `micro.py:1004`: add `start_phase: str | None = None` parameter; when `start_phase` is set, dispatch to the matching phase function directly instead of starting from RED. In `_run_single()` at `micro.py:1320`: load `session.current_phase` and if in `{"YELLOW", "JUDGE", "REFACTOR"}`, call `_run_tdd_cycle(..., start_phase=session.current_phase)`. Verify `_find_task_record` at line 441 uses `_collect_latest_task_records` which returns last record per ID — already correct by inspection but add assertion.
    - **Refactor**: Extract `_resume_phase` function for clarity from `_run_single` session-check logic
    - **Edge Cases**: When `session.current_phase` is IDLE (no resume needed), fall back to existing PENDING dispatch; when session phase is RED/GREEN but task was already completed, existing TASK_ALREADY_DONE guard takes precedence; when session phase is YELLOW but yellow_triggered was cleared, treat as GREEN resume
    - **Acceptance**: `_run_single` dispatches to YELLOW/JUDGE/REFACTOR directly when session.current_phase matches; `_run_tdd_cycle(start_phase="JUDGE")` skips RED/GREEN and starts at JUDGE; `_find_task_record` returns latest status record; `TASK_ALREADY_DONE` guard triggers for completed tasks

---

## Phase 8: Test Infrastructure Refactoring & Skills Cleanup
**Goal**: Replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock in `conftest.py`, remove `_run_pytest` function-level mocks from test files, add step 7 to `deviate-tasks` SKILL.md, and audit all 18 skills for stale `--no-judge`/`--no-refactor` flags (US-006-MOCK, US-005-SKILLS)

### Tasks

- TSK-005-08: System-edge mocks in conftest.py, test refactoring, and skills cleanup
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_micro/conftest.py tests/test_micro/test_red.py tests/test_micro/test_green.py tests/test_micro/test_refactor.py tests/test_micro/test_orchestration.py tests/test_skills/ -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-005-03 (needs StubAgentBackend for system-edge contract)
  - **Files**:
    - `tests/test_micro/conftest.py`
    - `tests/test_micro/test_red.py`
    - `tests/test_micro/test_green.py`
    - `tests/test_micro/test_refactor.py`
    - `tests/test_micro/test_orchestration.py`
    - `src/deviate/prompts/skills/deviate-tasks/SKILL.md`
  - **Rationale**: US-006-MOCK (FR-017) Scenario 2 requires `conftest.py` to mock `subprocess.Popen` instead of `_invoke_agent` — line 20 of conftest currently patches `_invoke_agent`. US-005-SKILLS (FR-012) requires step 7 in deviate-tasks decision tree for integration/wiring code. AGENTS.md mandates no `_run_pytest` mocks for performance. Both are mechanical changes with existing test coverage (IMMEDIATE mode).
  - **Details**:
    - **Implementation**: In `tests/test_micro/conftest.py`: replace `patch("deviate.cli.micro._invoke_agent")` with `patch("subprocess.Popen")`. In test files (`test_red.py`, `test_green.py`, `test_refactor.py`, `test_orchestration.py`): remove all `@patch("deviate.cli.micro._run_pytest")` decorators and function-level mocks — these are no longer needed because the `subprocess.Popen` system-edge mock covers the subprocess boundary. Add assertion blocks that verify `Popen` call args (CLI, env vars, stdin) were passed correctly. In `deviate-tasks/SKILL.md`: add step 7 to the decision tree: "Does this task connect/wire already-tested components via subprocess, API, or message passing? → TDD with system-edge mock boundary (mock subprocess.Popen, assert CLI args/env/stdin)."
    - **Refactor**: Audit test files for any remaining stale `_run_pytest` references using `grep`; ensure `conftest.py` `Popen` mock returns appropriate `subprocess.CompletedProcess` for each test case. Audit all 18 SKILL.md files under `prompts/skills/` for `--no-judge`/`--no-refactor` flags (these should have been replaced with `--profile` in prior work — if found, replace them).
    - **Acceptance**: All 5 test files pass with `subprocess.Popen` mock instead of `_invoke_agent`; zero `_run_pytest` mocks remain in test files; `deviate-tasks` SKILL.md contains step 7 in its decision tree; skills audit confirms zero `--no-judge`/`--no-refactor` refs across all 18 skill files

---

## Phase 9: Wiring Skills — YELLOW and JUDGE
**Goal**: Verify `_load_skill_content("YELLOW")` is wired into yellow_pre/yellow_post and `_load_skill_content("JUDGE")` into judge CLI commands and `_run_judge_phase`, with graceful degradation on missing skill files (US-007-YELSKILL, US-008-JUDSKILL)

### Tasks

- TSK-005-09: Wire YELLOW and JUDGE skill loading into CLI handlers and _run_judge_phase
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `grep -q "_load_skill_content" src/deviate/cli/micro.py && echo "SKILL LOADING WIRED"` and `pytest tests/test_cli/test_micro.py -v --no-header -q`
  - **Estimated Time**: 30 minutes
  - **Dependency**: (none)
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/skills/deviate-yellow/SKILL.md`
    - `src/deviate/prompts/skills/deviate-judge/SKILL.md`
  - **Rationale**: US-007-YELSKILL (FR-018) Scenario 3 and US-008-JUDSKILL (FR-019) Scenario 3 require `_load_skill_content` to be called from respective CLI handlers and phase functions. The skills already exist on disk (`deviate-yellow/SKILL.md`, `deviate-judge/SKILL.md`) and `_SKILL_NAMES` already maps them correctly — this task verifies the wiring and adds any missing `_load_skill_content()` calls.
  - **Details**:
    - **Implementation**: Verify `yellow_pre` (line 1842) and `yellow_post` (line 1861) call `_load_skill_content("YELLOW")` — if missing, add the call and pass skill content into YELLOW phase manifest. Verify `_run_judge_phase` (line 812) already calls `_load_skill_content("JUDGE")` at line 825 — already done. Verify judge_pre CLI handler at line 1914 calls `_load_skill_content("JUDGE")` — if missing, add. Ensure all loading is wrapped in try/except with graceful warning on failure: `console.print(f"[yellow]SKILL_NOT_FOUND[/] {skill_name}")`.
    - **Refactor**: Ensure consistent logging format for skill loading across all 5 phases (RED, GREEN, YELLOW, JUDGE, REFACTOR)
    - **Acceptance**: `yellow_pre` and `yellow_post` invoke `_load_skill_content("YELLOW")`; `judge_pre` and `_run_judge_phase` invoke `_load_skill_content("JUDGE")`; missing skill files produce warning log but do NOT block execution; all 5 phases use consistent skill-loading pattern

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-005-01: Status Expansion) — foundation for YELLOW_APPROVED/YELLOW_REJECTED status values
2. Phase 2 (TSK-005-02: CacheDiscipline) — standalone new module, no dependencies
3. Phase 3 (TSK-005-03: StubAgentBackend) — standalone, enables Phase 8
4. Phase 4 (TSK-005-04: YELLOW Handoff) — depends on Phase 1 (status values)
5. Phase 5 (TSK-005-05: Train Rollback) — standalone, mechanical change
6. Phase 6 (TSK-005-06: Tasks Ledger) — standalone new module
7. Phase 7 (TSK-005-07: Session Resume) — depends on Phase 4 (YELLOW handoff)
8. Phase 8 (TSK-005-08: Mocks & Cleanup) — depends on Phase 3 (StubAgentBackend)
9. Phase 9 (TSK-005-09: Skills Wiring) — standalone, verification pass

**Critical Dependency Chains**:
- TSK-005-04 (YELLOW Handoff) → must follow TSK-005-01 (Status Expansion)
- TSK-005-07 (Session Resume) → must follow TSK-005-04 (YELLOW Handoff)
- TSK-005-08 (System Mocks) → must follow TSK-005-03 (StubAgentBackend)

**Risk Hotspots**:
- `_run_tdd_cycle` in `micro.py:1004` is the most coupled function — 4 tasks touch it (TSK-005-02, TSK-005-04, TSK-005-05, TSK-005-07). Merge conflicts likely.
- `_run_judge_phase` at `micro.py:812` — 2 tasks touch it (TSK-005-04, TSK-005-05). Rollback logic must be coordinated.
- `green_post` at `micro.py:1736` — YELLOW handoff logic must not break existing tamper detection path.

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` — touched by Phases 2, 4, 5, 7, 9
- `src/deviate/state/ledger.py` — touched by Phases 1, 5
- `tests/test_micro/conftest.py` — touched by Phase 8
- Batch Phases 2, 4, 5, 7 into a single sequential commit train to minimize merge overhead

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, check=True)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.

## Per-Task Git Isolation

### TSK-005-01: Status Expansion
- No git operations in this task — purely schema/model changes. No isolation needed.

### TSK-005-02: CacheDiscipline
- `_run_tdd_cycle` in micro.py calls `git diff` — the `tmp_git_repo` fixture must be passed through the session cascade. New `CacheDiscipline` methods accept `repo: Path | None = None`.

### TSK-005-03: StubAgentBackend
- No git operations — StubAgentBackend returns manifest without subprocess. No isolation needed.

### TSK-005-04: YELLOW Handoff
- `green_post` and `yellow_post` run `git restore`, `git add`, `git commit` — ALL tests MUST use `tmp_git_repo` fixture. Mock `subprocess.Popen` for agent calls; mock `_run_pytest` for performance (AGENTS.md mandate).

### TSK-005-05: Train Rollback
- `git revert --no-edit <red_sha>..HEAD` is the core behavior under test — absolutely critical to use `tmp_git_repo` with known commit history. Fixture must create: RED commit → GREEN commit(s) → verify revert. Mock `_invoke_agent` with `subprocess.Popen` mock for contract assertions.

### TSK-005-06: Tasks Ledger
- No git operations — pure file I/O over JSONL. No isolation needed, but use `tmp_path` for file-system independence.

### TSK-005-07: Session Resume
- `_run_single` delegates to `_run_tdd_cycle` which may run git operations. All tests use `tmp_git_repo` fixture. Session state is JSON file under `.deviate/` — use `tmp_path` for session file independence.

### TSK-005-08: Mocks & Cleanup
- Test-only changes. No new git operations introduced. Existing git-asserting test behavior preserved via `tmp_git_repo`.

### TSK-005-09: Skills Wiring
- No git operations — purely import/function wiring. No isolation needed.
