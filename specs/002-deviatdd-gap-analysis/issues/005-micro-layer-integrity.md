---
title: Micro-Layer Integrity — Cache Discipline, Train Rollback, Skill Action Logic, Tasks Ledger Separation, TDD Mock Boundary, YELLOW/JUDGE Skills
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-004"]
coordinates_with: []
issue_id: ISS-002-005
epic_id: ISS-002
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/005-micro-layer-integrity.md`
- **Workstation Paths**:
  - `src/deviate/core/cache_discipline.py` — NEW: `CacheDiscipline` class with 4 validation rules
  - `src/deviate/cli/micro.py` — MODIFY: hook `CacheDiscipline.validate()` at phase boundaries, implement JUDGE train rollback with `git revert`
  - `src/deviate/state/ledger.py` — MODIFY: add `RollbackSnapshot` model
  - `src/deviate/core/tasks_ledger.py` — NEW: `generate_jsonl_from_md()`, `validate_tasks_jsonl()`
  - `src/deviate/cli/meso.py` — MODIFY: `tasks post` generates `.jsonl.proposal`, requires `--confirm`
  - `src/deviate/prompts/skills/deviate-*/SKILL.md` — MODIFY: 18 files, replace `--no-judge`/`--no-refactor` with `--profile`, remove `.sh` refs, use `deviate <cmd> pre/post`
  - `src/deviate/core/agent.py` — MODIFY: add `StubAgentBackend` class + `"stub"` entry in `BACKEND_COMMANDS` (#17)
  - `tests/test_micro/conftest.py` — MODIFY: replace `_invoke_agent` mock with `subprocess.Popen` system-edge mock (#17)
  - `tests/test_micro/test_red.py`, `test_green.py`, `test_refactor.py` — MODIFY: remove `_run_pytest` function-level mocks (#17)
  - `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — MODIFY: add integration/wiring guidance to decision tree (step 7) (#17)
  - `src/deviate/prompts/skills/deviate-yellow/SKILL.md` — NEW: YELLOW phase skill with review/amend workflow (#18)
  - `src/deviate/cli/micro.py` — MODIFY: add `"YELLOW": "deviate-yellow"` to `_SKILL_NAMES`; wire skill into `yellow_pre`/`yellow_post` (#18)
  - `src/deviate/prompts/skills/deviate-judge/SKILL.md` — NEW: JUDGE phase skill with compliance evaluation workflow (#19)
  - `src/deviate/cli/micro.py` — MODIFY: replace `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"`; wire skill into `_run_judge_phase` and judge CLI commands (#19)

## [THE_PROBLEM_CONTRACT]

**User Journey**: During a TDD cycle, the agent model changes between RED and GREEN phases — `CacheDiscipline.validate()` at the GREEN phase boundary detects the change and raises `CacheDisciplineViolation`, halting the cycle. When JUDGE detects a `COMPLIANCE_VIOLATION`, it executes `git revert --no-edit <green_sha>` to safely roll back, logs a `RollbackSnapshot` to `.deviate/rollback.jsonl`, injects judge feedback, and re-routes to GREEN. After `tasks post`, a `.jsonl.proposal` file is created, requiring `--confirm` to append to `tasks.jsonl`. All 18 SKILL.md files use `deviate <subcommand> pre/post` with `--profile` instead of boolean flags and `.sh` scripts. Tests currently mock `_invoke_agent` at the function boundary (`conftest.py:16-17`), leaving all agent subprocess wiring untested — the TDD integration gap from `plan-tdd-integration-gap.md:7-14`. The YELLOW phase has CLI commands but no `deviate-yellow` skill in `_SKILL_NAMES` — agents cannot be guided through amendment review. The JUDGE phase has `_SKILL_NAMES['JUDGE'] = None` (`micro.py:42`) — the constitutional V4 Pro tiering mandate goes unfulfilled.

**System Response**: CacheDiscipline enforces model/tool/prompt/test-file continuity at dispatch level. Train rollback uses `git revert` (never `--hard`) with precise SHA tracking. Tasks ledger uses proposal + `--confirm` pattern per Append-Only Protocol. Skills rewritten in dependency order from simplest to most complex. `StubAgentBackend` provides deterministic test backend without subprocess overhead. Tests mock at `subprocess.Popen` system edge instead of `_invoke_agent`. `deviate-yellow` and `deviate-judge` skills added to `_SKILL_NAMES` with proper model routing (V4 Pro for compliance per constitution).

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `CacheDiscipline` class with 4 rules: no model switching, no tool def changes, no system prompt mutation, no read-only test file conversation append
- Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries
- JUDGE `_run_judge_phase()`: on `COMPLIANCE_VIOLATION` → `RollbackSnapshot` → `git revert --no-edit <green_sha>` → inject feedback → re-route to GREEN
- `RollbackSnapshot` model in `state/ledger.py` with `extra = "forbid"`
- `tasks post`: parse `tasks.md` → `.jsonl.proposal` → requires `--confirm` to append to `tasks.jsonl`
- 18 SKILL.md rewrites: replace flags, remove `.sh` refs, use `deviate <cmd> pre/post`
- Rewrite skills in dependency order (simplest → most complex)
- `StubAgentBackend` class in `src/deviate/core/agent.py` with `"stub"` entry in `BACKEND_COMMANDS` (#17)
- `conftest.py`: replace autouse `_invoke_agent` mock with `subprocess.Popen` system-edge mock (#17)
- Test files: remove `_run_pytest` function-level mocks; use system-edge mocks (#17)
- `deviate-tasks` SKILL.md: add integration/wiring guidance to decision tree (#17)
- `deviate-yellow` SKILL.md: NEW skill with review/amend workflow (#18)
- `_SKILL_NAMES["YELLOW"] = "deviate-yellow"` in `micro.py` (#18)
- Wire `_load_skill_content("YELLOW")` into `yellow_pre`/`yellow_post` CLI handlers (#18)
- `deviate-judge` SKILL.md: NEW skill with compliance evaluation workflow (#19)
- Replace `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"` (#19)
- Wire `_load_skill_content("JUDGE")` into `_run_judge_phase()` and judge CLI commands (#19)

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
| ID | Description |
|----|-------------|
| AC-007-01 | Model change between RED and GREEN triggers `CacheDisciplineViolation` |
| AC-007-02 | Tool definition change mid-cycle triggers `CacheDisciplineViolation` |
| AC-008-01 | JUDGE detects violation → `git revert --no-edit <green_sha>` → `RollbackSnapshot` → feedback → GREEN re-route |
| AC-008-02 | Non-violating JUDGE proceeds to REFACTOR without snapshot |
| AC-012-01 | No `.sh` references in any SKILL.md; all use `deviate <cmd> pre/post` |
| AC-012-02 | All skill files use `--profile [full|fast|secure]` instead of `--no-judge`/`--no-refactor` |
| AC-013-01 | `tasks post` without `--confirm` creates `.jsonl.proposal`, does NOT modify `tasks.jsonl` |
| AC-013-02 | `tasks post --confirm` with valid proposal appends to `tasks.jsonl`, removes proposal |
| AC-017-01 | `StubAgentBackend.invoke()` returns valid `HandoverManifest` without subprocess |
| AC-017-02 | `conftest.py` autouse mock patches `subprocess.Popen`, not `_invoke_agent` |
| AC-017-03 | Integration tests assert `subprocess.Popen` was called with correct CLI args, env, stdin |
| AC-017-04 | `deviate-tasks` SKILL.md decision tree includes step 7 for integration/wiring code |
| AC-018-01 | `deviate-yellow` SKILL.md exists at `prompts/skills/deviate-yellow/SKILL.md` |
| AC-018-02 | `_SKILL_NAMES["YELLOW"]` resolves to `"deviate-yellow"` |
| AC-018-03 | `yellow_pre`/`yellow_post` invoke `_load_skill_content("YELLOW")` |
| AC-019-01 | `deviate-judge` SKILL.md exists at `prompts/skills/deviate-judge/SKILL.md` |
| AC-019-02 | `_SKILL_NAMES["JUDGE"]` resolves to `"deviate-judge"` (not `None`) |
| AC-019-03 | `_run_judge_phase()` invokes `_load_skill_content("JUDGE")` with agent prompt |

### Data Model Entities
- `CacheEntry`, `CacheStore` — `src/deviate/core/cache_discipline.py`
- `RollbackSnapshot` — `src/deviate/state/ledger.py`
- `TaskLedgerBatch` — `src/deviate/core/tasks_ledger.py`
- `CacheStore` — `src/deviate/core/cache_discipline.py`
- `StubAgentBackend` — `src/deviate/core/agent.py` (new)
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
- `tests/test_micro/test_red.py` — refactored: `test_red_post_validates_test_fails` uses system-edge mock
- `tests/test_micro/test_green.py` — refactored: `test_green_post_validates_tests_pass` uses system-edge mock
- `tests/test_micro/test_refactor.py` — refactored: `test_refactor_post_test_invariance` uses system-edge mock
- `tests/test_micro/test_yellow.py` — `test_yellow_skill_loaded`, `test_yellow_pre_emits_manifest`, `test_yellow_post_approved`
- `tests/test_micro/test_judge.py` — `test_judge_skill_loaded`, `test_judge_pre_emits_manifest`, `test_judge_post_compliance`

## [DEMONSTRATION_PATH]

```bash
# Verify cache discipline model switch detection
uv run python -c "
from deviate.core.cache_discipline import CacheDiscipline
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
# Simulate proposal generation
from pathlib import Path
proposal = Path('.deviate/tasks.jsonl.proposal')
proposal.write_text('{\"test\": true}\n')
assert proposal.exists()
proposal.unlink()
print('Proposal pattern OK')
"

# Verify no stale shell references in skills
! grep -r '\.sh' src/deviate/prompts/skills/ --include='SKILL.md' && echo 'No .sh references OK' || echo 'WARNING: .sh references found'

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
grep -q '"YELLOW": "deviate-yellow"' src/deviate/cli/micro.py && echo 'YELLOW _SKILL_NAMES OK' || echo 'WARNING: YELLOW not in _SKILL_NAMES'

# Verify JUDGE skill exists and is registered
ls src/deviate/prompts/skills/deviate-judge/SKILL.md 2>/dev/null && echo 'JUDGE skill OK' || echo 'WARNING: JUDGE skill missing'
grep -q '"JUDGE": "deviate-judge"' src/deviate/cli/micro.py && echo 'JUDGE _SKILL_NAMES OK' || echo 'WARNING: JUDGE still None in _SKILL_NAMES'

# Verify conftest mocks subprocess.Popen not _invoke_agent
grep -q 'subprocess.Popen' tests/test_micro/conftest.py && echo 'System-edge mock OK' || echo 'WARNING: conftest still mocks _invoke_agent'

# Run verification tests
pytest tests/test_core/test_cache_discipline.py tests/test_core/test_agent.py tests/test_cli/test_micro.py tests/test_cli/test_meso.py tests/test_micro/test_yellow.py tests/test_micro/test_judge.py -v --no-header -q
```
