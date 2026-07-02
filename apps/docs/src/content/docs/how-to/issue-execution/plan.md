---
title: "Run /deviate-plan"
description: "How to turn a spec-enriched BACKLOG issue into plan.md via per-issue localized research so /deviate-tasks can decompose it."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-ADH-003
prev: false
next: false
---

This how-to covers the meso-layer `/deviate-plan` phase: turning a spec-enriched `BACKLOG` issue into a planning document that contextualizes the workstation mapping, data flow, and risks for the downstream `/deviate-tasks` decomposition. Run it after `/deviate-shard` has registered the issue in `specs/issues.jsonl`.

## Prerequisites

- DeviaTDD installed: `uv tool install deviatdd` (or `pipx install deviatdd`)
- The repo initialized with `deviate setup` and at least one `BACKLOG` issue in `specs/issues.jsonl`
- An active epic bucket under `specs/<NNN>-<slug>/` with the issue file at `specs/<epic>/issues/<NNN>-<slug>.md` carrying the spec sections (`[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[SYSTEM_TOPOLOGY_MAPPING]`)
- `deviate plan pre` accepts the session in `SPECIFY` or `PLAN` phase; `deviate plan post` requires `PLAN`

## Steps

### 1. Run `/deviate-plan`

Inside the agent on the feature branch, run `/deviate-plan`. The slash command invokes `deviate plan pre`, which has two modes:

- **Outside a linked worktree** — auto-claim mode discovers the next unblocked `BACKLOG` issue (or uses `--issue <id>`), creates the worktree via `_specify_pre`, claims the issue, force-transitions the session to `PLAN`, prints the worktree path, and exits 0. `cd` into the printed path and re-run `/deviate-plan` to enter contract mode.
- **Inside a linked worktree** — contract mode loads the session, resolves the issue file via `record.source_file`, and prints a JSON contract with `issue_id`, `spec_path`, `plan_target`, `branch_name`, `constitution_path`, `constitution_test_command`, `constitution_lint_command`, and (when parseable) a `file_structure` appendix from the workstation mapping.

### 2. Parse the contract and read the issue file

From the JSON contract, capture `spec_path`, `plan_target`, and `branch_name`. Read `spec_path` to extract the spec sections: `[SYSTEM_TOPOLOGY_MAPPING]`, `[THE_PROBLEM_CONTRACT]`, `[SCOPE_BOUNDARIES]`, `[UPSTREAM_REQUIREMENT_TRACING]`, `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[EDGE_CASES_AND_BOUNDARIES]`, `[PERFORMANCE_CONSTRAINTS]`, `[MULTI_TIERED_VERIFICATION_TARGETS]`. If any required section is missing, halt with `INCOMPLETE_ISSUE_SPEC` and regenerate the issue.

### 3. Scan the current codebase

Run `git log --oneline -20`, read `specs/issues.jsonl` for related issues, read each workstation file in `[SYSTEM_TOPOLOGY_MAPPING]`, and scan `specs/constitution.md` for applicable invariants. Use `libref query <library> <topic>` for offline library docs instead of web fetching. Keep the scan under `L_max ≤ 200ms`.

### 4. Generate `plan.md`

Write the plan body (no wrapper tags, no preamble) to `plan_target` with these sections: `## Plan Summary`, `## Workstation Mapping`, `## Implementation Strategy` (numbered phases with files, approach, and verification), `## Data Flow Analysis`, `## Risk Assessment` (Markdown table — Risk / Impact / Likelihood / Mitigation), `## Integration Points`, `## Constitutional Alignment`.

### 5. Commit and advance the session

The agent runs `deviate plan post`, which validates `plan.md` exists and is non-empty (unless `--force`), commits with the message `docs({epic}-{issue}): create plan.md` via `commit_artifact()`, and transitions the session to `TASKS`. A `COMMIT_SKIP` notice means there were no changes to stage.

### 6. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
ls specs/<epic>/issues/<NNN>-<slug>/plan.md
```

Expected: a new commit on the feature branch, `current_phase: "TASKS"`, and a non-empty `plan.md` at the issue workspace.

## Troubleshooting

### `NO_UNBLOCKED_ISSUES` from `plan pre`

No claimable issue exists. Inspect `specs/issues.jsonl` for issues whose `blocked_by` is empty and `status` is `BACKLOG`. If the ledger is empty, run `/deviate-shard` first.

### `ISSUE_NOT_FOUND`

The issue file is missing at `spec_path`. Search `specs/<epic>/issues/` for the matching `<NNN>-<slug>.md`; if absent, halt with `ISSUE_FILE_NOT_FOUND` and regenerate the issue via `/deviate-shard`.

### `PLAN_EMPTY` from `plan post`

`plan.md` exists but is empty (or contains only whitespace). Write the seven required sections, then re-run `deviate plan post` (or pass `--force` to bypass the empty check).

### Worktree created but agent still in root

`_is_linked_worktree()` returned `False` even after the worktree was created. `cd` into the printed worktree path and re-run `/deviate-plan` so the command enters contract mode instead of auto-claim mode.

## Next Steps

- [How to run /deviate-tasks](/how-to/issue-execution/tasks) — decompose `plan.md` into the `tasks.jsonl` ledger
- [Reference: `deviate plan` flags](/reference/cli/plan) — full flag list for the `plan pre` / `plan post` subcommands
- [Why meso-layer planning lives between shard and tasks](/explanation/meso-layer-purpose) — design rationale for the per-issue research step
