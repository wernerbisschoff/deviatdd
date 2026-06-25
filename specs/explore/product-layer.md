# Exploration: Product Layer

## Problem Definition

[Statement]: Introduce a new Product layer that lives above the existing Macro layer of the DeviaTDD CLI. The layer consolidates the existing `/deviate-constitution` phase and adds three new phases: `/deviate-flow`, `/deviate-architecture`, and `/deviate-release`. The layer is responsible for canonical product artifacts (user flows, cross-epic architecture, release plans) that epics and adhoc work reference, rather than redefining per epic.

[Scope]: In-scope structural components verified across the scan:
- The current macro-layer phase set under `prompts/deviate-*/SKILL.md` (15 SKILL.md files).
- The CLI command tree at `src/deviate/cli/__init__.py` (Typer sub-app registrations).
- The constitution at `specs/constitution.md` (v0.2.0; declares a fixed three-layer Macro/Meso/Micro architecture).
- The Product-layer staging directory at `specs/_product/` (exists, contains empty `flows/` subdirectory).
- The state modules at `src/deviate/state/` (Pydantic models for session and config).
- The authoritativespec documents at `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md`.
- The macro-layer orchestration phase order `_PHASE_ORDER` in `src/deviate/cli/macro.py:747`.
- The CLI command pattern used by existing phase modules (`src/deviate/cli/constitution.py` as reference).

[Exclusions]: Architectural decisions, design trade-offs, risk analysis, data modeling, phase-routing strategy, prompt templates for the new phases, and failure-mode speculation — all deferred to the `deviate-research` skill. This scan catalogs what exists; it does not propose how the new layer should be implemented.

## Discovery Audit Results

### Verified Dependencies

Dependencies declared in `pyproject.toml` (lines 6-32):
- `typer>=0.12` — present at `src/deviate/cli/__init__.py:653` (`cli = typer.Typer(no_args_is_help=True)`).
- `rich>=13.0` — present at `src/deviate/cli/constitution.py:9` (`from rich.console import Console`).
- `pydantic>=2.0` — present at `src/deviate/state/config.py` (referenced by subagent as containing `class DeviateConfig(BaseModel)`).
- `pyyaml>=6.0.3` — declared, no current `src/` import sites flagged by subagent (potential future use for Product-layer frontmatter parsing).
- `tree-sitter` + 24 language grammars — declared; used by AST/symbol-extraction tooling referenced in `prompts/deviate-research/SKILL.md` and `prompts/deviate-tasks/SKILL.md`.

Dev dependencies (lines 38-41, 56-61): `pytest>=8.0`, `pytest>=9.0.3`, `ruff>=0.4`, `ruff>=0.15.16`, `typer>=0.26.7`. Both `[project.optional-dependencies] dev` and `[dependency-groups] dev` blocks exist (duplication noted).

`package.json` declares `opencode-codebase-index: ^0.10.0` (tooling outside the Python runtime).

### Ghost Dependencies

- **`aider.coders.Coder`** — referenced in `specs/DeviaTDD-architecture.md` (lines 66-78) and historically in `src/deviate/cli/micro.py`. Not declared in `pyproject.toml`. Current `AgentBackend` (`src/deviate/core/agent.py`) dispatches to `opencode`, `droid`, or `claude` binaries; the aider substrate appears to be a legacy reference.
- **`bats`** — referenced in `specs/constitution.md:43` and `mise.toml:14`. Not a Python package; expected at the system level.
- **`graphite` / `gt` CLI** — referenced in `src/deviate/cli/meso.py:1137-1157` and `.deviate/config.toml:5` (`graphite = false`). Not declared in `pyproject.toml`; conditional system dependency.
- **`gh` CLI** — referenced in `src/deviate/cli/meso.py:1175-1196`. Not declared; system-level.
- **`fcntl`** — referenced in `src/deviate/state/ledger.py:17-22`. Stdlib (Windows fallback).
- **`tomllib`** — referenced in multiple places. Stdlib (Python 3.11+).
- **`importlib.resources`** — referenced in `src/deviate/cli/constitution.py:30` (`seed = importlib.resources.files("deviate.prompts").joinpath(filename)`). Stdlib.

