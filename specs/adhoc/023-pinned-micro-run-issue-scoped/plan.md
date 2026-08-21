## Plan Summary
- **Issue**: ISS-ADH-023 — Scope pinned micro run TASK_ID to the active issue
- **Implementation Strategy**: Stop `_find_task_record` from returning a sibling `preferred` row when the active issue is known. Reuse `_find_all_pending_tasks` to synthesize this issue's PENDING task from `tasks.md`, and refuse `TASK_ALREADY_DONE` unless the resolved record belongs to that issue.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-3 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/023-pinned-micro-run-issue-scoped.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it scopes pinned `micro run <task-id>` to the active issue.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase state and the TDD runner)

## Acceptance Contract

**Scenario AC-PLAN-001: Dispatch this issue's PENDING pin instead of a sibling COMPLETED row**
- **Source Outline**: `AO-023-01`
- **Upstream Traceability**: `US-023-01`, `FR-ADHOC-023`, `AC-ADHOC-023-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_find_task_record`; `src/deviate/cli/micro.py:_run_single`
- **Given**: A feature-branch worktree lists unchecked `TSK-001-04` in this issue's `tasks.md`, this issue has no JSONL row for that id, and a sibling ledger holds COMPLETED `TSK-001-04`.
- **When**: The operator runs `deviate micro run TSK-001-04` in that worktree.
- **Then**: The runner resolves a PENDING record with this issue's `issue_id` and dispatches it, and the output does not contain `TASK_ALREADY_DONE`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep bare and --all scans on this issue's pending queue**
- **Source Outline**: `AO-023-01`
- **Upstream Traceability**: `US-023-01`, `FR-ADHOC-023`, `AC-ADHOC-023-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_find_all_pending_tasks`; `src/deviate/cli/micro.py:_resolve_task_context`
- **Given**: The same sibling COMPLETED `TSK-001-04` exists and this issue lists that id unchecked in `tasks.md`.
- **When**: The operator runs bare `deviate micro run` or `deviate micro run --all`.
- **Then**: The scan selects this issue's first pending task and ignores sibling ledgers.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Return this issue's record or a synthesized PENDING when the branch issue is known**
- **Source Outline**: `AO-023-02`
- **Upstream Traceability**: `US-023-01`, `FR-ADHOC-023`, `AC-ADHOC-023-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_find_task_record`; `tests/test_micro/test_e2e.py:test_find_task_record_prefers_branch_issue`
- **Given**: `_resolve_issue_id_from_branch` returns `001-002`, a sibling ledger has COMPLETED `TSK-001-04`, and `001-002` has zero JSONL rows for that id.
- **When**: `_find_task_record(root, "TSK-001-04")` or `_resolve_task_context("TSK-001-04", root)` runs.
- **Then**: The hit is a `001-002` record or a synthesized PENDING with `issue_id=001-002`, never the sibling COMPLETED row.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Raise TASK_NOT_FOUND when this issue does not list the TSK**
- **Source Outline**: `AO-023-02`
- **Upstream Traceability**: `US-023-01`, `FR-ADHOC-023`, `AC-ADHOC-023-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_task_context`
- **Given**: The active issue is known, this issue's `tasks.md` and JSONL omit the pinned id, and a sibling ledger still has that id.
- **When**: The operator pins `deviate micro run TSK-001-04` or `_resolve_task_context` looks up that id.
- **Then**: The command prints `TASK_NOT_FOUND` and exits 1, and it does not bind the sibling row.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep unscoped same-id lookup when no active issue resolves**
- **Source Outline**: `AO-023-02`
- **Upstream Traceability**: `US-023-01`, `FR-ADHOC-023`, `AC-ADHOC-023-02`
- **Current-Code Evidence**: `tests/test_cli/test_micro.py:TestFindTaskRecord`; `src/deviate/cli/micro.py:_find_task_record`
- **Given**: A test uses `tmp_path` with no feature branch and no resolvable `active_issue_id`.
- **When**: `_find_task_record` looks up a TSK that exists as one latest record.
- **Then**: The helper still returns that same-id record, and only a known active issue is forbidden from receiving another issue's row.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Keep TASK_ALREADY_DONE for this issue's own terminal status**
- **Source Outline**: `AO-023-03`
- **Upstream Traceability**: `US-023-02`, `FR-ADHOC-023`, `AC-ADHOC-023-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_single`; `tests/test_micro/test_run.py:test_run_skips_already_completed_task`
- **Given**: The session `current_phase` is `IDLE` and this issue's latest status is `COMPLETED`, `REFACTOR`, `JUDGE`, or `YELLOW`.
- **When**: The operator runs `deviate micro run` with that same TSK.
- **Then**: The runner prints `TASK_ALREADY_DONE` and exits 0.
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Refuse TASK_ALREADY_DONE for a foreign COMPLETED record**
- **Source Outline**: `AO-023-03`
- **Upstream Traceability**: `US-023-02`, `FR-ADHOC-023`, `AC-ADHOC-023-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_single`
- **Given**: The session `current_phase` is `IDLE` and the resolved record's `issue_id` differs from the active branch or re-keyed session issue.
- **When**: `_run_single` evaluates the terminal-status guard.
- **Then**: The runner does not print `TASK_ALREADY_DONE`; it re-resolves this issue's task or raises `TASK_NOT_FOUND`.
- **Verification Mode**: automated

