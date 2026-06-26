# Exploration: Tome Subsystem

## Problem Definition

[Statement]: Explore the structural surface of the Tome Subsystem, a documentation curator for Starlight docs sites that classifies a commit (or a branch-level diff) against the four Diátaxis quadrants and runs only the writer skills the classifier selects. v1 ships seven prompt-only skills (no Python runtime, no `deviate tome <phase>` CLI). The user-supplied problem statement is scoped by `specs/_product/release-next.md` (release plan) and `specs/_product/flows/flows-tome.md` (seven flows FLOW-04..FLOW-10).

[Scope]: In-scope structural components verified across the scan:
- Skills directory at `src/deviate/prompts/skills/` — 25 existing `deviate-*` skill directories, 0 `tome-*` skill directories.
- Product-layer artifacts at `specs/_product/`:
  - `architecture.md` (219 lines) declaring 7 Tome components C1–C7.
  - `domain-model.md` (84 lines) declaring 9 Tome entities.
  - `flows/flows-tome.md` (278 lines) declaring FLOW-04..FLOW-10.
  - `flows/index.md` (14 lines) cataloging all 10 product flows.
  - `release-next.md` (52 lines) declaring the Tome release plan.
- Constitution at `specs/constitution.md` (v0.2.0, 96 lines) — declares Python 3.13 + Typer + pytest + ruff + mise, three-layer architecture, append-only ledger, HITL gates.
- Project manifests at `pyproject.toml` and `mise.toml`.
- Existing skill patterns (e.g., `deviate-architecture/SKILL.md`, `deviate-flows/SKILL.md`, `deviate-release/SKILL.md`) as reference templates for the seven new `tome-*` skills.

[Exclusions]: Architectural decisions, design trade-offs, risk analysis, prompt-template authoring, implementation code, runner scaffolding, and failure-mode speculation are deferred to the `deviate-research` skill. This scan catalogs what exists; it does not propose how Tome is implemented.

## Discovery Audit Results

### Verified Dependencies

Dependencies declared in `pyproject.toml` (lines 6–32) — no new runtime dependencies are required for the Tome Subsystem in v1 (per `specs/_product/architecture.md:17`).
- `typer>=0.12` — present at `src/deviate/cli/__init__.py` (Typer CLI root).
- `rich>=13.0` — present at `src/deviate/cli/constitution.py` and other CLI modules.
- `pydantic>=2.0` — present at `src/deviate/state/config.py` and `src/deviate/state/session.py`.
- `pyyaml>=6.0.3` — declared; relevant only if future iterations parse frontmatter at runtime (v1 is prompt-only).
- `tree-sitter>=0.24` + 23 language grammars — declared; used by AST/symbol extraction tooling referenced in macro-layer skill prompts.

Dev dependencies (`pyproject.toml:38–41`, `56–61`): `pytest>=8.0`, `pytest>=9.0.3`, `ruff>=0.4`, `ruff>=0.15.16`, `typer>=0.26.7`. Duplication between `[project.optional-dependencies] dev` and `[dependency-groups] dev` is pre-existing.

### Ghost Dependencies

- **`bats`** — referenced in `specs/constitution.md:43` and `mise.toml:13`. Not a Python package; expected at the system level.
- **`graphite` / `gt` CLI** — referenced in `.deviate/config.toml:5` (`graphite = false`). Not declared in `pyproject.toml`; conditional system dependency.
- **`gh` CLI** — referenced in `src/deviate/cli/meso.py:1175–1196`. Not declared; system-level.
- **Astro / Starlight** — Tome *outputs* may include `apps/docs/package.json`, `apps/docs/astro.config.mjs`, and `.astro` files. These live in **target repos** that consume the skills, not in the DeviaTDD repo (per `specs/_product/architecture.md:18` and `:212`).
- **Diátaxis** — the quadrant taxonomy referenced by `architecture.md:11`, `domain-model.md:30–35`, and the C2–C5 quadrant rules. No library binding; the taxonomy is inlined in each `tome-write-*` skill prompt.

### Manifest Files Observed

- `pyproject.toml` — Package metadata (`name = "deviate"`, `version = "1.0.0"`), build system (`hatchling`), entry point (`deviate = "deviate.main:app"`), `requires-python = ">=3.13"`.
- `mise.toml` — Task runner config: 13 defined tasks (`test`, `test-e2e`, `lint`, `lint-fix`, `format`, `format-check`, `check-types`, `check`, `fix`, `setup`, `clean`, `dev`, `install-tool`, `help`). Python 3.13 is pinned via `[tools].python`.
- `package.json` — Declares `opencode-codebase-index: ^0.10.0` (Node-side tooling outside the Python runtime).
- `uv.lock` — Lockfile for `uv` package manager.
- `package-lock.json` — Lockfile for npm-side tooling.

