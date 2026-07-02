---
title: "mise.toml Schema"
description: "Reference for the mise.toml task surface — top-level sections, task attributes, and the complete task catalog defined in this repo's mise.toml."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: apps/docs/src/content/docs/reference/config/deviate-config.md
next: false
---

`mise.toml` is this project's task-runner configuration file. This page documents the sections actually used here, the standard task attributes, and the full task catalog operators invoke with `mise run`.

## Top-level sections

| Section | Required | In this repo | Purpose |
|---|---|---|---|
| `[env]` | optional | yes | Shell environment variables exported when `mise` activates the project. |
| `[tools]` | optional | yes | Tool versions `mise` installs on first activation (`mise install`). |
| `[tasks]` | optional | yes | Named tasks runnable as `mise run <task>` (or the shorthand `mise <task>`). |
| `[vars]` | optional | no | Project variables referenced from task `run` strings via `{{vars.name}}`. |
| `[alias]` | optional | no | Per-tool command aliases (e.g., `node = "corepack"`). |
| `[redactions]` | optional | no | Patterns to redact from `mise run` output (secrets masking). |

Sections absent from the file are simply unavailable; no error is raised. The three sections above are the only ones this repo's `mise.toml` declares.

## `[env]` keys

| Key | Type | Default | Description |
|---|---|---|---|
| `python` | `string` | `"3.13"` | Sets `MISE_PYTHON_VERSION` for the project; pins the interpreter `uv` resolves to. |

The schema permits arbitrary environment variable keys (any string). `mise env` prints the resolved set after `[env]` and shell exports are merged.

## `[tools]` entries

| Tool | Version | Backend | Description |
|---|---|---|---|
| `python` | `"3.13"` | `core:python` | Pin the CPython interpreter to 3.13; `uv` reads this for `uv sync` / `uv run`. |
| `uv` | `"latest"` | `aqua:astral-sh/uv` (auto) | Track the latest stable `uv` release for dependency sync and editable installs. |

`[tools]` accepts `{ <name> = <version> }` pairs. The version string follows `mise`'s pinned-version grammar: exact (`"3.13"`), range (`">=3.12"`), or `"latest"` / `"prefix"`.

## Task attributes

| Attribute | Type | Default | Required | Description |
|---|---|---|---|---|
| `run` | `string \| list[string]` | (required if no `depends`) | when present | Shell command(s) executed by `mise run <task>`. Multi-line scripts use YAML-style `\|` or arrays of strings. |
| `description` | `string` | `""` | no | Human-readable summary surfaced by `mise tasks` and the docs site's task tables. |
| `depends` | `list[string]` | `[]` | no | Tasks executed before this one runs; failures abort the parent task. |
| `sources` | `list[string]` | `[]` | no | Filesystem globs whose changes mark the task as stale (cache invalidation). Not used in this repo. |
| `env` | `table` | `{}` | no | Per-task environment variable overrides. Not used in this repo. |
| `dir` | `string` | `""` | no | Working directory for `run`; default is the directory of `mise.toml` (project root). Not used in this repo. |
| `alias` | `string` | `""` | no | Short alias for the task (e.g., `t` for `test`). Not used in this repo. |
| `quiet` | `bool` | `false` | no | Suppress command-echo preamble. Not used in this repo. |
| `raw` | `bool` | `false` | no | Skip shell parsing and execute the command verbatim via `exec`. Not used in this repo. |

## Task catalog

All tasks below are defined in the repository root `mise.toml`. Dotted names (`docs:install`, `docs:build`, `docs:preview`) use the literal colon; `mise run docs:install` is the canonical invocation.

