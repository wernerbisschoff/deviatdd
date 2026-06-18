---
title: "Offline Context Documentation System — Integrate `context` CLI into DeviaTDD Framework"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: [ISS-ADH-005, ISS-001-005]
issue_id: ISS-ADH-006
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/006-context-cli-integration.md`
- **Primary Architectural Workstation**:
  - `src/deviate/state/config.py` — Add `use_context: bool` field to `DeviateConfig`
  - `src/deviate/cli/__init__.py` — Detect `context` binary during `init`, write `use_context = true` to config; when true, emit rich governance block with context mandate
  - `src/deviate/prompts/core/core.md` — Add offline documentation system section referencing `context` CLI as the universal documentation source
  - `src/deviate/prompts/governance/claudemd_seed.md` — Add `## Offline Context Documentation System` section with context usage mandate
  - `src/deviate/prompts/governance/agents_seed.md` — Add `## Offline Context Documentation System` section with context usage mandate
  - `src/deviate/prompts/skills/deviate-explore/SKILL.md` — Add `context add <source>` step for registering relevant documentation sources
  - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` — Add `context add <source>` step for lightweight discovery
  - `src/deviate/prompts/skills/deviate-research/SKILL.md` — Add `context query <source> <query>` mandate for architectural reasoning; replace web-fetch last-resort with context-first lookup
  - `src/deviate/prompts/skills/deviate-plan/SKILL.md` — Add `context query <source> <query>` step for localized codebase research
  - `src/deviate/prompts/core/macro-skill.md` — Add context consultation requirement
  - `src/deviate/prompts/core/meso-skill.md` — Add context consultation requirement
  - `src/deviate/prompts/core/micro-skill.md` — Add context consultation guidance

## [THE_PROBLEM_CONTRACT]
The DeviaTDD framework depends on AI agents having accurate, up-to-date documentation for the libraries and frameworks they interact with during all phases. Currently, agents rely on either their training data (which may be stale) or web fetching (which is slow, unreliable, and adds network latency). The `context` CLI provides offline, deterministic, version-pinned documentation lookups for all declared dependencies. The framework must detect the `context` CLI at init time, configure a boolean in `.deviate/config.toml` to track its availability, inject context-mandate governance blocks into `CLAUDE.md` and `AGENTS.md`, and thread `context add` / `context query` instructions through every phase's skill prompt so that agents use the local documentation index as their primary documentation source — reducing latency, increasing accuracy, and enabling fully offline operation.

## [SCOPE_BOUNDARIES]
### Hard Inclusions
- Add `use_context: bool = False` field to `DeviateConfig` in `src/deviate/state/config.py`
- Detect `context` binary on `$PATH` during `deviate init` in `src/deviate/cli/__init__.py`; set `use_context = true` in config if found
- Add `## Offline Context Documentation System` section to `claudemd_seed.md` and `agents_seed.md` with:
  - Mandate that ALL agents MUST use `context query <library> <topic>` as their primary documentation lookup mechanism
  - Instruction to call `context list` first to discover available documentation packages
  - Instruction to call `context add <source>` when documentation for a library is missing
- Add a universal documentation section to `core.md` (loaded by ALL phase prompts) requiring agents to prefer `context query` over web fetching
- Add `context add <source>` step to `deviate-explore` skill: the ecosystem researcher subagent registers relevant documentation sources before querying
- Add `context add <source>` step to `deviate-adhoc` skill: lightweight discovery includes registering documentation sources
- Add `context query <source> <query>` mandate to `deviate-research` skill: architectural analysis MUST use `context query` for library-specific decisions, replacing web-fetch as the last-resort fallback
- Add `context query <source> <query>` mandate to `deviate-plan` skill: localized codebase research MUST use `context query` for understanding library APIs and framework conventions
- Thread context consultation into `macro-skill.md`, `meso-skill.md`, and `micro-skill.md` layer preambles
- When `use_context` is true in config, the generated CLAUDE.md/AGENTS.md governance block must include the context mandate section; the existing governance seeds must be updated unconditionally (the seed IS the mandate — config boolean controls CLI behavior only)

### Defensive Exclusions
- No runtime checking of `use_context` config in prompt assembly — the governance seeds and core.md are written unconditionally; agents should use `context` if available, gracefully skip if not
- No dynamic prompt injection based on config — all prompt files are static markdown; the `use_context` boolean is reserved for future CLI-layer behavior (e.g., conditional `context sync` during init)
- No `context` binary download or installation — detection only; users install `context` separately
- No dependency on `context` for framework operation — when absent, agents fall back to training data and web fetch as before
- No changes to `.deviate/config.toml` serialization beyond adding the boolean field
- No migration of existing `.deviate/config.toml` files — the `use_context` field is absent until next init run

## [UPSTREAM_REQUIREMENT_TRACING]
- **Requirements Tokens**: `FR-ADHOC-006`
- **Acceptance Criteria Tokens**: `AC-ADHOC-006-01`, `AC-ADHOC-006-02`, `AC-ADHOC-006-03`, `AC-ADHOC-006-04`, `AC-ADHOC-006-05`, `AC-ADHOC-006-06`
- **Data Model Entities**: `DeviateConfig.use_context` (bool)
- **Constitution Anchors**: [`TECH_STACK_STANDARDS — Tooling`] New section entry for `context` CLI

