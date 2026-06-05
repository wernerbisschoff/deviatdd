---
title: "[FR-003] Meso-Layer Specification & Task Decomposition"
labels: ["epic:001-deviate-cli-python", "layer:meso"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-002"]
coordinates_with: []
issue_id: "ISS-003"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/003-meso-layer-specification-task-decomposition.md`
- **Workstation Paths**: 
  - `src/deviate/cli/meso.py` (or integrated in `src/deviate/cli/__init__.py`)
  - `src/deviate/state/ledger.py` (TaskRecord model, append logic)
  - `specs/{issue_id}/tasks.jsonl`
  - `tests/test_meso/`

## [THE_PROBLEM_CONTRACT]
As a task engineer, I need the CLI to handle `/specify` and `/tasks` commands, reading the active `IssueRecord` and generating granular, TDD-ready task units appended to the issue-specific task ledger, so that the Micro-layer has deterministic, self-contained execution units.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - `deviate specify` and `deviate tasks` Typer subcommands.
  - `TaskRecord` Pydantic model with strict validation.
  - Reading active `IssueRecord` from `specs/issues.jsonl`.
  - Appending `TaskRecord` entries to `specs/{issue_id}/tasks.jsonl`.
  - Validation of `issue_id` (halting with `INVALID_ISSUE_ID` if not found).
- **Defensive Exclusions**: 
  - Macro-layer feature scoping logic.
  - Micro-layer TDD sandbox execution or Tamper Guard enforcement.
  - OS-level file locking (simple atomic append is sufficient).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-003-MESO**: Handles `/specify` and `/tasks` commands, reading the active `IssueRecord` and generating granular, TDD-ready task units appended to the issue-specific task ledger.
- **AC-003-MESO-01**: Valid `IssueRecord` with status `SHARDED` results in at least one `TaskRecord` with status `PENDING` appended to `specs/{issue_id}/tasks.jsonl`.
- **AC-003-MESO-02**: Invalid `issue_id` provided to `deviate specify` exits with non-zero code and outputs `INVALID_ISSUE_ID`.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_meso/test_specify.py`, `tests/test_meso/test_tasks.py`
- **Integration Tests**: `tests/test_integration/test_meso_task_ledger.py`

## [DEMONSTRATION_PATH]
```bash
# Verify meso-layer specification and task decomposition
pytest tests/test_meso/ -v
pytest tests/test_integration/test_meso_task_ledger.py -v
```