---
title: "Initialize the Project Constitution"
description: "Scaffold specs/constitution.md so DeviaTDD has authoritative tech-stack, testing, and Definition of Done governance before any task runs."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: how-to/getting-started/init.md
next: how-to/getting-started/starter-first-task.md
---

This how-to covers scaffolding `specs/constitution.md` — the authoritative governance artifact that pins down the tech stack, testing mandates, and Definition of Done for every DeviaTDD run. Run it after `/deviate-init` (which seeds a placeholder) and before queueing any tasks.

## Prerequisites

- DeviaTDD installed: `uv tool install deviatdd` (or `pipx install deviatdd`)
- A git-initialised repo with `/deviate-init` already run (creates the placeholder)
- One or more stack signals on disk so the slash command can infer facts: `package.json`, `pyproject.toml`, `mix.exs`, `Dockerfile`, or CI config

## Steps

### 1. Run the constitution slash command

Run `/deviate-constitution` inside the agent. The command invokes `deviate constitution pre` to gather git state and resolve the constitution path, then derives tech-stack facts from your project files and writes `specs/constitution.md`.

Expected result: the agent prints the sections it generated (Architectural Principles, Tech Stack Standards, Testing Protocols, Definition of Done, Version History) and shows a preview.

### 2. Inspect the scaffolded constitution

Open `specs/constitution.md` and confirm every required section is present:

```bash
grep -E '^## (.*Architectural Principles|.*Tech Stack Standards|TESTING_PROTOCOLS|.*Definition of Done)' specs/constitution.md
```

Expected result: four matches — one per required heading, including the literal `## TESTING_PROTOCOLS` token (the pre-script validates this exact spelling).

### 3. Validate and commit via the post-script

The agent finishes by running `deviate constitution post <manifest>` to validate required sections and commit. Wait for it to return; the post-script runs the full precommit hook chain (allow ≥ 180 s).

Expected result: a single line `{"status": "SUCCESS"}` on stdout and a new commit `docs(constitution): add/update project constitution`.

## Verification

From the repo root, confirm the constitution is on disk and clean:

```bash
test -s specs/constitution.md && git log --oneline -1 -- specs/constitution.md
```

Expected result: the file exists and is non-empty; `git log` shows the commit from step 3.

## Troubleshooting

### `pre` returns `constitution validation failed`

The constitution exists but `validate_constitution()` rejected it — usually a malformed or missing `## TESTING_PROTOCOLS` block. Open the file and ensure that heading uses the literal token and the section body is non-empty.

### `post` exits with `Missing sections`

The manifest named sections the on-disk constitution doesn't have. Add the missing headings (Architectural Principles, Tech Stack Standards, Testing Protocols, Definition of Done) and re-run `/deviate-constitution` from step 1.

### Precommit hook fails during `post`

The constitution is valid but a hook in the chain (typically the test suite) failed. Inspect the failing hook's output, fix the underlying issue, then re-run `deviate constitution post <manifest>` — the constitution file itself is unchanged.

## Next Steps

- [How to run your first DeviaTDD task](/how-to/getting-started/starter-first-task) — once the constitution is committed, queue and drive your first micro-cycle.
- [Reference: deviate constitution subcommands](/reference/cli/constitution) — full flag and JSON-contract reference for `generate`, `pre`, `post`.
- [Reference: /deviate-constitution slash command](/reference/slash-commands/deviate-constitution) — execution sequence and required output template.