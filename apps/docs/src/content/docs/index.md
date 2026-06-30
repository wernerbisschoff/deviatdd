---
title: "DeviaTDD Docs"
description: "Agent-orchestration framework that runs your entire TDD loop — explore, spec, red, green, refactor — with three mandatory human-in-the-loop gates."
doc_type: explanation
status: verified
last_verified_at: 2026-06-30
verified_sha: f2686f6
related_issues:
  - ISS-001-001
  - ISS-001-002
  - ISS-001-003
  - ISS-001-004
---

# DeviaTDD

DeviaTDD is a Python CLI (`deviate`) that drives your AI coding agent
through the full Test-Driven Development lifecycle — from problem
framing through documentation — across four layers (Product · Macro ·
Meso · Micro), an append-only JSONL ledger, worktree-isolated branches,
and tamper-guarded test execution. Three mandatory **human-in-the-loop
gates** keep the framework from drifting into autonomous closed-loop
operation: design approval after research (Gate 1), contract sign-off
after shard (Gate 2), and final merge audit (Gate 3).

This site renders the framework's reference documentation from the
markdown sources committed under `apps/docs/src/content/docs/`. The
content is **curated by the Tome subsystem** (the seven
`/tome-write-*` slash commands); this site only renders what Tome has
produced. To learn more, start with the four quadrant guides below.

## Where to start

- **New to DeviaTDD?** Begin with [Tutorials](/tutorials/intro/) — a
  guided end-to-end walkthrough from `deviate setup` to your first
  RED → GREEN → REFACTOR cycle.
- **Coming back for a specific task?** Jump to [How-Tos](/how-to/intro/)
  — one task per page, named after the operator action or phase.
- **Looking up a flag, schema, or field?** Head to [Reference](/reference/intro/)
  — flag tables, command contracts, and configuration lookups.
- **Trying to understand *why* the system is shaped this way?** Read
  [Explanations](/explanation/intro/) — design rationale, mental models,
  and architectural trade-offs.

## The four-quadrant layout (Diátaxis)

The docs follow the [Diátaxis](https://diataxis.fr/) framework: each
quadrant answers a different reader question and serves a different
reading moment. The taxonomy is enforced at the schema layer — every
page declares its `doc_type` in YAML frontmatter, and
`apps/docs/src/content.config.ts` rejects pages whose declared quadrant
does not match the directory the file lives in.

| Quadrant | Reader question | When to read it |
| :--- | :--- | :--- |
| **Tutorials** | *"Can you show me how?"* | When you're learning the system end-to-end. |
| **How-Tos** | *"How do I do X?"* | When you know what you want and need the steps. |
| **Reference** | *"What does X look like?"* | When you have a terminal or config file in front of you. |
| **Explanation** | *"Why is it this way?"* | After you've used the system and are asking deeper questions. |

## Local development

The site is a standard Astro + Starlight project. From the repo root:

```bash
mise run docs:install   # one-shot; creates apps/docs/node_modules/
mise run docs           # dev server at http://localhost:4321
mise run docs:build     # static build into apps/docs/dist/
```

Content edits under `apps/docs/src/content/docs/**` hot-reload; schema
or config changes (`astro.config.mjs`, `src/content.config.ts`) trigger
a full restart. Pages whose frontmatter fails the `docsSchema()`
declaration (e.g. unknown `doc_type`, malformed `last_verified_at`,
missing `verified_sha`) will not render — fix the frontmatter and the
page will appear on the next content sync.

## Provenance

Every page carries `verified_sha: <commit>` in its frontmatter —
the commit SHA Tome generated the page against. Use this to confirm a
doc reflects the code as of that SHA. Page-level
`related_issues: [ISS-NNN-NNN]` cross-references resolve against
`specs/issues.jsonl`; an unresolved reference is a soft drift signal,
not a build failure.
