---
title: "Slash Commands"
description: "Reference catalog of every DeviaTDD slash command — primary invocation, aliases, version, and purpose, grouped by product, macro, meso, micro, and tome layers."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: false
next: false
---

Slash commands are package resources at `src/deviate/prompts/commands/<name>.md`, installed by `deviate setup` to `<workdir>/.<agent>/commands/`. Each command ingests a JSON contract from a pre-script, executes its phase workflow, and writes the corresponding artifact.

## Product Layer

| Command | Aliases | Version | Purpose |
|---|---|---|---|
| `/deviate-flows` | `/flows`, `spec:flows`, `spec.flows` | 1.2.0 | FLOW-01 flows authoring — discover customer flows, write `flows-<domain>.md`, maintain `specs/_product/flows/index.md` |
| `/deviate-architecture` | `/architecture`, `spec:architecture`, `spec.architecture` | 1.0.0 | FLOW-02 architecture authoring — produce `specs/_product/architecture.md` and `domain-model.md` as cross-epic contracts (requires flows) |
| `/deviate-release` | `/release`, `spec:release`, `spec.release` | 1.0.0 | FLOW-03 release planning — compile the next coherent release from flows and architecture into `specs/_product/release-next.md` |

## Macro Layer

| Command | Aliases | Version | Purpose |
|---|---|---|---|
| `/deviate-init` | `/init`, `spec:init` | 1.0.0 | Initialize a repo with DeviaTDD conventions — `mise.toml` (zero-test-pass), `specs/` + `issues.jsonl`, `constitution.md` scaffold |
| `/deviate-explore` | `/explore`, `spec:full:explore` | 2.0.0 | Read-only structural scan of the codebase; emits raw `explore.md` (what exists, not what to do) |
| `/deviate-research` | `/research`, `spec:full:research`, `tools:research` | 2.0.0 | Architectural analysis — produce `design.md` (options, trade-offs, risk register) and `data-model.md` from `explore.md` |
| `/deviate-prd` | `/deviate-prd`, `spec:full:prd`, `spec.full.prd` | 1.0.0 | Compile `explore.md` into `prd.md` — the singular source of truth for downstream sharding into `specs/issues.jsonl` |
| `/deviate-shard` | `/deviate-shard`, `/shard`, `spec:full:shard` | 1.0.0 | Decompose `prd.md` into self-contained Feature Vertical issues registered in `specs/issues.jsonl` with a DAG dependency topology |
| `/deviate-constitution` | `/deviate-constitution`, `spec:constitution`, `spec.constitution` | 1.0.0 | Initialize or update `specs/constitution.md` — the authoritative governance artifact defining tech stack, testing mandates, and DoD |
| `/deviate-triage` | `/deviate-triage`, `spec:triage`, `spec.triage` | 1.0.0 | Classify requirements against fixed predicates (FULL, CORE, TDD, NONE) for deterministic workflow routing |
| `/deviate-adhoc` | `/deviate-adhoc`, `spec:adhoc`, `spec.adhoc` | 1.0.0 | Emit a single ad-hoc vertical-slice issue from a natural-language task with lightweight discovery, shared PRD tracking, and `flow_refs` |
| `/deviate-hotfix` | `/hotfix`, `/spec.hotfix` | 1.0.0 | Decompose bug reports into autonomous Red-Green-Refactor hotfix units |

## Meso Layer

| Command | Aliases | Version | Purpose |
|---|---|---|---|
| `/deviate-plan` | `/deviate-plan`, `/plan`, `spec:core:plan`, `spec.core.plan` | 1.0.0 | Per-issue localized research — scan codebase and prior implementations; produce `plan.md` with strategy, file mappings, and risks |
| `/deviate-tasks` | `/deviate-tasks`, `/tasks`, `spec:core:tasks`, `spec.core.tasks` | 1.0.0 | Decompose a spec-enriched issue into `tasks.md` — autonomous Red-Green-Refactor units (vertical, 30-90 min each) |
| `/deviate-review` | `/deviate-review`, `/review` | 2.0.0 | HITL Gate 3 PR review — structured scan across Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD, and Flow Coverage |
| `/deviate-pr` | `/deviate-pr`, `tools:pr` | 1.0.0 | Create a PR from the current worktree branch; on merge, append `COMPLETED` to `specs/issues.jsonl` to unblock dependents |

## Micro Layer

