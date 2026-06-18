---
title: "Graphite CLI Integration — Optional Branch & PR Management via `gt`"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-007
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/007-graphite-cli.md`
- **Primary Architectural Workstation**: `src/deviate/state/config.py`, `src/deviate/cli/__init__.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/feature.py`, `src/deviate/prompts/governance/claudemd_seed.md`, `src/deviate/prompts/governance/agents_seed.md`, `.opencode/skills/deviate-pr/SKILL.md`

## The Problem Contract
Enable DeviaTDD users who use Graphite's stacked-changes workflow to replace native `git` branch creation and `gh` PR submission with Graphite's `gt create` and `gt submit --stack` commands, gated behind an optional `graphite` boolean in `.deviate/config.toml`. When disabled (default), all existing behavior is preserved.

## Scope Boundaries
### Hard Inclusions
- Add `graphite: bool = False` field to `DeviateConfig` Pydantic model in `src/deviate/state/config.py:98`
- Add `--graphite` boolean CLI flag to `deviate init` command in `src/deviate/cli/__init__.py:320`
- Thread `graphite` parameter through `_scaffold_dotfiles` to persist in `.deviate/config.toml`
- Add conditional `## Graphite Stacked Changes Workflow` section to governance seeds (`claudemd_seed.md`, `agents_seed.md`) that is emitted only when `graphite = true`
- Add `resolve_graphite_config()` helper to load the `graphite` key from `.deviate/config.toml`
- Conditional branch in `meso.py:_pr_run` (near line 1008): when `graphite = true`, use `["gt", "submit", "--stack"]` instead of `["gh", "pr", "create", ...]`
- Conditional branch in `feature.py:_create_feature_branch` (near line 27): when `graphite = true`, use `["gt", "create", "-am", msg]` instead of `["git", "branch", name]`
- Update `deviate-pr/SKILL.md` to document `gt submit` as the PR creation path when `graphite` is enabled

### Defensive Exclusions
- No Graphite CLI installation verification or auto-install logic
- No migration/upgrade path for existing `.deviate/config.toml` files (existing configs without `graphite` default to `false`)
- No CI/CD pipeline changes
- No `gt` MCP integration (beta feature)
- No legacy `gt` alias configuration (`.graphite_aliases`)
- No changes to `deviate run --all` streaming pipeline monitor
- No changes to micro-layer TDD sandbox (the sandbox already prohibits branch-switching commands)

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-007`
- **Acceptance Criteria Tokens**: `AC-ADHOC-007-01`, `AC-ADHOC-007-02`, `AC-ADHOC-007-03`, `AC-ADHOC-007-04`, `AC-ADHOC-007-05`, `AC-ADHOC-007-06`, `AC-ADHOC-007-07`
- **Data Model Entities**: `DeviateConfig.graphite` (bool, default False)

## User Stories Ledger
- **US-007-01**: As a developer using Graphite for stacked changes, I want `deviate init --graphite` to generate config that routes all branch creation and PR submission through `gt` commands so that my DeviaTDD workflow integrates natively with my Graphite stack. *(Ref: FR-ADHOC-007)*

## ATDD Acceptance Criteria
**Scenario 007-01**: Graphite config key written during init
**Given** a workspace without `.deviate/` directory
**When** the user runs `deviate init --graphite`
**Then** `.deviate/config.toml` contains the line `graphite = true`

**Scenario 007-02**: Default behavior preserves existing workflow
**Given** a workspace without `.deviate/` directory
**When** the user runs `deviate init` (without `--graphite`)
**Then** `.deviate/config.toml` either contains `graphite = false` or omits the `graphite` key entirely

**Scenario 007-03**: Governance seed includes Graphite section when enabled
**Given** `graphite = true` in `.deviate/config.toml`
**When** `deviate init` runs and applies governance seeds
**Then** `CLAUDE.md` and `AGENTS.md` both contain a `## Graphite Stacked Changes Workflow` section with `gt create -am`, `gt submit --stack`, `gt sync`, and anti-pattern warnings (do not use `git checkout -b` alongside `gt`)

**Scenario 007-04**: Governance seed omits Graphite section when disabled
**Given** `graphite = false` or absent in config
**When** `deviate init` runs and applies governance seeds
**Then** `CLAUDE.md` and `AGENTS.md` do NOT contain a `## Graphite Stacked Changes Workflow` section