**Scenario AC-PLAN-008: Document that pinned TSK ids are a per-issue namespace**
- **Source Outline**: `AO-023-03`
- **Upstream Traceability**: `US-023-02`, `FR-ADHOC-023`, `AC-ADHOC-023-03`
- **Current-Code Evidence**: `specs/DeviaTDD-api.md:deviate micro run [task-id]`; `specs/DeviaTDD-architecture.md:Execution Engine`
- **Given**: The lookup and `_run_single` guard land in one implementation commit.
- **When**: GREEN writes the issue-scoped pin.
- **Then**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` state that pinned `micro run <task-id>` is issue-scoped and same-number TSK ids stay a per-issue namespace.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Own the pinned lookup and the `TASK_ALREADY_DONE` guard.
  - **Current State**: `_find_task_record` returns the branch-issue row when one exists, then falls back to `preferred` (first same-id record from any issue). `_resolve_task_context` on a pinned `task_id` returns that hit with no `tasks.md` synthesis. `_find_all_pending_tasks` already skips `rec_issue != issue_id` and synthesizes PENDING from this issue's `tasks.md`. `_run_single` prints `TASK_ALREADY_DONE` on IDLE plus `{COMPLETED, REFACTOR, JUDGE, YELLOW}` with no `issue_id` check. `_collect_latest_task_records` already keys `(issue_id, tid)`.
  - **Changes Required**: When the active issue is known (branch via `_resolve_issue_id_from_branch`, else `session.active_issue_id` after the existing GH-54 re-key), `_find_task_record` must not return a record whose `issue_id` differs. On a miss, `_resolve_task_context` must reuse `_find_all_pending_tasks(root, issue_id=active)` to pick this issue's synthesized PENDING, or raise `TASK_NOT_FOUND`. `_run_single` may take the `TASK_ALREADY_DONE` exit only when the resolved record belongs to the active issue. Do not fork a second scanner. Do not revert `_collect_latest_task_records` to id-only dedup. Do not change TSK id format. Leave bare / `--all` on the existing issue-id filter unless a shared helper is required. `execute post` keeps calling `_find_task_record`; the scoped lookup must not complete a sibling task.
  - **Integration Surface**: `_resolve_issue_id_from_branch`; `SessionState.active_issue_id`; `_find_all_pending_tasks`; `_resolve_pending_feedback_task`; `_run_all`; `run_command`.

- **tests/test_micro/test_e2e.py**: Extend the branch-preference pin to the empty-ledger hole.
  - **Current State**: `test_find_task_record_prefers_branch_issue` seeds both issues with JSONL rows, so the branch hit exists and `preferred` is unused.
  - **Changes Required**: Add or extend a case: sibling COMPLETED `TSK-001-04`, active issue has zero ledger rows, branch checkout of the pending issue. The hit must be this issue (synthesized PENDING or `None`), never the sibling COMPLETED row. Use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>`.
  - **Integration Surface**: `_find_task_record`; `_resolve_issue_id_from_branch`.

- **tests/test_cli/test_micro.py**: Unit-pin scoped lookup and keep unscoped latest-status tests green.
  - **Current State**: `TestFindTaskRecord` uses `tmp_path` with one issue and no feature branch. Those tests must keep returning the single same-id record.
  - **Changes Required**: Add a unit pin that two issues share `TSK-005-07` and a known branch issue returns only that issue's record (or `None` / synthesized PENDING), never the foreign COMPLETED row. Keep `test_find_task_record_returns_latest_status` and `test_find_task_record_multiple_entries_returns_last` green.
  - **Integration Surface**: `_find_task_record`; `_resolve_task_context`.

