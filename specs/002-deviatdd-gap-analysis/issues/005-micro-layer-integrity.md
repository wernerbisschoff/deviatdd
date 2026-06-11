---
title: Micro-Layer Integrity — Cache Discipline, Train Rollback, Skill Rewrites, Tasks Ledger Separation, TDD Mock Boundary, YELLOW/JUDGE Skills
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
  - `src/deviate/state/ledger.py` — MODIFY: add `RollbackSnapshot` model
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

**User Journey**: During a TDD cycle, the agent model changes between RED and GREEN phases — `CacheDiscipline.validate()` at the GREEN phase boundary detects the change and raises `CacheDisciplineViolation`, halting the cycle. When JUDGE detects a `COMPLIANCE_VIOLATION`, it executes `git revert --no-edit <green_sha>` to safely roll back, logs a `RollbackSnapshot` to `.deviate/rollback.jsonl`, injects judge feedback, and re-routes to GREEN. After `tasks post`, a `.jsonl.proposal` file is created, requiring `--confirm` to append to `tasks.jsonl`. All 18 SKILL.md files use `deviate <subcommand> pre/post` with `--profile` instead of boolean flags and `.sh` scripts.

**Integration Gap (FR-017)**: Tests currently mock `_invoke_agent` at the function boundary (`conftest.py:16-17`), leaving all agent subprocess wiring untested. Per `plan-tdd-integration-gap.md:7-14`, this means the TDD cycle satisfies the test by ensuring the mock is called, but the actual critical-path `subprocess.Popen` invocation code inside `AgentBackend.invoke()` is never driven by a failing test. The fix per `plan-tdd-integration-gap.md:42-54`: push mock boundary to the system edge (`subprocess.Popen`), introduce `StubAgentBackend` for deterministic testing, and ensure all integration/wiring tasks are typed as TDD (not IMMEDIATE).

**Skill Gap (FR-018/FR-019)**: The YELLOW phase has CLI commands but no `deviate-yellow` skill in `_SKILL_NAMES` — agents cannot be guided through amendment review (`micro.py:39-44`). The JUDGE phase has `_SKILL_NAMES['JUDGE'] = None` (`micro.py:42`) — the constitutional V4 Pro tiering mandate (`specs/constitution.md §[1_ARCHITECTURAL_PRINCIPLES]`) goes unfulfilled. After Tamper Guard detection at `micro.py:753`, YELLOW is triggered but no skill guides the agent. `_run_judge_phase()` performs compliance checking without loading a skill.

**System Response**: CacheDiscipline enforces model/tool/prompt/test-file continuity at dispatch level. Train rollback uses `git revert` (never `--hard`) with precise SHA tracking (`plan-tdd-integration-gap.md:308-314`). Tasks ledger uses proposal + `--confirm` pattern per Append-Only Protocol. Skills rewritten in dependency order from simplest to most complex per adversarial finding R08. `StubAgentBackend` provides deterministic test backend without subprocess overhead (`plan-tdd-integration-gap.md:86-109`). Tests mock at `subprocess.Popen` system edge instead of `_invoke_agent` — asserting CLI args, env vars, and stdin content (`plan-tdd-integration-gap.md:57-74`). Wire-code tasks typed as TDD with `Mock Boundary` metadata field (`plan-tdd-integration-gap.md:184-204`). Test refactoring focuses on contract testing (args, env vars) not implementation details (`plan-tdd-integration-gap.md:324-327`). `deviate-yellow` and `deviate-judge` skills added to `_SKILL_NAMES` with proper model routing (V4 Pro for compliance per constitution).

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `CacheDiscipline` class with 4 rules: no model switching, no tool def changes, no system prompt mutation, no read-only test file conversation append
- Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries
- JUDGE `_run_judge_phase()`: on `COMPLIANCE_VIOLATION` → `RollbackSnapshot` → `git revert --no-edit <green_sha>` → inject feedback → re-route to GREEN
- `RollbackSnapshot` model in `state/ledger.py` with `extra = "forbid"`
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
| ID | Description | Source |
|----|-------------|--------|
| AC-007-01 | Model change between RED and GREEN triggers `CacheDisciplineViolation` | PRD FR-007 |
| AC-007-02 | Tool definition change mid-cycle triggers `CacheDisciplineViolation` | PRD FR-007 |
| AC-008-01 | JUDGE detects violation → `git revert --no-edit <green_sha>` → `RollbackSnapshot` → feedback → GREEN re-route | PRD FR-008 |
| AC-008-02 | Non-violating JUDGE proceeds to REFACTOR without snapshot | PRD FR-008 |
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

### Data Model Entities
- `CacheEntry`, `CacheStore` — `src/deviate/core/cache_discipline.py`
- `RollbackSnapshot` — `src/deviate/state/ledger.py`
- `TaskLedgerBatch` — `src/deviate/core/tasks_ledger.py`
- `StubAgentBackend` — `src/deviate/core/agent.py`
- `YELLOWSkillManifest` — transient contract emitted by `yellow_pre`
- `JUDGESkillManifest` — transient contract emitted by `judge_pre`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_core/test_cache_discipline.py` — `test_cache_discipline_model_switch`, `test_cache_discipline_tool_change`, `test_cache_discipline_phase_boundary`
- `tests/test_cli/test_micro.py` — `test_judge_train_rollback`, `test_judge_rollback_preserves_red`, `test_judge_no_violation_proceeds`
- `tests/test_state/test_ledger.py` — `test_rollback_snapshot_model`, `test_rollback_snapshot_sha_validation`
- `tests/test_core/test_tasks_ledger.py` — `test_generate_jsonl_from_md`, `test_validate_tasks_jsonl`
- `tests/test_cli/test_meso.py` — `test_tasks_post_proposal`, `test_tasks_post_confirm`
- `tests/test_skills/` — grep-based audit for `.sh`/`--no-judge`/`--no-refactor` in skill files
- `tests/test_core/test_agent.py` — `test_stub_backend_returns_valid_manifest`, `test_stub_backend_no_subprocess`
- `tests/test_micro/conftest.py` — audit autouse mock targets `subprocess.Popen` not `_invoke_agent`
- `tests/test_micro/test_red.py` — refactored: uses system-edge mock (`subprocess.Popen`), no `_run_pytest` mock
- `tests/test_micro/test_green.py` — refactored: uses system-edge mock, no `_run_pytest` mock
- `tests/test_micro/test_refactor.py` — refactored: uses system-edge mock, no `_run_pytest` mock
- `tests/test_micro/test_yellow.py` — `test_yellow_skill_loaded`, `test_yellow_pre_emits_manifest`, `test_yellow_post_approved`, `test_yellow_post_rejected`
- `tests/test_micro/test_judge.py` — `test_judge_skill_loaded`, `test_judge_pre_emits_manifest`, `test_judge_post_compliance`

## [DEMONSTRATION_PATH]

```bash
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

# Run verification tests
pytest tests/test_core/test_cache_discipline.py tests/test_core/test_agent.py tests/test_core/test_tasks_ledger.py tests/test_micro/test_yellow.py tests/test_micro/test_judge.py -v --no-header -q
```
