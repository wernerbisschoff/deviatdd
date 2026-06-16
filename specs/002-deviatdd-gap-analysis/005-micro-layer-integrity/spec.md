# FEATURE_SPECIFICATION: specs/002-deviatdd-gap-analysis/005-micro-layer-integrity/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Issue ID**: ISS-002-005
- **Issue Title**: Micro-Layer Integrity — FULL TDD Phase Model (RED → GREEN → YELLOW? → JUDGE → REFACTOR), Train Rollback, Skill Rewrites, Tasks Ledger Separation, TDD Mock Boundary, YELLOW/JUDGE Skills
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/005-micro-layer-integrity.md`
- **Workstation Paths**:
  - `src/deviate/core/cache_discipline.py` — NEW: `CacheDiscipline` class with 4 validation rules
  - `src/deviate/cli/micro.py` — MODIFY: hook `CacheDiscipline.validate()` at phase boundaries, implement JUDGE train rollback with `git revert` targeting all commits since RED, add `"YELLOW": "deviate-yellow"` and `"JUDGE": "deviate-judge"` to `_SKILL_NAMES`
  - `src/deviate/state/ledger.py` — MODIFY: add `RollbackSnapshot` model, add `YELLOW`/`JUDGE` to `TaskRecord.status` Literal
  - `src/deviate/core/tasks_ledger.py` — NEW: `generate_jsonl_from_md()`, `validate_tasks_jsonl()`
  - `src/deviate/cli/meso.py` — MODIFY: `tasks post` generates `.jsonl.proposal`, requires `--confirm`
  - `src/deviate/prompts/skills/deviate-*/SKILL.md` — MODIFY: 18 files, replace `--no-judge`/`--no-refactor` with `--profile`, remove `.sh` refs, use `deviate <cmd> pre/post`
  - `src/deviate/core/agent.py` — MODIFY: add `StubAgentBackend` class + `"stub"` entry in `BACKEND_COMMANDS`
  - `tests/test_micro/conftest.py` — MODIFY: replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock
  - `tests/test_micro/test_red.py`, `test_green.py`, `test_refactor.py`, `test_orchestration.py` — MODIFY: remove `_run_pytest` function-level mocks, use system-edge subprocess assertions
  - `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — MODIFY: add integration/wiring guidance to decision tree step 7
  - `src/deviate/prompts/skills/deviate-yellow/SKILL.md` — NEW: YELLOW phase skill
  - `src/deviate/prompts/skills/deviate-judge/SKILL.md` — NEW: JUDGE phase skill
- **Upstream PRD**: `specs/002-deviatdd-gap-analysis/prd.md`
- **Constitution Path**: `specs/constitution.md`

## THE_PROBLEM_CONTRACT

### Phase Handoff Contract — The YELLOW Decision Tree

The core question this issue resolves: **How does YELLOW get invoked, how does `green_post` decide YELLOW must run next, and how does `deviate run` route to YELLOW instead of JUDGE?**

There are three distinct invocation pathways, each currently broken or missing:

1. **Manual CLI — `deviate green post` → YELLOW handoff**: `green_post` at `micro.py:693-755` does NOT transition to YELLOW on tamper detection. The `YELLOW_TRIGGERED` message at line 753 is a side-effect of `_commit_phase` returning `False`, not a deliberate routing signal. `yellow_post --approved` incorrectly transitions to GREEN instead of JUDGE.
2. **Auto cycle — `deviate run` / `_run_tdd_cycle()`**: `_PHASE_MAP` has no YELLOW entry. `_run_green_phase` doesn't run TamperGuard. The cycle is rigid RED → GREEN → JUDGE → REFACTOR with no conditional branching.
3. **Session-state-based resumable routing**: `_run_single()` always starts from PENDING, ignoring `session.current_phase`. No mechanism for "resume from YELLOW" or "resume from JUDGE".

### Current Gaps Summary

