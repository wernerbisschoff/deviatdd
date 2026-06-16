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

## 🧪 Git Isolation (MANDATORY — Tests AND Production Code)

All git operations — in both tests and production code — MUST target the
correct repository and MUST NOT mutate the worktree's branch state.

### Test Git Isolation

- Use the `tmp_git_repo` fixture (created by T002 in `tests/conftest.py`)
- Every `git` subprocess call MUST include BOTH `cwd=<tmp_git_repo>` and
  `env=_git_env()` — `cwd` targets the temp repo, `env=_git_env()` strips
  `GIT_*` env vars that could leak from the parent process
- Import `_git_env` from `tests.conftest` (not redefined locally)
- Never use `Path.cwd()`, `os.getcwd()`, or the real repo root in tests
- Verify test isolation: `git config user.name` inside the fixture should
  show `Test Runner`, never the real user's name

### Production Code Git Isolation

- CLI commands that run `git checkout -b` (or any branch-switching command)
  MUST save the current branch and restore it after the operation
- Always use `_git_env()` (strips `GIT_*` env vars) for all `git` subprocess
  calls — prevents inheriting parent repo's git configuration
- Prefer creating branch refs (`git branch`) over checking out branches
  (`git checkout -b`) in non-interactive commands
- If a command must switch branches, use the pattern:
  1. Save `git rev-parse --abbrev-ref HEAD` before
  2. Execute the branch switch
  3. Restore original branch afterwards

Agents running TDD cycles MUST NOT execute CLI commands that mutate git
branch state (e.g., `feature create`, `git checkout -b`). These operations
will switch the worktree off its intended branch and break the TDD cycle.

See `spec.md` §`TEST_ISOLATION_CONSTRAINTS` and `tasks.md` §`Universal
Test Constraints` for full rules.

## ⚡ Test Performance (MANDATORY)

Never call `_run_pytest()` (in `src/deviate/cli/micro.py`) in tests.
Tests that invoke CLI commands which internally call `_run_pytest` (red post,
green post, refactor post) MUST mock `deviate.cli.micro._run_pytest` with an
appropriate `subprocess.CompletedProcess` return value.

Performance target: full suite < 18s. If adding a test via `runner.invoke(cli,
["red", "post"])` and it calls `_run_pytest`, the test will trigger ALL pytest
tests as a subprocess (~5s per invocation). Always mock it.

Example:
```python
@patch("deviate.cli.micro._run_pytest")
def test_something(self, mock_pytest, tmp_git_repo):
    mock_pytest.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="1 passed", stderr=""
    )
```

For refactor_post tests that call `_run_pytest` twice, use `side_effect`:
```python
mock_pytest.side_effect = [
    subprocess.CompletedProcess(args=[], returncode=0, stdout="1 passed", stderr=""),
    subprocess.CompletedProcess(args=[], returncode=0, stdout="1 passed", stderr=""),
]
```

## Spec Alignment (MANDATORY)

- `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` are the authoritative
  source-of-truth documents for the DeviaTDD architecture. Any change to CLI commands,
  phase workflows, model routing, file structure, or HITL gates MUST be reflected in
  both documents.
- When adding, removing, or renaming a CLI command, skill, or phase, update both spec
  files in the same commit.
- When the ADHOC-003 restructured workflow changes (Shard+Specify merged, Plan phase,
  Gate 2 repositioned), keep these docs in sync with the actual implementation.

## DeviaTDD Phase Architecture

### Macro Layer — Feature Scoping
- `/explore` → **DeepSeek V4 Flash**: Fast scan of codebase structure, dependencies, and patterns. Outputs `explore.md` (what exists, not what to do).
- `/research` → **Qwen3.7-Plus [Thinking Mode]**: Consumes `explore.md`, performs architectural analysis. Outputs `design.md` (trade-offs, decisions) and `data-model.md` (schemas, relationships).
- `/prd` → **Qwen3.7-Plus [Thinking Mode]**: Translates `design.md` into immutable user requirements and acceptance criteria in `prd.md`.
- `/shard` → **Qwen3.7-Plus [Thinking Mode]**: Breaks PRD into spec-enriched issue files with Gherkin AC, user stories, and edge cases (merged with Specify). Target ~5 issues (3-10 bounds).

