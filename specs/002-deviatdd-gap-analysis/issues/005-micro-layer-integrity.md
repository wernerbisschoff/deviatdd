---
title: Micro-Layer Integrity — FULL TDD Phase Model (RED → GREEN → YELLOW? → JUDGE → REFACTOR), Train Rollback, Skill Rewrites, Tasks Ledger Separation, TDD Mock Boundary, YELLOW/JUDGE Skills
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-004"]
coordinates_with: []
issue_id: ISS-002-005
epic_id: ISS-002
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/005-micro-layer-integrity.md`
- **Workstation Paths**:
  - `src/deviate/core/cache_discipline.py` — NEW: `CacheDiscipline` class with 4 validation rules
  - `src/deviate/cli/micro.py` — MODIFY: hook `CacheDiscipline.validate()` at phase boundaries, implement JUDGE train rollback with `git revert`, add `"YELLOW": "deviate-yellow"` and `"JUDGE": "deviate-judge"` to `_SKILL_NAMES`
  - `src/deviate/state/ledger.py` — MODIFY: add `RollbackSnapshot` model, add `YELLOW`/`JUDGE` to `TaskRecord.status` Literal
  - `src/deviate/core/tasks_ledger.py` — NEW: `generate_jsonl_from_md()`, `validate_tasks_jsonl()`
  - `src/deviate/cli/meso.py` — MODIFY: `tasks post` generates `.jsonl.proposal`, requires `--confirm`
  - `src/deviate/prompts/skills/deviate-*/SKILL.md` — MODIFY: 18 files, replace `--no-judge`/`--no-refactor` with `--profile`, remove `.sh` refs, use `deviate <cmd> pre/post`
  - `src/deviate/core/agent.py` — MODIFY: add `StubAgentBackend` class + `"stub"` entry in `BACKEND_COMMANDS` (FR-017)
  - `tests/test_micro/conftest.py` — MODIFY: replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock (FR-017)
  - `tests/test_micro/test_red.py`, `test_green.py`, `test_refactor.py`, `test_orchestration.py` — MODIFY: remove `_run_pytest` function-level mocks, use system-edge subprocess assertions (FR-017)
  - `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — MODIFY: add integration/wiring guidance to decision tree step 7 (FR-017)
  - `src/deviate/prompts/skills/deviate-yellow/SKILL.md` — NEW: YELLOW phase skill with review/amend workflow (FR-018)
  - `src/deviate/cli/micro.py` — MODIFY: wire `_load_skill_content("YELLOW")` into `yellow_pre`/`yellow_post` CLI handlers (FR-018)
  - `src/deviate/prompts/skills/deviate-judge/SKILL.md` — NEW: JUDGE phase skill with compliance evaluation workflow (FR-019)
  - `src/deviate/cli/micro.py` — MODIFY: replace `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"`, wire `_load_skill_content("JUDGE")` into `_run_judge_phase()` and judge CLI commands (FR-019)

## [THE_PROBLEM_CONTRACT]

### Phase Handoff Contract — The YELLOW Decision Tree

The core question this issue must resolve: **How does YELLOW get invoked, how does `green_post` decide YELLOW must run next, and how does `deviate run` route to YELLOW instead of JUDGE?**

There are three distinct invocation pathways. Each is currently broken or missing.

---

#### Pathway 1: Manual CLI — `deviate green post` → YELLOW handoff

**Current behavior** (`micro.py:693-755`):
1. Runs `_run_pytest()` — tests must pass or `green_post` errors out at line 724
2. Runs `TamperGuard.evaluate(TamperContext.GREEN_IMPLEMENTATION)` — line 726-728
3. If `TAMPER_DETECTED` → **prints `[yellow]TAMPER_DETECTED[/]`** but **does nothing else** (line 730-731, no session change, no ledger change, no flow guard)
4. Appends GREEN to ledger — line 734-740
5. Transitions session to **GREEN** — line 742-743 (always, regardless of tampering)
6. Commits. If nothing to commit, prints `[yellow]YELLOW_TRIGGERED[/]` — line 753 (this is a bug: the message fires when `_commit_phase` returns `False` because TamperGuard already restored files, NOT as a deliberate routing signal)

