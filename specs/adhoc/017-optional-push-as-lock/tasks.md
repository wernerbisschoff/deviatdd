# Implementation Tasks: `feat/adhoc/017-optional-push-as-lock`

## Phase 1: Config field and resolver
**Goal**: Add standing `claim_remote` on `DeviateConfig` and resolve it to `True` unless the TOML bool is explicitly `false`.

### Tasks

- TSK-017-01: Add `DeviateConfig.claim_remote` and `resolve_claim_remote`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_config.py -k claim_remote -v`
  - **Estimated Time**: 45 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_state/test_config.py`
  - **Rationale**: US-017-01 and US-017-02 need a standing default in `.deviate/config.toml` (constitution §2 Config). `config.py` owns `DeviateConfig` with `extra = forbid` and `resolve_graphite_config`. `test_config.py` already pins graphite default / round-trip / absent-key. This slice implements the data contract for `AC-PLAN-001` (absent file or key = push) and `AC-PLAN-002` (`claim_remote = false`).
  - **Details**:
    - **Red**: Add `test_config_claim_remote_field_default` asserting `DeviateConfig().claim_remote is True`. Add `test_config_claim_remote_round_trip` asserting `model_dump()` includes `"claim_remote": True` and `"claim_remote": False`. Add `test_resolve_claim_remote_true`, `test_resolve_claim_remote_false`, `test_resolve_claim_remote_key_absent`, `test_resolve_claim_remote_no_file`, and `test_resolve_claim_remote_non_bool` using `tmp_path` / `tmp_git_repo` with `.deviate/config.toml`.
    - **Green**: Add `claim_remote: bool = True` on `DeviateConfig` beside `graphite`. Keep `model_config = {"extra": "forbid"}`. Add `resolve_claim_remote(root: Path) -> bool` beside `resolve_graphite_config`. Load via `_load_deviate_config_toml(root)`. Return `True` when the file is absent, the key is absent, or the value is not a bool. Return the bool when it is a bool.
    - **Refactor**: Mirror `resolve_graphite_config` control flow. Do not add extra loaders. Do not nest the key under `[models]` or `[agent]`.
    - **Edge Cases**: Missing `.deviate/config.toml` returns `True` (`AC-PLAN-001`). Malformed TOML follows `_load_deviate_config_toml` (`None` → `True`). String `"false"` is not a bool and returns `True`.
    - **Acceptance**: Default field is `True`. Resolver matches the six cases. Existing graphite tests still pass. Constitution §2 Config surface is the only store.

---

## Phase 2: Effective-local claim and discovery
**Goal**: Resolve `--local` OR `claim_remote = false` inside `_specify_pre`, skip only the remote lock, and stop treating origin branches as claimed-elsewhere in local mode.

### Tasks

- TSK-017-02: Resolve effective local in `_specify_pre` and skip the remote lock
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_meso.py::TestSpecifyLocalFlag tests/test_meso/test_specify.py -k "local or claim_remote" -v`
  - **Estimated Time**: 75 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_cli/test_meso.py`
    - `tests/test_meso/test_specify.py`
  - **Rationale**: US-017-01 / US-017-02 / US-017-03 require omitted `--local` to honor config and `--local` to win when config is true (`AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003`). Resolution lives in `_specify_pre` so `_claim_and_setup` / `deviate plan pre` inherit it (constitution §1 Git Isolation: worktree + ledger claim stay). `_try_claim_issue(..., local=True)` already skips `branch_exists_on_remote` and `git push`. Tests pin that path through `TestSpecifyLocalFlag` and `test_specify.py`.
  - **Details**:
    - **Red**: In `TestSpecifyLocalFlag`, add a config-false case that writes `.deviate/config.toml` with `claim_remote = false`, calls `_specify_pre` with `local=False`, and asserts `branch_exists_on_remote` and `git push` are never called while the worktree is created and SPECIFIED is written. Keep the four existing `local=True` pins. In `tests/test_meso/test_specify.py`, add `test_specify_omitted_local_honors_claim_remote_false` (omitted `--local` forwards effective `local=True`) and `test_specify_local_overrides_claim_remote_true` (`--local` still forwards `True` when config is true). Assert `LOCAL_ONLY` on the skip-push path. Use `tmp_git_repo` + `_git_env()`.
    - **Green**: In `_specify_pre`, set `local = local or not resolve_claim_remote(Path.cwd())` before `_try_claim_issue`. Import `resolve_claim_remote` from `deviate.state.config`. Do not change `_try_claim_issue` skip-push semantics, `feat/{epic}/{issue}` naming, or `.worktrees/feat/...` layout. Do not skip `claim_issue()` or the local claim commit.
    - **Refactor**: Extract `_effective_local(local: bool, root: Path | None = None) -> bool` in `meso.py` if `specify` and `_meso_run` need the same formula for discovery. Keep a single resolution rule: flag `True` always wins.
    - **Edge Cases**: Absent config file keeps the push path (`AC-PLAN-001`). Existing local branch plus effective local still prints `ALREADY_CLAIMED_LOCAL`. `_claim_and_setup` calls `_specify_pre` without `local` and inherits config. Do not add `--no-local`.
    - **Acceptance**: Config-false skips remote pre-check and `git push`, still creates the worktree, still writes SPECIFIED, still commits. `--local` with `claim_remote = true` takes the same skip-push path. Default omitted flag still pushes.
  - **Dependency**: TSK-017-01

