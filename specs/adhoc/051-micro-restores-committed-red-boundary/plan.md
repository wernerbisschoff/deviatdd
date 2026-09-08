## Plan Summary
- **Issue**: ISS-ADH-051 — Restore a committed RED boundary after session loss
- **Implementation Strategy**: Add a ledger-plus-Git recovery step that rebuilds `session.red_commit_sha` before the pre-GREEN decision. Keep RED authoring, GREEN scope, retry budgets, model routing, and JUDGE behavior unchanged.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Resume GREEN from a recovered RED boundary**
- **Source Outline**: `AO-051-01`
- **Upstream Traceability**: `US-051-01`, `FR-ADHOC-051`, `AC-ADHOC-051-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:return bool(session.red_commit_sha.strip())`
- **Given**: A task whose latest ledger record is RED and whose RED commit exists on the active branch, with `session.red_commit_sha` empty after session loss
- **When**: The runner reaches the pre-GREEN decision
- **Then**: The runner restores `red_commit_sha`, clears stale attempt rejection, and proceeds to GREEN without invoking RED or rollback
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Accept a cherry-picked RED commit with matching task evidence**
- **Source Outline**: `AO-051-01`
- **Upstream Traceability**: `US-051-01`, `FR-ADHOC-051`, `AC-ADHOC-051-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:def _resolve_rewritten_sha(root: Path, stored_sha: str) -> str:`
- **Given**: The RED commit exists on the active branch through a cherry-pick and its task evidence matches
- **When**: The runner recovers the RED boundary
- **Then**: The cherry-picked commit is accepted as the valid boundary
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Stop with a named diagnostic when RED evidence is missing or ambiguous**
- **Source Outline**: `AO-051-02`
- **Upstream Traceability**: `US-051-02`, `FR-ADHOC-051`, `AC-ADHOC-051-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:if not _has_red_commit_boundary(session):`
- **Given**: No single RED commit can be identified from ledger plus Git evidence
- **When**: The runner attempts boundary recovery
- **Then**: The runner emits a diagnostic naming the task and the evidence gap, and neither reruns RED silently nor rolls back
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Ignore stale rejection from an earlier RED attempt**
- **Source Outline**: `AO-051-02`
- **Upstream Traceability**: `US-051-02`, `FR-ADHOC-051`, `AC-ADHOC-051-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:def _forward_route_is_stale(session: SessionState, task_id: str) -> bool:`
- **Given**: A recovered later RED boundary with rejection state (`pending_judge_action`, `judge_rejected`) referencing an earlier attempt
- **When**: The runner resumes GREEN on the recovered boundary
- **Then**: The earlier rejection state does not block or reroute the recovered run
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Owns the pre-GREEN decision and session-boundary helpers
  - **Current State**: `_has_red_commit_boundary` reads only `session.red_commit_sha`; `_tdd_pre_green_decision` escalates to RED on empty SHA; `_run_red_phase` persists the SHA in session only; `_resolve_rewritten_sha` and `_forward_route_is_stale` already solve the rewrite and stale-route subproblems
  - **Changes Required**: Add a recovery helper that derives the RED boundary from the latest ledger record plus on-branch Git evidence, restores `session.red_commit_sha`, clears stale rejection tied to an earlier attempt, and returns a named diagnostic when evidence is missing or ambiguous. Call it before `_tdd_pre_green_decision` dispatches. Keep RED authoring, retry budgets, routing, and JUDGE handling unchanged.
  - **Integration Surface**: `_execute_task_with_retry` dispatch, `_tdd_pre_green_decision`, `_run_red_phase`, `_refresh_session_commit_anchors`, task log diagnostics
- **tests/unit/test_micro/test_orchestration.py**: Owns recovery and stale-rejection cases
  - **Current State**: Covers orchestration decisions including forward-route staleness
  - **Changes Required**: Add cases for ledger-plus-Git recovery, cherry-picked commit acceptance, missing-evidence diagnostic, ambiguous-evidence diagnostic, and stale-rejection clearing on a recovered boundary
  - **Integration Surface**: Recovery helper, `_tdd_pre_green_decision`, `_forward_route_is_stale`
