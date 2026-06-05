# Implementation Tasks: feat/001-deviate-cli-python/001-cli-initialization-governance-provisioning

## Phase 1: State Foundation — Package Scaffold & Pydantic Models
**Goal**: Establish the `src/deviate/` package structure with importable state models (`DeviateConfig`, `SessionState`) and their unit tests, so downstream tasks can import and instantiate validated configuration and session objects.

### Tasks

- [x] T001: Package Structure & Pydantic State Models
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_state/test_config.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/__init__.py`
    - `src/deviate/state/__init__.py`
    - `src/deviate/state/config.py`
    - `src/deviate/main.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_state/__init__.py`
    - `tests/test_state/test_config.py`
  - **Rationale**: `src/deviate/__init__.py` and `src/deviate/state/__init__.py` make the package importable. `src/deviate/state/config.py` defines `DeviateConfig` and `SessionState` per the data-model schema (US-002-CONF: schema validation, default values, `extra="forbid"`). `src/deviate/main.py` exposes the Typer app instance for CLI invocation. `src/deviate/cli/__init__.py` creates the Typer sub-app shell (init command wiring added in T003). `tests/test_state/test_config.py` validates model defaults, field constraints, IO round-trips, and edge cases (US-002-CONF scenarios).
  - **Details**:
    - **Implementation**: Create `src/deviate/__init__.py` with `__version__ = "0.1.0"`.
    - **Implementation**: Create `src/deviate/state/__init__.py` (empty, package marker).
    - **Implementation**: Implement `DeviateConfig(BaseModel)` in `state/config.py` with fields: `profile: str = "default"`, `llm_backend: str = "droid"`, `timeout_seconds: int = Field(default=300, gt=0)`, `agent_export_mode: Literal["local", "global"] = "local"`, and `model_config = {"extra": "forbid"}`.
    - **Implementation**: Implement `SessionState(BaseModel)` in `state/config.py` with fields: `current_phase: str = "IDLE"`, `active_issue_id: Optional[str] = None`, `last_command: str = ""`, `timestamp: datetime = Field(default_factory=datetime.utcnow)`, and a `@field_validator("current_phase")` that accepts only the 11 valid DeviaTDD phase names.
    - **Implementation**: Create `src/deviate/main.py` with `import typer; app = typer.Typer()` and register `cli` sub-app via `app.add_typer()`.
    - **Implementation**: Create `src/deviate/cli/__init__.py` with `import typer; cli = typer.Typer()` (shell only; no commands yet).
    - **Implementation**: Write `tests/test_state/test_config.py` covering: `DeviateConfig` default values, `extra="forbid"` rejection, `timeout_seconds > 0` enforcement, `SessionState` default phase and timestamp, phase validator rejection of invalid values, JSON round-trip fidelity.
    - **Edge Cases**: Extra forbidden keys cause `ValidationError`; `timeout_seconds=0` and `-1` are rejected; `current_phase="INVALID"` raises `ValueError` listing valid phases; `None` serializes/deserializes correctly for `active_issue_id`.
    - **Acceptance**: `pytest tests/test_state/test_config.py -v` exits 0. All model instances are importable from `src.deviate.state.config`.

- [x] T002: Prompt Seed Resources
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `python -c "from deviate.prompts import governance; print(governance.__file__)"`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/__init__.py`
    - `src/deviate/prompts/constitution_seed.md`
    - `src/deviate/prompts/governance/__init__.py`
    - `src/deviate/prompts/governance/claudemd_seed.md`
    - `src/deviate/prompts/governance/agents_seed.md`
  - **Rationale**: `constitution_seed.md` provides the tokenized boilerplate for `specs/constitution.md` provisioning (US-003-CONS). `claudemd_seed.md` and `agents_seed.md` supply authoritative `## DeviaTDD Orchestration Rules` content for idempotent append/overwrite into `CLAUDE.md` and `AGENTS.md` respectively (US-004-GOV). `__init__.py` files ensure `importlib.resources` can locate the package data. These are static content files with no runtime logic — IMMEDIATE mode is appropriate.
  - **Details**:
    - **Implementation**: Create `src/deviate/prompts/__init__.py` (empty, package marker).
    - **Implementation**: Create `src/deviate/prompts/constitution_seed.md` with the full constitution boilerplate containing `${PROJECT_NAME}`, `${REPO_ROOT}` tokenized placeholders. Must include `[CONSTITUTION_VERSION]`, `[1_ARCHITECTURAL_PRINCIPLES]`, `[2_TECH_STACK_STANDARDS]`, `[3_TESTING_PROTOCOLS]`, `[4_DEVELOPMENT_WORKFLOW]` sections.
    - **Implementation**: Create `src/deviate/prompts/governance/__init__.py` (empty).
    - **Implementation**: Create `src/deviate/prompts/governance/claudemd_seed.md` with `## DeviaTDD Orchestration Rules` as the primary H2, containing the three-layer architecture summary, append-only ledger protocol, git isolation, tamper guard, HITL gates, model tiering, and `mise run` task reference table.
    - **Implementation**: Create `src/deviate/prompts/governance/agents_seed.md` with matching `## DeviaTDD Orchestration Rules` content adapted for AGENTS.md format.
    - **Edge Cases**: Both governance seed files MUST contain the exact header `## DeviaTDD Orchestration Rules` (the idempotency guard in T003 scans for this exact string). Template file encoding must be UTF-8.
    - **Acceptance**: Files are importable via `importlib.resources.files("deviate.prompts")`. Content is valid Markdown. Governance seeds contain `## DeviaTDD Orchestration Rules` header.

