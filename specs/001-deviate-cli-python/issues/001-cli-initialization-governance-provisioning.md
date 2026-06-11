---
title: "[FR-001] CLI Initialization & Governance Provisioning"
labels: ["epic:001-deviate-cli-python", "layer:init"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: []
coordinates_with: []
issue_id: "ISS-001-001"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/001-cli-initialization-governance-provisioning.md`
- **Workstation Paths**: 
  - `src/deviate/cli/__init__.py`
  - `src/deviate/main.py`
  - `src/deviate/state/config.py` (DeviateConfig, SessionState models)
  - `src/deviate/prompts/constitution_seed.md`
  - `tests/test_cli/test_init.py`

## [THE_PROBLEM_CONTRACT]
As a developer setting up the DeviaTDD environment, I need the `deviate init` command to scaffold the `.deviate/` directory structure, provision default configuration and session state using strict Pydantic validation, and idempotently update project-level agent governance files, so that the workspace is ready for Macro-layer operations without manual setup.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - `deviate init` Typer subcommand implementation.
  - Pydantic-based state models (`DeviateConfig`, `SessionState`) with `extra="forbid"` validation.
  - Scaffolding of `.deviate/config.toml` and `.deviate/session.json`.
  - Idempotent provisioning of `specs/constitution.md` from tokenized boilerplate.
  - Idempotent append/write mechanics for `CLAUDE.md` and `AGENTS.md` (skip if `## DeviaTDD Orchestration Rules` exists).
- **Defensive Exclusions**: 
  - Execution of Macro, Meso, or Micro layer commands.
  - OS-level file locking (concurrency handled at ledger append level, not config init).
  - Dynamic LLM-driven constitution generation (core logic is offline template resolution).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-001-INIT**: The `deviate init` command scaffolds the `.deviate/` directory structure, provisions default configuration and session state, and idempotently updates project-level agent governance files.
- **AC-001-INIT-01**: Clean repository root executes `deviate init` and creates `.deviate/config.toml` with valid TOML structure matching `DeviateConfig` schema.
- **AC-001-INIT-02**: `specs/constitution.md` is created from the tokenized boilerplate template if it does not exist.
- **AC-001-INIT-03**: If `CLAUDE.md` already contains `## DeviaTDD Orchestration Rules`, the file is not modified, and the CLI outputs an idempotency skip message.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_cli/test_init.py`, `tests/test_state/test_config.py`
- **Integration Tests**: `tests/test_integration/test_init_export_cycle.py`

## [DEMONSTRATION_PATH]
```bash
# Verify CLI initialization, Pydantic validation, and idempotency
pytest tests/test_cli/test_init.py -v
pytest tests/test_state/test_config.py -v
pytest tests/test_integration/test_init_export_cycle.py -v
```