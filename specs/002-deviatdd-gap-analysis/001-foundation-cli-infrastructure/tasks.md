# Implementation Tasks: feat/002-deviatdd-gap-analysis/001-foundation-cli-infrastructure

## Phase 1: Profile Module + Config Models
**Goal**: Create `ExecutionProfile` enum and `resolve_profile()` function in the new `core/profile.py` module, and add `ProfileConfig` TOML section to `state/config.py`. This phase establishes the foundational type-safe profile dispatch that downstream tasks wire into the CLI.

### Tasks

- [/] TSK-001-01: Profile Module + ProfileConfig TOML Section
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_profile.py tests/test_state/test_config.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/profile.py`
    - `src/deviate/state/config.py`
    - `tests/test_core/test_profile.py`
    - `tests/test_state/test_config.py`
  - **Rationale**: New `core/profile.py` module is the sole location for the `ExecutionProfile` enum and `resolve_profile()` dispatch logic defined by US-001 (FR-001). `state/config.py` must get `ProfileConfig` TOML section so profile defaults can be persisted in `.deviate/config.toml`. Tests validate all 4 ACs from US-001: fast profile, secure override, invalid profile, explicit flag precedence.
  - **Details**:
    - **Red**: Write `test_resolve_profile_fast()` asserting `resolve_profile("fast")` returns `(True, True)`. Write `test_resolve_profile_secure_override()` asserting `resolve_profile("secure", no_refactor=False)` returns `(False, False)`. Write `test_resolve_profile_invalid()` asserting invalid profile raises `ValueError` with available choices. Write `test_profile_config_toml_roundtrip()` asserting `ProfileConfig` serializes/deserializes via TOML. Write `test_profile_config_defaults()` asserting sensible defaults.
    - **Green**: Create `ExecutionProfile` type alias (`Literal["full", "fast", "secure"]`) in `core/profile.py`. Implement `resolve_profile(profile: ExecutionProfile, no_judge: bool | None = None, no_refactor: bool | None = None) -> tuple[bool, bool]` — profile defaults, then explicit boolean overrides take precedence. Add `ProfileConfig` Pydantic model to `state/config.py` with TOML serialization hook.
    - **Refactor**: Ensure `resolve_profile` is pure (no I/O, no CLI coupling). Validate Pydantic `extra = "forbid"` on ProfileConfig.
    - **Edge Cases**: Handle `profile="invalid"` with descriptive `ValueError` listing valid choices. Handle `no_judge=None` (not passed) correctly — don't override profile default. Handle `no_judge=False` explicitly — re-enable a phase the profile would skip.
    - **Acceptance**: AC-001-01, AC-001-02, AC-001-04 pass. ProfileConfig round-trips through TOML. Performance: `resolve_profile` completes in L_max <= 5ms.

- [ ] TSK-001-02: @with_json_quiet Decorator + Pre-Subcommand Wiring
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_common.py -v`
  - **Estimated Time**: 75 minutes
  - **Files**:
    - `src/deviate/cli/_common.py`
    - `src/deviate/cli/macro.py`
    - `src/deviate/cli/meso.py`
    - `src/deviate/cli/context.py`
    - `src/deviate/cli/adhoc.py`
    - `src/deviate/cli/constitution.py`
    - `tests/test_cli/test_common.py`
  - **Rationale**: US-002 (FR-009) requires `--json` and `--quiet` flags on all `pre` subcommands. Creating a single `@with_json_quiet` decorator in `_common.py` ensures consistent behavior across all 6 command modules (macro, meso, context, adhoc, constitution). The decorator is the reusable cross-cutting concern — wiring it into each pre command is mechanical but must be verified per command.
  - **Details**:
    - **Red**: Write `test_with_json_quiet_json_flag()` asserting that when `--json` is passed, stdout contains only the JSON contract and all Rich output is suppressed. Write `test_with_json_quiet_quiet_flag()` asserting Rich suppressed but stderr errors preserved. Write `test_with_json_quiet_both()` asserting JSON on stdout + errors on stderr (orthogonal). Write `test_with_json_quiet_no_flags()` asserting normal Rich output. Write integration test per wired command asserting the decorator is present and functional.
    - **Green**: Implement `@with_json_quiet` decorator in `_common.py`. The decorator injects two Typer `Option` arguments (`--json`, `--quiet`). On `--json`: capture stdout, serialize the command's return value as JSON, print only JSON. On `--quiet`: pass `quiet=True` to Rich console, errors still go to stderr. On both: quiet suppresses diagnostics, JSON contract still emitted. Apply `@with_json_quiet` to all `pre` command functions in `macro.py`, `meso.py`, `context.py`, `adhoc.py`, `constitution.py`.
    - **Refactor**: Ensure decorator does not mutate the wrapped function's signature in a way that breaks Typer's command registration. Use `functools.wraps`. Verify no duplicate `--json`/`--quiet` options if a command already has them.
    - **Edge Cases**: `--json` + `--quiet` orthogonality (FR-009 spec explicitly defines behavior). Empty JSON contract (empty dict, not null). Very large contracts must not be truncated.
    - **Acceptance**: AC-009-01, AC-009-02 pass. All 6 pre command groups have the decorator. No pre-existing test failures.

