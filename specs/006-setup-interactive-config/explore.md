# Explore: setup-interactive-config

Version: 0.9.0
Phase: EXPLORE (Macro Layer)
Slug: `setup-interactive-config`

## Problem Definition

[Statement]: Interactive `deviate setup` and production `config.toml` tidy. When flags are omitted, setup must choose a backend and choose which command/skill packs to install. Default packs are product + macro + meso + micro (by layer intent, not the current frontmatter `category` strings). Optional packs (merge, pr, walkthrough, review, html, hotfix, triage, prune, e2e, release, and peers) stay uninstalled unless selected. Generated production config must keep `base_branch` and `claim_remote`; stop shipping a fake top-level `profile = "default"` that `resolve_profile` does not accept; omit `use_libref` and every libref mention unless `--libref` was passed; persist `[agent].backend` correctly (`codex` when Codex is chosen) without writing `pi_rpc` or `transport = "rpc"` unless the backend is `pi` or `omp`; keep the already-shipped Codex Luna + high-reasoning defaults without clobbering user-set models. ISS-ADH-030 remains BACKLOG and stale. This scan catalogs the current setup, config, pack-install, profile, and libref surfaces.

[Scope]: In-scope structural components verified across the scan:
- `.deviate/config.toml` — persisted TOML (`profile`, `timeout_seconds`, `agent_export_mode`, `use_libref`, `base_branch`, `claim_remote`, `[agent]`, optional `[models]`).
- `deviate setup` in `src/deviate/cli/__init__.py` — flags, interactive agent/claim prompts, `_scaffold_dotfiles`, `_write_agent_block_to_config`, `_apply_codex_setup_defaults`, `_apply_governance`, `_install_commands_to_agents`, `_install_deviatdd_skill`.
- `DeviateConfig` / `AgentConfig` / unused `ProfileConfig` in `src/deviate/state/config.py`.
- `resolve_profile` in `src/deviate/core/profile.py` and `deviate micro run --profile` in `src/deviate/cli/micro.py`.
- Command discovery/install in `src/deviate/core/commands.py` (`discover_commands` returns every `*.md` stem; no pack filter).
- Command frontmatter `category` vs `layer` under `src/deviate/prompts/commands/`.
- Libref surfaces: `use_libref` key, `src/deviate/prompts/governance/libref_seed.md`, `src/deviate/prompts/core/core.md` Offline Documentation Mandate, `_apply_governance` unconditional upsert.
- Packaged skill `src/deviate/prompts/skills/deviatdd/SKILL.md` (no libref token).
- ISS-ADH-030 at `specs/adhoc/issues/030-config-rework.md` (BACKLOG) and the already-shipped per-agent install / Graphite-free code on `main`.

[Exclusions]: Architectural decisions, design trade-offs, risk analysis, data modeling, pack-taxonomy design, and the final config schema are deferred to `deviate-research`. This document only catalogs what exists. PR #125 (prune COMPLETED gate) stays open/unmerged and is out of this scan's mutation scope.

## Discovery Audit Results

### Verified Dependencies
- `typer>=0.12`: Declared in `pyproject.toml` `[project] dependencies`; imported in `src/deviate/cli/__init__.py` as the CLI framework.
- `rich>=13.0`: Declared in `pyproject.toml`; `Console` and `rich.prompt.Prompt` drive setup I/O (`_prompt_agent_selection`, `_prompt_claim_remote`).
- `pydantic>=2.0`: Declared in `pyproject.toml`; defines `DeviateConfig`, `AgentConfig`, and `ProfileConfig` in `src/deviate/state/config.py`.
- `pyyaml>=6.0.3`: Declared in `pyproject.toml`.
- `tomllib` (stdlib): Used in `src/deviate/state/config.py` `_load_deviate_config_toml` and in `src/deviate/cli/__init__.py` TOML helpers.