- TSK-017-03: Skip origin-as-claimed in local discovery
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_meso/test_meso_orchestration.py::TestDiscoverClaimableIssue -v`
  - **Estimated Time**: 45 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_meso/test_meso_orchestration.py`
  - **Rationale**: US-017-01 / `AC-PLAN-005` require `_discover_claimable_issue` to return a BACKLOG id in local mode even when `feat/{epic}/{issue}` exists on origin. Default mode must still skip origin branches (`AC-PLAN-001`). `TestDiscoverClaimableIssue` is the current origin-skip pin. Bare `specify` and `_meso_run` auto-claim share this function.
  - **Details**:
    - **Red**: Add `test_discover_local_returns_backlog_when_origin_branch_exists` asserting `_discover_claimable_issue(local=True)` returns the first unblocked BACKLOG when `branch_exists_on_remote` is True. Add `test_discover_config_false_does_not_skip_origin` for effective local via `claim_remote = false`. Keep a default-mode test that still skips origin branches. Empty ledger still returns `None`.
    - **Green**: Add `local: bool = False` to `_discover_claimable_issue`. When `local` is True, skip the `branch_exists_on_remote` continue path. When `local` is False, keep today's origin skip. In `specify` (omitted id) and `_meso_run` (auto-discover), pass `_effective_local(local)` / `local or not resolve_claim_remote(Path.cwd())`.
    - **Refactor**: Detect `origin` once as today. Do not change `select_unblocked_candidates` order. Do not treat completed issues as claimable.
    - **Edge Cases**: No BACKLOG still returns `None` / `NO_CLAIMABLE_ISSUES`. No `origin` remote already returns the first candidate; local mode must not call `branch_exists_on_remote`. Default `claim_remote = true` without `--local` keeps origin skip.
    - **Acceptance**: Local mode returns the leftover-origin BACKLOG. Default mode still skips it. `specify` auto-discovery uses the same effective-local value as `_specify_pre`.
  - **Dependency**: TSK-017-02

---

## Phase 3: `--local` on meso run and run
**Goal**: Thread `--local` through `meso_run_command` and `run_command` into `_meso_run`. Keep `--no-setup` as the worktree/claim skip.

### Tasks