**Bug**: `YELLOW_TRIGGERED` at line 753 is NOT the same as "YELLOW phase should run now". It's an incidental side-effect of `_commit_phase` returning `False` when TamperGuard restored everything. The session is still in GREEN. The ledger shows GREEN. There is no automatic routing to YELLOW.

`yellow_post --approved` (`micro.py:835-838`): transitions session to **GREEN** — this is wrong. After a successfully approved YELLOW amendment, the next expected phase is JUDGE (not GREEN). The session should transition to JUDGE.

**Desired behavior**:
```
deviate green post
  → run pytest (pass required)
  → TamperGuard.evaluate(GREEN_IMPLEMENTATION)
  → if TAMPER_PASS:
      session → GREEN, ledger ← GREEN, print "GREEN_POST_OK", proceed to JUDGE
  → if TAMPER_DETECTED:
      session → GREEN → append GREEN to ledger
      session → YELLOW ← TRANSITION TO YELLOW
      ledger ← YELLOW(PENDING) ← signal for next phase
      print "YELLOW_TRIGGERED — run 'deviate yellow post --approved' or --rejected"
      exit (do NOT proceed to JUDGE)

deviate yellow post --approved:
  → commit amendments
  → session → JUDGE ← not GREEN!
  → ledger ← YELLOW(APPROVED)
  → next deviate run picks up JUDGE phase

deviate yellow post --rejected:
  → git restore .
  → session → GREEN ← revert to GREEN for re-do
  → ledger ← YELLOW(REJECTED)
  → next deviate run picks up GREEN phase for re-implementation
```

---

#### Pathway 2: Auto cycle — `deviate run` / `_run_tdd_cycle()`

**Current behavior** (`micro.py:345-379`):
- `_PHASE_MAP = {"RED": _run_red_phase, "GREEN": _run_green_phase, "JUDGE": _run_judge_phase, "REFACTOR": _run_refactor_phase}`
- No YELLOW entry in `_PHASE_MAP`
- `_run_green_phase` (line 262-282) runs NO TamperGuard check — it only transitions session + optionally invokes agent
- Cycle is rigid: RED → GREEN → JUDGE → REFACTOR — no conditional branching

**Desired behavior**:
The decision tree must be embedded in the cycle loop:

```
_run_tdd_cycle():
  session = RED   (append RED)
  session = GREEN (append GREEN)

  if TamperGuard.evaluate(GREEN_IMPLEMENTATION) == TAMPER_DETECTED:
      session = YELLOW (append YELLOW)
      agent invokes YELLOW skill → agent produces approved/rejected decision
      if approved:
          session = JUDGE (append YELLOW_APPROVED)
      if rejected:
          session = GREEN (append YELLOW_REJECTED)
          # cycle back: user/agent re-does implementation
          session = GREEN (append GREEN again)
          session = JUDGE (append JUDGE)

  session = JUDGE   (append JUDGE)
  if COMPLIANCE_VIOLATION:
      git revert → RollbackSnapshot → session = GREEN → re-run from GREEN
  session = REFACTOR (append REFACTOR)
  session = COMPLETED
```

This means `_PHASE_MAP` must become dynamic or the cycle loop must inline the YELLOW branch:

```python
def _run_tdd_cycle(...):
    session = _run_red_phase(...)
    session = _run_green_phase(...)

    # YELLOW gate — inline decision, not a _PHASE_MAP entry
    tamper = TamperGuard.evaluate(TamperContext.GREEN_IMPLEMENTATION, repo_path=root)
    if tamper == TamperVerdict.TAMPER_DETECTED:
        session = _run_yellow_phase(...)  # NEW helper
        # yellow_phase returns (session, decision)
        if decision == "rejected":
            session = _run_green_phase(...)  # re-enter GREEN
        # fall through to JUDGE

    session = _run_judge_phase(...)
    session = _run_refactor_phase(...)
    # COMPLETED...
```

YELLOW is explicitly NOT in `_PHASE_MAP` because it's a conditional branch, not a fixed phase. The gate lives in the loop body between GREEN and JUDGE.

---

#### Pathway 3: Session-state-based resumable routing

When `deviate run` is invoked without arguments (picks next task from session), or when `_run_single()` is invoked after a phase boundary, the session state determines what phase runs next:

