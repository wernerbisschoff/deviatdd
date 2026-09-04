## Plan Summary
- **Issue**: ISS-ADH-040 — JUDGE rollback must never remove tasks.md from the feature branch
- **Implementation Strategy**: Clamp the JUDGE rollback boundary to at or after the commit that created `tasks.md`, and refuse the reset with a plain error when no safe boundary resolves.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Rollback keeps tasks.md on the active branch**
- **Source Outline**: `AO-040-01`
- **Upstream Traceability**: `US-040-01`, `FR-ADHOC-040`, `AC-ADHOC-040-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A feature branch holds committed `tasks.md` plus RED and GREEN commits
- **When**: JUDGE fires a rollback and then commits feedback
- **Then**: `git ls-tree -r HEAD --name-only` still lists `tasks.md` at its latest committed state
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Unsafe rollback refuses without touching the branch**
- **Source Outline**: `AO-040-02`
- **Upstream Traceability**: `US-040-01`, `FR-ADHOC-040`, `AC-ADHOC-040-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: The resolved rollback boundary predates the commit that created `tasks.md`
- **When**: JUDGE attempts the rollback
- **Then**: The runner raises a plain error before any reset and leaves branch, index, and untracked files unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Meso run after rollback reuses existing Tasks**
- **Source Outline**: `AO-040-01`
- **Upstream Traceability**: `US-040-01`, `FR-ADHOC-040`, `AC-ADHOC-040-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_commit_judge_feedback_and_advance`
- **Given**: A rollback completed while `tasks.md` stayed on the branch
- **When**: The operator runs meso after the rollback
- **Then**: Meso sees the existing Tasks and does not regenerate them
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Prior recovery refs stay reachable after rollback**
- **Source Outline**: `AO-040-02`
- **Upstream Traceability**: `US-040-01`, `FR-ADHOC-040`, `AC-ADHOC-040-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_preserve_agent_work`
- **Given**: Prior JUDGE attempts stored per-attempt recovery refs
- **When**: A later rollback runs or refuses
- **Then**: All prior recovery refs remain resolvable and no ref is overwritten
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Owns the rollback boundary and reset in this issue — clamp the boundary at or after the `tasks.md` commit and refuse unsafe resets
  - **Current State**: `_execute_rollback` resets to any ancestor boundary and checks only ancestry, so a pre-Tasks baseline truncates `tasks.md`
  - **Changes Required**: Resolve the commit that created `tasks.md` on the active branch, advance any older boundary to it, refuse when no safe boundary resolves, keep recovery-ref and snapshot behavior unchanged
  - **Integration Surface**: `_resolve_revert_red_boundary`, `_require_revert_green_boundary`, `_planned_revert_anchor`, JUDGE verdict handlers, `RollbackSnapshot` ledger append
- **tests/unit/test_micro/test_rollback_safety.py**: Pins the rollback contract — needs new cases for this issue
  - **Current State**: Covers explicit boundary and per-attempt recovery refs on fixture repos
  - **Changes Required**: Add failing-then-passing cases for boundary predating `tasks.md` refused and `tasks.md` present after rollback
  - **Integration Surface**: `_execute_rollback`, git fixture helpers, `_git_env`

## Implementation Strategy
- **Phase 1**: Clamp rollback boundary to the tasks.md commit and refuse unsafe resets
  - **Files**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_rollback_safety.py`
  - **Approach**: Add a helper that resolves the `tasks.md`-creating commit on the active branch via git log, advance any boundary older than it, raise a plain `PhaseFailedError` before any reset when no safe boundary resolves, and leave the uncommitted-or-absent `tasks.md` path on the existing behavior
  - **Verification**: New unit cases pass, `mise run check` passes, manual fixture run shows `git ls-tree HEAD` listing `tasks.md` after a JUDGE revert verdict

## Data Flow Analysis
- Input: JUDGE verdict with action and stored RED boundary plus the active branch history containing the `tasks.md` commit. Transform: resolve the `tasks.md` commit, compare boundary ancestry against it, either advance the boundary or refuse. Output: safe `git reset --hard` to the clamped boundary plus feedback commit, or an unchanged branch with a plain error. Storage: per-attempt recovery refs and existing `RollbackSnapshot` records unchanged.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Boundary clamp misresolves on amended or rebased history | High | Medium | Keep the existing `ROLLBACK_STALE_BOUNDARY` ancestry refusal and refuse when the safe commit is not an ancestor |
| `tasks.md` lookup adds slow git calls to every rollback | Low | Low | Run one log query per rollback inside the 5000ms overhead budget with no retry loop |
| Feedback commit path diverges from clamped reset | Medium | Low | Reuse the existing feedback commit step unchanged after the clamped reset |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: boundary predating tasks.md refuses before reset, branch and untracked files unchanged on refusal
Constraints: no new dependencies, no new ledger event types, GREEN/RED/REFACTOR and Gate 3 flows untouched

## Integration Points
- **JUDGE verdict handlers**: Callers pass resolved boundaries into `_execute_rollback` and commit feedback after the reset
- **`RollbackSnapshot` ledger**: Existing append-only snapshot records keep their shape and ordering
- **Meso Tasks reader**: Sees the preserved `tasks.md` after rollback and skips regeneration

## Constitutional Alignment
- **Architecture**: Micro-layer fix inside RED → GREEN → JUDGE → REFACTOR, no layer skipped, Gate 2 stays removed per §1
- **Testing**: pytest under `tests/unit/test_micro`, RED-first unit cases plus fixture integration run, `mise run check` gate per §3
- **Git Isolation**: All rollback work stays on the dedicated issue branch, commits at phase boundaries per §1 and §4
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-004` encode `US-040-01` plus the ATDD outlines `AO-040-01` and `AO-040-02`; RED turns those into failing tests
