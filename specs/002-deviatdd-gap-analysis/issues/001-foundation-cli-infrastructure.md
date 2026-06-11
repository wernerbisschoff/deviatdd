---
title: Foundation CLI Infrastructure — Profile, JSON/Quiet Flags, Placeholders, Pytest Report
labels: ["feature", "ISS-002", "P0"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: []
coordinates_with: []
issue_id: ISS-002-001
epic_id: ISS-002
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/001-foundation-cli-infrastructure.md`
- **Workstation Paths**:
  - `src/deviate/core/profile.py` — NEW: `ExecutionProfile` enum + `resolve_profile()`
  - `src/deviate/cli/_common.py` — MODIFY: add `@with_json_quiet` decorator
  - `src/deviate/cli/__init__.py` — MODIFY: extend `_resolve_placeholder()` to 6 vars
  - `src/deviate/cli/micro.py` — MODIFY: replace booleans with `--profile`, add `--json`/`--quiet`, optional `--json-report` in `_run_pytest()`
  - `src/deviate/cli/macro.py` — MODIFY: wire `--json`/`--quiet` on all pre commands
  - `src/deviate/cli/meso.py` — MODIFY: wire `--json`/`--quiet` on all pre commands
  - `src/deviate/state/config.py` — MODIFY: add `PytestReportConfig`, `ProfileConfig`
  - `pyproject.toml` — MODIFY: add `pytest-json-report` dev dependency

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer runs `deviate run TSK-001-01 --profile fast` and expects the TDD cycle to skip JUDGE and REFACTOR phases. They run `deviate explore pre --json` and get a machine-parseable JSON contract on stdout without Rich console noise. They run `deviate init --generate-constitution` and expect all 6 `${VARIABLE}` placeholders to be resolved from the project's actual filesystem state. When pytest runs, they can optionally get structured JSON output.

**System Response**: `--profile` maps to effective boolean combinations for phase skipping. `--json`/`--quiet` flags inject into all pre commands via a reusable decorator. Placeholder resolution discovers TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM via filesystem heuristics. `_run_pytest()` supports `--json-report` mode as an optional toggle with string-parsing fallback.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `src/deviate/core/profile.py` with `ExecutionProfile` enum and `resolve_profile()` mapping `full`→(F,F), `fast`→(T,T), `secure`→(F,T)
- `@with_json_quiet` decorator in `_common.py` injecting two Typer options
- Wire `--json`/`--quiet` into all pre commands in macro.py, meso.py, micro.py
- `_run_pytest()` optional `--json-report` mode with fallback to string parsing
- `PytestReportConfig` in `state/config.py`
- Extend `_resolve_placeholder()` from 2 to 6 variables
- Retain `--no-judge`/`--no-refactor` as composable overrides to `--profile`
- Add `pytest-json-report` to dev dependencies

### Defensive Exclusions
- NO changes to the TDD cycle logic itself (micro.py phase dispatch remains)
- NO changes to session state machine transitions
- NO changes to constitution validation or governance blocks
- NO changes to ledgers or issue tracking
- NO changes to skill files
- NO changes to AGENTS.md or CLAUDE.md

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-001 | Execution Profile Dispatch | FR-001-Profile |
| FR-009 | Cross-Cutting CLI Flags (--json/--quiet) | FR-009-JsonQuietFlags |
| FR-010 | Full Variable Resolution | FR-010-PlaceholderResolution |
| FR-016 | Pytest JSON Report | FR-016-PytestJsonReport |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-001-01 | `resolve_profile("fast")` returns `(True, True)` |
| AC-001-02 | `resolve_profile("secure")` with `no_refactor=False` returns `(False, False)` |
| AC-001-03 | `run_command --profile fast` skips JUDGE and REFACTOR |
| AC-001-04 | `run_command --profile invalid` emits CLI validation error |
| AC-009-01 | Any `pre` subcommand with `--json` emits only valid JSON on stdout |
| AC-009-02 | Any `pre` subcommand with `--quiet` suppresses Rich output, errors on stderr |
| AC-010-01 | `TARGET_BACKEND_FRAMEWORK` resolves from `pyproject.toml` dependencies |
| AC-010-02 | Unresolvable variables emit `"UNKNOWN"` with warning |
| AC-016-01 | `PytestReportConfig.json_report=True` includes `--json-report` flag |
| AC-016-02 | `PytestReportConfig.json_report=False` uses string-based classification |

### Data Model Entities
- `ExecutionProfile` — `src/deviate/core/profile.py`
- `ProfileConfig` — `src/deviate/state/config.py`
- `CommonCLIFlags` — `src/deviate/cli/_common.py`
- `PlaceholderRegistry` — `src/deviate/cli/__init__.py`
- `PytestReportConfig` — `src/deviate/state/config.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_core/test_profile.py` — `test_resolve_profile_full`, `test_resolve_profile_fast`, `test_resolve_profile_secure`, `test_resolve_profile_boolean_override`, `test_resolve_profile_invalid`
- `tests/test_cli/test_common.py` — `test_with_json_quiet_decorator_json`, `test_with_json_quiet_decorator_quiet`, `test_with_json_quiet_both_flags`
- `tests/test_cli/test_init.py` — `test_placeholder_resolution_6_vars`, `test_placeholder_resolution_unknown_fallback`
- `tests/test_cli/test_micro.py` — `test_run_command_profile_flag`, `test_run_pytest_json_report`, `test_run_pytest_json_report_fallback`
- `tests/test_state/test_config.py` — `test_pytest_report_config_defaults`, `test_profile_config_toml_roundtrip`

## [DEMONSTRATION_PATH]

```bash
# Verify profile resolution
uv run python -c "
from deviate.core.profile import resolve_profile
assert resolve_profile('fast') == (True, True)
assert resolve_profile('secure') == (False, True)
assert resolve_profile('full') == (False, False)
print('Profile resolution OK')
"

# Verify --json flag on explore pre
uv run deviate explore pre --json 2>/dev/null | python -c "import sys, json; json.load(sys.stdin); print('JSON output OK')"

# Verify placeholder resolution
uv run python -c "
from deviate.cli.__init__ import _resolve_placeholder
result = _resolve_placeholder()
assert 'PROJECT_NAME' in result
assert 'REPO_ROOT' in result
assert 'TARGET_BACKEND_FRAMEWORK' in result
assert 'TARGET_PACKAGE_MANAGER' in result
assert 'TARGET_TEST_RUNNER' in result
assert 'TARGET_COVERAGE_MINIMUM' in result
print('All 6 placeholders resolved OK')
"

# Run verification tests
pytest tests/test_core/test_profile.py tests/test_cli/test_common.py tests/test_cli/test_init.py -v --no-header -q
```
