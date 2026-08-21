## Plan Summary
- **Issue**: ISS-ADH-024 — Re-key stale worktree session to the claimed branch issue
- **Implementation Strategy**: Make a known feature-branch issue beat a leftover `session.active_issue_id` on bare `deviate micro run`, `--all`, and ISS-ADH-023 pinned lookup. Persist the branch id to the worktree `.deviate/session.json`. Write that same id on meso claim and `MESO_ALREADY_COMPLETE`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/024-worktree-session-stale-issue-id.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it keys the worktree session to the claimed branch issue.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase state and `.deviate/session.json`)

## Acceptance Contract

**Scenario AC-PLAN-001: Consume the branch issue queue despite a leftover session id**
- **Source Outline**: `AO-024-01`
- **Upstream Traceability**: `US-024-01`, `FR-ADHOC-024`, `AC-ADHOC-024-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_rekey_session_issue_to_branch`; `src/deviate/cli/micro.py:_resolve_task_context`
- **Given**: The worktree sits on `feat/001-forge-layer/007-inventory-inspection` with unchecked `TSK-007-*` in that issue `tasks.md`, and `.deviate/session.json` still names `001-006`.
- **When**: The operator runs bare `deviate micro run` or `deviate micro run --all`.
- **Then**: The resolver returns the first pending `001-007` task and stdout does not contain `NO_PENDING_TASKS`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep NO_PENDING_TASKS when the branch issue queue is empty**
- **Source Outline**: `AO-024-01`
- **Upstream Traceability**: `US-024-01`, `FR-ADHOC-024`, `AC-ADHOC-024-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_task_context`
- **Given**: The branch maps to an issue whose `tasks.md` has zero unchecked tasks.
- **When**: The operator runs bare `deviate micro run`.
- **Then**: The command prints `NO_PENDING_TASKS` and exits 0.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Prefer the branch issue and rewrite session.json**
- **Source Outline**: `AO-024-02`
- **Upstream Traceability**: `US-024-01`, `FR-ADHOC-024`, `AC-ADHOC-024-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_rekey_session_issue_to_branch`; `src/deviate/state/config.py:SessionState.active_issue_id`
- **Given**: Session `active_issue_id` names issue A, A still has a `tasks.md` in this checkout, and the branch maps to issue B.
- **When**: `_resolve_task_context(None, root)` or `_resolve_known_active_issue_id(root)` runs.
- **Then**: The resolver returns B and worktree `.deviate/session.json` `active_issue_id` equals B.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep a valid session id when the branch does not resolve**
- **Source Outline**: `AO-024-02`
- **Upstream Traceability**: `US-024-01`, `FR-ADHOC-024`, `AC-ADHOC-024-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_rekey_session_issue_to_branch`; `src/deviate/cli/micro.py:_resolve_issue_id_from_branch`
- **Given**: `session.active_issue_id` is a valid issue id and `_resolve_issue_id_from_branch` returns None.
- **When**: The re-key helper runs.
- **Then**: The helper keeps the session id and does not rewrite `session.json` to a blank id.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Write the claimed issue on MESO_ALREADY_COMPLETE**
- **Source Outline**: `AO-024-03`
- **Upstream Traceability**: `US-024-02`, `FR-ADHOC-024`, `AC-ADHOC-024-03`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_meso_run`
- **Given**: `_meso_run` is inside the worktree with leftover `active_issue_id` and `resume_state` is `COMPLETE`.
- **When**: The command prints `MESO_ALREADY_COMPLETE` and returns.
- **Then**: Worktree `.deviate/session.json` `active_issue_id` equals the claimed issue.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Key the worktree session on meso claim**
- **Source Outline**: `AO-024-03`
- **Upstream Traceability**: `US-024-02`, `FR-ADHOC-024`, `AC-ADHOC-024-03`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_claim_and_setup`; `src/deviate/cli/meso.py:_meso_run`
- **Given**: The main-repo session still names a previous issue and `_meso_run` claims a new worktree.
- **When**: SPECIFY copies `.deviate/` into that worktree.
- **Then**: The worktree `.deviate/session.json` `active_issue_id` equals the claimed issue.
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Scope pinned TSK lookup to the re-keyed issue**
- **Source Outline**: `AO-024-03`
- **Upstream Traceability**: `US-024-01`, `FR-ADHOC-024`, `AC-ADHOC-024-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_known_active_issue_id`; `src/deviate/cli/micro.py:_synthesize_pinned_pending`
- **Given**: Session names leftover issue A, the branch maps to issue B, and both issues share a TSK number.
- **When**: The operator runs `deviate micro run TSK-NNN-NN`.
- **Then**: Pinned lookup uses B as the active issue and does not bind A's COMPLETED row.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Own the branch-authoritative re-key and persist it.
  - **Current State**: `_rekey_session_issue_to_branch` returns the branch only when the leftover session issue has no `tasks.md`. When a board exists it keeps the leftover id. It never writes `session.json`. `_resolve_task_context` and `_resolve_known_active_issue_id` call that helper. `_run_all` still reads raw `session.active_issue_id` and falls back to the branch only when the session id is empty.
  - **Changes Required**: When `_resolve_issue_id_from_branch` returns an id that differs from `session.active_issue_id`, the branch id wins even if the leftover issue still has a `tasks.md`. Persist the authoritative id via `SessionState.save` to `.deviate/session.json`. Route bare resolve, `--all`, and `_resolve_known_active_issue_id` through the same helper. Keep `test_stale_session_issue_rekeys_to_branch_issue`. Cover epic-prefix ids (`001-006` / `001-007`) and `ISS-*`. Do not add session fields. Do not unify `micro._resolve_issue_id_from_branch` with `_common.resolve_issue_id_from_branch` unless a lookup mismatch blocks this slice.
  - **Integration Surface**: `_resolve_issue_id_from_branch`; `_find_all_pending_tasks`; `_synthesize_pinned_pending`; `SessionState.save`; `_run_all`.

