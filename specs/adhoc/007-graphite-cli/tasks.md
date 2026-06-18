# Implementation Tasks: `feat/adhoc/007-graphite-cli`

## Phase 1: Config Model Foundation
**Goal**: Add `graphite` field to `DeviateConfig` Pydantic model and a `resolve_graphite_config()` runtime helper

### Tasks

- TSK-007-01: Add `DeviateConfig.graphite` field and `resolve_graphite_config()` helper
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_config.py::test_config_graphite_field_default tests/test_state/test_config.py::test_config_graphite_field_explicit_true tests/test_cli/test_init.py::test_resolve_graphite_config_true tests/test_cli/test_init.py::test_resolve_graphite_config_false -v`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `src/deviate/cli/__init__.py`
  - **Rationale**: `config.py` receives the `graphite: bool = Field(default=False)` field on `DeviateConfig` (line 106) per US-007-01 (FR-ADHOC-007) — this is the canonical data entity for the configuration contract. `cli/__init__.py` receives `resolve_graphite_config(root: Path) -> bool` because it is the module-level CLI utility that reads `.deviate/config.toml` at runtime; both `meso.py` and `feature.py` already import from `cli/__init__.py` (via `cli/__init__.py:12-14` imports), making this the natural integration surface for the config-reading helper consumed by TSK-007-04 and TSK-007-05.
  - **Details**:
    - **Red**: Write `test_config_graphite_field_default` asserting `DeviateConfig().graphite` is `False`; `test_config_graphite_field_explicit_true` asserting `DeviateConfig(graphite=True).graphite` is `True` and `model_dump()` includes `"graphite": True`. In `tests/test_cli/test_init.py`, write `test_resolve_graphite_config_true` creating a `.deviate/config.toml` with `graphite = true` in `tmp_git_repo` and asserting `resolve_graphite_config(repo)` returns `True`; `test_resolve_graphite_config_false` asserting `False` when key absent or `false`.
    - **Green**: In `config.py:98-106`, add `graphite: bool = Field(default=False)` to `DeviateConfig`. In `cli/__init__.py`, add `resolve_graphite_config(root: Path) -> bool` that reads `.deviate/config.toml` via `tomllib.load`, returns `data.get("graphite", False)`. Catch `FileNotFoundError` and `TOMLDecodeError` returning `False` per Edge Cases line 84.
    - **Refactor**: Verify `_serialize_value` at `cli/__init__.py:57-58` already handles `bool` round-trip. Confirm `model_dump()` → `_dict_to_toml` path correctly serializes `graphite = true` / `graphite = false` per existing bool handling. No other refactoring needed — this is greenfield on a well-established model.
    - **Edge Cases**: TOML file missing entirely → return `False`. TOML file has no `graphite` key → return `False`. TOML file has `graphite = false` → return `False`. Malformed TOML → return `False`. `model_config = {"extra": "forbid"}` on `DeviateConfig` does NOT reject the defined `graphite` field (it's part of the model).
    - **Acceptance**: `DeviateConfig().graphite is False`, `DeviateConfig(graphite=True).graphite is True`, `resolve_graphite_config()` reads correctly from filesystem TOML. No regressions in existing config tests (`pytest tests/test_state/ -v`).

---

## Phase 2: Init Integration & Governance
**Goal**: Wire `--graphite` CLI flag through init command, persist in config, and emit conditional governance section

### Tasks

- TSK-007-02: Add `--graphite` flag to `deviate init` and thread through to config persistence
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_with_graphite_flag tests/test_cli/test_init.py::test_init_without_graphite_flag tests/test_cli/test_init.py::test_init_graphite_toml_round_trip -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-007-01
  - **Files**:
    - `src/deviate/cli/__init__.py`
  - **Rationale**: The `init` command signature at line 320 and `_scaffold_dotfiles` at line 225 are modified to accept and persist the `graphite` boolean. This satisfies AC-ADHOC-007-01 (config.toml contains `graphite = true` after `init --graphite`) and AC-ADHOC-007-02 (config.toml omits or defaults `graphite` when flag absent). The `_scaffold_dotfiles` function at line 230 already constructs a `DeviateConfig` — extending it to pass `graphite` is a surgical parameter threading.
  - **Details**:
    - **Red**: Write `test_init_with_graphite_flag` in `tests/test_cli/test_init.py` using `runner.invoke(cli, ["init", "--graphite"])` on a `tmp_git_repo`, asserting `.deviate/config.toml` contains `graphite = true`. Write `test_init_without_graphite_flag` asserting `graphite = false` or key absent. Write `test_init_graphite_toml_round_trip` asserting `DeviateConfig.model_validate({"graphite": True})` works and that `_dict_to_toml` serializes it correctly.
    - **Green**: In `cli/__init__.py:320-331`, add `graphite: bool = typer.Option(False, "--graphite", help="Enable Graphite stacked-changes workflow")` to `init()` signature. Pass `graphite` to `_scaffold_dotfiles(workdir, agent_export_mode, graphite)` at line 336. Update `_scaffold_dotfiles` signature at line 225 to accept `graphite: bool = False`. Construct `DeviateConfig(agent_export_mode=agent_export_mode, graphite=graphite)` at line 230. `model_dump()` includes the field; `_dict_to_toml` serializes via `_serialize_value` bool branch.
    - **Refactor**: Confirm `_write_if_missing` at line 45 correctly skips existing config.toml (idempotency preserved — re-running init won't overwrite user edits). No other refactoring needed.
    - **Edge Cases**: `_write_if_missing` skips existing config → flag on re-run won't overwrite. `model_validate` from existing TOML without `graphite` key defaults to `False` (Pydantic field default). TOML round-trip: `graphite = true` → `tomllib.load` → `bool(True)` → `_serialize_value` → `"true"` (line 57-58 already handles this).
    - **Acceptance**: `runner.invoke(cli, ["init", "--graphite"])` writes `graphite = true` in `.deviate/config.toml`. `runner.invoke(cli, ["init"])` writes `graphite = false` or omits key. Existing init tests pass without modification. AC-ADHOC-007-01 and AC-ADHOC-007-02 satisfied.

- TSK-007-03: Create Graphite governance seed file and add conditional governance section
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_graphite_governance_section_present tests/test_cli/test_init.py::test_init_graphite_governance_section_absent tests/test_cli/test_init.py::test_init_graphite_governance_idempotent -v`
  - **Estimated Time**: 50 minutes
  - **Dependency**: TSK-007-02
  - **Files**:
    - `src/deviate/prompts/governance/graphite_seed.md`
    - `src/deviate/cli/__init__.py`
  - **Rationale**: `graphite_seed.md` is the new governance seed resource containing the `## Graphite Stacked Changes Workflow` section per spec Hard Inclusions (line 22-23). `cli/__init__.py:_apply_governance` at line 257-270 is updated to conditionally read and upsert this seed into CLAUDE.md/AGENTS.md when `graphite = true`. Satisfies AC-ADHOC-007-03 (section present when enabled) and AC-ADHOC-007-04 (section absent when disabled).
  - **Details**:
    - **Red**: Write `test_init_graphite_governance_section_present` — create a `.deviate/config.toml` with `graphite = true` in `tmp_git_repo`, run `_apply_governance(repo)` or `runner.invoke(cli, ["init", "--graphite"])`, assert `## Graphite Stacked Changes Workflow` exists in both CLAUDE.md and AGENTS.md. Write `test_init_graphite_governance_section_absent` with `graphite = false`, assert section is NOT present. Write `test_init_graphite_governance_idempotent` to verify re-running init with graphite updates existing block per `_upsert_governance_block` pattern.
    - **Green**: Create `src/deviate/prompts/governance/graphite_seed.md` containing `## Graphite Stacked Changes Workflow` section with `gt create -am "feat/<slug>"`, `gt submit --stack`, `gt sync`, and anti-pattern warnings (do not use `git checkout -b`/`gh pr create` alongside `gt`). In `_apply_governance` at line 257-270, after writing CLAUDE.md and AGENTS.md, load config TOML via `tomllib.load((workdir / ".deviate" / "config.toml").read_text())`, check `config.get("graphite", False)`. If `True`, read `graphite_seed.md` via `_read_seed("deviate.prompts.governance", "graphite_seed.md")` and call `_upsert_governance_block` for each target file with the graphite seed content. Follow existing pattern — `_upsert_governance_block` already handles create/append/update via `## Graphite Stacked Changes Workflow` header detection at line 206-222.
    - **Refactor**: No extraction needed for seed reading — uses existing `_read_seed` + `_upsert_governance_block` pattern. The `_apply_governance` function grows from 13 lines to ~25 lines — acceptable given the single conditional block. Follow EXACT existing pattern from lines 258-270 (read → upsert for CLAUDE.md, read → upsert for AGENTS.md) extended with graphite conditional.
    - **Edge Cases**: Config TOML file missing entirely → treat as `graphite = False` (no section). Config TOML has `graphite = false` → no section. Existing CLAUDE.md already has `## Graphite Stacked Changes Workflow` → update in-place per `_upsert_governance_block` regex pattern (line 216-220). graphite_seed.md missing from package resources → `_read_seed` returns `None`, gracefully skip.
    - **Acceptance**: With `graphite = true` in config, CLAUDE.md and AGENTS.md both contain `## Graphite Stacked Changes Workflow` section. With `graphite = false` or absent, neither file contains the section. Idempotent across repeated `init` runs. AC-ADHOC-007-03 and AC-ADHOC-007-04 satisfied.

