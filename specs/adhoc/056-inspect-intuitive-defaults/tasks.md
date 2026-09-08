# Implementation Tasks: `feat/adhoc/056-inspect-intuitive-defaults`

## Phase 1: Bare issues group defaults to list
**Goal**: Bare `deviate inspect issues` renders the same issues table as the explicit list command

### Tasks

- TSK-056-01: Bare inspect issues lists table with flags and error path
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_inspect.py`
    - `src/deviate/cli/inspect.py`
  - **Rationale**: `US-056-01` with `AC-PLAN-001` and `AC-PLAN-002` need the issues group callback; tests encode the bare-form user scenario, implementation adds the `invoke_without_command` callback that delegates to the shared list render path.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_cli/test_inspect.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert `runner.invoke(cli, ["inspect", "issues"])` exits 0 and matches `["inspect", "issues", "list"]` table output; assert `--type`/`--status`/`--json` flags filter identically on the bare form; assert malformed `specs/issues.jsonl` fails non-zero on the bare form.
    - **Green**: Implement issues group callback on `issues_app` with `invoke_without_command=True`, accept `--type`/`--status`/`--json`/`--quiet` options, delegate to `_issues_list` render path shared with `issues_list_command`.
    - **Refactor**: Share one render helper between callback and `list` command; keep `inspect_app` as `no_args_is_help=True` with no callback.
    - **Edge Cases**: Handle missing ledger with the current readable error; handle empty ledger identically to `list`.
    - **Acceptance**: Bare and explicit issues forms produce byte-identical output for the same flags; existing suite passes.

---

## Phase 2: Bare tasks group defaults to list
**Goal**: Bare `deviate inspect tasks` renders the same tasks table as the explicit list command

### Tasks

- TSK-056-02: Bare inspect tasks lists table with flags and warn-skip path
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_inspect.py`
    - `src/deviate/cli/inspect.py`
  - **Rationale**: `US-056-02` with `AC-PLAN-003` and `AC-PLAN-004` need the tasks group callback; tests encode the bare-form user scenario, implementation adds the `invoke_without_command` callback that delegates to the shared tasks render path.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_cli/test_inspect.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert `runner.invoke(cli, ["inspect", "tasks"])` exits 0 and matches `["inspect", "tasks", "list"]` table output; assert `--status`/`--json` flags filter identically on the bare form; assert malformed per-issue ledger warns and skips on the bare form.
    - **Green**: Implement tasks group callback on `tasks_app` with `invoke_without_command=True`, accept `--status`/`--json`/`--quiet` options, delegate to `_tasks_list` render path shared with `tasks_list_command`.
    - **Refactor**: Share one render helper between callback and `list` command; preserve `COMPLETED`-sticky aggregation and sort order.
    - **Edge Cases**: Handle missing `specs/issues.jsonl` as empty list; handle malformed per-issue ledger with warn-and-skip, not abort.
    - **Acceptance**: Bare and explicit tasks forms produce byte-identical output for the same flags; existing suite passes.
  - **Dependency**: TSK-056-01

---

## Phase 3: Explicit paths and help text stay consistent
**Goal**: Explicit `list`/`show` commands and help text keep current behavior with documented bare defaults

### Tasks

- TSK-056-03: Explicit commands keep flags and group help documents defaults
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `tests/unit/test_cli/test_inspect.py`
    - `src/deviate/cli/inspect.py`
  - **Rationale**: `US-056-01` and `US-056-02` with `AC-PLAN-005` guard against callback regressions; tests pin explicit and help behavior, implementation updates group help text to describe the bare defaults.
  - **Details**:
    - **Red**: Write failing tests in `tests/unit/test_cli/test_inspect.py` only — forbid `tests/integration/` and `tests/e2e/`. Assert explicit `issues list`, `issues show`, `tasks list`, `tasks show` keep current flags and output shapes; assert bare `deviate inspect` still shows group help; assert `issues --help` and `tasks --help` mention the bare-list default.
    - **Green**: Update `issues_app`/`tasks_app` help text to describe bare defaults; leave `inspect_app` callback-free so bare `inspect` shows help.
    - **Refactor**: Keep help wording short and consistent across both groups; no new dependencies or config keys.
    - **Edge Cases**: Handle `--help` on every level without invoking list rendering or ledger reads.
    - **Acceptance**: Explicit commands unchanged, bare `inspect` shows help, group help documents defaults.
  - **Dependency**: TSK-056-02

- TSK-056-04: Full verification ladder for inspect defaults
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/cli/inspect.py`
    - `tests/unit/test_cli/test_inspect.py`
  - **Rationale**: Closing verification for `US-056-01` and `US-056-02` across `AC-PLAN-001` through `AC-PLAN-005`; runs the existing suite with no new tests to catch regressions from the new callbacks.
  - **Details**:
    - **Implementation**: Run `mise unit`; run `mise lint` and `mise format-check` when available; confirm bare-vs-explicit parity manually for one table and one `--json` case per group.
    - **Refactor**: No production changes unless the ladder fails.
    - **Edge Cases**: Missing or empty ledgers still match `list` behavior on both bare forms.
    - **Acceptance**: `mise unit` exits 0; bare and explicit forms agree; help text documents defaults.
  - **Dependency**: TSK-056-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (Logical dependency order)

**Critical Dependency Chains**:
- TSK-056-01 must precede TSK-056-02
- TSK-056-02 must precede TSK-056-03
- TSK-056-03 must precede TSK-056-04

**Risk Hotspots**:
- Typer callback signature drift duplicates list options; share one render helper
- Bare `inspect` with no group must keep showing help; leave `inspect_app` callback-free

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/inspect.py`, `tests/unit/test_cli/test_inspect.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
