## Plan Summary
- **Issue**: ISS-ADH-007 — Graphite CLI Integration — Optional Branch & PR Management via `gt`
- **Implementation Strategy**: Add a `graphite: bool = False` field to `DeviateConfig`, thread a `--graphite` CLI flag through `deviate init` to persist it in `.deviate/config.toml`, add a `resolve_graphite_config()` helper to load the key from TOML at runtime, and insert conditional branches in `feature.py:_create_feature_branch` and `meso.py:_pr_run` that route to `gt create -am` and `gt submit --stack` respectively when `graphite = true`. Governance seeds gain a conditional `## Graphite Stacked Changes Workflow` section emitted only when `graphite = true`.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Workstation Mapping
- **`src/deviate/state/config.py`**: Add `graphite: bool = False` field to `DeviateConfig` model
  - **Current State**: `DeviateConfig` (line 98-106) has `profile`, `llm_backend`, `timeout_seconds`, `agent_export_mode`, `agent`, `models` — no `graphite` field. `model_config = {"extra": "forbid"}` is active.
  - **Changes Required**: Add `graphite: bool = Field(default=False)` to `DeviateConfig`. No validation logic needed — a simple boolean with default False. When `model_dump()` runs, it includes `graphite: False`, serialized via `_serialize_value` as `graphite = false` (line 57-58 of `cli/__init__.py` handles `bool` already).
  - **Integration Surface**: Consumed by `cli/__init__.py` for config writing during init, by `cli/meso.py` for PR routing decision, and by `cli/feature.py` for branch creation routing.

- **`src/deviate/cli/__init__.py`**: Add `--graphite` flag, thread through `_scaffold_dotfiles`, add conditional governance section
  - **Current State**: `init` command (line 320-350) takes `agent_export_mode`, `generate_constitution`, and `agent` params. `_scaffold_dotfiles` (line 225-236) creates `DeviateConfig` with only `agent_export_mode` parameter and writes config via `_dict_to_toml` + `_write_if_missing`. `_apply_governance` (line 257-270) unconditionally writes CLAUDE.md/AGENTS.md from seed files. No `resolve_graphite_config()` helper exists.
  - **Changes Required**:
    1. Add `--graphite` boolean flag to `init` command (line 320): `graphite: bool = typer.Option(False, "--graphite", help="Enable Graphite stacked-changes workflow (gt create + gt submit)")`
    2. Pass `graphite` through to `_scaffold_dotfiles(workdir, agent_export_mode, graphite)`
    3. In `_scaffold_dotfiles`, include `graphite=graphite` in `DeviateConfig(...)` constructor
    4. Pass `graphite` config to `_apply_governance`: load config TOML, conditionally append `## Graphite Stacked Changes Workflow` section from a separate seed file `graphite_seed.md` using `_upsert_governance_block` (following existing pattern at line 196-222 that already supports create/append/update idempotency)
    5. Add `resolve_graphite_config(root: Path) -> bool` helper at module level: reads `.deviate/config.toml`, returns `data.get("graphite", False)`. Gracefully returns `False` on file-not-found or parse errors.
  - **Integration Surface**: `_dict_to_toml` (line 65-91), `_serialize_value` (line 54-62), `_write_if_missing` (line 45-51), `DeviateConfig` model, `_upsert_governance_block` (line 196-222), `_read_seed` (line 187-193).

- **`src/deviate/cli/meso.py`**: Conditional branch in `_pr_run` for `gt submit --stack` vs `gh pr create`
  - **Current State**: `_pr_run` (line 930-1022) unconditionally uses `["gh", "pr", "create", ...]` (line 1009) with `--title`, `--body-file`, and optional `--merge`/`--auto-merge` flags. Config is not loaded for routing decisions.
  - **Changes Required**: Before the `cmd = [...]` block (line 1009), call `resolve_graphite_config(repo_root)`. If `True`, replace `cmd` with `["gt", "submit", "--stack"]`. Edge case: `gt submit --stack` doesn't accept `--merge` or `--auto-merge` — when graphite is enabled, log a warning if merge flags are passed and ignore them (or document in `deviate-pr/SKILL.md` that merge flags are incompatible with graphite).
  - **Integration Surface**: `resolve_graphite_config` from `cli/__init__.py`, existing `subprocess.run` pattern, `_git_env()` for subprocess isolation.

- **`src/deviate/cli/feature.py`**: Conditional branch in `_create_feature_branch` for `gt create -am` vs `git branch`
  - **Current State**: `_create_feature_branch` (line 27-42) checks if branch exists via `git rev-parse --verify`, then creates via `git branch`. No config-driven routing.
  - **Changes Required**: Before the `subprocess.run(["git", "branch", ...])` call at line 37, call `resolve_graphite_config(repo_path)`. If `True`, use `["gt", "create", "-am", f"feat/{slug}"]` instead of `["git", "branch", f"feat/{slug}"]`. Edge case: `gt create -am` auto-commits working changes — if working tree is clean this may fail. The issue spec (Edge Cases line 87) notes this: `gt create -m` (without `-a`) might be needed. Default to `-am` and catch `CalledProcessError`, surfacing a clear message instructing the user to install Graphite CLI if `gt` is not on `$PATH`.
  - **Integration Surface**: `resolve_graphite_config` from `cli/__init__.py`, `git_env()` for subprocess isolation.

