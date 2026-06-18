# Exploration: Graphite PR Stacks Integration

## Problem Definition
[Statement]: Integrate Graphite (`gt` CLI) into DeviaTDD workflow as an optional alternative to `gh` for PR creation. When `graphite = true` in config, each task (TDD cycle or execute cycle) becomes its own PR in a Graphite stack. The micro runner creates new branches via `gt create` before each task and submits via `gt submit` after each task. The meso `deviate pr` command uses `gt submit --stack` instead of `gh pr create`.

[Scope]: Existing PR flow (`meso.py` `_pr_run`), micro task dispatch (`micro.py` `_dispatch_task`, `_run_tdd_cycle`, `_run_execute_phase`), config model (`config.py` `DeviateConfig`). No new Pydantic models, no new JSONL ledgers, no state machines, no review ledger.

[Exclusions]: Review flow changes, Graphite AI Review, stack-aware merge queue, Graphite MCP, new skill files, PR review tracking.

## Discovery Audit Results

### Verified Dependencies
- **typer>=0.12**: `src/deviate/cli/` — all CLI command definitions
- **rich>=13.0**: `src/deviate/cli/_common.py` — terminal I/O (`console` singleton)
- **pydantic>=2.0**: `src/deviate/state/config.py` — `DeviateConfig` model
- **pytest>=8.0** (dev): `tests/` — test framework
- **ruff>=0.4** (dev): lint settings in pyproject.toml
- **mise**: task runner (all tasks defined in `.mise.toml`)
- **uv**: package manager

### Ghost Dependencies
- **gh (GitHub CLI)**: Referenced in `meso.py::_pr_run()` as the PR creation mechanism.
- **gt (Graphite CLI)**: Already a ghost dependency pattern (`npm install -g @withgraphite/graphite-cli`). Will be detected at runtime, same as `gh`.
- **aider**: Referenced in constitution as micro-sandbox LLM execution substrate.

### Manifest Files Observed
- **pyproject.toml**: No changes — `gt` is npm-based, cannot be declared in pyproject.toml.
- **mise.toml**: No changes.

### Test Runner Configuration
- **pytest**: `pytest tests/ -v` — all Graphite integration tests MUST mock `subprocess.run` for `gt` calls (never call real `gt` in tests).

### Architectural Baselines
- **PR flow**: `meso.py::_pr_pre()` (line 882) reads session/issue, emits contract. `_pr_run()` (line 929) pushes branch, calls `gh pr create`. No stack support.
- **TDD flow**: `micro.py::_run_tdd_cycle()` (line 1325) runs RED→GREEN→(YELLOW)→JUDGE→REFACTOR on the current branch. `_commit_phase()` handles commits. No branch creation before task — task runs on the issue branch already checked out.
- **Execute flow**: `micro.py::_run_execute_phase()` (line 1511) runs a single agent pass then commits. Same — no per-task branch creation.
- **Config**: `DeviateConfig` in `config.py:98` has `profile`, `llm_backend`, `timeout_seconds`, `agent_export_mode`, `agent`, `models`. Must be extended with `graphite: bool = False`.

## Ecosystem Research

Source: `context query graphite.com@latest` — authoritative and version-specific.

### Key CLI Commands

| Command | Purpose | Relevant Flags |
|---------|---------|----------------|
| `gt create <name>` | Create a new branch tracked by Graphite | `-o, --onto <branch>` (1.8.6+) — create on top of specified branch |
| `gt submit` | Idempotently force-push branches in current stack, creating/updating PRs | `--stack` (submit descendants too), `--no-edit-title`, `--no-edit-description` (skip prompts), `--cli` (CLI flow instead of web), `--draft` (draft PRs) |
| `gt log` | Visualize stack | None |
| `gt sync` | Sync all branches with remote, clean up merged PRs | `-a, --all` for all trunks |

### PR Title/Body Behavior
- `gt submit` infers PR title from branch name and commits. No `--title`/`--body` flags exist — use `--cli` for terminal flow or `--no-edit-title`/`--no-edit-description` to use defaults.
- Commit messages (`feat(TSK-NNN-NN): description`) become PR titles directly.
- `gt submit --no-edit-title --no-edit-description` is the correct non-interactive combination for agentic workflows.

### Runtime Detection
- `gt` is npm-based: `npm install -g @withgraphite/graphite-cli`
- Detect via `subprocess.run(["gt", "--version"], capture_output=True)`
- Identical pattern to existing `gh` detection in `meso.py`

### Context Query Mandate
All `gt` CLI flag references during implementation MUST be verified against the authoritative documentation source via:
```
context query graphite.com@latest "<topic>"
```
`gt` CLI flags evolve (the `--onto` flag was stabilized in 1.8.6). Do not hardcode flags from memory or web search.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Impact |
| :--- | :--- | :--- | :--- |
| `src/deviate/state/config.py` | Codebase | `DeviateConfig` model | **Add** `graphite: bool = False` field |
| `src/deviate/cli/micro.py` | Codebase | TDD/execute task dispatch | **Add** `gt create` before task, `gt submit` after task |
| `src/deviate/cli/meso.py` | Codebase | `_pr_run()` — PR creation | **Add** `gt submit --stack` branch when graphite=true |
| `src/deviate/cli/_common.py` | Codebase | `_check_gh_available()` pattern | **Add** `_check_gt_available()` helper (optional — can be inline) |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| FEATURE_SLUG | graphite-pr-stacks |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/004-graphite-pr-stacks/explore.md |
| NEXT_ACTION | Run the `deviate-research` skill |