| Gap | Location | Impact |
|-----|----------|--------|
| `green_post` doesn't transition to YELLOW on tamper detect | `micro.py:730-731` | Session stays at GREEN, no routing signal |
| `YELLOW_TRIGGERED` is a misleading side-effect | `micro.py:753` | Not an actual YELLOW routing signal |
| `_PHASE_MAP` has no YELLOW entry | `micro.py:345` | Auto cycle can never run YELLOW |
| `_run_green_phase` doesn't run TamperGuard | `micro.py:262-282` | No tamper detection in auto cycle |
| `yellow_post --approved` transitions to GREEN | `micro.py:837` | Session state contradicts next expected phase |
| `TaskRecord.status` lacks YELLOW and JUDGE | `ledger.py:63` | Can't record YELLOW/JUDGE transitions |
| `_run_judge_phase` doesn't append status transition | `micro.py:285-319` | JUDGE transitions invisible in ledger |
| `_run_single` has no session-phase resume logic | `micro.py:425-449` | Always restarts from PENDING |
| `_find_task_record()` returns first match (stale PENDING) | `micro.py:150` | `TASK_ALREADY_DONE` guard never triggers |
| Train rollback targets single SHA, not full revert scope | `micro.py` (implied) | Partial revert may leave inconsistent state |

### Upstream Requirement Tracing

| ID | Title | PRD Section |
|----|-------|-------------|
| FR-007 | Cache Discipline Enforcement Module | FR-007-CacheDiscipline |
| FR-008 | JUDGE Train Rollback | FR-008-TrainRollback |
| FR-012 | Skill File Rewrites | FR-012-SkillActionLogic |
| FR-013 | tasks.md vs tasks.jsonl Separation | FR-013-TasksLedgerSeparation |
| FR-017 | TDD Integration Mock Boundary | FR-017-TDDMockBoundary |
| FR-018 | YELLOW Phase Skill | FR-018-YELLOWSkill |
| FR-019 | JUDGE Phase Skill | FR-019-JUDGESkill |

## SCOPE_BOUNDARIES

### Hard Inclusions

**Cache Discipline and Phase Boundaries**
- `CacheDiscipline` class with 4 rules: no model switching, no tool def changes, no system prompt mutation, no read-only test file conversation append
- Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries

**YELLOW Handoff Contract (GREEN → [YELLOW?] → JUDGE)**
- `green_post` at `micro.py:693`: on `TamperGuard.evaluate() == TAMPER_DETECTED`, session transitions to YELLOW, ledger appends YELLOW. Currently stays at GREEN — primary YELLOW handoff bug.
- `green_post` YELLOW_TRIGGERED message at `micro.py:753`: replace with explicit `if tamper_verdict == TAMPER_DETECTED: session → YELLOW; return`
- `_run_tdd_cycle()` at `micro.py:353`: add TamperGuard gate between GREEN and JUDGE using extracted `_run_yellow_phase()` helper. NOT a `_PHASE_MAP` entry.
- `_run_yellow_phase()` helper: returns `(session, decision)` tuple. Called from cycle loop body, not from `_PHASE_MAP`. On `approved` → JUDGE, on `rejected` → re-run GREEN.
- `yellow_post --approved` at `micro.py:837`: transition session to JUDGE (not GREEN)
- `yellow_post --rejected` at `micro.py:843`: transition session to GREEN (already correct)
- `_run_tdd_cycle` accepts optional `start_phase` parameter for session-resume mode

**Ledger and Status Model**
- Expand `TaskRecord.status` Literal in `ledger.py:63` to include `YELLOW`, `JUDGE`, `YELLOW_APPROVED`, `YELLOW_REJECTED`
- `_run_judge_phase()`: add `_append_status_transition(task, "JUDGE", ledger_path)`
- `green_post`: append YELLOW to ledger when TamperGuard detects tampering
- `yellow_post`: append `YELLOW_APPROVED` or `YELLOW_REJECTED` to ledger

**Stale PENDING Record Resolution (HITL Decision)**
- Modify `_find_task_record()` in `micro.py:150` to return the LAST record matching `task_id`, not the first. This ensures `TASK_ALREADY_DONE` guard in `_run_single` (`micro.py:437`) correctly identifies completed tasks via their latest status record.

