---
title: "Run /deviate-explore"
description: "How to allocate a feature bucket, register a DRAFT ledger entry, and commit explore.md so the macro-layer pipeline can begin."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: false
next: false
---

This how-to covers running `/deviate-explore`, the first macro-layer phase. The pre-script allocates a feature bucket, registers a DRAFT ledger entry, transitions the session to `EXPLORE`, and emits a JSON contract; the agent then authors `specs/explore/{slug}.md`; the post-script validates, runs hooks, and commits. Run it before `/deviate-research`.

## Prerequisites

- Working repo with the DeviaTDD constitution (`specs/constitution.md`) in place
- `deviate` CLI on `PATH` (verify with `uv tool list | grep deviate`)
- A one-sentence problem statement you can pass as `<problem>`

## Steps

### 1. Run the pre-script

```text
/deviate-explore "your one-sentence problem statement"
```

The slash command invokes `explore_pre`, which validates the constitution, allocates a feature bucket under `specs/explore/`, appends a DRAFT ledger entry, transitions the session to `EXPLORE`, and prints a JSON contract with `spec_target`, `feature_dir`, and `issue_id`. Pass `--slug NAME` to override the auto-generated slug, `--json` for machine-readable output, or `--quiet` to suppress diagnostics.

### 2. Author the artifact

The macro-layer agent writes `specs/explore/{slug}.md` with the problem statement, scope boundaries, and any open questions for `/deviate-research` to investigate. Required headings are enforced by `validate_artifact()` in the post step.

### 3. Hand off via the post-script

The post step (`explore_post`) auto-discovers the latest `specs/explore/*.md`, validates required sections via `validate_artifact()`, runs pre-commit hooks, commits with `docs(explore): scan {stem}`, and saves the session.

### 4. Verify the artifact

```bash
git log --oneline -3
git show --stat HEAD
jq '.current_phase' .deviate/session.json
```

Expected: a new commit touching `specs/explore/{slug}.md` and `current_phase` set to `"EXPLORE"`.

## Troubleshooting

### `CONSTITUTION_MISSING`

The constitution file is absent or fails validation. Restore `specs/constitution.md` (or run `deviate init`) and re-invoke `/deviate-explore`.

### Pre-commit hook aborts the commit

`explore_post` runs hooks before committing. Inspect `.pre-commit-config.yaml` output, fix the flagged issue in `explore.md`, and re-invoke the post step.

### `validate_artifact` rejects the post step

`explore.md` is missing a required section. Read the validator's section list output, add the missing heading to the artifact, and re-run `/deviate-explore`.

## Next Steps

- [How to run /deviate-prd](/how-to/feature-lifecycle/prd) — compile the upstream exploration into a PRD
- [Reference: deviate explore flags](/reference/deviate-explore) — full flag list for the `explore` subcommand
- [Why macro layers gate downstream work](/explanation/macro-layer-gating) — design rationale