| Command | Aliases | Version | Purpose |
|---|---|---|---|
| `/deviate-red` | `/red`, `/spec.tdd.red`, `/tdd.red` | 1.0.0 | RED phase — write the failing test for a single TDD task |
| `/deviate-green` | `/green`, `/spec.tdd.green`, `/tdd.green` | 1.0.0 | GREEN phase — minimal implementation that passes the failing test |
| `/deviate-yellow` | `/yellow`, `/spec.tdd.yellow`, `/tdd.yellow` | 1.0.0 | YELLOW phase — evaluate proposed test changes from the GREEN phase for conditional amendment |
| `/deviate-judge` | `/judge`, `/tdd.judge` | 1.1.0 | JUDGE phase — review GREEN implementation against `spec.md` for correctness and integrity; emit `COMPLIANCE_PASS` |
| `/deviate-refactor` | `/refactor`, `/spec.tdd.refactor`, `/tdd.refactor` | 1.0.0 | REFACTOR phase — behavior-preserving structural improvement after tests pass |
| `/deviate-prune` | `/prune`, `/spec.tdd.prune`, `/tdd.prune` | 1.0.0 | PRUNE phase — remove implementation-coupled and redundant tests while preserving public behavioral contracts |
| `/deviate-execute` | `/x`, `/spec.execute` | 1.0.0 | Direct task execution (no TDD cycle) for low-complexity tasks, trivial changes, docs, or refactors with existing coverage |
| `/deviate-e2e` | `/e2e`, `/spec.tdd.e2e`, `/tdd.e2e` | 1.0.0 | Run final E2E verification after all tasks complete — user-facing tests confirming the feature meets intent |

## Tome Layer

| Command | Aliases | Version | Purpose |
|---|---|---|---|
| `/tome-classify` | `/tome-classify`, `spec:classify`, `spec.classify`, `spec:tome-classify`, `spec.tome-classify` | 1.2.0 | C1 — ingest commit, branch, or whole-codebase evidence; emit Diátaxis classification with IA fields (`layer_order`, `parent`, `next`, `group`) |
| `/tome-setup` | `/tome-setup`, `spec:setup`, `spec.setup`, `spec:tome-setup`, `spec.tome-setup` | 1.2.0 | C7 — idempotent bootstrap of `apps/docs/` with Starlight, the four Diátaxis quadrants, theme sub-dirs, and `content.config.ts` extending `docsSchema()` |
| `/tome-verify-docs` | `/tome-verify-docs`, `spec:verify-docs`, `spec.verify-docs`, `spec:tome-verify-docs`, `spec.tome-verify-docs` | 1.2.0 | C6 — read-only cross-doc verification over C2-C5 outputs (factual consistency, paths, Diátaxis purity, IA reachability, length budget) |
| `/tome-write-tutorial` | `/tome-write-tutorial`, `spec:write-tutorial`, `spec.write-tutorial`, `spec:tome-write-tutorial`, `spec.tome-write-tutorial` | 1.2.0 | C2 — write one tutorial page when `tome-classify` selects tutorial |
| `/tome-write-how-to` | `/tome-write-how-to`, `spec:write-how-to`, `spec.write-how-to`, `spec:tome-write-how-to`, `spec.tome-write-how-to` | 1.2.0 | C3 — write one how-to page when `tome-classify` selects how-to |
| `/tome-write-reference` | `/tome-write-reference`, `spec:write-reference`, `spec.write-reference`, `spec:tome-write-reference`, `spec.tome-reference` | 1.2.0 | C4 — write one reference page when `tome-classify` selects reference |
| `/tome-write-explanation` | `/tome-write-explanation`, `spec:write-explanation`, `spec.write-explanation`, `spec:tome-write-explanation`, `spec.tome-write-explanation` | 1.2.0 | C5 — write one explanation page when `tome-classify` selects explanation |

## Invocation Contract

| Field | Value |
|---|---|
| Source path | `src/deviate/prompts/commands/<name>.md` (package resource) |
| Install path | `<workdir>/.<agent>/commands/<name>.md` (per agent: opencode, claude, pi) |
| Install command | `deviate setup` |
| Pre-script | `deviate <phase> pre` — emits JSON contract on stdout |
| Post-script | `deviate <phase> post` — validates, stages, commits |
| Argument source | `<user_input>` block (verbatim `$ARGUMENTS` substitution) |
| Layer routing | `src/deviate/prompts/assembly.py::_LAYER_MAP` |
| Frontmatter required | `name`, `description`, `category`, `version`, `aliases` |

Example:

```
deviate setup    # install all 31 slash commands to <workdir>/.<agent>/commands/
/deviate-init    # run a command in the agent's chat
```

## See Also

- [Reference: introduction](/reference/index) — quadrant navigation pivot for all reference families
- [Tutorial: starter-first-run](/tutorials/starter-first-run) — guided walk through the slash-command lifecycle
- [How-To: getting-started/init](/how-to/getting-started/init) — operational steps to run `/deviate-init`
- [Explanation: introduction](/explanation/index) — why-frames for layer ordering and HITL gates
- [Reference: CLI](/reference/cli/inspect-issues) — companion surface for the `deviate <subcommand>` CLI flags