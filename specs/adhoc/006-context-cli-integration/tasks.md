# Implementation Tasks: `feat/adhoc/006-context-cli-integration`

## Phase 1: Config Model & Binary Detection
**Goal**: Backend plumbing — add `use_context` boolean to `DeviateConfig`, detect `context` binary on `$PATH` during `deviate init`, and persist the value in `.deviate/config.toml`.

### Tasks

- TSK-006-01: Add `use_context` field and wire `shutil.which("context")` into `deviate init`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_config.py::test_config_use_context_default tests/test_state/test_config.py::test_config_use_context_round_trip tests/test_cli/test_init.py::test_init_detects_context tests/test_cli/test_init.py::test_init_missing_context -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_state/test_config.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: Config model field (`use_context: bool`) is the data foundation. CLI detection (`shutil.which("context")`) is the consumer that populates it. Tested together because the field has no consumer without detection, and detection has no effect without the field. Covers US-ADH-006-01, AC-ADH-006-01, AC-ADH-006-02.
  - **Details**:
    - **Red**: Write `test_config_use_context_default` asserting `DeviateConfig().use_context is False`. Write `test_config_use_context_round_trip` asserting `use_context=True` survives `model_dump()` → `model_validate()`. Write `test_init_detects_context` mocking `shutil.which("context")` to return a `Path`, then asserting `.deviate/config.toml` contains `use_context = true`. Write `test_init_missing_context` mocking `shutil.which("context")` to return `None`, then asserting `use_context = false`.
    - **Green**: Add `use_context: bool = Field(default=False)` to `DeviateConfig` class. In `init()`, after `_scaffold_dotfiles()`, call `shutil.which("context")`. If truthy, re-read config from `.deviate/config.toml`, set `use_context=True`, re-serialize and write. The `_serialize_value()` function already handles `bool` → TOML lowercase.
    - **Refactor**: Ensure `init()` flow is readable — extract the `which` check into a named private helper `_detect_context() -> bool` for testability and clarity.
    - **Edge Cases**: `shutil.which` returns `None` when binary not found — config stays at `False` default. `config.toml` already exists (second init run) — `_write_if_missing` skips, but the `init()` function's post-detection write uses direct file write (not `_write_if_missing`), so the field is always set correctly.
    - **Acceptance**: `DeviateConfig()` returns `use_context = False`. Serializing and deserializing preserves `True`. Running `deviate init` with context on `$PATH` writes `use_context = true` to config. Running `deviate init` without context on `$PATH` writes `use_context = false`.

---

## Phase 2: Context Mandate in Governance Seeds
**Goal**: `CLAUDE.md` and `AGENTS.md` governance blocks instruct ALL agents to use `context query` as primary documentation source, with `context list` for discovery and `context add` for registration.

### Tasks

- TSK-006-02: Append `## Offline Context Documentation System` section to claudemd_seed.md and agents_seed.md
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_context_governance_block -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/governance/claudemd_seed.md`
    - `src/deviate/prompts/governance/agents_seed.md`
    - `tests/test_cli/test_init.py`
  - **Rationale**: Governance seeds are the authoritative source for CLAUDE.md/AGENTS.md content. Both seed files need the same context mandate section. The associated test validates that `deviate init` emits the section in both files. Covers US-ADH-006-02, AC-ADH-006-03.
  - **Details**:
    - **Implementation**: Append a new `## Offline Context Documentation System` section to both `claudemd_seed.md` and `agents_seed.md`. The section must contain:
      - Mandate that ALL agents MUST use `context query <library> <topic>` as primary documentation lookup mechanism
      - Instruction to run `context list` first to discover available documentation packages
      - Instruction to run `context add <source>` when documentation for a library is missing
      - Example block showing `context query python@3.13 "subprocess run"` syntax
      - Note that web fetch is last resort only when `context` is unavailable
    - **Refactor**: Verify `_upsert_governance_block()` handles `## Offline Context Documentation System` header for idempotency (the existing regex pattern searches for `## DeviaTDD Orchestration Rules` — the new section is appended separately, not part of the orchestration rules block, so the existing replace logic is unaffected).
    - **Acceptance**: After `deviate init`, CLAUDE.md contains `## Offline Context Documentation System` with `context query`, `context list`, and `context add` references. AGENTS.md contains the identical section.