### Manifest Files Observed

- `pyproject.toml` — Package metadata (`name = "deviate"`, `version = "0.4.4"`), build system (`hatchling`), entry point (`deviate = "deviate.main:app"`).
- `mise.toml` — Task runner config: 13 defined tasks (`test`, `test-e2e`, `lint`, `lint-fix`, `format`, `format-check`, `check-types`, `check`, `fix`, `setup`, `clean`, `dev`, `install-tool`, `help`).
- `package.json` — Declares `opencode-codebase-index: ^0.10.0` (Node-side tooling).
- `uv.lock` — Lockfile for `uv` package manager.
- `package-lock.json` — Lockfile for npm-side tooling.

### Test Runner Configuration

- `mise.toml:8-9`: `[tasks.test]\nrun = "uv run pytest tests/ -v"` — Root-level test invocation.
- `mise.toml:12-13`: `[tasks.test-e2e]\nrun = "bats tests/e2e/"` — E2E tests via bats.
- `pyproject.toml:53-54`: `[tool.pytest.ini_options]\ntestpaths = ["tests"]`.
- `tests/conftest.py` — defines `_git_env()` (strips `GIT_*` env vars) and `tmp_git_repo` fixture.
- `tests/` contains 10 subdirectories: `core/`, `test_cli/`, `test_core/`, `test_e2e/`, `test_integration/`, `test_macro/`, `test_meso/`, `test_micro/`, `test_state/`, `test_ui/`.

### Manifest-Constitution Divergence

`pyproject.toml:5` declares `requires-python = ">=3.13"`. The constitution at `specs/constitution.md:21` declares `Python 3.13`. No divergence on Python version.

`pyproject.toml:9` declares `pydantic>=2.0`; the constitution does not mention Pydantic specifically but declares `Config: TOML via .deviate/config.toml` (line 33) and `Session state: JSON files under .deviate/` (line 31). The constitution does not explicitly cite Pydantic as a state-validation substrate, but the code under `src/deviate/state/` uses Pydantic `BaseModel` extensively. No manifest-constitution divergence to adjudicate — the constitution is silent on Pydantic rather than contradictory.

The constitution at `specs/constitution.md:36` cites `Micro-sandbox: Aider Python API (aider.coders.Coder) as LLM execution substrate`. The current `src/deviate/core/agent.py` uses an `AgentBackend` abstraction that does NOT depend on `aider.coders.Coder` (aider is ghost). The constitution text is aspirational vs. implementation reality — divergence flagged for the research skill.

## Constitution Quotes

Constitution excerpts quoted verbatim from `specs/constitution.md`. No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.

- **Architectural Principles**: "- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."
- **Tech Stack Standards**: "- Python 3.13\n- Target: CLI application (`deviate`)\n- Framework: Typer (CLI entry points) with Rich for terminal I/O\n\n### Database\n- No persistent database runtime (all state tracked in JSONL ledgers and TOML config)\n- Session state: JSON files under `.deviate/`\n- Issue ledger: `specs/issues.jsonl` (append-only JSONL)\n- Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)\n- Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment"
- **Testing Protocols**: "- Test framework: pytest\n- Test root: `tests/`\n- Test extension: `.py`\n- Test command: `pytest tests/ -v`\n- Lint command: `ruff check .`\n- E2E command: `bats tests/e2e/`\n\n### Coverage\n- Coverage target: >= 80%\n- RED phase tests must fail with `AssertionError` or `NotImplementedError` — syntax crashes are rejected\n- GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits\n- REFACTOR phase runs regression gate: tests must re-pass after polish"
- **Definition of Done**: "- [ ] Code implemented (satisfies acceptance criteria from `spec.md`)\n- [ ] Tests passing (pytest with clean exit code 0)\n- [ ] Lint passing (ruff check with no violations)\n- [ ] Judge phase passed (git diff validated against `spec.md` invariants)\n- [ ] E2E tests passing (if applicable; bats for CLI integration)\n- [ ] Documentation updated (`spec.md` and `design.md` reflect final implementation)\n- [ ] No governance violations (constitution rules upheld, no HITL gates bypassed)\n- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)"