---

## Phase 3: Runtime Routing
**Goal**: Route branch creation and PR submission through `gt` commands when `graphite = true`

### Tasks

- TSK-007-04: Conditional `gt create -am` routing in `_create_feature_branch`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_feature.py::test_feature_create_with_graphite tests/test_cli/test_feature.py::test_feature_create_without_graphite -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-007-01
  - **Files**:
    - `src/deviate/cli/feature.py`
  - **Rationale**: `feature.py:_create_feature_branch` at line 27-42 unconditionally calls `git branch`. With `graphite = true`, it must call `gt create -am` instead per spec Hard Inclusions line 25 and AC-ADHOC-007-06. The `resolve_graphite_config()` helper from TSK-007-01 is the integration point — imported from `cli/__init__.py`. This is a single conditional branch at line 37 with fallback to existing `git branch` path when `graphite = false` (AC-ADHOC-007-07).
  - **Details**:
    - **Red**: Write `test_feature_create_with_graphite` in `tests/test_cli/test_feature.py` — mock `subprocess.run` with `side_effect` (first call for `git rev-parse` returns non-zero, second observed), call `_create_feature_branch(slug, repo_path)` where config has `graphite = true`, assert `subprocess.run` was called with `["gt", "create", "-am", "feat/<slug>"]`. Write `test_feature_create_without_graphite` asserting `["git", "branch", "feat/<slug>"]` when `graphite = false`. Mock `resolve_graphite_config` return value.
    - **Green**: In `feature.py:27-42`, import `resolve_graphite_config` from `deviate.cli.__init__` (add import at top). Before the `subprocess.run(["git", "branch", branch_name], ...)` at line 37, call `resolve_graphite_config(repo_path)`. If `True`, construct `cmd = ["gt", "create", "-am", f"feat/{slug}"]` and `subprocess.run(cmd, cwd=repo_path, env=git_env(), check=True)`. If `False`, fall through to existing `git branch` path. Preserve the `git rev-parse --verify` existence check at lines 29-36 for both paths.
    - **Refactor**: Extract the branch-creation subprocess logic into a single conditional with identical `cwd=repo_path, env=git_env(), check=True` parameters. The `git rev-parse` pre-check at lines 29-36 applies to both paths unchanged — `gt create` on an existing branch name is handled by Graphite's own collision check.
    - **Edge Cases**: `gt` binary not on `$PATH` when `graphite = true` → `subprocess.run` raises `FileNotFoundError`, which propagates to caller with clear error (per Edge Cases line 84). `gt create -am` on clean working tree may fail → surface `CalledProcessError` with stderr (per Edge Cases line 87). Branch already exists per `git rev-parse` → return early before either path (existing guard at line 35-36). Both paths use `git_env()` for isolation.
    - **Acceptance**: When `graphite = true`, `_create_feature_branch("my-feature", repo)` calls `gt create -am "feat/my-feature"`. When `graphite = false`, original `git branch feat/my-feature` path is preserved. All existing feature tests pass. AC-ADHOC-007-06 and AC-ADHOC-007-07 satisfied.