- **`src/deviate/prompts/governance/graphite_seed.md`**: New seed file with Graphite workflow section
  - **Current State**: Does not exist (new file).
  - **Changes Required**: Create with `## Graphite Stacked Changes Workflow` section containing:
    - `gt create -am "feat/<slug>"` for branch creation (stages + commits working changes)
    - `gt submit --stack` for PR submission (submits stacked PRs)
    - `gt sync` for rebasing stack on trunk
    - Anti-pattern warnings: do not use `git checkout -b` alongside `gt` (branch conflicts); do not use `gh pr create` when graphite is active
  - **Integration Surface**: Read by `_apply_governance` via `_read_seed` + `importlib.resources`, written via `_upsert_governance_block` to both CLAUDE.md and AGENTS.md.

- **`.opencode/skills/deviate-pr/SKILL.md`**: Document `gt submit` as the PR creation path when graphite is enabled
  - **Current State**: 165 lines. `<execution_sequence>` step 4 (line 69) references `deviate pr run --body-file <path> [--merge] [--auto-merge]` using `gh pr create`. No graphite mention.
  - **Changes Required**: Add a note in step 4 that when `graphite = true` in `.deviate/config.toml`, the PR command routes to `gt submit --stack` instead of `gh pr create`. Mention that `--merge` and `--auto-merge` flags are not applicable in graphite mode.
  - **Integration Surface**: The deviate-pr skill prompt consumed by agents executing the PR workflow.

## Implementation Strategy
- **Phase 1**: Add `graphite` field to `DeviateConfig` and `resolve_graphite_config()` helper
  - **Files**: `src/deviate/state/config.py`, `src/deviate/cli/__init__.py`
  - **Approach**: Add `graphite: bool = Field(default=False)` to `DeviateConfig` (line 98-106). Add `resolve_graphite_config(root: Path) -> bool` to `cli/__init__.py` that reads `.deviate/config.toml` via `tomllib.load` and returns `data.get("graphite", False)`. Gracefully handles FileNotFoundError and TOMLDecodeError returning False.
  - **Verification**: Unit test `test_config_graphite_field_default` and `test_config_graphite_field_explicit_true` in `tests/test_state/test_config.py`. Unit test `test_resolve_graphite_config_true` and `test_resolve_graphite_config_false` in `tests/test_cli/test_init.py`.

- **Phase 2**: Thread `--graphite` flag through `deviate init` to config persistence and governance
  - **Files**: `src/deviate/cli/__init__.py`, `src/deviate/prompts/governance/graphite_seed.md` (new)
  - **Approach**: Add `--graphite` flag to `init` command. Pass it to `_scaffold_dotfiles`, which constructs `DeviateConfig(graphite=graphite, ...)`. Create `graphite_seed.md` with `## Graphite Stacked Changes Workflow` content. Update `_apply_governance` to conditionally read and upsert the graphite section when config's `graphite` is true.
  - **Verification**: `test_init_with_graphite_flag` — `runner.invoke(cli, ["init", "--graphite"])` → verify `graphite = true` in `.deviate/config.toml`. `test_init_without_graphite_flag` — verify `graphite = false` or absent. `test_init_graphite_governance_section` — verify Graphite section in CLAUDE.md/AGENTS.md when graphite is true, absent when false.

- **Phase 3**: Conditional routing in `feature create` and `pr run`
  - **Files**: `src/deviate/cli/feature.py`, `src/deviate/cli/meso.py`
  - **Approach**: In `_create_feature_branch`, call `resolve_graphite_config(repo_path)` before the `git branch` subprocess. When true, construct `["gt", "create", "-am", f"feat/{slug}"]`. In `_pr_run`, call `resolve_graphite_config(repo_root)` before the `gh pr create` subprocess. When true, construct `["gt", "submit", "--stack"]` — silently ignore `merge` and `auto_merge` flags (log warning).
  - **Verification**: `test_feature_create_with_graphite` — mock `subprocess.run` to assert `["gt", "create", "-am", ...]` called when graphite = true. `test_pr_run_with_graphite` — mock `subprocess.run` to assert `["gt", "submit", "--stack"]` called.

- **Phase 4**: Update `deviate-pr/SKILL.md` for graphite path documentation
  - **Files**: `.opencode/skills/deviate-pr/SKILL.md`
  - **Approach**: Add a note in step 4 documenting that `graphite = true` routes to `gt submit --stack` and merge flags are N/A in graphite mode.
  - **Verification**: Manual review of the updated SKILL.md content.