**Current behavior**:
- `_resolve_task_context(None, root)` → finds first PENDING task from ledger → dispatches to `_run_tdd_cycle()` which always starts from RED
- No mechanism for "resume from YELLOW" or "resume from JUDGE"
- Session phase is consulted only for validation in `transition_to()` — not for dispatch routing

**Desired behavior**:
```python
def _run_single(task_id, root, ...):
    result = _resolve_task_context(task_id, root)
    task, ledger_file = result
    status = task.get("status", "PENDING")

    # NEW: check session for resumable phase
    session = SessionState.load(session_path)
    if session.current_phase in ("YELLOW", "JUDGE", "REFACTOR"):
        # Resume from where we left off instead of restarting
        _resume_cycle_from(session.current_phase, task, ...)
        return
    ...
```

This requires:
- Session state to persist across `deviate run` invocations (already done)
- `_run_tdd_cycle` to accept a `start_phase` parameter (NEW)
- After each manual CLI command, the next `deviate run` reads the session phase and runs the correct remaining phases

---

### Current Gaps Summary

| Gap | Location | Impact |
|-----|----------|--------|
| `green_post` doesn't transition to YELLOW on tamper detect | `micro.py:730-731` | Session stays at GREEN, no routing signal to next `deviate run` |
| `YELLOW_TRIGGERED` is a misleading side-effect of `_commit_phase` returning False | `micro.py:753` | Not an actual YELLOW routing signal |
| `_PHASE_MAP` has no YELLOW entry | `micro.py:345` | Auto cycle can never run YELLOW |
| `_run_green_phase` doesn't run TamperGuard | `micro.py:262-282` | No tamper detection in auto cycle at all |
| `yellow_post --approved` transitions to GREEN instead of JUDGE | `micro.py:837` | Session state contradicts next expected phase |
| `TaskRecord.status` lacks YELLOW and JUDGE | `ledger.py:63` | Can't record YELLOW/JUDGE in ledger — no idempotency key for transitions |
| `_run_judge_phase` doesn't append status transition | `micro.py:285-319` | JUDGE transitions invisible in ledger |
| `_run_single` has no session-phase resume logic | `micro.py:425-449` | Can't resume from YELLOW/JUDGE/REFACTOR — always restarts from PENDING |

### Status enum gap
`TaskRecord.status` (`ledger.py:63`) only allows `PENDING | RED | GREEN | REFACTOR | COMPLETED | FAILED`. Missing `YELLOW` and `JUDGE`. This means `_run_judge_phase()` and `yellow_pre`/`yellow_post` can't append status transitions — those phases are invisible in the task ledger.

### Stale PENDING records
The ledger is append-only — completed task records are never removed. `_find_all_pending_tasks()` (`micro.py:159`) matches ANY record with `status == "PENDING"`, including the original PENDING record for already-completed tasks. `_find_task_record()` (`micro.py:150`) returns the FIRST record by ID (the PENDING one), not the latest status — so the `TASK_ALREADY_DONE` guard in `_run_single` (`micro.py:437`) never triggers for re-run tasks.

### Other known gaps
- **FR-017 Mock boundary**: Tests mock `_invoke_agent` at the function boundary (`conftest.py:16-17`), leaving agent subprocess wiring untested per `plan-tdd-integration-gap.md:7-14`
- **FR-018/FR-019 Skill gaps**: YELLOW has CLI commands but no `deviate-yellow` skill; JUDGE has `_SKILL_NAMES['JUDGE'] = None` at `micro.py:42`
- **Train rollback**: JUDGE on `COMPLIANCE_VIOLATION` should execute `git revert --no-edit <green_sha>`, log `RollbackSnapshot`, re-route to GREEN — currently no wallet tracking for the green SHA
- **CacheDiscipline**: Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries to prevent model/tool/prompt drift

