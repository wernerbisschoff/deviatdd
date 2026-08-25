# Explore: config-rework

Version: 0.9.0
Phase: EXplore (Macro Layer)
Slug: `config-rework`

## Problem Definition

[Statement]: Rework the DeviaTDD configuration system. The `.deviate/` directory should be git-ignored by default. The `.dv8` path should be added to the root `.gitignore`. The obsolete Graphite configuration is no longer relevant and should be removed. The `config.toml` file should be streamlined and made more user-friendly. Two separate timeout settings currently exist and should be consolidated. The `setup --agent` behavior should install skills only for the specified agent; when no agent is supplied, the system should detect which agents are installed and install skills accordingly.

[Scope]: In-scope structural components verified across the scan:
- `.deviate/config.toml` — the persisted configuration profile with top-level keys (`profile`, `timeout_seconds`, `agent_export_mode`, `graphite`, `use_context`, `use_libref`), `[agent]` block, and `[models]` block.
- `deviate setup` command — the `--agent` flag handling and the install-to-all-agents dispatch.
- `.gitignore` / `.deviate/.gitignore` — current ignore rules and tracked `.deviate/` files.
- `DeviateConfig` / `AgentConfig` models in `src/deviate/state/config.py`.
- The two timeout fields: top-level `timeout_seconds` and `[agent] timeout`.

[Exclusions]: Architectural decisions, design trade-offs, risk analysis, data modeling, failure-mode speculation, and the final consolidated schema are deferred to the `deviate-research` skill. This document only catalogs what exists.

## Discovery Audit Results

### Verified Dependencies
- `typer>=0.12`: Declared in `pyproject.toml` `[project] dependencies`; imported in `src/deviate/cli/__init__.py` as the CLI framework.
- `rich>=13.0`: Declared in `pyproject.toml`; used for terminal I/O (`console.print`) in `src/deviate/cli/__init__.py`.
- `pydantic>=2.0`: Declared in `pyproject.toml`; defines `DeviateConfig` and `AgentConfig` in `src/deviate/state/config.py`.
- `pyyaml>=6.0.3`: Declared in `pyproject.toml`.
- `tomllib` (stdlib): Used in `src/deviate/state/config.py` `_load_deviate_config_toml` to parse `.deviate/config.toml`.

### Ghost Dependencies
- `gt` (Graphite CLI): Referenced in `AGENTS.md` line 96-98 as the branch/PR management CLI when `graphite = true`. Not declared in `pyproject.toml` and not referenced in `src/`. `CHANGELOG.md` records that Graphite CLI integration was removed from active code, prompts, and specs. This is a declarative finding only.
- `droid` (Factory Droid IDE binary): Referenced in `src/deviate/core/agent.py` as the backend binary for the `factory`/`droid` agent. Not declared as an installation dependency (runtime-only, out of tree).

### Manifest Files Observed
- `.deviate/config.toml`: The DeviaTDD persisted configuration profile (TOML).
- `pyproject.toml`: Python package manifest declaring runtime dependencies and the `deviate` console script.
- `mise.toml`: Task runner configuration (tasks: `setup`, `check`, `test`, `lint`, etc.).
- `.gitignore`: Project-root ignore rules.
- `.deviate/.gitignore`: Local ignore rules for `.deviate/` runtime state.
- `.gitattributes`: Union-merge rules for append-only JSONL ledgers.

### Test Runner Configuration
- Test command: `pytest tests/ -v` (quoted in `specs/constitution.md` §3).
- Lint command: `ruff check .` (quoted in `specs/constitution.md` §3).
- E2E command: `bats tests/e2e/` (quoted in `specs/constitution.md` §3).
- Code quality gate: `mise run check` (quoted in `specs/constitution.md` §2 Tooling).
- Verified dependency present: `tests/test_integration/test_skill_installation.py::TestSkillInstallation` exercises `deviate setup --agent opencode` and asserts `INSTALL` in output. The integration test mocks `_get_agent_command_dir`.

### Manifest-Constitution Divergence
- Constitution §2 Tooling states: "Task runner: `mise` (see `mise.toml` for all tasks)". The actual task-runner file in the repo is `mise.toml`. `AGENTS.md` and the `.mise.toml` reference in `AGENTS.md` header do not match this filename, but the constitution's quoted `mise.toml` matches the observed file. No adjudication.
- Constitution §1 Model Tiering and the `AGENTS.md` Graphite workflow both reference `.deviate/config.toml` keys. `AGENTS.md` line 96 still documents a `graphite = true` workflow while `CHANGELOG.md` records Graphite removal from active code. Both quoted verbatim; no adjudication.

## Constitution Quotes

Constitution excerpts quoted verbatim from `specs/constitution.md` (Version 0.9.0). No interpretation.