### Ghost Dependencies
- `libref` (offline documentation CLI): Referenced in `src/deviate/prompts/core/core.md` (universal invariant 7), `src/deviate/prompts/governance/libref_seed.md`, `_detect_libref()` via `shutil.which("libref")`, and the `use_libref` config key. Not declared in `pyproject.toml`. Runtime-only, out of tree.
- `codex` / `pi` / `omp` / `claude` / `opencode` / `droid` binaries: Referenced as agent backends in `src/deviate/core/agent.py` `AGENT_TO_BACKEND`. Not declared as installation dependencies.
- No `graphite` / `gt` symbol remains under `src/deviate` (Python). `CHANGELOG.md` records Graphite removal. This is a declarative finding only.

### Manifest Files Observed
- `.deviate/config.toml`: The DeviaTDD persisted configuration profile (TOML).
- `pyproject.toml`: Python package manifest declaring runtime dependencies and the `deviate` console script.
- `mise.toml`: Task runner configuration.
- `.gitignore`: Project-root ignore rules.
- `.deviate/.gitignore`: Local ignore rules for `.deviate/` runtime state.
- `.gitattributes`: Union-merge rules for append-only JSONL ledgers.

### Test Runner Configuration
- Test command: `pytest tests/ -v` (quoted in `specs/constitution.md` §3).
- Lint command: `ruff check .` (quoted in `specs/constitution.md` §3).
- E2E command: `bats tests/e2e/` (quoted in `specs/constitution.md` §3).
- Code quality gate: `mise run check` (quoted in `specs/constitution.md` §2 Tooling).
- Verified test surfaces: `tests/test_cli/test_setup.py` (per-agent isolation, Codex Luna/reasoning upserts, no-clobber); `tests/test_state/test_config.py` (`DeviateConfig.profile == "default"`, `use_libref` default False, unused `ProfileConfig`); `tests/test_core/test_profile.py` (`resolve_profile` public names are `full` / `fast`; legacy `secure` is an internal alias); `tests/test_integration/test_skill_installation.py`.

### Manifest-Constitution Divergence
- Constitution §1 Config-Driven Model Routing documents `[models]` resolution (phase key → `default` → backend-native) and Codex Luna + `reasoning_effort` seeding. The same constitution does not mention a top-level `profile` key. Observed `DeviateConfig.profile` default is the string `"default"`, which is not in `resolve_profile`. Both quoted verbatim; no adjudication.
- Constitution §2 Database states "Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment". Observed generated config also writes `profile`, `use_libref`, `pi_rpc`, and `transport` even when unused by the chosen backend. Quoted verbatim; no adjudication.
- Constitution §1 Four-Layer Architecture names Product / Macro / Meso / Micro. Observed command frontmatter `category` strings do not match that layering (`deviate-red.md` has `category: deviattd-macro-layer` and `layer: micro`; `deviate-green.md` and `deviate-refactor.md` same mismatch; `deviate-prune.md` misspells `deviattd`). Quoted verbatim; no adjudication.

## Constitution Quotes

Constitution excerpts quoted verbatim from `specs/constitution.md` (Version 0.9.0). No interpretation.

- **Architectural Principles**: "**Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Macro PRD/shard/adhoc artifacts carry acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract. The Product layer is skipped in single-feature repos; the remaining three layers have strict phase gates — no layer may be skipped."
- **Architectural Principles**: "**Config-Driven Model Routing**: Phase→model assignments are declared in `.deviate/config.toml` under `[models]`. The `default` key sets the model for all phases without an explicit entry. Any other key (e.g., `judge`, `plan`, `red`) is treated as a phase name. Resolution order: phase-specific key → `default` key → no model flag (backend-native default). `opencode`, `droid`, `pi`, `omp`, and `codex` backends support `--model`; `claude` backend ignores model config silently. Codex setup seeds `[models].default = \"gpt-5.6-luna\"` and `[agent].reasoning_effort = \"high\"` when those keys are missing/empty; spawned `codex exec` receives `-c model_reasoning_effort=<value>` from that field (official values `minimal|low|medium|high|xhigh`)."
- **Tech Stack Standards**: "Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment" and "Session state: JSON files under `.deviate/`".
- **Testing Protocols**: "Test command: `pytest tests/ -v`", "Lint command: `ruff check .`", "E2E command: `bats tests/e2e/`", "Coverage target: >= 80%".
- **Definition of Done**: "Documentation updated (`plan.md` Acceptance Contract, `spec.md`, and `design.md` reflect final implementation…)" and "CHANGELOG.md updated under `[Unreleased]` for user-visible changes"; "No governance violations (constitution rules upheld…)".

