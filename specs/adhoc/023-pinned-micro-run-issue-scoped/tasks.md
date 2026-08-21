# Implementation Tasks: `feat/adhoc/023-pinned-micro-run-issue-scoped`

## Phase 1: Issue-Scoped Pinned Lookup
**Goal**: A known active issue never receives a sibling same-number TSK row. A JSONL miss synthesizes this issue's PENDING task or raises `TASK_NOT_FOUND`.

### Tasks

- TSK-023-01: Scope pinned TSK lookup to the active issue
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_micro/test_e2e.py tests/test_cli/test_micro.py -q -k "find_task_record or TASK_NOT_FOUND or prefers_branch"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_e2e.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-023-01 and `AC-PLAN-003` require `_find_task_record` or `_resolve_task_context` to return this issue's row or a synthesized PENDING. `AC-PLAN-004` requires `TASK_NOT_FOUND` when this issue omits the pin. `AC-PLAN-005` keeps unscoped same-id lookup when no active issue resolves. `AC-PLAN-002` keeps bare and `--all` on this issue's pending queue. `src/deviate/cli/micro.py` owns `_find_task_record` and `_resolve_task_context`. `tests/test_micro/test_e2e.py` pins the empty-ledger branch hole. `tests/test_cli/test_micro.py` pins scoped lookup and keeps `TestFindTaskRecord` green. Constitution §1 Append-Only Ledger Protocol: task ids stay a per-issue `TSK-NNN-NN` namespace. Constitution §3: pytest under `tests/` with `tmp_git_repo` and `_git_env()`.
  - **Details**:
    - **Red**: In `tests/test_micro/test_e2e.py`, add or extend a case beside `test_find_task_record_prefers_branch_issue`. Seed sibling COMPLETED `TSK-001-04`. Give active issue `001-002` zero JSONL rows for that id. Check out the pending-issue feature branch with `cwd=<tmp_git_repo>` and `env=_git_env()`. Assert `_find_task_record(root, "TSK-001-04")` is `None` or a `001-002` record, never the sibling COMPLETED row. Assert `_resolve_task_context("TSK-001-04", root)` returns a synthesized PENDING with `issue_id=001-002` when `tasks.md` lists the id unchecked. Add a `TASK_NOT_FOUND` pin: this issue's `tasks.md` and JSONL omit the pin while a sibling ledger still has it; `_resolve_task_context` prints `TASK_NOT_FOUND` and exits 1. In `tests/test_cli/test_micro.py`, add a unit pin that two issues share `TSK-005-07` and a known branch issue returns only that issue's record or `None`. Keep `test_find_task_record_returns_latest_status` and `test_find_task_record_multiple_entries_returns_last` green on `tmp_path` with no feature branch. Pin that `_find_all_pending_tasks` / bare `_resolve_task_context(None, root)` still select this issue's first pending task and ignore sibling ledgers (`AC-PLAN-002`).
    - **Green**: Share the GH-54 active-issue resolution (branch via `_resolve_issue_id_from_branch` wins when the session issue has no tasks board). When that issue is known, `_find_task_record` returns only a matching `issue_id` row and never `preferred`. If the JSONL miss happens on a pinned id, `_resolve_task_context` calls `_find_all_pending_tasks(root, issue_id=active)` and returns the matching synthesized PENDING, or prints `TASK_NOT_FOUND` and exits 1. Tests without a resolvable issue keep the current single-record fallback. Do not rewrite `_collect_latest_task_records`. Do not fork a second `tasks.md` scanner. Do not change TSK id format. Leave bare / `--all` on the existing issue-id filter.
    - **Refactor**: Keep one ownership site for active-issue resolution so `_find_task_record` and the pinned `_resolve_task_context` path share the same GH-54 rule.
    - **Edge Cases**: Checked `[x]` with no JSONL is not invented as new work. Stale `session.active_issue_id` follows GH-54. Unscoped `tmp_path` tests still find a single same-id record. Do not call un-mocked `_run_pytest`.
    - **Acceptance**: Known active issue never receives another issue's row. Pinned miss synthesizes this issue's PENDING or raises `TASK_NOT_FOUND`. Unscoped latest-status pins stay green. Bare / `--all` stay issue-scoped.

---

## Phase 2: Issue-Owned TASK_ALREADY_DONE
**Goal**: `_run_single` prints `TASK_ALREADY_DONE` only for this issue's terminal status. A sibling COMPLETED pin dispatches this issue's PENDING task.

### Tasks

