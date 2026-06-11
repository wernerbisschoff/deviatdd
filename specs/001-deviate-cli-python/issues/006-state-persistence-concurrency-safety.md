---
title: "[FR-006] State Persistence & Concurrency Safety"
labels: ["epic:001-deviate-cli-python", "layer:state"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: []
coordinates_with: []
issue_id: "ISS-001-006"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/006-state-persistence-concurrency-safety.md`
- **Workstation Paths**: 
  - `src/deviate/state/config.py` (file locking, atomic writes)
  - `src/deviate/state/session.py` (session state concurrency)
  - `src/deviate/core/ledger.py` (atomic JSONL append)

## [THE_PROBLEM_CONTRACT]
As a developer running multiple CLI instances or background processes, I need all state mutations (JSON, TOML, JSONL) to be atomic and protected against concurrent access race conditions, so that no state file is ever corrupted by simultaneous writes.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - OS-level advisory file locking (e.g., `fcntl`) for all state file mutations.
  - Atomic append operations for `specs/issues.jsonl` ledger.
  - Atomic read/write for `.deviate/config.toml` and `.deviate/session.json`.
  - Config validation on load: `timeout_seconds` must be > 0.
  - Graceful failure when lock cannot be acquired within `timeout_seconds`.
  - Unit test coverage for all state mutation functions.
- **Defensive Exclusions**: 
  - Core module business logic (covered by ISS-001-005).
  - Micro-layer TDD sandbox execution (covered by ISS-001-004).
  - Database-level concurrency (state is strictly file-based).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-006-STATE**: Ensures all state mutations (JSON, TOML, JSONL) are atomic and protected against concurrent access race conditions.
- **AC-006-STATE-01**: Two concurrent processes attempting to append to `specs/issues.jsonl` — one acquires lock and succeeds, the other waits or fails gracefully.
- **AC-006-STATE-02**: Invalid `timeout_seconds` (e.g., `-1`) in `.deviate/config.toml` triggers Pydantic validation failure with structured error.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_state/test_concurrency.py`, `tests/test_state/test_config.py`
- **Integration Tests**: `tests/test_integration/test_file_locking.py`

## [DEMONSTRATION_PATH]
```bash
# Verify state persistence and concurrency safety
pytest tests/test_state/test_concurrency.py -v
pytest tests/test_state/test_config.py -v
pytest tests/test_integration/test_file_locking.py -v
python -c "import json; [json.loads(l) for l in open('specs/issues.jsonl')]"
```