**Train Rollback — All Commits Since RED (HITL Decision)**
- JUDGE `_run_judge_phase()`: on `COMPLIANCE_VIOLATION` → `RollbackSnapshot` → `git revert --no-edit <red_sha>..HEAD` (revert ALL commits since RED boundary, not just the single GREEN SHA) → inject feedback → re-route to GREEN
- `RollbackSnapshot` model in `state/ledger.py` with `extra = "forbid"`
- Track the RED commit SHA in addition to GREEN SHA for boundary detection

**Tasks Ledger and Skills**
- `tasks post`: parse `tasks.md` → `.jsonl.proposal` → requires `--confirm` to append
- 18 SKILL.md rewrites: replace flags, remove `.sh` refs, use `deviate <cmd> pre/post`
- `StubAgentBackend` class in `src/deviate/core/agent.py` with `"stub"` in `BACKEND_COMMANDS`
- `conftest.py`: replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock
- Test files: remove `_run_pytest` mocks; use system-edge mocks; assert `Popen` call args
- `deviate-tasks` SKILL.md: add step 7 for integration/wiring guidance
- `deviate-yellow` SKILL.md: NEW skill with review/amend workflow
- `_SKILL_NAMES["YELLOW"] = "deviate-yellow"`
- Wire `_load_skill_content("YELLOW")` into `yellow_pre`/`yellow_post` CLI handlers
- `deviate-judge` SKILL.md: NEW skill with compliance evaluation workflow
- Replace `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"`
- Wire `_load_skill_content("JUDGE")` into `_run_judge_phase()` and judge CLI commands
- Programmatic compliance gate remains authoritative; skill is complementary agent guidance
- Skill loading failure logs warning and proceeds without skill — does not block execution

### Defensive Exclusions
- NO changes to `deviate init` or constitution provisioning
- NO changes to context sync or AGENTS.md alignment
- NO changes to profile enum itself (already shipped in SHARD-001)
- NO changes to the session state machine transitions
- NO removal of existing test infrastructure or regression test behavior
- `--confirm` flag for tasks.jsonl append — no automatic merge
- NO changes to AgentBackend real backend invocation logic — StubBackend is additive
- NO changes to TamperGuard or micro-sandboxing enforcement
- NO changes to existing `green_pre`/`yellow_pre` contract schemas — skills read existing contracts
- StubAgentBackend returns same `HandoverManifest` schema as real backends
- Test refactoring preserves existing coverage — contract testing (args, env vars) not implementation details
- YELLOW skill is agent-facing guidance, not human workflow requirement

## PERFORMANCE_CONSTRAINTS

- `CacheDiscipline.validate()` must complete in L_max <= 5ms per invocation
- `RollbackSnapshot` serialization must complete in L_max <= 2ms
- `_find_task_record()` latest-record resolution must complete in L_max <= 1ms
- `generate_jsonl_from_md()` must process a 200-line `tasks.md` in L_max <= 100ms
- `tasks post --confirm` full proposal cycle must complete in L_max <= 200ms (excluding user confirmation delay)
- `_run_yellow_phase()` helper (no agent invocation) must complete in L_max <= 10ms for the session/ledger transition logic
- Skill rewrites: zero regression in training mode — all 18 skills load within existing startup budget

## MULTI_TIERED_VERIFICATION_TARGETS

**Cache Discipline**
- `tests/test_core/test_cache_discipline.py` — `test_cache_discipline_model_switch`, `test_cache_discipline_tool_change`, `test_cache_discipline_phase_boundary`

