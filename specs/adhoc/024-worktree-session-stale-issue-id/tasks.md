# Implementation Tasks: `feat/adhoc/024-worktree-session-stale-issue-id`

## Phase 1: Branch-Authoritative Micro Session Re-Key
**Goal**: A known feature-branch issue owns the micro queue, pinned TSK lookup, and worktree `session.active_issue_id`.

### Tasks

- TSK-024-01: Re-key leftover session ids to the branch issue and persist
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_cli/test_micro.py -q -k "stale_session or rekey or NO_PENDING_TASKS or pinned"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-024-01 and `AC-PLAN-001` require bare `deviate micro run` and `--all` to consume the first pending branch-issue task when `.deviate/session.json` still names a leftover id. `AC-PLAN-002` keeps `NO_PENDING_TASKS` exit 0 when that branch issue has zero unchecked tasks. `AC-PLAN-003` requires the resolver to return issue B and rewrite worktree `session.active_issue_id` to B even when leftover issue A still has a `tasks.md`. `AC-PLAN-004` keeps a valid session id when `_resolve_issue_id_from_branch` returns None. `AC-PLAN-007` scopes pinned `TSK-NNN-NN` lookup through `_resolve_known_active_issue_id` so ISS-ADH-023 does not bind issue A's COMPLETED row. `src/deviate/cli/micro.py` owns `_rekey_session_issue_to_branch`, `_resolve_task_context`, `_resolve_known_active_issue_id`, and `_run_all`. `tests/test_cli/test_micro.py` keeps `test_stale_session_issue_rekeys_to_branch_issue` and adds the leftover-with-board persist pin. Constitution §1 Git Isolation Principle and Session Continuity: the worktree session names the claimed branch issue. Constitution §2: persist via existing `SessionState.active_issue_id` and `SessionState.save`. Constitution §3: pytest under `tests/` with `tmp_git_repo` and `_git_env()`.
  - **Details**:
    - **Red**: Keep `TestResolveTaskContextUsesBranch.test_stale_session_issue_rekeys_to_branch_issue` (GH-54, leftover issue has no board). Add a leftover-with-board pin: seed issue A (`001-006` or `ISS-006`) with a `tasks.md`, seed issue B (`001-007` or `ISS-007`) with unchecked `TSK-007-*`, check out `feat/001-forge-layer/007-inventory-inspection` via `cwd=<tmp_git_repo>` and `env=_git_env()`, write `.deviate/session.json` `active_issue_id` to A. Assert `_resolve_task_context(None, root)` returns B's first pending task and that worktree `.deviate/session.json` `active_issue_id` equals B. Add a CLI pin for bare `deviate micro run` (and `--all` if dispatched) whose stdout does not contain `NO_PENDING_TASKS`. Add an empty-queue pin: B's `tasks.md` has zero unchecked tasks, bare resolve prints `NO_PENDING_TASKS` and exits 0 (`AC-PLAN-002`). Add an unresolved-branch pin: valid session id, `_resolve_issue_id_from_branch` returns None, helper keeps the session id and does not write a blank id (`AC-PLAN-004`). Add a pinned pin: A and B share `TSK-NNN-NN`, session names A, branch maps to B; `deviate micro run TSK-NNN-NN` / `_resolve_known_active_issue_id` uses B and does not bind A's COMPLETED row (`AC-PLAN-007`). Cover epic-prefix ids and `ISS-*`.
    - **Green**: Change `_rekey_session_issue_to_branch` so a known `branch_issue_id` that differs from `session.active_issue_id` wins even when leftover A still has a `tasks.md`. Persist the authoritative id with `SessionState.save` to worktree `.deviate/session.json` when it differs. Route `_resolve_task_context`, `_resolve_known_active_issue_id`, and `_run_all` through that helper. Empty session still falls back to the branch. Unresolved branch keeps a valid session id. Reuse `SessionState.active_issue_id`; do not add session fields. Do not unify `micro._resolve_issue_id_from_branch` with `_common.resolve_issue_id_from_branch` unless a lookup mismatch blocks this slice. Do not restore ISS-ADH-023 foreign `preferred` fallback.
    - **Refactor**: Keep one ownership site for the branch-authoritative rule so bare resolve, `--all`, and pinned lookup share the same helper.
    - **Edge Cases**: Session id that already matches the branch stays unchanged. Missing session still falls back to the branch. Unresolved non-`feat/` branch does not blank a valid session id. Re-key does not invent an issue id. Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` on every CLI path that would spawn it.
    - **Acceptance**: Leftover A with a board yields B's pending task. `session.json` equals B. Empty branch queue still prints `NO_PENDING_TASKS` and exits 0. Pinned lookup uses B. GH-54 no-board pin stays green.

---

## Phase 2: Meso Worktree Session Key
**Goal**: Meso claim and `MESO_ALREADY_COMPLETE` write the claimed issue into the worktree session.

### Tasks

- TSK-024-02: Key the worktree session on meso claim and already-complete
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `uv run pytest tests/test_meso/test_meso_resume.py tests/test_meso/test_meso_orchestration.py -q -k "ALREADY_COMPLETE or worktree or active_issue"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_meso/test_meso_resume.py`
    - `tests/test_meso/test_meso_orchestration.py`
  - **Rationale**: US-024-02 and `AC-PLAN-005` require `_meso_run` to write worktree `session.active_issue_id` to the claimed issue before it prints `MESO_ALREADY_COMPLETE` and returns. `AC-PLAN-006` requires the worktree `.deviate/session.json` after SPECIFY `.deviate/` copy to name the claimed issue, not the previous main-repo id. `src/deviate/cli/meso.py` owns `_meso_run` and `_claim_and_setup`. `tests/test_meso/test_meso_resume.py` extends `test_valid_plan_and_tasks_skip_both_phases`. `tests/test_meso/test_meso_orchestration.py` asserts the copied worktree session after claim. Constitution §1 Git Isolation Principle: each worktree session names the claimed issue. Constitution §2: reuse `SessionState.save`. Constitution §3: mock `deviate.cli.micro._run_pytest`.
  - **Details**:
    - **Red**: In `tests/test_meso/test_meso_resume.py`, seed leftover `active_issue_id` on the worktree session. After `_meso_run` prints `MESO_ALREADY_COMPLETE`, assert worktree `.deviate/session.json` `active_issue_id` equals the claimed issue (`AC-PLAN-005`). Keep the existing skip-agents pin. In `tests/test_meso/test_meso_orchestration.py`, seed the main-repo session with a previous issue, run `_meso_run` so SPECIFY copies `.deviate/` into the new worktree, and assert the worktree session equals the claimed issue, not the previous main-repo id (`AC-PLAN-006`). Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` and mock the agent cycle.
    - **Green**: Before the `resume_state == "COMPLETE"` return, set `session.active_issue_id` to the claimed issue and save the worktree session. After `.deviate/` copy, rewrite the worktree session when the copied file still names the previous issue. Keep `_claim_and_setup` write-then-copy order. Do not add `SessionState` fields. Do not add extra agent calls.
    - **Refactor**: Share one write of `session.active_issue_id` plus `SessionState.save` for claim copy and already-complete.
    - **Edge Cases**: `--no-setup` already-complete still rewrites `$CWD` `.deviate/session.json` to the claimed issue. Copytree must not leave the previous main-repo id in the worktree. Do not delete branches. Do not mutate operator-local `.deviate/config.toml`.
    - **Acceptance**: `MESO_ALREADY_COMPLETE` leaves the worktree session on the claimed issue. Claim/copy leaves the worktree session on the claimed issue. Existing meso resume and orchestration pins stay green.
  - **Dependency**: TSK-024-01

