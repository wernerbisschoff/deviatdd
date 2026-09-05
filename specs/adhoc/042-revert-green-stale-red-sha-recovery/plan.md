## Plan Summary
- **Issue**: ISS-ADH-042 — revert_green recovers from a stale RED boundary instead of raising ROLLBACK_STALE_RED_SHA
- **Implementation Strategy**: Extend `_require_revert_green_boundary` to reuse the existing RED-anchor classification (`rewritten`, `already_reverted`) plus a tasks.md-safe fallback, so stale stored SHAs resolve to an on-branch boundary and only truly unresolvable SHAs refuse.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Stale RED SHA with rewritten RED on train remaps and resets GREEN work**
- **Source Outline**: `AO-042-01`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_green_boundary`
- **Given**: Stored `red_commit_sha` is off-branch after a train rebase and a same-subject RED commit sits on HEAD
- **When**: JUDGE routes `revert_green` for the task
- **Then**: The runner remaps to the rewritten RED SHA, logs `RED_SHA_REWRITTEN` with old and new SHA, and resets GREEN work to that boundary
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Stored SHA still an ancestor of HEAD keeps exact current behavior**
- **Source Outline**: `AO-042-01`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_red_anchor_kind`
- **Given**: Stored `red_commit_sha` is an ancestor of HEAD
- **When**: JUDGE routes `revert_green` for the task
- **Then**: The runner returns the stored SHA unchanged with no remap log and no behavior change
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Unresolvable stored SHA refuses with plain error and leaves branch unchanged**
- **Source Outline**: `AO-042-01`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_is_fatal_missing_revert_green_boundary`
- **Given**: Stored `red_commit_sha` is off-branch with no rewritten RED and no safe on-branch fallback
- **When**: JUDGE routes `revert_green` for the task
- **Then**: The runner raises a plain refusal error, performs no reset, and leaves HEAD unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Discarded RED beside feedback commit resolves without reset past tasks.md**
- **Source Outline**: `AO-042-01`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_revert_red_boundary`
- **Given**: Stored RED object is discarded and its parent still sits on HEAD beside a judge feedback commit
- **When**: JUDGE routes `revert_green` for the task
- **Then**: The runner resolves to the current-train boundary without resetting past the tasks.md-safe commit
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Recovery preserves latest committed tasks.md plus feedback commit**
- **Source Outline**: `AO-042-02`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: A stale stored RED SHA resolves to a safe on-branch boundary on a branch carrying tasks.md
- **When**: The recovery reset runs and the judge feedback commit lands
- **Then**: tasks.md at its latest committed state remains on the branch after recovery
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Empty stored SHA keeps ROLLBACK_BOUNDARY_MISSING refusal**
- **Source Outline**: `AO-042-02`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_green_boundary`
- **Given**: Session `red_commit_sha` is empty
- **When**: JUDGE routes `revert_green` for the task
- **Then**: The runner raises `ROLLBACK_BOUNDARY_MISSING`, records the failure on the task, and emits no traceback past the cycle
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Six-reroute train from gh issue 207 completes rollback**
- **Source Outline**: `AO-042-02`
- **Upstream Traceability**: `US-042-01`, `FR-ADHOC-042`, `AC-ADHOC-042-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_green_boundary`
- **Given**: A GREEN/JUDGE train with repeated reroutes and a moved RED boundary
- **When**: The next JUDGE routes `revert_green`
- **Then**: The runner completes the rollback to the remapped boundary and the task continues training
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Owns the rollback gate; extend `_require_revert_green_boundary` with recovery fallbacks and keep `_execute_rollback` tasks.md restore on the path
  - **Current State**: `_require_revert_green_boundary` remaps only `rewritten` kind; `already_reverted` and `missing` raise `ROLLBACK_STALE_RED_SHA`
  - **Changes Required**: Add already-reverted current-train resolution and tasks.md-safe fallback; keep plain-error refusal when nothing safe resolves; keep `revert_red` resolver untouched
  - **Integration Surface**: `_red_anchor_kind`, `_resolve_rewritten_sha`, `_refresh_session_commit_anchors`, `_execute_rollback`, `_is_fatal_missing_revert_green_boundary`, JUDGE reroute call site
- **tests/unit/test_micro/test_revert_green_stale_sha.py**: New unit sandbox for the recovery matrix
  - **Current State**: File does not exist; `test_rebase_red_sha.py` covers the `rewritten` remap and `test_rollback_safety.py` covers tasks.md preservation
  - **Changes Required**: Add stale-with-rewritten remap, unresolvable refusal without HEAD move, current-SHA passthrough, tasks.md survival cases; mock `_run_pytest` subprocess per repo rule
  - **Integration Surface**: `_require_revert_green_boundary`, fixture repos via `tmp_git_repo` and `_git_env`

## Implementation Strategy
- **Phase 1**: Extend the revert_green boundary resolver with safe recovery
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Classify stored SHA via `_red_anchor_kind`; keep `current` passthrough and `rewritten` remap; resolve `already_reverted` to current HEAD or pre-GREEN train boundary without resetting past the tasks.md-safe SHA; fall back to latest tasks.md-safe boundary only when it is an ancestor of HEAD; else raise the plain refusal; log remap with old and new SHA
  - **Verification**: New unit file passes; existing `test_rebase_red_sha.py` and `test_rollback_safety.py` still pass
- **Phase 2**: Cover the recovery matrix with unit tests
  - **Files**: `tests/unit/test_micro/test_revert_green_stale_sha.py`
  - **Approach**: Build fixture repos (rebased RED, discarded RED beside feedback, dangling SHA, empty SHA); assert reset target, HEAD immobility on refusal, and tasks.md survival
  - **Verification**: `mise run test -- tests/unit/test_micro/test_revert_green_stale_sha.py` passes; full suite under 30s

## Data Flow Analysis
- Input: `session.red_commit_sha` plus branch history (`HEAD` ancestors, commit subjects, tasks.md boundary). Transform: classify anchor kind, remap rewritten SHA by subject, resolve already-reverted to on-branch boundary, validate tasks.md-safe fallback ancestry. Output: on-branch boundary SHA to `_execute_rollback` plus `RED_SHA_REWRITTEN` log; or plain refusal error with HEAD untouched.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Reset to unrelated commit on weak subject match | High | Low | Accept exact subject match only; refuse when no safe boundary resolves |
| Regression in revert_red path | Medium | Low | Touch only `_require_revert_green_boundary`; keep `_resolve_revert_red_boundary` unchanged; run existing rebase tests |
| Tasks.md loss on recovery reset | High | Low | Route recovery through `_execute_rollback` JUDGE tasks.md restore path; add survival test |
| Added gate check exceeds 200ms | Low | Low | Reuse cached git captures; classification is a fixed small set of rev-parse calls |

## Security Profile
Risk surfaces: subprocess (git), file paths (tasks.md restore)
Negative tests: empty SHA refuses with ROLLBACK_BOUNDARY_MISSING; unresolvable SHA refuses without moving HEAD; resolver never resets to a non-ancestor of HEAD
Constraints: no new dependencies; no shell interpolation of SHAs; git only via existing `_git_env` helpers

## Integration Points
- **JUDGE reroute call site**: Continues to call `_require_revert_green_boundary` then `_execute_rollback`; no signature change required
- **`_is_fatal_missing_revert_green_boundary`**: Keeps treating stale/missing green boundary as fatal-stop; recovery success never reaches it
- **Verdict and rollback ledgers**: Recovery reset flows through existing `_RollbackTrace` and verdict records unchanged

## Constitutional Alignment
- **Architecture**: Micro-layer TDD sandbox fix (§1 Micro-Layer Scope, Git Isolation Principle); no layer skipped, no change to `revert_red` or JUDGE verdict semantics per issue exclusions
- **Testing**: pytest unit sandbox `tests/unit/test_micro/test_revert_green_stale_sha.py` with mocked `_run_pytest`; full suite under 30s; ≥80% coverage target
- **Git Isolation**: All recovery work stays on the dedicated issue branch; destructive reset only to an ancestor-of-HEAD boundary; agent work preserved via existing recovery refs
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-007` encode `US-042-01` plus the `AO-042-01`/`AO-042-02` outlines; RED turns the automated scenarios into failing tests before GREEN