- TSK-007-05: Conditional `gt submit --stack` routing in `_pr_run`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_meso.py::test_pr_run_with_graphite tests/test_cli/test_meso.py::test_pr_run_without_graphite tests/test_cli/test_meso.py::test_pr_run_graphite_merge_flags_ignored -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-007-01
  - **Files**:
    - `src/deviate/cli/meso.py`
  - **Rationale**: `meso.py:_pr_run` at line 930-1018 unconditionally constructs `["gh", "pr", "create", ...]` at line 1009. With `graphite = true`, it must use `["gt", "submit", "--stack"]` per spec Hard Inclusions line 24 and AC-ADHOC-007-05. `resolve_graphite_config()` from TSK-007-01 is the integration point. The function also handles `merge` and `auto_merge` flags (lines 1010-1013) which are incompatible with `gt submit --stack` — these must be silently ignored with a warning when graphite is active (per plan Risk Assessment).
  - **Details**:
    - **Red**: Write `test_pr_run_with_graphite` in `tests/test_cli/test_meso.py` — mock `subprocess.run`, `_load_session_accept` (returning a session with `active_issue_id`), `resolve_issue_record`, `_append_ledger_event`. Set up `.deviate/config.toml` with `graphite = true`. Assert final `subprocess.run` call uses `["gt", "submit", "--stack"]`. Write `test_pr_run_without_graphite` asserting `["gh", "pr", "create", ...]` path. Write `test_pr_run_graphite_merge_flags_ignored` asserting that when `merge=True` and `graphite=True`, the `gt submit --stack` command is used without `--merge` flag, and a warning is logged.
    - **Green**: In `meso.py:_pr_run` at line 1008-1014, before constructing `cmd`, call `resolve_graphite_config(repo_root)`. If `True`:
      1. If `merge or auto_merge`: log `[yellow]GRAPHITE_MERGE_FLAGS_IGNORED[/]` via `console.print`.
      2. Set `cmd = ["gt", "submit", "--stack"]`.
      If `False`: use existing `["gh", "pr", "create", ...]` logic (lines 1009-1013). Note: `gt submit --stack` has no `--title` or `--body-file` equivalent — it uses the branch's commit metadata. The existing PR title/body generation at lines 1008 and the body file are still created but not passed to `gt`. Import `resolve_graphite_config` from `deviate.cli.__init__` (add to imports).
    - **Refactor**: Keep the graphite branch as a clean early-return or conditional block separate from the `gh` path. Do not extract `gh` path into a separate function — the change is a single conditional at line 1008-1014. The `resolve_graphite_config` call happens once before the command construction, reusing the `repo_root` already resolved at line 949.
    - **Edge Cases**: `gt` not on `$PATH` → `FileNotFoundError` propagates (default subprocess behavior). `gt submit --stack` without prior `gt create` → Graphite CLI surfaces its own error. `merge`/`auto_merge` flags with graphite → silently ignored with warning, per plan Risk Assessment line. `_pr_run` already has extensive try/except around subprocess calls — the graphite path inherits this safety net. Ledger update (COMPLETED event) at lines 957-963 is unchanged — it runs before the PR command.
    - **Acceptance**: When `graphite = true`, `_pr_run(body_file)` calls `gt submit --stack`. When `graphite = false`, existing `gh pr create` path preserved. Merge flags ignored with warning when graphite enabled. All existing meso tests pass. AC-ADHOC-007-05 and AC-ADHOC-007-07 satisfied.

