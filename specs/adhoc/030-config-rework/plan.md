# Plan: Rework DeviaTDD Configuration and setup Provisioning

## Plan Summary
- **Issue**: ISS-ADH-030 — Rework DeviaTDD Configuration and setup Provisioning to Git-Ignore `.deviate/`, Auto-Detect Agents, and Consolidate Timeouts
- **Implementation Strategy**: Rework `deviate setup` so `--agent <name>` installs commands and skills only to that named agent, an omitted `--agent` auto-detects and targets only the installed agent directories, and setup provisions a `.gitignore` entry that makes `.deviate/` untracked by default. Streamline `.deviate/config.toml` to a Graphite-free schema with exactly one timeout field while preserving the `[models]` phase→model resolution order.
- **Estimated Complexity**: High
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/030-config-rework.md` (frontmatter field: `flow_refs`)
- **Release Context**: `N/A`
- **Architecture Components Touched**: None (no `specs/_product/architecture.md` §3 Components apply; this issue is CLI/config provisioning rework)

## Acceptance Contract

**Scenario AC-PLAN-001: Rework setup to git-ignore the .deviate directory by default**
- **Source Outline**: `AO-030-01`
- **Upstream Traceability**: `US-030-01`, `FR-ADHOC-030`, `AC-ADHOC-030-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_ensure_root_gitignore`
- **Given**: a fresh consumer project and a `deviate setup` run that provisions dotfiles and ignore files
- **When**: the operator runs `deviate setup` and then executes `git check-ignore .deviate/`
- **Then**: git resolves `.deviate/` as an ignored path and reports no untracked `.deviate/` candidate in `git status` on an empty working tree
- **Verification Mode**: automated

**Scenario AC-PLAN-002: setup with --agent installs commands and skills only under that agent directory**
- **Source Outline**: `AO-030-02`
- **Upstream Traceability**: `US-030-02`, `FR-ADHOC-030`, `AC-ADHOC-030-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:setup`
- **Given**: a consumer project where multiple agent directories (`.claude`, `.opencode`) exist and `_get_agent_command_dir` maps to the temp tree
- **When**: the operator runs `deviate setup --agent opencode`
- **Then**: command and skill files are written only under `.opencode/`, no other agent directory receives command or skill files, and setup exits with code 0 and prints `INSTALL`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: setup with no --agent auto-detects installed agents and targets exactly those**
- **Source Outline**: `AO-030-02`
- **Upstream Traceability**: `US-030-02`, `FR-ADHOC-030`, `AC-ADHOC-030-02`
- **Current-Code Evidence**: `src/deviate/core/commands.py:detect_agents`
- **Given**: a consumer project with `.claude/` and `.opencode/` present and no other agent directory
- **When**: the operator runs `deviate setup` with no `--agent` flag
- **Then**: setup detects `claude` and `opencode` as installed and writes command and skill files only to those two detected directories
- **Verification Mode**: automated

**Scenario AC-PLAN-004: setup fails closed on an unknown or uninstalled agent without partial install**
- **Source Outline**: `AO-030-02`
- **Upstream Traceability**: `US-030-02`, `FR-ADHOC-030`, `AC-ADHOC-030-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_validate_agent_choice`
- **Given**: an operator passes an agent name that is not in `AGENT_CHOICES` or is declared but not installed
- **When**: the operator runs `deviate setup --agent <unknown>`
- **Then**: setup exits with a clear error, does not write any command or skill files to any agent directory, and leaves no partial install
- **Verification Mode**: automated

**Scenario AC-PLAN-005: config.toml exposes a Graphite-free single-timeout schema with intact model routing**
- **Source Outline**: `AO-030-03`
- **Upstream Traceability**: `US-030-03`, `FR-ADHOC-030`, `AC-ADHOC-030-03`
- **Current-Code Evidence**: `src/deviate/state/config.py:DeviateConfig`
- **Given**: `DeviateConfig` loads a streamlined schema with one consolidated timeout field and no `graphite` key
- **When**: the operator inspects the provisioned `.deviate/config.toml` and resolves a phase model from the `[models]` block
- **Then**: the config declares the single `timeout_seconds` field, the `[agent]` block carries no `timeout` field, no `graphite` key or field exists, and `resolve_phase_model` still applies phase key → `default` → backend-native order
- **Verification Mode**: automated

**Scenario AC-PLAN-006: DeviateConfig rejects a stale graphite key with extra forbid**
- **Source Outline**: `AO-030-03`
- **Upstream Traceability**: `US-030-03`, `FR-ADHOC-030`, `AC-ADHOC-030-03`
- **Current-Code Evidence**: `src/deviate/state/config.py:DeviateConfig:model_config`
- **Given**: a user `.deviate/config.toml` contains a literal top-level `graphite` key
- **When**: the loader parses that config into `DeviateConfig`
- **Then**: validation raises a clean error because `extra = "forbid"` rejects the unknown field, and no `graphite` value is silently accepted
- **Verification Mode**: automated

## Workstation Mapping
- **`src/deviate/cli/__init__.py`**: primary provisioning surface — the `setup` command, `_install_commands_to_agents`, `_install_deviatdd_skill`, `_ensure_gitignore`, `_ensure_root_gitignore`, and `_scaffold_dotfiles`.
  - **Current State**: `setup` installs commands and skills to ALL active agents (`active_agents = ("claude", "opencode", "factory", "pi", "omp")`) regardless of `--agent`; `--agent` only drives the `[agent].backend` value. `_ensure_root_gitignore` and `_ensure_gitignore` ignore subpaths of `.deviate/` but not `.deviate/` itself. `_CONFIG_TOML_COMMENTS` documents `timeout_seconds`.
  - **Changes Required**: Replace install-to-all dispatch with per-agent install when `--agent` is given and auto-detection (via `detect_agents`) when omitted; skip unknown/uninstalled agents with a clear error; add a `.gitignore` entry (root or `.deviate/.gitignore`) that ignores `.deviate/`; update the config writer so the `[agent]` block omits `timeout` and remove any Graphite surface.
  - **Integration Surface**: calls `detect_agents` in `src/deviate/core/commands.py`; calls `DeviateConfig`/`AgentConfig` in `src/deviate/state/config.py`; writes `.gitignore`/`.deviate/.gitignore`/`.deviate/config.toml`.
- **`src/deviate/state/config.py`**: authoritative config schema — `DeviateConfig` and `AgentConfig`.
  - **Current State**: `DeviateConfig` declares top-level `timeout_seconds` (default 1800); `AgentConfig` declares `timeout` (default 600); both models use `extra = "forbid"`.
  - **Changes Required**: Consolidate to one timeout field by removing `AgentConfig.timeout` and routing agent invocation deadlines to the single `timeout_seconds`; keep `extra = "forbid"` so a stale `graphite` key is rejected; keep `[models]` resolution order (`resolve_phase_model`) untouched.
  - **Integration Surface**: consumed by `src/deviate/core/agent.py` (`AgentBackend`), `src/deviate/cli/meso.py` (`_invoke_agent_phase`), and `src/deviate/cli/micro.py` (`_resolve_agent_timeout`, `_resolve_test_timeout_seconds`).
- **`src/deviate/core/agent.py`**: agent dispatch layer that reads `AgentConfig.timeout`.
  - **Current State**: `AgentBackend.invoke` sets `effective_timeout = timeout or self.config.timeout`; `detect_agents` lives in `src/deviate/core/commands.py` and is already available.
  - **Changes Required**: Route the agent-process wall-clock from the consolidated `timeout_seconds` instead of the removed `AgentConfig.timeout`; keep `AGENT_TO_BACKEND` mapping unchanged.
  - **Integration Surface**: `AgentBackend` invoked from `meso.py`; timeout default is the single consolidated value.
- **`src/deviate/cli/meso.py`**: meso agent invocation reads `[agent].timeout`.
  - **Current State**: `_invoke_agent_phase` builds `AgentConfig(timeout=(data.get("agent", {}).get("timeout", 600)...))`.
  - **Changes Required**: Build `AgentConfig` without the removed `timeout` field and resolve the agent wall-clock from the single `timeout_seconds`.
  - **Integration Surface**: `_invoke_agent_phase` → `AgentBackend(config=agent_cfg).invoke`.
- **`src/deviate/cli/micro.py`**: micro agent and test deadlines read timeout fields.
  - **Current State**: `_resolve_agent_timeout` reads `[agent].timeout` (default 600); `_resolve_test_timeout_seconds` reads `timeout_seconds` (default 1800).
  - **Changes Required**: Point `_resolve_agent_timeout` at the single consolidated `timeout_seconds` field so one value governs both agent-process and test-command deadlines.
  - **Integration Surface**: `_resolve_agent_timeout` and `_resolve_test_timeout_seconds` feed `run_safe_command` and agent dispatch.
- **`.deviate/config.toml`**: the shipped sample config surface.
  - **Current State**: declares top-level `timeout_seconds = 1800`, `[agent]` block with `timeout = 600`, `backend`, `pi_rpc`, `transport`, and no `[models]` block.
  - **Changes Required**: remove the `[agent] timeout` entry so exactly one timeout field remains; drop any `graphite` residual; keep `[models]` optional and readable.
  - **Integration Surface**: parsed by `_load_deviate_config_toml` in `src/deviate/state/config.py`.
- **`.gitignore` and `.deviate/.gitignore`**: ignore-file provisioning targets for the git-ignore rework.
  - **Current State**: `.gitignore` ignores deviatdd command/skill install paths and `.worktrees/`; `.deviate/.gitignore` ignores `session.json` and runtime state; neither ignores `.deviate/` itself.
  - **Changes Required**: provision an entry so `.deviate/` is untracked by default for new consumer setups while preserving already-tracked history.
  - **Integration Surface**: written by `_ensure_root_gitignore` and `_ensure_gitignore` in `src/deviate/cli/__init__.py`.
- **`specs/DeviaTDD-api.md`**, **`specs/DeviaTDD-architecture.md`**, **`AGENTS.md`**, **`CHANGELOG.md`**: authoritative CLI/config spec, architecture spec, governance doc, and changelog.
  - **Current State**: `DeviaTDD-api.md` documents setup install-to-all and the two timeouts; `AGENTS.md` line 96 still documents a `graphite = true` Graphite workflow; `resolve_graphite_config` is already absent from active code.
  - **Changes Required**: update the api/architecture specs to the per-agent install, auto-detect, git-ignore-by-default, and single-timeout schema; remove the AGENTS.md Graphite section; append a CHANGELOG `[Unreleased]` bullet in the same implementation commit.
  - **Integration Surface**: specs are the compliance contract for `mise run check`; docs mirror the implementation in the same commit.

## Implementation Strategy
- **Phase 1**: Consolidate the timeout schema
  - **Files**: `src/deviate/state/config.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/micro.py`, `src/deviate/core/agent.py`, `.deviate/config.toml`, `tests/test_state/test_config.py`
  - **Approach**: Remove `AgentConfig.timeout`; route the agent-process wall-clock and test deadline from the single `timeout_seconds`; keep `extra = "forbid"` so a stale `graphite` key raises; keep `resolve_phase_model` order intact.
  - **Verification**: `pytest tests/test_state/test_config.py -v` passes; `grep -rn "timeout"` confirms one consolidated field; `ruff check .`.
- **Phase 2**: Per-agent install and auto-detection in `setup`
  - **Files**: `src/deviate/cli/__init__.py`, `tests/test_cli/test_setup.py`, `tests/test_integration/test_skill_installation.py`
  - **Approach**: When `--agent` is given, install commands and skills only to that agent via `_get_agent_command_dir`/`_get_agent_skill_dir`; when omitted, call `detect_agents` and target exactly the detected installed agents; fail closed on unknown/uninstalled names; keep the `[agent].backend` write unchanged.
  - **Verification**: `pytest tests/test_cli/test_setup.py tests/test_integration/test_skill_installation.py -v`; assert `INSTALL` + exit code 0 and no cross-agent writes.
- **Phase 3**: Git-ignore `.deviate/` by default
  - **Files**: `src/deviate/cli/__init__.py`, `.gitignore`, `.deviate/.gitignore`, `tests/test_cli/test_setup.py`
  - **Approach**: Extend `_ensure_gitignore`/`_ensure_root_gitignore` to provision an entry that makes `.deviate/` untracked by default for new consumer setups; report the provisioning step on `deviate setup`.
  - **Verification**: `git check-ignore .deviate/` resolves in a fresh temp consumer; `pytest tests/test_cli/test_setup.py -v`.
- **Phase 4**: Spec, governance, and changelog alignment
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `AGENTS.md`, `CHANGELOG.md`
  - **Approach**: Update the specs to the per-agent install, auto-detect, git-ignore-by-default, and single-timeout behavior; remove the `AGENTS.md` Graphite section; append a user-visible CHANGELOG bullet.
  - **Verification**: `mise run check` passes; `grep -rn "graphite"` returns no active-code matches.

## Data Flow Analysis
- `deviate setup` reads the working directory, opts in via `--agent` or calls `detect_agents(workdir)` from `src/deviate/core/commands.py`, then writes the config, governance seeds, agent command/skill files, and ignore files.
- `.deviate/config.toml` is parsed by `_load_deviate_config_toml` into `DeviateConfig`, which owns the single `timeout_seconds` field and the `[models]` phase→model map.
- `resolve_model_for_phase` / `resolve_phase_model` read the `[models]` block and resolve phase key → `default` → backend-native for agent dispatch.
- `AgentBackend` (in `src/deviate/core/agent.py`) reads the consolidated `timeout_seconds` as the agent wall-clock; `meso.py`/`micro.py` read the same field for agent and test-command deadlines, feeding `run_safe_command`.
- `.gitignore` / `.deviate/.gitignore` govern whether `.deviate/` runtime state and config reach a consumer's version control.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Install-to-all → per-agent change breaks the pinned `tests/test_integration/test_skill_installation.py` contract | High | Medium | Update the integration asserts while preserving `INSTALL` + exit code 0 for `setup --agent opencode`; add unit coverage in `tests/test_cli/test_setup.py`. |
| Auto-detection confuses an installed agent directory with a name merely declared in `AGENT_TO_BACKEND` | Medium | Medium | Target only the installed agent dirs returned by `detect_agents`; fail closed on unknown or uninstalled names. |
| Consolidating the timeout changes agent or test deadlines and regresses the GREEN-hang guard | High | Low | Keep `gt=0` validation on the single field; default 1800; route both agent and test deadlines from `timeout_seconds`. |
| Git-ignoring `.deviate/` untracks currently committed files in existing consumers | Medium | Medium | Apply ignore-by-default to new provisioning only; preserve already-tracked history per AO-030-01 Boundary. |
| Stale `graphite` key handling changes config load for existing users | Low | Low | `extra = "forbid"` already rejects unknown fields; add a rejection test to pin the behavior. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile
Risk surfaces: file paths, git subprocess, config deserialization, subprocess dispatch.
Negative tests: `DeviateConfig` rejects a stale `graphite` key via `extra = "forbid"` rather than silently accepting it; `setup` with an unknown agent name fails closed and writes no files to any agent directory; the consolidated timeout refuses non-positive values (`gt=0`); `.deviate/` ignore-by-default does not expose runtime config/log state to git tracking.
Constraints: no new dependencies without checksum; no hardcoded secrets in config or ignore files; `.env*` and secrets stay untracked; no branch-mutating git commands from micro-layer agents.

## Integration Points
- **`deviate setup`** (in `src/deviate/cli/__init__.py`): the provisioning entry point; its `--agent` flag and auto-detect path target agent dirs and write the config, governance, skills, and ignore files.
- **`detect_agents`** (in `src/deviate/core/commands.py`): the installed-agent detector consumed by `setup` when `--agent` is omitted.
- **`DeviateConfig` / `AgentConfig`** (in `src/deviate/state/config.py`): schema contract for the single consolidated timeout and the `extra = "forbid"` rejection of stale keys.
- **`AgentBackend.invoke`** (in `src/deviate/core/agent.py`): consumes the consolidated `timeout_seconds` for the agent wall-clock.
- **`_invoke_agent_phase`** (in `src/deviate/cli/meso.py`) and **`_resolve_agent_timeout` / `_resolve_test_timeout_seconds`** (in `src/deviate/cli/micro.py`): read the single timeout field for phase and test-command deadlines.

## Constitutional Alignment
- **Architecture**: Aligns with the four-layer architecture and config-driven model routing (constitution §1). The `[models]` resolution order (phase key → `default` → backend-native) is preserved; the timeout and git-ignore rework touches CLI provisioning and config schema only.
- **Testing**: Uses pytest (`tests/`) for the new `tests/test_state/test_config.py`, `tests/test_cli/test_setup.py`, and `tests/test_integration/test_skill_installation.py` cases; ruff lint and `mise run check` gate completion; GREEN writes only to `src/` and permitted paths.
- **Git Isolation**: The plan runs in the dedicated `feat/adhoc/030-config-rework` worktree; commits are automatic at phase boundaries; no `git checkout -b` or branch-mutating micro commands; `.deviate/` ignore-by-default governs new consumer provisioning without disturbing tracked history.
- **Product Layer**: `flow_refs` is empty (`[]`), so the rework preserves the existing user-visible behavior of config-driven model routing and setup provisioning without authoring or synchronizing any Product-layer flows; this is traceability context, not a deliverables pipeline.
