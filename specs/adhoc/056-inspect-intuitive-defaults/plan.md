## Plan Summary
- **Issue**: ISS-ADH-056 — List issues and tasks from bare inspect groups
- **Implementation Strategy**: Add `invoke_without_command` callbacks on the issues and tasks Typer groups that delegate to the existing list commands; keep bare `inspect` as help and update help text to describe the defaults.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Bare inspect issues renders issues table**
- **Source Outline**: `AO-056-01`
- **Upstream Traceability**: `US-056-01`, `FR-ADHOC-056`, `AC-ADHOC-056-01`
- **Current-Code Evidence**: `src/deviate/cli/inspect.py:issues_app`
- **Given**: A seeded `specs/issues.jsonl` ledger exists
- **When**: The user runs `deviate inspect issues` with no subcommand
- **Then**: The command renders the ID, Type, Title, Status columns matching `list` output
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Bare inspect issues honors list flags and error path**
- **Source Outline**: `AO-056-01`
- **Upstream Traceability**: `US-056-01`, `FR-ADHOC-056`, `AC-ADHOC-056-01`
- **Current-Code Evidence**: `src/deviate/cli/inspect.py:issues_list_command`
- **Given**: The issues group callback forwards options to the list command
- **When**: The user runs bare `deviate inspect issues` with `--type`, `--status`, or `--json`
- **Then**: The output filters identically to `deviate inspect issues list` and a missing ledger surfaces the current readable error
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Bare inspect tasks renders tasks table**
- **Source Outline**: `AO-056-02`
- **Upstream Traceability**: `US-056-02`, `FR-ADHOC-056`, `AC-ADHOC-056-02`
- **Current-Code Evidence**: `src/deviate/cli/inspect.py:tasks_app`
- **Given**: Seeded per-issue `tasks.jsonl` ledgers exist
- **When**: The user runs `deviate inspect tasks` with no subcommand
- **Then**: The command renders the ID, Issue ID, Description, Status columns matching `list` output
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Bare inspect tasks honors list flags and warn-skip path**
- **Source Outline**: `AO-056-02`
- **Upstream Traceability**: `US-056-02`, `FR-ADHOC-056`, `AC-ADHOC-056-02`
- **Current-Code Evidence**: `src/deviate/cli/inspect.py:tasks_list_command`
- **Given**: The tasks group callback forwards options to the list command
- **When**: The user runs bare `deviate inspect tasks` with `--status` or `--json`
- **Then**: The output filters identically to `deviate inspect tasks list` and a malformed per-issue ledger keeps the warn-and-skip path
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Explicit paths and help text stay consistent**
- **Source Outline**: `AO-056-01`, `AO-056-02`
- **Upstream Traceability**: `US-056-01`, `FR-ADHOC-056`, `AC-ADHOC-056-01`
- **Current-Code Evidence**: `src/deviate/cli/inspect.py:inspect_app`
- **Given**: The issues and tasks groups gain default callbacks
- **When**: The user runs explicit `list` or `show` commands or requests `--help`
- **Then**: Explicit commands keep current flags and output shapes, bare `deviate inspect` still shows group help, and group help text describes the bare defaults
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/inspect.py**: Role in this issue — add default callbacks to issues and tasks groups
  - **Current State**: `issues_app` and `tasks_app` use `no_args_is_help=True` with only `list` and `show` commands, so bare invocations print help
  - **Changes Required**: Add `invoke_without_command=True` callbacks that delegate to `_issues_list` / `_tasks_list` render paths with the same options as the `list` commands
  - **Integration Surface**: `issues_list_command`, `tasks_list_command`, `_issues_list`, `_tasks_list`, Typer group registration
- **src/deviate/cli/__init__.py**: Role in this issue — verify inspect group wiring needs no change
  - **Current State**: Registers `inspect_app` with `name="inspect"`
  - **Changes Required**: None expected unless help text lives at registration
  - **Integration Surface**: `inspect_app` import and `add_typer` call
- **tests/unit/test_cli/test_inspect.py**: Role in this issue — RED/GREEN verification target
  - **Current State**: Covers explicit `issues list` and `tasks list` paths via CliRunner
  - **Changes Required**: No plan change; RED adds bare-form cases here
  - **Integration Surface**: `deviate.cli.cli` entry point, seeded JSONL ledgers

## Implementation Strategy
- **Phase 1**: Default callbacks delegate to list rendering
  - **Files**: `src/deviate/cli/inspect.py`
  - **Approach**: Set `invoke_without_command=True` on `issues_app` and `tasks_app` with group callbacks accepting the same `--type/--status/--json/--quiet` options and calling the shared list helpers; extract shared render helpers if needed to avoid duplication
  - **Verification**: `runner.invoke(cli, ["inspect", "issues"])` equals `["inspect", "issues", "list"]` output; same for tasks; existing test suite passes

## Data Flow Analysis
- Bare `deviate inspect issues` enters the issues group callback, reads `specs/issues.jsonl` via `_read_ledger_strict`, deduplicates via `_deduplicate_issues`, applies filters, and renders the Issues table or JSON. Bare `deviate inspect tasks` enters the tasks group callback, aggregates per-issue `tasks.jsonl` via `_tasks_list`, applies the status filter, and renders the Tasks table or JSON. No writes occur on either path.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Typer callback signature drift duplicates list options | Medium | Medium | Share one render helper between callback and `list` command |
| Bare `inspect` with no group changes behavior | Low | Low | Leave `inspect_app` as `no_args_is_help=True` without a callback |
| Empty or missing ledger output diverges from `list` | Low | Low | Delegate to the same code path, not a copy |

## Security Profile
Risk surfaces: file paths (ledger paths under `specs/`), deserialization (JSONL ledger parse)
Negative tests: malformed `specs/issues.jsonl` fails with readable error on bare form, malformed per-issue tasks ledger warns and skips on bare form
Constraints: no new dependencies, no ledger writes, no config keys

## Integration Points
- **`deviate inspect issues list`**: Bare issues form must produce byte-identical output for the same flags
- **`deviate inspect tasks list`**: Bare tasks form must produce byte-identical output for the same flags
- **`deviate inspect --help` / `deviate --help`**: Help text documents the bare-group defaults

## Constitutional Alignment
- Micro-Layer Scope: GREEN writes only to `src/` implementation paths.
- User Scenarios Are the Flow: RED encodes `US-056-01` and `US-056-02` bare-list scenarios as failing tests.
- Three-Layer Architecture: Plan owns the finalized Gherkin Acceptance Contract for Tasks and JUDGE.
