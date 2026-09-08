---
title: "List issues and tasks from bare inspect groups"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-056
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/056-inspect-intuitive-defaults.md`
- **Primary Architectural Workstation**: `src/deviate/cli/inspect.py`, `src/deviate/cli/__init__.py`, `tests/unit/test_cli/test_inspect.py`

## The Problem Contract
Bare `deviate inspect issues` prints help instead of the issues list. Users memorize the `list` verb before they review any status. This issue makes the bare group names list records.

## Scope Boundaries
### Hard Inclusions
- Bare `deviate inspect issues` renders the same output as `deviate inspect issues list`
- Bare `deviate inspect tasks` renders the same output as `deviate inspect tasks list`
- Explicit `list` and `show` paths keep current flags and output shapes
- Root `deviate --help` and `deviate inspect --help` text describe the bare defaults

### Defensive Exclusions
- No change to ledger write paths or append-only parse rules
- No change to phase workflows, agent prompts, or session handling
- No new persistence, config keys, or external integrations

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-056`
- **Acceptance Criteria Tokens**: `AC-ADHOC-056-01`, `AC-ADHOC-056-02`
- **Data Model Entities**: IssueRecord ledger rows, per-issue task ledger rows

## User Stories Ledger
- **US-056-01**: As a CLI user, I want bare `deviate inspect issues` to list issues so that I review statuses without memorizing subcommands. *(Ref: FR-ADHOC-056)*
- **US-056-02**: As a CLI user, I want bare `deviate inspect tasks` to list tasks so that I review task state with one command. *(Ref: FR-ADHOC-056)*

## Acceptance Outline
- **AO-056-01** *(Ref: AC-ADHOC-056-01, US-056-01)*: Bare `deviate inspect issues` renders the issues table
  - **Happy Path**: User runs `deviate inspect issues` and sees ID, Type, Title, Status columns
  - **Error Category**: Missing `specs/issues.jsonl` surfaces the current readable error path
  - **Boundary Category**: `--type`, `--status`, `--json` flags work on the bare form
- **AO-056-02** *(Ref: AC-ADHOC-056-02, US-056-02)*: Bare `deviate inspect tasks` renders the tasks table
  - **Happy Path**: User runs `deviate inspect tasks` and sees ID, Issue ID, Description, Status columns
  - **Error Category**: Malformed per-issue ledger keeps the current warn-and-skip path
  - **Boundary Category**: `--status` and `--json` flags work on the bare form

## Edge Cases and Boundaries
- Bare `deviate inspect` with no group still shows group help
- `deviate inspect issues --help` still shows the command list including `list` and `show`
- Empty ledgers render empty tables, matching current `list` output

## Performance Constraints
- L_max: 500ms for list render on a typical ledger
- Throughput: single invocation, no batch path

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_cli/test_inspect.py` — bare issues form emits table, bare tasks form emits table, explicit `list` and `show` paths unchanged
- **Integration Sandbox Targets**: `deviate inspect issues`, `deviate inspect tasks`, `deviate inspect issues list`, `deviate inspect tasks list` against a seeded ledger

## Demonstration Path
```bash
deviate inspect issues
deviate inspect tasks
deviate inspect issues list --json
deviate inspect tasks list --json
```