- **tests/unit/test_micro/test_run.py**: Owns session-resume cases
  - **Current State**: Covers task run dispatch and session handling
  - **Changes Required**: Add a session-loss resume case: empty `red_commit_sha` with RED ledger state and on-branch RED commit proceeds to GREEN
  - **Integration Surface**: `_execute_task_with_retry`, `SessionState` load path

## Implementation Strategy
- **Phase 1**: Add the RED boundary recovery helper
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Read the latest ledger record for the task, resolve the candidate commit with `_resolve_rewritten_sha`, verify it is on-branch with matching task evidence, restore `session.red_commit_sha`, clear stale rejection state, and return a named diagnostic on missing or ambiguous evidence. Wire it into the dispatch path before `_tdd_pre_green_decision`. Keep the 200ms recovery budget excluding Git subprocess time.
  - **Verification**: Focused orchestration tests plus `mise run check`.
- **Phase 2**: Verify recovery and safe-stop behavior
  - **Files**: `tests/unit/test_micro/test_orchestration.py`, `tests/unit/test_micro/test_run.py`
  - **Approach**: Assert GREEN resume on valid recovery, cherry-pick acceptance, named diagnostic with no RED rerun or rollback on missing or ambiguous evidence, and stale-rejection clearing.
  - **Verification**: Run `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_run.py -q` and `mise run check`.

## Data Flow Analysis
- Dispatch loads the session and the latest ledger record for the task. The recovery helper runs before the pre-GREEN decision: ledger RED state plus on-branch Git evidence rebuilds `session.red_commit_sha` and clears stale rejection. A valid boundary routes to GREEN; missing or ambiguous evidence emits the diagnostic and stops. The existing TDD loop, retry budgets, and JUDGE path run unchanged after recovery.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Recovery accepts the wrong commit when several candidates match | High | Medium | Treat multiple matches as ambiguous and stop with the diagnostic |
| Recovery masks a genuinely missing RED and skips needed test authoring | High | Low | Require both ledger RED state and on-branch commit evidence before resume |
| Session rebuild fights concurrent ledger appends | Medium | Low | Read latest-per-task records at dispatch; keep ledgers append-only |

## Security Profile
Risk surfaces: session handling, git evidence parsing, ledger reads
Negative tests: ambiguous candidates stop without rollback; missing evidence never triggers silent RED
Constraints: keep append-only ledgers and Git isolation rules unchanged; add no subprocess beyond Git evidence reads, no network call, no dependency, no secret

## Integration Points
- **Dispatch path**: `_execute_task_with_retry` loads `SessionState` and the task record before `_dispatch_task`.
- **Pre-GREEN gate**: `_tdd_pre_green_decision` keeps its precedence; recovery runs before it dispatches.
- **Rewrite resolution**: `_resolve_rewritten_sha` and `_refresh_session_commit_anchors` verify on-branch identity including cherry-picks.
- **Stale routes**: `_forward_route_is_stale` / `_invalidate_stale_forward_route` clear earlier-attempt rejection on the recovered boundary.

## Constitutional Alignment
- **Architecture**: This change stays within the Micro RED → GREEN → JUDGE → REFACTOR flow required by `specs/constitution.md` §1: “Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).”
- **Testing**: Pytest covers recovery and safe-stop behavior. The checks use the repository test command and preserve the 80% coverage target from §3.
- **Git Isolation**: Recovery reads Git evidence only; commits still land at phase boundaries per §1: “Every task loop executes on a clean git branch or worktree.”
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `AO-051-01`; `AC-PLAN-003` and `AC-PLAN-004` encode `AO-051-02`. RED turns these scenarios into failing tests before GREEN.