- **src/deviate/cli/meso.py**: Key the worktree session on claim and on already-complete.
  - **Current State**: `_claim_and_setup` sets `session.active_issue_id = issue_id` then copies `.deviate/` into the worktree. `_meso_run` copies `.deviate/` first. On `resume_state == "COMPLETE"` it prints `MESO_ALREADY_COMPLETE` and returns before `session.active_issue_id = issue_id`.
  - **Changes Required**: On `MESO_ALREADY_COMPLETE`, still write `session.active_issue_id` to the claimed issue in the worktree session. After `.deviate/` copy, the worktree session must name the claimed issue. Keep the `_claim_and_setup` write-then-copy order. Prefer write-then-copy, or rewrite the worktree session after copy.
  - **Integration Surface**: `_resolve_meso_worktree`; `_specify_pre`; `SessionState.save`.

- **src/deviate/state/config.py**: Persist `active_issue_id` with the existing field.
  - **Current State**: `SessionState.active_issue_id` is optional. `save` writes `.deviate/session.json`.
  - **Changes Required**: Do not add fields. Reuse `save` from the re-key and meso write sites.
  - **Integration Surface**: `SessionState.load`; `SessionState.save`.

- **tests/test_cli/test_micro.py**: Pin the stronger mismatch plus persist.
  - **Current State**: `TestResolveTaskContextUsesBranch.test_stale_session_issue_rekeys_to_branch_issue` covers GH-54 (leftover issue has no board).
  - **Changes Required**: Keep that pin. Add a case where leftover issue A has a `tasks.md`, branch maps to B with unchecked tasks, `_resolve_task_context(None, root)` returns B's pending task, and `session.json` equals B. Add a CLI pin for bare `deviate micro run` that does not print `NO_PENDING_TASKS`. Use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>`. Mock `deviate.cli.micro._run_pytest` and the agent cycle.
  - **Integration Surface**: `_resolve_task_context`; `_rekey_session_issue_to_branch`; `_resolve_known_active_issue_id`.