**Scenario 007-05**: PR creation uses `gt submit --stack` when graphite enabled
**Given** `graphite = true` in `.deviate/config.toml`
**When** `deviate pr run` executes
**Then** the subprocess command is `["gt", "submit", "--stack"]` instead of `["gh", "pr", "create", ...]`

**Scenario 007-06**: Feature branch created via `gt create` when graphite enabled
**Given** `graphite = true` in `.deviate/config.toml`
**When** `deviate feature create "My Feature"` runs
**Then** the branch is created via `gt create -am "feat/<slug>"` instead of `git branch feat/<slug>`

**Scenario 007-07**: All existing behavior preserved when graphite disabled
**Given** `graphite = false` (or absent) in `.deviate/config.toml`
**When** any command executes (`init`, `feature create`, `pr run`)
**Then** no `gt` commands are invoked; `git branch` and `gh pr create` are used as before

## Edge Cases and Boundaries
- Config TOML round-trip: `graphite = true` and `graphite = false` must serialize correctly through `_dict_to_toml` and `_serialize_value` (which already handles `bool` at `src/deviate/cli/__init__.py:57`).
- Existing `config.toml` without `graphite` key: `DeviateConfig.model_validate` must default `graphite` to `False` after `extra = "forbid"` — the `graphite` field is defined on the model, so it defaults silently.
- `_gt` not on `$PATH`: when `graphite = true` but `gt` is not installed, `subprocess.run` will raise `FileNotFoundError` at the call site — surface a clear error message with instructions to install Graphite.
- Config loaded from TOML with `tomllib.load`: `graphite` key is parsed as a Python bool; the Pydantic model accepts it directly.
- Governance idempotency: if `## Graphite Stacked Changes Workflow` already exists in `CLAUDE.md`, the existing block is updated (matching the `_upsert_governance_block` pattern from `src/deviate/cli/__init__.py:196`). If graphite is false, the section is not appended on any init run.
- `feature create` branch naming: `gt create` with `-am` flag creates a branch and automatically stages + commits working changes with the given message. If working tree is clean, this may fail — `gt create -m` (without `-a`) might be needed.
- `gt submit --stack` discovery: `_pr_run` in meso.py must load the config TOML to read `graphite` before forking the subprocess path.

## Performance Constraints
- L_max: init with `--graphite` flag adds < 5ms overhead (one additional boolean key serialized to TOML)
- PR submit: `gt submit --stack` network latency comparable to `gh pr create` (both are CLI-to-API calls)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/test_state/test_config.py`: test `DeviateConfig(graphite=True)` serialization and `DeviateConfig()` default `graphite=False`
  - `tests/test_cli/test_init.py::test_init_with_graphite_flag`: `runner.invoke(cli, ["init", "--graphite"])` → verify `graphite = true` in config.toml
  - `tests/test_cli/test_init.py::test_init_without_graphite_flag`: `runner.invoke(cli, ["init"])` → verify `graphite` absent or `false`
  - `tests/test_cli/test_init.py::test_init_graphite_governance_section`: verify Graphite section in CLAUDE.md/AGENTS.md when graphite is true
  - `tests/test_cli/test_feature.py::test_feature_create_with_graphite`: mock `subprocess.run` to assert `["gt", "create", "-am", ...]` called when graphite = true
  - `tests/test_cli/test_meso.py::test_pr_run_with_graphite`: mock `subprocess.run` to assert `["gt", "submit", "--stack"]` called
- **Integration Sandbox Targets**:
  - `tests/test_integration/test_init_export_cycle.py`: verify graphite flag does not break init cycle

## Demonstration Path
```bash
# 1. Init with graphite flag and verify config
deviate init --graphite
grep "graphite" .deviate/config.toml
# Expected: graphite = true

# 2. Verify governance seeds include Graphite section
grep -q "Graphite Stacked Changes" CLAUDE.md && echo "PASS" || echo "FAIL"
grep -q "Graphite Stacked Changes" AGENTS.md && echo "PASS" || echo "FAIL"

# 3. Run full test suite
mise run test
# Expected: all tests pass, exit code 0
```
