## Summary

Implements the DeviaTDD meso layer — `deviate specify` and `deviate tasks` commands — bridging the gap between high-level issue sharding and micro-level TDD execution. The specify command converts JSON issue contracts into functional specs with Gherkin acceptance criteria; the tasks command decomposes those specs into ordered, actionable TDD task units. Both commands are backed by a shared ledger model and follow the same CLI patterns established by the macro layer.

## Changes

### Ledger infrastructure (`src/deviate/state/ledger.py`)
- Added `TaskRecord` model (Pydantic) for task decomposition records in the issues ledger
- Implemented `append_task_record()` and `resolve_issue_record()` for ledger append/lookup
- Refactored existing inline ledger scanning into a shared `_read_ledger()` helper to eliminate duplication
- Enhanced `SessionState.phase_transition()` to support branching meso-to-micro transitions

### Specify command (`src/deviate/cli/meso.py` + `tests/test_meso/test_specify.py`)
- New `deviate specify <issue_id>` command that reads a JSON issue contract from the ledger
- Transpiles the contract into a `spec.md` file with Gherkin `Scenario:` blocks
- Includes idempotency guard: skips if spec.md already exists
- 136-line RED-phase acceptance test suite covering nominal and edge cases

### Tasks command (`src/deviate/cli/meso.py` + `tests/test_meso/test_tasks.py`)
- New `deviate tasks <issue_id>` command that decomposes an existing `spec.md` into ~5 TDD task units
- Each task is a self-contained unit with implementation hints and a terminal E2E task
- Writes `tasks.md` alongside `spec.md` in the issue directory
- Includes session state transition and idempotency guard
- 154-line RED-phase acceptance test suite

### Shared error handling (`src/deviate/cli/_common.py` + `src/deviate/cli/macro.py`)
- Extracted `resolve_issue_record()` and error formatting into `_common.py` for cross-layer reuse
- Refactored macro.py to consume shared helpers, reducing duplication between layers
- Phase-parameterized error handlers to consistently match macro.py patterns

### Integration tests (`tests/test_integration/test_meso_task_ledger.py` + `tests/test_integration/conftest.py`)
- Full end-to-end integration test verifying the specify → tasks → ledger cycle
- Shared `conftest.py` with a `meso_project` fixture providing a standardized scratch workspace
- 132-line integration suite

### State config (`src/deviate/state/config.py`)
- Added `ConstitutionConfig` with `LLMBackend` enum and `timeout_seconds` field
- Extended config TOML serialization for the new fields
- Updated config tests (31 lines added)

### Spec artifacts
- `specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/spec.md` — 159-line functional spec for ISS-003
- `specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/tasks.md` — 143-line task decomposition (5 TDD tasks + 1 E2E)
- `specs/issues.jsonl` — ledger entries for ISS-002 spec and ISS-003 task decomposition

17 files changed, 1170 insertions, 46 deletions.
