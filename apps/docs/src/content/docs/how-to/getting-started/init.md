---
title: "Run /deviate-init"
description: "How to scaffold a repo with the DeviaTDD governance skeleton — mise.toml, specs/constitution.md, and specs/issues.jsonl — so the macro-layer pipeline can begin."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: false
next: getting-started/starter-first-task
---

This how-to covers running `/deviate-init`, the DeviaTDD bootstrap. The pre-script detects the project type and scaffolds the governance skeleton (`mise.toml`, `specs/`, `specs/constitution.md`, `specs/issues.jsonl`); the post-script validates and stages the artifacts. Run it once when adding DeviaTDD to a repo, before `/deviate-explore` or any first task.

## Prerequisites

- A git repository on the default branch — `/deviate-init` refuses non-git directories
- `deviate` CLI on `PATH` (verify with `uv tool list | grep deviate`)
- `mise`, `git`, and the language toolchain (`uv`, `npm`, `cargo`, `go`, or `mix`) available on the system `PATH`

## Steps

### 1. Run the pre-script

```text
/deviate-init
```

The slash command invokes `deviate init pre`, which detects the project type from `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, or `mix.exs`; generates `mise.toml` with the zero-test-pass invariant; creates `specs/constitution.md`; touches `specs/issues.jsonl`; and prints a JSON contract carrying `project_type`, `artifacts_created`, and `tooling`.

### 2. Inspect the contract

Read the JSON output of step 1. Confirm `project_type` matches the repo (e.g. `python` for a `pyproject.toml` project) and that `artifacts_created` lists `mise.toml`, `specs/`, `specs/constitution.md`, and `specs/issues.jsonl`.

### 3. Run the post-script

```text
/deviate-init post
```

The post step validates `mise.toml` tasks, confirms `specs/constitution.md` is well-formed, stages every init artifact with `git add`, and prints a status JSON. Allocate at least 180 s — pre-commit hooks may run.

### 4. Verify the scaffolding

```bash
ls mise.toml specs/constitution.md specs/issues.jsonl
git status --short
mise run test
```

Expected: all four paths exist, `git status` lists the staged artifacts, and `mise run test` exits `0` even when no tests have been written yet (zero-test-pass invariant).

## Legacy alias: `deviate setup`

Older scripts and muscle memory may reference `deviate setup`. It is a legacy flat alias for `deviate init` and behaves identically (scaffolds the same artifacts, accepts the same flags). The slash command `/deviate-init` is the canonical entry point; the CLI form is `deviate init` for interactive use and `deviate setup --agent <name>` for non-interactive shells where the Rich prompt menu cannot render.

## Troubleshooting

### `Not a git repository`

`deviate init pre` exits before scaffolding. Run `git init` from the repo root and re-invoke `/deviate-init`.

### `project_type: unknown`

None of the supported manifests (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `mix.exs`) was found. Add the project manifest for your language, or proceed with the generic `test = "echo 'No test framework' || true"` task.

### `mise.toml` already exists

The pre-script skips generation when `mise.toml` is already present. If the existing file lacks the zero-test-pass task, replace it with the form documented in `specs/_product/architecture.md` §3.4 before invoking the post step.

### Pre-commit hook aborts the staging

The post step runs hooks before committing. Read the hook output, fix the flagged issue in `mise.toml` or `specs/constitution.md`, and re-invoke `/deviate-init post`.

## Next Steps

- [How to run your first task](/how-to/getting-started/starter-first-task) — pick up an issue and drive it through the red → green → refactor micro-cycle
- [Reference: deviate init flags](/reference/deviate-init) — full flag list for the init subcommand
- [Why append-only ledgers need union-merge](/explanation/append-only-ledgers) — design rationale for `specs/issues.jsonl`