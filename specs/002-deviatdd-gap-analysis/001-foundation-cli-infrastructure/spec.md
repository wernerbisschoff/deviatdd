# FEATURE_SPECIFICATION: specs/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/001-foundation-cli-infrastructure.md`
- **Branch**: `feat/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure`

### Workstation Paths

| Path | Action |
|------|--------|
| `src/deviate/core/profile.py` | NEW — `ExecutionProfile` enum + `resolve_profile()` function |
| `src/deviate/cli/micro.py` | MODIFY — `run_command()` uses `--profile` flag, retains booleans as overrides |
| `src/deviate/cli/_common.py` | MODIFY — add `@with_json_quiet` decorator |
| `src/deviate/state/config.py` | MODIFY — add `ProfileConfig` + `PytestReportConfig` TOML sections |
| `src/deviate/cli/__init__.py` | MODIFY — extend `_resolve_placeholder()` from 2→6 variables |
| `src/deviate/cli/macro.py` | MODIFY — all `pre` subcommands use `@with_json_quiet` |
| `src/deviate/cli/meso.py` | MODIFY — all `pre` subcommands use `@with_json_quiet` |
| `src/deviate/cli/context.py` | MODIFY — `context pre` uses `@with_json_quiet` |
| `src/deviate/cli/adhoc.py` | MODIFY — `adhoc pre` uses `@with_json_quiet` |
| `src/deviate/cli/constitution.py` | MODIFY — `constitution pre` uses `@with_json_quiet` |
| `pyproject.toml` | MODIFY — add `pytest-json-report` to dev dependencies |

## THE_PROBLEM_CONTRACT

**User Journey**: A developer invokes `deviate run TSK-001 --profile fast` and expects JUDGE and REFACTOR phases to be skipped without passing `--no-judge --no-refactor`. A CI pipeline invokes `deviate context pre --json` and expects a parseable JSON contract on stdout, not rich terminal output. A new project runs `deviate init --generate-constitution` and expects all 6 `${VARIABLE}` placeholders to be resolved from filesystem heuristics, not just 2. A power user configures `PytestReportConfig.json_report = True` in `.deviate/config.toml` and expects pytest output classified via JSON report.

**System Response**: `resolve_profile("fast")` returns `(True, True)` — composable `--no-judge`/`--no-refactor` overrides take precedence. `@with_json_quiet` injects `--json` (stdout gets raw contract) and `--quiet` (Rich suppressed, errors to stderr). `_resolve_placeholder()` scans `pyproject.toml`/`package.json` for backend framework, package manager, test runner, coverage minimum — unresolvable vars fall back to `"UNKNOWN"` with stderr warning. `_run_pytest()` conditionally appends `--json-report`; if the plugin is missing, logs a warning and falls back to string parsing.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `ExecutionProfile` enum (`Literal["full", "fast", "secure"]`) in `src/deviate/core/profile.py`
- `resolve_profile()` logic: profile defaults + boolean overloads; explicit flags override profile defaults
- `run_command()`: `--profile` Typer option replaces individual `--no-judge`/`--no-refactor` flags; retain flags as composable overrides
- `@with_json_quiet` decorator in `_common.py` — reusable across all `pre` subcommands
- `--json`: stdout gets only the JSON contract; all other output suppressed
- `--quiet`: Rich console output suppressed; stderr errors preserved
- `--json` + `--quiet`: JSON contract on stdout, errors on stderr (orthogonal flags)
- `_resolve_placeholder()`: 6 variables (PROJECT_NAME, REPO_ROOT, TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM)
- Placeholder resolution heuristics: best-effort per variable — `pyproject.toml` → framework, package manager; `package.json` → fallback
- Unresolvable placeholders: `"UNKNOWN"` with per-variable stderr warning
- Coverage min default: `"80"` if unset
- `ProfileConfig` TOML section in `state/config.py`
- `PytestReportConfig` TOML section with `json_report: bool`
- `_run_pytest()` conditionally appends `--json-report` and uses JSON classification path
- String parsing remains primary path; JSON parsing is fallback
- `pytest-json-report` added to dev dependencies (optional, not required)

### Defensive Exclusions

- NO changes to `CacheDiscipline`, JUDGE train rollback, or other micro-layer logic
- NO changes to session state machine transitions
- NO changes to existing test structure beyond new profile/flag/placeholder tests
- NO breaking changes to `run_command()` API — booleans remain as optional overrides
- NO changes to ledger models or append-only protocol
- Unknown profile value: Typer validation error, not `ValueError`
- `--json-report` plugin missing: warn and fall back silently — no hard failure

## PERFORMANCE_CONSTRAINTS

- `resolve_profile()`: L_max <= 5ms (pure enum dispatch, no I/O)
- `@with_json_quiet` decorator: L_max <= 1ms overhead per invocation
- `_resolve_placeholder()`: L_max <= 50ms (file I/O for heuristics)
- `_run_pytest()` `--json-report` branch: L_max <= 10ms overhead (arg construction only; test runtime is excluded)

## MULTI_TIERED_VERIFICATION_TARGETS