- **tests/test_meso/test_meso_resume.py**: Pin already-complete session rewrite.
  - **Current State**: `test_valid_plan_and_tasks_skip_both_phases` asserts `MESO_ALREADY_COMPLETE` and skips agents. It does not check `active_issue_id`.
  - **Changes Required**: Seed a leftover `active_issue_id`. After `_meso_run` returns `MESO_ALREADY_COMPLETE`, assert worktree `session.json` equals the claimed issue.
  - **Integration Surface**: `_meso_run`; `SessionState.load`.

- **tests/test_meso/test_meso_orchestration.py**: Pin worktree claim/copy session key.
  - **Current State**: `test_meso_specific_issue` asserts main-repo session `active_issue_id` after a full run. It does not assert the copied worktree session after claim.
  - **Changes Required**: Assert the worktree `.deviate/session.json` equals the claimed issue after claim/copy, not the previous main-repo id. Mock `deviate.cli.micro._run_pytest`.
  - **Integration Surface**: `_meso_run`; `_claim_and_setup`.

- **specs/DeviaTDD-api.md**: State that a known branch issue beats a leftover session id.
  - **Current State**: Queue drain resolves from `session.active_issue_id` and falls back to the branch only when the session is empty.
  - **Changes Required**: Document that a known `feat/{bucket}/{slug}` issue beats a leftover session id. Document that meso claim and `MESO_ALREADY_COMPLETE` rewrite the worktree session. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` §10.

- **specs/DeviaTDD-architecture.md**: Align §10 with the conflicting-session rule.
  - **Current State**: §10 says the active issue comes from `session.active_issue_id`, then branch fallback when the session is empty.
  - **Changes Required**: State that a conflicting leftover session yields to the known feature-branch issue. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` Queue Drain.

- **CHANGELOG.md**: Record the remaining sticky-id plus meso write fix.
  - **Current State**: `[Unreleased]` already has a GH-54 bullet for the no-board re-key only.
  - **Changes Required**: Append an `[Unreleased]` bullet for leftover ids that still have a board, plus the meso claim / already-complete session write.
  - **Integration Surface**: user-visible `deviate micro run` / `deviate meso run` session behavior.

## Implementation Strategy
- **Phase 1**: RED pins for re-key, persist, and meso session write
  - **Files**: `tests/test_cli/test_micro.py`, `tests/test_meso/test_meso_resume.py`, `tests/test_meso/test_meso_orchestration.py`
  - **Approach**: Keep `test_stale_session_issue_rekeys_to_branch_issue`. Add the leftover-with-board persist pin. Add `MESO_ALREADY_COMPLETE` leftover-id rewrite. Add worktree claim/copy keyed to the claimed issue. Mock `_run_pytest` and the agent cycle.
  - **Verification**: `uv run pytest tests/test_cli/test_micro.py tests/test_meso/test_meso_resume.py tests/test_meso/test_meso_orchestration.py -q -k "stale_session or rekey or ALREADY_COMPLETE or worktree"` fails on the new pins.

