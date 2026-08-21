---
title: "Optional push-as-lock: claim_remote config + --local on specify, meso run, and run"
labels: [enhancement, adhoc, vertical-slice, config, cli]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-017
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/017-optional-push-as-lock.md`
- **Primary Architectural Workstations**:
  - `src/deviate/state/config.py` — TARGET: add `claim_remote: bool = True` on `DeviateConfig` (`extra = forbid`); add `resolve_claim_remote(root) -> bool` defaulting to `True` when the key or file is absent (parallel to `resolve_graphite_config`, inverted default).
  - `src/deviate/cli/meso.py::_try_claim_issue` — REFERENCE: already honors `local=True` (skip `branch_exists_on_remote`, skip `git push`, `ALREADY_CLAIMED_LOCAL` reuse). Do not change worktree layout or `feat/{epic}/{issue}` naming. Do not skip `claim_issue()` or the local claim commit.
  - `src/deviate/cli/meso.py::_specify_pre` — TARGET: when the caller omits `local=True`, resolve standing config (`local = local or not resolve_claim_remote(cwd)`). Explicit `local=True` always wins.
  - `src/deviate/cli/meso.py::_discover_claimable_issue` — TARGET: in local mode, do not skip candidates whose `feat/{epic}/{issue}` branch already exists on origin.
  - `src/deviate/cli/meso.py::_meso_run` / `meso_run_command` — TARGET: add `--local`; forward to `_specify_pre` and `_discover_claimable_issue`. Do not treat `--local` as `--no-setup`.
  - `src/deviate/cli/meso.py::specify` — TARGET: keep `--local`; omitted flag honors config. Auto-discovery path must pass the same effective-local value into `_discover_claimable_issue`.
  - `src/deviate/cli/meso.py::_claim_and_setup` — TARGET: inherits config via `_specify_pre` so `deviate plan pre` outside a worktree also skips push when `claim_remote = false`.
  - `src/deviate/cli/__init__.py::run_command` — TARGET: add `--local` and forward to `_meso_run` so auto-claim on `deviate run` does not push when local.
  - `src/deviate/cli/__init__.py::setup` / `_scaffold_dotfiles` / `_merge_flag_keys` / `_CONFIG_TOML_COMMENTS` — TARGET: persist `claim_remote` on new configs (default `true`); `--no-claim-remote` (and optional interactive prompt when TTY and the flag is omitted) writes `false` without clobbering `[models]`, `timeout_seconds`, `backend`, or other keys.
  - `tests/test_state/test_config.py` — TARGET: default / round-trip / `resolve_claim_remote` absent-key = true.
  - `tests/test_cli/test_meso.py` / `tests/test_meso/test_specify.py` / `tests/test_meso/test_meso_orchestration.py` — TARGET: config-false skips push; `--local` overrides config-true; discovery does not skip origin branches in local mode; meso run / run forward `--local`; `--no-setup` still drops worktree.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document `claim_remote`, `--local` on meso run / run, and that Atomic Concurrency Protocol push-as-lock is optional.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible config key and flags.
- **Upstream Evidence**:
  - `src/deviate/cli/meso.py:433-627` — `_try_claim_issue(..., local=True)` already skips remote check + push.
  - `src/deviate/cli/meso.py:1919-1959` — `deviate specify --local` exists; auto-discover still calls `_discover_claimable_issue()` which always consults origin today.
  - `src/deviate/cli/meso.py:1512-1557` — `_discover_claimable_issue` treats origin branch as claimed-elsewhere.
  - `src/deviate/cli/meso.py:1649-1744` / `1866-1894` — `_meso_run` / `meso_run_command` have `--no-setup` but never pass `local=True`.
  - `src/deviate/cli/__init__.py:1018-1046` — `deviate run` calls `_meso_run(issue_id=..., force=...)` with no local flag.
  - `src/deviate/state/config.py:162-177` — `DeviateConfig` has `graphite` but no `claim_remote`.

## The Problem Contract

Claiming an issue creates a worktree on `feat/{epic}/{issue}`, writes ledger BACKLOG → SPECIFIED, commits, then `git push -u <remote> <branch>` as a distributed lock. That lock is reasonable for a personal repo and is today's default. It is not reasonable as a default at work: it may need review, it pollutes a shared remote, and it is pointless for a single operator. `deviate specify --local` already skips the remote check and the push while keeping worktree + branch + ledger claim. `deviate meso run` and `deviate run` never pass `local=True`, so the work path still pushes. `--no-setup` is the wrong escape because it drops the worktree too. This issue turns off **only** the push-as-lock via standing config and a flag override.

## Scope Boundaries

### Hard Inclusions
- Add `claim_remote: bool = True` to `DeviateConfig` and `resolve_claim_remote(root) -> bool` (absent key / absent file → `True`).
- Effective local mode: `--local` OR `claim_remote = false`. Flag overrides config. Omitted flag uses config.
- In local mode, `_try_claim_issue` / `_specify_pre` skip remote-branch-exists and skip `git push`; still create `.worktrees/feat/{epic}/{issue}/`, still `claim_issue()` → SPECIFIED, still commit the claim locally.
- In local mode, `_discover_claimable_issue` must not treat "branch already on origin" as claimed-elsewhere (personal leftover origin branches must not starve auto-claim).
- `deviate specify --local` stays; omitted flag honors config.
- New `deviate meso run --local` and `deviate run --local` with the same meaning; both also honor config when the flag is omitted.
- `deviate setup --no-claim-remote` writes `claim_remote = false` (surgical merge, parallel to `--graphite`). Optional TTY prompt when the flag is omitted. Fresh setup without the flag writes `claim_remote = true`.
- `_claim_and_setup` / `deviate plan pre` (outside a worktree) inherit the same resolution through `_specify_pre`.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit (Atomic Concurrency Protocol: push-as-lock is the default, not mandatory).
- Append a `CHANGELOG.md` `[Unreleased]` bullet.

### Defensive Exclusions
- Do NOT skip ledger SPECIFIED or the local claim commit.
- Do NOT change `feat/{epic}/{issue}` branch naming or `.worktrees/feat/...` layout.
- Do NOT treat `--local` as `--no-setup`. `--no-setup` still skips worktree + ledger claim.
- Do NOT change Graphite / stacked PR flow (`graphite = true` path).
- Do NOT implement #59 two-counter retry or #60 shard padding.
- Do NOT revert operator-local `.deviate/config.toml` settings (`backend=pi`, `transport=cli`, `pi_rpc=false`, `timeout=1800`, `models.default=grok-4.6`, `timeout_seconds=1800`).
- Do NOT add a `--no-local` flag; flipping back to remote lock is a config edit (`claim_remote = true`).
- Do NOT author or synchronize Product-layer flows; `flow_refs: []`.
- Do NOT add tests that invoke `deviate.cli.micro._run_pytest` without mocking it.
- Classification for plan/tasks: this is CLI/config **behavior** (resolution + discovery + flags), not prompt-only text. Prefer a RED/GREEN cycle for the claim path. Do not classify as IMMEDIATE prompt/shard-rule work.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-017`
- **Acceptance Criteria Tokens**: `AC-ADHOC-017-01`, `AC-ADHOC-017-02`, `AC-ADHOC-017-03`, `AC-ADHOC-017-04`, `AC-ADHOC-017-05`, `AC-ADHOC-017-06`
- **Data Model Entities**: `DeviateConfig.claim_remote` (boolean, default `true`; not a ledger model)
- **Spec Source Anchors**:
  - `specs/constitution.md` §1 Git Isolation Principle — worktree/branch isolation stays; only the remote lock is optional
  - `specs/constitution.md` §2 Config — `.deviate/config.toml` is the standing config surface
  - `specs/DeviaTDD-architecture.md` Atomic Concurrency Protocol — push-as-lock is the default serialization mechanism
  - `specs/DeviaTDD-api.md` `deviate specify [--local]` — existing local-claim contract to extend, not replace