---

## Phase 3: Specs and Changelog
**Goal**: Document that a known feature-branch issue beats a leftover session id, and that meso claim / already-complete rewrite the worktree session.

### Tasks

- TSK-024-03: Document branch-authoritative session re-key
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_cli/test_micro.py tests/test_meso/test_meso_resume.py tests/test_meso/test_meso_orchestration.py -q -k "stale_session or rekey or ALREADY_COMPLETE or worktree"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-001` through `AC-PLAN-007` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md` §10, and `CHANGELOG.md` `[Unreleased]` in the same change as the session contract. US-024-01 is the user-visible queue rule. US-024-02 is the meso write rule. AGENTS.md Spec Alignment requires both spec files. Constitution §1 Four-Layer Architecture: this slice stays in C1 and does not restore Gate 2.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md` Queue Drain, state that a known `feat/{bucket}/{slug}` issue beats a leftover `session.active_issue_id`. State that meso claim and `MESO_ALREADY_COMPLETE` rewrite the worktree session to the claimed issue.
    - **Implementation**: In `specs/DeviaTDD-architecture.md` §10, state that a conflicting leftover session yields to the known feature-branch issue.
    - **Implementation**: Append one `[Unreleased]` bullet in `CHANGELOG.md` for leftover ids that still have a board, plus the meso claim / already-complete session write. Keep the existing GH-54 no-board bullet.
    - **Implementation**: Re-run the Phase 1 and Phase 2 pins. Do not author or sync Product-layer flows. Do not change TSK id format.
    - **Refactor**: Reuse existing Queue Drain and §10 wording. Do not add a second session field or a second slug parser contract.
    - **Edge Cases**: Empty branch queue stays documented as `NO_PENDING_TASKS` exit 0. Unresolved branch may keep a valid session id. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture name the branch-authoritative rule. CHANGELOG `[Unreleased]` has the leftover-with-board plus meso write bullet. Micro and meso pins stay green.
  - **Dependency**: TSK-024-02

---

## Phase 4: CLI E2E
**Goal**: Prove the installed `deviate` binary consumes the branch issue queue when the worktree session is leftover.

### Tasks

- TSK-024-04: [E2E] Verify leftover session cannot empty the branch queue
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_worktree_session_stale_issue.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: US-024-01 and `AC-PLAN-001` are the user-visible happy path: leftover `session.active_issue_id` must not print `NO_PENDING_TASKS` when the branch issue still has unchecked tasks. `AC-PLAN-002` is the critical-failure empty-queue path: `NO_PENDING_TASKS` exit 0 stays legal when the branch issue queue is empty. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_worktree_session_stale_issue.bats`. In a fresh tmp git repo, seed issues `001-006` and `001-007`, give `001-007` an unchecked `TSK-007-*`, check out `feat/001-forge-layer/007-inventory-inspection`, and write leftover `active_issue_id` `001-006`. Run `deviate micro run --dry-run`. Assert exit 0, stdout names the `001-007` task, and stdout does not contain `NO_PENDING_TASKS`.
    - **Implementation**: Add the empty-queue case in the same bats file: branch issue `tasks.md` has zero unchecked tasks. Run `deviate micro run --dry-run`. Assert exit 0 and stdout contains `NO_PENDING_TASKS`.
    - **Implementation**: Keep `tests/e2e/test_macro_workflow.bats` as the existing CLI smoke suite. Do not invoke a live agent cycle. Do not call un-mocked `_run_pytest`.
    - **Refactor**: Reuse the existing bats tmpdir setup/teardown pattern from `tests/e2e/test_macro_workflow.bats`.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` is unused. Do not delete branches in the host repo.
    - **Acceptance**: `bats tests/e2e/` exits 0. Happy path does not print `NO_PENDING_TASKS`. Empty branch queue still prints `NO_PENDING_TASKS` and exits 0.
  - **Dependency**: TSK-024-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

**Critical Dependency Chains**:
- TSK-024-01 must precede TSK-024-02
- TSK-024-02 must precede TSK-024-03
- TSK-024-03 must precede TSK-024-04

**Risk Hotspots**:
- Existing tests assume leftover session wins when that issue still has a `tasks.md`
- `_run_all` keeps reading raw `session.active_issue_id` after `_resolve_task_context` is fixed
- `_meso_run` copytree overwrites a later main-repo write, or COMPLETE returns before any write
- Dual slug parsers diverge
- Un-mocked `_run_pytest` blows the 30s suite budget
- Bats E2E picks up the host repo `.deviate/session.json`

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none. Phase 1 owns `src/deviate/cli/micro.py`. Phase 2 owns `src/deviate/cli/meso.py`.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/024-worktree-session-stale-issue-id/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