## Phase 2: Profile Integration into run_command
**Goal**: Wire the `--profile` flag into `deviate run` and integrate profile dispatch with the TDD cycle. Booleans retained as composable overrides per spec.

### Tasks

- [ ] TSK-001-03: --profile Flag in run_command
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_run.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-001-01
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_run.py`
  - **Rationale**: US-001 (FR-001) requires `run_command` to accept `--profile` (AC-001-03, AC-001-04). This task wires the profile dispatch built in TSK-001-01 into the CLI entry point, replacing the existing boolean-only `--no-judge`/`--no-refactor` flags while retaining them as composable overrides per the Hard Inclusions in the spec. The test file already has the `TestRunCommand` class — this task adds profile-related test cases.
  - **Details**:
    - **Red**: Write `test_run_with_profile_fast()` asserting `--profile fast` skips JUDGE and REFACTOR phases in the TDD cycle. Write `test_run_with_flag_overrides()` asserting `--profile fast --no-judge` works (redundant but no error). Write `test_run_with_profile_invalid()` asserting Typer validation error for `--profile invalid`.
    - **Green**: Add `profile: str = typer.Option("full", "--profile", help="Execution profile: full, fast, secure")` to `run_command()`. At dispatch point, call `resolve_profile(profile, no_judge, no_refactor)` to compute effective flags. Pass result to `_run_tdd_cycle()`. Booleans remain as Typer `Option(None)` — when provided, they override profile defaults.
    - **Refactor**: Extract profile argument construction into a helper to keep `run_command()` clean. Ensure existing `--no-judge`/`--no-refactor` tests still pass unchanged.
    - **Edge Cases**: `--profile full` (default, explicit) must match behavior of no flags. `--profile invalid` must produce Typer validation error, not `ValueError`. Combining `--profile fast --no-judge` must not error (explicit flag redundant with profile is fine).
    - **Acceptance**: AC-001-03, AC-001-04 pass. Existing `test_run_dispatches_*` tests pass unchanged. No breaking changes to `run_command()` API.

## Phase 3: Placeholder Resolution + Pytest Report + E2E
**Goal**: Extend placeholder resolution to all 6 variables, add optional pytest JSON report support, and verify the full integration.

### Tasks

- [ ] TSK-001-04: Extended Placeholder Resolution (2→6 Variables)
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_init.py::test_resolve_placeholder_complete tests/test_cli/test_init.py::test_resolve_placeholder_missing_pyproject -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-003 (FR-010) requires `_resolve_placeholder()` to handle 6 variables (up from 2): PROJECT_NAME, REPO_ROOT, TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM. The existing function in `cli/__init__.py` only resolves 2 — this task extends it with filesystem heuristics and best-effort resolution per the HITL decision.
  - **Details**:
    - **Red**: Write `test_resolve_placeholder_complete()` with a fixture `pyproject.toml` containing project name, dependencies (framework), and tool config (package manager, test runner) — assert all 6 variables resolved. Write `test_resolve_placeholder_missing_pyproject()` in a temp dir without config — assert unresolvable vars get `"UNKNOWN"` with per-variable stderr warnings and REPO_ROOT still resolved. Write `test_resolve_placeholder_partial()` with partial config — assert best-effort resolution.
    - **Green**: Extend `_resolve_placeholder(repo_root: Path | None = None) -> dict[str, str]` in `cli/__init__.py`. Scan `pyproject.toml`: `[project].name` → PROJECT_NAME, `[project].dependencies` → backtick parsing for framework, `[tool.uv]` or `[tool.poetry]` → package manager, `[tool.pytest.ini_options]` → test runner. Accept `repo_root` param for test isolation. Per-variable fallback to `"UNKNOWN"` with `warnings.warn()`.
    - **Refactor**: Extract filesystem scanning into helper functions (`_scan_pyproject()`, `_scan_package_json()`) for testability. Keep REPO_ROOT as `str(Path.cwd())` default with `repo_root` override.
    - **Edge Cases**: No `pyproject.toml` → all non-REPO_ROOT vars UNKNOWN. Partial `pyproject.toml` → best-effort per HITL decision. `TARGET_COVERAGE_MINIMUM` defaults to `"80"` if unset. `package.json` fallback for non-Python projects.
    - **Acceptance**: AC-010-01, AC-010-02 pass. Performance: L_max <= 50ms. Unresolvable vars produce per-variable stderr warnings.

- [ ] TSK-001-05: Pytest JSON Report Support
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_micro.py -v`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/state/config.py`
    - `pyproject.toml`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: US-004 (FR-016) requires `_run_pytest()` to optionally use `--json-report` flag with JSON-based outcome classification, gated by `PytestReportConfig.json_report`. String parsing remains primary path. The `pytest-json-report` plugin is optional — missing plugin falls back gracefully with a warning.
  - **Details**:
    - **Red**: Write `test_run_pytest_json_report_enabled()` mocking `subprocess.run` and asserting `--json-report` appears in pytest args when `PytestReportConfig.json_report=True`. Write `test_run_pytest_json_report_fallback()` with `json_report=True` but missing plugin — assert warning logged and string parsing used. Write `test_run_pytest_json_report_disabled()` with `json_report=False` — assert no `--json-report` flag. Write `test_pytest_report_config_defaults()` asserting sensible defaults.
    - **Green**: Add `PytestReportConfig` Pydantic model to `state/config.py` with `json_report: bool = False`. In `_run_pytest()` in `micro.py`, conditionally append `--json-report` when config enabled. Update `_classify_pytest_outcome()` to parse JSON report when available, falling back to string parsing. Add `pytest-json-report` to `pyproject.toml` dev dependencies as optional.
    - **Refactor**: Keep string parsing as primary path per adversarial finding R10. Wrap JSON parsing in try/except — any JSON parse failure falls back to string parsing silently.
    - **Edge Cases**: Plugin not installed → warn + fall back to string parsing (no hard failure). JSON report has unexpected schema → fall back to string parsing. `json_report=True` but `--json-report` flag conflicts with other pytest args → last-flag-wins behavior is acceptable.
    - **Acceptance**: AC-016-01, AC-016-02 pass. Plugin missing does not break existing behavior. Performance: L_max <= 10ms overhead.

- [ ] TSK-001-06: E2E Integration Verification
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_core/test_profile.py tests/test_state/test_config.py tests/test_cli/test_common.py tests/test_cli/test_init.py tests/test_cli/test_micro.py tests/test_micro/test_run.py -v`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-001-01, TSK-001-02, TSK-001-03, TSK-001-04, TSK-001-05
  - **Files**:
    - (No file changes — verification-only task)
  - **Rationale**: All preceding tasks are individual units. This E2E task runs the full verification suite for ISS-002-001 to ensure no regression across all 4 user stories (US-001 through US-004) and their acceptance criteria, plus the full project-wide `mise run check` suite. No code changes — pure verification.
  - **Details**:
    - **Implementation**: Run `pytest tests/test_core/test_profile.py tests/test_state/test_config.py tests/test_cli/test_common.py tests/test_cli/test_init.py tests/test_cli/test_micro.py tests/test_micro/test_run.py -v` and verify all tests pass. Run `mise run check` to ensure lint, format, and type checks pass across the full project.
    - **Refactor**: If tests fail, identify the regressing task and report which task needs rework.
    - **Acceptance**: All targeted tests pass. `mise run check` green. No regression in pre-existing tests (full suite: `pytest tests/ -v`).

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Profile Module + Config) → Phase 2 (run_command profile flag)
2. Phase 1 (Config) → Phase 3 (PytestReportConfig reuses same config.py)
3. Phase 3 tasks (Placeholder, Pytest) can run in parallel after Phase 1
4. Phase 3 E2E runs last