## Phase 2: Init Command — Core Feature Implementation
**Goal**: Implement the `deviate init` Typer subcommand with full idempotency, partial recovery, configuration scaffolding, constitution provisioning, and governance file management. This is the primary feature logic; tested via TDD.

### Tasks

- [\] T003: Init Subcommand — Scaffolding, Governance & Idempotency
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_init.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T001, T002
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_cli/__init__.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: `src/deviate/cli/__init__.py` receives the `init` command definition and all business logic (US-001-SCAF: directory + file scaffolding; US-003-CONS: constitution provisioning; US-004-GOV: governance file append/overwrite; US-005-RECOV: partial recovery). `tests/test_cli/test_init.py` tests every spec scenario via `CliRunner` isolated invocations against temp directories. All init behavior shares one logical capability per the workstation mandate.
  - **Details**:
    - **Red**: Write `test_init_creates_dotfile_structure` asserting `.deviate/config.toml` and `.deviate/session.json` exist after `deviate init` on clean dir.
    - **Red**: Write `test_init_creates_constitution` asserting `specs/constitution.md` exists and contains resolved `${VARIABLE}` placeholders (US-003-CONS).
    - **Red**: Write `test_init_appends_governance_to_nonexistent_file` asserting `CLAUDE.md` is created with `## DeviaTDD Orchestration Rules` block when file is absent (US-004-GOV).
    - **Red**: Write `test_init_overwrites_governance_block_when_exists` asserting only the `## DeviaTDD Orchestration Rules` section is replaced when the block already exists; surrounding content preserved (US-004-GOV).
    - **Red**: Write `test_init_skip_existing_dotfiles` asserting `.deviate/config.toml` is NOT overwritten and skip message emitted when it already exists (US-001-SCAF idempotency).
    - **Red**: Write `test_init_recover_partial_scaffold` asserting `.deviate/session.json` is created when `config.toml` exists but `session.json` is missing (US-005-RECOV).
    - **Green**: Implement `@cli.command() def init(agent_export_mode, generate_constitution)` in `cli/__init__.py`:
      - Create `.deviate/` directory with `os.makedirs(exist_ok=True)`.
      - Write `config.toml` via `DeviateConfig().model_dump()` serialized with `tomllib`/`tomli_w` only if file missing.
      - Write `session.json` via `SessionState().model_dump_json(indent=2)` only if file missing.
      - Read `constitution_seed.md` via `importlib.resources`, resolve `${VARIABLE}` placeholders with regex, write to `specs/constitution.md` only if file missing.
      - Implement `_upsert_governance_block(target_path, seed_content)` helper: if file missing → create it with seed content; if file exists and contains `## DeviaTDD Orchestration Rules` → replace that section in-place; if file exists without the section → append seed content at end.
      - Wire `--agent-export-mode` (choices: local/global, default: local).
      - Wire `--generate-constitution` flag (default: False).
    - **Refactor**: Extract helper functions `_ensure_dir`, `_write_if_missing`, `_upsert_governance_block` for readability. Ensure Rich `console.print()` for idempotency skip messages.
    - **Edge Cases**: Handle `permission denied` gracefully with clear error; gracefully handle empty existing `CLAUDE.md` (treat as absent); handle `specs/` directory already existing but without `constitution.md`; handle trailing whitespace/newlines in governance block boundary detection.
    - **Acceptance**: `pytest tests/test_cli/test_init.py -v` passes all 6 test cases. Running `deviate init` twice on same directory produces no file changes on second run and exits 0.