---

## Phase 4: Documentation
**Goal**: Document graphite integration in the deviate-pr skill prompt

### Tasks

- TSK-007-06: Document `gt submit` path in `deviate-pr/SKILL.md`
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `ruff check .opencode/skills/deviate-pr/SKILL.md`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `.opencode/skills/deviate-pr/SKILL.md`
  - **Rationale**: The deviate-pr skill prompt at lines 67-75 documents the `deviate pr run` command and flags. When `graphite = true`, the command routes to `gt submit --stack` and the `--merge`/`--auto-merge` flags are not applicable. Agents executing the PR workflow need this context to avoid confusion when graphite is active. This is a pure documentation update — no code changes. Per spec Hard Inclusions line 26.
  - **Details**:
    - **Implementation**: In `.opencode/skills/deviate-pr/SKILL.md`, after step 4's command block (line 69), add a note documenting that when `graphite = true` in `.deviate/config.toml`, the `deviate pr run` command routes to `gt submit --stack` instead of `gh pr create`. Mention that `--merge` and `--auto-merge` flags are silently ignored in graphite mode and that users should rely on Graphite's native merge workflow. Place this note before the options list (line 71) or as a new sub-bullet under step 4. Keep the change minimal — do not restructure the document.
    - **Edge Cases**: Not applicable — doc-only change.
    - **Acceptance**: SKILL.md step 4 documents the graphite path. `ruff check .opencode/skills/deviate-pr/SKILL.md` passes. No test regressions.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-007-01) — Config model + helper foundation
