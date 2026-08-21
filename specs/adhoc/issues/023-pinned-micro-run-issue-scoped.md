---
title: "Scope pinned micro run TASK_ID to the active issue"
labels: [bugfix, adhoc, vertical-slice, micro]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-023
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/023-pinned-micro-run-issue-scoped.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py::_find_task_record` — TARGET: stop falling back to `preferred` (first same-id record from any issue) when the branch/session issue is known. A missing ledger row for the active issue is not a license to return a sibling's COMPLETED `TSK-NNN-NN`.
  - `src/deviate/cli/micro.py::_resolve_task_context` — TARGET: pinned `task_id` must stay issue-scoped the same way the `task_id is None` path already scopes `_find_all_pending_tasks(root, issue_id=issue_id)`. When the active issue has no JSONL row, synthesize PENDING from that issue's `tasks.md` (same helper `_find_all_pending_tasks` already uses) or raise `TASK_NOT_FOUND` for this issue.
  - `src/deviate/cli/micro.py::_run_single` — TARGET: before the IDLE + `{COMPLETED, REFACTOR, JUDGE, YELLOW}` `TASK_ALREADY_DONE` exit, verify `task["issue_id"]` equals the active branch/session issue. A foreign COMPLETED record must not terminate the run.
  - `src/deviate/cli/micro.py::_find_all_pending_tasks` — REFERENCE: already skips `rec_issue != issue_id` and synthesizes PENDING from the issue's `tasks.md`. Reuse; do not fork a second scanner. Bare `deviate micro run` / `--all` stay on this path.
  - `src/deviate/cli/micro.py::_resolve_issue_id_from_branch` / `SessionState.active_issue_id` — REFERENCE: same stale-session / branch-authoritative rules already used by unscoped `_resolve_task_context`.
  - `src/deviate/cli/micro.py::_collect_latest_task_records` — REFERENCE: already keys `(issue_id, tid)`. Do not revert to id-only dedup.
  - `tests/test_micro/test_e2e.py` — TARGET: extend `test_find_task_record_prefers_branch_issue` with the hole: sibling COMPLETED, active issue has zero ledger rows for that TSK, branch checkout of the pending issue.
  - `tests/test_micro/test_run.py` — TARGET: CLI pin that `deviate micro run TSK-001-04` in the pending-issue worktree does not emit `TASK_ALREADY_DONE` / exit 0.
  - `tests/test_cli/test_micro.py` — TARGET: unit pin that `_find_task_record` returns None (or a synthesized PENDING for the active issue), never the foreign COMPLETED row.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document that pinned `micro run <task-id>` is issue-scoped; same-number TSK ids are per-issue namespaces.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible runner fix.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - Worktree for issue `001-002` (`specs/001-phone-to-pi-relay/002-node-pairing-and-presence/tasks.jsonl`) had no `TSK-001-04` row.
  - Issue `001-001` ledger contained COMPLETED `TSK-001-04` (`issue_id: 001-001`, different description).
  - `deviate micro run TSK-001-04` printed `TASK_ALREADY_DONE TSK-001-04 is already completed` and exited 0.
  - Bare `deviate micro run` (issue-scoped pending scan) then ran the real `001-002` task.
  - `session.current_phase == IDLE` satisfied the `_run_single` terminal guard.

## The Problem Contract

Pinned `deviate micro run <TASK_ID>` can resolve a sibling issue's COMPLETED row for the same TSK number and exit 0 as `TASK_ALREADY_DONE` while this worktree's task is still PENDING with an empty ledger. Operators need the pinned path to be issue-scoped the same way the bare / `--all` pending scan already is.

## Scope Boundaries

### Hard Inclusions

- When the active issue is known (branch slug via `_resolve_issue_id_from_branch`, else `session.active_issue_id` after the existing stale-session re-key), `_find_task_record` / `_resolve_task_context` must not return a record whose `issue_id` differs from that active issue.
- Missing JSONL row for this issue + TSK listed (unchecked) in this issue's `tasks.md` → treat as this issue's PENDING task (reuse `_find_all_pending_tasks` synthesis), never as a sibling COMPLETED.
- Missing JSONL row and TSK absent from this issue's `tasks.md` → `TASK_NOT_FOUND` for this issue, not a foreign hit.
- `_run_single` may print `TASK_ALREADY_DONE` and exit 0 only when the resolved record belongs to the active issue and that issue's latest status is in the existing terminal set. Defense in depth even if lookup is fixed.
- Bare `deviate micro run` and `deviate micro run --all` remain issue-scoped; change them only if needed to keep the same issue-id filter.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for any git; mock `deviate.cli.micro._run_pytest` when a CLI path would spawn it.

### Defensive Exclusions

- Do **not** reopen GH #63 / #65 / #74 (ISS-ADH-020 evidence gate, ISS-ADH-021 SHA / GREEN-entry, ISS-ADH-022 already_satisfied files) except to compose. This slice is lookup scoping only.
- Do **not** change TSK id format or make task ids globally unique; per-issue reuse of `TSK-NNN-NN` stays.
- Do **not** rewrite `_collect_latest_task_records` back to id-only dedup.
- Do **not** delete branches, mutate operator-local `.deviate/config.toml`, or author/synchronize Product-layer flows (`flow_refs: []`).
- Do **not** change the unscoped lookup used by unit tests that have no feature branch / no active issue, except that a *known* active issue must never receive a foreign record.
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** treat a missing Product-layer flow as work.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-023`
- **Acceptance Criteria Tokens**: `AC-ADHOC-023-01`, `AC-ADHOC-023-02`, `AC-ADHOC-023-03`
- **Data Model Entities**: `TaskRecord.id`, `TaskRecord.issue_id`, `SessionState.active_issue_id` — no new ledger row types
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` `_find_task_record` / `_resolve_task_context` / `_run_single`
  - `src/deviate/cli/micro.py` `_find_all_pending_tasks` (issue-scoped reference)
  - `specs/constitution.md` §1 Append-Only Ledger Protocol (canonical state by sequential parse; issue ids unique, task ids namespaced per issue)

## User Stories Ledger

- **US-023-01**: As a DeviaTDD operator, I want a pinned `deviate micro run TSK-NNN-NN` to run this issue's task even when a sibling already completed the same TSK number so worktrees cannot skip PENDING work. *(Ref: FR-ADHOC-023)*
- **US-023-02**: As a DeviaTDD operator, I want `_run_single` to refuse `TASK_ALREADY_DONE` unless the resolved record belongs to the active issue so a foreign COMPLETED row cannot terminate the run. *(Ref: FR-ADHOC-023)*

## Acceptance Outline

- **AO-023-01** *(Ref: AC-ADHOC-023-01, US-023-01)*: Pinned run does not skip this issue's PENDING TSK.
  - **Happy Path**: In a worktree whose branch issue lists `TSK-001-04` in `tasks.md` with no JSONL row, while a sibling ledger has COMPLETED `TSK-001-04`, `deviate micro run TSK-001-04` resolves to this issue's PENDING task and dispatches it.
  - **Error Category**: Printing `TASK_ALREADY_DONE` and exiting 0 because of the sibling COMPLETED row is a failure of this slice.
  - **Boundary Category**: Bare `deviate micro run` / `--all` continue to pick this issue's first pending task and ignore sibling ledgers.

- **AO-023-02** *(Ref: AC-ADHOC-023-02, US-023-01)*: Lookup never returns a foreign-issue record when the active issue is known.
  - **Happy Path**: `_find_task_record(root, "TSK-001-04")` on the `001-002` branch returns the `001-002` record or a synthesized PENDING with `issue_id=001-002`.
  - **Error Category**: TSK absent from this issue's `tasks.md` and JSONL → `TASK_NOT_FOUND`; not a silent bind to `001-001`.
  - **Boundary Category**: Tests without a resolvable feature-branch issue may still find a single same-id record; the forbidden case is a *known* active issue receiving another issue's row.

- **AO-023-03** *(Ref: AC-ADHOC-023-03, US-023-02)*: `TASK_ALREADY_DONE` is issue-owned.
  - **Happy Path**: IDLE session + this issue's own COMPLETED/REFACTOR/JUDGE/YELLOW latest status still prints `TASK_ALREADY_DONE` and exits 0.
  - **Error Category**: IDLE session + foreign COMPLETED record must not take that exit; re-resolve to this issue or `TASK_NOT_FOUND`.
  - **Boundary Category**: API / architecture / CHANGELOG update in the same implementation commit. No extra agent calls.

## Edge Cases and Boundaries

- Same TSK number COMPLETED on this issue remains terminal; only foreign-issue COMPLETED is ignored.
- Stale `session.active_issue_id` pointing at the sibling while the branch maps to this issue must follow the existing GH-54 re-key (branch wins when the session issue has no tasks board here).
- `execute post` also calls `_find_task_record`; once lookup is issue-scoped it must not complete a sibling task. Do not expand EXECUTE behavior beyond that consistency.
- Checked `[x]` in this issue's `tasks.md` with no JSONL row stays skipped by `_find_all_pending_tasks`; pinned run of that id is not required to invent work.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: ≤ 500ms CLI init; pinned lookup is an in-process JSONL + `tasks.md` scan already paid by `_collect_latest_task_records` / `_find_all_pending_tasks`, ≤ 50ms extra on the dispatch path (no extra agent call).
- Throughput: no additional agent calls versus today's `_run_single`. Full test suite remains < 30s; tests that would drive `_run_pytest` must mock `deviate.cli.micro._run_pytest`.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_micro/test_e2e.py` — extend `test_find_task_record_prefers_branch_issue`: sibling COMPLETED `TSK-001-04` + active issue has no ledger row → hit is this issue (synthesized PENDING or None), never the sibling COMPLETED row.
  - `tests/test_cli/test_micro.py` — `_find_task_record` with two issues sharing `TSK-005-07` and a known branch issue returns only that issue's record.
  - `tests/test_micro/test_run.py` — existing same-issue `TASK_ALREADY_DONE` pins stay green (IDLE + this issue COMPLETED still exits 0).
- **Integration Sandbox Targets**:
  - `tests/test_micro/test_run.py` — CLI `deviate micro run TSK-001-04` in a `tmp_git_repo` feature-branch worktree whose issue `tasks.md` lists the TSK and whose JSONL is empty, while a sibling ledger is COMPLETED: output must not contain `TASK_ALREADY_DONE`; dispatch / resolve uses `issue_id` of the branch issue. Mock `_run_pytest` and the agent cycle so the suite stays under 30s.

## Demonstration Path

```bash
# Mocked lookup + CLI pins (no live agent, no un-mocked pytest)
uv run pytest tests/test_micro/test_e2e.py tests/test_micro/test_run.py tests/test_cli/test_micro.py -q -k "find_task_record or TASK_ALREADY_DONE or already_done or pinned"
```
