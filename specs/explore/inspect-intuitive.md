## Problem Definition
**Statement**: Make `deviate inspect` intuitive to use for review of issues and tasks.
**Scope**: The `inspect` command group covers `issues` and `tasks` list and show paths.
**Exclusions**: No change to ledger write paths, phase workflows, or agent prompts.

## Discovery Audit Results
### Verified Dependencies
The project declares `typer` and `rich` as runtime dependencies. The scan confirms `typer` builds the CLI. The scan confirms `rich` renders the tables.
### Ghost Dependencies
None observed. The scan finds no import that lacks a manifest entry.
### Manifest Files Observed
The scan finds `pyproject.toml` as the package manifest. The scan finds `.mise.toml` as the task runner. The scan finds `specs/constitution.md` as the governance file.
### Test Runner Configuration
The project uses `pytest` with root `tests/`. The constitution sets the test command to `pytest tests/ -v`. The constitution sets the lint command to `ruff check .`.
### Manifest-Constitution Divergence
None observed. The manifest declares `typer` and `rich`. The constitution names `Typer` with `Rich` for terminal I/O.

## Constitution Quotes
- **Architectural Principles**: "**Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Tech Stack Standards**: "- Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Testing Protocols**: "- Test command: `pytest tests/ -v`"
- **Definition of Done**: "- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt"

## Architectural Baselines
- **Existing Architectural Patterns**
The CLI registers one `Typer` app per command group. The root `cli` adds `inspect_app` under name `inspect`. Each subgroup uses `no_args_is_help=True`.
- **Infrastructure & Operations**
The project runs on local host with `uv`, `mise`, `pytest`, `ruff`, and `bats`. The scan finds no container target.
- **Data & State Management**
State lives in append-only JSONL ledgers. The issue ledger is `specs/issues.jsonl`. Task ledgers live per issue at `specs/<bucket>/<slug>/tasks.jsonl`.
- **Quality, Safety & Observability**
Tests live under `tests/` with `tests/unit/test_cli/test_inspect.py` for inspect. Lint uses `ruff`. The quality gate is `mise run check`.
- **External Integrations**
None observed for inspect. The sandbox uses the `aider` Python API. No third-party API client serves inspect.

## Sibling Flow Inventory
The nearest sibling is `deviate specify` with a bare-arg default. It claims the next unblocked issue with no ID. It shows the desired discoverable pattern.

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | src/deviate/cli/inspect.py |
| Lock vs reserve | none observed | src/deviate/cli/inspect.py |
| Vendor call | none observed | src/deviate/cli/inspect.py |
| Idempotency | read-only ledger parse, no writes | src/deviate/cli/inspect.py |
| Destination shape | typed Rich table plus `--json` array | src/deviate/cli/inspect.py |

## Ecosystem Research
Catalog only. Later phases must not treat these rows as Required unless a local flow, constitution clause, or money/auth/provider integrity test applies.
- **Best Practices**
Typer documents `no_args_is_help` to show help when the user gives no args (https://typer.tiangolo.com/reference/typer/). Typer supports `callback(invoke_without_command=True)` to run a default action for a bare group (https://stackoverflow.com/questions/79486643/python-command-line-tool-with-subcommands-in-typer-how-do-i-include-a-typer-in).
- **Common Use Cases & Pitfalls**
CLI guides state the bare group name must do the common read action. Help stays behind `--help`. The clig.dev guide codifies this default-action rule (https://clig.dev/).
- **Standard Tooling**
`typer` plus `rich` already cover defaults and tables. No new tool is required.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| src/deviate/cli/inspect.py | source | Issues and tasks list and show commands | `inspect_app = typer.Typer(no_args_is_help=True)` |
| src/deviate/cli/inspect.py | source | Issues and tasks subgroups require explicit verb | `issues_app = typer.Typer(no_args_is_help=True)` |
| src/deviate/cli/inspect.py | source | Tasks subgroup requires explicit verb | `tasks_app = typer.Typer(no_args_is_help=True)` |
| src/deviate/cli/inspect.py | source | Issues list implementation with type and status filters | `@issues_app.command("list")` |
| src/deviate/cli/inspect.py | source | Tasks list implementation with status filter | `@tasks_app.command("list")` |
| src/deviate/cli/__init__.py | source | Root registration of inspect group | `inspect_app,` |
| src/deviate/cli/__init__.py | source | Inspect help text on root CLI | `help="Inspect issue and task ledgers",` |
| tests/unit/test_cli/test_inspect.py | test | Pinned tests for issues and tasks list and show | `result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])` |
| pyproject.toml | manifest | Runtime dependencies and pytest config | `"pytest>=8.0",` |
| specs/constitution.md | governance | Tech stack and ledger rules | `- Framework: Typer (CLI entry points) with Rich for terminal I/O` |
| specs/DeviaTDD-api.md | spec | Authoritative CLI command contract | `deviate inspect tasks list` |
| CHANGELOG.md | changelog | User-visible change history | `deviate inspect tasks list` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Low |
| Files Likely Modified | 3 — src/deviate/cli/inspect.py, src/deviate/cli/__init__.py, tests/unit/test_cli/test_inspect.py |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Help text in specs/DeviaTDD-api.md plus CHANGELOG.md Unreleased entry |
| Rationale | The change adds bare-group defaults on one file. No new state exists. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | inspect-intuitive |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/inspect-intuitive.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