- **Architectural Principles**: "**Config-Driven Model Routing**: Phase→model assignments are declared in `.deviate/config.toml` under `[models]`. The `default` key sets the model for all phases without an explicit entry. Any other key (e.g., `judge`, `plan`, `red`) is treated as a phase name. Resolution order: phase-specific key → `default` key → no model flag (backend-native default). Both `opencode` and `droid` backends support `--model`; `claude` backend ignores model config silently."
- **Tech Stack Standards**: "Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment" and "Session state: JSON files under `.deviate/`".
- **Testing Protocols**: "Test command: `pytest tests/ -v`", "Lint command: `ruff check .`", "E2E command: `bats tests/e2e/`", "Coverage target: >= 80%".
- **Definition of Done**: "Documentation updated (`plan.md` Acceptance Contract, `spec.md`, and `design.md` reflect final implementation…)" and "CHANGELOG.md updated under `[Unreleased]` for user-visible changes"; "No governance violations (constitution rules upheld…)".

## Architectural Baselines

[Pattern_Over_Instance]: Representative examples only. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: The `deviate setup` command (`src/deviate/cli/__init__.py`) provisions agent directories and dotfiles. It currently installs commands and skills into ALL active agents regardless of `--agent`. Snippet:
  ```
  active_agents = ("claude", "opencode", "factory", "pi", "omp")
  _install_commands_to_agents(workdir, list(active_agents))
  _install_deviatdd_skill(workdir, list(active_agents))
  ```
- **Infrastructure & Operations**: `.gitattributes` declares union-merge rules for append-only JSONL ledgers, provisioned by `deviate setup` via `_ensure_root_gitattributes`. `mise.toml` `[tasks.setup]` runs `uv sync --extra dev && git config core.hooksPath .githooks`.
- **Data & State Management**: Configuration is a single TOML file parsed by `_load_deviate_config_toml` (`src/deviate/state/config.py`) into `DeviateConfig`. Session state and runtime logs live under `.deviate/` and are excluded by `.deviate/.gitignore`.
- **Quality, Safety & Observability**: Tests use `typer.testing.CliRunner` invoking the `cli` group. The skill-installation test mocks `_get_agent_command_dir` to redirect agent directories into a temp path.
- **External Integrations**: The `droid`/`factory` backend maps to the Factory Droid IDE; `omp` is an independent backend. `AGENTS.md` still documents a Graphite (`gt`) integration that `CHANGELOG.md` records as removed from active code.

## Ecosystem Research

[Web_Discovery]: Factual cataloging. No recommendations.