- TSK-023-02: Refuse TASK_ALREADY_DONE for a foreign COMPLETED pin
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `uv run pytest tests/test_micro/test_run.py -q -k "already_done or TASK_ALREADY_DONE or pinned or TSK-001-04"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_run.py`
  - **Rationale**: US-023-01 and `AC-PLAN-001` require `deviate micro run TSK-001-04` to dispatch this issue's PENDING pin. US-023-02 and `AC-PLAN-007` forbid `TASK_ALREADY_DONE` on a foreign COMPLETED record. `AC-PLAN-006` keeps `TASK_ALREADY_DONE` for this issue's own COMPLETED, REFACTOR, JUDGE, or YELLOW latest status. `_run_single` in `src/deviate/cli/micro.py` owns the IDLE terminal-status guard. `tests/test_micro/test_run.py` pins the sibling-COMPLETED CLI hole and keeps `test_run_skips_already_completed_task` plus `test_task_already_done_triggers_for_judge_latest` green. Constitution §3: mock `deviate.cli.micro._run_pytest`. Constitution §1 Git Isolation: every test git call uses `cwd=<tmp_git_repo>` and `env=_git_env()`.
  - **Details**:
    - **Red**: In `tests/test_micro/test_run.py`, add a CLI pin: `deviate micro run TSK-001-04` in a `tmp_git_repo` feature-branch worktree whose `tasks.md` lists the TSK unchecked and whose JSONL is empty, while a sibling ledger is COMPLETED. Session `current_phase` is `IDLE`. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` and mock `_invoke_agent`. Assert output does not contain `TASK_ALREADY_DONE`. Assert dispatch / resolve uses the branch `issue_id`. Add a guard pin for `AC-PLAN-007`: when the resolved record's `issue_id` differs from the active branch or re-keyed session issue, `_run_single` does not print `TASK_ALREADY_DONE`; it re-resolves this issue's task or raises `TASK_NOT_FOUND`. Keep `test_run_skips_already_completed_task` and `test_task_already_done_triggers_for_judge_latest` green (`AC-PLAN-006`).
    - **Green**: In `_run_single`, compare `task["issue_id"]` to the active issue before the IDLE plus `{COMPLETED, REFACTOR, JUDGE, YELLOW}` exit. Take `TASK_ALREADY_DONE` only when the resolved record belongs to the active issue. A foreign record must re-resolve this issue or raise `TASK_NOT_FOUND`. Do not expand EXECUTE beyond inheriting the scoped `_find_task_record`. Do not revert `_collect_latest_task_records` to id-only dedup.
    - **Refactor**: Keep the existing IDLE plus terminal-set exit when `task["issue_id"]` matches the active issue. Share the GH-54 active-issue resolution from TSK-023-01.
    - **Edge Cases**: Same-issue COMPLETED, REFACTOR, JUDGE, and YELLOW still print `TASK_ALREADY_DONE` and exit 0. Unknown format still prints `TASK_NOT_FOUND` and exits 1. Do not call un-mocked `_run_pytest`. Do not delete branches.
    - **Acceptance**: Sibling COMPLETED same-number TSK does not print `TASK_ALREADY_DONE`. This issue's own terminal status still does. CLI pin dispatches the branch issue's PENDING record.
  - **Dependency**: TSK-023-01

---

## Phase 3: Specs and Changelog
**Goal**: Document that pinned `micro run <task-id>` is issue-scoped and that `TSK-NNN-NN` stays a per-issue namespace.

### Tasks

- TSK-023-03: Document issue-scoped pinned micro run
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_micro/test_e2e.py tests/test_micro/test_run.py tests/test_cli/test_micro.py -q -k "find_task_record or TASK_ALREADY_DONE or already_done or pinned"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-008` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same change as the runner contract. US-023-02 is the user-visible rule: pinned `TSK-NNN-NN` is a per-issue namespace. AGENTS.md Spec Alignment requires both spec files. Constitution §1 Four-Layer Architecture: this slice does not skip a layer and does not restore Gate 2.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, update the Single-Task paragraph for `deviate micro run [task-id]`. State that a pinned id stays in the active issue's namespace when the branch or re-keyed session issue is known. State that a sibling COMPLETED row for the same number is not a hit.
    - **Implementation**: In `specs/DeviaTDD-architecture.md`, update the Execution Engine text for `deviate micro run <task-id>`. State that resolution is issue-scoped when the branch or re-keyed session issue is known. State that same-number TSK ids remain a per-issue namespace.
    - **Implementation**: Append one bullet under `CHANGELOG.md` `[Unreleased]`: pinned `deviate micro run <task-id>` no longer treats a sibling COMPLETED same-number TSK as `TASK_ALREADY_DONE` when this issue is still PENDING.
    - **Implementation**: Re-run the Phase 1 and Phase 2 pins. Do not author or sync Product-layer flows. Do not change TSK id format in the docs.
    - **Refactor**: Reuse existing Micro-layer Single-Task wording. Do not add a second lookup contract.
    - **Edge Cases**: `--all` stays described as issue-scoped. `flow_refs` stays `[]`. Do not mutate operator-local `.deviate/config.toml`.
    - **Acceptance**: API and architecture state that pinned `micro run <task-id>` is issue-scoped. CHANGELOG `[Unreleased]` has the user-visible bullet. Lookup and already-done pins stay green.
  - **Dependency**: TSK-023-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3

**Critical Dependency Chains**:
- TSK-023-01 must precede TSK-023-02
- TSK-023-02 must precede TSK-023-03

**Risk Hotspots**:
- Unscoped `TestFindTaskRecord` tests lose their single-record hit
- A second scanner forks `_find_all_pending_tasks` and drifts
- Same-issue COMPLETED / JUDGE stops emitting `TASK_ALREADY_DONE`
- `execute post` still completes a sibling via `_find_task_record`
- `_collect_latest_task_records` reverts to id-only dedup
- Tests spawn un-mocked `_run_pytest` and blow the 30s budget
- Stale `session.active_issue_id` points at the sibling

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/023-pinned-micro-run-issue-scoped/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
