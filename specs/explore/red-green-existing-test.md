## Problem Definition
**Statement**: GitHub issue #236 reports that a GREEN retry loses the committed RED boundary after rollback recovery fails.
**Scope**: The repository contains RED/GREEN/JUDGE orchestration, `SessionState.red_commit_sha`, rollback handling, tests, and specifications for GREEN entry.
**Exclusions**: This scan does not implement or verify a fix. It does not run tests.

## Discovery Audit Results
### Verified Dependencies
- `pyproject.toml` declares `typer`, `rich`, `pydantic`, and `pyyaml`; it also declares development dependencies including `pytest` and `ruff`.
- `pyproject.toml`: `requires-python = ">=3.13"`.
- `mise.toml` declares `pytest`, `ruff`, and `bats` task integration.

### Ghost Dependencies
- None observed in the reviewed manifests and source search.

### Test Runner Configuration
- `pyproject.toml` sets `testpaths = ["tests"]` and defines pytest markers.
- `mise.toml` defines `mise run test` with `uv run pytest --testmon-noselect tests/ -v`.
- `mise.toml` defines `mise run lint` with `uv run ruff check`.
- `mise.toml` defines `mise run test-e2e` with Bats.

## Constitution Quotes
- **Architectural Principles**: "Micro-Layer Scope: GREEN phase writes only to `src/` and permitted implementation paths. Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation."
- **Tech Stack Standards**: "Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Testing Protocols**: "GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files"
- **Definition of Done**: "[ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)"

## Architectural Baselines
### Routing and State
- `src/deviate/cli/micro.py` contains `_run_tdd_cycle`, `_run_green_phase`, and JUDGE retry routing.
- `src/deviate/state/config.py` defines `SessionState.red_commit_sha`.
- `specs/DeviaTDD-api.md` documents a GREEN entry invariant and missing-boundary rollback behavior.

### Quality and Testing
- `tests/unit/test_micro/test_orchestration.py` contains orchestration coverage for GREEN test failures.
- `tests/unit/test_micro/test_two_counter_retry.py` contains retry-counter coverage.
- `tests/unit/test_micro/test_rollback_safety.py` contains rollback safety coverage.

### External Integrations
- `src/deviate/core/agent.py` contains the configured agent backend integration.
- `pyproject.toml` declares the GitHub repository and issue tracker URLs.

## Sibling Flow Inventory
| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | `src/deviate/cli/micro.py` |
| lock vs reserve | none observed | `src/deviate/cli/micro.py` |
| Vendor call | agent invocation path | `src/deviate/core/agent.py` |
| Idempotency | session and retry state persist across phases | `src/deviate/state/config.py` |
| Destination shape | session state contains `red_commit_sha` | `src/deviate/state/config.py` |
| RED/GREEN retry | JUDGE routes retries through RED or GREEN | `specs/DeviaTDD-api.md` |

## Related Epic Candidates
| Path | Title | Evidence |
| :--- | :--- | :--- |
| `specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md` | Escalate no_failing_test to RED; never GREEN without red_commit_sha | "`deviate micro` can log `escalate_to_red` ... and then invoke GREEN anyway." (`specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md`) |
| `specs/005-acceptance-gates/003-micro-phase-gates-red-green.md` | Micro phase gates RED/GREEN | "`_run_green_phase` requires `_run_test_cmd` returncode 0" (`specs/005-acceptance-gates/003-micro-phase-gates-red-green.md`) |

## Ecosystem Research
SKIPPED (sibling + constitution sufficient)

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/micro.py` | Python module | Micro phase orchestration | "`_run_tdd_cycle`" appears in the repository search result for this module. |
| `src/deviate/state/config.py` | Python module | Session state model | "red_commit_sha: str = \"\"" (`src/deviate/state/config.py`) |
| `src/deviate/core/agent.py` | Python module | Agent backend integration | "class AgentBackend:" (`src/deviate/core/agent.py`) |
| `tests/unit/test_micro/test_orchestration.py` | Python tests | Micro orchestration tests | "test_micro_green_test_defect_failure_routes_to_judge" (`tests/unit/test_micro/test_orchestration.py`) |
| `tests/unit/test_micro/test_two_counter_retry.py` | Python tests | Retry behavior tests | "test_two_counter_retry" (`tests/unit/test_micro/test_two_counter_retry.py`) |
| `tests/unit/test_micro/test_rollback_safety.py` | Python tests | Rollback behavior tests | "revert_to_red" (`tests/unit/test_micro/test_rollback_safety.py`) |
| `pyproject.toml` | TOML manifest | Package and test configuration | "testpaths = [\"tests\"]" (`pyproject.toml`) |
| `mise.toml` | TOML task manifest | Test and lint commands | "run = \"uv run ruff check\"" (`mise.toml`) |
| `specs/DeviaTDD-api.md` | Markdown specification | API and orchestration contract | "**GREEN Entry Invariant:**" (`specs/DeviaTDD-api.md`) |
| `specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md` | Markdown issue | Existing related issue contract | "The Problem Contract" (`specs/adhoc/issues/021-no-failing-test-escalate-invokes-green.md`) |
| `CHANGELOG.md` | Markdown changelog | User-visible change history | "[Unreleased]" (`CHANGELOG.md`) |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | Unknown; likely `src/deviate/cli/micro.py` and related micro tests |
| New Modules Required | No evidence of a required new module |
| New Persistence / Data Models | No; `SessionState.red_commit_sha` exists |
| New External Integrations | No; GitHub issue evidence exists through repository metadata |
| Upstream / Cross-Cutting Concerns | RED/GREEN/JUDGE retry routing, rollback boundaries, and existing adhoc issue 021 overlap |
| Related Epic Attach | attach_existing_epic `adhoc` |
| Rationale | GitHub issue #236 describes a concrete failure log. Existing issue 021 and the API specification describe the same RED-boundary invariant. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | red-green-existing-test |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/red-green-existing-test.md |
| NEXT_ACTION | `attach_existing_epic` `adhoc` |
| ATTACH_EPIC | `adhoc` |
| HITL_OVERRIDE | none |