## Architectural Baselines

[Pattern_Over_Instance]: Only representative examples or base classes are listed, not every instance. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: CLI command tree via Typer sub-apps at `src/deviate/cli/__init__.py:653-677` — 22 subcommands registered (`explore`, `research`, `prd`, `shard`, `specify`, `plan`, `tasks`, `pr`, `meso`, `macro`, `red`, `green`, `yellow`, `judge`, `refactor`, `execute`, `e2e`, `hotfix`, `adhoc`, `constitution`, `init`, `feature`, `inspect`, `review`, `run`). Phase constants declared at `src/deviate/state/config.py:21-39` (`_VALID_PHASES = frozenset({"IDLE", "EXPLORE", "RESEARCH", "PRD", "SHARD", "SPECIFY", "PLAN", "TASKS", "RED", "GREEN", "YELLOW", "JUDGE", "REFACTOR", "E2E", "EXECUTE", "HOTFIX"})`). Error-handling pattern: `_halt(phase, message)` in `src/deviate/cli/_common.py:98-100` raises `SystemExit(1)` via Rich red-text console output.

- **Infrastructure & Operations**: `mise.toml:1-62` declares 13 tasks via `[tasks.<name>]` blocks. No `.github/` directory observed (no CI pipeline config present). Deployment via `uv tool install --editable .` (`mise.toml:56-57`, `[tasks.install-tool]`). Env config in `.deviate/config.toml` (`profile`, `timeout_seconds`, `agent_export_mode`, `[agent]`, `[models]`, `graphite`, `use_libref`).

- **Data & State Management**: JSONL append-only ledgers at `specs/issues.jsonl`, `specs/**/tasks.jsonl`, `specs/adhoc.jsonl`, `.deviate/rollback.jsonl`. Single-file session state at `.deviate/session.json`. Pydantic `BaseModel` serialization to TOML via `_dict_to_toml()` + `_CONFIG_TOML_COMMENTS` dict in `src/deviate/state/config.py:184-248`.

- **Quality, Safety & Observability**: pytest with `tmp_git_repo` fixture at `tests/conftest.py` (git isolation). Mock pattern: `@patch("deviate.cli.micro._run_pytest")` for tests that invoke CLI commands running pytest internally (mandated by AGENTS.md). TamperGuard in `src/deviate/core/tamper.py:20-30` with three contexts (`RED_TEST_CREATION`, `GREEN_IMPLEMENTATION`, `YELLOW_AMENDMENT`) and two verdicts (`TAMPER_PASS`, `TAMPER_DETECTED`). HITL Gate 1 implementation in `src/deviate/cli/macro.py:425-494` via `_check_pending_hitl_decisions()`.

- **External Integrations**: Agent backends (`opencode`, `droid`, `claude`) at `src/deviate/core/agent.py` (literal types per subagent). Graphite CLI (`gt`) conditional integration at `src/deviate/cli/meso.py:1137-1157` when `.deviate/config.toml` has `graphite = true`. `gh` CLI direct subprocess at `src/deviate/cli/meso.py:1198-1217` when Graphite is disabled. `libref` offline documentation tool referenced in `.deviate/config.toml:7` (`use_libref = true`) and across AGENTS.md guidance.

## Ecosystem Research

[Web_Discovery]: Factual cataloging of industry best practices, common use cases, and standard tools relevant to the Product-layer problem domain. Library/framework documentation was queried via `libref`; web research was used for higher-level SDD patterns.