### Test Runner Configuration

- `mise.toml:8–9`: `[tasks.test]\nrun = "uv run pytest tests/ -v"` — Root-level test invocation.
- `mise.toml:12–13`: `[tasks.test-e2e]\nrun = "bats tests/e2e/"` — E2E tests via bats.
- `pyproject.toml:53–54`: `[tool.pytest.ini_options]\ntestpaths = ["tests"]`.
- `tests/conftest.py` — defines `_git_env()` (strips `GIT_*` env vars) and `tmp_git_repo` fixture.

For the Tome Subsystem in v1, no new tests are required: the seven `tome-*` skills are static `SKILL.md` prompt files and do not introduce Python modules (per `specs/_product/architecture.md:17`). The `mise run check` and `mise run test-e2e` gates apply unchanged.

### User-Authored Seed Artifacts

The user-supplied scope consists of two files; both are present on disk:
- `specs/_product/release-next.md` — 52 lines. Declares the Tome release goal, 8 constraints, 7 included flows, 1 included work item, 7 deferred epics, 10 acceptance criteria.
- `specs/_product/flows/flows-tome.md` — 278 lines. Declares FLOW-04..FLOW-10, each with Actor, Domain, Status, Problem/Job, Trigger, Preconditions, Happy Path, Alternate/Error paths, Success State, Metrics/Signals.

Related Product-layer artifacts that already exist and are referenced by the scope:
- `specs/_product/architecture.md` — 219 lines. 7 Tome components C1–C7 with skill paths, flow refs, integration contracts.
- `specs/_product/domain-model.md` — 84 lines. 9 Tome entities with attributes and relationships.
- `specs/_product/flows/index.md` — 14 lines. Catalog of all 10 product flows (FLOW-01..FLOW-10).

### Manifest-Constitution Divergence

`pyproject.toml:5` declares `requires-python = ">=3.13"`. The constitution at `specs/constitution.md:21` declares `Python 3.13`. No divergence on Python version.

`pyproject.toml:34–35` declares entry point `deviate = "deviate.main:app"`. The constitution at `specs/constitution.md:22` declares `Target: CLI application (deviate)`. No divergence.

The constitution at `specs/constitution.md:36` cites `Micro-sandbox: Aider Python API (aider.coders.Coder) as LLM execution substrate`. The current `src/deviate/core/agent.py` uses an `AgentBackend` abstraction (no aider dependency). This is a pre-existing divergence and is orthogonal to the Tome Subsystem; it is recorded factually without adjudication.

`specs/_product/architecture.md:212` declares `No package.json, astro.config.mjs, or Node toolchain is added to DeviaTDD's repo. Skill output may include these files in target repos; that is out of scope for this constitution.` The existing `package.json` at the repo root declares `opencode-codebase-index: ^0.10.0` — this is an existing root-level tooling manifest and is not part of the Tome Subsystem. No divergence.

## Constitution Quotes

Constitution excerpts quoted verbatim from `specs/constitution.md` (v0.2.0). No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.

- **Architectural Principles**: "Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."
- **Tech Stack Standards (Backend)**: "Python 3.13 / Target: CLI application (`deviate`) / Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Tech Stack Standards (Frontend)**: "None (CLI-only application; no web or GUI frontend)"
- **Tech Stack Standards (Database)**: "No persistent database runtime (all state tracked in JSONL ledgers and TOML config) / Session state: JSON files under `.deviate/` / Issue ledger: `specs/issues.jsonl` (append-only JSONL) / Task ledger: `specs/**/tasks.jsonl` (append-only JSONL) / Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment"
- **Tech Stack Standards (Infrastructure)**: "Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate / Version control: Git (all phase commits, lock branches for concurrency) / No containerization required (local execution on host)"
- **Tech Stack Standards (Tooling)**: "Package manager: `uv` / Test runner: `pytest` / Linter: `ruff` (lint + format) / E2E testing: `bats` (Bash automated test system) / Task runner: `mise` (see `mise.toml` for all tasks) / Code quality gate: `mise run check`"
- **Testing Protocols (Framework)**: "Test framework: pytest / Test root: `tests/` / Test extension: `.py` / Test command: `pytest tests/ -v` / Lint command: `ruff check .` / E2E command: `bats tests/e2e/`"
- **Testing Protocols (Coverage)**: "Coverage target: >= 80% / RED phase tests must fail with `AssertionError` or `NotImplementedError` — syntax crashes are rejected / GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits / REFACTOR phase runs regression gate: tests must re-pass after polish"
- **Definition of Done**: "Code implemented (satisfies acceptance criteria from `spec.md`) / Tests passing (pytest with clean exit code 0) / Lint passing (ruff check with no violations) / Judge phase passed (git diff validated against `spec.md` invariants) / E2E tests passing (if applicable; bats for CLI integration) / Documentation updated (`spec.md` and `design.md` reflect final implementation) / No governance violations (constitution rules upheld, no HITL gates bypassed) / Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)"