## Phase 3: Integration & Performance Gates
**Goal**: Verify the full `deviate init` cycle end-to-end and validate performance constraints (`L_max <= 500ms`).

### Tasks

- [ ] T004: Integration Validation & Performance Compliance
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_init_export_cycle.py -v`
  - **Estimated Time**: 30 minutes
  - **Dependency**: T003
  - **Files**:
    - `tests/test_integration/__init__.py`
    - `tests/test_integration/test_init_export_cycle.py`
  - **Rationale**: Integration tests verify the aggregate behavior of all components together (US-006-PERF: wall-clock timing within 500ms, structural validity of all output files). IMMEDIATE mode is appropriate because integration tests validate existing behavior rather than driving new implementation.
  - **Details**:
    - **Implementation**: Create `tests/test_integration/__init__.py` (empty, package marker).
    - **Implementation**: Write `test_full_init_cycle_completes` that runs `deviate init` via `CliRunner` on a temp directory, asserts all 6 output files exist (`.deviate/config.toml`, `.deviate/session.json`, `specs/constitution.md`, `CLAUDE.md`, `AGENTS.md`, `.deviate/prompts.log`), and validates each file's structure.
    - **Implementation**: Write `test_init_performance_under_500ms` that times `deviate init` execution on a clean directory and asserts `elapsed < 0.5` seconds.
    - **Implementation**: Write `test_init_idempotent_performance` that runs init twice on the same directory and asserts second run does not exceed 500ms.
    - **Implementation**: Write `test_init_export_files_not_created_when_existing` that verifies `deviate init` on a pre-scaffolded directory exits zero without overwriting existing valid config.
    - **Edge Cases**: Performance test should skip the `--generate-constitution` flag (LLM calls excluded from timing). Use `time.perf_counter()` for precise wall-clock measurement.
    - **Acceptance**: `pytest tests/test_integration/test_init_export_cycle.py -v` exits 0. All performance gates pass.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (T001 → T002): Foundation models and prompt resources, parallelizable since T002 has no code dependencies.
2. Phase 2 (T003): Init subcommand implementation; depends on both T001 and T002.
3. Phase 3 (T004): Integration validation; depends on T003.

**Critical Dependency Chains**:
- T001 (state models) must precede T003 (init command imports models)
- T002 (prompt seeds) must precede T003 (init command reads seeds via importlib.resources)
- T003 (init command) must precede T004 (integration tests invoke init)
- T001 and T002 are independent and can proceed in parallel

**Risk Hotspots**:
- `src/deviate/cli/__init__.py` is touched by T001 (skeleton) and T003 (full init logic). T003 extends the file created by T001; merge conflict is unlikely if T001 creates only the Typer instance and T003 adds the `init` command definition after it.
- Governance block in-place replacement in `_upsert_governance_block` is string-manipulation-heavy; test edge cases thoroughly (especially boundary detection between sections).

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` — T001 (skeleton: `cli = typer.Typer()`) and T003 (command: `@cli.command()` decorator and function below). No other tasks touch this file.
- `tests/test_state/test_config.py` — T001 only.
- `tests/test_cli/test_init.py` — T003 only.
- `tests/test_integration/test_init_export_cycle.py` — T004 only.