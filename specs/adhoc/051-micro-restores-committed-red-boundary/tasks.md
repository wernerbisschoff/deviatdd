# Implementation Tasks: `feat/adhoc/051-micro-restores-committed-red-boundary`

## Phase 1: RED boundary recovery
**Goal**: Resume GREEN from a ledger-plus-Git recovered RED boundary after session loss.

### Tasks

- TSK-051-01: Recover the RED boundary and resume GREEN after session loss
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_orchestration.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns the pre-GREEN decision for US-051-01 and AC-PLAN-001. `tests/unit/test_micro/test_orchestration.py` verifies the recovery contract at the orchestration boundary.
  - **Details**:
    - **Red**: Add failing unit assertions in `tests/unit/test_micro/test_orchestration.py` only. Use the unit layer and forbid `tests/integration` and `tests/e2e`. Build a task with a latest RED ledger record, an empty `session.red_commit_sha`, and an on-branch RED commit in a `tmp_git_repo` fixture. Assert the recovery helper restores `red_commit_sha`, the pre-GREEN decision routes to GREEN, and neither RED nor rollback runs. Assert a cherry-picked RED commit with matching task evidence is accepted as the valid boundary. Preserve the existing assertions for missing-SHA escalation and forward-route behavior.
    - **Green**: Implement the recovery helper in `src/deviate/cli/micro.py` only. Read the latest ledger record for the task, resolve the candidate commit with `_resolve_rewritten_sha`, verify it is on-branch with matching task evidence, restore `session.red_commit_sha`, and wire the helper into the dispatch path before `_tdd_pre_green_decision`. Keep RED authoring, GREEN scope, retry budgets, model routing, and JUDGE handling unchanged. GREEN cannot edit tests.
    - **Refactor**: Keep the helper next to `_has_red_commit_boundary` and `_tdd_pre_green_decision`. Reuse `_resolve_rewritten_sha` and `_refresh_session_commit_anchors` without duplicating SHA logic.
    - **Edge Cases**: Handle the cherry-picked commit through `_resolve_rewritten_sha`. Keep the recovery decision within the 200ms budget excluding Git subprocess time.
    - **Acceptance**: `mise unit` passes. A RED ledger state with a matching on-branch commit and empty session SHA resumes GREEN. A cherry-picked RED commit with matching evidence is accepted.

- TSK-051-02: Stop with a named diagnostic on missing or ambiguous RED evidence
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_orchestration.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns the safe-stop path for US-051-02 and AC-PLAN-003. `tests/unit/test_micro/test_orchestration.py` verifies the diagnostic contract at the orchestration boundary.
  - **Dependency**: TSK-051-01
  - **Details**:
    - **Red**: Add failing unit assertions in `tests/unit/test_micro/test_orchestration.py` only. Use the unit layer and forbid `tests/integration` and `tests/e2e`. Assert that a task with no RED ledger state emits a named diagnostic naming the task and the evidence gap. Assert that multiple candidate commits matching partial evidence emit the ambiguity diagnostic. Assert that neither case reruns RED silently nor rolls back. Preserve the TSK-051-01 recovery assertions.
    - **Green**: Extend the recovery helper in `src/deviate/cli/micro.py` only. Return the named diagnostic when no single boundary is identifiable, and stop the run without dispatching RED or rollback. Keep the TSK-051-01 valid-recovery path unchanged. GREEN cannot edit tests.
    - **Refactor**: Keep the diagnostic names and evidence details in one helper return shape used by the dispatch path and the task log.
    - **Edge Cases**: Handle zero candidates (missing) and two-or-more candidates (ambiguous) as distinct diagnostic reasons. Never delete or rewrite completed work on the safe-stop path.
    - **Acceptance**: `mise unit` passes. Missing evidence and ambiguous evidence each emit a diagnostic with task and evidence details. No silent RED rerun and no rollback occur on either path.

- TSK-051-03: Clear stale rejection on a recovered boundary and resume GREEN end to end
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_run.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns session resume for US-051-01, US-051-02, AC-PLAN-001, and AC-PLAN-004. `tests/unit/test_micro/test_run.py` verifies the dispatch-level resume contract.
  - **Dependency**: TSK-051-02
  - **Details**:
    - **Red**: Add failing unit assertions in `tests/unit/test_micro/test_run.py` only. Use the unit layer and forbid `tests/integration` and `tests/e2e`. Build a dispatch with an empty `session.red_commit_sha`, a RED ledger record, an on-branch RED commit, and stale `pending_judge_action` plus `judge_rejected` from an earlier attempt. Assert the run clears the earlier rejection state, restores the later boundary, and proceeds to GREEN. Preserve the existing session-resume assertions.
    - **Green**: Wire stale-rejection clearing into the recovery path in `src/deviate/cli/micro.py` only, reusing `_forward_route_is_stale` and `_invalidate_stale_forward_route`. Run recovery at dispatch before `_tdd_pre_green_decision` so the full RED-to-GREEN resume works end to end. Keep retry budgets, model routing, and JUDGE handling unchanged. GREEN cannot edit tests.
    - **Refactor**: Keep rejection clearing inside the recovery helper call sequence. Do not duplicate forward-route logic.
    - **Edge Cases**: Handle an unbound pre-fix forward route (GH-148 poison) as stale once a RED boundary exists. Keep the valid no-failing-test handoff (empty SHA forward route) intact.
    - **Acceptance**: `mise unit` passes. Stale rejection from an earlier attempt does not block a recovered later boundary. Session loss with a valid RED boundary resumes GREEN end to end.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-051-01 -> TSK-051-02 -> TSK-051-03)

**Critical Dependency Chains**:
- TSK-051-01 must precede TSK-051-02
- TSK-051-02 must precede TSK-051-03

**Risk Hotspots**:
- Recovery could accept the wrong commit when several candidates match partial evidence.
- Clearing rejection state could mask a genuinely needed RED rerun.

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` and `tests/unit/test_micro/test_orchestration.py` are touched by TSK-051-01 and TSK-051-02. `tests/unit/test_micro/test_run.py` is touched only by TSK-051-03.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