### Meso Layer — Issue Engineering
- **[HITL Gate 2]**: Human reviews spec-enriched shard issues before planning proceeds.
- `/plan` → **DeepSeek V4 Pro** (planned): Per-issue localized research — scans current codebase, analyzes prior issue implementations, produces `plan.md` with implementation strategy.
- `/tasks` → **DeepSeek V4 Pro**: Decomposes spec-enriched issue + `plan.md` into ~5 TDD-cycle tasks with implementation hints (3-10 bounds). Appends terminal `type: "e2e"` task.
- `/review` → **DeepSeek V4 Flash**: Lightweight PR/merge scan at HITL Gate 3 — checks ledger integrity, cross-task consistency, and security surface. Chat-based output, no report file.
- `/specify` → **Deprecated** (merged into shard). Legacy skill redirects to new workflow.

### Micro Layer — TDD Sandbox
- **RED** → **DeepSeek V4 Flash**: Write failing test; verified to fail due to missing implementation.
- **GREEN** → **DeepSeek V4 Flash**: Write production code to pass test; TamperGuard reverts unauthorized test edits. If tampering detected, session transitions to YELLOW.
- **YELLOW** → **DeepSeek V4 Pro** (conditional, TamperGuard-triggered): Propose amendment for isolated judge approval/rejection. NOT in `_PHASE_MAP` — conditional branch between GREEN and JUDGE.
- **JUDGE** → **DeepSeek V4 Pro**: Isolated compliance gate evaluates `git diff` against `spec.md` and security rubrics (secrets, injection, path traversal, auth gaps). On violation: `git revert` (never `git reset --hard`), persist `RollbackSnapshot`, inject `<judge_feedback>`, route back to GREEN.
- **REFACTOR** → **DeepSeek V4 Flash**: Polish implementation; regression gate re-runs tests, rolls back on failure.

### Fast-Path
- `/adhoc` → **Qwen3.7-Plus [Thinking Mode]**: Compresses Explore + Research + PRD + Shard for low/medium complexity tasks via `ComplexityGate`. Produces spec-enriched issues directly.

### HITL Gates
- **Gate 1**: After `/research`, before `/prd` — human approves design and data model.
- **Gate 2**: After `/shard`, before `/plan` — human reviews spec-enriched issue files.
- **Gate 3**: After all tasks complete — human approves merge.

### Model Routing Rationale
- **Explorers (low-cost ingestion)**: `/explore`, RED/GREEN/REFACTOR → V4 Flash for high-volume reading and code generation.
- **Architects (premium strategic logic)**: `/research`, `/prd`, `/shard`, `/adhoc` → Qwen3.7-Plus [Thinking Mode] for abstract reasoning and constraint satisfaction.
- **Translators (cached engineering)**: `/plan` + `/tasks` → V4 Pro in single continuous thread per issue for 90%+ prefix cache discount.
- **Compliance gates**: YELLOW, JUDGE → V4 Pro for isolated compliance + security verification (injection, secrets, path traversal).

## Python-Only Architecture

All deviate operations are Python-based. Skills live as package resources under
`src/deviate/prompts/skills/<name>/SKILL.md` and are invoked via the `deviate`
CLI (`deviate <subcommand>`) instead of shell scripts. No `.sh` files exist in
the `prompts/` directory. The `mise.toml` file defines all task execution via
`uv run` — no shell script tasks.

## Skill Resolution

When a skill file references `<SKILL_DIR>/<script>.sh`, resolve `<SKILL_DIR>` to
`src/deviate/prompts/skills/<name>/` and use `deviate <subcommand>` instead.

## 📚 Context-Aware Documentation (MANDATORY)

The `context` CLI (`~/.local/share/mise/installs/node/24.14.0/bin/context`) is a local-first documentation
MCP server for AI agents. It provides offline-queryable API docs for all project dependencies.
**Always prefer `context query <lib> <topic>` over web fetching** — results are local, instant, and
token-cheap.

### Installed Packages