- **tests/test_micro/test_run.py**: CLI-pin the skip hole and keep same-issue `TASK_ALREADY_DONE`.
  - **Current State**: `test_run_skips_already_completed_task` and `test_task_already_done_triggers_for_judge_latest` pin IDLE plus this issue's COMPLETED / JUDGE exit 0.
  - **Changes Required**: Add a CLI pin: `deviate micro run TSK-001-04` in a `tmp_git_repo` feature-branch worktree whose `tasks.md` lists the TSK and whose JSONL is empty, while a sibling ledger is COMPLETED. Output must not contain `TASK_ALREADY_DONE`. Dispatch / resolve uses the branch `issue_id`. Mock `deviate.cli.micro._run_pytest` and the agent cycle. Keep the same-issue already-done tests green.
  - **Integration Surface**: `_run_single`; `_resolve_task_context`; `cli`.

- **specs/DeviaTDD-api.md**: State that pinned `micro run <task-id>` is issue-scoped.
  - **Current State**: The Single-Task paragraph resolves a task by `TSK-NNN-NN` and does not say same-number ids are a per-issue namespace. `--all` is already described as issue-scoped.
  - **Changes Required**: Document that a pinned id stays in the active issue's namespace. A sibling COMPLETED row for the same number is not a hit. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` Execution Engine.