**System Response**: CacheDiscipline enforces model/tool/prompt/test-file continuity at dispatch level. The TDD cycle runs RED → GREEN → [TamperGuard gate → YELLOW?] → JUDGE → REFACTOR → COMPLETED. YELLOW is NOT in `_PHASE_MAP` — it's a conditional branch between GREEN and JUDGE in the cycle loop body. JUDGE ("Train") is automatic — on `COMPLIANCE_VIOLATION`, `git revert` (never `--hard`) with precise SHA tracking (`plan-tdd-integration-gap.md:308-314`). Both `TaskRecord.status` and `_append_status_transition` must support `YELLOW` and `JUDGE` as first-class status values so ledger reflects every phase transition. Tasks ledger uses proposal + `--confirm` pattern per Append-Only Protocol. Skills rewritten in dependency order from simplest to most complex per adversarial finding R08. `StubAgentBackend` provides deterministic test backend without subprocess overhead (`plan-tdd-integration-gap.md:86-109`). Tests mock at `subprocess.Popen` system edge instead of `_invoke_agent` — asserting CLI args, env vars, and stdin content (`plan-tdd-integration-gap.md:57-74`). Wire-code tasks typed as TDD with `Mock Boundary` metadata field (`plan-tdd-integration-gap.md:184-204`). Test refactoring focuses on contract testing (args, env vars) not implementation details (`plan-tdd-integration-gap.md:324-327`). `deviate-yellow` and `deviate-judge` skills added to `_SKILL_NAMES` with proper model routing (V4 Pro for compliance per constitution).

## [SCOPE_BOUNDARIES]

### Hard Inclusions

**Cache Discipline and Phase Boundaries**
- `CacheDiscipline` class with 4 rules: no model switching, no tool def changes, no system prompt mutation, no read-only test file conversation append
- Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries

**YELLOW Handoff Contract (GREEN → [YELLOW?] → JUDGE)**
- `green_post` at `micro.py:693`: on `TamperGuard.evaluate() == TAMPER_DETECTED`, the session **must transition to YELLOW** (not GREEN) and the ledger **must append a YELLOW entry**. Currently it only prints a warning and stays at GREEN — this is the primary YELLOW handoff bug.
- `green_post` YELLOW_TRIGGERED message at `micro.py:753`: this is a side-effect bug — the message fires when `_commit_phase` returns `False` because TamperGuard restored files, making the tree clean. Replace with explicit `if tamper_verdict == TAMPER_DETECTED: session → YELLOW; return`
- `_run_tdd_cycle()` at `micro.py:353`: add a **TamperGuard gate in the cycle body** between the GREEN phase and JUDGE phase. This is NOT a `_PHASE_MAP` entry — YELLOW is a conditional branch:
  ```python
  session = _run_green_phase(...)
  if TamperGuard.evaluate(GREEN_IMPLEMENTATION) == TAMPER_DETECTED:
      session, decision = _run_yellow_phase(...)
      if decision == "rejected":
          session = _run_green_phase(...)  # re-do GREEN
  session = _run_judge_phase(...)
  ```
- `yellow_post --approved` at `micro.py:837`: transition session to **JUDGE** (not GREEN). After YELLOW is approved, JUDGE is the next expected phase in the cycle.
- `yellow_post --rejected` at `micro.py:843`: transition session to **GREEN** (correct — YELLOW rejected means re-do the implementation). This is already correct.
- `_run_tdd_cycle` must accept a `start_phase` parameter for session-resume mode (Pathway 3): when `deviate run` picks up after a manual CLI command, it resumes from the session's `current_phase` instead of RED.

**Ledger and Status Model**
- Expand `TaskRecord.status` Literal in `ledger.py:63` from `PENDING | RED | GREEN | REFACTOR | COMPLETED | FAILED` to include `YELLOW` and `JUDGE`
- Add `YELLOW_APPROVED` and `YELLOW_REJECTED` to `TaskRecord.status` Literal (or use a separate `resolution` field)
- `_run_judge_phase()`: add `_append_status_transition(task, "JUDGE", ledger_path)` — JUDGE transitions must be recorded in the task ledger (not just session state)
- `green_post`: add `_append_status_transition(task, "YELLOW", ledger_path)` when TamperGuard detects tampering
- `yellow_post`: append `YELLOW_APPROVED` or `YELLOW_REJECTED` to ledger

**Train Rollback**
- JUDGE `_run_judge_phase()`: on `COMPLIANCE_VIOLATION` → `RollbackSnapshot` → `git revert --no-edit <green_sha>` → inject feedback → re-route to GREEN
- `RollbackSnapshot` model in `state/ledger.py` with `extra = "forbid"`
- Must track the GREEN commit SHA so `git revert` targets the correct commit

