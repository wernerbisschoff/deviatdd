## Summary

The fast-path commands fill the gap between adhoc tasks and full orchestration in the DeviaTDD workflow. Small tasks like "fix typo" no longer require the full Explore→Research→PRD→Shard→Specify→Tasks pipeline — a single `deviate adhoc pre/post` handles classification, gating, and record-keeping. Feature workspace scaffolding (`deviate feature create`) creates the branch, directory structure, and session state from a single command, and `specify pre` auto-invokes it when no active workspace exists.

## Changes

- **Complexity Gate**: `ComplexityGate.classify()` — 3-tier LOW/MEDIUM/HIGH classification with deterministic stub support. LOW/MEDIUM routes to DIRECT execution mode; HIGH without `--skip-gates` halts with rejection. (`src/deviate/core/complexity.py`)
- **Adhoc Record**: `AdhocRecord` Pydantic model with `issue_id`, `description`, `execution_mode`, `status`, `timestamp` — persisted to `specs/adhoc.jsonl` with auto-create on first append. (`src/deviate/state/ledger.py`)
- **Adhoc CLI**: `deviate adhoc pre <description>` — classify, gate-check, persist record, emit JSON contract. `deviate adhoc post <manifest>` — transition PENDING→COMPLETED, save session to IDLE. (`src/deviate/cli/adhoc.py`)
- **Feature CLI**: `deviate feature create <title> [--slug]` — kebab-case slug derivation, `specs/{SLUG}/` directory creation, `feat/{SLUG}` branch via git, session update. Idempotent on existing branches. (`src/deviate/cli/feature.py`)
- **Meso Integration**: `specify pre` checks for active session and auto-invokes feature creation when absent, enabling the US-010 flow. (`src/deviate/cli/meso.py`)
- **Test Isolation**: All git subprocess calls use `_git_env()` to strip inherited `GIT_*` env vars. Session and production git operations are fully isolated from the parent repo. (`src/deviate/cli/micro.py`, `tests/` across 5 test files)