## Data Flow Analysis
- **Init flow**: `deviate init --graphite` → `init()` callback receives `graphite=True` → `_scaffold_dotfiles(workdir, agent_export_mode, graphite=True)` → `DeviateConfig(graphite=True, ...)` → `model_dump()` → `_dict_to_toml()` → writes `graphite = true` to `.deviate/config.toml` → `_apply_governance(workdir)` loads graphite from config → conditionally reads `graphite_seed.md` → `_upsert_governance_block` writes/updates Graphite section to CLAUDE.md and AGENTS.md.
- **Feature create flow**: `deviate feature create "My Feature"` → `_create_feature_branch(slug, repo_path)` → `resolve_graphite_config(repo_path)` reads `.deviate/config.toml` → if `graphite = true`: `subprocess.run(["gt", "create", "-am", f"feat/{slug}"])` → branch created via Graphite CLI.
- **PR run flow**: `deviate pr run --body-file <path>` → `_pr_run(body_file, merge, auto_merge)` → `resolve_graphite_config(repo_root)` reads `.deviate/config.toml` → if `graphite = true`: `subprocess.run(["gt", "submit", "--stack"])` → PR submitted via Graphite CLI.
- **Default (disabled) flow**: All existing behavior preserved — `graphite` defaults to `False`. `_scaffold_dotfiles` writes `graphite = false` (or key omitted). `_create_feature_branch` calls `git branch`. `_pr_run` calls `gh pr create`. Governance seeds contain no Graphite section.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `gt` binary not on `$PATH` when `graphite = true` | High | Medium | `subprocess.run` raises `FileNotFoundError` — catch and surface clear `[red]GRAPHITE_NOT_FOUND[/]` message with installation instructions. Do not auto-install (per defensive exclusions). |
| `gt create -am` fails on clean working tree | Low | Low | The `-am` flag requires changes to stage+commit. If working tree is clean, surface error suggesting `gt create -m` instead. Acceptable edge case — graphite workflow users typically have staged changes. |
| `gt submit --stack` incompatible with `--merge`/`--auto-merge` flags | Medium | Low | Silently ignore merge flags when graphite is enabled, log warning `[yellow]GRAPHITE_MERGE_FLAGS_IGNORED[/]`. Document in deviates-pr/SKILL.md that merge flags are N/A. |
| Config TOML round-trip: `graphite = true` correctly serialized/deserialized | Low | Low | `_serialize_value` (line 57-58 of `cli/__init__.py`) already handles `bool` → `"true"/"false"`. `tomllib.load` returns Python `bool`. Pydantic accepts it natively. Covered by existing `_dict_to_toml` round-trip test pattern. |
| Existing `.deviate/config.toml` without `graphite` key | Low | Low | `resolve_graphite_config()` returns `data.get("graphite", False)` — absent key defaults to `False` gracefully. `DeviateConfig` model also defaults `graphite = False`. |
| Idempotency: re-running `deviate init` with graphite enabled | Low | Low | `_write_if_missing` skips existing `config.toml` (line 45-51). `_upsert_governance_block` handles create/append/update via `## Graphite Stacked Changes Workflow` section header detection (line 196-222 pattern). |

## Integration Points
- **`_scaffold_dotfiles` ↔ `DeviateConfig`**: `DeviateConfig` constructor must accept `graphite` parameter, `model_dump()` must include it, `_dict_to_toml` must serialize it. Source: `src/deviate/cli/__init__.py:230-232`.
- **`_apply_governance` ↔ `graphite_seed.md`**: When `graphite = true` in config, read `deviate.prompts.governance.graphite_seed` via `_read_seed()`, write via `_upsert_governance_block()` to CLAUDE.md/AGENTS.md. Source: `src/deviate/cli/__init__.py:257-270` for current pattern.
- **`resolve_graphite_config()` ↔ `meso.py` and `feature.py`**: Both modules import and call `resolve_graphite_config()` to drive conditional routing. Source: `src/deviate/cli/__init__.py` (new function) → `src/deviate/cli/meso.py:1009`, `src/deviate/cli/feature.py:37`.
- **`gt submit --stack` ↔ `gh pr create` parity**: Graphite's `gt submit --stack` performs the same conceptual function as `gh pr create` — opening PR(s) on the remote. No ledger changes needed. Source: `src/deviate/cli/meso.py:1008-1014` for current `gh` path.

## Constitutional Alignment
- **Architecture**: This change spans configuration (`.deviate/config.toml` via `DeviateConfig`), CLI commands (`deviate init`, `deviate feature create`, `deviate pr run`), and governance seeds (CLAUDE.md, AGENTS.md). It is a vertical-slice enhancement that respects the three-layer architecture — no layer-skipping occurs. Source: `specs/constitution.md` §`[1_ARCHITECTURAL_PRINCIPLES]`.
- **Testing**: pytest with `tmp_git_repo` fixture for isolation. Tests follow existing patterns: mock `subprocess.run` for external CLI calls, assert config TOML content for init tests, assert governance file content for governance tests. All new code must have corresponding tests per `DEFINITION_OF_DONE`. Source: `specs/constitution.md` §`[3_TESTING_PROTOCOLS]`.
- **Git Isolation**: `_git_env()` is already used in all `subprocess.run` calls in `feature.py` (line 39) and `meso.py` (line 968-969, 1014). No new git operations that switch branches — `gt create` is a branch creation command, not a checkout. The `gt` subprocess calls inherit the same `_git_env()` isolation pattern. Source: `specs/constitution.md` §`Git Isolation Principle`.
