## Problem Definition
**Statement**: The request asks that `deviate specify` and `deviate micro run` run `mise setup:integration` so RED phases that need integration tests have `.env.instance` set up, and asks how `.env.instance` is set up today (generate new or copy from root).
**Scope**: The scan covers `deviate specify` status, `deviate micro run` test invocation, mise task definitions, `.env` handling, and worktree asset sync in this repository.
**Exclusions**: No design decision on the requested change. No test execution. No implementation code.

## Discovery Audit Results
### Verified Dependencies
- The project declares `mise` as the task runner. The `[env]` block in `mise.toml` loads `.env`.
- The project declares `uv`, `pytest`, `ruff`, `bats` as tooling. No `setup:integration` task exists in `mise.toml`.

### Ghost Dependencies
- None observed. `mise setup:integration` and `.env.instance` are referenced only in a worktree adhoc issue file as downstream specifics, not in this repo's manifests.

### Manifest Files Observed
- `mise.toml` defines tasks `test`, `test-e2e`, `setup`, `clean`, `dev`, `install-tool`, `publish`, `bench-lmstudio`, `bench-coding-mini`. No `setup:integration` task exists.
- `.env.example` declares `PYPI_API_TOKEN`. `.env` holds the real token. `.gitignore` ignores `.env` and `.env.*` except `.env.example`.
- `pyproject.toml` declares the `deviate` CLI package.

### Test Runner Configuration
- Unit tests run via `uv run pytest` (`mise run test`). E2E tests run via `bats tests/e2e/`.
- Micro-layer RED/GREEN invoke pytest as a subprocess via `src/deviate/cli/micro.py::_run_pytest` with `cwd=root`. The subprocess inherits the parent environment. No `.env.instance` loading occurs in that path.

### Manifest-Constitution Divergence
- None observed. The manifest tooling (`uv`, `pytest`, `ruff`, `bats`, `mise`) matches the constitution Tooling section verbatim.

## Constitution Quotes
- **Architectural Principles**: "Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Tech Stack Standards**: "Package manager: `uv`. Test runner: `pytest`. Linter: `ruff` (lint + format). E2E testing: `bats` (Bash automated test system). Task runner: `mise` (see `mise.toml` for all tasks)."
- **Testing Protocols**: "Test framework: pytest. Test root: `tests/`. Test extension: `.py`. Test command: `pytest tests/ -v`. Lint command: `ruff check .`. E2E command: `bats tests/e2e/`."
- **Definition of Done**: "Tests passing (pytest with clean exit code 0). Lint passing (ruff check with no violations). Judge phase passed (git diff validated against the authoritative plan acceptance contract)."

## Architectural Baselines
- **Existing Architectural Patterns**: Typer CLI entry points live in `src/deviate/cli/`. Meso logic lives in `src/deviate/cli/meso.py`. Micro logic lives in `src/deviate/cli/micro.py`. The `specify` command is a deprecated legacy shim merged into `shard`.
- **Infrastructure & Operations**: `mise run setup` runs `uv sync --extra dev` plus git-hooks configuration. `_setup_mise()` in `meso.py` runs `mise trust`, `mise install`, `mise run setup` inside worktrees. `.gitignore` ignores `.env` and `.env.*`.
- **Data & State Management**: State lives in JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`) and TOML config (`.deviate/config.toml`). No database runtime exists.
- **Quality, Safety & Observability**: `mise run check` runs lint plus format-check. Micro `_run_pytest` invokes pytest as a subprocess. Tests that hit that path mock `deviate.cli.micro._run_pytest`.
- **External Integrations**: None observed in this repo. The publish task uses `PYPI_API_TOKEN` from `.env`.

## Sibling Flow Inventory
| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | n/a |
| Lock vs reserve | none observed | n/a |
| Vendor call | none observed | n/a |
| Idempotency | none observed | n/a |
| Destination shape | none observed | n/a |

The nearest sibling flow is worktree environment setup. The project syncs `.env` into worktrees via `_WORKTREE_SYNC_FILES`. No `.env.instance` sync exists. Quote paths: `src/deviate/cli/meso.py`, `mise.toml`, `.env.example`.

## Ecosystem Research
- **Best Practices**: Mise documents per-task `run` steps in `mise.toml`. Mise loads env files via the `[env]` `_.file` key. This repo uses `_.file = ".env"`.
- **Common Use Cases & Pitfalls**: Projects that need per-instance integration config commonly add a second env file (for example `.env.instance`) plus a dedicated setup task that copies a template or generates values. This repo contains no such task or file.
- **Standard Tooling**: `uv sync`, `pytest`, `ruff`, `bats`, and `mise` cover setup, test, lint, and E2E in this repo. No integration-env generator tool is declared.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `mise.toml` | config | Declares mise tasks and env file | `[env]` / `_.file = ".env"` / `[tasks.setup]` / `run = "uv sync --extra dev && git config core.hooksPath .githooks"` |
| `src/deviate/cli/meso.py` | source | Runs mise setup in worktrees; defines worktree sync files; holds deprecated specify shim | `subprocess.run(["mise", "trust"], cwd=repo, check=True, capture_output=True)` / `subprocess.run(["mise", "install"], cwd=repo, check=True, capture_output=True)` / `subprocess.run(["mise", "run", "setup"], cwd=repo, check=True, capture_output=True)` / `_WORKTREE_SYNC_FILES = (".env",)` / `"[yellow]DEPRECATED[/] 'deviate specify' is deprecated. "` |
| `src/deviate/cli/micro.py` | source | Invokes pytest as a subprocess for RED/GREEN phases | `cmd = [sys.executable, "-m", "pytest", *test_file_list, "-v"]` / `return subprocess.run(` / `cwd=root,` / `capture_output=True,` / `text=True,` |
| `.env.example` | config | Committed template for the real `.env` | `PYPI_API_TOKEN=` (template with generation comment for pypi.org token scope) |
| `.gitignore` | config | Ignores real env files | `.env` / `.env.*` / `!.env.example` |
| `.worktrees/feat/adhoc/052-e2e-task-preconditions-red-verification/specs/adhoc/issues/052-e2e-task-preconditions-red-verification.md` | doc | Worktree-only note that downstream `.env.instance` specifics do not exist in this repo | `Downstream specifics from issue 212 (`.env.instance`, `setup:e2e`, `test_full_local_startup.py`) do not exist in this repo.` |
| `specs/constitution.md` | doc | Declares three-layer architecture and tooling | `Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 3-4: `src/deviate/cli/meso.py`, `src/deviate/cli/micro.py`, `mise.toml`, `.env.example` |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Worktree env sync covers `.env` only; RED subprocess env inheritance covers the test path |
| Rationale | The repo contains no `setup:integration` task and no `.env.instance` file. The change touches setup invocation and worktree sync only. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | env-instance-setup |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/env-instance-setup.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