- TSK-017-04: Forward `--local` on `meso run` and `deviate run`; keep `--no-setup` separate
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_meso/test_meso_orchestration.py::TestMesoRunNoSetup tests/test_cli/test_top_level_run.py -k "local or no_setup or meso_run" -v`
  - **Estimated Time**: 75 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_meso/test_meso_orchestration.py`
    - `tests/test_cli/test_top_level_run.py`
  - **Rationale**: US-017-03 / `AC-PLAN-003` require `deviate meso run --local` and `deviate run --local` to forward `local=True` into `_specify_pre`. `AC-PLAN-006` requires `--no-setup` (alone or with `--local`) to skip `_specify_pre`, skip the worktree, skip the ledger claim, and run PLAN plus TASKS in `$CWD`. Linked-worktree auto-detect still sets `no_setup=True` and must not force a second claim (constitution §1 Git Isolation).
  - **Details**:
    - **Red**: Add tests that `meso_run_command --local` and omitted-flag plus `claim_remote = false` call `_specify_pre(..., local=True)`. Add `test_meso_run_local_does_not_imply_no_setup` asserting `_specify_pre` still runs when `--local` is set and `--no-setup` is not. Add `test_meso_run_no_setup_with_local_skips_specify_pre` asserting combined flags skip `_specify_pre`. Add `test_top_level_run_forwards_local` patching `_meso_run` and asserting `local=True`. Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` on any test that reaches it (AGENTS.md test-performance rule; suite < 30s).
    - **Green**: Add `local: bool = False` to `_meso_run`. Add `--local` on `meso_run_command` and `run_command`. Do not add `--no-local`. Forward `local` into `_discover_claimable_issue` and `_specify_pre`. When `no_setup` is True (flag or linked-worktree auto-detect), do not call `_specify_pre`. `--local` does not set `no_setup`.
    - **Refactor**: Keep the `no_setup` branch and the claim branch separate in `_meso_run`. Pass `local` through `run_command` as `_meso_run(issue_id=issue, force=force, local=local)`.
    - **Edge Cases**: Linked worktree with `--local` still skips a second claim. Unknown extra flags still fail Typer parsing. `--no-setup` still drops SPECIFY from `PipelineBanner.steps`.
    - **Acceptance**: `meso run --local` and `run --local` take the skip-push claim path. `--no-setup` still skips claim. Combined flags do not invent a third mode.
  - **Dependency**: TSK-017-03

---

## Phase 4: Setup persistence
**Goal**: Persist `claim_remote` through `deviate setup --no-claim-remote` without dropping other config keys.

### Tasks

- TSK-017-05: Persist `claim_remote` via `deviate setup --no-claim-remote`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_init.py -k claim_remote -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-017-01 / `AC-PLAN-004` require `deviate setup --no-claim-remote` to upsert `claim_remote = false` without dropping `[models]`, `timeout_seconds`, or `[agent]`. Fresh setup without the flag writes `claim_remote = true`. `_merge_flag_keys` already upserts `graphite` and `use_libref`. `_CONFIG_TOML_COMMENTS` documents standing keys. Constitution §2 Config is the persist surface.
  - **Details**:
    - **Red**: Add `test_setup_no_claim_remote_writes_false` asserting `claim_remote = false` after `runner.invoke(cli, ["setup", "--agent", "opencode", "--no-claim-remote"])`. Add `test_setup_fresh_writes_claim_remote_true` for omitted flag. Add `test_setup_no_claim_remote_preserves_models_timeout_agent` that seeds `[models]`, `timeout_seconds`, and `[agent]` then asserts they survive the upsert. Use `tmp_git_repo`. Do not mutate this worktree's `.deviate/config.toml`.
    - **Green**: Add `claim_remote` to `_CONFIG_TOML_COMMENTS`. Extend `_merge_flag_keys` with `claim_remote: bool`. Thread `claim_remote` through `_scaffold_dotfiles` into `DeviateConfig(...)`. Add `--no-claim-remote` on `setup` (`typer.Option` with `is_flag` / `--no-claim-remote` so omitted keeps `True`). Set `force_update_flags` when the operator passes `--no-claim-remote`. Optional TTY prompt only when the flag is omitted and `is_interactive()` is true, following `_prompt_agent_selection`. Non-interactive sessions without the flag keep `true`.
    - **Refactor**: Reuse the graphite upsert loop. Insert the new key before the first `[table]` header. Do not rewrite the whole file.
    - **Edge Cases**: Re-run on existing config upserts the key like `--graphite`. Interactive prompt is TTY-only. Do not add `--no-local`. Do not revert operator-local `backend`, `transport`, `pi_rpc`, `timeout`, or `models.default` in this worktree.
    - **Acceptance**: `--no-claim-remote` writes `false` and keeps unrelated keys. Fresh setup writes `true`. `resolve_claim_remote` reads the written file.
  - **Dependency**: TSK-017-01

---

## Phase 5: Spec and changelog alignment
**Goal**: Document optional push-as-lock in the API and architecture specs and record the user-visible change.

### Tasks

- TSK-017-06: Document `claim_remote` and `--local` in specs and CHANGELOG
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `rg -n "claim_remote|--no-claim-remote" specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md CHANGELOG.md`
  - **Estimated Time**: 30 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: AGENTS.md Spec Alignment and constitution §5 Definition of Done require API + architecture + `[Unreleased]` in the same commit as the behavior change. `AC-PLAN-001` through `AC-PLAN-006` are the documented contracts: default push, config-false skip-push, `--local` on specify / meso run / run, setup persist, local discovery, and `--no-setup` as a separate escape.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, document `claim_remote` (default true), `deviate setup --no-claim-remote`, omitted `--local` honors config, and `--local` on `deviate specify`, `deviate meso run`, and `deviate run`. Keep `--no-setup` as skip of worktree plus claim. In `specs/DeviaTDD-architecture.md` Atomic Concurrency Protocol, state that push-as-lock is the default serialization. Local mode keeps worktree + ledger SPECIFIED and skips the remote lock. In `CHANGELOG.md` `[Unreleased]`, append one bullet for `claim_remote`, `--no-claim-remote`, and `--local` on `meso run` / `run`.
    - **Refactor**: Reuse the existing `deviate specify --local` wording. Do not duplicate Graphite stacked-PR docs. Do not change `feat/{epic}/{issue}` layout docs.
    - **Edge Cases**: Do not document a `--no-local` flag. Do not mark push-as-lock as removed; it stays the default (`AC-PLAN-001`).
    - **Acceptance**: Both spec files name `claim_remote` and the new flags. CHANGELOG has one `[Unreleased]` bullet. Same-commit alignment with the implementation tasks.
  - **Dependency**: TSK-017-04

---

## Phase 6: E2E CLI surface
**Goal**: Verify the installed CLI exposes `--local` and `--no-claim-remote` and rejects `--no-local`.

### Tasks

- TSK-017-07: [E2E] Help surface for optional push-as-lock flags
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_optional_push_as_lock.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: The issue is a user-facing CLI workflow (`deviate specify`, `deviate meso run`, `deviate run`, `deviate setup`) for US-017-01 / US-017-02 / US-017-03. Constitution §3 E2E command is `bats tests/e2e/`. This task verifies the installed binary, not DeviaTDD setup internals. Happy path covers `AC-PLAN-003` and `AC-PLAN-004` flag presence. Critical failure covers the defensive exclusion of `--no-local`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_optional_push_as_lock.bats`. Happy path: `deviate specify --help`, `deviate meso run --help`, and `deviate run --help` exit 0 and print `--local`; `deviate setup --help` exits 0 and prints `--no-claim-remote`; `deviate meso run --help` still prints `--no-setup` as a separate flag. Critical failure: `deviate run --no-local` exits non-zero (no `--no-local` flag). Keep each test in a fresh tmpdir like `test_macro_workflow.bats`. Do not run live `git push` against this product repo.
    - **Refactor**: Reuse the existing bats `setup`/`teardown` tmpdir pattern. Do not add pytest subprocess tests here.
    - **Edge Cases**: Unknown extra flags fail Typer parsing. Help text must not treat `--local` as `--no-setup`.
    - **Acceptance**: `bats tests/e2e/` exits 0.
  - **Dependency**: TSK-017-06

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-017-01) — config field + resolver
2. Phase 2 (TSK-017-02 → TSK-017-03) — `_specify_pre` then discovery
3. Phase 3 (TSK-017-04) — `--local` on meso run / run
4. Phase 4 (TSK-017-05) — setup persist (can start after TSK-017-01)
5. Phase 5 (TSK-017-06) — specs + CHANGELOG
6. Phase 6 (TSK-017-07) — E2E help surface