| Package | Sections | Coverage |
|---------|----------|----------|
| `python@3.13` | 5,047 | stdlib + library reference |
| `typer@0.12` | 302 | CLI framework |
| `rich@13.8` | 170 | terminal formatting |
| `pytest@9.0` | 952 | test framework |
| `pydantic@2.13.4` | 508 | data validation |

### Query Usage

```
context query <library@version> "<topic>"
```

Examples:
```
context query python@3.13 "subprocess run"
context query typer@0.12 "create command"
context query rich@13.8 "console print"
context query pytest@9.0 "fixture scope"
context query pydantic@2.13.4 "BaseModel field types"
```

### Documentation Refresh

When a dependency version changes, update its docs:
```
context add <git-repo-url> --name <lib> --path docs --tag <semver>
```

See `/Users/werner/Development/tools/context/` for the tool source.

## Prompt Edit Discipline

All skill and prompt template edits MUST target `src/deviate/prompts/`.
The `~/.config/opencode/skills/` directory is a read-only install mirror;
edits there are overwritten on reinstall. Always edit the source tree and commit
through the deviate system.

## Technical Execution Context
Tasks=Environment Preflight Passed: YES, AST Inventory Synchronized: YES, Data Model Artifact Created: YES, Traceability Validation Confirmed: YES, Total Execution Phases: 8, Primary Technical Milestone: Scaffold the deviate CLI package with package-backed prompt initialization, local/global configurable agent exports, automated CLAUDE.md/AGENTS.md workspace governance patching, constitution boilerplate bootstrap, optional LLM-driven constitution generation, offline context synchronization, and TOML serialization hooks., Execution Mode: TDD (Red-Green-Refactor via deviate cycle), Performance Constraints: L_max <= 500ms for init, L_max <= 200ms per agent export, Core Strategy Ledger: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/plan.md`, Data Model Definitions: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/data-model.md`, Diagnostic Explorer Record: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/research.md`, Specification Source: `specs/001-deviate-cli-bootstrapping/000-project-bootstrap/spec.md`, Project Constitution: `specs/constitution.md`, **Goal**: Create the `src/deviate/` Python package structure with all `__init__.py` stubs, model components, and the static `src/deviate/prompts/` resource vault directory., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/`, **Impacted File Nodes**:, `src/deviate/__init__.py` — Package initialization marker, `src/deviate/prompts/explore.md` — Base template for /explore directive, `src/deviate/prompts/prd.md` — Base template for /prd directive, `src/deviate/prompts/specify.md` — Base template for /specify directive, `src/deviate/prompts/plan.md` — Base template for /plan directive, `src/deviate/main.py` — Runtime bootstrap entry point exposing the Typer app, `src/deviate/cli/__init__.py` — CLI command tree root (Typer instance), `src/deviate/state/__init__.py` — State module initializer, `src/deviate/state/session.py` — Session state entity with Pydantic validation, `src/deviate/state/config.py` — Configuration entity with Pydantic validation, **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_scaffolds_src_package -v`, **Goal**: Implement resource streaming layer to read seed prompts directly from the installation package path rather than relying on dynamic string literals or external path parameters., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Integrate `importlib.resources.files("deviate.prompts")` layer., **Verification Command**: `pytest tests/test_cli/test_init.py::test_resource_vault_binding -v`, **Goal**: Implement `deviate init` command that creates `.deviate/` directory structure with config.toml, session.json, and prompts.log., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `init` subcommand with directory scaffolding logic, `src/deviate/state/session.py` — Session state creation for initial state, `src/deviate/state/config.py` — Config entity for default profile (with `to_toml_string`), **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_creates_dotfile_structure -v`, **Goal**: Implement template mapping execution loops tracking `ExportMode`. `local` routes to `{repo_root}/.claude/commands/`, whereas `global` maps directly out to `$HOME/.claude/commands/`., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Agent variant flag and export routing logic, `.claude/commands/` — Claude agent command directory target (local workspace), `.factory/commands/` — Droid agent command directory target (local workspace), **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_handles_agent_export_mappings -v`, **Performance Gate**: L_max <= 200ms per agent platform export, **Goal**: Implement idempotent append/write mechanics within `deviate init` targeting project-level agent guidelines., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add filesystem write/append tracking logic for project root documentation indicators, `src/deviate/prompts/governance/claudemd_seed.md` — Authoritative text block for agent behavior, **Idempotency Guarantee**: If a section matching `## DeviaTDD Orchestration Rules` already exists in `CLAUDE.md`, skip write, **Verification Command**: `pytest tests/test_cli/test_init.py::test_init_manages_agent_instruction_ledgers -v`, **Goal**: Drop a tokenized `specs/constitution.md` from `src/deviate/prompts/constitution_seed.md` during `deviate init`. Offline mode resolves `${VARIABLE}` placeholders via regex-based project file scanning (L_max <= 50ms). Optional `--generate-constitution` flag invokes LLM runner for deeper analysis., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `--generate-constitution` flag and LLM runner invocation logic, `src/deviate/prompts/constitution_seed.md` — Tokenized boilerplate constitution template with `${VARIABLE}` placeholders, `src/deviate/state/config.py` — `ConstitutionConfig` model with `LLMBackend` enum and `timeout_seconds`, **Tokenized Placeholder Mapping**:, **Idempotency Guarantee**: If `specs/constitution.md` already exists, skip write, **LLM Backend Selection**: Read from `.deviate/config.toml` or environment variable; defaults to `droid`, **Performance Gate**: Offline resolution completes in L_max <= 50ms, **Verification Commands**:, `pytest tests/test_cli/test_init.py::test_init_provisions_constitution_boilerplate -v`, `pytest tests/test_cli/test_init.py::test_init_generate_constitution_flag -v`, **Goal**: Implement offline deterministic context resolution with zero network overhead., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/cli/__init__.py` and `src/deviate/state/context.py`, **Impacted File Nodes**:, `src/deviate/cli/__init__.py` — Add `context` subcommand, `src/deviate/state/context.py` — `ConstitutionContext` model with `resolve_paths()` method, **Execution Steps** (all local, zero network):, **Verification Command**: `pytest tests/test_cli/test_context.py -v`, **Goal**: Implement Pydantic-based type-safe validation for `DeviaTDDSessionState` and `DeviateConfig` entities; verify IO cycles., **Execution Mode**: TDD, **Primary Workstation**: `src/deviate/state/session.py` and `src/deviate/state/config.py`, **Impacted File Nodes**:, `src/deviate/state/session.py` — Session state with field validators, `src/deviate/state/config.py` — Config state with field validators, **Verification Commands**:, `pytest tests/test_state/test_session.py::test_session_state_schema_validation -v`, `pytest tests/test_state/test_session.py::test_session_io_cycles -v`, `pytest tests/test_state/test_config.py::test_config_schema_validation -v`, **Goal**: Verify full init + agent export cycle completes within performance constraints., **Execution Mode**: Integration, **Primary Workstation**: `tests/test_integration/test_init_export_cycle.py`, **Verification Command**: `pytest tests/test_integration/test_init_export_cycle.py -v`, **Performance Gate**: L_max <= 500ms for init command, **Target Boundary Alignment**: Verified. Out-of-scope criteria (human-facing spec directories, branch management, REPL engines, test generation during init) are blocked via strict code boundaries in PHASE_001 through PHASE_005., **Sandbox Routing Match**: 100% correlation across unit and integration testing checkpoints., **Named File Entity Coverage**: All named file entities from spec.md are covered:, `config.toml` → PHASE_003, `session.json` → PHASE_003, `prompts.log` → PHASE_003, `prompts/` → PHASE_003, `CLAUDE.md` → PHASE_005, `specs/constitution.md` → PHASE_006, `AGENTS.md` → PHASE_007, `src/deviate/__init__.py` → PHASE_001, `src/deviate/main.py` → PHASE_001, `src/deviate/cli/__init__.py` → PHASE_001, PHASE_002, PHASE_003, PHASE_004, PHASE_005, PHASE_006, PHASE_007, `src/deviate/state/session.py` → PHASE_001, PHASE_008

