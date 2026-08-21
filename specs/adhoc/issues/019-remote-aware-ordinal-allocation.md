---
title: "Allocate Issue and Epic Ordinals from Remote Feat Branches"
labels: [enhancement, adhoc, vertical-slice, git, cli]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-019
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/019-remote-aware-ordinal-allocation.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/macro.py::_compute_next_issue_id` — TARGET: stop using only `max(local ledger) + 1`. Fold in `origin/main` ledger ordinals and remote `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*` refs. Parse `ISS-ADH-NNN` and `ISS-NNN` as the same adhoc series (today `iid.split("-")[1]` skips `ISS-ADH-017`).
  - `src/deviate/core/epic.py::_find_next_epic_num` / `allocate_feature_bucket` — TARGET: next epic number is `max(local numbered specs dirs ∪ remote feat/<NNN>-* prefixes) + 1`, not local dirs only.
  - Shared helper (prefer `src/deviate/core/epic.py` or a small sibling module, not a second counter) — TARGET: collect remote-tracking ordinals via `git for-each-ref` on already-fetched `origin` (optional `git fetch --prune`); every git subprocess uses `deviate.core._shared.git_env`.
  - `src/deviate/cli/meso.py::_try_claim_issue` — TARGET: when `git push` of `feat/.../NNN-*` is rejected because the name exists, increment the ordinal and retry. Do not fall back to `--local` to win the collision. Keep `claim_remote = false` / explicit `--local` as the optional skip from ISS-ADH-017 (optional-push-as-lock / GH #64).
  - `src/deviate/prompts/commands/deviate-adhoc.md` — TARGET: tell the adhoc compiler to use the same remote-aware counter (not `max(local ledger)+1`) so agent-written `specs/adhoc/issues/{NNN}-{slug}.md` cannot mint a duplicate `017`.
  - `tests/test_cli/test_macro_contracts.py` — TARGET: pin adhoc next-id when origin has `feat/adhoc/017-*` and the local ledger does not.
  - `tests/test_core/test_epic.py` — TARGET: pin `allocate_feature_bucket` against remote epic prefixes.
  - Meso claim tests (`tests/test_cli/test_meso.py` / `tests/test_meso/test_specify.py`) — TARGET: push name-collision increments and retries; no `--local` fallback.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document remote-aware ordinal allocation and push-as-claim retry in the same implementation commit.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible allocation change.
- **Classification for plan/tasks**: allocator + claim-retry is production Python with observable fail-to-pass behavior. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices; this slice does not change that classifier.
- **Upstream Evidence**:
  - GH #59 `feat/adhoc/017-two-counter-tdd-retry` and GH #64 `feat/adhoc/017-optional-push-as-lock` both allocated **017**.
  - `src/deviate/cli/macro.py` `_compute_next_issue_id` (local ledger max; two-part id parse).
  - `src/deviate/core/epic.py` `_find_next_epic_num` (local `specs/*` max).
  - `src/deviate/cli/meso.py` `_try_claim_issue` push-failure path (skip / `--force`, no increment).
  - `src/deviate/core/worktree.py::branch_exists_on_remote` and `git_env()` isolation.

## The Problem Contract

Parallel `adhoc` / `specify` / shard on two checkouts (or two worktrees from stale `main`) reuse the same `NNN` because the next id is `max(local ledger) + 1` and unmerged claims live only on `feat/{epic}/{NNN}-*` / `feat/adhoc/{NNN}-*`, invisible on `origin/main`. Operators need one remote-aware counter so a second parallel adhoc while `origin/feat/adhoc/017-*` exists allocates **018**, and a rejected push of that name increments rather than colliding.

## Scope Boundaries

### Hard Inclusions

- Next issue id = `max(ordinals) + 1` over: `origin/main` ledger, current-branch ledger if present, remote refs `feat/<epic>/<NNN>-*` and `feat/adhoc/<NNN>-*`.
- Optional `git fetch --prune`; already-fetched `origin` is sufficient.
- Same rule for epic bucket numbers in `allocate_feature_bucket`.
- One adhoc series: `ISS-ADH-NNN`, `ISS-NNN`, file `NNN-slug.md`, branch `feat/adhoc/NNN-slug` share the ordinal. Do not invent a second series.
- Local-only unpushed branches do not reserve a number; the reservation is the remote ref (same idea as push-as-claim).
- Push-as-claim is the lock: if `git push` of `feat/.../NNN-*` rejects because the name exists, increment and retry.
- Update API + architecture specs in the same implementation commit; CHANGELOG `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>`; production git calls use `git_env()`.

### Defensive Exclusions

- Do **not** fall back to `--local` to “win” a name collision.
- Do **not** change `claim_remote` default (`true`) or the meaning of explicit `--local` when the operator asked for a local claim (ISS-ADH-017 optional-push-as-lock).
- Do **not** let local-only branches reserve ordinals.
- Do **not** fatten GREEN or change how adhoc/plan picks TDD vs IMMEDIATE.
- Do **not** retarget two-counter retry (`src/deviate/cli/micro.py` green/red attempts).
- Do **not** author or synchronize Product-layer flows; `flow_refs: []`.
- Do **not** revert operator-local `.deviate/config.toml` (backend=pi, transport=cli, pi_rpc=false, timeout=1800, models.default=grok-4.6).
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** delete remote or local feat branches.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-019`
- **Acceptance Criteria Tokens**: `AC-ADHOC-019-01`, `AC-ADHOC-019-02`, `AC-ADHOC-019-03`, `AC-ADHOC-019-04`
- **Data Model Entities**: none new (`IssueRecord` schema unchanged; ordinals remain derived)
- **Spec Source Anchors**:
  - `src/deviate/cli/macro.py::_compute_next_issue_id`
  - `src/deviate/core/epic.py::allocate_feature_bucket`
  - `src/deviate/cli/meso.py::_try_claim_issue`
  - `specs/constitution.md` §1 Append-Only Ledger Protocol (ids unique; format-agnostic resolve)

## User Stories Ledger

- **US-019-01**: As a DeviaTDD operator running parallel `adhoc` / `specify` / shard on two checkouts from stale `main`, I want the next `NNN` to come from remote `feat/adhoc/<NNN>-*` (and the origin ledger) so two unmerged claims cannot both mint `017`. *(Ref: FR-ADHOC-019)*
- **US-019-02**: As a DeviaTDD operator allocating an epic bucket, I want `allocate_feature_bucket` to count remote `feat/<NNN>-*` refs so two `research pre` calls do not reuse the same epic number. *(Ref: FR-ADHOC-019)*
- **US-019-03**: As a DeviaTDD operator whose `git push` of `feat/.../NNN-*` is rejected because that name already exists, I want the allocator to increment and retry rather than `--local` winning the collision. *(Ref: FR-ADHOC-019)*

## Acceptance Outline

- **AO-019** *(Ref: AC-ADHOC-019-01, US-019-01)*: Next adhoc ordinal is remote-aware and one series.
  - **Happy Path**: `origin/feat/adhoc/017-*` exists and the local `main` ledger has no `017`; next allocation is `018` (or `max(remote ordinals)+1`). `ISS-ADH-018`, `ISS-018` if that fallback is emitted, file `018-*.md`, and branch `feat/adhoc/018-*` share `018`.
  - **Error Category**: Parsing that skips `ISS-ADH-NNN` (two-part split on `-`) is a fail; both `ISS-ADH-NNN` and `ISS-NNN` contribute the same ordinal.
  - **Boundary Category**: Current-branch ledger ordinals still count when present; `origin/main` ledger counts even when the working copy is stale.

- **AO-019** *(Ref: AC-ADHOC-019-02, US-019-02)*: Epic buckets use the same remote-ref rule.
  - **Happy Path**: Remote `feat/005-*` (or `feat/005-<slug>/...`) raises the next epic number above `005` even if local `specs/` has no `005-*` dir.
  - **Error Category**: `allocate_feature_bucket` that still does `max(local specs dirs)+1` fails the pin.
  - **Boundary Category**: Numbered slugs already passed in (`005-acceptance-gates`) stay idempotent; only unnumbered slugs allocate.

- **AO-019** *(Ref: AC-ADHOC-019-03, US-019-03)*: Push name-collision increments; no `--local` escape.
  - **Happy Path**: First push of `feat/adhoc/018-*` rejected because the name exists; allocator retries `019` and push succeeds.
  - **Error Category**: Falling back to `--local` (or keeping the colliding local branch as the winner) fails review.
  - **Boundary Category**: Non-name-collision push errors still surface; explicit operator `--local` / `claim_remote = false` is unchanged.

- **AO-019** *(Ref: AC-ADHOC-019-04)*: Unpushed local branches do not reserve; docs match.
  - **Happy Path**: A local-only `feat/adhoc/019-*` that was never pushed does not block a remote-aware allocator from emitting `019`.
  - **Error Category**: Treating `git branch` (no remote) as a reservation fails the pin.
  - **Boundary Category**: API/architecture docs and CHANGELOG `[Unreleased]` record the rule in the same commit.

## Edge Cases and Boundaries

- **Two-allocator race**: fetch-at-the-same-time can still pick the same `NNN`; push-as-claim is the lock, not a second local counter.
- **Duplicate remote 017**: `origin/feat/adhoc/017-two-counter-tdd-retry` and `origin/feat/adhoc/017-optional-push-as-lock` already exist; next id must be `max+1` (currently `018` or higher), never a third `017`.
- **Per-epic vs adhoc**: numbered epics keep `<epic-prefix>-<ordinal>` (e.g. `005-003` from `feat/005-acceptance-gates/003-*`); adhoc keeps the global adhoc ordinal. Do not mix epic `003` into the adhoc series.
- **Fetch optional**: network-less tests may seed `refs/remotes/origin/feat/...` without calling the real remote; production may `git fetch --prune` or use already-fetched origin.
- **Git isolation**: every test git call `cwd=<tmp_git_repo>` and `env=_git_env()`; production uses `git_env()`.
- **Micro pytest**: do not call un-mocked `_run_pytest`.

## Performance Constraints

- **L_max**: init remains ≤ 500ms (AGENTS.md). Prefer `git for-each-ref refs/remotes/origin/feat` over `ls-remote` on the hot path; `git fetch --prune` is allocation-time, not CLI init.
- **Per-agent export**: ≤ 200ms. No new export path.
- **Full test suite**: `mise run test` remains < 30s. New tests must not hit the network; seed remote-tracking refs in `tmp_git_repo`.
- **Allocation latency**: listing already-fetched origin refs should stay well under 200ms in tests.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_cli/test_macro_contracts.py` — next adhoc id is `ISS-018` / `ISS-ADH-018` (same ordinal) when origin has `feat/adhoc/017-*` and the local ledger does not.
  - `tests/test_core/test_epic.py` — `allocate_feature_bucket` skips a remote-claimed epic prefix.
  - Meso claim tests — push rejection on existing `feat/.../NNN-*` increments; `--local` is not used as the collision winner.
  - Pin that a local-only unpushed `feat/adhoc/019-*` does not reserve `019`.
- **Integration Sandbox Targets**: none required beyond tmp-git remote-tracking refs. Skip E2E; no new FLOW.

## Demonstration Path

```bash
# Seed: origin has feat/adhoc/017-*, local ledger has no 017
# Expect next adhoc ordinal 018 (or max(remote)+1), not 017
uv run pytest tests/test_cli/test_macro_contracts.py tests/test_core/test_epic.py -q

# Remote-tracking refs, not local-only branches, drive the max
git for-each-ref --format='%(refname:short)' refs/remotes/origin/feat

# Collision path: push reject on existing name must increment, not --local
rg -n "increment|--local" src/deviate/cli/meso.py src/deviate/cli/macro.py src/deviate/core/epic.py
```