---

## Phase 3: Context Mandate in Core Prompts
**Goal**: Every phase prompt includes a universal offline documentation lookup preference — `core.md` (loaded by ALL phases) and the three layer skill files (macro-skill.md, meso-skill.md, micro-skill.md).

### Tasks

- TSK-006-03: Add offline documentation section to core.md and context consultation bullets to layer skill files
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `python3 -c "p='src/deviate/prompts/core/core.md';assert open(p).read().count('### Offline Documentation Lookup')==1" && for f in macro-skill.md meso-skill.md micro-skill.md; do python3 -c "p=f'src/deviate/prompts/core/$f';c=open(p).read();assert 'context query' in c"; done`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/core/core.md`
    - `src/deviate/prompts/core/macro-skill.md`
    - `src/deviate/prompts/core/meso-skill.md`
    - `src/deviate/prompts/core/micro-skill.md`
  - **Rationale**: `core.md` is loaded by `assembly.py:assemble_prompt()` and injected into every phase prompt — adding the context mandate here ensures ALL agents see it. Layer skill files (macro/meso/micro) are loaded by all phases in their respective layers — adding context consultation guidance ensures agents at every layer prefer local docs. Covers US-ADH-006-06, AC-ADH-006-04, AC-ADH-006-05.
  - **Details**:
    - **Implementation**: In `core.md`, add a `### Offline Documentation Lookup` subsection before `## KV Cache Preservation` with 3-4 bullet points requiring agents to prefer `context query <library> <topic>` over web fetching. In `macro-skill.md`, add bullet point 8 under `## Shared Macro Disciplines`: "`context` Documentation: Use `context query <library> <topic>` for library-specific decisions during macro phases. Call `context list` to discover available packages. Web fetch is last resort." In `meso-skill.md`, add bullet point 8 under `## Shared Meso Disciplines`. In `micro-skill.md`, add bullet point 7 under `## Shared Micro Disciplines`.
    - **Acceptance**: `core.md` contains `### Offline Documentation Lookup` section. Each layer skill file has a context documentation bullet under shared disciplines.

---

## Phase 4: Skill-Level Context Integration
**Goal**: Individual skill prompts (`explore`, `adhoc`, `research`, `plan`) reference `context add` or `context query` in their execution sequences so that agents register documentation sources and query local docs during their respective phases.

### Tasks