**YELLOW Handoff Contract (GREEN → YELLOW → JUDGE)**
- `tests/test_cli/test_green.py` — `test_green_post_tamper_detected_transitions_to_yellow`, `test_green_post_tamper_pass_stays_green`, `test_green_post_yellow_triggered_by_tamper_not_commit`
- `tests/test_cli/test_yellow.py` — `test_yellow_post_approved_transitions_to_judge`, `test_yellow_post_rejected_transitions_to_green`, `test_yellow_appends_status_transition`
- `tests/test_micro/test_orchestration.py` — `test_tdd_cycle_inlines_yellow_gate`, `test_tdd_cycle_yellow_approved_continues_to_judge`, `test_tdd_cycle_yellow_rejected_re_runs_green`, `test_yellow_not_in_phase_map`, `test_run_yellow_phase_helper_returns_decision`
- `tests/test_micro/test_run.py` — `test_run_resumes_from_session_phase`, `test_run_resumes_from_yellow`, `test_run_resumes_from_judge`

**Train Rollback — All Commits Since RED**
- `tests/test_cli/test_micro.py` — `test_judge_train_rollback_all_commits_since_red`, `test_judge_rollback_preserves_red`, `test_judge_no_violation_proceeds`
- `tests/test_state/test_ledger.py` — `test_rollback_snapshot_model`, `test_rollback_snapshot_sha_validation`, `test_rollback_snapshot_tracks_red_boundary`

**Stale PENDING Record Resolution**
- `tests/test_cli/test_micro.py` — `test_find_task_record_returns_latest_status`, `test_find_task_record_multiple_entries_returns_last`
- `tests/test_micro/test_run.py` — `test_task_already_done_triggers_for_re_run_tasks`

**Ledger and Status Model**
- `tests/test_state/test_ledger.py` — `test_task_record_status_includes_yellow`, `test_task_record_status_includes_judge`, `test_task_record_status_includes_yellow_approved`, `test_task_record_status_includes_yellow_rejected`
- `tests/test_cli/test_micro.py` — `test_judge_appends_status_transition`, `test_green_post_appends_yellow_on_tamper`

**Tasks Ledger**
- `tests/test_core/test_tasks_ledger.py` — `test_generate_jsonl_from_md`, `test_validate_tasks_jsonl`
- `tests/test_cli/test_meso.py` — `test_tasks_post_proposal`, `test_tasks_post_confirm`

**Skills Audit**
- `tests/test_skills/` — grep-based audit for `.sh`/`--no-judge`/`--no-refactor` in skill files

**Agent & Mock Boundary**
- `tests/test_core/test_agent.py` — `test_stub_backend_returns_valid_manifest`, `test_stub_backend_no_subprocess`
- `tests/test_micro/conftest.py` — audit autouse mock targets `subprocess.Popen` not `_invoke_agent`

**Test Refactoring (system-edge mocks)**
- `tests/test_micro/test_red.py` — refactored: uses `subprocess.Popen` mock, no `_run_pytest` mock
- `tests/test_micro/test_green.py` — refactored: uses `subprocess.Popen` mock, no `_run_pytest` mock
- `tests/test_micro/test_refactor.py` — refactored: uses `subprocess.Popen` mock, no `_run_pytest` mock

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-CACHE: Cache Discipline Enforcement

* **Upstream Requirement Traceability**: FR-007

**Scenario 1: Model change between RED and GREEN triggers violation**
**Given** a TDD cycle is in progress with `CacheDiscipline` active
**When** the model changes between RED phase invocation and GREEN phase invocation
**Then** `CacheDiscipline.validate()` raises `CacheDisciplineViolation` with reason matching `model_switch`

**Scenario 2: Tool definition change mid-cycle triggers violation**
**Given** a TDD cycle is in progress with `CacheDiscipline` active
**When** a tool definition changes between any two consecutive phases
**Then** `CacheDiscipline.validate()` raises `CacheDisciplineViolation` with reason matching `tool_change`

**Scenario 3: No changes pass validation**
**Given** a TDD cycle is in progress with `CacheDiscipline` active
**When** model and tool definitions remain unchanged across phase boundaries
**Then** `CacheDiscipline.validate()` returns without error