- **Phase 2**: GREEN branch-authoritative re-key and persist
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/state/config.py`
  - **Approach**: Change `_rekey_session_issue_to_branch` so a known branch id beats a different session id even when the leftover issue has a `tasks.md`. Write `SessionState.active_issue_id` when the authoritative id differs. Call the same helper from `_resolve_task_context`, `_resolve_known_active_issue_id`, and `_run_all`. Empty session still falls back to the branch. Unresolved branch keeps a valid session id.
  - **Verification**: New micro pins pass. GH-54 no-board pin stays green. Empty-queue `NO_PENDING_TASKS` stays exit 0.

- **Phase 3**: GREEN meso session key
  - **Files**: `src/deviate/cli/meso.py`
  - **Approach**: Before `MESO_ALREADY_COMPLETE` returns, set `session.active_issue_id` to the claimed issue and save the worktree session. After `.deviate/` copy, rewrite the worktree session if the copied file still names the previous issue. Keep `_claim_and_setup` write-then-copy.
  - **Verification**: Meso resume and orchestration pins pass.

- **Phase 4**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Update Queue Drain and §10 so a known branch issue beats a leftover session id. Record meso claim / already-complete rewrite. Append the `[Unreleased]` bullet in the same implementation commit.
  - **Verification**: Docs name the branch-authoritative rule. `mise run check` stays green.

## Data Flow Analysis
- **Input**: Worktree git branch (`feat/{bucket}/{slug}`), leftover `.deviate/session.json` `active_issue_id`, `specs/issues.jsonl` `source_file`, and the branch issue `tasks.md`.
- **Transform**: `_resolve_issue_id_from_branch` maps the branch slug to `IssueRecord.issue_id`. `_rekey_session_issue_to_branch` compares that id to `SessionState.active_issue_id`. When both are known and differ, the branch id becomes the active issue.
- **Output**: Bare `deviate micro run` and `--all` scan `_find_all_pending_tasks` for the branch issue. Pinned `TSK-NNN-NN` uses `_resolve_known_active_issue_id` so ISS-ADH-023 stays on the re-keyed issue.
- **Storage**: `SessionState.save` writes the authoritative id to worktree `.deviate/session.json`. Meso claim copies `.deviate/` only after that write, or rewrites the worktree file after copy. `MESO_ALREADY_COMPLETE` performs the same write before return.
- **Empty queue**: When the branch issue has no pending tasks, `_resolve_task_context` still prints `NO_PENDING_TASKS` and exits 0.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Existing tests assume a leftover session id wins when that issue still has a `tasks.md` | Medium | Medium | Update only the GH-54 stronger-mismatch contract. Keep empty-session fallback and unresolved-branch keep-session pins. |
| `_run_all` keeps reading raw `session.active_issue_id` after `_resolve_task_context` is fixed | High | High | Route `--all` through the same re-key helper in Phase 2. |
| `_meso_run` copytree overwrites a later main-repo write, or COMPLETE returns before any write | High | High | Write the claimed id before copy, or rewrite the worktree session after copy and on COMPLETE. |
| Dual slug parsers (`micro._resolve_issue_id_from_branch` vs `_common.resolve_issue_id_from_branch`) diverge | Low | Low | Reuse the existing micro helper on the micro path. Unify only if a lookup mismatch blocks this slice. |
| Un-mocked `_run_pytest` blows the 30s suite budget | High | Medium | Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` on every CLI path that would spawn it. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (worktree `.deviate/session.json` rewrite)
Negative tests: unresolved non-`feat/` branch does not blank a valid session id; re-key does not invent an issue id; leftover board on issue A does not keep A when the branch maps to B
Constraints: no new dependencies; no new `SessionState` fields; no hardcoded secrets; no un-mocked `_run_pytest`; no branch deletion; no operator-local `.deviate/config.toml` mutation

## Integration Points
- **`_resolve_issue_id_from_branch` / `resolve_issue_id_from_branch`**: Existing `feat/{bucket}/{slug}` → `specs/issues.jsonl` `source_file` lookup. This slice reuses it. It does not add a second slug parser.
- **`SessionState.active_issue_id`**: Single cache field. Re-key and meso claim/complete write the claimed or branch issue into the worktree file.
- **ISS-ADH-023 pinned lookup**: `_resolve_known_active_issue_id` must return the re-keyed branch issue so a leftover session cannot bind a sibling COMPLETED row.
- **`_find_all_pending_tasks`**: Bare run and `--all` scan only the authoritative issue. `NO_PENDING_TASKS` stays legal only for that issue's empty queue.
- **API / architecture §10**: Same-commit contract that a conflicting leftover session yields to the known feature-branch issue.

## Constitutional Alignment
- **Architecture**: Meso claim and Micro queue resolve stay in C1. The change preserves Git Isolation (constitution §1) by keying each worktree session to the claimed issue. Session Continuity still uses `.deviate/session.json` (constitution §2) with no new ledger row types.
- **Testing**: pytest unit and CLI pins under `tests/`. RED writes failing pins first. GREEN changes only `src/` plus the listed spec and changelog files. Tests use `tmp_git_repo` and `_git_env()`. Coverage target remains >= 80%.
- **Git Isolation**: Work stays on the pre-configured issue worktree. Micro agents do not run branch-mutating git. The slice never deletes a branch.
- **Product Layer**: `flow_refs` stays `[]`. The change keeps C1 session ownership. It does not author or index Product-layer flows.