**Critical Dependency Chains**:
- TSK-017-01 must precede TSK-017-02 and TSK-017-05
- TSK-017-02 must precede TSK-017-03
- TSK-017-03 must precede TSK-017-04
- TSK-017-04 must precede TSK-017-06
- TSK-017-06 must precede TSK-017-07
- TSK-017-05 may run in parallel with TSK-017-02 after TSK-017-01

**Risk Hotspots**:
- Default must stay `True` so personal repos still push (`AC-PLAN-001`)
- `--local` must not set `no_setup` (`AC-PLAN-006`)
- Local discovery must not skip leftover origin branches (`AC-PLAN-005`)
- `_merge_flag_keys` must upsert without dropping `[models]` / `timeout_seconds` / `[agent]` (`AC-PLAN-004`)
- Resolution must live in `_specify_pre` so `_claim_and_setup` inherits config
- CLI tests that reach `_run_pytest` must mock it with `subprocess.CompletedProcess`

**Merge Conflict Boundaries**:
- `src/deviate/cli/meso.py` touched by TSK-017-02, TSK-017-03, TSK-017-04
- `src/deviate/cli/__init__.py` touched by TSK-017-04 and TSK-017-05
- `src/deviate/state/config.py` touched by TSK-017-01 only
- `tests/test_meso/test_meso_orchestration.py` touched by TSK-017-03 and TSK-017-04

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/017-optional-push-as-lock/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Mock `_run_pytest`**: Tests that invoke CLI commands reaching `deviate.cli.micro._run_pytest` MUST mock it with `subprocess.CompletedProcess` so the full suite stays under 30s.
- **Do not revert operator-local config**: Tests write `.deviate/config.toml` only under tmp fixtures. Do not change this worktree's `backend`, `transport`, `pi_rpc`, `timeout`, or `models.default`.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