| Tier | Target | Command |
|------|--------|---------|
| Unit | `tests/test_core/test_profile.py` | `pytest tests/test_core/test_profile.py -v` |
| Unit | `tests/test_cli/test_common.py` | `pytest tests/test_cli/test_common.py -v` |
| Unit | `tests/test_cli/test_init.py` | `pytest tests/test_cli/test_init.py::test_resolve_placeholder_* -v` |
| Unit | `tests/test_cli/test_micro.py` | `pytest tests/test_cli/test_micro.py::test_run_pytest_json_* -v` |
| Unit | `tests/test_state/test_config.py` | `pytest tests/test_state/test_config.py::test_profile_config* test_pytest_report_config* -v` |

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-Profile: Execution Profile Dispatch

* **Upstream Requirement Traceability**: FR-001

1. **Scenario: Fast profile skips JUDGE and REFACTOR**
   **Given** a `deviate` CLI with `ExecutionProfile` supporting `"full"`, `"fast"`, `"secure"`
   **When** `resolve_profile("fast")` is called
   **Then** it returns `(True, True)` (skip JUDGE=True, skip REFACTOR=True)

2. **Scenario: Secure profile with explicit no_refactor=False override**
   **Given** `resolve_profile()` accepts boolean overrides for `no_judge` and `no_refactor`
   **When** `resolve_profile("secure", no_refactor=False)` is called
   **Then** it returns `(False, False)` (profile says skip both, but explicit `no_refactor=False` re-enables REFACTOR)

3. **Scenario: Explicit flag overrides profile default**
   **Given** a profile that defaults to skipping JUDGE
   **When** an explicit `--no-judge` flag is passed alongside `--profile fast`
   **Then** the explicit flag takes precedence over the profile default

4. **Scenario: Invalid profile value emits Typer validation error**
   **Given** `run_command()` with a `--profile` Typer option
   **When** `--profile invalid` is passed
   **Then** Typer emits a validation error (not `ValueError`)

### US-002-JsonQuiet: Cross-Cutting JSON/Quiet CLI Flags

* **Upstream Requirement Traceability**: FR-009

1. **Scenario: --json flag emits raw contract on stdout**
   **Given** a `pre` subcommand decorated with `@with_json_quiet`
   **When** the subcommand is invoked with `--json`
   **Then** stdout contains only the JSON contract (no Rich output)
   **And** all non-JSON output is suppressed

2. **Scenario: --quiet flag suppresses Rich console**
   **Given** a `pre` subcommand decorated with `@with_json_quiet`
   **When** the subcommand is invoked with `--quiet`
   **Then** Rich console output is suppressed
   **And** error output is still written to stderr

3. **Scenario: --json + --quiet flags are orthogonal**
   **Given** a `pre` subcommand decorated with `@with_json_quiet`
   **When** the subcommand is invoked with both `--json` and `--quiet`
   **Then** stdout contains only the JSON contract
   **And** error output is written to stderr
   **And** Rich console output is suppressed

4. **Scenario: No flags produce normal Rich output**
   **Given** a `pre` subcommand decorated with `@with_json_quiet`
   **When** the subcommand is invoked without `--json` or `--quiet`
   **Then** normal Rich console output is displayed

### US-003-Placeholder: Full Variable Placeholder Resolution

* **Upstream Requirement Traceability**: FR-010

1. **Scenario: Complete pyproject.toml resolves all 6 placeholders**
   **Given** a project root with a complete `pyproject.toml`
   **When** `_resolve_placeholder()` is called
   **Then** all 6 variables (PROJECT_NAME, REPO_ROOT, TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM) are resolved from filesystem heuristics
   **And** no stderr warnings are emitted

2. **Scenario: Partial pyproject.toml resolves best-effort**
   **Given** a project root with a `pyproject.toml` containing `[project] name` but no `[tool]` section
   **When** `_resolve_placeholder()` is called
   **Then** PROJECT_NAME is resolved from `pyproject.toml`
   **And** unresolvable variables (TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER) are set to `"UNKNOWN"`
   **And** per-variable stderr warnings are emitted for each unresolvable variable

3. **Scenario: No pyproject.toml — all variables fall back to UNKNOWN**
   **Given** a project root with neither `pyproject.toml` nor `package.json`
   **When** `_resolve_placeholder()` is called
   **Then** all variables except REPO_ROOT are set to `"UNKNOWN"`
   **And** per-variable stderr warnings are emitted

### US-004-PytestReport: Pytest JSON Report Support

* **Upstream Requirement Traceability**: FR-016

1. **Scenario: json_report=True appends --json-report flag**
   **Given** `PytestReportConfig.json_report = True`
   **When** `_run_pytest()` is called
   **Then** `--json-report` is appended to the pytest arguments

2. **Scenario: json_report=False uses string parsing**
   **Given** `PytestReportConfig.json_report = False`
   **When** `_run_pytest()` is called
   **Then** `--json-report` is NOT appended to the pytest arguments
   **And** outcome classification uses string parsing

3. **Scenario: pytest-json-report plugin missing — graceful fallback**
   **Given** `PytestReportConfig.json_report = True`
   **And** the `pytest-json-report` plugin is not installed
   **When** `_run_pytest()` is called
   **Then** a warning is logged
   **And** the system falls back to string-based outcome classification without hard failure

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| STATUS | DRAFT |
| EPIC_SLUG | 002-deviatdd-gap-analysis |
| ISSUE_SLUG | 001-foundation-cli-infrastructure |
| BRANCH_NAME | feat/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure |
| SPEC_PATH | specs/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure/spec.md |
| ISSUE_ID | ISS-002-001 |
| CONSTITUTION_PATH | specs/constitution.md |
| NEXT_ACTION | HITL Gate 2 — Human reviews spec.md; then run `deviate tasks pre` |
