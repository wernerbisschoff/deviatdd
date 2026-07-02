---
title: "Bootstrap with `deviate setup`"
description: "How to initialise a workspace with `deviate setup` — the legacy flat CLI form of `/deviate-init`, used from non-interactive shells where the Rich prompt cannot render."
doc_type: how-to
status: draft
last_verified_at: 2026-07-02
verified_sha: 36b6a8b
related_issues: []
prev: apps/docs/src/content/docs/how-to/getting-started/starter-first-task.md
next: false
---

This how-to covers bootstrapping a DeviaTDD workspace with `deviate setup`, the legacy flat CLI form of `/deviate-init`. Use it from non-interactive shells — CI runners, Docker build steps, scripted onboarding — where the Rich agent-selection prompt cannot render. The slash command `/deviate-init` is the canonical entry for interactive agent sessions; `deviate setup` produces identical scaffolding and is fully idempotent.

## Prerequisites

- `deviate` on `PATH` (`uv tool list | grep deviate`)
- A git repository initialised at the workdir root
- One of `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, or `mix.exs` at the root — or accept the `unknown` project type

## Steps

### 1. Run `deviate setup` non-interactively

```bash
deviate setup --agent <name>
```

Pick `<name>` from `claude | opencode | droid | factory | pi`. The flag skips the Rich prompt menu and writes `[agent].backend` directly into `.deviate/config.toml`. The CLI then scaffolds `.deviate/`, applies governance blocks to `CLAUDE.md` and `AGENTS.md`, writes a seeded `specs/constitution.md`, and provisions `.gitignore` plus `.gitattributes` with `merge=union` rules for the append-only JSONL ledgers.

### 2. Install slash commands to every agent directory

Slash-command install is independent of `--agent`: regardless of which backend you passed, `deviate setup` copies the 24 `deviate-*.md` files into all four agent directories — `.claude/commands/`, `.opencode/commands/`, `.factory/commands/`, and `.pi/prompts/`. The `--agent` flag only drives which backend the meso/micro layers spawn; it never gates which directories receive commands.

```bash
ls .claude/commands/deviate-init.md .opencode/commands/deviate-init.md \
   .factory/commands/deviate-init.md .pi/prompts/deviate-init.md
```

Expected: all four paths resolve. If any is missing, re-run step 1 — install is idempotent.

### 3. Verify the scaffolding

```bash
test -s .deviate/config.toml && test -s specs/constitution.md && \
grep -q 'merge=union' .gitattributes && echo OK
```

Expected: prints `OK`. The three artifacts must exist and `.gitattributes` must carry `merge=union` for both `specs/issues.jsonl` and `specs/**/tasks.jsonl`.

## Troubleshooting

### `NO_AGENT_SELECTED` exit 1

`deviate setup` was invoked without `--agent` in a non-TTY context. Re-run with `--agent <name>` (`claude | opencode | droid | factory | pi`), or attach a TTY so the prompt menu can render.

### `specs/constitution.md` is `TBD`-only

The seed scaffolds placeholders for tech-stack facts. Populate the file by running `/deviate-constitution` (slash command) or `deviate constitution generate` (CLI form). `TBD` does not block downstream tasks but is tracked as a Definition-of-Done gap.

### Slash commands missing in the agent

The install copies 24 files into each of the four agent directories in a single invocation; if the count is short, the copy was interrupted. Re-run `deviate setup` — the install path is idempotent and only writes missing files.

### `.gitattributes` union-merge rules absent

Older scaffolds ran before `_ensure_root_gitattributes` existed. Re-run `deviate setup`; the helper preserves user-authored entries and only appends missing union-merge lines.

## Next Steps

- [How to run /deviate-init](/how-to/getting-started/init) — slash command equivalent for interactive agent sessions
- [Reference: deviate CLI flags](/reference/cli) — full flag reference for setup and the rest of the CLI surface
- [Reference: deviate-config schema](/reference/config/deviate-config) — `.deviate/config.toml` schema written by setup
- [Why append-only ledgers need union-merge](/explanation/data-and-governance/append-only-ledgers) — rationale for the `.gitattributes` rules
