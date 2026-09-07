# Implementation Tasks: `feat/adhoc/050-judge-feedback-clean-slate-retry`

## Phase 1: Clean-slate JUDGE rejection feedback
**Goal**: Make both JUDGE rejection routes describe only the state available after rollback.

### Tasks

- TSK-050-01: Define and verify clean-slate feedback for `revert_green` and `revert_red`
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/auto/judge.md`
    - `tests/unit/test_micro/test_orchestration.py`
  - **Rationale**: `src/deviate/prompts/auto/judge.md` defines the JUDGE rollback and feedback contract for US-050-01. `tests/unit/test_micro/test_orchestration.py` verifies AC-PLAN-001, AC-PLAN-002, AC-PLAN-003, and AC-PLAN-004 through the prompt assembly boundary.
  - **Details**:
    - **Red**: Add failing unit assertions in `tests/unit/test_micro/test_orchestration.py` only. Use the unit layer and forbid `tests/integration` and `tests/e2e`. Assert that `revert_green` feedback names the retained RED test and restored implementation baseline, gives durable behavior, interface, file, and proof requirements, and excludes instructions to modify or inspect discarded GREEN artifacts. Assert that `revert_red` feedback names the pre-RED baseline, gives durable replacement-state test and proof requirements, and treats rejected RED and GREEN references as diagnostic context only. Preserve the existing assertions for route meanings and forward-route REFACTOR behavior.
    - **Green**: Update `src/deviate/prompts/auto/judge.md` only. State that the runner removes the rejected commit set before the next agent. Define `revert_green` as a next-GREEN attempt from retained RED plus the restored implementation baseline. Define `revert_red` as a next-RED attempt from the pre-RED baseline. Require feedback to describe durable replacement behavior, interfaces, files, and proof. Keep rollback boundaries, Git commands, retry budgets, session continuity, model routing, verdict coercion, findings, summaries, and REFACTOR notes unchanged. GREEN cannot edit tests.
    - **Refactor**: Keep the prompt rules grouped with rollback semantics and rejection feedback requirements. Use precise route-specific wording without changing prompt assembly code.
    - **Edge Cases**: Permit JUDGE to retain observed paths and behavior as diagnostics. Require every action instruction to refer to the restored baseline. Exclude discarded `path:line` locations and artifact-preservation instructions from required retry work.
    - **Acceptance**: `mise unit` passes. The rendered JUDGE prompt contains distinct clean-slate rules for both rejection routes. Existing forward-route behavior remains covered. No rollback command, retry limit, session rule, model rule, verdict rule, finding, summary, or REFACTOR note changes.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1

**Critical Dependency Chains**:
- None

**Risk Hotspots**:
- Ambiguous baseline wording could cause retry agents to rebuild discarded artifacts.
- Prompt edits could alter forward-route feedback behavior.

**Merge Conflict Boundaries**:
- `src/deviate/prompts/auto/judge.md` and `tests/unit/test_micro/test_orchestration.py` are touched only by Phase 1.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