- TSK-006-04: Add `context add` / `context query` instructions to deviate-explore, deviate-adhoc, deviate-research, and deviate-plan skills
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `for f in deviate-explore/SKILL.md deviate-adhoc/SKILL.md deviate-research/SKILL.md deviate-plan/SKILL.md; do python3 -c "p=f'src/deviate/prompts/skills/$f';c=open(p).read();assert 'context' in c"; done`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-explore/SKILL.md`
    - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
    - `src/deviate/prompts/skills/deviate-research/SKILL.md`
    - `src/deviate/prompts/skills/deviate-plan/SKILL.md`
  - **Rationale**: Each skill prompt defines the execution sequence its phase agent follows. Adding `context` commands at the right insertion points ensures agents register documentation during discovery phases (explore/adhoc) and query documentation during reasoning/planning phases (research/plan). Covers US-ADH-006-03, US-ADH-006-04, US-ADH-006-05, AC-ADH-006-04, AC-ADH-006-05, AC-ADH-006-06.
  - **Details**:
    - **Implementation — explore**: In the `ecosystem researcher` subagent prompt (`<subagent_ecosystem_prompt>`), add a step before web search instructions to run `context add <source>` for detected dependency libraries (e.g., `context add <git-repo-url> --name <lib> --path docs --tag <semver>`). Add a note to run `context list` first to check what's already installed.
    - **Implementation — adhoc**: In step 3 (`Lightweight Discovery Pass`), add a sub-step after file discovery to run `context add <source>` for libraries detected during the scan. Add a note that this makes documentation available for downstream phases.
    - **Implementation — research**: In invariant 3 (`Token Efficiency & Context Primacy Rule`), add `context query <library> <topic>` as the preferred documentation lookup mechanism before web search. Add a discovery step to run `context list` to see available packages.
    - **Implementation — plan**: In step 3 (`Current Codebase State Scan`), add a sub-step (g) to query `context` for framework conventions and library APIs detected in workstation files. For example, if a file uses Pydantic, run `context query pydantic@2.13.4 "field types"`.
    - **Acceptance**: Each skill file references `context` CLI commands at the appropriate step in its execution sequence.

---

## Phase 5: End-to-End Verification
**Goal**: Verify the full init → config → governance chain works end-to-end with mocked context binary.

### Tasks

- TSK-006-05: End-to-end init cycle with context detection, governance block, and full test suite
  - **Type**: Integration
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_init_export_cycle.py -v && mise run check`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `tests/test_integration/test_init_export_cycle.py`
  - **Rationale**: Integration test validates that the full `deviate init` pipeline works end-to-end — config creation, context binary detection, governance block rendering, and skills installation. This is the terminal validation gate that proves all 4 prior phases compose correctly.
  - **Details**:
    - **Implementation**: Add an integration test (`test_init_context_detection`) that:
      1. Creates a temp directory with a mock `context` binary in a `bin/` subdir
      2. Patches `$PATH` to include `bin/`
      3. Runs `runner.invoke(cli, ["init"])`
      4. Asserts `.deviate/config.toml` contains `use_context = true`
      5. Asserts CLAUDE.md contains `## Offline Context Documentation System`
      6. Asserts AGENTS.md contains `## Offline Context Documentation System`
    - **Edge Cases**: Also add a negative test (`test_init_context_not_installed`) that verifies `use_context = false` and no context section in governance when `context` is absent.
    - **Acceptance**: Full init pipeline passes with `context` detected. Config contains `use_context = true`. Governance blocks contain context mandate. Full test suite green.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-006-01) — Config model + CLI detection (backend foundation)
2. Phase 2 (TSK-006-02) — Governance seeds (CLAUDE.md / AGENTS.md content)
3. Phase 3 (TSK-006-03) — Core prompts (universal mandate)
4. Phase 4 (TSK-006-04) — Skill prompts (per-phase references)
5. Phase 5 (TSK-006-05) — E2E verification (composition test)

**Critical Dependency Chains**:
- TSK-006-02 depends on TSK-006-01 (governance block test needs init with context detection working)
- TSK-006-03 and TSK-006-04 are independent of Phase 1 and 2 (static markdown, no logic coupling)
- TSK-006-05 depends on TSK-006-01 and TSK-006-02 (integration test exercises both)

**Risk Hotspots**:
- Governance seed section must not break `_upsert_governance_block()` regex — the new `## Offline Context Documentation System` section is appended after the existing `## DeviaTDD Orchestration Rules` block. The existing `_upsert_governance_block()` only replaces content under `## DeviaTDD Orchestration Rules` — it does NOT touch any other `##` headers. Verify this by reading `_upsert_governance_block()`: it uses `re.compile(r"^## DeviaTDD Orchestration Rules.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)` which anchors to that exact header — the new section won't interfere.
- Skill prompt edits must preserve all existing `<step>` IDs and instruction blocks — only add new steps or amend existing ones.

**Merge Conflict Boundaries**:
- Files touched by multiple tasks: none (each file is touched by exactly one task)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
