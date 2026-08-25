---
title: "Rework DeviaTDD Configuration and setup Provisioning to Git-Ignore .deviate/, Auto-Detect Agents, and Consolidate Timeouts"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-030
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/030-config-rework.md`
- **Primary Architectural Workstation**: `src/deviate/cli/__init__.py`, `src/deviate/state/config.py`, `src/deviate/core/agent.py`, `.deviate/config.toml`, `.gitignore`, `.deviate/.gitignore`

## The Problem Contract

The `deviate setup` command does not git-ignore `.deviate/` by default, installs skills and commands into every active agent regardless of the `--agent` flag, and ships an obsolete Graphite config key plus two redundant timeout settings. This issue reworks the DeviaTDD configuration system so consumer projects get a user-friendly, single-timeout `config.toml` and deterministic setup provisioning with per-agent install and agent auto-detection.

## Scope Boundaries

### Hard Inclusions
- Provision a root `.gitignore` and/or `.deviate/.gitignore` entry so `deviate setup` makes `.deviate/` untracked by default for consumer projects.
- Remove the obsolete Graphite configuration surface (`graphite` key, setup flag, and documented workflow) from active config, CLI, and specs.
- Consolidate the two timeout fields (top-level `timeout_seconds` and `[agent] timeout`) into one field.
- Streamline `config.toml` for readability and user-friendliness.
- Change `setup --agent <name>` to install skills only for that named agent; when `--agent` is omitted, detect which agents are installed and install accordingly.
- Keep config-driven model routing via the `[models]` block and the resolution order (phase key → `default` → backend-native) intact.

### Defensive Exclusions
- Do not invent a `.dv8` artifact; `.deviate/` is the sole target of the git-ignore change.
- Do not add new backend integrations or change the `AGENT_TO_BACKEND` mapping.
- Do not author or modify Product-layer flows or the flow index; `flow_refs: []`.
- Do not implement the full downstream micro pipeline; this issue covers macro and meso scoping plus the setup/config rework surface only.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-030`
- **Acceptance Criteria Tokens**: `AC-ADHOC-030-01`, `AC-ADHOC-030-02`, `AC-ADHOC-030-03`
- **Data Model Entities**: `DeviateConfig`, `AgentConfig`

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-030-01**: As a consumer-project operator, I want `deviate setup` to git-ignore `.deviate/` by default so runtime state and local config do not get committed. *(Ref: FR-ADHOC-030)*
- **US-030-02**: As a consumer-project operator, I want `setup --agent <name>` to install only that agent and an omitted `--agent` to auto-detect installed agents so setup targets exactly the used CLI. *(Ref: FR-ADHOC-030)*
- **US-030-03**: As a DeviaTDD operator, I want one consolidated timeout and a Graphite-free, readable `config.toml` so the config surface is unambiguous and matches the shipped product. *(Ref: FR-ADHOC-030)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-030-01** *(Ref: AC-ADHOC-030-01, US-030-01)*: Running `deviate setup` in a consumer project provisions a root `.gitignore` and/or `.deviate/.gitignore` entry that makes `.deviate/` untracked by default.
  - **Happy Path**: After setup, `git check-ignore .deviate/` resolves and `.deviate/` is not in `git status` as an untracked candidate for a fresh consumer.
  - **Error Category**: Setup succeeds without error and reports the git-ignore provisioning step; a missing `.deviate/` directory is created.
  - **Boundary Category**: The change does not untrack already-committed history retrospectively; it governs new provisioning for consumers.
- **AO-030-02** *(Ref: AC-ADHOC-030-02, US-030-02)*: `setup --agent opencode` installs commands and skills only under the opencode agent directory; `setup` with no `--agent` detects installed agents and installs to exactly those.
  - **Happy Path**: With `--agent opencode`, no other agent directory receives command/skill files. With no `--agent`, only directories for actually installed agents are written.
  - **Error Category**: Unknown or uninstalled agent names produce a clear setup error and do not partially install.
  - **Boundary Category**: The integration test `tests/test_integration/test_skill_installation.py` keeps asserting `INSTALL` and exit code 0 for `setup --agent opencode`.
- **AO-030-03** *(Ref: AC-ADHOC-030-03, US-030-03)*: The `config.toml` surface is Graphite-free and has exactly one timeout field; `DeviateConfig` accepts the streamlined schema.
  - **Happy Path**: No `graphite` key or field remains; one consolidated timeout governs both top-level and agent use; `[models]` model routing still resolves phase key → `default` → backend-native.
  - **Error Category**: `DeviateConfig` fails cleanly (extra=`forbid`) on any stale `graphite` key in a user config.
  - **Boundary Category**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` reflect the schema and setup changes in the same implementation commit.
<!-- `**Given**` / `**When**` / `**Then**` are forbidden here. -->

## Edge Cases and Boundaries
- A consumer already tracking `.deviate/config.toml` keeps existing history; the ignore-by-default applies to new provisioning.
- Agent auto-detection distinguishes an installed agent (present directory/binary) from one merely declared in `AGENT_TO_BACKEND`.
- Unknown or uninstalled target agents fail closed instead of installing to all agents.
- A stale literal `graphite` key in a user `config.toml` is rejected by `extra = "forbid"` rather than silently ignored.
- The `[models]` default/phase resolution order is untouched by the timeout and git-ignore rework.
- `specs/DeviaTDD-architecture.md` and `specs/DeviaTDD-api.md` must remain authoritative; `AGENTS.md` Graphite section and `resolve_graphite_config` references are removed in the same change set.

## Performance Constraints
- L_max: `deviate setup` provisioning completes within 500 ms overhead beyond file writes.
- Throughput: Consolidating the two timeout fields does not regress model-routing resolution or per-agent export setup time.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_state/test_config.py` — `test_consolidated_timeout_field` and `test_parse_stale_graphite_key_rejected` (new); `tests/test_cli/test_setup.py` — `test_setup_gitignores_dotdeviate`, `test_setup_single_agent_only`, `test_setup_auto_detect_installed_agents` (new).
- **Integration Sandbox Targets**: `tests/test_integration/test_skill_installation.py::TestSkillInstallation` — assert `INSTALL` and exit code 0 for the single-agent and auto-detect paths using the mocked `_get_agent_command_dir`.

## Demonstration Path
```bash
# Provision a temp consumer project and verify setup rework
TMP=$(mktemp -d) && cd "$TMP"
deviate setup                    # should auto-detect installed agents and git-ignore .deviate/
git check-ignore .deviate/       # should print .deviate/ (resolves path)
deviate setup --agent opencode   # should install only to .opencode/
grep -rn "graphite" .deviate/config.toml src/deviate  # should produce no matches
pytest tests/ -v && ruff check .
```