| Task | Attribute | Value | Description |
|---|---|---|---|
| `test` | `run` | `uv run pytest tests/ -v` | Run unit tests |
| `test` | `description` | `Run unit tests` | — |
| `test-e2e` | `run` | `bats tests/e2e/` | Run E2E tests via bats |
| `test-e2e` | `description` | `Run E2E tests via bats` | — |
| `lint` | `run` | `uv run ruff check` | Lint Python |
| `lint` | `description` | `Lint Python` | — |
| `lint-fix` | `run` | `uv run ruff check --fix` | Apply lint fixes |
| `lint-fix` | `description` | `Apply lint fixes` | — |
| `format` | `run` | `uv run ruff format` | Format Python |
| `format` | `description` | `Format Python` | — |
| `format-check` | `run` | `uv run ruff format --check` | Check formatting |
| `format-check` | `description` | `Check formatting` | — |
| `check-types` | `run` | `echo "No type checker configured"` | Type check |
| `check-types` | `description` | `Type check` | — |
| `check` | `depends` | `["lint", "format-check"]` | All validation checks |
| `check` | `description` | `All validation checks` | — |
| `fix` | `depends` | `["lint-fix", "format"]` | Format + lint fix |
| `fix` | `description` | `Format + lint fix` | — |
| `setup` | `run` | `uv sync --extra dev && git config core.hooksPath .githooks` | Install deps + configure git hooks |
| `setup` | `description` | `Install deps + configure git hooks` | — |
| `clean` | `run` | `rm -rf .ruff_cache/ .pytest_cache/ __pycache__/ .mypy_cache/ dist/ build/ *.egg-info/` | Remove artifacts |
| `clean` | `description` | `Remove artifacts` | — |
| `dev` | `run` | `uv run deviate` | Run the deviate CLI (pass args directly, e.g. `mise run dev init`) |
| `dev` | `description` | `Run the deviate CLI (pass args directly, e.g. \`mise run dev init\`)` | — |
| `install-tool` | `run` | `uv tool install --editable .` | Install package as editable tool via uv |
| `install-tool` | `description` | `Install package as editable tool via uv` | — |
| `help` | `run` | `mise tasks` | List tasks |
| `help` | `description` | `List tasks` | — |
| `docs` | `run` | `cd apps/docs && npm run dev` | Run the Starlight docs dev server |
| `docs` | `description` | `Run the Starlight docs dev server` | — |
| `docs:install` | `run` | `cd apps/docs && npm install` | Install Starlight + Astro dependencies (creates `apps/docs/node_modules/`) |
| `docs:install` | `description` | `Install Starlight + Astro dependencies (creates apps/docs/node_modules/)` | — |
| `docs:build` | `run` | `cd apps/docs && npm run build` | Build the static docs site into `apps/docs/dist/` |
| `docs:build` | `description` | `Build the static docs site into apps/docs/dist/` | — |
| `docs:preview` | `run` | `cd apps/docs && npm run preview` | Serve the built static docs site |
| `docs:preview` | `description` | `Serve the built static docs site` | — |

### Task bundles

| Task | Composed of |
|---|---|
| `check` | `lint` + `format-check` (pre-commit gate) |
| `fix` | `lint-fix` + `format` |

`check` and `fix` carry `depends = [...]` only; their `run` attribute is omitted, so `mise` resolves the composition and runs each dependency in declared order, aborting on the first non-zero exit.

## Examples

List every task and its description:

```
mise tasks
```

Run the pre-commit gate bundle (lint + format-check):

```
mise run check
```

Run the Starlight docs dev server:

```
mise run docs
```

Build and preview the static docs site without invoking the dev server:

```
mise run docs:build && mise run docs:preview
```

Install the `deviate` CLI as an editable `uv` tool so it is on `$PATH` for the session:

```
mise run install-tool
```

## See Also

- [Deviate Config Schema](./deviate-config) — sibling config reference for `.deviate/config.toml`
- [Config Field Reference](./starter-config) — the nine Tome frontmatter fields every page in this docs site must carry
- [How to scaffold a repo with DeviaTDD](/how-to/getting-started/init) — exercises the `/deviate-init` flow that creates `mise.toml` on a fresh repo
- [Why Diátaxis: The Architecture Behind This Docs Site](/explanation/architecture/starter-architecture) — grounding for the schema-vs-ledger separation the run/task surface depends on
