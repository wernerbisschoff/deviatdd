---
title: "Make deviate setup interactive for backend and command packs, and tidy production config.toml"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: ["ISS-ADH-030"]
issue_id: ISS-ADH-034
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/034-setup-interactive-config.md`
- **Primary Architectural Workstation**: `src/deviate/cli/__init__.py`, `src/deviate/state/config.py`, `src/deviate/core/commands.py`, `src/deviate/core/profile.py`, `src/deviate/cli/micro.py`, `src/deviate/prompts/core/core.md`

## The Problem Contract

Operators running `deviate setup` without choice flags need an interactive backend picker and a command-pack picker. Default installs should be the four layers (product + macro + meso + micro) plus the shared `deviatdd` skill. Optional packs stay off unless selected. Generated `config.toml` must be production-clean: truthful `profile`, no libref unless `--libref`, and `[agent]` keys that match the chosen backend.

## Scope Boundaries
### Hard Inclusions
- Interactive setup when `--agent` / `--packs` are omitted on a TTY: choose backend; choose optional command packs. Non-interactive sessions without `--packs` install default packs only.
- Default packs by layer intent (not frontmatter `category`): product (`deviate-flows`, `deviate-architecture`, `deviate-release`), macro (`deviate-explore`, `deviate-research`, `deviate-prd`, `deviate-shard`, `deviate-adhoc`, `deviate-constitution`, `deviate-init`), meso (`deviate-plan`, `deviate-tasks`), micro (`deviate-red`, `deviate-green`, `deviate-judge`, `deviate-refactor`, `deviate-execute`) plus the shared `deviatdd` skill.
- Optional packs stay uninstalled unless selected: `merge`, `pr`, `review`, `walkthrough`, `html`, `hotfix`, `triage`, `prune`, `e2e`.
- `--packs` for scripted selection (`none`, `all-optional`, or comma-separated optional names).
- Generated `config.toml` always persists `base_branch` and `claim_remote`.
- Top-level `profile` is `full` / `fast` / `secure` (default `full`) and is the `deviate micro run` default when `--profile` is omitted. Do not persist `"default"`. Legacy `"default"` coerces to `"full"` on read.
- `--libref` is the only libref opt-in. Without it: no `use_libref` key, no libref seed in CLAUDE.md/AGENTS.md, no libref token in composed installed commands or skills. PATH detection does not enable libref.
- `[agent]` persists the chosen backend (`codex` when Codex is picked). Write `transport` only for `pi` / `omp`. Never write `pi_rpc` on a fresh dump. Strip dead Pi keys when switching an existing file to a non-pi/omp backend.
- Keep Codex if-empty defaults: `[models].default = gpt-5.6-luna` and `[agent].reasoning_effort = high`. Do not clobber user-set models or reasoning.
- Pin the above with tests. Update `CHANGELOG.md` `[Unreleased]`.

### Defensive Exclusions
- Do not reopen ISS-ADH-030 ACs: gitignore-all-of-`.deviate`, Graphite removal, timeout consolidation, install-to-all-agents (per-agent install already shipped).
- Do not merge PR #125.
- Do not add a new prompt library (stay on Typer + Rich).
- Do not persist pack selection in `config.toml`.
- Do not rewrite command frontmatter `category` strings in this slice.
- Do not author or modify Product-layer flows; `flow_refs: []`.
- Do not invent a fourth profile named `default`.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-034`
- **Acceptance Criteria Tokens**: `AC-ADHOC-034-01`, `AC-ADHOC-034-02`, `AC-ADHOC-034-03`, `AC-ADHOC-034-04`, `AC-ADHOC-034-05`
- **Data Model Entities**: `CommandPack`, `PackSelection`, `DeviateConfig`, `AgentBlock`, `ExecutionProfile`, `LibrefOptIn`

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-034-01**: As a consumer-project operator, I want `deviate setup` without `--agent` / `--packs` to ask which backend and which optional packs to install so the workspace matches the tools I actually use. *(Ref: FR-ADHOC-034)*
- **US-034-02**: As a consumer-project operator, I want default setup to install only product + macro + meso + micro plus `deviatdd`, so optional commands such as merge, pr, and review stay off until I select them. *(Ref: FR-ADHOC-034)*
- **US-034-03**: As a consumer-project operator, I want a tidy `config.toml` whose `profile` is a real micro default and whose `[agent]` block has no dead Pi keys, so the file matches what the CLI actually runs. *(Ref: FR-ADHOC-034)*
- **US-034-04**: As a consumer-project operator, I want setup without `--libref` to mention libref nowhere in generated config, prompts, or installed skills, so an unused tool does not leak into the workspace. *(Ref: FR-ADHOC-034)*
- **US-034-05**: As a Codex operator, I want Luna + high reasoning seeded only when those keys are empty, so my custom model and effort survive a re-run. *(Ref: FR-ADHOC-034)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-034-01** *(Ref: AC-ADHOC-034-01, US-034-01)*: Setup without `--agent` on a TTY prompts for a backend from `AGENT_CHOICES` and persists that backend. Setup without `--packs` on a TTY prompts for optional packs; the default answer installs none of them.
  - **Happy Path**: `--agent codex --packs none` (or TTY equivalent) writes `[agent].backend = "codex"` and default-pack commands only.
  - **Error Category**: Unknown `--agent` or unknown `--packs` name fails closed without a partial install of the unknown name.
  - **Boundary Category**: Non-interactive setup without `--agent` and without an existing backend still exits `NO_AGENT_SELECTED`. Non-interactive setup without `--packs` installs default packs only.