**Scenario 4: CacheDiscipline hooks into every phase boundary**
**Given** `_run_tdd_cycle()` is executing
**When** each phase function (`_run_red_phase`, `_run_green_phase`, `_run_yellow_phase`, `_run_judge_phase`, `_run_refactor_phase`) completes
**Then** `CacheDiscipline.validate()` is invoked before the next phase begins

### US-002-YELMAN: YELLOW Handoff — Manual green_post

* **Upstream Requirement Traceability**: FR-018, FR-008

**Scenario 1: Tamper pass stays green**
**Given** `green_post` runs after a GREEN implementation
**When** `TamperGuard.evaluate() == TAMPER_PASS`
**Then** session transitions to GREEN
**And** ledger appends GREEN status
**And** YELLOW is NOT triggered
**And** the next expected phase is JUDGE

**Scenario 2: Tamper detected transitions to YELLOW**
**Given** `green_post` runs after a GREEN implementation
**When** `TamperGuard.evaluate() == TAMPER_DETECTED`
**Then** session transitions to YELLOW (not GREEN)
**And** ledger appends GREEN then YELLOW status
**And** `YELLOW_TRIGGERED` is printed as a deliberate routing signal

**Scenario 3: YELLOW_TRIGGERED driven by TamperGuard, not _commit_phase**
**Given** `green_post` executes
**When** `_commit_phase` returns `False` (tree clean from TamperGuard restore)
**Then** `YELLOW_TRIGGERED` is NOT emitted unless `TamperGuard.evaluate() == TAMPER_DETECTED`

**Scenario 4: yellow_post --approved transitions to JUDGE**
**Given** the session is in YELLOW phase
**When** `deviate yellow post --approved` is executed
**Then** session transitions to JUDGE (not GREEN)
**And** ledger appends `YELLOW_APPROVED` status

**Scenario 5: yellow_post --rejected transitions back to GREEN**
**Given** the session is in YELLOW phase
**When** `deviate yellow post --rejected` is executed
**Then** `git restore .` is run
**And** session transitions to GREEN
**And** ledger appends `YELLOW_REJECTED` status

### US-003-YELAUTO: YELLOW as Conditional Branch — Auto Cycle

* **Upstream Requirement Traceability**: FR-018

**Scenario 1: YELLOW is NOT in _PHASE_MAP**
**Given** the `_PHASE_MAP` dictionary at `micro.py:345`
**When** inspected
**Then** it MUST NOT contain a `"YELLOW"` key
**And** YELLOW logic lives in a separate `_run_yellow_phase()` helper, not in `_PHASE_MAP`

**Scenario 2: _run_tdd_cycle inlines TamperGuard between GREEN and JUDGE**
**Given** `_run_tdd_cycle()` executes
**When** the GREEN phase completes
**Then** `TamperGuard.evaluate(GREEN_IMPLEMENTATION)` is called before entering JUDGE phase
**And** the TamperGuard gate is part of the cycle loop body, not `_PHASE_MAP`

**Scenario 3: Approved YELLOW continues to JUDGE**
**Given** `_run_tdd_cycle()` executes
**When** TamperGuard detects tampering AND `_run_yellow_phase()` returns `approved`
**Then** the cycle continues to `_run_judge_phase()`

**Scenario 4: Rejected YELLOW re-runs GREEN**
**Given** `_run_tdd_cycle()` executes
**When** TamperGuard detects tampering AND `_run_yellow_phase()` returns `rejected`
**Then** `_run_green_phase()` is re-executed
**And** the cycle then proceeds to JUDGE from the re-implementation

**Scenario 5: _run_tdd_cycle accepts start_phase parameter**
**Given** `_run_tdd_cycle()` is defined
**When** called with an optional `start_phase` parameter
**Then** execution begins from that phase instead of RED

**Scenario 6: _run_single resumes from session.current_phase**
**Given** `_run_single()` is invoked
**When** `session.current_phase` is YELLOW, JUDGE, or REFACTOR
**Then** execution resumes from that phase (does NOT restart from PENDING)

**Scenario 7: _run_yellow_phase helper returns (session, decision)**
**Given** `_run_yellow_phase()` is invoked
**When** it completes
**Then** it returns a tuple of `(SessionState, str)` where the string is `"approved"` or `"rejected"`

