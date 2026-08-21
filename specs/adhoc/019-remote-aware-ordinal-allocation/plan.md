## Plan Summary
- **Issue**: ISS-ADH-019 — Allocate Issue and Epic Ordinals from Remote Feat Branches
- **Implementation Strategy**: Add one remote-aware ordinal helper and call it from `_compute_next_issue_id`, `_find_next_epic_num`, and `_try_claim_issue`. Next `NNN` is `max(origin ledger, current ledger, remote feat refs) + 1`. A name-collision push increments and retries. Explicit `--local` stays an opt-out, not a collision winner.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/019-remote-aware-ordinal-allocation.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable `deviate` meso and micro phases to drive Pi or OMP agent runtimes through RPC and stream live progress into a compact TUI.
- **Architecture Components Touched**: C1

## Acceptance Contract

**Scenario AC-PLAN-001: Allocate the next adhoc ordinal from remote feat refs and one id series**
- **Source Outline**: `AO-019`
- **Upstream Traceability**: `US-019-01`, `FR-ADHOC-019`, `AC-ADHOC-019-01`
- **Current-Code Evidence**: `src/deviate/cli/macro.py:_compute_next_issue_id`
- **Given**: Origin has `refs/remotes/origin/feat/adhoc/017-*` and the local `specs/issues.jsonl` has no `017` row.
- **When**: `_compute_next_issue_id` runs with `epic_slug="adhoc"`.
- **Then**: The function returns `ISS-018` or `ISS-ADH-018` and treats `ISS-ADH-017` and `ISS-017` as ordinal `017`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Allocate the next epic bucket from remote feat prefixes**
- **Source Outline**: `AO-019`
- **Upstream Traceability**: `US-019-02`, `FR-ADHOC-019`, `AC-ADHOC-019-02`
- **Current-Code Evidence**: `src/deviate/core/epic.py:_find_next_epic_num`
- **Given**: Origin has `refs/remotes/origin/feat/005-*` and local `specs/` has no `005-*` directory.
- **When**: `allocate_feature_bucket` runs with an unnumbered slug.
- **Then**: The created bucket number is greater than `005`, and a numbered slug such as `005-acceptance-gates` stays idempotent.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Increment and retry when push rejects an existing feat name**
- **Source Outline**: `AO-019`
- **Upstream Traceability**: `US-019-03`, `FR-ADHOC-019`, `AC-ADHOC-019-03`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_try_claim_issue`
- **Given**: Default claim mode is on (`claim_remote = true`, no `--local`) and the first `git push` of `feat/adhoc/018-*` is rejected because that name exists.
- **When**: `_try_claim_issue` handles the rejected push.
- **Then**: The claim path increments to `019`, retries the push, and does not set `--local` or keep the colliding name as the winner.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Ignore unpushed local feat branches when choosing NNN**
- **Source Outline**: `AO-019`
- **Upstream Traceability**: `US-019-01`, `FR-ADHOC-019`, `AC-ADHOC-019-04`
- **Current-Code Evidence**: `src/deviate/cli/macro.py:_compute_next_issue_id`
- **Given**: A local-only `feat/adhoc/019-*` branch exists and origin has no `feat/adhoc/019-*` ref.
- **When**: The remote-aware allocator computes the next adhoc ordinal.
- **Then**: The allocator still emits `019` and does not treat `git branch` local names as a reservation.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/epic.py**: Own the single ordinal helper and fold remote prefixes into epic allocation.
  - **Current State**: `_find_next_epic_num` scans local `specs/*` dirs only. `allocate_feature_bucket` is idempotent for numbered slugs. The module has no git calls.
  - **Changes Required**: Add a helper that lists already-fetched `refs/remotes/origin/feat` via `git for-each-ref` with `git_env()`. Optional `git fetch --prune` stays off the hot path and is allocation-time only. Next epic number is `max(local numbered dirs ∪ remote feat/<NNN>-* prefixes) + 1`. Keep numbered-slug idempotency.
  - **Integration Surface**: `_compute_next_issue_id` in `src/deviate/cli/macro.py`; `_try_claim_issue` in `src/deviate/cli/meso.py`.
- **src/deviate/cli/macro.py**: Make `_compute_next_issue_id` remote-aware and parse one adhoc series.
  - **Current State**: Adhoc fallback uses `int(iid.split("-")[1])` on local ledger rows. `ISS-ADH-017` is skipped. No origin ledger. No remote refs.
  - **Changes Required**: Next id is `max(ordinals) + 1` over `origin/<base_branch>` ledger, current-branch ledger, and remote `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*` refs. Parse `ISS-ADH-NNN` and `ISS-NNN` as the same adhoc ordinal. Keep per-epic `<prefix>-<ordinal>` for numbered buckets. Do not mix epic `003` into the adhoc series. Use `resolve_base_branch` for the origin ledger path.
  - **Integration Surface**: `shard_pre` `next_issue_id`; the adhoc compiler rule in `src/deviate/prompts/commands/deviate-adhoc.md`.
- **src/deviate/cli/meso.py**: Retry claim on name-collision push. Keep `--local` as the ISS-ADH-017 skip.
  - **Current State**: Rejected push that now exists on remote prints `BRANCH_ON_REMOTE` and returns `None`. Other push failures roll back unless `--force`. `local=True` skips remote check and push.
  - **Changes Required**: When `git push` of `feat/.../NNN-*` is rejected because the name exists, increment the ordinal and retry. Cap retries at 3. Do not set `local=True` to win. Non-name-collision push errors still surface stderr and keep `--force` / rollback. Explicit `--local` and `claim_remote = false` stay unchanged.
  - **Integration Surface**: `_specify_pre`, `claim_remote` / `--local` from ISS-ADH-017.
- **src/deviate/prompts/commands/deviate-adhoc.md**: Point the compiler at the same remote-aware counter.
  - **Current State**: Step 6 uses `ISS-NNN` and file `NNN-slug.md` with no remote-ref rule, so agents can mint a second `017`.
  - **Changes Required**: Instruct the compiler to take `max(origin ledger, current ledger, remote feat/adhoc/<NNN>-*) + 1`. Parse `ISS-ADH-NNN` and `ISS-NNN` as one series. Do not use `max(local ledger)+1` or local-only branches.
  - **Integration Surface**: `_compute_next_issue_id` behavior; issue file `specs/adhoc/issues/{NNN}-{slug}.md`.
- **tests/test_cli/test_macro_contracts.py**: Pin adhoc next-id against remote-tracking refs.
  - **Current State**: Tests cover per-epic labels and local-ledger adhoc `ISS-NNN` fallback. No origin `feat/adhoc/017-*` case. No `ISS-ADH-NNN` parse pin.
  - **Changes Required**: Seed `refs/remotes/origin/feat/adhoc/017-*` in `tmp_git_repo` with `_git_env()`. Assert next id ordinal is `018` when the local ledger has no `017`. Pin `ISS-ADH-017` counting as `017`. Pin a local-only unpushed `feat/adhoc/019-*` that does not reserve `019`.
  - **Integration Surface**: `_compute_next_issue_id`.
- **tests/test_core/test_epic.py**: Pin `allocate_feature_bucket` against remote epic prefixes.
  - **Current State**: Tests cover `discover_epic` and the missing-`explore.md` warning. No `allocate_feature_bucket` remote pin.
  - **Changes Required**: Seed `refs/remotes/origin/feat/005-*`. Assert an unnumbered slug allocates above `005`. Assert `005-acceptance-gates` stays idempotent.
  - **Integration Surface**: `_find_next_epic_num`, `allocate_feature_bucket`.
- **tests/test_cli/test_meso.py**: Pin push name-collision increment and no `--local` fallback.
  - **Current State**: `TestSpecifyPushFailure` pins stderr, rollback, and race-keep. `TestSpecifyLocalFlag` pins explicit `--local`.
  - **Changes Required**: When push rejects because the name exists, assert a retry at `NNN+1` and assert `local` stays false. Keep non-name-collision rollback. Keep explicit `--local` skip-push tests.
  - **Integration Surface**: `_try_claim_issue`.
- **tests/test_meso/test_specify.py**: Keep `--local` / `claim_remote = false` as the optional skip.
  - **Current State**: Local-flag forwarding and config-false skip-push are pinned.
  - **Changes Required**: Collision retry must not call the local skip path. Do not change `claim_remote` default `true`.
  - **Integration Surface**: `_specify_pre`, `_try_claim_issue`.
- **specs/DeviaTDD-api.md**: Document remote-aware ordinal allocation and push-as-claim retry.
  - **Current State**: Shard `next_issue_id` and claim push-as-lock are documented as local ledger plus exact-branch push.
  - **Changes Required**: State the max-over-origin-ledger-and-remote-feat-refs rule. State name-collision increment-and-retry. State local-only branches do not reserve.
  - **Integration Surface**: Same-commit alignment with `specs/DeviaTDD-architecture.md`.
- **specs/DeviaTDD-architecture.md**: Record the remote-aware counter beside Atomic Concurrency Protocol §7.
  - **Current State**: §7 describes try-claim plus default `git push -u` and optional local skip.
  - **Changes Required**: Document that unmerged `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*` refs feed the next ordinal. Document increment-and-retry on name collision. Keep `--local` / `claim_remote = false` as the skip, not a collision winner.
  - **Integration Surface**: Same-commit alignment with `specs/DeviaTDD-api.md`.
- **CHANGELOG.md**: Record the user-visible allocation change.
  - **Current State**: `[Unreleased]` has no remote-aware ordinal bullet.
  - **Changes Required**: Append one `[Unreleased]` bullet: next issue/epic `NNN` includes remote feat refs; name-collision push increments; local-only branches do not reserve.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: Shared remote ordinal helper
  - **Files**: `src/deviate/core/epic.py`, `tests/test_core/test_epic.py`
  - **Approach**: Collect ordinals from `git for-each-ref --format='%(refname:short)' refs/remotes/origin/feat` with `cwd` at the repo root and `env=git_env()`. Parse `feat/adhoc/<NNN>-*` for the adhoc series and `feat/<NNN>-*` for epic prefixes. Skip local-only branches. Seed remote-tracking refs in `tmp_git_repo`. Do not call `ls-remote` on the hot path.
  - **Verification**: `mise run test tests/test_core/test_epic.py` — remote `005-*` raises the next epic number; numbered slugs stay idempotent.
- **Phase 2**: Remote-aware `_compute_next_issue_id`
  - **Files**: `src/deviate/cli/macro.py`, `tests/test_cli/test_macro_contracts.py`
  - **Approach**: Union ordinals from current `specs/issues.jsonl`, `git show origin/<base_branch>:specs/issues.jsonl` when that blob exists, and remote feat refs from Phase 1. Parse `ISS-ADH-NNN` and `ISS-NNN` as one adhoc series. Keep per-epic compound ids. Missing origin blob is zero extra ordinals, not an error.
  - **Verification**: Origin `feat/adhoc/017-*` with empty local ledger yields ordinal `018`. `ISS-ADH-017` counts. Local-only `feat/adhoc/019-*` does not reserve `019`.
- **Phase 3**: Claim name-collision increment
  - **Files**: `src/deviate/cli/meso.py`, `tests/test_cli/test_meso.py`, `tests/test_meso/test_specify.py`
  - **Approach**: On rejected push whose cause is an existing `feat/.../NNN-*` name, recompute `NNN+1` from the helper and retry push, at most 3 times. Do not pass `local=True`. Non-name-collision failures still print `PUSH_STDERR` and follow `--force` or rollback. Explicit `--local` / `claim_remote = false` still skip push.
  - **Verification**: First rejected `018-*` retries `019` and succeeds. Collision path never records a local-only win. Existing local-flag tests still pass.
- **Phase 4**: Adhoc prompt plus specs and changelog
  - **Files**: `src/deviate/prompts/commands/deviate-adhoc.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Tell the compiler to use the same max-over-remote rule. Update API and architecture in the same implementation commit. Append the `[Unreleased]` bullet.
  - **Verification**: Same-commit spec and changelog review against constitution §5 and AGENTS.md Spec Alignment.

## Data Flow Analysis
- **Inputs**: Local `specs/issues.jsonl`, optional `origin/<base_branch>:specs/issues.jsonl`, already-fetched `refs/remotes/origin/feat/*`, current `epic_slug` or unnumbered feature slug, and `git push` result.
- **Transform**: The helper parses `ISS-ADH-NNN`, `ISS-NNN`, `feat/adhoc/<NNN>-*`, and `feat/<NNN>-*` into integer ordinals. Adhoc uses the global adhoc series. Numbered epics use `<epic-prefix>` for buckets and `<epic-prefix>-<ordinal>` for issues.
- **Allocation output**: `_compute_next_issue_id` returns the next issue id. `allocate_feature_bucket` returns `specs/<NNN>-<slug>/` for unnumbered slugs.
- **Claim output**: `_try_claim_issue` pushes `feat/<epic>/<NNN>-*`. Name collision increments `NNN` and retries. Non-collision errors surface. `--local` skips this lock.
- **Storage**: Ledgers stay append-only. No new `IssueRecord` fields. Reservation is the remote ref, not a local branch.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Two allocators fetch at the same time and still pick the same `NNN` | High | Medium | Keep push-as-claim as the lock. Increment and retry on name collision. Do not add a second local counter. |
| `iid.split("-")[1]` keeps dropping `ISS-ADH-017` | High | High | Parse the last numeric segment for `ISS-ADH-NNN` and `ISS-NNN`. Pin both in `test_macro_contracts.py`. |
| Local-only branches reserve `NNN` and block a second checkout | Medium | High | Count only `refs/remotes/origin/feat`. Pin AC-PLAN-004. |
| Collision retry sets `local=True` and “wins” without a remote lock | High | Medium | Retry with `local` false. Keep ISS-ADH-017 `--local` as an explicit skip only. |
| Epic `003` from `feat/005-*/003-*` leaks into the adhoc series | High | Medium | Scope adhoc refs to `feat/adhoc/<NNN>-*`. Scope epic prefixes to `feat/<NNN>-*`. |
| `git fetch` or `ls-remote` on the hot path blows L_max or hits the network in tests | Medium | Medium | Use `git for-each-ref` on already-fetched origin. Seed remote-tracking refs in `tmp_git_repo`. Keep fetch optional and allocation-time. |
| Tests inherit parent git config or call un-mocked `_run_pytest` | Medium | Medium | Every git call uses `cwd=<tmp_git_repo>` and `env=_git_env()`. Production uses `git_env()`. Do not add tests that invoke `deviate.cli.micro._run_pytest` un-mocked. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (`git for-each-ref`, optional `git fetch --prune`, `git show`, `git push`), file paths (`specs/issues.jsonl`, `specs/` dirs).
Negative tests: `ISS-ADH-017` is not skipped; local-only `feat/adhoc/019-*` does not reserve `019`; name-collision retry does not set `--local`; non-name-collision push errors still surface; `claim_remote = false` / explicit `--local` still skip push; git subprocesses use `git_env()`; tests do not hit the network.
Constraints: no new dependencies; no hardcoded secrets; do not delete remote or local feat branches; do not retarget two-counter retry in `src/deviate/cli/micro.py`; do not revert operator-local `.deviate/config.toml`; do not fatten GREEN.

## Integration Points
- **`git for-each-ref refs/remotes/origin/feat`**: Source of remote ordinals. Called with `git_env()`. Tests seed tracking refs instead of a live remote.
- **`git show origin/<base_branch>:specs/issues.jsonl`**: Origin ledger ordinals when the blob exists. `base_branch` comes from `resolve_base_branch`.
- **`_compute_next_issue_id`**: Shard `next_issue_id` and the adhoc series. Consumes the helper plus local ledger rows.
- **`allocate_feature_bucket` / `_find_next_epic_num`**: Research-pre bucket allocation. Numbered slugs stay idempotent.
- **`_try_claim_issue`**: Push-as-claim lock. Name-collision increment-and-retry. `--local` / `claim_remote = false` unchanged.
- **`src/deviate/prompts/commands/deviate-adhoc.md`**: Compiler uses the same max-over-remote rule so agent-written `specs/adhoc/issues/{NNN}-{slug}.md` cannot mint a duplicate `017`.

## Constitutional Alignment
- **Architecture**: Macro shard/adhoc allocation and meso claim stay in the four-layer model (constitution §1). Issue ids stay unique and format-agnostic at resolve time. This plan does not skip a layer and does not add Product-layer work.
- **Testing**: pytest under `tests/` with `tmp_git_repo` and `_git_env()` (constitution §3). Coverage target ≥ 80%. Full suite stays under 30s. No un-mocked `_run_pytest`.
- **Git Isolation**: Work stays on `feat/adhoc/019-remote-aware-ordinal-allocation`. Production git uses `git_env()`. This issue does not delete branches.
- **Product Layer**: Issue `flow_refs` is `[]`. Downstream artifacts keep empty flow references. This plan does not author or sync Product-layer flows.
