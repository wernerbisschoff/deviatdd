## Plan Summary
- **Issue**: ISS-ADH-017 — Optional push-as-lock: claim_remote config + --local on specify, meso run, and run
- **Implementation Strategy**: Add `DeviateConfig.claim_remote` (default `true`) and `resolve_claim_remote`. Resolve effective local as `--local` OR `claim_remote = false` inside `_specify_pre`, then forward that value into `_try_claim_issue`, `_discover_claimable_issue`, `_meso_run`, and `run_command`. Persist the standing default through `deviate setup --no-claim-remote`.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/017-optional-push-as-lock.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable `deviate` meso and micro phases to drive Pi or OMP agent runtimes through RPC and stream live progress into a compact TUI.
- **Architecture Components Touched**: C1

## Acceptance Contract

**Scenario AC-PLAN-001: Keep the default claim path pushing the lock branch**
- **Source Outline**: `AO-017-01`
- **Upstream Traceability**: `US-017-02`, `FR-ADHOC-017`, `AC-ADHOC-017-01`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_try_claim_issue`
- **Given**: The config file is absent or `claim_remote` is true, and the caller omits `--local`.
- **When**: The operator claims an issue through `deviate specify <id>` or `deviate meso run --issue <id>`.
- **Then**: `_try_claim_issue` creates the worktree, writes SPECIFIED, commits the claim, and runs `git push -u <remote> <branch>`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Skip only the remote lock when claim_remote is false**
- **Source Outline**: `AO-017-02`
- **Upstream Traceability**: `US-017-01`, `FR-ADHOC-017`, `AC-ADHOC-017-02`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_specify_pre`
- **Given**: `.deviate/config.toml` sets `claim_remote = false` and the caller omits `--local`.
- **When**: The operator runs `deviate specify 001-001` or `deviate meso run --issue 001-001`.
- **Then**: The claim creates `.worktrees/feat/{epic}/{issue}/`, writes SPECIFIED, commits locally, skips the remote pre-check, skips `git push`, and prints `LOCAL_ONLY`.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Honor --local over claim_remote true on specify, meso run, and run**
- **Source Outline**: `AO-017-03`
- **Upstream Traceability**: `US-017-03`, `FR-ADHOC-017`, `AC-ADHOC-017-03`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:specify`
- **Given**: Config sets `claim_remote = true` and the caller passes `--local`.
- **When**: The operator runs `deviate specify --local`, `deviate meso run --local`, or `deviate run --local`.
- **Then**: Each command forwards `local=True` into `_specify_pre` and takes the same skip-push path as AC-PLAN-002.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Persist claim_remote through deviate setup**
- **Source Outline**: `AO-017-04`
- **Upstream Traceability**: `US-017-01`, `FR-ADHOC-017`, `AC-ADHOC-017-04`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_merge_flag_keys`
- **Given**: The operator runs `deviate setup` against a missing or existing `.deviate/config.toml`.
- **When**: The operator passes `--no-claim-remote`, or omits the flag on a fresh setup.
- **Then**: `--no-claim-remote` upserts `claim_remote = false` without dropping `[models]`, `timeout_seconds`, or `[agent]`; a fresh setup without the flag writes `claim_remote = true`.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Return BACKLOG issues in local discovery even when origin already has the branch**
- **Source Outline**: `AO-017-05`
- **Upstream Traceability**: `US-017-01`, `FR-ADHOC-017`, `AC-ADHOC-017-05`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_discover_claimable_issue`
- **Given**: Local mode is on through `--local` or `claim_remote = false`, and a BACKLOG issue already has `feat/{epic}/{issue}` on origin.
- **When**: `_discover_claimable_issue` selects the next claimable issue.
- **Then**: The function returns that BACKLOG id and does not treat the origin branch as claimed-elsewhere.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Keep --no-setup as a separate escape that skips worktree and claim**
- **Source Outline**: `AO-017-06`
- **Upstream Traceability**: `US-017-03`, `FR-ADHOC-017`, `AC-ADHOC-017-06`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_meso_run`
- **Given**: The caller passes `--no-setup`, alone or together with `--local`.
- **When**: `_meso_run` starts the meso pipeline.
- **Then**: The pipeline skips `_specify_pre`, skips worktree creation, skips the ledger claim, and runs PLAN plus TASKS in `$CWD`.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/state/config.py**: Own the standing `claim_remote` key and resolver.
  - **Current State**: `DeviateConfig` has `graphite: bool = False` with `extra = forbid`. `resolve_graphite_config` returns `False` when the file or key is absent.
  - **Changes Required**: Add `claim_remote: bool = True`. Add `resolve_claim_remote(root) -> bool` that returns `True` when the file is absent, the key is absent, or the value is not a bool.
  - **Integration Surface**: `_specify_pre`, `_meso_run`, `setup` / `_scaffold_dotfiles`.
