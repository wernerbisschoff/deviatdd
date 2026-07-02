---
title: "Run /deviate-research"
description: "How to consume an approved explore.md and produce design.md + data-model.md, the inputs to HITL Gate 1."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: false
next: prd.md
---

This how-to covers the macro-layer `/deviate-research` phase: consuming an approved `explore.md`, performing architectural trade-off analysis, and producing `design.md` (options matrix, recommended architecture, risk register, constitutional audit) and `data-model.md` (entities, relationships, schemas, state transitions). Run it after `/deviate-explore` has committed `explore.md`; the artifacts are the inputs to HITL Gate 1 before `/deviate-prd` may proceed.

## Prerequisites

- `/deviate-explore` completed: `specs/explore/<slug>.md` exists on the feature branch
- A clean working tree — the post-script runs pre-commit hooks before committing
- A 180s timeout available for the post-script (pre-commit runs the full test suite)
- `specs/constitution.md` either present or ready to be bootstrapped (greenfield flow)

## Steps

### 1. Run `/deviate-research`

Inside the agent on the feature branch, run `/deviate-research`. The slash command invokes `deviate research pre`, which resolves the latest `specs/explore/<slug>.md`, validates the constitution, allocates a numbered epic bucket at `specs/NNN-<slug>/`, transitions the session to `RESEARCH`, and emits a JSON contract carrying `design_target` and `data_model_target`.

### 2. Wait for the agent to produce the artifacts

The orchestrating agent reads `explore.md` and the constitution, dispatches three parallel subagent forks (Alpha: architecture options, Beta: data modeling, Gamma: adversarial audit), merges their fragments into `design.md` and `data-model.md`, and populates the `## Pending HITL Decisions` table with every decision that reverses the explore brief, rejects an explicitly requested tool, or otherwise needs human judgment.

### 3. Resolve HITL Gate 1

Open `specs/NNN-<slug>/design.md` and review the `## Pending HITL Decisions` table. For each `PENDING` row, either set its `Status` to `RESOLVED` (accepting the recommended resolution) or amend the design. The agent uses the `question` tool to surface key decisions interactively. `/deviate-prd` will block until every row is `RESOLVED`.

### 4. Wait for the post-script to validate and commit

The agent invokes `deviate research post`, which validates both files via `validate_artifact()` (required sections, non-empty content), runs pre-commit hooks, and creates a single commit with message `docs({epic_id}): add research artifacts (design.md, data-model.md)`. The session transitions back to `IDLE`.

### 5. Verify the change

```bash
ls specs/<NNN>-<slug>/
git log --oneline -3
grep -E "RESOLVED|PENDING" specs/<NNN>-<slug>/design.md
```

Expected: both `design.md` and `data-model.md` exist in the numbered epic bucket, no rows remain `PENDING`, and a new commit is on the feature branch.

## Troubleshooting

### `EXPLORE_NOT_FOUND`

`specs/explore/<slug>.md` is missing. Run `/deviate-explore` first to produce the factual baseline, then re-invoke `/deviate-research`.

### `MISSING_CONSTITUTION_SECTIONS`

The constitution is missing `Architectural Principles` or `Testing Protocols` — the constitutional alignment audit cannot proceed. Amend `specs/constitution.md` to populate those sections, then re-run.

### `CONSTITUTIONAL_VIOLATION` surfaced by Subagent Gamma

Gamma's adversarial audit found a `Violation` row. The agent writes a `Constitutional Violation` block to `design.md` and halts WITHOUT calling the post-script. Amend the constitution, amend the architecture, or rerun `/deviate-explore` with a different problem statement.

### Pre-commit hook aborts the commit

Inspect `.pre-commit-config.yaml` output. The post-script runs the full test suite; fix lint, format, or test failures in `design.md` / `data-model.md` and re-run `deviate research post` directly.

## Next Steps

- [How to run /deviate-prd](/how-to/feature-lifecycle/prd) — translate the resolved architecture into immutable user requirements
- [Reference: deviate research flags](/reference/deviate-research) — full flag list for the `research` subcommand
- [Why HITL Gate 1 blocks PRD](/explanation/macro-layer-gating) — design rationale behind the pending-decisions gate