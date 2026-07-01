---
title: "Shard the PRD into issues"
description: "How to decompose a completed prd.md into vertical-slice issues and register them as BACKLOG in specs/issues.jsonl."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: d47f88c
related_issues: []
prev: null
next: null
---

This how-to covers the macro-layer `/deviate-shard` phase: decomposing a completed PRD into self-contained vertical-slice issues and registering each as `BACKLOG` in the append-only ledger. Run it after `/deviate-prd` has committed `prd.md` and HITL Gate 1 is clear.

## Prerequisites

- DeviaTDD installed and `deviate setup` already run on the repo
- An active epic bucket under `specs/<NNN>-<slug>/` containing `prd.md`
- All `## Pending HITL Decisions` rows in `design.md` set to `RESOLVED` (Gate 1)
- Clean working tree on the feature branch — shard pre/post runs pre-commit hooks
- A 180s timeout available for the post-script (pre-commit runs the full test suite)

## Steps

### 1. Run `/deviate-shard`

Inside the agent on the feature branch, run `/deviate-shard`. The slash command invokes `deviate shard pre`, which discovers the epic, resolves `prd.md`, computes the next global `ISS-{NNN}` counter, and emits a JSON contract carrying `epic_slug`, `prd_path`, `next_issue_id`, and `issues_dir`.

### 2. Wait for vertical-slice generation

The agent reads the PRD, groups related `FR-{NNN}-{ID}` tokens into vertical slices (Pass 1), demarcates scope boundaries (Pass 2), audits against the horizontal-slice anti-pattern (Pass 3), and maps each `AC-{NNN}-{ID}-{NN}` to a `## Demonstration Path` bash block (Pass 4). One shard file is written per slice under `specs/<epic>/issues/<NNN>-<kebab-slug>.md`.

### 3. Wait for the post-script to register and commit

The agent invokes `deviate shard post <manifest>`, which validates each shard's YAML frontmatter, appends each issue as `BACKLOG` to `specs/issues.jsonl`, stages the shard files and ledger, runs pre-commit hooks, and commits.

### 4. Verify the change

Confirm the shard produced the expected ledger entries and files:

```bash
tail -n 20 specs/issues.jsonl
ls specs/<epic>/issues/
git log --oneline -1
```

Expected: new `BACKLOG` rows for each shard, one `<NNN>-<slug>.md` file per slice in `specs/<epic>/issues/`, and a commit on the feature branch. The session transitions back to `IDLE`.

## Troubleshooting

### `NO_EPIC` from `shard pre`

No epic bucket under `specs/` is resolvable. Run `/deviate-explore` (or the full `/deviate-explore` → `/deviate-research` → `/deviate-prd` chain) and confirm `specs/<NNN>-<slug>/` exists.

### `MALFORMED_PRD_CONTRACT`

The PRD is missing `FR-{NNN}-{ID}` or `AC-{NNN}-{ID}-{NN}` tokens, or tokens are duplicated or ambiguous. Re-edit `prd.md` so every requirement and acceptance criterion carries a unique token, then re-run `/deviate-shard`.

### `INCOMPLETE_FR_COVERAGE`

One or more FRs from the PRD are not assigned to any slice. Open each shard file, confirm its frontmatter lists the relevant FRs, and add or re-cluster the slice so every PRD FR appears in at least one shard.

### `TOPOLOGY_LOOP_FAULT`

Circular dependency in the DAG — slice A blocks B and B blocks A. Edit the affected shards' `blocked_by` and `coordinates_with` frontmatter to break the cycle, then re-run `/deviate-shard`.

### Pre-commit hook failure

The post-script ran the full test suite and at least one test failed. Read the failure from the post-script output, fix the offending code or shard content, and re-run `deviate shard post <manifest>` directly.

## Next Steps

- [How to plan a shard](/how-to/issue-execution/plan) — pick up a `BACKLOG` issue and run `/deviate-plan`
- [Reference: shard manifest schema](/reference/shard-manifest) — required IssueRecord fields
- [Why vertical slicing](/explanation/vertical-slicing) — the design rationale behind the anti-pattern gate