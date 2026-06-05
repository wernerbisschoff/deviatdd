---
title: "[FR-002] Macro-Layer State & Ledger Management"
labels: ["epic:001-deviate-cli-python", "layer:macro"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-001"]
coordinates_with: []
issue_id: "ISS-002"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/002-macro-layer-state-ledger-management.md`
- **Workstation Paths**: 
  - `src/deviate/cli/macro.py` (or integrated in `src/deviate/cli/__init__.py`)
  - `src/deviate/state/ledger.py` (IssueRecord model, append logic)
  - `specs/issues.jsonl`
  - `tests/test_macro/`

## [THE_PROBLEM_CONTRACT]
As a feature architect, I need the CLI to orchestrate the `/explore`, `/research`, `/prd`, and `/shard` commands, managing session state transitions and appending to the global issue ledger, so that feature scoping is systematically tracked and downstream agents receive deterministic context packets.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - `deviate explore`, `research`, `prd`, `shard` Typer subcommands.
  - Session state transitions (`IDLE` ➔ `EXPLORE` ➔ `RESEARCH` ➔ `PRD` ➔ `SHARD` ➔ `IDLE`).
  - `IssueRecord` Pydantic model with strict validation.
  - Appending `IssueRecord` to `specs/issues.jsonl` with valid UUID4 `id` and status `SHARDED`.
  - Validation of upstream artifacts (e.g., halting with `EXPLORE_MISSING` if `explore.md` is absent).
- **Defensive Exclusions**: 
  - Task-level decomposition (`/specify`, `/tasks`).
  - Actual code generation or test execution (Micro-layer responsibilities).
  - OS-level file locking (simple atomic append is sufficient per project constraints).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-002-MACRO**: Orchestrates the `/explore`, `/research`, `/prd`, and `/shard` commands, managing session state transitions and appending to the global issue ledger.
- **AC-002-MACRO-01**: Valid `specs/constitution.md` and empty `specs/issues.jsonl` results in a new `IssueRecord` with status `SHARDED` appended to `specs/issues.jsonl`.
- **AC-002-MACRO-02**: Missing `specs/001-deviate-cli-python/explore.md` during `deviate prd` exits with non-zero code and outputs `EXPLORE_MISSING`.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_macro/test_explore.py`, `tests/test_macro/test_prd.py`, `tests/test_macro/test_shard.py`
- **Integration Tests**: `tests/test_integration/test_macro_ledger_append.py`

## [DEMONSTRATION_PATH]
```bash
# Verify macro-layer commands and ledger management
pytest tests/test_macro/ -v
pytest tests/test_integration/test_macro_ledger_append.py -v
```