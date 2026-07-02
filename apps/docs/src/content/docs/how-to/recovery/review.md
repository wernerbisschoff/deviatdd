---
title: "Run a HITL Gate 3 review via /deviate-review"
description: "How to invoke /deviate-review for a 7-domain PR scan at HITL Gate 3, select fixes, and persist the report."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-ADH-011
prev: false
next: false
---

This how-to covers the meso-layer `/deviate-review` phase: a V4 Flash single-pass scan across Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD Alignment, and Flow Coverage at HITL Gate 3, with interactive fix selection and report persistence.

## Prerequisites

- Feature branch diverged from `main` with all task commits present
- `specs/constitution.md`, `specs/issues.jsonl`, and `specs/_product/flows/index.md` available when the parent issue carries `flow_refs`
- Override the default V4 Flash model via `.deviate/config.toml` → `[models].review` if needed

## Steps

### 1. Emit the review contract

From inside the feature worktree, parse the JSON: `diff`, `structured_diff`, `structured_diff_markdown`, `constitution_path`, `prd_path`, `base_branch`. If `diff` is empty, exit.

```bash
deviate review pre --base main --branch HEAD
```

### 2. Run `/deviate-review`

Inside the agent:

```
/deviate-review
```

The slash command reads the contract from step 1 and surfaces findings as chat text with `[CRITICAL]`, `[SUGGESTION]`, and `[OPPORTUNITY]` tags plus a Compliance Matrix table.

### 3. Select which fixes to apply (HITL)

The slash command presents a `question` with four scopes: Critical only / Quick fixes only / Critical + Suggestions / All changes. Pick one — the agent edits only files in scope and reports applied vs. skipped items.

### 4. Persist the report

Pipe the surfaced findings into the persistence subcommand:

```bash
deviate review post < reviews/notes.md
```

A timestamped `reviews/review-report-{timestamp}.md` is written under the worktree root.

### 5. Verify the change

```bash
ls reviews/review-report-*.md | tail -n 1
git status --short
```

Expected: one fresh `review-report-*.md` and either a clean tree or staged fix edits ready for the next commit.

## Troubleshooting

### Empty diff / `SKIP: no changes since main`

`deviate review pre` returned an empty `diff`. Re-run with `--base main --branch <feature-branch>` to scope the diff to the current PR.

### `structured_diff_markdown` is `(no source changes)`

Tree-sitter is unavailable; per-symbol analysis is skipped. Note the reduced coverage in the Compliance Matrix or install the optional tree-sitter dependencies.

### `[CRITICAL] FLOW_BREAKAGE` / `STALE_FLOW_REF`

A `removed` symbol closes off a flow's capability, or the issue references a `FLOW-XX` no longer in `specs/_product/flows/index.md`. Re-open the symbol, amend the issue's `flow_refs`, or re-run `/deviate-tasks` to propagate flow context.

## Next Steps

- [Reference: deviate review flags and contract fields](/reference/cli/review)
- [Why review runs at HITL Gate 3 in V4 Flash](/explanation/pr-review-gate)
- [How to open and merge a PR](/how-to/issue-execution/pr)