**Tasks Ledger and Skills**
- `tasks post`: parse `tasks.md` → `.jsonl.proposal` → requires `--confirm` to append to `tasks.jsonl`
- 18 SKILL.md rewrites: replace flags, remove `.sh` refs, use `deviate <cmd> pre/post`, in dependency order
- `StubAgentBackend` class in `src/deviate/core/agent.py` with `"stub"` entry in `BACKEND_COMMANDS`
- `conftest.py`: replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock
- Test files: remove `_run_pytest` function-level mocks; use system-edge mocks; assert `Popen` call args (CLI, env, stdin) not function-call assertions
- `deviate-tasks` SKILL.md: add step 7: "Does this task connect/wire already-tested components via subprocess, API, or message passing? → TDD with system-edge mock boundary"
- `deviate-yellow` SKILL.md: NEW skill with review/amend workflow — `yellow_pre` emits `YELLOWSkillManifest`, agent evaluates amendments, `yellow_post --approved` commits, `--rejected` runs `git restore .`
- `_SKILL_NAMES["YELLOW"] = "deviate-yellow"` in `micro.py`
- Wire `_load_skill_content("YELLOW")` into `yellow_pre`/`yellow_post` CLI handlers
- `deviate-judge` SKILL.md: NEW skill with compliance evaluation workflow — reads `JUDGESkillManifest`, verifies git diff against spec.md invariants
- Replace `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"`
- Wire `_load_skill_content("JUDGE")` into `_run_judge_phase()` and judge CLI commands
- Programmatic compliance gate remains authoritative — skill is complementary agent guidance
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
- NO changes to existing green_pre/yellow_pre contract schemas — skills read existing JSON contracts
- StubAgentBackend returns same `HandoverManifest` schema as real backends — E2E task with real backend validates divergence (`plan-tdd-integration-gap.md:308-314`)
- Test refactoring preserves existing coverage — contract testing (args, env vars) not implementation details (`plan-tdd-integration-gap.md:324-327`)
- YELLOW skill is agent-facing guidance, not human workflow requirement
- JUDGE programmatic compliance is authoritative; skill is complementary

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-007 | Cache Discipline Enforcement Module | FR-007-CacheDiscipline |
| FR-008 | JUDGE Train Rollback | FR-008-TrainRollback |
| FR-012 | Skill File Rewrites | FR-012-SkillActionLogic |
| FR-013 | tasks.md vs tasks.jsonl Separation | FR-013-TasksLedgerSeparation |
| FR-017 | TDD Integration Mock Boundary | FR-017-TDDMockBoundary |
| FR-018 | YELLOW Phase Skill | FR-018-YELLOWSkill |
| FR-019 | JUDGE Phase Skill | FR-019-JUDGESkill |

### Acceptance Criteria

**Cache Discipline**
| ID | Description | Source |
|----|-------------|--------|
| AC-007-01 | Model change between RED and GREEN triggers `CacheDisciplineViolation` | PRD FR-007 |
| AC-007-02 | Tool definition change mid-cycle triggers `CacheDisciplineViolation` | PRD FR-007 |

**YELLOW Handoff Contract**
| ID | Description | Source |
|----|-------------|--------|
| AC-YEL-01 | `green_post` with `TamperGuard.evaluate() == TAMPER_PASS` → session=GREEN, ledger=GREEN, no YELLOW | This issue |
| AC-YEL-02 | `green_post` with `TamperGuard.evaluate() == TAMPER_DETECTED` → session=YELLOW, ledger=GREEN+YELLOW, prints YELLOW_TRIGGERED | This issue |
| AC-YEL-03 | `green_post` YELLOW_TRIGGERED is driven by TamperGuard verdict, not by `_commit_phase` return value (fix the line-753 bug) | This issue |
| AC-YEL-04 | `yellow_post --approved` → session=JUDGE (not GREEN), ledger=YELLOW_APPROVED | This issue |
| AC-YEL-05 | `yellow_post --rejected` → session=GREEN, ledger=YELLOW_REJECTED, `git restore .` | This issue |

