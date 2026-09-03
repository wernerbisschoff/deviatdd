---
title: "Re-key stale worktree session to the claimed branch issue"
labels: [bugfix, adhoc, vertical-slice, micro]
blocked_by: []
coordinates_with: [ISS-ADH-023]
issue_id: ISS-ADH-024
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/024-worktree-session-stale-issue-id.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py::_rekey_session_issue_to_branch` — TARGET: when a branch-derived issue is known and differs from `session.active_issue_id`, the branch wins. A leftover truthy session id is not sticky, including when the leftover issue still has a `tasks.md` in this checkout. Persist the authoritative id to the worktree `.deviate/session.json`.
  - `src/deviate/cli/micro.py::_resolve_task_context` — TARGET: bare `deviate micro run` (no task id) must scan `_find_all_pending_tasks` for the branch issue after re-key, not for a previous issue that has no (or the wrong) board here. `NO_PENDING_TASKS` is legal only when the *branch* issue has no pending work.
  - `src/deviate/cli/micro.py::_resolve_known_active_issue_id` — TARGET: same branch-authoritative rule as the unscoped resolver so ISS-ADH-023 pinned lookup composes (active issue is the branch issue, not the leftover session id).
  - `src/deviate/cli/micro.py::_resolve_issue_id_from_branch` / `src/deviate/cli/_common.py::resolve_issue_id_from_branch` — REFERENCE: existing `feat/{bucket}/{slug}` → `specs/issues.jsonl` `source_file` lookup. Reuse; do not invent a second slug parser. Do not require unifying the two helpers unless a mismatch blocks this slice.
  - `src/deviate/state/config.py::SessionState.active_issue_id` — TARGET: worktree session cache must be rewritten to the claimed/branch issue. Do not add fields.
  - `src/deviate/cli/meso.py::_meso_run` — TARGET: `MESO_ALREADY_COMPLETE` currently prints and returns *before* `session.active_issue_id = issue_id`. It must still key the worktree session to the claimed issue. The `.deviate/` `copytree` into a new worktree must not leave the previous issue's id in the worktree session (write-then-copy, or write the worktree session after copy).
  - `src/deviate/cli/meso.py::_claim_and_setup` — REFERENCE: already sets `session.active_issue_id = issue_id` then copies `.deviate/` into the worktree. Keep that order; do not regress it.
  - `tests/unit/test_cli/test_micro.py::TestResolveTaskContextUsesBranch` — TARGET: keep `test_stale_session_issue_rekeys_to_branch_issue` (GH-54, no board for the leftover issue) and add the stronger mismatch case plus a persist pin.
  - `tests/unit/test_meso/test_meso_resume.py` / `tests/unit/test_meso/test_meso_orchestration.py` — TARGET: `MESO_ALREADY_COMPLETE` and worktree claim leave `active_issue_id` equal to the claimed issue in the worktree session.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document that a known feature-branch issue beats a leftover session id, and that meso claim / already-complete rewrite the worktree session.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible queue/session fix. An earlier GH-54 bullet covers only the "no tasks board" re-key; this slice is the remaining sticky-id + meso write hole.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - GitHub #54: worktree branch `feat/001-forge-layer/007-inventory-inspection` with five unchecked `TSK-007-*` tasks; worktree session `active_issue_id: "001-006"`; `deviate micro run` → `NO_PENDING_TASKS` exit 0. Main-repo session already showed `001-007`.
  - `_rekey_session_issue_to_branch` already prefers the branch when the session issue has no `tasks.md` here, but keeps the session id when a board exists and never writes `session.json`.
  - `_meso_run` copies `.deviate/` into the worktree, then on `resume_state == "COMPLETE"` returns without `session.active_issue_id = issue_id`.
  - Several later micro sites still read raw `session.active_issue_id` (not the re-key helper).

## The Problem Contract

A claimed feature worktree can carry a previous issue's `active_issue_id` in its untracked `.deviate/session.json`. Bare `deviate micro run` then treats that leftover id as the queue owner, finds no pending work for it, and exits `NO_PENDING_TASKS` while the branch issue's `tasks.md` still has unchecked tasks. Operators need the current branch to own the queue and the worktree session, without a manual session edit.

## Scope Boundaries

### Hard Inclusions

- When `_resolve_issue_id_from_branch` (or the shared `_common` helper) returns an issue id that differs from `session.active_issue_id`, the branch id is the active issue for bare `deviate micro run`, `--all`, and the ISS-ADH-023 pinned-lookup scope.
- Unchecked tasks in the branch issue's `tasks.md` are consumed. `NO_PENDING_TASKS` exit 0 is reserved for a truly empty branch-issue queue.
- Persist the authoritative issue id to the worktree `.deviate/session.json` so subsequent meso/micro/e2e commands and humans do not see the leftover id.
- Meso worktree creation/claim must leave the *worktree* session keyed to the claimed issue (not a copy of the previous main-repo session).
- `MESO_ALREADY_COMPLETE` inside the worktree must still write `session.active_issue_id` to the claimed/branch issue.
- Cover epic-prefix ids (`001-006` / `001-007`) as well as `ISS-*` forms; the GH-54 repro used `001-006`.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for any git; mock `deviate.cli.micro._run_pytest` when a CLI path would spawn it.

### Defensive Exclusions

- Do **not** reopen GitHub #62 / #63 / #65 / #74 (ISS-ADH-020 evidence, ISS-ADH-021 SHA / GREEN-entry, ISS-ADH-022 already_satisfied files) except to compose.
- Do **not** reopen ISS-ADH-023 except to compose: pinned `micro run TSK-NNN-NN` stays issue-scoped to the *re-keyed* active issue. Do not restore foreign `preferred` fallback.
- Do **not** change `NO_PENDING_TASKS` when the branch issue itself has no pending tasks.
- Do **not** require unifying `micro._resolve_issue_id_from_branch` and `_common.resolve_issue_id_from_branch` unless a lookup mismatch is what blocks this slice.
- Do **not** author, repair, or index Product-layer flows (`flow_refs: []`).
- Do **not** delete branches, mutate operator-local `.deviate/config.toml`, or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** change TSK id format or ledger append-only rules.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-024`
- **Acceptance Criteria Tokens**: `AC-ADHOC-024-01`, `AC-ADHOC-024-02`, `AC-ADHOC-024-03`
- **Data Model Entities**: `SessionState.active_issue_id`, `IssueRecord.issue_id`, `IssueRecord.source_file` — no new ledger row types
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` `_rekey_session_issue_to_branch` / `_resolve_task_context` / `_resolve_known_active_issue_id`
  - `src/deviate/cli/meso.py` `_meso_run` (`MESO_ALREADY_COMPLETE` early return and `.deviate/` copy order)
  - `specs/constitution.md` §1 Git Isolation Principle + Session Continuity; §2 session state under `.deviate/`
  - `specs/DeviaTDD-architecture.md` §10 Issue-Scoped Resolution (session then branch fallback — this slice makes a *conflicting* session yield to the branch)

## User Stories Ledger

- **US-024-01**: As a DeviaTDD operator, I want bare `deviate micro run` in a claimed worktree to consume the current branch's pending tasks even when the worktree session still names a previous issue so a leftover id cannot empty the queue. *(Ref: FR-ADHOC-024)*
- **US-024-02**: As a DeviaTDD operator, I want meso claim and `MESO_ALREADY_COMPLETE` to write the claimed issue into the worktree session so I never hand-edit `.deviate/session.json`. *(Ref: FR-ADHOC-024)*

## Acceptance Outline

- **AO-024-01** *(Ref: AC-ADHOC-024-01, US-024-01)*: Stale session cannot empty a live branch queue.
  - **Happy Path**: Worktree on `feat/001-forge-layer/007-inventory-inspection` with unchecked `TSK-007-*` in that issue's `tasks.md`, session `active_issue_id` still `001-006`. Bare `deviate micro run` resolves the first pending `001-007` task and does not print `NO_PENDING_TASKS`.
  - **Error Category**: Printing `NO_PENDING_TASKS` and exiting 0 because the leftover session id has no pending board is a failure of this slice.
  - **Boundary Category**: When the branch issue itself has no pending tasks, `NO_PENDING_TASKS` exit 0 remains the empty-queue contract.

- **AO-024-02** *(Ref: AC-ADHOC-024-02, US-024-01)*: Branch issue beats a leftover session id and the session is rewritten.
  - **Happy Path**: Session names issue A, branch maps to issue B. Resolver returns B even if A still has a `tasks.md` in this checkout. After resolve, worktree `.deviate/session.json` `active_issue_id` equals B.
  - **Error Category**: Keeping A because it is truthy, or because A still has a board, is a failure. Leaving `session.json` on A so the next command repeats the hole is a failure.
  - **Boundary Category**: Empty session still falls back to the branch (existing behavior). Non-`feat/` / unresolved branch with a valid session id may keep the session id.

- **AO-024-03** *(Ref: AC-ADHOC-024-03, US-024-02)*: Meso claim and already-complete key the worktree session.
  - **Happy Path**: After worktree claim/copy, and after `MESO_ALREADY_COMPLETE` inside that worktree, `.deviate/session.json` `active_issue_id` equals the claimed issue.
  - **Error Category**: Copying a previous main-repo session into the worktree and returning on already-complete without rewriting the id is a failure.
  - **Boundary Category**: API / architecture / CHANGELOG update in the same implementation commit. ISS-ADH-023 pinned lookup uses the re-keyed issue. No extra agent calls.

## Edge Cases and Boundaries

- GH-54 "no `tasks.md` for the leftover issue" remains covered; this slice also covers leftover issue *with* a board plus a different branch issue.
- Epic-prefix ids (`001-006`) and `ISS-*` / `ISS-ADH-*` ids share the same re-key rule.
- A session id that matches the branch is left unchanged (not a stale id).
- Pinned `deviate micro run TSK-NNN-NN` must use the re-keyed issue so a leftover session cannot bind a sibling COMPLETED row (compose with ISS-ADH-023).
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: ≤ 500ms CLI init; re-key plus one `session.json` write is in-process ledger/`tasks.md` work already paid by resolve, ≤ 50ms extra on the dispatch path (no extra agent call).
- Throughput: no additional agent calls versus today's `_resolve_task_context` / `_meso_run`. Full test suite remains < 30s; tests that would drive `_run_pytest` must mock `deviate.cli.micro._run_pytest`.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_cli/test_micro.py::TestResolveTaskContextUsesBranch::test_stale_session_issue_rekeys_to_branch_issue` — keep the GH-54 pin (leftover issue has no board).
  - `tests/unit/test_cli/test_micro.py` — new pin: leftover session issue *has* a `tasks.md`, branch maps to a different issue with unchecked tasks → `_resolve_task_context(None, root)` returns the branch issue's pending task and `session.json` is rewritten.
  - `tests/unit/test_meso/test_meso_resume.py` — `MESO_ALREADY_COMPLETE` with a leftover `active_issue_id` writes the claimed issue into the worktree session.
- **Integration Sandbox Targets**:
  - `tests/unit/test_cli/test_micro.py` or `tests/unit/test_micro/test_run.py` — CLI `deviate micro run` in a `tmp_git_repo` feature-branch checkout whose session names a previous issue and whose branch issue `tasks.md` has unchecked tasks: stdout must not contain `NO_PENDING_TASKS`; resolved/dispatched `issue_id` is the branch issue. Mock `_run_pytest` and the agent cycle so the suite stays under 30s.
  - `tests/unit/test_meso/test_meso_orchestration.py` — worktree claim/copy leaves the *worktree* `.deviate/session.json` keyed to the claimed issue, not the previous main-repo id.

## Demonstration Path

```bash
# Mocked resolve + meso session pins (no live agent, no un-mocked pytest)
uv run pytest tests/unit/test_cli/test_micro.py tests/unit/test_meso/test_meso_resume.py tests/unit/test_meso/test_meso_orchestration.py -q -k "stale_session or rekey or ALREADY_COMPLETE or worktree"
```