- **Best Practices — GitHub spec-kit canonical SDD pipeline**: spec-kit (115k stars) defines `/speckit.constitution` → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` → `/speckit.converge`. Includes an explicit **constitution** phase as the first governance artifact, pre-committing the project to behavioral principles before any feature work. Bundle manifest pattern (`bundle.yml`) supports role-based personas (product manager, business analyst, security researcher, developer). Source: https://github.com/github/spec-kit — "The first step should be establishing your project's governing principles using the `/speckit.constitution` command. This helps ensure consistent decision-making throughout all subsequent development phases."

- **Best Practices — Kiro multi-layer spec model**: Kiro layers specs into requirements → architectural designs → sequenced tasks → property-based test verification. Includes a correctness gate (property-based testing) positioned after implementation, not within it. Source: https://kiro.dev/ — "Kiro can turn your prompts into structured requirements, architectural designs, and sequenced tasks implemented by parallel agents. It then validates code with property-based tests which catch the edge cases that pass unit tests but break in production."

- **Best Practices — GSD Core five-phase loop**: GSD Core (5.1k stars) uses **Discuss → Plan → Execute → Verify → Ship** as its unit of work. The Product layer naturally hosts "Discuss" (user-flow definition) and "Ship" (release planning). Source: https://github.com/open-gsd/gsd-core — "Each milestone repeats the same five-step loop, one phase at a time: 1. Discuss — capture implementation decisions before anything is planned. 2. Plan — research, decompose, and verify the plan fits a fresh context window. 3. Execute — run plans in parallel waves. 4. Verify — walk through what was built; diagnose and fix before declaring done. 5. Ship — create the PR, archive the phase."

- **Best Practices — arc42 architecture template**: arc42 defines 12 sections for system architecture: (1) Introduction & Goals, (2) Constraints, (3) Context & Scope, (4) Solution Strategy, (5) Building Block View, (6) Runtime View, (7) Deployment View, (8) Crosscutting Concepts, (9) Architecture Decisions, (10) Quality Requirements, (11) Risks & Technical Debt, (12) Glossary. Sections 3-4 are the natural home for a Product-layer architecture phase output. Source: https://arc42.de/overview/ — "The core of architecture documentation consists of the context delineation (ch. 3), three views (building block view, runtime view, and deployment view — ch. 5-7), and crosscutting concepts (ch. 8). The remaining chapters round out the documentation."

- **Best Practices — C4 model for cross-epic architecture visualization**: C4 provides hierarchical abstractions: software system → container → component → code. Product-layer architecture phase produces L1 (System Context) and optionally L2 (Container). Deep component/code views belong to Meso/Micro. Source: https://c4model.com/ — "The C4 model is an easy to learn, developer friendly approach to software architecture diagramming: (1) A set of hierarchical abstractions — software systems, containers, components, and code. (2) A set of hierarchical diagrams — system context, containers, components, and code."

- **Best Practices — Jobs-to-be-Done (JTBD) for user-flow modeling**: JTBD is the standard for Product-layer user flow modeling. The job map (universal job steps: Define → Locate → Prepare → Confirm → Execute → Monitor → Modify → Conclude) provides a template for `/deviate-flow`. Source: https://www.jtbd.info/ — JTBD is "a framework for understanding customer needs based on the 'jobs' customers are trying to get done in their lives."

- **Common Use Cases & Pitfalls — SAFe PI Planning as release planning template**: PI Planning outputs include committed PI objectives and an ART planning board with feature delivery dates and dependencies. Maps directly to a `/deviate-release` phase. Source: https://www.scaledagileframework.com/pi-planning/ — "PI Planning outputs include committed PI objectives from the Agile Teams and an ART planning board that reflects new feature delivery dates and dependencies."

- **Common Use Cases & Pitfalls — Artifact proliferation without traceability**: OpenSpec documentation warns against rigidity: heavy phase gates create friction. A Product layer must ensure that `/deviate-flow`, `/deviate-architecture`, and `/deviate-release` produce artifacts that are consumed by downstream layers AND updated by downstream changes. Source: https://github.com/Fission-AI/OpenSpec — "vs. Spec Kit — Thorough but heavyweight. Rigid phase gates, lots of Markdown, Python setup. OpenSpec is lighter and lets you iterate freely."

- **Common Use Cases & Pitfalls — Context rot across sessions**: GSD Core highlights "context rot" — quality degradation as an AI fills its context window. Product-layer artifacts must be lightweight reference documents that fresh-context subagents can consume. Source: https://github.com/open-gsd/gsd-core — "It solves context rot — the quality degradation that accumulates as an AI fills its context window — by running all heavy research, planning, and execution work in fresh-context subagents while keeping your main session lean."

- **Standard Tooling — Jido for Elixir agent orchestration**: Jido provides actor-based orchestration with Actions (pure state transforms returning directives) and Signals (routed messages). Relevant submodules: `Jido.Actions.Scheduling` (delayed signals, cron jobs, timeouts for release planning), `Jido.Actions.Lifecycle` (parent-child spawning for macro/micro orchestration), `Jido.Actions.Control` (signal forwarding, cancellation, broadcast for workflow routing). Source: libref query jido "actions" — "Jido keeps agent decision logic pure. Actions may be pure or effectful. Directives are for effects you want the runtime to own." Source: libref query jido "Actions.Scheduling" — "Base actions for scheduling delayed signals and timeouts."

- **Standard Tooling — Jellyfish engineering intelligence**: Commercial pattern for layering "business alignment" on top of "engineering metrics." Product layer in DeviaTDD would serve the same role as Business Alignment. Source: https://jellyfish.co/ — "Align Engineering Effort — See how engineering allocation maps to strategic priorities and rebalance work as goals shift."

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | Manifest | Package metadata + dependencies for the `deviate` Python package | `name = "deviate"`<br>`version = "0.4.4"`<br>`description = "DeviaTDD CLI — agent orchestration framework"`<br>`requires-python = ">=3.13"`<br>`dependencies = [`<br>`    "typer>=0.12",`<br>`    "rich>=13.0",`<br>`    "pydantic>=2.0",` |
| `mise.toml` | Manifest | Task runner config; 13 tasks for test/lint/format/check/clean/install | `[tasks.test]`<br>`run = "uv run pytest tests/ -v"`<br>`description = "Run unit tests"`<br><br>`[tasks.test-e2e]`<br>`run = "bats tests/e2e/"`<br>`description = "Run E2E tests via bats"`<br><br>`[tasks.lint]`<br>`run = "uv run ruff check"` |
| `specs/constitution.md` | Governance | Project constitution declaring three-layer Macro/Meso/Micro architecture | `# Project Constitution`<br><br>`Version: 0.2.0`<br><br>`---`<br><br>`## 1. Architectural Principles`<br><br>`- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped.` |
| `src/deviate/cli/__init__.py` | Codebase_File | Typer CLI command tree root registering 22 subcommands | `cli.add_typer(explore_app, name="explore")`<br>`cli.add_typer(research_app, name="research")`<br>`cli.add_typer(prd_app, name="prd")`<br>`cli.add_typer(shard_app, name="shard")`<br>`cli.command(name="specify")(specify)`<br>`cli.command(name="plan")(plan)`<br>`cli.command(name="tasks")(tasks)`<br>`cli.command(name="pr")(pr)`<br>`cli.add_typer(meso_app, name="meso")`<br>`cli.add_typer(macro_app, name="macro")` |
| `src/deviate/cli/constitution.py` | Codebase_File | Reference implementation pattern for an existing Product-adjacent CLI command module | `constitution_app = typer.Typer(no_args_is_help=True)`<br>`console = Console()`<br><br>`def _fail_with(reason: str) -> NoReturn:`<br>`    print(json.dumps({"status": "FAILURE", "reason": reason}))`<br>`    raise typer.Exit(code=1)`<br><br>`def _read_seed(filename: str) -> str \| None:`<br>`    try:`<br>`        seed = importlib.resources.files("deviate.prompts").joinpath(filename)`<br>`        return seed.read_text(encoding="utf-8")` |
| `src/deviate/cli/macro.py` | Codebase_File | Macro-layer orchestration with `_PHASE_ORDER` constant declaring phase routing | `_PHASE_ORDER = ["explore", "research", "prd", "shard"]`<br><br>`if from_phase and from_phase not in _PHASE_ORDER:`<br>`    valid = ", ".join(_PHASE_ORDER)`<br>`...`<br>`start_idx = _PHASE_ORDER.index(from_phase) if from_phase else 0`<br>`phases = _PHASE_ORDER[start_idx:]` |
| `prompts/deviate-constitution/SKILL.md` | Codebase_File | Reference skill frontmatter format for Product-layer-adjacent phase | `---`<br>`name: deviate-constitution`<br>`description: Governance artifact generation — initialize or update specs/constitution.md as an authoritative document defining architectural standards, tech stack constraints, testing mandates, and completion criteria`<br>`category: deviatdd-macro-layer`<br>`version: 1.0.0`<br>`aliases:`<br>`  - constitution`<br>`  - /deviate-constitution`<br>`  - spec:constitution`<br>`  - spec.constitution`<br>`---` |
| `prompts/deviate-explore/SKILL.md` | Codebase_File | Existing macro-layer explore SKILL (frontmatter format reference for new phases) | `name: deviate-explore`<br>`description: Pure exploration only. Deterministic, factual structural scan of the codebase. Allocates a feature bucket, scans the repo, and emits a raw explore.md (what exists, not what to do). NEVER writes, modifies, or generates any implementation code. The research/design phase belongs to the deviate-research skill.`<br>`category: deviatdd-macro-layer`<br>`version: 2.0.0`<br>`aliases:`<br>`  - /deviate-explore`<br>`  - /explore`<br>`  - spec:full:explore` |
| `src/deviate/state/config.py` | Codebase_File | State models including `_VALID_PHASES` frozenset and `DeviateConfig` / `SessionState` Pydantic models | `_VALID_PHASES = frozenset({`<br>`    "IDLE", "EXPLORE", "RESEARCH", "PRD", "SHARD", "SPECIFY", "PLAN", "TASKS",`<br>`    "RED", "GREEN", "YELLOW", "JUDGE", "REFACTOR", "E2E", "EXECUTE", "HOTFIX",`<br>`})`<br><br>`class SessionState(BaseModel):`<br>`    current_phase: str = "IDLE"`<br>`    active_issue_id: Optional[str] = None` |
| `.deviate/config.toml` | Config | Runtime config for the local repo; declares `[agent]`, `[models]`, `graphite`, `use_libref` | `profile = "default"`<br>`timeout_seconds = 300`<br>`agent_export_mode = "local"`<br><br>`graphite = false`<br>`use_context = true`<br>`use_libref = true`<br>`[agent]`<br>`backend = "opencode"`<br><br>`[models]`<br>`default = "opencode-go/deepseek-v4-flash"`<br>`plan = "opencode-go/deepseek-v4-pro"`<br>`tasks = "opencode-go/deepseek-v4-pro"` |
| `specs/_product/` | Directory | Empty product-layer staging directory containing only an empty `flows/` subdirectory | (directory listing: only `.` and `..` and one subdirectory `flows`; no files present) |
| `specs/_product/flows/` | Directory | Empty subdirectory prepared for canonical product flow artifacts; no `index.md` or domain flow files present | (directory listing: only `.` and `..`; no files present) |
| `specs/DeviaTDD-api.md` | Spec | Authoritative CLI/API spec covering command tree, phase workflows, model routing, file structure, HITL gates | (Referenced by subagent as authoritative source-of-truth alongside `specs/DeviaTDD-architecture.md`; existence confirmed via directory listing under `specs/`) |
| `specs/DeviaTDD-architecture.md` | Spec | Authoritative architecture spec covering macro/meso/micro layering, HITL gates, execution phases, E2E boundaries | (Referenced by subagent as authoritative source-of-truth; existence confirmed via directory listing under `specs/`) |
| `tests/conftest.py` | Test | Defines `_git_env()` and `tmp_git_repo` fixture for git isolation in tests | `def _git_env() -> dict[str, str]:`<br>`    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}`<br>`...`<br>`tmp_git_repo(tmp_path)` (fixture creates initialized git repo at temp path with `Test Runner` identity) |
| `src/deviate/core/agent.py` | Codebase_File | AgentBackend abstraction with `HandoverManifest` Pydantic model dispatching to `opencode`/`droid`/`claude` backends | `class HandoverManifest(BaseModel):`<br>`...`<br>(Referenced by subagent; verified presence via file registry) |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | 6 categories: `prompts/deviate-*/SKILL.md` (3 new), `src/deviate/cli/*.py` (3 new Typer modules + 1 register line), `src/deviate/core/*.py` (new pre/post scripts per phase), `src/deviate/state/*.py` (potential new Product-layer state models), `tests/test_cli/*.py` (3 new test modules), `specs/DeviaTDD-api.md` + `specs/DeviaTDD-architecture.md` (spec alignment per AGENTS.md mandate), `specs/constitution.md` (v0.3.0 likely — adds Product-layer principle to Three-Layer Architecture). Approximate count: 12-18 source files + 4 spec/manifest files. |
| New Modules Required | Yes — 3 new CLI Typer sub-apps (`flow_app`, `architecture_app`, `release_app`), 3 new pre/post scripts, optional Product-layer state model. |
| New Persistence / Data Models | Yes — Product-layer state may require new Pydantic models under `src/deviate/state/` (e.g., `ProductLayerState`, `FlowIndex`). New artifacts: `specs/_product/flows.md` (or modular `flows/index.md` + domain files), `specs/_product/architecture.md`, `specs/_product/release-next.md`, `specs/_product/domain-model.md`. |
| New External Integrations | None strictly required; existing `AgentBackend` (`opencode`/`droid`/`claude`) is sufficient. Optional: `libref` for offline docs (already enabled). |
| Upstream / Cross-Cutting Concerns | Yes — adding a new layer above Macro requires updating `_PHASE_ORDER` in `src/deviate/cli/macro.py:747` (currently `["explore", "research", "prd", "shard"]`), `_VALID_PHASES` frozenset in `src/deviate/state/config.py:21-39`, the Typer command tree at `src/deviate/cli/__init__.py:653-677`, and the constitution's `§1 Architectural Principles` (currently hardcodes three layers; would need to become four). `DeviateConfig` may need new optional Product-layer fields. |
| Rationale | The request introduces a structural addition above the existing three-layer architecture declared in `specs/constitution.md:9`. Adding 3 new CLI commands, 3 new SKILL.md prompts, new state models, and new spec artifacts across multiple directories with cross-cutting changes to the phase registry, CLI tree, and constitution version (currently v0.2.0). Multi-module, new persistence, new spec documents — fits the High complexity classification criteria. |

**Classification criteria** (factual only, no recommendation):
- **Low**: Localized change, 1-3 files. No new modules, persistence, or integrations.
- **Medium**: 2-5 files, potentially a new module or simple state. No new persistence layer.
- **High**: Multi-module, new persistence/data models, new external integrations, or cross-cutting concerns.

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | product-layer |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/product-layer.md |
| NEXT_ACTION | Run `/deviate-research` (High complexity) — see `## Scope Sizing` |