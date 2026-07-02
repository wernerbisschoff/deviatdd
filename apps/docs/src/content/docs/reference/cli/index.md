---
title: "CLI"
description: "Reference for the `deviate` CLI — top-level flags, bootstrap commands, macro/meso/micro phase commands, inspection, and review."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: false
next: apps/docs/src/content/docs/reference/cli/inspect-issues.md
---

The `deviate` CLI is a Typer application rooted at `src/deviate/cli/__init__.py`; every phase of the macro/meso/micro pipeline is exposed as a subcommand, with command registration listed at `src/deviate/cli/__init__.py:773-799`.

## Top-level Flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--version` | `bool` | `false` | Print the installed `deviate` version and exit (handled eagerly by `cli.callback`). |

## Bootstrap & Governance

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate init` | Typer sub-group | `pre`, `post` | Initialize a project; detect project type and scaffold the DeviaTDD structure. |
| `deviate setup` | Flat command | — | Legacy flat alias for `deviate init`; equivalent behavior, idempotent. |
| `deviate constitution` | Typer sub-group | `generate`, `pre`, `post` | Manage `specs/constitution.md` — LLM-generate, pre-flight validate, post-commit. |

## Macro Layer

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate explore` | Typer sub-group | `pre`, `post` | Allocate a feature bucket and capture `explore.md`. |
| `deviate research` | Typer sub-group | `pre`, `post` | Produce `design.md` and `data-model.md`. |
| `deviate prd` | Typer sub-group | `pre`, `post` | Synthesize `prd.md` from the design artifacts. |
| `deviate shard` | Typer sub-group | `pre`, `post` | Decompose PRD into spec-enriched issue files. |
| `deviate adhoc` | Typer sub-group | `pre`, `post` | Compressed single-issue workflow with complexity gate. |
| `deviate feature` | Typer sub-group | `create` | Create a feature workspace, branch, and bucket directory. |
| `deviate macro` | Typer sub-group | `run` | Automate the explore→research→prd→shard pipeline. |

## Meso Layer

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate specify` | Flat command | — | Legacy: claim an issue and create a linked worktree. |
| `deviate plan` | Flat command | — | Per-issue localized research; emits `plan.md`. |
| `deviate tasks` | Flat command | — | Decompose issue into tasks; emits `tasks.md` and `tasks.jsonl`. |
| `deviate pr` | Flat command | — | Create a GitHub PR via `gh pr create`. |
| `deviate meso` | Typer sub-group | `run` | Automate the specify→plan→tasks pipeline. |

## Micro Layer

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate red` | Typer sub-group | `pre`, `post` | TDD red phase; failing test must be authored. |
| `deviate green` | Typer sub-group | `pre`, `post` | TDD green phase; implementation passes the red test. |
| `deviate yellow` | Typer sub-group | `pre`, `post` | Optional amendment gate; commit on `--approved`, revert on `--rejected`. |
| `deviate judge` | Typer sub-group | `pre` | Compliance judgment against `spec.md`. |
| `deviate refactor` | Typer sub-group | `pre`, `post` | TDD refactor phase; regression-checked via pytest before/after. |
| `deviate execute` | Typer sub-group | `pre`, `post` | DIRECT-mode execution; bypasses the RED phase. |
| `deviate e2e` | Typer sub-group | `pre`, `post` | End-to-end verification across all tasks. |
| `deviate hotfix` | Typer sub-group | `pre`, `post` | Bug fix workflow; bypasses the RED phase. |

## Task Runners

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate run` | Flat command | — | Drive the RED→GREEN→[YELLOW?]→JUDGE→REFACTOR cycle for a single task or `--all` tasks of the active issue. |

## Inspection & Diagnostics

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate inspect` | Typer sub-group | `issues list`, `tasks list` | Read `specs/issues.jsonl` and `tasks.jsonl`; render Rich table or JSON array, filter by `--type` / `--status`. |

Per-command reference:

- [deviate inspect issues](./inspect-issues) — flags, status filters, JSON output, and `ORPHAN_CLAIM` detection
- [deviate inspect tasks](./inspect-tasks) — flags, status filters, JSON output, and the project-root `tasks.jsonl` ledger

## Code Review & Quality

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate review` | Typer sub-group | `pre`, `post` | Gather diff and governance context for HITL Gate 3 review. |

## Tome Subsystem

| Command | Registration | Subcommands | Description |
|---|---|---|---|
| `deviate tome` | Typer sub-group | `write`, `list` | Invoke Tome writer and verifier skills. |

## See Also

- [deviate inspect issues](./inspect-issues) — starter reference for the CLI family (next page in the IA chain)
- [Tutorials: a guided tour](/tutorials/) — walks the macro/meso/micro pipeline end-to-end
- [How-To: accomplish a specific task](/how-to/) — recipes for `deviate init`, `deviate run`, recovery flows
- [Explanation: understand the why](/explanation/) — design rationale for the macro/meso/micro layer split this CLI implements