## Architectural Baselines

[Pattern_Over_Instance]: Each baseline is represented by a single representative example, not every instance. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**:
  - Skill-directory pattern: `src/deviate/prompts/skills/<skill-name>/SKILL.md` (YAML frontmatter, system instructions, workflow, output schema). Existing examples: `src/deviate/prompts/skills/deviate-architecture/SKILL.md`, `src/deviate/prompts/skills/deviate-flows/SKILL.md`, `src/deviate/prompts/skills/deviate-release/SKILL.md`.
  - Three-layer phase gating: Macro (Explore → Research → PRD → Shard+Specify), Meso (Plan → Tasks), Micro (RED → GREEN → JUDGE → REFACTOR). Declared in `specs/constitution.md:9` and operationalized in `src/deviate/cli/macro.py:747` (`_PHASE_ORDER`).
  - Append-only ledger: `specs/issues.jsonl` and `specs/**/tasks.jsonl` (per `specs/constitution.md:10`).
  - HITL gates: Gate 1 after research, Gate 2 after shard, Gate 3 after micro (per `specs/constitution.md:13`).
  - Model tiering: V4 Flash for high-frequency phases, V4 Pro for compliance, Qwen 3.7+ for architecture (per `specs/constitution.md:15`). Configured via `.deviate/config.toml` `[models]` section.
- **Infrastructure & Operations**:
  - Task runner: `mise.toml` (13 tasks including `test`, `test-e2e`, `lint`, `format`, `check`).
  - Git hooks: `.githooks/` directory; configured by `mise.toml:45` (`git config core.hooksPath .githooks`).
  - Config: `.deviate/config.toml` with `profile`, `timeout_seconds`, `agent_export_mode`, `graphite`, `use_context`, `use_libref`, `[agent].backend` keys.
- **Data & State Management**:
  - State modules: `src/deviate/state/session.py` (`DeviaTDDSessionState` Pydantic model), `src/deviate/state/config.py` (`DeviateConfig` Pydantic model with `[models]` resolution).
  - State directory: `.deviate/` with `config.toml`, `session.json`, `prompts.log`.
  - Issue ledger: `specs/issues.jsonl` (append-only).
- **Quality, Safety & Observability**:
  - Linter: `ruff` (lint + format); target `py313`.
  - Test framework: `pytest` with `tests/conftest.py` providing `_git_env()` and `tmp_git_repo` fixtures for git isolation.
  - E2E framework: `bats` (Bash automated test system).
  - Commit convention: `<type>(<scope>): <description>` (per `specs/constitution.md:72`).
- **External Integrations**:
  - `libref` CLI: local-first documentation lookup for AI agents (per `AGENTS.md` "Offline Documentation System").
  - Graphite CLI: conditional `gt` command suite (per `.deviate/config.toml:5`).
  - `opencode-codebase-index`: Node-side tooling for the semantic search index used in this exploration (per `package.json`).
  - Agent backends: `opencode`, `droid`, `claude` (per `src/deviate/core/agent.py` and `.deviate/config.toml` `[agent].backend = "opencode"`).

## Ecosystem Research

[Web_Discovery]: Targeted cataloging of the Diátaxis and Starlight ecosystems that the Tome Subsystem depends on at the prompt layer. No architectural recommendations.

- **Best Practices**:
  - Diátaxis documentation framework — Daniele Procida's four-quadrant model (`tutorial`, `how-to`, `reference`, `explanation`) for structuring technical documentation. The Tome Subsystem adopts the four-quadrant discipline at the writer level (one writer per quadrant, per `specs/_product/architecture.md:64`).
