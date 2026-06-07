---
title: "[FR-004] Micro-Layer TDD Sandbox Execution"
labels: ["epic:001-deviate-cli-python", "layer:micro"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-005"]
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
As a developer writing code, I need the CLI to execute the full micro-layer TDD cycle — EXECUTE, RED, GREEN, REFACTOR, YELLOW, JUDGE, E2E, and HOTFIX — within a strictly sandboxed environment, enforcing the Tamper Guard and running validation gates via `mise`, so that production code is generated safely without corrupting tests, specs, or configuration files.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**: 
  - `deviate execute pre [--task <id>]` and `deviate execute post <manifest>` — workflow discovery, task context surfacing, validation command resolution, precommit hooks, commit.
  - `deviate red pre [--task <id>]` and `deviate red post <manifest>` — task context, test command resolution, spec_dir discovery, test failure validation, commit.
  - `deviate green pre [--task <id>]` and `deviate green post <manifest>` — task context, test/lint resolution, test pass validation, commit.
  - `deviate refactor pre [--task <id>]` and `deviate refactor post <manifest>` — task context, test invariance validation, commit.
  - `deviate e2e pre` and `deviate e2e post` — phase completion verification, E2E test discovery, execution results, commit.
  - `deviate hotfix pre` and `deviate hotfix post <manifest>` — bug context discovery, commit.
  - **YELLOW phase** (conditional): If RED test is flawed, propose amendment for isolated judge approval/rejection.
  - **JUDGE phase**: Isolated compliance gate evaluating `git diff` against `spec.md` for security and structural violations.
  - Tamper Guard implementation: evaluates `git diff` and triggers `git restore` rollback if `tests/`, `specs/`, or config files are modified.
  - Integration with `mise run check` (ruff + pytest) for validation gates.
  - Session state updates reflecting active task and phase transitions, including atomic `TaskRecord` status updates in the ledger.
- **Defensive Exclusions**: 
  - Macro or Meso layer orchestration (covered by ISS-005).
  - Core module implementations (repo, ledger, contract, commit, constitution, epic, validation, worktree, issues, prd, skills — covered by ISS-005).
  - Direct modification of `tests/`, `specs/`, or configuration files by the LLM sandbox (strictly read-only, enforced by Tamper Guard).

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-004-EXECUTE**: `deviate execute pre/post` discovers workflow context, resolves validation commands, and manages precommit hooks.
- **FR-004-RED**: `TaskRecord` with status `PENDING` executes `deviate red`, generating a failing test in `tests/` and updating status to `RED`.
- **FR-004-GREEN**: `deviate green` writes production code; passes `mise run check` (exit code 0); updates `TaskRecord` to `GREEN`.
- **FR-004-REFACTOR**: `deviate refactor` polishes implementation; test invariance validated; `TaskRecord` updated to `REFACTORED`.
- **FR-004-YELLOW**: Conditional YELLOW phase allows test amendment proposals with isolated JUDGE approval/rejection.
- **FR-004-JUDGE**: Isolated compliance gate evaluates `git diff` against `spec.md` for security and structural violations.
- **FR-004-E2E**: `deviate e2e pre/post` verifies phase completion and runs E2E tests.
- **FR-004-HOTFIX**: `deviate hotfix pre/post` handles bug context discovery and commit.
- **FR-004-TAMPER**: Sandbox attempts to modify `specs/constitution.md` during `deviate green` triggers Tamper Guard rollback, CLI error, and `TAMPER_DETECTED` log.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_micro/test_execute.py`, `tests/test_micro/test_red.py`, `tests/test_micro/test_green.py`, `tests/test_micro/test_refactor.py`, `tests/test_micro/test_yellow.py`, `tests/test_micro/test_judge.py`, `tests/test_micro/test_e2e.py`, `tests/test_micro/test_hotfix.py`
- **Integration Tests**: `tests/test_integration/test_tamper_guard.py`, `tests/test_integration/test_mise_check_gate.py`, `tests/test_integration/test_full_cycle.py`

## [DEMONSTRATION_PATH]
```bash
# Verify micro-layer TDD execution and Tamper Guard
pytest tests/test_micro/ -v
pytest tests/test_integration/test_tamper_guard.py -v
pytest tests/test_integration/test_full_cycle.py -v
mise run check
```