## Architectural Baselines

[Pattern_Over_Instance]: Representative examples only. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: `deviate setup` (`src/deviate/cli/__init__.py`) already prompts for an agent when `--agent` is omitted and no `[agent].backend` exists (`_prompt_agent_selection` via `rich.prompt.Prompt.ask`). It also prompts for `claim_remote` on a fresh workspace (`_prompt_claim_remote`). There is no pack-selection prompt. Command install calls `discover_commands()` and writes every packaged `deviate-*.md` (26 stems) plus the shared `deviatdd` skill to the single selected agent. Per-agent isolation already shipped on `main` (2.23.1): `_install_commands_to_agents(workdir, [install_agent])`.
- **Infrastructure & Operations**: `_ensure_gitignore` writes `.deviate/.gitignore` entries for `session.json`, `artifacts/`, `reports/`, `rollback.jsonl`, `logs/`. `_ensure_root_gitignore` writes agent-install globs and `.worktrees/`. Neither ignores `.deviate/` itself. `.gitattributes` union-merge rules are provisioned by `_ensure_root_gitattributes`. Graphite CLI symbols are absent from `src/deviate`.
- **Data & State Management**: Configuration is a single TOML file parsed by `_load_deviate_config_toml` into callers that read individual keys (`resolve_base_branch`, `resolve_claim_remote`, `resolve_model_for_phase`, `resolve_reasoning_effort`). `DeviateConfig` is constructed at setup-scaffold time via `model_dump()` + `_dict_to_toml`. `DeviateConfig.profile` default is `"default"`. Runtime execution profiles live in `src/deviate/core/profile.py`: `full` = judge+refactor, `fast` = skip both. Legacy `secure` is an internal alias (JUDGE on, REFACTOR off), not a public profile. `deviate micro run --profile` defaults to `"full"` and validates via `resolve_profile`. Nothing in `src/deviate` reads `DeviateConfig.profile` to feed `resolve_profile`. An unused `ProfileConfig` model already types `default: Literal["full", "fast"] = "full"`.
- **Quality, Safety & Observability**: Tests use `typer.testing.CliRunner` invoking the `cli` group from a temp `chdir`. `tests/test_cli/test_setup.py` pins per-agent isolation and Codex Luna/reasoning no-clobber. `tests/test_state/test_config.py` asserts `config.profile == "default"`. `tests/test_core/test_profile.py` asserts `resolve_profile("invalid")` raises and that public names are `full` / `fast`.
- **External Integrations**: Agent backends are `factory`/`droid`/`claude`/`opencode`/`pi`/`omp`/`codex` (`AGENT_CHOICES` / `AGENT_TO_BACKEND`). Codex CLI 0.117+ installs under `.agents/skills/<name>/SKILL.md`. Pi uses `.pi/prompts/`; OMP uses `.omp/prompts/`. `libref` is PATH-detected (`_detect_libref`) and unconditionally seeded into `CLAUDE.md`/`AGENTS.md` by `_apply_governance`.

## Ecosystem Research

[Web_Discovery]: Factual cataloging. No recommendations.