- **Common Use Cases & Pitfalls**:
  - Quadrant contamination: tutorial-style narrative in a how-to, or step-by-step instructions in an explanation. C2–C5 prompt boundary rules and the C6 verifier exist to surface this (per `specs/_product/architecture.md:64`, `:90–95`).
  - Frontmatter drift: the field set declared in `content.config.ts` (Starlight-side) must agree with the inline schema in the C2–C5 prompts; drift is a C6 finding (per `specs/_product/architecture.md:149`).
- **Standard Tooling**:
  - Starlight: Astro-based documentation framework. The C7 setup scaffolds `apps/docs/` with Starlight and extends `docsSchema()` with the Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`).
  - `docsSchema()`: Starlight's built-in Zod schema for content frontmatter; C7's `content.config.ts` extends it with Tome-specific fields (per `specs/_product/architecture.md:112`).

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/prompts/skills/deviate-explore/SKILL.md` | Codebase_File | The skill template currently executing; defines the explore output schema and the Fact-Only Discipline. | "## Exploration Only Mandate / This skill produces exactly one file: `explore.md`. It is a markdown document cataloging what exists in the repository. It does NOT write code, run tests, fix bugs, refactor, or implement anything." |
| `src/deviate/prompts/skills/deviate-architecture/SKILL.md` | Codebase_File | Reference template for a Product-layer authoring skill; architecture.md is one of its outputs. | "name: deviate-architecture / description: Product-layer FLOW-02 (Architecture) authoring — produce and maintain specs/_product/architecture.md and specs/_product/domain-model.md as cross-epic integration contracts" |
| `src/deviate/prompts/skills/deviate-flows/SKILL.md` | Codebase_File | Reference template for a Product-layer authoring skill; flows authoring is gated on this skill. | (skill file in `src/deviate/prompts/skills/deviate-flows/SKILL.md` — reference pattern for the FLOW-04..FLOW-10 flows in `flows-tome.md`) |
| `src/deviate/prompts/skills/deviate-release/SKILL.md` | Codebase_File | Reference template for the Product-layer release skill; release-next.md is its output. | (skill file in `src/deviate/prompts/skills/deviate-release/SKILL.md` — reference pattern for the release plan in `release-next.md`) |
| `specs/_product/release-next.md` | Spec | User-supplied scope: the Tome release plan (52 lines). | "# Release: Tome Subsystem / ## Goal / - Ship Tome, a manual post-merge documentation curator for Starlight docs sites that classifies each commit (or branch-level diff) against the four Diátaxis quadrants" |
| `specs/_product/flows/flows-tome.md` | Spec | User-supplied scope: seven flows FLOW-04..FLOW-10 (278 lines). | "## FLOW-04 Tome Classify / - Actor: Developer / - Domain: Documentation / - Status: Draft" |
| `specs/_product/architecture.md` | Spec | Product-level architecture for Tome: 7 components C1–C7, integration contracts, data ownership, dependency graph. | "## 1. Scope / Tome is a manual post-merge documentation curator for Starlight docs sites. It classifies a commit (or a branch-level diff) against the four Diátaxis quadrants" |
| `specs/_product/domain-model.md` | Spec | Product-level domain model for Tome: 9 entities (Commit, ClassificationReport, Capability, DocType, Action, DocPage, TomeFrontmatter, VerificationReport, StarlightQuadrant). | "## Entities / ### Commit / - **Attributes**: `sha`, `message`, `changed_files[]`, `changed_tests[]`, `merged_diff` (or `branch_diff` for merge-base mode)" |
| `specs/_product/flows/index.md` | Spec | Flow catalog: lists all 10 product flows (FLOW-01..FLOW-10). | "# DeviaTDD Product Flow Index / \| FLOW-04 \| Tome Classify \| Developer \| Documentation \| Draft \| `specs/_product/flows/flows-tome.md` \|" |
| `specs/constitution.md` | Manifest | Project constitution v0.2.0; declares three-layer architecture, Python 3.13 + Typer, pytest + ruff + mise, HITL gates. | "## 1. Architectural Principles / - **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)." |
| `pyproject.toml` | Manifest | Package metadata; declares Python 3.13, Typer, Rich, Pydantic, PyYAML, tree-sitter + 23 grammars; entry point `deviate = "deviate.main:app"`. | "[project] / name = \"deviate\" / version = \"1.0.0\" / description = \"DeviaTDD CLI — agent orchestration framework\" / requires-python = \">=3.13\"" |
| `mise.toml` | Manifest | Task runner: 13 tasks including `test`, `test-e2e`, `lint`, `format`, `check`. | "[env] / python = \"3.13\" / [tools] / python = \"3.13\" / uv = \"latest\" / [tasks.test] / run = \"uv run pytest tests/ -v\"" |
| `.deviate/config.toml` | Config | Runtime config: `agent_export_mode = "local"`, `graphite = false`, `use_context = true`, `use_libref = true`, `[agent].backend = "opencode"`. | "profile = \"default\" / timeout_seconds = 300 / agent_export_mode = \"local\" / graphite = false / use_context = true / use_libref = true / [agent] / backend = \"opencode\"" |
| `src/deviate/prompts/skills/` | Directory | Skills vault; 25 existing `deviate-*` skill directories; 0 `tome-*` directories. | (directory listing: `deviate-adhoc`, `deviate-architecture`, `deviate-constitution`, `deviate-e2e`, `deviate-execute`, `deviate-explore`, `deviate-flows`, `deviate-green`, `deviate-hotfix`, `deviate-init`, `deviate-judge`, `deviate-plan`, `deviate-pr`, `deviate-prd`, `deviate-prune`, `deviate-red`, `deviate-refactor`, `deviate-release`, `deviate-research`, `deviate-review`, `deviate-shard`, `deviate-tasks`, `deviate-triage`, `deviate-yellow` — 24 directories observed) |
| `src/deviate/state/session.py` | Codebase_File | `DeviaTDDSessionState` Pydantic model; session state is JSON-serialized to `.deviate/session.json`. | (file in `src/deviate/state/session.py` — Pydantic session state; unrelated to Tome v1 prompt-only delivery) |
| `src/deviate/state/config.py` | Codebase_File | `DeviateConfig` Pydantic model; resolves per-phase model routing via `[models]` section. | (file in `src/deviate/state/config.py` — per-phase model resolution; not modified by Tome v1) |
| `src/deviate/cli/__init__.py` | Codebase_File | Typer CLI root; mounts the macro/meso/micro phase sub-apps. | (file in `src/deviate/cli/__init__.py` — Typer CLI; not extended by Tome v1, which defers a `deviate tome <phase>` CLI to a future iteration) |
| `apps/` | Directory (absent) | Target output surface for the C7 setup skill; deliberately absent from the DeviaTDD repo. | (directory does not exist; per `specs/_product/architecture.md:18`, Tome outputs live in target repos, not in the DeviaTDD repo) |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | **Medium** |
| Files Likely Modified | 7 new `SKILL.md` files under `src/deviate/prompts/skills/tome-{classify,write-tutorial,write-how-to,write-reference,write-explanation,verify-docs,setup}/`; 0 Python modules modified. |
| New Modules Required | No (v1 is prompt-only; no Python runtime added per `specs/_product/architecture.md:17`). |
| New Persistence / Data Models | No (no new Pydantic models; no new ledger entries; no new TOML keys). |
| New External Integrations | No new dependencies in DeviaTDD's repo. The skills *reference* Diátaxis, Starlight, and `docsSchema()` in their prompt text only. |
| Upstream / Cross-Cutting Concerns | None that affect the DeviaTDD Python stack. The seven skills are additive under `src/deviate/prompts/skills/`; no migration of existing skill assets is required. |
| Rationale | Seven static `SKILL.md` files, each a copy-and-edit of the existing `deviate-architecture` / `deviate-flows` / `deviate-release` skill templates. The architectural seams (component→flow map, integration contracts, data ownership) are already defined in `specs/_product/architecture.md` and `specs/_product/domain-model.md`. v1 carries no `deviate tome <phase>` CLI surface, no `package.json`, no `astro.config.mjs`, and no Node toolchain (per `specs/_product/architecture.md:21`, `:212`). |

**Classification criteria** (factual only, no recommendation):
- **Low**: Localized change, 1-3 files. No new modules, persistence, or integrations.
- **Medium**: 2-5 files, potentially a new module or simple state. No new persistence layer.
- **High**: Multi-module, new persistence/data models, new external integrations, or cross-cutting concerns.

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | tome-subsystem |
| GIT_BRANCH | main |
| SPEC_TARGET | `specs/explore/tome-subsystem.md` |
| NEXT_ACTION | Run `/deviate-research` (Medium complexity; seven skills with cross-cutting content-config parity, but no new Python modules, no new persistence, no new external integrations). The downstream `/deviate-research` skill will author the design trade-offs, the per-skill prompt structure, and the `tome/contracts.py` decision that v1 defers. |