- **specs/DeviaTDD-architecture.md**: Same contract on the per-task dispatcher.
  - **Current State**: Execution Engine says `deviate micro run <task-id>` resolves a task by its `TSK-NNN-NN` identifier from the ledger.
  - **Changes Required**: Add that resolution is issue-scoped when the branch or re-keyed session issue is known. Same-number TSK ids remain a per-issue namespace. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` Single-Task paragraph.

- **CHANGELOG.md**: Record the user-visible runner fix.
  - **Current State**: `[Unreleased]` already notes `(issue_id, task_id)` dedup and branch preference when both ledgers have rows.
  - **Changes Required**: Append one `[Unreleased]` bullet: pinned `deviate micro run <task-id>` no longer treats a sibling COMPLETED same-number TSK as `TASK_ALREADY_DONE` when this issue is still PENDING.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: Issue-scoped lookup and PENDING synthesis
  - **Files**: `src/deviate/cli/micro.py`, `tests/test_micro/test_e2e.py`, `tests/test_cli/test_micro.py`
  - **Approach**: Share the existing GH-54 active-issue resolution (branch wins when the session issue has no tasks board). When that issue is known, `_find_task_record` returns only a matching `issue_id` row and never `preferred`. If the JSONL miss happens on a pinned id, `_resolve_task_context` calls `_find_all_pending_tasks(root, issue_id=active)` and returns the matching synthesized PENDING, or prints `TASK_NOT_FOUND` and exits 1. Tests without a resolvable issue keep the current single-record fallback. Do not rewrite `_collect_latest_task_records`.
  - **Verification**: `uv run pytest tests/test_micro/test_e2e.py tests/test_cli/test_micro.py -q -k "find_task_record or TASK_NOT_FOUND or prefers_branch"`

- **Phase 2**: Issue-owned `TASK_ALREADY_DONE` and CLI pin
  - **Files**: `src/deviate/cli/micro.py`, `tests/test_micro/test_run.py`
  - **Approach**: In `_run_single`, compare `task["issue_id"]` to the active issue before the IDLE + terminal-status exit. A foreign record must re-resolve this issue or raise `TASK_ALREADY_DONE` is forbidden; use `TASK_NOT_FOUND` when this issue has no matching pending or ledger row. Add the sibling-COMPLETED CLI pin. Mock `_run_pytest` and `_invoke_agent`. Keep `test_run_skips_already_completed_task` and `test_task_already_done_triggers_for_judge_latest` green.
  - **Verification**: `uv run pytest tests/test_micro/test_run.py -q -k "already_done or TASK_ALREADY_DONE or pinned or TSK-001-04"`

- **Phase 3**: Specs and changelog
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: In the same implementation commit, document that pinned `micro run <task-id>` is issue-scoped and that `TSK-NNN-NN` is a per-issue namespace. Append the `[Unreleased]` bullet. Do not author Product-layer flows.
  - **Verification**: `uv run pytest tests/test_micro/test_e2e.py tests/test_micro/test_run.py tests/test_cli/test_micro.py -q -k "find_task_record or TASK_ALREADY_DONE or already_done or pinned"`

## Data Flow Analysis
- **Inputs**: Pinned `task_id`; branch from `_git_branch` / `_resolve_issue_id_from_branch`; `SessionState.active_issue_id`; latest rows from `_collect_latest_task_records`; this issue's `tasks.md` via `_find_all_pending_tasks`.
- **Transform**: Known active issue filters ledger hits to that `issue_id`. A JSONL miss becomes a synthesized PENDING when `tasks.md` lists the id unchecked. A miss in both stores becomes `TASK_NOT_FOUND`. Foreign COMPLETED status does not enter the IDLE terminal exit.
- **Pass output**: `_run_single` dispatches this issue's PENDING (or in-progress) task. Same-issue COMPLETED / REFACTOR / JUDGE / YELLOW still prints `TASK_ALREADY_DONE` and exits 0.
- **Fail output**: Unknown format or no local match prints `TASK_NOT_FOUND` and exits 1. Output does not claim the sibling task is done.
- **Storage**: No new ledger row type. Canonical state stays sequential parse of `tasks.jsonl`. Task ids stay `TSK-NNN-NN` per issue.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Unscoped `TestFindTaskRecord` tests lose their single-record hit | High | Medium | Apply the foreign-row ban only when a branch or re-keyed session issue is known. |
| A second scanner forks `_find_all_pending_tasks` and drifts | High | Medium | Reuse `_find_all_pending_tasks` for PENDING synthesis. Do not copy the `tasks.md` parser. |
| Same-issue COMPLETED / JUDGE stops emitting `TASK_ALREADY_DONE` | High | Low | Keep the existing IDLE + terminal-set exit when `task["issue_id"]` matches the active issue. |
| `execute post` still completes a sibling via `_find_task_record` | Medium | Medium | Scope the shared lookup. Do not expand EXECUTE beyond that consistency. |
| `_collect_latest_task_records` reverts to id-only dedup | High | Low | Leave the `(issue_id, tid)` key unchanged. |
| Tests spawn un-mocked `_run_pytest` and blow the 30s budget | Medium | Medium | Mock `deviate.cli.micro._run_pytest`. Every test git call uses `cwd=<tmp_git_repo>` and `env=_git_env()`. |
| Stale `session.active_issue_id` points at the sibling | Medium | Medium | Keep GH-54: branch wins when the session issue has no tasks board here. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (`specs/**/tasks.jsonl`, `specs/**/tasks.md`, `.deviate/session.json`), subprocess (existing `_git_branch` / `git rev-parse` in `_resolve_issue_id_from_branch`).
Negative tests: sibling COMPLETED same-number TSK does not print `TASK_ALREADY_DONE` or exit 0 as done; known active issue never receives another issue's row; TSK absent from this issue's `tasks.md` and JSONL is `TASK_NOT_FOUND`; checked `[x]` with no JSONL is not invented as new work; unscoped tests without a resolvable issue still find a single same-id record.
Constraints: no new dependencies; no hardcoded secrets; no extra agent call; pinned lookup stays an in-process JSONL + `tasks.md` scan (≤ 50ms extra); do not mutate operator-local `.deviate/config.toml`; do not delete branches; do not call un-mocked `_run_pytest`; do not change TSK id format.

## Integration Points
- **`_find_task_record`**: Stops `preferred` fallback when the active issue is known. Returns this issue's latest row or `None`.
- **`_find_all_pending_tasks`**: Sole PENDING synthesis path. Pinned miss reuses it. Bare / `--all` stay on this helper.
- **`_resolve_task_context`**: Pinned path applies GH-54 issue resolution, then lookup, then synthesis, then `TASK_NOT_FOUND`.
- **`_run_single`**: `TASK_ALREADY_DONE` requires `task["issue_id"]` to match the active issue.
- **`_collect_latest_task_records`**: Reference only. Keep `(issue_id, tid)` keys.
- **`_resolve_pending_feedback_task` / `execute post`**: Callers of `_find_task_record`. They inherit issue scope. Do not add EXECUTE behavior.
- **API / architecture / CHANGELOG**: Same implementation commit. Pinned `TSK-NNN-NN` is a per-issue namespace.

## Constitutional Alignment
- **Architecture**: Micro stays the TDD sandbox in the four-layer model (constitution §1). This plan does not skip a layer. Gate 2 stays absent. Append-only ledgers stay sequential-parse canonical state; task ids stay namespaced per issue.
- **Testing**: pytest under `tests/` with `tmp_git_repo` and `_git_env()` (constitution §3). GREEN must pass the suite. Coverage target ≥ 80%. Full suite stays under 30s. No un-mocked `_run_pytest`.
- **Git Isolation**: Work stays on `feat/adhoc/023-pinned-micro-run-issue-scoped`. Production git uses `git_env`. This issue does not delete branches.
- **Product Layer**: Issue `flow_refs` is `[]`. Downstream artifacts keep empty flow references. This plan does not author or sync Product-layer flows.