- **src/deviate/cli/meso.py**: Resolve effective local mode and keep `_try_claim_issue` as the skip-push engine.
  - **Current State**: `_try_claim_issue(..., local=True)` already skips `branch_exists_on_remote` and `git push`, still claims, still commits, and reuses `ALREADY_CLAIMED_LOCAL`. `_specify_pre` only honors the caller `local` flag. `_discover_claimable_issue` always skips origin branches. `_meso_run` / `meso_run_command` have `--no-setup` and never pass `local=True`. `_claim_and_setup` calls `_specify_pre` without `local`.
  - **Changes Required**: In `_specify_pre`, set `local = local or not resolve_claim_remote(Path.cwd())` so an explicit `local=True` always wins. Add a `local` argument to `_discover_claimable_issue` and skip the origin check in local mode. Add `--local` on `meso_run_command` and thread it through `_meso_run` into discovery and `_specify_pre`. Keep `--no-setup` as the setup skip. Do not change `feat/{epic}/{issue}` naming or `.worktrees/feat/...` layout.
  - **Integration Surface**: `specify`, `_claim_and_setup` / `deviate plan pre`, `run_command`.
- **src/deviate/cli/__init__.py**: Persist the key at setup and forward `--local` from `deviate run`.
  - **Current State**: `_CONFIG_TOML_COMMENTS` documents `graphite`. `_merge_flag_keys` upserts only `graphite` and `use_libref`. `setup` has `--graphite` / `--libref`. `run_command` calls `_meso_run(issue_id=..., force=...)` with no local flag.
  - **Changes Required**: Add `claim_remote` to comments, `DeviateConfig(...)` construction, and `_merge_flag_keys`. Add `--no-claim-remote` on `setup`. Optional TTY prompt when the flag is omitted and the session is interactive (`is_interactive()` / `_prompt_agent_selection` pattern). Non-interactive sessions without the flag keep `true`. Add `--local` on `run_command` and forward it to `_meso_run`. Do not add `--no-local`.
  - **Integration Surface**: `DeviateConfig`, `_scaffold_dotfiles`, `_meso_run`.
- **tests/test_state/test_config.py**: Pin default, round-trip, and resolver semantics.
  - **Current State**: Graphite tests cover default `False`, round-trip, true / false / key-absent / no-file.
  - **Changes Required**: Mirror those cases for `claim_remote` with inverted defaults (absent key / absent file = `True`).
  - **Integration Surface**: `DeviateConfig`, `resolve_claim_remote`.
- **tests/test_cli/test_meso.py**: Extend `TestSpecifyLocalFlag` for config-false.
  - **Current State**: Four tests pin `local=True` skips remote check and push, plus `ALREADY_CLAIMED_LOCAL`.
  - **Changes Required**: Add a config-false path that never calls `branch_exists_on_remote` or `git push` while still creating the worktree and claiming.
  - **Integration Surface**: `_try_claim_issue` via `_specify_pre`.
- **tests/test_meso/test_specify.py**: Pin omitted-flag resolution and `--local` override.
  - **Current State**: `--local` forwards `local=True` into `_specify_pre`. Bare specify uses `_discover_claimable_issue` and still skips origin branches.
  - **Changes Required**: Assert omitted `--local` with `claim_remote = false` forwards `local=True`. Assert `--local` with `claim_remote = true` still forwards `True`. Assert auto-discovery in local mode does not skip origin branches.
  - **Integration Surface**: `specify`, `_specify_pre`, `_discover_claimable_issue`.
- **tests/test_meso/test_meso_orchestration.py**: Pin discovery, meso run `--local`, config-false, and `--no-setup`.
  - **Current State**: `TestDiscoverClaimableIssue` skips origin branches. `TestMesoRunNoSetup` proves `--no-setup` does not call `_specify_pre`.
  - **Changes Required**: Local mode (flag or config-false) returns the first BACKLOG even when `branch_exists_on_remote` is True. Default mode still skips origin branches. `meso run --local` and omitted-flag + `claim_remote = false` call `_specify_pre(..., local=True)`. Combined `--no-setup --local` still skips `_specify_pre`.
  - **Integration Surface**: `_discover_claimable_issue`, `_meso_run`.
