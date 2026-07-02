---
title: "Run /deviate-hotfix"
description: "How to decompose a critical bug into a single TDD bugfix task via /deviate-hotfix, bypassing the RED boundary so the fix lands through one targeted cycle."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-004
prev: false
next: false
---

This how-to covers the micro-layer `/deviate-hotfix` slash command (aliases: `/hotfix`, `/spec.hotfix`): decomposing a critical, well-scoped bug into a single TDD-style bugfix task in `tasks.md` and committing via `deviate hotfix post`. Use it when a bug touches 1-2 files and is small enough to skip the explore / research / prd / shard pipeline — the HOTFIX path emits a `bypasses_red: true` contract so the post-script commits without re-enforcing the RED boundary. For broader bug-fix scope, escalate to `/deviate-tasks`.

## Prerequisites

- DeviaTDD installed: `uv tool install deviatdd` (or `pipx install deviatdd`)
- The repo initialised: `deviate setup` has been run
- A clean feature branch with no in-flight RED/GREEN transitions (HOTFIX refuses to interleave with the active micro-cycle)
- A one-sentence bug description (file + line + observed-vs-expected)

## Steps

### 1. Run `/deviate-hotfix`

Inside the agent on the feature branch, run:

```text
/deviate-hotfix "Division by zero in calc_total() at cart.py:47 when cart is empty"
```

The slash command invokes `deviate hotfix pre`, which resolves the active task (or the `--task TSK-NNN-NN` if supplied) and emits a JSON contract with `issue_context`, `bypasses_red: true`, and `completion_criteria: "Bug fix — bypasses RED phase"`.

### 2. Confirm the bug scope

Read the broken file plus its matching `tests/**/test_*.py`. If the bug touches more than 2 files or spans multiple concerns, halt and route the work to `/deviate-tasks` — the HOTFIX contract caps scope to a single `T001` (or `T001` + `T002`) row.

### 3. Author the `tasks.md` artifact

The agent writes `tasks.md` at the workspace root with one TDD bugfix row carrying `[RED]`, `[GREEN]`, `[EDGE_CASES]`, and `[ACCEPTANCE]` bullets, a deterministic `Verification` CLI command, and `Files_Touched` listing the broken file plus its test file. Pre-commit hooks enforce the format.

### 4. Commit via the post-script

```bash
deviate hotfix post
```

It validates the manifest, stages `tasks.md`, runs pre-commit hooks (full test suite — allocate ≥ 180s), and commits with `feat: HOTFIX phase`. Pass `<manifest>` to override the subject via `commit_subject`.

### 5. Verify the change

```bash
git log --oneline -1
ls tasks.md
grep -E '^### T001' tasks.md
```

Expected: latest commit starts with `feat: HOTFIX phase`, `tasks.md` exists, and it carries one (or two) `TNNN` heading lines.

## Troubleshooting

### `TASK_NOT_FOUND` from `deviate hotfix pre`

The supplied `--task` ID does not match `^TSK-\d{3}-\d{2}$`, or no matching row exists in `specs/**/tasks.jsonl`. Re-run `/deviate-hotfix` without `--task` to auto-resolve the active task, or fix the ID format.

### Scope exceeded

The bug spans more than 2 files or multiple concerns. `/deviate-hotfix` will refuse to emit a row. Halt and route the work to `/deviate-tasks` so the bug lands through the full micro-cycle (RED → GREEN → JUDGE → REFACTOR).

### Pre-commit hook aborts the commit

`deviate hotfix post` runs `mise run lint`, `mise run format-check`, and `mise run test` before committing. Read the hook output, fix the violation in `tasks.md`, and re-invoke `deviate hotfix post`. As a last resort, fall back to `git commit -m "feat: HOTFIX phase"`.

### Commit subject malformed

The manifest's `commit_subject` exceeds 50 chars or is missing the `<type>(<scope>):` prefix. Edit the manifest's `commit_subject` to `fix(<scope>): <subject>`, then re-run `deviate hotfix post <manifest>`.

## Next Steps

- [How to run a TDD task through RED/GREEN/REFACTOR](/how-to/tdd-micro-cycle/red) — execute the `T001` row `/deviate-hotfix` produced
- [Reference: deviate hotfix flags](/reference/cli/hotfix) — full flag list for `hotfix pre` / `hotfix post`
- [Why HOTFIX bypasses the RED boundary](/explanation/micro-layer-purpose) — design rationale for the bugfix-mode shortcut