## User Stories Ledger

- **US-017-01**: As a work-repo operator, I want `deviate setup` to persist `claim_remote = false` so specify / meso run / run claim locally without pushing a lock branch to the shared remote. *(Ref: FR-ADHOC-017)*
- **US-017-02**: As a personal-project operator, I want the default (`claim_remote = true`, no flag) to keep pushing the claim branch so today's distributed lock still works. *(Ref: FR-ADHOC-017)*
- **US-017-03**: As an operator on a one-shot no-remote run, I want `--local` on specify / meso run / run to skip the push even when config still says `claim_remote = true`. *(Ref: FR-ADHOC-017)*

## Acceptance Outline

- **AO-017-01** *(Ref: AC-ADHOC-017-01, US-017-02)*: Default claim still pushes the lock branch.
  - **Happy Path**: No `claim_remote` key (or `true`) and no `--local` → worktree created, SPECIFIED written, claim committed, `git push -u <remote> <branch>` attempted.
  - **Error Category**: Push race / remote error keeps today's `_try_claim_issue` failure behavior (`BRANCH_ON_REMOTE` / `PUSH_FAILED` / `--force` continue).
  - **Boundary Category**: Absent config file equals `claim_remote = true`.
- **AO-017-02** *(Ref: AC-ADHOC-017-02, US-017-01)*: Standing `claim_remote = false` skips only the remote lock.
  - **Happy Path**: `deviate specify 001-001` and `deviate meso run --issue 001-001` create `.worktrees/feat/...` and SPECIFIED locally; no remote-branch pre-check; no `git push`.
  - **Error Category**: Worktree create failure still returns `None` / `CLAIM_FAILED` as today.
  - **Boundary Category**: Ledger claim commit still runs; `LOCAL_ONLY` banners still emit.
- **AO-017-03** *(Ref: AC-ADHOC-017-03, US-017-03)*: `--local` overrides config `true` on specify, meso run, and run.
  - **Happy Path**: Config `claim_remote = true` plus `--local` takes the same skip-push path as AO-017-02.
  - **Error Category**: Unknown extra flags still fail Typer parsing.
  - **Boundary Category**: Omitted `--local` with `claim_remote = true` remains the push path (AO-017-01).
