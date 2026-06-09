<!-- MANAGED_BY: tools:init -->

## ⚙️ Project Execution Contract (MANDATORY)

- **Repository Type**: single-language (Python)
- **Execution Mode**: TDD (Red-Green-Refactor via deviate cycle)
- **Performance Constraints**: L_max <= 500ms for init, L_max <= 200ms per agent export

## 🧠 State & Authority Model (MANDATORY)

- Primary State Tracker: `git` commits
- Project Constitution: `specs/constitution.md`
- Core Strategy Ledger: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/plan.md`

## ⚡ Fast-Lane Execution Contract

- Use `mise run <task>` for all task execution
- Deterministic tooling via `.mise.toml`
- Git hooks under `.githooks/`

## 🛠️ Mise Tasks as Execution API

| Task | Purpose |
|------|---------|
| `mise run test` | Run unit tests |
| `mise run test-e2e` | Run E2E tests via bats |
| `mise run lint` | Lint Python |
| `mise run lint-fix` | Apply lint fixes |
| `mise run format` | Format Python |
| `mise run format-check` | Check formatting |
| `mise run check-types` | Type check |
| `mise run fix` | Format + lint fix |
| `mise run check` | All validation checks |
| `mise run setup` | Install deps + hooks |
| `mise run clean` | Remove artifacts |
| `mise run help` | List tasks |

## 🔐 Git Commit Authority (MANDATORY)

- Commit after each verified successful verification loop
- Never use `--no-verify`
- Preserve all semantic anchors

## 🧪 Test Git Isolation (MANDATORY)

Never run git commands against the real repo during tests. Every git
operation in tests MUST target a `tmp_path`-based isolated repo.

- Use the `tmp_git_repo` fixture (created by T002 in `tests/conftest.py`)
- Every `git` subprocess call MUST include `cwd=<tmp_git_repo>` — the `cwd`
  flag is the ONLY thing scoping the command to the temp repo
- Never use `Path.cwd()`, `os.getcwd()`, or the real repo root in tests
- Verify test isolation: `git config user.name` inside the fixture should
  show `Test Runner`, never the real user's name

See `spec.md` §`TEST_ISOLATION_CONSTRAINTS` and `tasks.md` §`Universal
Test Constraints` for full rules.

## DeviaTDD Phase Architecture

### Macro Layer — Feature Scoping
- `/explore` → **DeepSeek V4 Flash**: Fast scan of codebase structure, dependencies, and patterns. Outputs `explore.md` (what exists, not what to do).
- `/research` → **Qwen3.7-Plus [Thinking Mode]**: Consumes `explore.md`, performs architectural analysis. Outputs `design.md` (trade-offs, decisions) and `data-model.md` (schemas, relationships).
- `/prd` → **Qwen3.7-Plus [Thinking Mode]**: Translates `design.md` into immutable user requirements and acceptance criteria in `prd.md`.
- `/shard` → **Qwen3.7-Plus [Thinking Mode]**: Breaks PRD into ~5 independent vertical-slice issues (3-10 bounds). Each issue is end-to-end testable.

### Meso Layer — Issue Engineering
- `/specify` → **DeepSeek V4 Pro**: Converts issue data into functional contract `spec.md` (business boundaries, edge cases — no implementation).
- **[HITL Gate 2]**: Human reviews `spec.md` before task decomposition proceeds.
- `/tasks` → **DeepSeek V4 Pro** (same continuous thread as /specify for prefix cache): Decomposes `spec.md` into ~5 TDD-cycle tasks with implementation hints (3-10 bounds). Merged former `/plan` role. Appends terminal `type: "e2e"` task.

### Micro Layer — TDD Sandbox
- **RED** → **DeepSeek V4 Flash**: Write failing test; verified to fail due to missing implementation.
- **GREEN** → **DeepSeek V4 Flash**: Write production code to pass test; tamper guard reverts unauthorized test edits.
- **YELLOW** → **DeepSeek V4 Flash** (conditional): If RED test is flawed, propose amendment for isolated judge approval/rejection.
- **JUDGE** → **DeepSeek V4 Pro**: Isolated compliance gate evaluates `git diff` against `spec.md` for security and structural violations.
- **REFACTOR** → **DeepSeek V4 Flash**: Polish implementation; regression gate re-runs tests, rolls back on failure.

### Fast-Path
- `/adhoc` → **Qwen3.7-Plus [Thinking Mode]**: Compresses Explore + Research + PRD + Shard for low/medium complexity tasks via complexity gate.

### HITL Gates
- **Gate 1**: After `/research`, before `/prd` — human approves design and data model.
- **Gate 2**: After `/specify`, before `/tasks` — human approves functional contract.
- **Gate 3**: After all tasks complete — human approves merge.

### Model Routing Rationale
- **Explorers (low-cost ingestion)**: `/explore`, RED/GREEN/REFACTOR → V4 Flash for high-volume reading and code generation.
- **Architects (premium strategic logic)**: `/research`, `/prd`, `/shard`, `/adhoc` → Qwen3.7-Plus [Thinking Mode] for abstract reasoning and constraint satisfaction.
- **Translators (cached engineering)**: `/specify` + `/tasks` → V4 Pro in single continuous thread for 90%+ prefix cache discount.
- **Compliance gate**: JUDGE → V4 Pro for isolated security and drift verification.

## Python-Only Architecture

All deviate operations are Python-based. Skills live as package resources under
`src/deviate/prompts/skills/<name>/SKILL.md` and are invoked via the `deviate`
CLI (`deviate <subcommand>`) instead of shell scripts. No `.sh` files exist in
the `prompts/` directory. The `mise.toml` file defines all task execution via
`uv run` — no shell script tasks.

## Skill Resolution

When a skill file references `<SKILL_DIR>/<script>.sh`, resolve `<SKILL_DIR>` to
`src/deviate/prompts/skills/<name>/` and use `deviate <subcommand>` instead.

## Prompt Edit Discipline

All skill and prompt template edits MUST target `src/deviate/prompts/`.
The `~/.config/opencode/skills/` directory is a read-only install mirror;
edits there are overwritten on reinstall. Always edit the source tree and commit
through the deviate system.

## Technical Execution Context
Tasks=Environment Preflight Passed: YES, AST Inventory Synchronized: YES, Data Model Artifact Created: YES, Traceability Validation Confirmed: YES, Total Execution Phases: 8, Primary Technical Milestone: Scaffold the deviate CLI package with package-backed prompt initialization, local/global configurable agent exports, automated CLAUDE.md/AGENTS.md workspace governance patching, constitution boilerplate bootstrap, optional LLM-driven constitution generation, offline context synchronization, and TOML serialization hooks., Execution Mode: TDD (Red-Green-Refactor via deviate cycle), Performance Constraints: L_max <= 500ms for init, L_max <= 200ms per agent export, Core Strategy Ledger: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/plan.md`, Data Model Definitions: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/data-model.md`, Diagnostic Explorer Record: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/research.md`, Specification Source: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/spec.md`, Project Constitution: `specs/constitution.md`, **Goal**: Create the `src/deviate/` Python package structure with all `__init__.py` stubs, model components, and the static `src/deviate/prompts/` resource vault directory., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/`, **Impacted File Nodes**:, `src/deviate/__init__.py` — Package initialization marker, `src/deviate/prompts/explore.md` — Base template for /explore directive, `src/deviate/prompts/prd.md` — Base template for /prd directive, `src/deviate/prompts/specify.md` — Base template for /specify directive, `src/deviate/prompts/plan.md` — Base template for /plan directive, `src/deviate/main.py` — Runtime bootstrap entry point exposing the Typer app, `src/deviate/cli/__init__.py` — CLI command tree root (Typer instance), `src/deviate/state/__init__.py` — State module initializer, `src/deviate/state/session.py` — Session state entity with Pydantic validation, `src/deviate/state/config.py` — Configuration entity with Pydantic validation, **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_scaffolds_src_package -v`, **Goal**: Implement resource streaming layer to read seed prompts directly from the installation package path rather than relying on dynamic string literals or external path parameters., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Integrate `importlib.resources.files("deviate.prompts")` layer., **Verification Command**: `pytest tests/test_cli/test_init.py::test_resource_vault_binding -v`, **Goal**: Implement `deviate init` command that creates `.deviate/` directory structure with config.toml, session.json, and prompts.log., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `init` subcommand with directory scaffolding logic, `src/deviate/state/session.py` — Session state creation for initial state, `src/deviate/state/config.py` — Config entity for default profile (with `to_toml_string`), **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_creates_dotfile_structure -v`, **Goal**: Implement template mapping execution loops tracking `ExportMode`. `local` routes to `{repo_root}/.claude/commands/`, whereas `global` maps directly out to `$HOME/.claude/commands/`., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Agent variant flag and export routing logic, `.claude/commands/` — Claude agent command directory target (local workspace), `.factory/commands/` — Droid agent command directory target (local workspace), **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_handles_agent_export_mappings -v`, **Performance Gate**: L_max <= 200ms per agent platform export, **Goal**: Implement idempotent append/write mechanics within `deviate init` targeting project-level agent guidelines., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add filesystem write/append tracking logic for project root documentation indicators, `src/deviate/prompts/governance/claudemd_seed.md` — Authoritative text block for agent behavior, **Idempotency Guarantee**: If a section matching `## DeviaTDD Orchestration Rules` already exists in `CLAUDE.md`, skip write, **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_manages_agent_instruction_ledgers -v`, **Goal**: Drop a tokenized `specs/constitution.md` from `src/deviate/prompts/constitution_seed.md` during `deviate init`. Offline mode resolves `${VARIABLE}` placeholders via regex-based project file scanning (L_max <= 50ms). Optional `--generate-constitution` flag invokes LLM runner for deeper analysis., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `--generate-constitution` flag and LLM runner invocation logic, `src/deviate/prompts/constitution_seed.md` — Tokenized boilerplate constitution template with `${VARIABLE}` placeholders, `src/deviate/state/config.py` — `ConstitutionConfig` model with `LLMBackend` enum and `timeout_seconds`, **Tokenized Placeholder Mapping**:, **Idempotency Guarantee**: If `specs/constitution.md` already exists, skip write, **LLM Backend Selection**: Read from `.deviate/config.toml` or environment variable; defaults to `droid`, **Performance Gate**: Offline resolution completes in L_max <= 50ms, **Verification Commands**:, `pytest tests/test_cli/test_init.py::test_init_provisions_constitution_boilerplate -v`, `pytest tests/test_cli/test_init.py::test_init_generate_constitution_flag -v`, **Goal**: Implement offline deterministic context resolution with zero network overhead., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py` and `src/deviate/state/context.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `context` subcommand, `src/deviate/state/context.py` — `ConstitutionContext` model with `resolve_paths()` method, **Execution Steps** (all local, zero network):, **Verification Command**: `pytest tests/test_cli/test_context.py -v`, **Goal**: Implement Pydantic-based type-safe validation for `DeviaTDDSessionState` and `DeviateConfig` entities; verify IO cycles., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/state/session.py` and `src/deviate/state/config.py`, **Impacted File Nodes**:, `src/deviate/state/session.py` — Session state with field validators, `src/deviate/state/config.py` — Config state with field validators, **Verification Commands**:, `pytest tests/test_state/test_session.py::test_session_state_schema_validation -v`, `pytest tests/test_state/test_session.py::test_session_io_cycles -v`, `pytest tests/test_state/test_config.py::test_config_schema_validation -v`, **Goal**: Verify full init + agent export cycle completes within performance constraints., **Execution Mode**: Integration, **Primary Workstation**: `tests/test_integration/test_init_export_cycle.py`, **Verification Command**: `pytest tests/test_integration/test_init_export_cycle.py -v`, **Performance Gate**: L_max <= 500ms for init command, **Target Boundary Alignment**: Verified. Out-of-scope criteria (human-facing spec directories, branch management, REPL engines, test generation during init) are blocked via strict code boundaries in PHASE_001 through PHASE_005., **Sandbox Routing Match**: 100% correlation across unit and integration testing checkpoints., **Named File Entity Coverage**: All named file entities from spec.md are covered:, `config.toml` → PHASE_003, `session.json` → PHASE_003, `prompts.log` → PHASE_003, `prompts/` → PHASE_003, `CLAUDE.md` → PHASE_005, `specs/constitution.md` → PHASE_006, `AGENTS.md` → PHASE_007, `src/deviate/__init__.py` → PHASE_001, `src/deviate/main.py` → PHASE_001, `src/deviate/cli/__init__.py` → PHASE_001, PHASE_002, PHASE_003, PHASE_004, PHASE_005, PHASE_006, PHASE_007, `src/deviate/state/session.py` → PHASE_001, PHASE_008