**TDD Auto Cycle (deviate run)**
| ID | Description | Source |
|----|-------------|--------|
| AC-CYC-01 | `_PHASE_MAP` does NOT include YELLOW — YELLOW is a conditional branch, not a fixed phase | This issue |
| AC-CYC-02 | `_run_tdd_cycle()` inlines TamperGuard check between GREEN and JUDGE phase calls | This issue |
| AC-CYC-03 | `_run_tdd_cycle()` with TamperGuard TAMPER_DETECTED → runs YELLOW helper → if approved, continues to JUDGE; if rejected, re-runs GREEN | This issue |
| AC-CYC-04 | `_run_tdd_cycle()` accepts optional `start_phase` parameter for session-resume mode | This issue |
| AC-CYC-05 | `_run_single()` checks `session.current_phase` and resumes from YELLOW/JUDGE/REFACTOR instead of restarting from RED | This issue |

**Train Rollback**
| ID | Description | Source |
|----|-------------|--------|
| AC-008-01 | JUDGE detects violation → `git revert --no-edit <green_sha>` → `RollbackSnapshot` → feedback → GREEN re-route | PRD FR-008 |
| AC-008-02 | Non-violating JUDGE proceeds to REFACTOR without snapshot | PRD FR-008 |

**Skills and Ledger**
| ID | Description | Source |
|----|-------------|--------|
| AC-012-01 | No `.sh` references in any SKILL.md; all use `deviate <cmd> pre/post` | PRD FR-012 |
| AC-012-02 | All skill files use `--profile [full\|fast\|secure]` instead of `--no-judge`/`--no-refactor` | PRD FR-012 |
| AC-013-01 | `tasks post` without `--confirm` creates `.jsonl.proposal`, does NOT modify `tasks.jsonl` | PRD FR-013 |
| AC-013-02 | `tasks post --confirm` with valid proposal appends to `tasks.jsonl`, removes proposal | PRD FR-013 |
| AC-017-01 | `StubAgentBackend.invoke("test prompt")` returns valid `HandoverManifest` with `phase="RED"`, `status="success"` without subprocess | PRD FR-017 + plan:86-109 |
| AC-017-02 | `conftest.py` autouse fixture patches `subprocess.Popen` (not `deviate.cli.micro._invoke_agent`) | PRD FR-017 + plan:42-54 |
| AC-017-03 | Integration test with `agent="stub"` asserts `subprocess.Popen` called with correct CLI args, env vars, stdin | PRD FR-017 + plan:57-74 |
| AC-017-04 | `deviate-tasks` SKILL.md decision tree includes step 7 for integration/wiring code | PRD FR-017 + plan:184-204 |
| AC-018-01 | `deviate-yellow` SKILL.md exists at `prompts/skills/deviate-yellow/SKILL.md` with review/amend workflow | PRD FR-018 |
| AC-018-02 | `_SKILL_NAMES["YELLOW"]` resolves to `"deviate-yellow"` | PRD FR-018 |
| AC-018-03 | `yellow_pre`/`yellow_post` invoke `_load_skill_content("YELLOW")` | PRD FR-018 |
| AC-019-01 | `deviate-judge` SKILL.md exists at `prompts/skills/deviate-judge/SKILL.md` with compliance workflow | PRD FR-019 |
| AC-019-02 | `_SKILL_NAMES["JUDGE"]` resolves to `"deviate-judge"` (not `None`) | PRD FR-019 |
| AC-019-03 | `_run_judge_phase()` and judge CLI commands invoke `_load_skill_content("JUDGE")` | PRD FR-019 |
| AC-019-04 | `_run_judge_phase()` appends `JUDGE` status transition to task ledger | This issue |
| AC-019-05 | `TaskRecord.status` Literal accepts `YELLOW` and `JUDGE` as valid values | This issue |

### Data Model Entities
- `CacheEntry`, `CacheStore` — `src/deviate/core/cache_discipline.py`
- `RollbackSnapshot` — `src/deviate/state/ledger.py`
- `TaskLedgerBatch` — `src/deviate/core/tasks_ledger.py`
- `StubAgentBackend` — `src/deviate/core/agent.py`
- `YELLOWSkillManifest` — transient contract emitted by `yellow_pre`
- `JUDGESkillManifest` — transient contract emitted by `judge_pre`

## [MULTI_TIERED_VERIFICATION_TARGETS]

