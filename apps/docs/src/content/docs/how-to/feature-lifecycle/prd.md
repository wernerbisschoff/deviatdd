---
title: "Run /deviate-prd"
description: "How to compile explore.md into prd.md so /deviate-shard can later split the requirements into specs/issues.jsonl rows."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: d47f88c
related_issues: []
prev: false
next: false
---

This how-to covers compiling an approved `design.md` + `data-model.md` pair into `prd.md` so the downstream `/deviate-shard` phase can split functional requirements into ledger-tracked issues.

## Prerequisites

- HITL Gate 1 signed off: `specs/{NNN}-{SLUG}/design.md` and `data-model.md` exist and are reviewed
- `specs/{NNN}-{SLUG}/explore.md` populated by `/deviate-explore`
- An active feature worktree with `.deviate/session.json` whose `current_phase` is `RESEARCH`

## Steps

### 1. Open the feature worktree

```bash
git worktree list
```

Confirm the worktree path matches the active epic slug stored in `.deviate/session.json`. The PRD pre-script reads that slug to locate the feature directory.

### 2. Run the pre-script

```text
/deviate-prd
```

The pre-script (`prd_pre`) discovers the epic, validates that `design.md` and `data-model.md` exist, transitions the session to `PRD`, and emits a JSON contract. If it returns `NO_RESEARCH_BASELINE`, stop and run `/deviate-research` to finish the upstream phase first.

### 3. Author the PRD

The macro-layer agent writes `specs/{NNN}-{SLUG}/prd.md` with `FR-{NNN}-{ID}` tokens and Gherkin `Given/When/Then` acceptance criteria for each functional requirement. If ambiguity remains, the agent emits an `AMBIGUITY_INTERROGATION` block with `## Decision Readiness` and `## Clarification Log` sections and halts — resolve the open questions before continuing.

### 4. Hand off via the post-script

The agent writes the manifest to `.deviate/artifacts/manifest_prd.json` and the post step (`prd_post`) runs: validates sections, calls `extract_prd_requirements()` for FR traceability, runs pre-commit hooks, commits `prd.md`, and saves the session.

### 5. Verify the commit

```bash
git log --oneline -3
git diff --stat HEAD~1
```

Expected: a new commit on the feature branch with `prd.md` in the message body and `specs/{NNN}-{SLUG}/prd.md` listed in the diff stat.

## Troubleshooting

### `NO_RESEARCH_BASELINE`

`design.md` or `data-model.md` is missing. Run `/deviate-research` to finish the upstream phase, then re-invoke `/deviate-prd`.

### FR traceability failed

A functional requirement lacks a matching Gherkin acceptance criterion. Add an `AC-[ID]` block under each `FR-{NNN}-{ID}` header and re-run the post-script.

### Pre-commit hook aborts the commit

Inspect `.pre-commit-config.yaml` output. The PRD phase runs hooks before commit; fix lint or format errors in `prd.md` and re-invoke `/deviate-prd`.

## Next Steps

- [How to run /deviate-shard](/how-to/feature-lifecycle/shard) — split the PRD into ledger-tracked issues
- [Reference: deviate prd flags](/reference/deviate-prd) — full flag list for the `prd` subcommand
- [Why the macro layer gates downstream work](/explanation/macro-layer-gating) — design rationale