- **Best Practices**: Typer documents interactive `Prompt.ask` for missing values and prefers CLI options so scripts stay non-interactive. [Source: https://typer.tiangolo.com/tutorial/prompt/]
- **Best Practices**: Typer has no native multi-select menu; maintainers point operators at a separate prompt library used inside a Typer command. [Source: https://github.com/tiangolo/typer/issues/295]
- **Common Use Cases & Pitfalls**: Python `questionary.checkbox` is the documented multi-select pattern for "include optional tooling" setup wizards (returns `list[str]`). [Source: https://pythonhowtoprogram.com/how-to-use-python-questionary-for-interactive-cli-prompts/]
- **Common Use Cases & Pitfalls**: Plugin manifests treat optional packs as disabled unless `enabledByDefault` is exactly `true`; omit the field (or any non-`true` value) to leave the pack off. [Source: https://docs.openclaw.kr/plugins/manifest]
- **Standard Tooling**: Config loaders that emit a resolved object commonly omit internal/unused keys (`omit$Keys`) rather than persist every default. [Source: https://www.npmjs.com/package/c12]
- **Standard Tooling**: This repository already uses `rich.prompt.Prompt` for single-choice setup (`_prompt_agent_selection`, `_prompt_claim_remote`). Rich `Prompt.ask` is single-select (`choices=[]`); it is not a checkbox control.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `.deviate/config.toml` | Config | This repo's persisted config: `profile=default`, `use_libref=true`, `[agent]` backend=pi with `pi_rpc` + `transport=rpc`. | `profile = "default"` `timeout_seconds = 1800` `use_libref = true` `base_branch = "main"` `claim_remote = true` `[agent]` `backend = "pi"` `timeout = 600` `pi_rpc = false` `transport = "rpc"` |
| `src/deviate/state/config.py` | Codebase_File | `DeviateConfig.profile` default is the string `"default"`; `use_libref` defaults False; `extra = "forbid"`. | `class DeviateConfig(BaseModel):` `    # Profile name — defines preset config groups (default, full, fast)` `    profile: str = "default"` `    timeout_seconds: int = Field(default=1800, gt=0)` `    agent_export_mode: Literal["local", "global"] = "local"` `    agent: AgentConfig = Field(default_factory=AgentConfig)` `    use_libref: bool = False` `    base_branch: str = Field(default="main", min_length=1)` `    claim_remote: bool = Field(default=True)` |
| `src/deviate/state/config.py` | Codebase_File | `AgentConfig` always models `pi_rpc` and `transport`; validator defaults `transport` to `rpc` for `pi`/`omp`. | `backend: Literal["opencode", "claude", "droid", "pi", "omp", "codex"] = "pi"` `timeout: int = Field(default=600, gt=0)` `pi_rpc: bool = Field(default=False, ...)` `transport: Literal["rpc", "cli"] = Field(default="cli")` `reasoning_effort: Optional[ReasoningEffort] = Field(default=None)` |
| `src/deviate/state/config.py` | Codebase_File | Unused `ProfileConfig` already types only `full` / `fast`. | `class ProfileConfig(BaseModel):` `    default: Literal["full", "fast"] = "full"` `    model_config = {"extra": "forbid"}` |
| `src/deviate/core/profile.py` | Codebase_File | Runtime profiles accepted by `resolve_profile`; `"default"` is not a key. | `_PROFILE_DEFAULTS: dict[str, tuple[bool, bool]] = {` `    "full": (False, False),` `    "fast": (True, True),` `}` |
| `src/deviate/cli/micro.py` | Codebase_File | `deviate micro run --profile` defaults to `"full"` and validates via `resolve_profile`. | `profile: str = typer.Option(` `    "full",` `    "--profile",` `    callback=_validate_profile,` `    help="Execution profile: full, fast",` `)` |
| `src/deviate/cli/__init__.py` | Codebase_File | Generated TOML comment still advertises `"default"` as a preset group. | `"profile": 'Micro-run default when --profile is omitted: "full" or "fast"',` `"use_libref": "Enable the libref CLI for offline documentation lookups",` `"base_branch": "Trunk branch for worktrees, PR base, and review diffs",` `"claim_remote": "Push the claim branch as a distributed lock (default true)",` |
| `src/deviate/cli/__init__.py` | Codebase_File | Fresh scaffold dumps the full `DeviateConfig` (including `profile` and `use_libref`) via `model_dump()`. | `config = DeviateConfig(` `    agent_export_mode=agent_export_mode,` `    use_libref=use_libref,` `    claim_remote=claim_remote,` `)` `...` `_write_if_missing(` `    config_path,` `    _dict_to_toml(config.model_dump(), comments=_CONFIG_TOML_COMMENTS),` `)` |
| `src/deviate/cli/__init__.py` | Codebase_File | `_write_agent_block_to_config` upserts only `backend = "<value>"`; other `[agent]` keys stay as-is. | `def _write_agent_block_to_config(config_path: Path, backend: str) -> bool:` `    """Surgically upsert ``[agent]\nbackend = "<value>"`` in *config_path*.` |
| `src/deviate/cli/__init__.py` | Codebase_File | Setup flags: `--agent`, `--libref`, `--no-claim-remote`, `--agent-export-mode`. No pack flag. | `libref: bool = typer.Option(False, "--libref", help="Force-enable offline libref CLI integration (overrides PATH detection)",)` `agent: str \| None = typer.Option(None, "--agent", help="Agent platform to install and persist as [agent].backend", callback=_validate_agent_choice,)` |
| `src/deviate/cli/__init__.py` | Codebase_File | `use_libref` is True when `--libref` is passed, else PATH detection. | `use_libref_val = True if libref else _detect_libref()` |
| `src/deviate/cli/__init__.py` | Codebase_File | `_apply_governance` always upserts `libref_seed.md` into CLAUDE.md / AGENTS.md. | `libref_content = _read_seed(_GOVERNANCE_MODULE, "libref_seed.md")` `if libref_content:` `    for t in targets:` `        _upsert_governance_block(t, libref_content)` |
| `src/deviate/cli/__init__.py` | Codebase_File | Setup installs every discovered command plus the shared skill to the one selected agent. | `install_agent = _normalize_install_agent(selected_agent)` `_install_commands_to_agents(workdir, [install_agent])` `_install_deviatdd_skill(workdir, [install_agent])` |
| `src/deviate/core/commands.py` | Codebase_File | `discover_commands` returns every `*.md` stem; no pack or layer filter. | `def discover_commands(commands_root: Path \| None = None) -> list[str]:` `    root = _resolve_commands_root(commands_root)` `    if not root.exists():` `        return []` `    return sorted(p.stem for p in root.glob("*.md") if p.is_file())` |
| `src/deviate/prompts/commands/deviate-red.md` | Manifest | Frontmatter `category` says macro; `layer` says micro. | `name: deviate-red` `category: deviattd-macro-layer` `layer: micro` |
| `src/deviate/prompts/commands/deviate-explore.md` | Manifest | Macro command with matching `layer: macro`. | `name: deviate-explore` `category: deviatdd-macro-layer` `layer: macro` |
| `src/deviate/prompts/commands/deviate-plan.md` | Manifest | Meso command with matching `layer: meso`. | `name: deviate-plan` `category: deviatdd-meso-layer` `layer: meso` |
| `src/deviate/prompts/commands/deviate-flows.md` | Manifest | Product command with `layer: product`. | `name: deviate-flows` `category: deviatdd-product-layer` `layer: product` |
| `src/deviate/prompts/commands/deviate-pr.md` | Manifest | Optional-pack candidate; category meso; no `layer` key. | `name: deviate-pr` `category: deviatdd-meso-layer` `aliases:` `  - pr` |
| `src/deviate/prompts/core/core.md` | Manifest | Universal invariant 7 mandates `libref` on every composed command. | `7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism.` |
| `src/deviate/prompts/governance/libref_seed.md` | Manifest | Governance seed upserted on every setup. | `## 📚 Offline Documentation (libref)` `Prefer `libref query <lib> "<topic>"` over web fetching.` |
| `src/deviate/prompts/skills/deviatdd/SKILL.md` | Manifest | Shared skill body contains no `libref` token. | `name: deviatdd` `description: Prepare missing Meso artifacts with idempotent deviate meso run, then run deviate micro run one task at a time until NO_PENDING_TASKS; inspect and triage each result.` |
| `src/deviate/core/agent.py` | Codebase_File | `AGENT_TO_BACKEND` includes `codex`; `factory` maps to `droid`. | `"factory": "droid",` `"droid": "droid",` `"claude": "claude",` `"opencode": "opencode",` `"pi": "pi",` `"omp": "omp",` `"codex": "codex",` |
| `specs/adhoc/issues/030-config-rework.md` | Manifest | Stale BACKLOG issue: gitignore-all-of-`.deviate`, Graphite removal, timeout consolidation, auto-detect-all-agents. | `issue_id: ISS-ADH-030` `The `deviate setup` command does not git-ignore `.deviate/` by default, installs skills and commands into every active agent regardless of the `--agent` flag, and ships an obsolete Graphite config key plus two redundant timeout settings.` |
| `tests/test_cli/test_setup.py` | Test | Pins per-agent isolation and Codex Luna / reasoning no-clobber. | `result = runner.invoke(cli, ["setup", "--agent", "opencode"])` `assert result.exit_code == 0, result.output` `assert (tmp_path / ".opencode" / "commands" / "deviate-red.md").is_file()` |
| `tests/test_state/test_config.py` | Test | Pins `DeviateConfig.profile == "default"`. | `config = DeviateConfig()` `assert config.profile == "default"` `assert config.timeout_seconds == 1800` |
| `tests/test_core/test_profile.py` | Test | Pins `resolve_profile` rejects unknown names; public set is full/fast. | `with pytest.raises(ValueError) as exc:` `    resolve_profile("invalid")` `msg = str(exc.value).lower()` `assert "full" in msg` |
| `pyproject.toml` | Manifest | Runtime dependencies and `deviate` entry point. | `dependencies = [` `"typer>=0.12",` `"rich>=13.0",` `"pydantic>=2.0",` `"pyyaml>=6.0.3",` `]` |
| `specs/constitution.md` | Manifest | Four-layer architecture and config-driven model routing. | `**Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | 8+ — `src/deviate/cli/__init__.py`, `src/deviate/state/config.py`, `src/deviate/core/commands.py`, `src/deviate/core/profile.py` (or config-profile wiring), `src/deviate/prompts/core/core.md` and/or `src/deviate/prompts/governance/libref_seed.md`, `tests/test_cli/test_setup.py`, `tests/test_state/test_config.py`, `CHANGELOG.md` |
| New Modules Required | Yes — pack taxonomy / pack-filter for command install, plus an interactive pack prompt |
| New Persistence / Data Models | Yes — generated `config.toml` shape (profile meaning or removal; omit `use_libref` and dead `[agent]` keys) |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Every consumer `deviate setup`; composed slash-command bodies inherit `core.md` libref text; ISS-ADH-030 remains BACKLOG and must not be silently reopened; Codex Luna/reasoning already on `main` must not be clobbered |
| Rationale | The change spans setup interactivity, command-pack filtering, generated TOML schema, runtime profile wiring, and libref leakage into composed prompts. That is multi-module and cross-cutting across every consumer install. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | setup-interactive-config |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/setup-interactive-config.md |
| NEXT_ACTION | Run `/deviate-research` (High complexity) with the explore slug `setup-interactive-config` |