### US-004-ROLLBACK: JUDGE Train Rollback — All Commits Since RED

* **Upstream Requirement Traceability**: FR-008

**Scenario 1: Violation triggers revert of all commits since RED**
**Given** JUDGE phase detects `COMPLIANCE_VIOLATION`
**When** `_run_judge_phase()` executes rollback
**Then** `git revert --no-edit <red_sha>..HEAD` is executed (reverts all commits between the RED boundary and HEAD)
**And** a `RollbackSnapshot` is persisted with `phase="JUDGE"`, `branch`, `commit_sha` (red boundary), and `reason`
**And** judge feedback is injected
**And** execution is re-routed to GREEN phase

**Scenario 2: No violation proceeds normally**
**Given** JUDGE phase runs
**When** no compliance violation is detected
**Then** no `git revert` is executed
**And** no `RollbackSnapshot` is created
**And** execution proceeds to REFACTOR phase

**Scenario 3: RollbackSnapshot model enforces extra=forbid**
**Given** the `RollbackSnapshot` model in `state/ledger.py`
**When** instantiated
**Then** any unknown field raises a validation error (`extra = "forbid"`)
**And** required fields include `phase`, `branch`, `commit_sha`, `reason`

### US-005-SKILLS: Skill Files & Ledger Rewrites

* **Upstream Requirement Traceability**: FR-012, FR-013

**Scenario 1: No .sh references in any SKILL.md**
**Given** all SKILL.md files under `src/deviate/prompts/skills/`
**When** scanned for `.sh` patterns
**Then** zero files contain `.sh` references
**And** all use `deviate <cmd> pre/post` syntax

**Scenario 2: All skill files use --profile instead of --no-judge/--no-refactor**
**Given** all SKILL.md files under `src/deviate/prompts/skills/`
**When** scanned for `--no-judge` and `--no-refactor` flags
**Then** zero files contain these flags
**And** all use `--profile <name>` for training mode selection

**Scenario 3: tasks post without --confirm creates proposal only**
**Given** `tasks post` is run without `--confirm`
**When** `tasks.md` exists with valid task definitions
**Then** a `.jsonl.proposal` file is created
**And** `tasks.jsonl` is NOT modified

**Scenario 4: tasks post --confirm appends and removes proposal**
**Given** `tasks post --confirm` is run with a valid `.jsonl.proposal` present
**When** the confirmation flag is provided
**Then** the proposal content is appended to `tasks.jsonl`
**And** the `.jsonl.proposal` file is removed

### US-006-MOCK: System-Edge Mock Boundary

* **Upstream Requirement Traceability**: FR-017

**Scenario 1: StubAgentBackend returns valid HandoverManifest without subprocess**
**Given** `StubAgentBackend` is instantiated
**When** `invoke("test prompt")` is called
**Then** it returns a valid `HandoverManifest` with `phase="RED"` and `status="success"`
**And** no subprocess is spawned

**Scenario 2: conftest.py patches subprocess.Popen, not _invoke_agent**
**Given** `tests/test_micro/conftest.py`
**When** inspected for autouse fixture mock targets
**Then** the mock patches `subprocess.Popen`
**And** does NOT patch `deviate.cli.micro._invoke_agent`

**Scenario 3: Integration test with stub asserts Popen CLI args**
**Given** an integration test using `agent="stub"`
**When** the test invokes the CLI
**Then** it asserts that `subprocess.Popen` was called with correct CLI args, env vars, and stdin

### US-007-YELSKILL: YELLOW Phase Skill

* **Upstream Requirement Traceability**: FR-018

**Scenario 1: deviate-yellow SKILL.md exists**
**Given** the file `src/deviate/prompts/skills/deviate-yellow/SKILL.md`
**When** checked for existence
**Then** it exists with a review/amend workflow

