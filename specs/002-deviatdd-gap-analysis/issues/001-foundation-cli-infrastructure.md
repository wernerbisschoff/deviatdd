---
title: Foundation CLI Infrastructure — Profile, JSON/Quiet Flags, Placeholder Resolution, Pytest JSON Report
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: []
coordinates_with: []
issue_id: ISS-002-001
epic_id: ISS-002
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/001-foundation-cli-infrastructure.md`
- **Workstation Paths**:
  - `src/deviate/core/profile.py` — NEW: `ExecutionProfile` enum + `resolve_profile()` function
  - `src/deviate/cli/micro.py` — MODIFY: `run_command()` uses `--profile` flag, retains booleans as overrides
  - `src/deviate/cli/_common.py` — MODIFY: add `@with_json_quiet` decorator injecting `--json`/`--quiet` options
  - `src/deviate/state/config.py` — MODIFY: add `ProfileConfig` (TOML section) + `PytestReportConfig` (TOML section)
  - `src/deviate/cli/__init__.py` — MODIFY: extend `_resolve_placeholder()` from 2→6 variables
  - `src/deviate/cli/macro.py` — MODIFY: all `pre` subcommands use `@with_json_quiet`
  - `src/deviate/cli/meso.py` — MODIFY: all `pre` subcommands use `@with_json_quiet`
  - `src/deviate/cli/context.py` — MODIFY: `context pre` uses `@with_json_quiet`
  - `src/deviate/cli/adhoc.py` — MODIFY: `adhoc pre` uses `@with_json_quiet`
  - `src/deviate/cli/constitution.py` — MODIFY: `constitution pre` uses `@with_json_quiet`
  - `pyproject.toml` — MODIFY: add `pytest-json-report` to dev dependencies

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer invokes `deviate run TSK-001 --profile fast` and expects JUDGE and REFACTOR phases to be skipped without passing `--no-judge --no-refactor`. A CI pipeline invokes `deviate context pre --json` and expects a parseable JSON contract on stdout, not rich terminal output. A new project runs `deviate init --generate-constitution` and expects all 6 `${VARIABLE}` placeholders to be resolved from filesystem heuristics, not just 2. A power user configures `PytestReportConfig.json_report = True` in `.deviate/config.toml` and expects pytest output classified via JSON report.

**System Response**: `resolve_profile("fast")` returns `(True, True)` — composable `--no-judge`/`--no-refactor` overrides take precedence. `@with_json_quiet` injects `--json` (stdout gets raw contract) and `--quiet` (Rich suppressed, errors to stderr). `_resolve_placeholder()` scans `pyproject.toml`/`package.json` for backend framework, package manager, test runner, coverage minimum—unresolvable vars fall back to `"UNKNOWN"` with stderr warning. `_run_pytest()` conditionally appends `--json-report`; if the plugin is missing, logs a warning and falls back to string parsing.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `ExecutionProfile` enum (`Literal["full", "fast", "secure"]`) in `src/deviate/core/profile.py`
- `resolve_profile()` logic: profile defaults + boolean overloads
- `run_command()`: `--profile` Typer option replaces individual `--no-judge`/`--no-refactor` flags; retain flags as composable overrides
- `@with_json_quiet` decorator in `_common.py` — reusable across all `pre` subcommands
- `--json`: stdout gets only the JSON contract; all other output suppressed
- `--quiet`: Rich console output suppressed; stderr errors preserved
- `_resolve_placeholder()`: 6 variables (PROJECT_NAME, REPO_ROOT, TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM)
- Placeholder resolution heuristics: `pyproject.toml` → `[project.dependencies]` for framework, `[build-system]` requires for package manager
- Unresolvable placeholders: `"UNKNOWN"` with stderr warning
- Coverage min default: `"80"` if unset
- `ProfileConfig` TOML section in `state/config.py`
- `PytestReportConfig` TOML section with `json_report: bool`
- `_run_pytest()` conditionally appends `--json-report` and uses `_classify_pytest_outcome()` JSON path
- String parsing remains primary path; JSON parsing is fallback
- `pytest-json-report` added to dev dependencies (optional, not required)

### Defensive Exclusions
- NO changes to `CacheDiscipline`, JUDGE train rollback, or other micro-layer logic
- NO changes to session state machine transitions
- NO changes to existing test structure beyond new profile/flag/placeholder tests
- NO breaking changes to `run_command()` API — booleans remain as optional overrides
- NO changes to ledger models or append-only protocol
- Unknown profile value: Typer validation error, not ValueError
- `--json-report` plugin missing: warn and fall back silently — no hard failure

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-001 | Execution Profile Dispatch | FR-001-Profile |
| FR-009 | Cross-Cutting CLI Flags | FR-009-JsonQuietFlags |
| FR-010 | Full Variable Resolution | FR-010-PlaceholderResolution |
| FR-016 | Pytest JSON Report | FR-016-PytestJsonReport |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-001-01 | `resolve_profile("fast")` returns `(True, True)` |
| AC-001-02 | `resolve_profile("secure")` with `no_refactor=False` returns `(False, False)` |
| AC-001-03 | `run_command --profile fast` skips JUDGE and REFACTOR phases |
| AC-001-04 | `run_command --profile invalid` emits Typer validation error |
| AC-009-01 | Any `pre` subcommand with `--json` emits only valid JSON on stdout |
| AC-009-02 | Any `pre` subcommand with `--quiet` suppresses Rich; errors on stderr |
| AC-010-01 | Python project with `pyproject.toml` → `TARGET_BACKEND_FRAMEWORK` resolved, `TARGET_PACKAGE_MANAGER` resolved |
| AC-010-02 | Project without `pyproject.toml` → unresolvable vars emit `"UNKNOWN"` with stderr warning |
| AC-016-01 | `PytestReportConfig.json_report = True` → pytest includes `--json-report` flag |
| AC-016-02 | `PytestReportConfig.json_report = False` → string-based outcome classification |

### Data Model Entities
- `ExecutionProfile` — `src/deviate/core/profile.py`
- `ProfileConfig` — `src/deviate/state/config.py`
- `PytestReportConfig` — `src/deviate/state/config.py`
- `PlaceholderRegistry` — `src/deviate/cli/__init__.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_core/test_profile.py` — `test_resolve_profile_fast`, `test_resolve_profile_secure_override`, `test_resolve_profile_invalid`
- `tests/test_cli/test_run.py` — `test_run_with_profile`, `test_run_with_flag_overrides`
- `tests/test_cli/test_common.py` — `test_with_json_quiet_json_flag`, `test_with_json_quiet_quiet_flag`, `test_with_json_quiet_both`
- `tests/test_cli/test_init.py` — `test_resolve_placeholder_complete`, `test_resolve_placeholder_missing_pyproject`
- `tests/test_cli/test_micro.py` — `test_run_pytest_json_report_enabled`, `test_run_pytest_json_report_fallback`

## [DEMONSTRATION_PATH]

```bash
# Verify resolve_profile
uv run python -c "
from deviate.core.profile import resolve_profile
assert resolve_profile('fast') == (True, True)
assert resolve_profile('secure', no_refactor=False) == (False, False)
print('Profile OK')
"

# Verify with_json_quiet decorator (contract test)
uv run python -c "
from deviate.cli._common import with_json_quiet
print('Decorator importable OK')
"

# Verify placeholder resolution
uv run python -c "
from deviate.cli.__init__ import _resolve_placeholder
result = _resolve_placeholder()
assert 'PROJECT_NAME' in result
assert 'REPO_ROOT' in result
assert 'TARGET_BACKEND_FRAMEWORK' in result
print(f'{len(result)} placeholders resolved: {result}')
"

# Run tests
pytest tests/test_core/test_profile.py tests/test_cli/test_common.py tests/test_cli/test_init.py tests/test_cli/test_micro.py -v --no-header -q
```
