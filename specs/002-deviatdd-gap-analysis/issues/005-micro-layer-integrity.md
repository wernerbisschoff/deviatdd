---
title: Micro-Layer Integrity — Cache Discipline, Train Rollback, Skill Action Logic, Tasks Ledger Separation
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

## [THE_PROBLEM_CONTRACT]

**User Journey**: During a TDD cycle, the agent model changes between RED and GREEN phases — `CacheDiscipline.validate()` at the GREEN phase boundary detects the change and raises `CacheDisciplineViolation`, halting the cycle. When JUDGE detects a `COMPLIANCE_VIOLATION`, it executes `git revert --no-edit <green_sha>` to safely roll back, logs a `RollbackSnapshot` to `.deviate/rollback.jsonl`, injects judge feedback, and re-routes to GREEN. After `tasks post`, a `.jsonl.proposal` file is created, requiring `--confirm` to append to `tasks.jsonl`. All 18 SKILL.md files use `deviate <subcommand> pre/post` with `--profile` instead of boolean flags and `.sh` scripts.

**System Response**: CacheDiscipline enforces model/tool/prompt/test-file continuity at dispatch level. Train rollback uses `git revert` (never `--hard`) with precise SHA tracking. Tasks ledger uses proposal + `--confirm` pattern per Append-Only Protocol. Skills rewritten in dependency order from simplest to most complex.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `CacheDiscipline` class with 4 rules: no model switching, no tool def changes, no system prompt mutation, no read-only test file conversation append
- Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries
- JUDGE `_run_judge_phase()`: on `COMPLIANCE_VIOLATION` → `RollbackSnapshot` → `git revert --no-edit <green_sha>` → inject feedback → re-route to GREEN
- `RollbackSnapshot` model in `state/ledger.py` with `extra = "forbid"`
- `tasks post`: parse `tasks.md` → `.jsonl.proposal` → requires `--confirm` to append to `tasks.jsonl`
- 18 SKILL.md rewrites: replace flags, remove `.sh` refs, use `deviate <cmd> pre/post`
- Rewrite skills in dependency order (simplest → most complex)

### Defensive Exclusions
- NO changes to `deviate init` or constitution provisioning
- NO changes to context sync or AGENTS.md alignment
- NO changes to profile enum itself (already shipped in SHARD-001)
- NO changes to the session state machine transitions
- NO removal of existing test infrastructure or regression test behavior
- `--confirm` flag for tasks.jsonl append — no automatic merge

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-007 | Cache Discipline Enforcement Module | FR-007-CacheDiscipline |
| FR-008 | JUDGE Train Rollback | FR-008-TrainRollback |
| FR-012 | Skill File Rewrites | FR-012-SkillActionLogic |
| FR-013 | tasks.md vs tasks.jsonl Separation | FR-013-TasksLedgerSeparation |

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

### Data Model Entities
- `CacheEntry`, `CacheStore` — `src/deviate/core/cache_discipline.py`
- `RollbackSnapshot` — `src/deviate/state/ledger.py`
- `TaskLedgerBatch` — `src/deviate/core/tasks_ledger.py`
- `CacheStore` — `src/deviate/core/cache_discipline.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_core/test_cache_discipline.py` — `test_cache_discipline_model_switch`, `test_cache_discipline_tool_change`, `test_cache_discipline_phase_boundary`
- `tests/test_cli/test_micro.py` — `test_judge_train_rollback`, `test_judge_rollback_preserves_red`, `test_judge_no_violation_proceeds`
- `tests/test_state/test_ledger.py` — `test_rollback_snapshot_model`, `test_rollback_snapshot_sha_validation`
- `tests/test_core/test_tasks_ledger.py` — `test_generate_jsonl_from_md`, `test_validate_tasks_jsonl`
- `tests/test_cli/test_meso.py` — `test_tasks_post_proposal`, `test_tasks_post_confirm`
- `tests/test_skills/` — grep-based audit for `.sh`/`--no-judge`/`--no-refactor` in skill files

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

# Run verification tests
pytest tests/test_core/test_cache_discipline.py tests/test_cli/test_micro.py tests/test_core/test_tasks_ledger.py tests/test_cli/test_meso.py -v --no-header -q
```