**Cache Discipline**
- `tests/test_core/test_cache_discipline.py` — `test_cache_discipline_model_switch`, `test_cache_discipline_tool_change`, `test_cache_discipline_phase_boundary`

**YELLOW Handoff Contract (GREEN → YELLOW → JUDGE)**
- `tests/test_cli/test_green.py` — `test_green_post_tamper_detected_transitions_to_yellow`, `test_green_post_tamper_pass_stays_green`, `test_green_post_yellow_triggered_by_tamper_not_commit`
- `tests/test_cli/test_yellow.py` — `test_yellow_post_approved_transitions_to_judge`, `test_yellow_post_rejected_transitions_to_green`, `test_yellow_appends_status_transition`
- `tests/test_micro/test_orchestration.py` — `test_tdd_cycle_inlines_yellow_gate`, `test_tdd_cycle_yellow_approved_continues_to_judge`, `test_tdd_cycle_yellow_rejected_re_runs_green`, `test_yellow_not_in_phase_map`
- `tests/test_micro/test_run.py` — `test_run_resumes_from_session_phase`, `test_run_resumes_from_yellow`, `test_run_resumes_from_judge`

**Train Rollback**
- `tests/test_cli/test_micro.py` — `test_judge_train_rollback`, `test_judge_rollback_preserves_red`, `test_judge_no_violation_proceeds`

**Ledger and Status Model**
- `tests/test_state/test_ledger.py` — `test_rollback_snapshot_model`, `test_rollback_snapshot_sha_validation`
- `tests/test_state/test_ledger.py` — `test_task_record_status_includes_yellow`, `test_task_record_status_includes_judge`
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
- `tests/test_micro/test_red.py` — refactored: uses system-edge mock (`subprocess.Popen`), no `_run_pytest` mock
- `tests/test_micro/test_green.py` — refactored: uses system-edge mock, no `_run_pytest` mock
- `tests/test_micro/test_refactor.py` — refactored: uses system-edge mock, no `_run_pytest` mock

## [DEMONSTRATION_PATH]