- **tests/test_cli/test_init.py** / **tests/test_cli/test_top_level_run.py**: Pin setup persist and `deviate run --local`.
  - **Current State**: Init tests pin `--graphite` merge without clobbering `[models]`. Top-level run tests pin chaining into micro with no `--local`.
  - **Changes Required**: `deviate setup --no-claim-remote` writes `claim_remote = false` without dropping other keys. Fresh setup without the flag writes `true`. `deviate run --local` forwards to `_meso_run`. Mock `deviate.cli.micro._run_pytest` on any test that reaches it.
  - **Integration Surface**: `setup`, `run_command`.
- **specs/DeviaTDD-api.md**: Document the new config key and flags.
  - **Current State**: `deviate specify [<issue-id>] [--local]` exists. `deviate meso run` documents `--no-setup` and always describes a push. `deviate run` has no `--local`.
  - **Changes Required**: Document `claim_remote` (default true). Document `--local` on `meso run` and `run`. State that omitted `--local` honors config. Keep `--no-setup` as a distinct skip of worktree plus claim.
  - **Integration Surface**: Spec alignment with architecture in the same commit.
- **specs/DeviaTDD-architecture.md**: Mark push-as-lock as the default, not mandatory.
  - **Current State**: Atomic Concurrency Protocol §7 always pairs `claim_issue()` + `create_worktree()` + `git push -u`.
  - **Changes Required**: State that push-as-lock is the default serialization. Local mode (`--local` or `claim_remote = false`) keeps worktree + ledger claim and skips the remote lock.
  - **Integration Surface**: Spec alignment with the API in the same commit.
- **CHANGELOG.md**: Record the user-visible config key and flags.
  - **Current State**: `[Unreleased]` already lists `deviate specify --local`.
  - **Changes Required**: Append one `[Unreleased]` bullet for `claim_remote`, `--no-claim-remote`, and `--local` on `meso run` / `run`.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: Config field and resolver
  - **Files**: `src/deviate/state/config.py`, `tests/test_state/test_config.py`
  - **Approach**: Add `claim_remote: bool = True` on `DeviateConfig`. Implement `resolve_claim_remote` beside `resolve_graphite_config` with inverted default (`True` on missing file, missing key, or non-bool). Keep `extra = forbid`.
  - **Verification**: `mise run test tests/test_state/test_config.py` — default, round-trip, true, false, key-absent, no-file.
- **Phase 2**: Effective-local resolution on the claim and discovery path
  - **Files**: `src/deviate/cli/meso.py`, `tests/test_cli/test_meso.py`, `tests/test_meso/test_specify.py`, `tests/test_meso/test_meso_orchestration.py`
  - **Approach**: Resolve `local = local or not resolve_claim_remote(cwd)` inside `_specify_pre` so `_claim_and_setup` and `plan pre` inherit it. Pass the same effective-local value into `_discover_claimable_issue`. Do not change `_try_claim_issue` skip-push semantics.
  - **Verification**: Config-false never calls `branch_exists_on_remote` or `git push`. `--local` still forwards `True` when config is true. Local discovery returns a BACKLOG whose origin branch exists. Default discovery still skips origin branches.
- **Phase 3**: `--local` on `meso run` and `deviate run`
  - **Files**: `src/deviate/cli/meso.py`, `src/deviate/cli/__init__.py`, `tests/test_meso/test_meso_orchestration.py`, `tests/test_cli/test_top_level_run.py`
  - **Approach**: Add `--local` to `meso_run_command` and `run_command`. Forward it to `_meso_run`. Keep `--no-setup` as the worktree/claim skip. Linked-worktree auto-detect still sets `no_setup=True` and must not force a second claim.
  - **Verification**: `meso run --local` and `run --local` call `_specify_pre(..., local=True)`. `--no-setup` (alone or with `--local`) does not call `_specify_pre`. Mock `_run_pytest` on tests that reach it.
- **Phase 4**: Setup persistence
  - **Files**: `src/deviate/cli/__init__.py`, `tests/test_cli/test_init.py`
  - **Approach**: Extend `_merge_flag_keys` with `claim_remote`. Wire `--no-claim-remote` through `_scaffold_dotfiles`. Fresh config writes `claim_remote = true`. Re-run upserts the key like `--graphite`. Optional TTY prompt only when the flag is omitted and `is_interactive()` is true.
  - **Verification**: `--no-claim-remote` writes `false` and keeps `[models]` / `timeout_seconds` / `[agent]`. Fresh setup without the flag writes `true`.
- **Phase 5**: Spec and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Document `claim_remote`, `--local` on meso run / run, and optional push-as-lock. Append the `[Unreleased]` bullet in the same commit as the behavior change.
  - **Verification**: Same-commit spec + changelog review against constitution §5 and AGENTS.md Spec Alignment.