- **AO-034-02** *(Ref: AC-ADHOC-034-02, US-034-02)*: Default install writes the four-layer command set plus `deviatdd` and does not write optional-pack files (`deviate-pr`, `deviate-merge`, `deviate-review`, `deviate-walkthrough`, `deviate-html`, `deviate-hotfix`, `deviate-triage`, `deviate-prune`, `deviate-e2e`).
  - **Happy Path**: `--packs pr,review` adds only those two optional commands on top of the default set.
  - **Error Category**: `--packs graphite` (unknown) fails closed.
  - **Boundary Category**: Pack membership is the code-owned map, not frontmatter `category`. `deviate-red` is default micro even though its `category` says macro.
- **AO-034-03** *(Ref: AC-ADHOC-034-03, US-034-03)*: Fresh generated `config.toml` writes `profile = "full"` (or `fast`/`secure` if chosen), `base_branch`, and `claim_remote`. It never writes `profile = "default"`. `[agent]` for Codex/claude/opencode/droid contains `backend` and `timeout` and does not contain `pi_rpc` or `transport`. Pi/OMP may write `transport`.
  - **Happy Path**: `setup --agent claude` produces no `pi_rpc` and no `transport` key. `setup --agent pi` may write `transport = "rpc"` and does not write `pi_rpc`.
  - **Error Category**: Switching an existing pi config to `--agent codex` strips leftover `pi_rpc`/`transport` while keeping user `timeout` and seeding Luna/high if empty.
  - **Boundary Category**: `deviate micro run` without `--profile` uses the config `profile`. Legacy `profile = "default"` and a missing key both resolve as `full`.
- **AO-034-04** *(Ref: AC-ADHOC-034-04, US-034-04)*: Setup without `--libref` produces no `use_libref` key and no `libref` substring in generated `config.toml`, upserted governance files, or installed command/skill bodies.
  - **Happy Path**: `--libref` writes `use_libref = true` and the libref governance seed / compose overlay.
  - **Error Category**: `libref` present on PATH without `--libref` still omits every libref mention.
  - **Boundary Category**: The packaged `deviatdd` SKILL.md source already has no libref token; the installed copy stays that way unless a future overlay is explicitly opted in (this slice does not add one to the skill).
- **AO-034-05** *(Ref: AC-ADHOC-034-05, US-034-05)*: Codex setup still seeds `[models].default = gpt-5.6-luna` and `[agent].reasoning_effort = high` when those keys are missing or empty, and does not clobber user-set values.
  - **Happy Path**: Existing `models.default = gpt-5.4-custom` and `reasoning_effort = low` survive `setup --agent codex`.
  - **Error Category**: Non-Codex setup does not write Luna or `reasoning_effort`.
  - **Boundary Category**: Existing Codex no-clobber tests in `tests/unit/test_cli/test_setup.py` keep passing.
<!-- `**Given**` / `**When**` / `**Then**` are forbidden here. -->

## Edge Cases and Boundaries
- ISS-ADH-030 remains BACKLOG; this issue coordinates and does not implement 030's gitignore-all-of-`.deviate`, Graphite, or timeout-consolidation ACs.
- Unclassified new command stems must fail a unit test rather than install silently or disappear silently.
- `_write_agent_block_to_config` on an existing file must strip dead Pi keys when the new backend is not `pi` or `omp`.
- `DeviateConfig.profile` tests that currently assert `"default"` must move to `"full"`.
- Codex skill install under `.agents/skills/` still happens for the selected default (and selected optional) command stems only, not every packaged stem.
- PR #125 stays unmerged.

## Performance Constraints
- L_max: `deviate setup` pack filtering adds less than 100 ms beyond file writes.
- Throughput: Codex if-empty model seeding and profile coerce stay O(1) TOML edits.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_cli/test_setup.py` — interactive/pack install, libref-absent, agent-block keys by backend, default-vs-optional packs; `tests/unit/test_state/test_config.py` — `profile` is `full`/`fast`/`secure` and not `"default"`; `tests/unit/test_core/test_profile.py` — coerce legacy `"default"` to `full` if the coerce helper lives there; `tests/unit/test_core/test_commands.py` — every discovered stem is classified.
- **Integration Sandbox Targets**: `tests/test_integration/test_skill_installation.py` — `setup --agent opencode` still exits 0 and prints INSTALL for the default pack; Codex tests assert the default set rather than all 26 commands.

## Demonstration Path
```bash
TMP=$(mktemp -d) && cd "$TMP"
deviate setup --agent opencode --packs none
test -f .opencode/commands/deviate-red.md
test ! -f .opencode/commands/deviate-pr.md
grep -n libref .deviate/config.toml && exit 1 || true
grep -n 'profile = "full"' .deviate/config.toml
grep -n pi_rpc .deviate/config.toml && exit 1 || true
deviate setup --agent codex --packs pr
test -d .agents/skills/deviate-pr
pytest tests/unit/test_cli/test_setup.py tests/unit/test_state/test_config.py tests/unit/test_core/test_profile.py -v && ruff check .
```