```bash
# ===== YELLOW HANDOFF CONTRACT VERIFICATION =====

# Verify green_post TamperGuard decision tree: tamper→YELLOW, clean→GREEN
uv run python -c "
import json
from pathlib import Path
# Read green_post logic and verify TamperGuard gate
with open('src/deviate/cli/micro.py') as f:
    content = f.read()
# Check that green_post transitions to YELLOW on TAMPER_DETECTED
assert 'session.force_transition_to(\"YELLOW\")' in content or \
       'session = session.force_transition_to(\"YELLOW\")' in content, \
       'green_post must transition session to YELLOW when tampering is detected'
print('green_post YELLOW transition OK')
"

# Verify yellow_post --approved transitions to JUDGE (not GREEN)
uv run python -c "
with open('src/deviate/cli/micro.py') as f:
    content = f.read()
import re
# Find the --approved handler in yellow_post
approved_block = content[content.find('if approved:'):content.find('if approved:')+300]
assert 'force_transition_to(\"JUDGE\")' in approved_block or \
       'force_transition_to(\"JUDGE\")' in content, \
       'yellow_post --approved must transition to JUDGE'
print('yellow_post --approved -> JUDGE OK')
"

# Verify _run_tdd_cycle inlines TamperGuard gate between GREEN and JUDGE
uv run python -c "
with open('src/deviate/cli/micro.py') as f:
    content = f.read()
# The cycle should have a conditional YELLOW branch between GREEN and JUDGE
has_tamper_gate = 'TamperGuard' in content and 'GREEN_IMPLEMENTATION' in content
has_yellow_helper = '_run_yellow_phase' in content or 'yellow_phase' in content
if has_tamper_gate and has_yellow_helper:
    print('_run_tdd_cycle TamperGuard gate OK')
else:
    print('WARNING: _run_tdd_cycle missing TamperGuard YELLOW gate')
"

# Verify YELLOW is NOT in _PHASE_MAP (conditional branch, not fixed phase)
python3 -c "
with open('src/deviate/cli/micro.py') as f:
    content = f.read()
import re
# Check _PHASE_MAP dict doesn't include YELLOW
phase_map = re.search(r'_PHASE_MAP\s*=\s*\{([^}]+)\}', content)
if phase_map:
    map_content = phase_map.group(1)
    if 'YELLOW' not in map_content:
        print('YELLOW not in _PHASE_MAP OK')
    else:
        print('WARNING: YELLOW found in _PHASE_MAP')
else:
    print('WARNING: Could not find _PHASE_MAP')
"

# ===== EXISTING VERIFICATIONS =====

# Verify cache discipline model switch detection
uv run python -c "
from deviate.core.cache_discipline import CacheDiscipline, CacheDisciplineViolation
try:
    CacheDiscipline.validate(phase='GREEN', model='deepseek-v4-flash', previous_model='deepseek-v4-pro')
    print('FAIL: should have raised')
except CacheDisciplineViolation as e:
    print(f'Cache discipline OK: {e}')
"

# Verify rollback snapshot model
uv run python -c "
from deviate.state.ledger import RollbackSnapshot
snap = RollbackSnapshot(phase='JUDGE', branch='main', commit_sha='a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0', reason='violation')
print(f'RollbackSnapshot OK: {snap.commit_sha[:8]}...')
"

# Verify tasks.jsonl proposal pattern
uv run python -c "
from pathlib import Path
proposal = Path('.deviate/tasks.jsonl.proposal')
proposal.write_text('{\"test\": true}\n')
assert proposal.exists()
proposal.unlink()
print('Proposal pattern OK')
"

# Verify StubAgentBackend returns valid manifest without subprocess
uv run python -c "
from deviate.core.agent import StubAgentBackend
stub = StubAgentBackend()
result = stub.invoke('test prompt')
print(f'StubBackend OK: phase={result.phase}, status={result.status}')
assert result.phase == 'RED'
assert result.status == 'success'
"

# Verify YELLOW skill exists and is registered
ls src/deviate/prompts/skills/deviate-yellow/SKILL.md 2>/dev/null && echo 'YELLOW skill OK' || echo 'WARNING: YELLOW skill missing'
grep -q '\"YELLOW\": \"deviate-yellow\"' src/deviate/cli/micro.py && echo 'YELLOW _SKILL_NAMES OK' || echo 'WARNING: YELLOW not in _SKILL_NAMES'

# Verify JUDGE skill exists and is registered
ls src/deviate/prompts/skills/deviate-judge/SKILL.md 2>/dev/null && echo 'JUDGE skill OK' || echo 'WARNING: JUDGE skill missing'
grep -q '\"JUDGE\": \"deviate-judge\"' src/deviate/cli/micro.py && echo 'JUDGE _SKILL_NAMES OK' || echo 'WARNING: JUDGE still None in _SKILL_NAMES'

# Verify conftest mocks subprocess.Popen not _invoke_agent
grep -q 'subprocess.Popen' tests/test_micro/conftest.py && echo 'System-edge mock OK' || echo 'WARNING: conftest still mocks _invoke_agent'

# Verify no stale shell references in skills
! grep -r '\.sh' src/deviate/prompts/skills/ --include='SKILL.md' && echo 'No .sh references OK' || echo 'WARNING: .sh references found'

# Verify STUB entry in BACKEND_COMMANDS
grep -q '\"stub\":' src/deviate/core/agent.py && echo 'Stub backend registered OK' || echo 'WARNING: stub not in BACKEND_COMMANDS'

# Verify TaskRecord.status accepts YELLOW and JUDGE
uv run python -c "
from deviate.state.ledger import TaskRecord
try:
    r = TaskRecord(id='TSK-001-01', issue_id='ISS-001', description='test', status='YELLOW')
    print(f'YELLOW status OK: {r.status}')
except Exception as e:
    print(f'WARNING: YELLOW status rejected: {e}')
try:
    r = TaskRecord(id='TSK-001-01', issue_id='ISS-001', description='test', status='JUDGE')
    print(f'JUDGE status OK: {r.status}')
except Exception as e:
    print(f'WARNING: JUDGE status rejected: {e}')
"

# Run verification tests
pytest tests/test_cli/test_yellow.py tests/test_micro/test_orchestration.py tests/test_micro/test_run.py tests/test_core/test_cache_discipline.py tests/test_core/test_agent.py tests/test_state/test_ledger.py -v --no-header -q
```
