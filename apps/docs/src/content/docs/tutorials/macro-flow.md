---
title: "Run the Macro Layer End-to-End"
description: "Walk the full explore → research → prd → shard path from a problem statement to spec-enriched issues with both HITL gates."
doc_type: tutorial
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: starter-first-run.md
next: false
---

This tutorial walks the four Macro phases — `explore`, `research`, `prd`, `shard` — in order, with both human-in-the-loop gates in between. It builds on [Run Your First DeviaTDD Cycle](./starter-first-run.md), which skipped the Macro layer by writing one row directly into `specs/issues.jsonl`. By the end, you will have a one-line problem statement decomposed into spec-enriched `ISS-NNN` issues on a feature branch, all driven by slash commands inside your agent.

## Prerequisites

- Completed [Run Your First DeviaTDD Cycle](./starter-first-run.md), so you already have a worktree, a clean `main`, and `specs/constitution.md` populated
- A POSIX shell with `git`, `python` (3.13+), and `uv`
- The DeviaTDD slash commands installed (run `deviate setup --agent <name>` if not)

## Step 1 — Capture the problem with `/deviate-explore`

Run the explore phase inside your agent. It performs a read-only structural scan of the repo and writes one artifact — `explore.md` — describing what exists, not what to do.

```bash
/deviate-explore "Add a /healthz endpoint that returns liveness + version"
```

Expected result: a new directory under `specs/<epic-slug>/` containing `explore.md`, one git commit, and `git status` clean. The commit subject starts with `docs(<epic>): add explore.md`.

## Step 2 — Reason about the design with `/deviate-research` (Gate 1)

Research produces the architectural design and the data model. **This phase ends at HITL Gate 1** — you must review before `/deviate-prd` is allowed to advance.

```bash
/deviate-research
```

Expected result: `specs/<epic>/design.md` and `specs/<epic>/data-model.md` exist, one new git commit, and the agent displays a `STATUS: AWAITING_HITL_GATE_1` line. Open both files, confirm the recommended architecture matches what you want, then approve so the next phase can run.

## Step 3 — Compile the PRD with `/deviate-prd`

The PRD phase translates the design decisions into immutable, testable requirements tagged with `FR-[ID]` and `AC-[ID]` (Given/When/Then) tokens.

```bash
/deviate-prd
```

Expected result: `specs/<epic>/prd.md` exists with at least one `## FR-NNN-*` block, each carrying one or more `## AC-NNN-*-NN` Gherkin scenarios, plus one new git commit. If the agent halts on `Pending HITL Decisions`, resolve them in `design.md` first — the post-script blocks on any row left `PENDING` from research.

## Step 4 — Shard into issues with `/deviate-shard` (Gate 2)

Sharding decomposes the PRD into self-contained vertical slices (one issue per slice, each cutting through every layer needed to ship a user-visible feature) and registers them in the append-only ledger.

```bash
/deviate-shard
```

Expected result: one markdown file per slice under `specs/<epic>/issues/ISS-NNN-*.md`, one new row per slice appended to `specs/issues.jsonl`, and one new git commit. **Gate 2** is now open: open every issue file and confirm scope, defensive exclusions, and verification commands before any issue enters the Meso layer.

## Verification

From the repository root, run:

```bash
git log --oneline -n 5
cat specs/issues.jsonl | tail -5
ls specs/<epic>/issues/
```

Expected result: four macro-phase commits on top of `main` (one each for explore, research, prd, shard); the tail of `specs/issues.jsonl` shows freshly-registered `ISS-NNN` rows with `status: pending`; `specs/<epic>/issues/` contains at least one `ISS-NNN-*.md` file. The Macro flow is complete — you may now move into the Meso layer with `/deviate-plan ISS-NNN`.

## Next Steps

- [How-To → Issue Execution → Run /deviate-plan](../../how-to/issue-execution/plan.md) to begin the Meso layer on your first sharded issue
- [Explanation → Architecture → Why HITL Gates](../../explanation/architecture/hitl-gates.md) to understand why both gates pause the agent
- [Tutorials index](./index.md) to see the rest of the learning path