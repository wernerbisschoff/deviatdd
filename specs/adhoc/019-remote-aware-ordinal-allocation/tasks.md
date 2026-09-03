# Implementation Tasks: `feat/adhoc/019-remote-aware-ordinal-allocation`

## Phase 1: Remote epic-prefix ordinal helper
**Goal**: Next epic bucket number is `max(local numbered dirs ∪ remote feat/<NNN>-* prefixes) + 1`. Numbered slugs stay idempotent (constitution §1 Four-Layer Architecture; constitution §3 Testing Protocols).

### Tasks

- TSK-019-01: Allocate the next epic bucket from remote `feat/<NNN>-*` prefixes
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_core/test_epic.py -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/core/epic.py`
    - `tests/unit/test_core/test_epic.py`
  - **Rationale**: US-019-02 / `AC-PLAN-002` require `allocate_feature_bucket` to count already-fetched `refs/remotes/origin/feat/<NNN>-*` so two `research pre` calls do not reuse epic `005`. `epic.py` owns `_find_next_epic_num` and `allocate_feature_bucket`. `test_epic.py` is the pin surface. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: In `tests/unit/test_core/test_epic.py`, seed `refs/remotes/origin/feat/005-acceptance-gates` on `tmp_git_repo` with `cwd=<tmp_git_repo>` and `env=_git_env()`. Assert `allocate_feature_bucket` on an unnumbered slug creates a bucket whose number is greater than `005` when local `specs/` has no `005-*` directory. Assert `allocate_feature_bucket("005-acceptance-gates")` stays idempotent and reuses that numbered path.
    - **Green**: In `src/deviate/core/epic.py`, add one helper that lists `git for-each-ref --format='%(refname:short)' refs/remotes/origin/feat` with `cwd` at `repo_path` (default `Path.cwd()`) and `env=git_env()`. Parse `feat/<NNN>-*` as epic prefixes and `feat/adhoc/<NNN>-*` as the adhoc series. Fold remote epic prefixes into `_find_next_epic_num` as `max(local numbered dirs ∪ remote prefixes) + 1`. Keep numbered-slug idempotency in `allocate_feature_bucket`.
    - **Refactor**: Keep a single helper. Do not add a second counter. Do not call `ls-remote` on the hot path. Optional `git fetch --prune` stays allocation-time only.
    - **Edge Cases**: Missing origin remote yields local-dir max only, not an error. Local-only `feat/005-*` branches are ignored. `feat/005-*/003-*` must not leak epic issue `003` into the adhoc series. Tests must not hit the network.
    - **Acceptance**: Unnumbered slug allocates above remote `005`. Numbered `005-acceptance-gates` is idempotent. Existing `discover_epic` tests still pass.

---

## Phase 2: Remote-aware adhoc next-id
**Goal**: `_compute_next_issue_id` for `epic_slug="adhoc"` returns `max(origin ledger, current ledger, remote feat/adhoc/<NNN>-*) + 1`, parses `ISS-ADH-NNN` and `ISS-NNN` as one series, and ignores unpushed local feat branches (constitution §1 Append-Only Ledger Protocol).

### Tasks

- TSK-019-02: Allocate the next adhoc ordinal from origin ledger, remote feat refs, and one id series
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_cli/test_macro_contracts.py -v`
  - **Estimated Time**: 75 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/unit/test_cli/test_macro_contracts.py`
  - **Rationale**: US-019-01 / `AC-PLAN-001` require next adhoc id `018` when origin has `feat/adhoc/017-*` and the local ledger has no `017` row. The same slice pins `AC-PLAN-004`: a local-only `feat/adhoc/019-*` does not reserve `019`. `macro.py` owns `_compute_next_issue_id`. `test_macro_contracts.py` is the next-id pin surface. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: Seed `refs/remotes/origin/feat/adhoc/017-*` in `tmp_git_repo` with `_git_env()`. Assert `_compute_next_issue_id(..., epic_slug="adhoc")` returns `ISS-018` or `ISS-ADH-018` when local `specs/issues.jsonl` has no `017` row. Pin that a ledger row `ISS-ADH-017` counts as ordinal `017` (same series as `ISS-017`). Pin that a local-only unpushed `feat/adhoc/019-*` with no origin `feat/adhoc/019-*` still emits `019`.
    - **Green**: In `_compute_next_issue_id`, union ordinals from current `specs/issues.jsonl`, `git show origin/<base_branch>:specs/issues.jsonl` when that blob exists (`base_branch` from `resolve_base_branch`), and remote feat refs from the Phase 1 helper. Parse the last numeric segment so `ISS-ADH-NNN` and `ISS-NNN` share the adhoc series. Keep per-epic `<prefix>-<ordinal>` for numbered buckets. Do not mix epic `003` into the adhoc series.
    - **Refactor**: Call the shared helper. Replace `int(iid.split("-")[1])` for adhoc rows. Use `git_env()` on every git subprocess. Accept optional `repo_path: Path | None = None`.
    - **Edge Cases**: Missing origin ledger blob adds zero extra ordinals, not an error. Current-branch ledger ordinals still count. Duplicate remote `017` names still yield `max + 1`. Do not treat `git branch` local names as a reservation (`AC-PLAN-004`).
    - **Acceptance**: Origin `feat/adhoc/017-*` plus empty local ledger yields ordinal `018`. `ISS-ADH-017` counts as `017`. Local-only `feat/adhoc/019-*` does not reserve `019`. Per-epic compound ids stay unchanged.
  - **Dependency**: TSK-019-01

---

## Phase 3: Claim name-collision increment
**Goal**: When default claim mode is on and `git push` of `feat/.../NNN-*` is rejected because the name exists, increment the ordinal and retry. Do not set `--local` to win (constitution §1 Git Isolation Principle).

### Tasks

- TSK-019-03: Increment and retry claim when push rejects an existing feat name
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_cli/test_meso.py tests/unit/test_meso/test_specify.py -v`
  - **Estimated Time**: 75 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/unit/test_cli/test_meso.py`
    - `tests/unit/test_meso/test_specify.py`
  - **Rationale**: US-019-03 / `AC-PLAN-003` require `_try_claim_issue` to increment from rejected `feat/adhoc/018-*` to `019` and retry push. Collision retry must not set `local=True`. Explicit `--local` and `claim_remote = false` stay the ISS-ADH-017 skip. `TestSpecifyPushFailure` and `TestSpecifyLocalFlag` plus `tests/unit/test_meso/test_specify.py` are the pin surfaces. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: In `tests/unit/test_cli/test_meso.py`, when the first `git push` of `feat/adhoc/018-*` is rejected because that name exists, assert a retry at `019` that succeeds, and assert `local` stays false. Keep non-name-collision rollback / `PUSH_STDERR` / `--force` pins. Keep explicit `--local` skip-push tests. In `tests/unit/test_meso/test_specify.py`, assert collision retry does not call the local skip path and does not change `claim_remote` default `true`. Use `tmp_git_repo` + `_git_env()`. Do not invoke un-mocked `deviate.cli.micro._run_pytest`.
    - **Green**: In `_try_claim_issue`, when `git push` of `feat/.../NNN-*` is rejected because the name exists, recompute `NNN+1` from the shared helper and retry push, at most 3 times. Do not pass `local=True`. Non-name-collision push errors still print `PUSH_STDERR` and follow `--force` or rollback. Explicit `--local` and `claim_remote = false` still skip push.
    - **Refactor**: Keep one claim path. Do not add a second local counter. Do not retarget two-counter retry in `src/deviate/cli/micro.py`.
    - **Edge Cases**: Cap retries at 3. After 3 name collisions, surface the last push error. `BRANCH_ON_REMOTE` pre-check behavior stays for discovery; collision increment is the rejected-push path. Do not delete remote or local feat branches.
    - **Acceptance**: First rejected `018-*` retries `019` and succeeds. Collision path never records a local-only win. Existing `--local` / `claim_remote = false` tests still pass.
  - **Dependency**: TSK-019-02

---

## Phase 4: Compiler rule, specs, and changelog
**Goal**: Adhoc compiler uses the same max-over-remote rule. API and architecture record remote-aware allocation and collision retry. `CHANGELOG.md` `[Unreleased]` records the user-visible change (constitution §5 Definition of Done; AGENTS.md Spec Alignment).

### Tasks

- TSK-019-04: Point the adhoc compiler and specs at the remote-aware ordinal rule
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `rg -n "max\\(origin ledger|remote feat/adhoc|increment and retry|local-only" src/deviate/prompts/commands/deviate-adhoc.md specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md CHANGELOG.md`
  - **Estimated Time**: 45 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/prompts/commands/deviate-adhoc.md`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AO-019` / `AC-PLAN-004` require docs to match the allocator. The compiler in `deviate-adhoc.md` Step 6 must not mint a second `017` via `max(local ledger)+1` (`AC-PLAN-001`). API and architecture must state remote feat refs, name-collision increment-and-retry (`AC-PLAN-003`), and that local-only branches do not reserve. Constitution §5 requires the `[Unreleased]` bullet in the same implementation commit. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Implementation**: In `src/deviate/prompts/commands/deviate-adhoc.md` Step 6, instruct the compiler to take `max(origin ledger, current ledger, remote feat/adhoc/<NNN>-*) + 1`. Parse `ISS-ADH-NNN` and `ISS-NNN` as one series. Do not use `max(local ledger)+1` or local-only branches.
    - **Implementation**: In `specs/DeviaTDD-api.md`, document the max-over-origin-ledger-and-remote-feat-refs rule for shard `next_issue_id` / adhoc allocation, name-collision increment-and-retry on claim push, and that local-only branches do not reserve.
    - **Implementation**: In `specs/DeviaTDD-architecture.md` Atomic Concurrency Protocol §7, document that unmerged `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*` refs feed the next ordinal and that name collision increments and retries. Keep `--local` / `claim_remote = false` as the skip, not a collision winner.
    - **Implementation**: Append one `CHANGELOG.md` `[Unreleased]` bullet: next issue/epic `NNN` includes remote feat refs; name-collision push increments; local-only branches do not reserve.
    - **Refactor**: Keep API and architecture wording aligned in the same commit. Do not change `claim_remote` default `true`.
    - **Edge Cases**: Do not author or sync Product-layer flows. Do not revert operator-local `.deviate/config.toml`. Do not retarget two-counter retry wording in `src/deviate/cli/micro.py`.
    - **Acceptance**: Compiler, API, architecture, and CHANGELOG all state the remote-aware max rule, collision increment, and local-only non-reservation. `rg` verification exits 0.
  - **Dependency**: TSK-019-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (`TSK-019-01`) -> Phase 2 (`TSK-019-02`) -> Phase 3 (`TSK-019-03`) -> Phase 4 (`TSK-019-04`)

**Critical Dependency Chains**:
- TSK-019-01 must precede TSK-019-02 (shared remote ordinal helper)
- TSK-019-02 must precede TSK-019-03 (claim retry recomputes `NNN+1` from the helper)
- TSK-019-03 must precede TSK-019-04 (docs describe shipped allocator and retry behavior)

**Risk Hotspots**:
- `iid.split("-")[1]` keeps dropping `ISS-ADH-017`.
- Local-only branches counted as reservations.
- Collision retry sets `local=True` and wins without a remote lock.
- Epic `003` from `feat/005-*/003-*` leaks into the adhoc series.
- `git fetch` / `ls-remote` on the hot path or tests hitting the network.
- Un-mocked `deviate.cli.micro._run_pytest` blowing the 30s suite budget.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/epic.py` (helper used by Phase 2 and Phase 3 callers). `src/deviate/cli/meso.py` stays Phase 3 only. Docs stay Phase 4 only.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/019-remote-aware-ordinal-allocation.md` (frontmatter field: `flow_refs`)
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