- **AO-017-04** *(Ref: AC-ADHOC-017-04, US-017-01)*: Setup persists the standing default.
  - **Happy Path**: `deviate setup --no-claim-remote` writes `claim_remote = false`; fresh setup without the flag writes `claim_remote = true`.
  - **Error Category**: Existing config merge must not drop `[models]` / `timeout_seconds` / `[agent]`.
  - **Boundary Category**: Interactive prompt (TTY only, flag omitted) can set the same key; non-interactive sessions without the flag keep the `true` default.
- **AO-017-05** *(Ref: AC-ADHOC-017-05, US-017-01)*: Local discovery ignores origin-as-claimed.
  - **Happy Path**: With local mode on, a BACKLOG issue whose `feat/{epic}/{issue}` already exists on origin is still returned by `_discover_claimable_issue`.
  - **Error Category**: Empty ledger / no BACKLOG still returns `None` / `NO_CLAIMABLE_ISSUES`.
  - **Boundary Category**: With `claim_remote = true` and no `--local`, origin-branch skip remains (today's behavior).
- **AO-017-06** *(Ref: AC-ADHOC-017-06)*: `--no-setup` stays a different escape hatch.
  - **Happy Path**: `--no-setup` still skips worktree creation and ledger claim; PLAN+TASKS run in `$CWD`.
  - **Error Category**: Combining `--no-setup` with `--local` does not invent a third mode — `--no-setup` still wins for setup skipping.
  - **Boundary Category**: Local mode never implies `--no-setup`.

## Edge Cases and Boundaries

- **Existing local branch + `--local`**: keep `ALREADY_CLAIMED_LOCAL` reuse (no ledger re-write); config-false uses the same short-circuit because it shares `local=True` inside `_try_claim_issue`.
- **No `origin` remote**: today's `_try_claim_issue` still attempts push when not local; local mode must not call push even if origin exists.
- **Force-update setup**: re-running `deviate setup --no-claim-remote` on an existing config must upsert `claim_remote` like `_merge_flag_keys` does for `graphite`, not rewrite the whole file.
- **Plan-pre auto-claim**: `_claim_and_setup` currently calls `_specify_pre` without `local`; resolution must live in `_specify_pre` (or a shared helper) so every claim path honors config.
- **Linked worktree auto-detect**: `_meso_run` still treats an existing linked worktree as `--no-setup` continuation; `--local` must not force a second claim/push from inside that worktree.
- **Default True is the compatibility contract**: personal projects with no config change must still push.

## Performance Constraints

- **L_max (config resolve)**: `resolve_claim_remote` is one TOML load already used for models/graphite; extra latency ≤ 5ms, well under AGENTS.md L_max ≤ 500ms init / ≤ 200ms per agent export.
- **Claim path**: local mode is strictly less I/O (no `ls-remote` / no `git push`); no new subprocesses.
- **Full test suite**: `mise run test` remains < 30s. New tests must use `tmp_git_repo` + `_git_env` and must mock `_run_pytest` if they invoke CLI commands that reach it.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_state/test_config.py` — `test_config_claim_remote_field_default` (`True`); round-trip; `resolve_claim_remote` true / false / key-absent / no-file.
  - `tests/test_cli/test_meso.py::TestSpecifyLocalFlag` — keep existing `local=True` pins; add config-false path that never calls `branch_exists_on_remote` or `git push`.
  - `tests/test_meso/test_specify.py` — omitted `--local` with `claim_remote = false` forwards `local=True` into `_specify_pre`; `--local` with `claim_remote = true` still forwards `True`.
  - `tests/test_meso/test_meso_orchestration.py::TestDiscoverClaimableIssue` — local mode (flag or config-false) returns the first BACKLOG even when `branch_exists_on_remote` is True; default mode still skips origin branches.
- **Integration Sandbox Targets**:
  - `tests/test_meso/test_meso_orchestration.py` — `meso run --local` calls `_specify_pre(..., local=True)`; `meso run` without flag with `claim_remote = false` does the same; `--no-setup` still does not call `_specify_pre`.
  - `tests/test_cli/` (run / setup) — `deviate run --local` forwards to `_meso_run`; `deviate setup --no-claim-remote` writes `claim_remote = false` without clobbering other keys.

## Demonstration Path
```bash
# 1. Default (personal): claim still attempts push
deviate specify --help | rg -n "local"
deviate meso run --help | rg -n "local|no-setup"
deviate run --help | rg -n "local"

# 2. Standing work-repo default
deviate setup --agent pi --no-claim-remote
rg -n "claim_remote" .deviate/config.toml

# 3. After implementation: specify + meso run create worktree + SPECIFIED, no push
# (run inside a fixture repo with a BACKLOG issue; do not push this product repo)
# deviate specify ISS-ADH-017
# deviate meso run --issue ISS-ADH-017 --local

# 4. Targeted tests
mise run test tests/test_state/test_config.py tests/test_cli/test_meso.py tests/test_meso/test_specify.py tests/test_meso/test_meso_orchestration.py -v

# 5. Lint / types / full suite
mise run lint
mise run format-check
mise run check-types
mise run test
```
