# FEATURE_SPECIFICATION: specs/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Issue ID**: ISS-002-001
- **Issue Title**: Foundation CLI Infrastructure — Profile, JSON/Quiet Flags, Placeholders, Pytest Report
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/001-foundation-cli-infrastructure.md`
- **Upstream PRD**: `specs/002-deviatdd-gap-analysis/prd.md`
- **Workstation Paths**:
  - `src/deviate/core/profile.py` — NEW: `ExecutionProfile` enum + `resolve_profile()`
  - `src/deviate/cli/_common.py` — MODIFY: add `@with_json_quiet` decorator
  - `src/deviate/cli/__init__.py` — MODIFY: extend `_resolve_placeholder()` to 6 vars
  - `src/deviate/cli/micro.py` — MODIFY: replace booleans with `--profile`, add `--json`/`--quiet`, optional `--json-report` in `_run_pytest()`
  - `src/deviate/cli/macro.py` — MODIFY: wire `--json`/`--quiet` on all pre commands
  - `src/deviate/cli/meso.py` — MODIFY: wire `--json`/`--quiet` on all pre commands
  - `src/deviate/state/config.py` — MODIFY: add `PytestReportConfig`, `ProfileConfig`
  - `pyproject.toml` — MODIFY: add `pytest-json-report` dev dependency
- **Constitution Path**: `specs/constitution.md`

## THE_PROBLEM_CONTRACT

**User Journey**: A developer runs `deviate run TSK-001-01 --profile fast` and expects the TDD cycle to skip JUDGE and REFACTOR phases. They run `deviate explore pre --json` and get a machine-parseable JSON contract on stdout without Rich console noise. They run `deviate init --generate-constitution` and expect all 6 `${VARIABLE}` placeholders to be resolved from the project's actual filesystem state. When pytest runs, they can optionally get structured JSON output.

**System Response**: `--profile` maps to effective boolean combinations for phase skipping. `--json`/`--quiet` flags inject into all pre commands via a reusable decorator. Placeholder resolution discovers `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`, `TARGET_COVERAGE_MINIMUM` via filesystem heuristics. `_run_pytest()` supports `--json-report` mode as an optional toggle with string-parsing fallback.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `src/deviate/core/profile.py` with `ExecutionProfile` enum (`Literal["full", "fast", "secure"]`) and `resolve_profile()` mapping `full` → (False, False), `fast` → (True, True), `secure` → (False, True)
- `@with_json_quiet` decorator in `_common.py` injecting two Typer options into any pre command
- Wire `--json`/`--quiet` into all pre commands in `macro.py`, `meso.py`, `micro.py`
- `_run_pytest()` optional `--json-report` mode with fallback to string parsing
- `PytestReportConfig` in `state/config.py` with `json_report: bool = False`
- `ProfileConfig` in `state/config.py` with `default_profile: str = "full"`
- Extend `_resolve_placeholder()` from 2 to 6 variables with eager single-scan caching at module level
- Retain `--no-judge`/`--no-refactor` as composable overrides to `--profile`
- Add `pytest-json-report` to dev dependencies in `pyproject.toml`

### Defensive Exclusions

- NO changes to the TDD cycle logic itself (micro.py phase dispatch remains)
- NO changes to session state machine transitions
- NO changes to constitution validation or governance blocks
- NO changes to ledgers or issue tracking
- NO changes to skill files
- NO changes to AGENTS.md or CLAUDE.md

## PERFORMANCE_CONSTRAINTS

- Placeholder resolution (offline): L_max <= 50ms (eager single-scan at module import)
- `@with_json_quiet` decorator overhead: L_max <= 1ms per invocation
- `resolve_profile()` execution: L_max <= 1ms
- All `deviate init` operations: L_max <= 500ms
- All `pre` subcommand contract emission: L_max <= 100ms
- All `deviate run` profile parsing: L_max <= 10ms

## MULTI_TIERED_VERIFICATION_TARGETS

- `tests/test_core/test_profile.py` — `test_resolve_profile_full`, `test_resolve_profile_fast`, `test_resolve_profile_secure`, `test_resolve_profile_boolean_override`, `test_resolve_profile_invalid`
- `tests/test_cli/test_common.py` — `test_with_json_quiet_decorator_json`, `test_with_json_quiet_decorator_quiet`, `test_with_json_quiet_both_flags`, `test_with_json_quiet_failure_contract`
- `tests/test_cli/test_init.py` — `test_placeholder_resolution_6_vars`, `test_placeholder_resolution_unknown_fallback`, `test_placeholder_resolution_eager_single_scan`
- `tests/test_cli/test_micro.py` — `test_run_command_profile_flag`, `test_run_pytest_json_report`, `test_run_pytest_json_report_fallback`, `test_run_pytest_json_report_nonzero_exit`
- `tests/test_state/test_config.py` — `test_pytest_report_config_defaults`, `test_profile_config_toml_roundtrip`

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-Profile: Execution Profile Dispatch

- **Upstream Requirement Traceability**: FR-001

1. **Given** the `resolve_profile()` function in `src/deviate/core/profile.py`
   **When** called with `profile="full"`
   **Then** it returns `(False, False)` — neither JUDGE nor REFACTOR is skipped

2. **Given** the `resolve_profile()` function
   **When** called with `profile="fast"`
   **Then** it returns `(True, True)` — both JUDGE and REFACTOR are skipped

3. **Given** the `resolve_profile()` function
   **When** called with `profile="secure"`
   **Then** it returns `(False, True)` — only REFACTOR is skipped

4. **Given** the `resolve_profile()` function
   **When** called with `profile="secure"` and `no_refactor=False`
   **Then** it returns `(False, False)` — the explicit boolean override overrides the profile default for `no_refactor`

5. **Given** the `resolve_profile()` function
   **When** called with `profile="fast"` and `no_judge=False`
   **Then** it returns `(False, True)` — explicit `False` override replaces the profile's default `True`

6. **Given** the `resolve_profile()` function
   **When** called with `profile="invalid"`
   **Then** it raises `ValueError` with the message enumerating valid choices: `"full"`, `"fast"`, `"secure"`

7. **Given** the `run_command()` Typer command in `src/deviate/cli/micro.py`
   **When** invoked with `--profile fast`
   **Then** the TDD cycle skips JUDGE and REFACTOR phases, equivalent to passing both `--no-judge` and `--no-refactor`

8. **Given** the `run_command()` Typer command
   **When** invoked with `--profile invalid`
   **Then** Typer emits a CLI validation error with the valid choices enumerated

9. **Given** the `run_command()` Typer command
   **When** invoked with `--profile secure --no-judge`
   **Then** the explicit `--no-judge` flag overrides the profile, and only REFACTOR is skipped (JUDGE executes)

10. **Given** the `run_command()` Typer command
    **When** invoked with `--profile full --no-refactor`
    **Then** the explicit `--no-refactor` flag overrides the profile, and REFACTOR is skipped

### US-002-JsonQuiet: Cross-Cutting CLI Flags

- **Upstream Requirement Traceability**: FR-009

1. **Given** the `@with_json_quiet` decorator in `src/deviate/cli/_common.py`
   **When** applied to a Typer command
   **Then** it injects two Typer options: `--json` (bool) and `--quiet` (bool)

2. **Given** any `pre` subcommand in `macro.py`, `meso.py`, or `micro.py`
   **When** invoked with `--json`
   **Then** stdout contains only the valid JSON contract; all Rich console output is suppressed

3. **Given** any `pre` subcommand
   **When** invoked with `--quiet`
   **Then** Rich console output is suppressed; errors still appear on stderr

4. **Given** any `pre` subcommand
   **When** invoked with both `--json` and `--quiet`
   **Then** the JSON contract is emitted on stdout (as with `--json` alone); diagnostic Rich output is suppressed; errors go to stderr

5. **Given** any `pre` subcommand that encounters a failure (e.g., missing `.deviate/` directory)
   **When** invoked with `--json`
   **Then** a valid JSON contract is emitted on stdout containing `"status": "FAILURE"` and a descriptive `"reason"` field; non-JSON error diagnostics go to stderr

6. **Given** any `pre` subcommand that encounters a failure
   **When** invoked without `--json`
   **Then** errors are emitted to stderr with no JSON output on stdout

### US-003-Placeholder: Full Variable Resolution

- **Upstream Requirement Traceability**: FR-010

1. **Given** a Python project with `pyproject.toml` containing `[project.dependencies]` with `fastapi`
   **When** `_resolve_placeholder()` runs during `deviate init --generate-constitution`
   **Then** `TARGET_BACKEND_FRAMEWORK` resolves to `"fastapi"`

2. **Given** a Python project with a `uv.lock` or `poetry.lock` lockfile
   **When** `_resolve_placeholder()` runs
   **Then** `TARGET_PACKAGE_MANAGER` resolves to `"uv"` (for `uv.lock`), `"poetry"` (for `poetry.lock`), or `"pip"` (fallback)

3. **Given** a Python project with `pyproject.toml` containing `[tool.pytest.ini_options]`
   **When** `_resolve_placeholder()` runs
   **Then** `TARGET_TEST_RUNNER` resolves to `"pytest"`

4. **Given** a Python project with `pyproject.toml` containing `[tool.coverage.run]`
   **When** `_resolve_placeholder()` runs
   **Then** `TARGET_COVERAGE_MINIMUM` resolves to the coverage threshold value, or defaults to `"80"` if not specified

5. **Given** a Python project with `.deviate/config.toml` containing `[profile] coverage_minimum = 90`
   **When** `_resolve_placeholder()` runs
   **Then** `TARGET_COVERAGE_MINIMUM` uses `"90"` from the config file, overriding the default `"80"`

6. **Given** a project without `pyproject.toml` or any recognized config file
   **When** `_resolve_placeholder()` runs
   **Then** unresolvable variables emit `"UNKNOWN"` with a warning to stderr

7. **Given** the `_resolve_placeholder()` module
   **When** first imported and cached after module initialization
   **Then** subsequent calls return the cached `dict[str, str]` without re-scanning the filesystem (eager single-scan pattern)

### US-004-PytestReport: Pytest JSON Report

- **Upstream Requirement Traceability**: FR-016

1. **Given** `PytestReportConfig.json_report = True` in a loaded `DeviateConfig`
   **When** `_run_pytest()` executes
   **Then** the pytest command includes `--json-report` flag and outcome is classified via JSON report

2. **Given** `PytestReportConfig.json_report = False` in a loaded `DeviateConfig`
   **When** `_run_pytest()` executes
   **Then** the pytest command does NOT include `--json-report` and string-based outcome classification is used

3. **Given** `PytestReportConfig.json_report = True` and pytest exits with non-zero return code
   **When** `_run_pytest()` executes
   **Then** JSON report parsing is attempted first; only if the JSON report file is missing or malformed does it fall back to string-based classification

4. **Given** `PytestReportConfig.json_report = True` but the `pytest-json-report` plugin is not installed
   **When** `_run_pytest()` executes
   **Then** a warning is logged to stderr and the system falls back to string-based classification silently

5. **Given** a `PytestReportConfig` instance with `json_report = True`
   **When** serialized to TOML via `_dict_to_toml()`
   **Then** the TOML output contains `json_report = true` under the `[pytest_report]` section

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| STATUS | SPECIFIED |
| EPIC_SLUG | 002-deviatdd-gap-analysis |
| BRANCH_NAME | feat/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure |
| SPEC_PATH | specs/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure/spec.md |
| ISSUE_ID | ISS-002-001 |
| NEXT_ACTION | Execute `deviate tasks pre` to detect worktree and prepare for task decomposition |