- **Best Practices**: Collocate a `.gitignore` with the files it controls to make ignored files easier to find and delete. [Source: https://www.bennadel.com/blog/4751-collocating-my-gitignore-configuration-files-with-the-omitted-files.htm]
- **Best Practices**: Ignore temporary files, logs, secrets (`.env`), and build folders in `.gitignore`. Git will not track, stage, or commit ignored entries. [Source: https://github.com/orgs/community/discussions/165862]
- **Common Use Cases & Pitfalls**: Git provides no per-user mechanism to ignore changes to tracked files. A directory listed in `.gitignore` is not pushed; a file needed on the remote must not be ignored. [Source: https://github.com/balenalabs/uk-train-departure-display/issues/18]
- **Common Use Cases & Pitfalls**: Config files should not need comments; applications should document their default settings. [Source: https://news.ycombinator.com/item?id=17523304]
- **Standard Tooling**: `.gitignore` is the standard mechanism for excluding generated and developer-local files from version control. [Source: https://www.deployhq.com/git/ignoring-files]

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `.deviate/config.toml` | Config | The persisted config profile; top-level keys, `[agent]`, `[models]`; the subject of the rework. | `profile = "default"` `timeout_seconds = 1800` `agent_export_mode = "local"` `graphite = false` `use_context = true` `use_libref = true` `[agent]` `backend = "pi"` `transport = "cli"` `pi_rpc = false` `timeout = 1800` |
| `.deviate/.gitignore` | Config | Local ignore rules for `.deviate/` runtime state; `config.toml` is NOT ignored here. | `session.json` `artifacts/` `prompts.log` `reports/` `rollback.jsonl` `logs/` |
| `.gitignore` | Config | Project-root ignore rules; `.deviate/` only partially ignored; `.dv8` absent. | `.deviate/session.json` `.deviate/artifacts/` `.deviate/logs/` `.deviate/review/` |
| `.gitattributes` | Config | Union-merge rules for append-only JSONL ledgers. | `specs/issues.jsonl merge=union` `specs/**/tasks.jsonl merge=union` `specs/_product/flows.jsonl merge=union` |
| `pyproject.toml` | Manifest | Package manifest declaring runtime dependencies and the `deviate` entry point. | `dependencies = [` `"typer>=0.12",` `"rich>=13.0",` `"pydantic>=2.0",` `"pyyaml>=6.0.3",` `]` |
| `mise.toml` | Manifest | Task runner definition; `[tasks.setup]` installs deps and hooks. | `[tasks.setup]` `run = "uv sync --extra dev && git config core.hooksPath .githooks"` |
| `src/deviate/cli/__init__.py` | Codebase_File | `deviate setup` dispatch; installs commands/skills to ALL active agents regardless of `--agent`. | `active_agents = ("claude", "opencode", "factory", "pi", "omp")` `_install_commands_to_agents(workdir, list(active_agents))` `_install_deviatdd_skill(workdir, list(active_agents))` |
| `src/deviate/cli/__init__.py` | Codebase_File | `_ensure_gitignore` writes entries to `.deviate/.gitignore`. | `entries = [` `"session.json",` `"artifacts/",` `"reports/",` `"rollback.jsonl",` `"logs/",` `]` |
| `src/deviate/cli/__init__.py` | Codebase_File | `_get_agent_command_dir` maps each agent to its slash-command directory. | `if agent_name in ("claude", "opencode", "factory"):` `return workdir / f".{agent_name}" / "commands"` `if agent_name == "pi":` `return workdir / ".pi" / "prompts"` `if agent_name == "omp":` `return workdir / ".omp" / "prompts"` |
| `src/deviate/state/config.py` | Codebase_File | `DeviateConfig` model; top-level `timeout_seconds`; no `graphite` field; `extra = "forbid"`. | `profile: str = "default"` `timeout_seconds: int = Field(default=1800, gt=0)` `agent_export_mode: Literal["local", "global"] = "local"` `agent: AgentConfig = Field(default_factory=AgentConfig)` `models: dict[str, str] = Field(default_factory=dict)` `use_libref: bool = False` `base_branch: str = Field(default="main", min_length=1)` |
| `src/deviate/state/config.py` | Codebase_File | `AgentConfig` model; `[agent] timeout` is the second timeout field. | `backend: Literal["opencode", "claude", "droid", "pi", "omp"] = "pi"` `timeout: int = Field(default=600, gt=0)` `pi_rpc: bool = Field(default=False, ...)` |
| `src/deviate/core/agent.py` | Codebase_File | `AGENT_TO_BACKEND` maps user-facing agent names to backends; `factory`→`droid`. | `"factory": "droid",` `"droid": "droid",` `"claude": "claude",` `"opencode": "opencode",` `"pi": "pi",` `"omp": "omp",` |
| `specs/DeviaTDD-api.md` | Manifest | Authoritative CLI spec; documents `setup` command install-to-all behavior. | "Commands land in all agent directories… regardless of the selected `--agent`." |
| `CHANGELOG.md` | Manifest | Records Graphite CLI removal from active code; documents config-affecting changes. | "**Graphite CLI integration is removed from the active code, prompts, and specs.** The `--graphite` setup flag, the `graphite` config field and `resolve_graphite_config`, the `gt create` / `gt submit` routing… are gone." |
| `AGENTS.md` | Manifest | Governance doc; still documents the removed Graphite workflow. | "## 🌳 Graphite (when `graphite = true` in `.deviate/config.toml`)" |
| `tests/test_integration/test_skill_installation.py` | Test | Pins the `setup --agent opencode` skill-install contract. | `runner.invoke(cli, ["setup", "--agent", "opencode"])` `assert result.exit_code == 0` `assert "INSTALL" in result.output.upper()` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | 9+ — `.deviate/config.toml`, `.gitignore`, `.deviate/.gitignore`, `.gitattributes`, `src/deviate/cli/__init__.py`, `src/deviate/state/config.py`, `src/deviate/core/agent.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `AGENTS.md`, `CHANGELOG.md`, plus tests |
| New Modules Required | Yes — agent auto-detection helper for `setup` when `--agent` is omitted |
| New Persistence / Data Models | Yes — reworked `DeviateConfig` / timeout schema |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Config schema changes affect model routing, agent dispatch, and all config consumers; `.deviate/` untracking affects currently tracked files; spec alignment (api + architecture) and `CHANGELOG.md` are mandatory |
| Rationale | The rework touches 3+ source modules, the config data model, git ignore rules, and mandatory spec/CHANGELOG updates. The two-timeout consolidation and `.deviate` untracking are cross-cutting changes that ripple through config consumers and tracked-file state. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | config-rework |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/config-rework.md |
| NEXT_ACTION | Run `/deviate-research` (High complexity) with the explore slug `config-rework` |
