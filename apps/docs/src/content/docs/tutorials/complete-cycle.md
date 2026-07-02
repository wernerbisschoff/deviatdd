---
title: "Run a Complete End-to-End Cycle"
description: "One walkthrough of the full Macro → Meso → Micro flow — explore, research, prd, shard, plan, tasks, red, green, refactor, and judge."
doc_type: tutorial
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: false
next: false
---

This tutorial walks one full DeviaTDD cycle, from a fresh directory to a judged set of commits. Each step is driven by a `/deviate-*` slash command run inside the coding agent; you type only short verification commands from your shell. By the end you will have watched a raw idea become a green test, a refactored module, and a final `judge-pass` row in the ledger.

## Prerequisites

- A POSIX shell and Python 3.13
- `uv` ≥ 0.4, `git` ≥ 2.40, and `mise` on `PATH`
- The `deviate` CLI installed (`uv tool install deviate` or `pip install deviate`)
- An empty directory you are happy to initialise as a new Git repo
- 15 minutes of uninterrupted time

## Step 1 — Scaffold the repo

The init slash command writes `mise.toml` (with the zero-test-pass test task), `specs/constitution.md`, and an empty `specs/issues.jsonl` ledger.

```bash
/deviate-init
```

Then verify with `ls mise.toml specs/constitution.md && git status --short`. Expected result: both files exist and `git status` is clean.

## Step 2 — Scan the codebase

The first Macro phase audits what already exists and writes `explore.md` — a factual inventory, never design advice.

```bash
/deviate-explore
```

Then verify with `ls specs/explore.md`. Expected result: a single `explore.md` file appears under `specs/`.

## Step 3 — Build the spec through Macro

Run these Macro slash commands in order — they emit a problem statement, a PRD, and a spec-enriched issue file.

```bash
/deviate-research
/deviate-prd
/deviate-shard
```

Then verify with `tail -1 specs/issues.jsonl | jq .`. Expected result: the last row has `status: "shard-done"` and a `shard_id` field.

## Step 4 — Plan and queue the work

The Meso phases convert the issue into a plan and a task ledger the Micro layer will consume.

```bash
/deviate-plan
/deviate-tasks
```

Then verify with `ls specs/<feature-slug>/tasks.jsonl`. Expected result: at least one `TASK-001` row appears, with `status: "pending"`.

## Step 5 — Drive the Micro cycle

For each task, the slash-command library runs the three Micro phases on a dedicated worktree. Run them in order; let the agent finish one before issuing the next.

```bash
/deviate-red
/deviate-green
/deviate-refactor
```

Then verify with `grep '"phase":' specs/<feature-slug>/tasks.jsonl | tail -5 && git log --oneline -5`. Expected result: the ledger logs three phases for the task; `git log` shows three commits on `feature/<task>`.

## Step 6 — Judge the cycle

The judge slash command inspects every phase handover manifest and writes a verdict to `specs/issues.jsonl`.

```bash
/deviate-judge
```

Then verify with `tail -1 specs/issues.jsonl | jq .`. Expected result: the row carries `status: "judge-pass"`.

## Next Steps

- Read [How-To → Run Your First DeviaTDD Task](/how-to/getting-started/starter-first-task.md) for the operator-focused recipe version.
- Read [Explanation → Why Diátaxis](/explanation/architecture/starter-architecture.md) to learn why the docs are split into four quadrants.
- Read [Reference → Config Field Reference](/reference/config/starter-config.md) for the frontmatter contract every page carries.
- Re-read the quadrant landing page: [Tutorials → Introduction](/tutorials/index).