2. Phase 2 (TSK-007-02 → TSK-007-03) — Init flag + governance
3. Phase 3 (TSK-007-04, TSK-007-05 in parallel) — Runtime routing
4. Phase 4 (TSK-007-06) — Documentation

**Critical Dependency Chains**:
- TSK-007-01 must precede all other tasks (provides `DeviateConfig.graphite` and `resolve_graphite_config()`)
- TSK-007-02 must precede TSK-007-03 (governance logic needs config written to disk by init flow)
- TSK-007-04 and TSK-007-05 both depend on TSK-007-01 only and can run in parallel

**Risk Hotspots**:
- `gt` binary not on `$PATH` when `graphite = true` — `FileNotFoundError` propagates from `subprocess.run` with clear message; no auto-install per Defensive Exclusions line 29
- `_write_if_missing` skips existing `config.toml` during `init` — when TSK-007-02's tests validate config content, they must delete `.deviate/config.toml` first or use a fresh `tmp_git_repo`
- `_pr_run` mocks are extensive — tests must mock `_load_session_accept`, `resolve_issue_record`, `_append_ledger_event`, AND `subprocess.run`; use `@patch.multiple` for clarity

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` touched by TSK-007-01, TSK-007-02, TSK-007-03
- `src/deviate/state/config.py` touched by TSK-007-01 only

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

- **Mock `subprocess.run` for external CLI calls**: Tests for TSK-007-04 and TSK-007-05 mock `subprocess.run` to assert the correct `gt` or `git`/`gh` command is constructed without actually invoking external binaries. Use `@patch("deviate.cli.feature.subprocess.run")` and `@patch("deviate.cli.meso.subprocess.run")`.
- **Mock `_run_pytest` for micro-layer tests**: Not applicable to this issue — no micro-layer (red/green/refactor post) commands are modified.
- **Config round-trip validation**: Tests for TSK-007-01 and TSK-007-02 should verify that `_dict_to_toml(DeviateConfig(graphite=True).model_dump())` produces `graphite = true` and that `tomllib.loads(...)` parses it back correctly.
