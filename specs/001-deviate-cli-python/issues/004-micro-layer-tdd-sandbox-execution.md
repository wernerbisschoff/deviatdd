---
title: "[FR-004] Micro-Layer TDD Sandbox Execution"
labels: ["epic:001-deviate-cli-python", "layer:micro"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-003"]
coordinates_with: []
issue_id: "ISS-004"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/004-micro-layer-tdd-sandbox-execution.md`
- **Workstation Paths**: 
  - `src/deviate/cli/micro.py` (or integrated in `src/deviate/cli/__init__.py`)
  - `src/deviate/state/sandbox.py` (Tamper Guard logic, TaskRecord status updates)
  - `src/**/*.py` (Allowed write targets)
  - `tests/test_micro/`

## [THE_PROBLEM_CONTRACT]
As a developer writing code, I need the CLI to execute the RED, GREEN, and REFACTOR phases within a strictly sandboxed environment, enforcing the Tamper Guard and running validation gates via `mise`, so that production code is generated safely without corrupting tests, specs, or configuration files.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - `deviate red`, `green`, `refactor` Typer subcommands.
  - Tamper Guard implementation: evaluates `git diff` and triggers `git restore` rollback if `tests/`, `specs/`, or config files are modified.
  - Integration with `mise run check` (ruff + pytest) for validation gates.
  - Session state updates reflecting active task and phase transitions, including atomic `TaskRecord` status updates in the ledger.
- **Defensive Exclusions**: 
  - Macro or Meso layer orchestration.
  - Direct modification of `tests/`, `specs/`, or configuration files by the LLM sandbox (strictly read-only, enforced by Tamper Guard).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-004-MICRO**: Executes the RED, GREEN, and REFACTOR phases within a strictly sandboxed environment, enforcing the Tamper Guard and running validation gates via `mise`.
- **AC-004-MICRO-01**: `TaskRecord` with status `PENDING` executes `deviate red`, generating a failing test in `tests/` and updating status to `RED`.
- **AC-004-MICRO-02**: Sandbox attempts to modify `specs/constitution.md` during `deviate green` triggers Tamper Guard rollback, CLI error, and `TAMPER_DETECTED` log.
- **AC-004-MICRO-03**: Production code written during `deviate green` passes `mise run check` (exit code 0), updating `TaskRecord` status to `GREEN`.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_micro/test_red.py`, `tests/test_micro/test_green.py`, `tests/test_micro/test_refactor.py`
- **Integration Tests**: `tests/test_integration/test_tamper_guard.py`, `tests/test_integration/test_mise_check_gate.py`

## [DEMONSTRATION_PATH]
```bash
# Verify micro-layer TDD execution and Tamper Guard
pytest tests/test_micro/ -v
pytest tests/test_integration/test_tamper_guard.py -v
mise run check
```