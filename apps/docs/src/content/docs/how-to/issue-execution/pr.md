---
title: "Open and merge a PR via /deviate-pr"
description: "How to use /deviate-pr to validate the worktree, generate a PR body, create the PR, and append COMPLETED to the ledger."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-ADH-011
prev: issue-execution/tasks.md
next: false
---

This how-to covers the meso-layer `/deviate-pr` phase: closing the loop on a completed issue by creating (and optionally merging) a GitHub PR from the worktree branch, then appending a `COMPLETED` event to `specs/issues.jsonl` to unblock dependents. Run after `/deviate-tasks` reaches `STATUS: IDLE`.
## Prerequisites

- All `TSK-NNN-NN` slices from `tasks.md` committed; session phase `TASKS` or `IDLE`
- Worktree branch current (the script pushes for you if missing)
- GitHub CLI `gh` authenticated (`gh auth status`); Graphite CLI `gt` only when `.deviate/config.toml` has `graphite = true`
- A PR body file at `pr_descriptions/<branch>.md` with `SUMMARY` + `CHANGES` + `CLOSES #N` sections

## Steps
### 1. Enter the worktree and run the pre-script

From inside the worktree, emit the JSON contract (`issue_id`, `branch_name`, `pr_title`, `commit_titles`, `changed_files`, `diff_summary`):

```bash
deviate pr pre
```

### 2. Generate the PR body

Following the `<pr_body_format>` from `/deviate-pr`, write `SUMMARY` (2-4 sentences, problem-led), `CHANGES` (grouped by concern), and `CLOSES #N`. Save to `pr_descriptions/<branch>.md`.

### 3. Confirm with the stakeholder (HITL gate)

Present the branch, title, body, and merge intent. Only proceed after explicit confirmation — `/deviate-pr` is the last step before a public PR appears.

### 4. Run `/deviate-pr`

Inside the agent:

```
/deviate-pr
```

The slash command invokes `deviate pr run --body-file pr_descriptions/<branch>.md` with optional `--merge` or `--auto-merge`. It appends `COMPLETED` to the ledger, commits `chore({issue_id}): mark COMPLETED in ledger`, pushes the branch, then creates the PR via `gh pr create` (or `gt submit --stack` when Graphite is enabled).

### 5. Verify the change

```bash
gh pr view --json url,state,mergedAt
tail -n 1 specs/issues.jsonl | jq -r '.issue_id + " -> " + .status'
```

Expected: a PR URL on the feature branch and a `{issue_id} -> COMPLETED` ledger row.

## Troubleshooting

### `MISSING_BODY_FILE`

`deviate pr run` was called without `--body-file`. Re-run with `pr_descriptions/<branch>.md` from step 2.

### `NO_ACTIVE_ISSUE` or `ISSUE_NOT_FOUND`

Session's `active_issue_id` is missing, or the issue is not in `specs/issues.jsonl`. Re-enter the worktree (the pre-script resolves the issue from `Path.cwd()`) or run `/deviate-plan` to re-establish the session.

### `GT_SUBMIT_FAILED`

Graphite CLI (`gt`) is missing or unauthenticated. Install from <https://graphite.dev/docs/cli> or set `graphite = false` in `.deviate/config.toml` to fall back to `gh pr create`.

### `PR_CREATE_FAILED`

`gh pr create` exited non-zero. Common causes: an existing PR for the branch (use `gh pr edit`), missing repo permissions, or an unparseable title. The error is in `stderr`.

### `LEDGER_IDEMPOTENT`

The issue already has a `COMPLETED` event — no duplicate is appended. This is informational; PR creation continues.

## Next Steps
- [Reference: deviate pr flags and contract fields](/reference/cli/pr) — full flag list and the pre-script JSON schema
- [Why PR creation appends COMPLETED before merge](/explanation/pr-ledger-completion) — design rationale for the dual-write ordering