**Scenario 2: _SKILL_NAMES["YELLOW"] resolves to "deviate-yellow"**
**Given** `_SKILL_NAMES` dictionary in `micro.py`
**When** accessed with key `"YELLOW"`
**Then** the value is `"deviate-yellow"`

**Scenario 3: yellow_pre and yellow_post load YELLOW skill content**
**Given** `yellow_pre` or `yellow_post` CLI handler executes
**When** invoked
**Then** `_load_skill_content("YELLOW")` is called

### US-008-JUDSKILL: JUDGE Phase Skill & Ledger

* **Upstream Requirement Traceability**: FR-019

**Scenario 1: deviate-judge SKILL.md exists**
**Given** the file `src/deviate/prompts/skills/deviate-judge/SKILL.md`
**When** checked for existence
**Then** it exists with a compliance evaluation workflow

**Scenario 2: _SKILL_NAMES["JUDGE"] resolves to "deviate-judge"**
**Given** `_SKILL_NAMES` dictionary in `micro.py`
**When** accessed with key `"JUDGE"`
**Then** the value is `"deviate-judge"` (not `None`)

**Scenario 3: _run_judge_phase loads JUDGE skill content**
**Given** `_run_judge_phase()` executes
**When** invoked
**Then** `_load_skill_content("JUDGE")` is called

**Scenario 4: _run_judge_phase appends JUDGE status transition**
**Given** `_run_judge_phase()` executes to completion
**When** the phase ends (whether violation or not)
**Then** `_append_status_transition(task, "JUDGE", ledger_path)` is called

**Scenario 5: TaskRecord.status accepts YELLOW and JUDGE as valid values**
**Given** `TaskRecord.status` Literal type
**When** assigned values `"YELLOW"`, `"JUDGE"`, `"YELLOW_APPROVED"`, or `"YELLOW_REJECTED"`
**Then** the assignment is valid (no validation error)

### US-009-STALE: Stale PENDING Record Resolution

* **Upstream Requirement Traceability**: FR-019 (ledger integrity)

**Scenario 1: _find_task_record returns last matching record**
**Given** a ledger with multiple status records for the same task ID (e.g., PENDING at index 0, GREEN at index 3)
**When** `_find_task_record(task_id, ledger_path)` is called
**Then** it returns the record at the LAST occurrence (GREEN), not the first (PENDING)

**Scenario 2: Task already done guard triggers for re-run tasks**
**Given** a task with a completed status record (GREEN, JUDGE, or COMPLETED) as the latest entry
**When** `_run_single()` is invoked for that task
**Then** the `TASK_ALREADY_DONE` guard in `_run_single` (`micro.py:437`) triggers and prevents re-execution

### US-010-HITL: HITL Decision Integration

* **Upstream Requirement Traceability**: FR-008, FR-019

**Scenario 1: Train rollback reverts all commits since RED boundary (HITL)**
**Given** JUDGE detects a compliance violation
**When** rollback executes
**Then** the revert command targets all commits from `<red_sha>..HEAD` (not a single GREEN SHA)
**And** `RollbackSnapshot` stores both `red_sha` and `green_sha` for audit traceability

**Scenario 2: _find_task_record resolution verified across task lifecycle**
**Given** a task with records: `[PENDING, RED, GREEN, YELLOW, YELLOW_APPROVED, JUDGE]`
**When** `_find_task_record` is called
**Then** it returns the record with `status="JUDGE"` (the latest)
**And** calling again after a `COMPLETED` append returns `status="COMPLETED"`

## SYSTEM_STATUS_SUMMARY

| Parameter | Value |
|-----------|-------|
| STATUS | READY_FOR_TASKS |
| EPIC_SLUG | 002-deviatdd-gap-analysis |
| BRANCH_NAME | feat/002-deviatdd-gap-analysis/005-micro-layer-integrity |
| SPEC_PATH | specs/002-deviatdd-gap-analysis/005-micro-layer-integrity/spec.md |
| ISSUE_ID | ISS-002-005 |
| NEXT_ACTION | /deviate-tasks — decompose spec.md into granular Red-Green-Refactor task units |