**Critical Dependency Chains**:
- TSK-001-03 (run_command --profile) depends on TSK-001-01 (resolve_profile)
- TSK-001-05 (pytest report) depends on PytestReportConfig (state/config.py, shared with Phase 1)
- TSK-001-06 (E2E) depends on all TSK-001-01 through TSK-001-05

**Risk Hotspots**:
- `@with_json_quiet` decorator must not break Typer's signature introspection — verify all 6 pre commands still register correctly
- `resolve_profile()` override logic (`no_judge=False` means "DON'T skip judge") — boolean semantics must be crystal clear
- pytest-json-report plugin availability in CI — ensure fallback path is robust
- Placeholder resolution across diverse project configurations (Python, JS, monorepo)

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` — touched by TSK-001-03 (profile flag) and TSK-001-05 (pytest report). These modify different functions (_run_tdd_cycle vs _run_pytest), so conflicts are unlikely but coordinate between the two tasks.
- `src/deviate/state/config.py` — touched by TSK-001-01 (ProfileConfig) and TSK-001-05 (PytestReportConfig). Add new model classes, don't modify existing ones — no conflict expected.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal Test Performance Constraint (ALL TASKS)

- Never call `_run_pytest()` (in `src/deviate/cli/micro.py`) in tests. Tests that invoke CLI commands which internally call `_run_pytest` (red post, green post, refactor post) MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value.
- Performance target: full suite < 18s. If adding a test via `runner.invoke(cli, ["red", "post"])` and it calls `_run_pytest`, the test will trigger ALL pytest tests as a subprocess (~5s per invocation). Always mock it.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.
