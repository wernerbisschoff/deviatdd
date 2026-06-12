The `deviate` CLI lacked profile-based execution dispatch, cross-cutting JSON/quiet output flags, full placeholder variable resolution, and optional pytest JSON report support. This PR implements all four features as an atomic vertical slice, enabling developers to skip JUDGE/REFACTOR phases via `--profile fast`, pipe JSON contracts from `pre` subcommands, resolve 6 `${VARIABLE}` placeholders from filesystem heuristics, and gate pytest JSON report classification via config.

**Profile dispatch** (`core/profile.py`, `state/config.py`): `ExecutionProfile` type alias with `resolve_profile()` — profile defaults with composable boolean overrides, `ProfileConfig` TOML section for persisted defaults.

**JSON/Quiet output** (`cli/_common.py`): `@with_json_quiet` decorator injects `--json` (raw contract on stdout) and `--quiet` (suppress Rich, preserve stderr) — orthogonal flags wired to all 6 `pre` subcommands (macro, meso, context, adhoc, constitution).

**run_command profile flag** (`cli/micro.py`): `--profile` Typer option with explicit `--no-judge`/`--no-refactor` overrides; invalid profile values produce Typer validation errors, not `ValueError`.

**Placeholder resolution** (`cli/__init__.py`): Extended `_resolve_placeholder()` from 2 to 6 variables — `PROJECT_NAME`, `REPO_ROOT`, `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`, `TARGET_COVERAGE_MINIMUM`. Best-effort per-variable filesystem heuristics; unresolved variables emit per-variable stderr warning and fall back to `"UNKNOWN"`.

**Pytest JSON report** (`cli/micro.py`, `state/config.py`): `PytestReportConfig.json_report` gates optional `--json-report` flag. JSON classification when plugin available, graceful fallback to string parsing when missing. No hard failure on missing plugin.

**Tests**: Full coverage across profile dispatch, json/quiet decorator, run_command profile integration, placeholder resolution (complete, partial, missing config), and pytest report config — all verifying acceptance criteria from spec.md US-001 through US-004.