## Data Flow Analysis
- **Input**: Typer `--local` (default `False`), `--no-setup`, `--no-claim-remote`, and `.deviate/config.toml` `claim_remote`.
- **Transform**: `_specify_pre` computes effective local as `local or not resolve_claim_remote(cwd)`. `_meso_run` uses the same value for auto-discovery and claim. `setup` writes or upserts the TOML key.
- **Claim path**: `_try_claim_issue` still creates `.worktrees/feat/{epic}/{issue}/`, still calls `claim_issue()` to SPECIFIED, still commits `specs/issues.jsonl`. Local mode prints `LOCAL_ONLY` and skips `branch_exists_on_remote` plus `git push`. Default mode still attempts `git push -u <remote> <branch>` and keeps `BRANCH_ON_REMOTE` / `PUSH_FAILED` / `--force` behavior.
- **Discovery path**: Default mode skips candidates whose origin branch exists. Local mode returns the first unblocked BACKLOG even when that branch exists on origin.
- **Setup skip**: `--no-setup` (and linked-worktree auto-detect) skips `_specify_pre` entirely. PLAN and TASKS run in `$CWD`. `--local` does not imply `--no-setup`.
- **Storage**: Standing default lives in `.deviate/config.toml`. Ledger state stays append-only in `specs/issues.jsonl`. No new ledger model.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Personal repos stop pushing because the default flips to false | High | Low | Keep `claim_remote` default `True`. Absent file and absent key resolve to `True`. |
| `--local` is treated as `--no-setup` and drops the worktree | High | Medium | Keep the two flags on separate branches in `_meso_run`. Pin combined `--no-setup --local` still skips `_specify_pre` only because of `--no-setup`. |
| Local discovery still skips leftover origin branches and starves auto-claim | Medium | High | Pass effective-local into `_discover_claimable_issue` and skip the origin check only in local mode. |
| Setup rewrite clobbers `[models]`, `timeout_seconds`, or `[agent]` | High | Medium | Reuse `_merge_flag_keys` upsert. Pin a merge test that keeps those keys. |
| `_claim_and_setup` / `plan pre` still push because resolution lives only on the Typer flag | Medium | Medium | Resolve config inside `_specify_pre`, not only at the command entry points. |
| Tests that hit `_run_pytest` blow the 30s suite budget | Medium | Medium | Mock `deviate.cli.micro._run_pytest` with `subprocess.CompletedProcess` on CLI tests that reach it. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (`.deviate/config.toml` read/write), subprocess (`git push`, `git add`, `git commit`, `ls-remote` / `branch_exists_on_remote`).
Negative tests: local mode never invokes `git push`; config-false never calls `branch_exists_on_remote`; `--no-setup` never claims; setup merge does not drop unrelated keys; unknown extra flags still fail Typer parsing.
Constraints: no new dependencies; no hardcoded secrets; no `--no-local` flag; do not skip the local claim commit; do not change Graphite stacked-PR flow; do not revert operator-local `.deviate/config.toml` values in this worktree.

## Integration Points
- **`resolve_claim_remote`**: Returns `True` unless the TOML bool is explicitly `false`. Callers: `_specify_pre`, optionally `_meso_run` before discovery.
- **`_specify_pre` → `_try_claim_issue`**: Forwards effective `local`. Explicit `local=True` always wins over config.
- **`_discover_claimable_issue(local=...)`**: Shared by bare `specify` and `_meso_run` auto-claim. Local mode does not skip origin branches.
- **`_claim_and_setup`**: Calls `_specify_pre` without a local kwarg and inherits config resolution. `deviate plan pre` outside a worktree uses this path.
- **`meso_run_command` / `run_command`**: New `--local` option. Forward to `_meso_run`. Do not treat `--local` as `--no-setup`.
- **`setup` / `_scaffold_dotfiles` / `_merge_flag_keys`**: Persist `claim_remote` beside `graphite` and `use_libref`.

## Constitutional Alignment
- **Architecture**: Meso claim stays in the three-layer (plus optional Product) model. Only the remote lock becomes optional. Worktree layout and ledger SPECIFIED stay mandatory (constitution §1 Git Isolation; architecture Atomic Concurrency Protocol as default).
- **Testing**: pytest unit tests under `tests/` with `tmp_git_repo` + `_git_env`. Coverage target ≥ 80% (constitution §3). Mock `_run_pytest` to keep the suite under 30s.
- **Git Isolation**: Every claim still uses `feat/{epic}/{issue}` and `.worktrees/feat/...`. Commits stay at phase boundaries. This issue branch is `feat/adhoc/017-optional-push-as-lock`. Do not delete branches.
- **Product Layer**: Issue `flow_refs` is `[]`. Downstream artifacts keep empty flow references. This plan does not author or sync Product-layer flows.