## [USER_STORIES_LEDGER]
- **US-ADH-006-01**: As a DeviaTDD operator, I want `deviate init` to detect whether the `context` CLI is installed so that my project configuration accurately reflects its availability.
- **US-ADH-006-02**: As a DeviaTDD operator, I want the generated CLAUDE.md and AGENTS.md governance blocks to mandate `context` usage when `context` is installed so that AI agents use local documentation by default.
- **US-ADH-006-03**: As an architect running the `/research` phase, I want the skill to use `context query <source> <query>` for library-specific design decisions so that I get accurate, version-pinned documentation without web latency.
- **US-ADH-006-04**: As an engineer running the `/plan` phase, I want the skill to query `context` for framework conventions and library APIs during localized research so that my implementation strategy is grounded in current documentation.
- **US-ADH-006-05**: As an explorer running the `/explore` or `/adhoc` phase, I want the skill to register relevant documentation sources via `context add <source>` during discovery so that downstream phases have up-to-date documentation indexed.
- **US-ADH-006-06**: As a DeviaTDD operator, I want ALL phase prompts to include a universal context documentation mandate so that every agent phase consistently prefers local documentation over web fetching.

## [ATDD_ACCEPTANCE_CRITERIA]
**Scenario 006-01**: `deviate init` detects and configures `context` availability
**Given** the `context` binary is present on `$PATH`
**When** `deviate init` runs
**Then** `.deviate/config.toml` contains `use_context = true`

**Scenario 006-02**: `deviate init` handles missing `context` gracefully
**Given** the `context` binary is NOT on `$PATH`
**When** `deviate init` runs
**Then** `.deviate/config.toml` contains `use_context = false` (or the field is absent, defaulting to false)

**Scenario 006-03**: CLAUDE.md/AGENTS.md contain context mandate block
**Given** `context` is detected during init
**When** `deviate init` completes
**Then** `CLAUDE.md` contains a `## Offline Context Documentation System` section with `context query`, `context list`, and `context add` instructions
**And** `AGENTS.md` contains the same section

**Scenario 006-04**: research skill uses `context query` for library lookups
**Given** an `/research` phase execution with `context` available
**When** Subagent Alpha evaluates library-specific architectural options
**Then** the skill prompt instructs using `context query <library> <topic>` as the primary documentation mechanism, with web fetch as last resort

**Scenario 006-05**: plan skill uses `context query` during codebase scan
**Given** a `/plan` phase execution with `context` available
**When** the planning analyst scans current codebase state
**Then** the skill prompt instructs using `context query` for understanding library APIs and framework conventions detected in the codebase

**Scenario 006-06**: explore/adhoc skills register documentation sources
**Given** an `/explore` or `/adhoc` phase execution
**When** the subagent identifies the project's dependency ecosystem
**Then** the skill prompt instructs running `context add <source>` for detected frameworks and libraries to index their documentation

## [EDGE_CASES_AND_BOUNDARIES]
- **`context` binary not found**: `deviate init` sets `use_context = false` and skips the context mandate in governance seeds; agents use existing training-data / web-fetch behavior
- **`context` binary found but broken**: Detection is a simple `which` check; if `context list` or `context query` fails during agent execution, the agent catches the subprocess error and falls back gracefully
- **No documentation installed for a library**: `context list` returns empty; the explore skill's `context add <source>` step only runs for libraries that have known context documentation sources
- **Partial installation (per-user vs global)**: `which context` handles any PATH location; the config boolean reflects availability regardless of install method
- **Config round-trip**: `DeviateConfig(use_context=True).model_dump()` followed by `DeviateConfig(**data)` preserves the boolean
- **Concurrent init runs**: `_write_if_missing` on config.toml prevents overwrite; if config.toml already exists, the `use_context` field stays at whatever value was set during first init — users manually edit to update

## [PERFORMANCE_CONSTRAINTS]
- L_max: < 5ms for `which context` check during init
- L_max: < 10ms for boolean field load from TOML config
- Zero performance impact when `context` is not installed — the false boolean adds no overhead to hot paths
- `context query` latency depends on library size but is typically < 50ms local vs 500ms+ for web fetch

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Sandbox Targets**:
  - `tests/test_state/test_config.py::test_config_use_context_default` — `use_context` defaults to `False`
  - `tests/test_state/test_config.py::test_config_use_context_round_trip` — `use_context=true` survives serialize→deserialize
  - `tests/test_cli/test_init.py::test_init_detects_context` — init with `context` on PATH sets `use_context=true`
  - `tests/test_cli/test_init.py::test_init_missing_context` — init without `context` on PATH sets `use_context=false`
  - `tests/test_cli/test_init.py::test_init_context_governance_block` — CLAUDE.md/AGENTS.md contain `## Offline Context Documentation System` section
- **Integration Sandbox Targets**:
  - `tests/test_integration/test_init_export_cycle.py` — full init → export cycle with context detection

## [DEMONSTRATION_PATH]
```bash
# 1. Verify context is installed
which context

# 2. Run init
deviate init

# 3. Verify config contains use_context
grep use_context .deviate/config.toml

# 4. Verify governance blocks
grep -q "Offline Context Documentation System" CLAUDE.md && echo "CLAUDE.md OK"
grep -q "Offline Context Documentation System" AGENTS.md && echo "AGENTS.md OK"

# 5. Run unit tests
pytest tests/test_state/test_config.py::test_config_use_context -v
pytest tests/test_cli/test_init.py::test_init_detects_context -v
pytest tests/test_cli/test_init.py::test_init_missing_context -v
```
