# Feature Exploration: Graphite CLI Integration

## Problem Definition

**Statement**: Add an optional `--graphite` flag to `deviate init` that stores a boolean in config, and when set to `True`, all DeviaTDD phases switch from raw git/gh commands to Graphite's `gt` CLI for branch management, stack creation, and PR submission.

**Scope**: In-scope structural components:
- `deviate init` — the CLI command that initializes the workspace
- `DeviateConfig` — the Pydantic config model that serializes to `.deviate/config.toml`
- `_scaffold_dotfiles()` — writes config.toml from `DeviateConfig.model_dump()`
- `claudemd_seed.md` — the governance seed appended to `CLAUDE.md`
- Micro-layer branch creation in TDD cycle (RED/GREEN/REFACTOR phases)
- `deviate pr` / `_pr_run()` — PR creation via `gh pr create`
- `deviate-pr` skill — the SKILL.md that instructs the PR workflow

**Exclusions**: Explicitly out-of-scope for this exploration:
- Architectural decisions or trade-off analysis (deferred to `deviate-research`)
- Data modeling or schema changes beyond the `graphite: bool` config field
- Implementation code, source file changes, or test generation
- Web discovery of Graphite CLI internals beyond what `context query` returns
- Migration of existing projects to Graphite (no automatic `gt init` on existing repos)

## Discovery Audit Results

### Verified Dependencies

| Dependency | Manifest | Source |
|:---|---:|:---|
| `typer>=0.12` | `pyproject.toml` | `src/deviate/cli/__init__.py:8` |
| `rich>=13.0` | `pyproject.toml` | `src/deviate/cli/__init__.py:9` |
| `pydantic>=2.0` | `pyproject.toml` | `src/deviate/state/config.py:98` |
| `pyyaml>=6.0.3` | `pyproject.toml` | (YAML serialization) |
| `pytest>=9.0.3` | `pyproject.toml` (dev) | test suite |
| `ruff>=0.15.16` | `pyproject.toml` (dev) | linter |
| `hatchling` | `pyproject.toml` (build) | build backend |
| `bats` | `mise.toml` (e2e) | E2E test runner |

### Ghost Dependencies

None detected — all imported packages are declared in `pyproject.toml`.

### Manifest Files Observed

| Manifest | Description |
|:---|---:|
| `pyproject.toml` | Python project metadata, dependencies, build config, entry point |
| `mise.toml` | Task runner definitions (test, lint, format, check, setup, etc.) |
| `package.json` | Node dependency for `opencode-codebase-index` |

### Test Runner Configuration

**Source**: `pyproject.toml` `[tool.pytest]` and `mise.toml` tasks
```toml
# mise.toml test task
test = "uv run pytest tests/ -v"
```
```toml
# constitution TESTING_PROTOCOLS
TEST_COMMAND = "pytest tests/ -v"
```

### Manifest-Constitution Divergence

None detected. The constitution's `[2_TECH_STACK_STANDARDS]` aligns with all observed manifest declarations.

## Constitution Quotes

Constitution excerpts quoted verbatim. No interpretation, inference, or classification.

- **Architectural Principles** (Section `[1_ARCHITECTURAL_PRINCIPLES]`):
  > - **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped.
  > - **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only.
  > - **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary.
  > - **Model Tiering**: V4 Flash for high-frequency phases (RED, GREEN, REFACTOR, `/explore`); V4 Pro for compliance and planning (JUDGE, YELLOW, `/plan`); Qwen 3.7+ for architecture (`/research`, `/prd`, `/shard`).

- **Tech Stack Standards** (Section `[2_TECH_STACK_STANDARDS]`):
  > - Python 3.13
  > - Target: CLI application (`deviate`)
  > - Framework: Typer (CLI entry points) with Rich for terminal I/O
  > - Version control: Git (all phase commits, lock branches for concurrency)
  > - Package manager: `uv`
  > - Test runner: `pytest`

- **Testing Protocols** (Section `[3_TESTING_PROTOCOLS]`):
  > - `TEST_FRAMEWORK`: pytest
  > - `TEST_ROOT`: tests
  > - `TEST_COMMAND`: pytest tests/ -v
  > - RED phase tests must fail with `AssertionError` or `NotImplementedError`

- **Definition of Done** (Section `[4_DEFINITION_OF_DONE]`):
  > - [ ] Code implemented (satisfies acceptance criteria from `spec.md`)
  > - [ ] Tests passing (pytest with clean exit code 0)
  > - [ ] Lint passing (ruff check with no violations)
  > - [ ] Judge phase passed (git diff validated against `spec.md` invariants)

## Architectural Baselines

*Pattern_Over_Instance: Only representative examples or base classes are listed. All paths are strictly relative to `repo_root`.*

### Existing Architectural Patterns

- **CLI Entry Point**: `src/deviate/main.py` — `app = typer.Typer()` → `cli` from `src/deviate/cli/__init__.py`
  ```python
  cli = typer.Typer(no_args_is_help=True)
  ```
- **Subcommand Registration**: At module level in `cli/__init__.py:353-376`
  ```python
  cli.add_typer(explore_app, name="explore")
  cli.add_typer(explore_app, name="explore")
  cli.command(name="specify")(specify)
  ```
  All micro phases (red, green, refactor, etc.) are `typer.Typer` sub-apps; meso commands are direct `@cli.command()` functions.

- **Config Model (Pydantic)**: `src/deviate/state/config.py:98-106`
  ```python
  class DeviateConfig(BaseModel):
      profile: str = "default"
      llm_backend: str = "droid"
      timeout_seconds: int = Field(default=300, gt=0)
      agent_export_mode: Literal["local", "global"] = "local"
      agent: AgentConfig = Field(default_factory=AgentConfig)
      models: dict[str, str] = Field(default_factory=dict)
      model_config = {"extra": "forbid"}
  ```

- **Config Serialization**: `cli/__init__.py:65-91` — `_dict_to_toml()` turns `DeviateConfig.model_dump()` into TOML string
  ```python
  config = DeviateConfig(agent_export_mode=agent_export_mode)
  config_path = dot_dir / "config.toml"
  _write_if_missing(config_path, _dict_to_toml(config.model_dump()))
  ```

- **PR Workflow**: `src/deviate/cli/meso.py:1278-1296`
  ```python
  def pr(action, body_file=None, merge=False, auto_merge=False):
      if action == "pre": _pr_pre()
      elif action == "run": _pr_run(body_file, merge=merge, auto_merge=auto_merge)
  ```

- **PR Run — Branch Push + gh PR Create**: `src/deviate/cli/meso.py:993-1018`
  ```python
  subprocess.run(["git", "push", "-u", "origin", "HEAD"], ...)
  cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]
  ```

### Infrastructure & Operations

- **Task Runner**: `mise.toml` — all dev tasks via `uv run`
- **Version Control**: Git with `.githooks/` hooks, strict isolation via `_git_env()`
- **No containerization**: All execution is local on host

### Data & State Management

- **No persistent DB runtime**: State in JSONL ledgers (`specs/issues.jsonl`) and TOML config (`.deviate/config.toml`)
- **Session State**: JSON files under `.deviate/`

### Quality, Safety & Observability

- **Testing**: pytest with fixtures (`tmp_git_repo`, `_git_env()`)
- **E2E**: bats in `tests/e2e/`
- **Linting**: ruff (lint + format)
- **Git Isolation for Tests**: Mandatory `cwd=<tmp_git_repo>` + `env=_git_env()` on every `git` subprocess call

### External Integrations

- **GitHub CLI (`gh`)**: Required by `_pr_run()` for `gh pr create`
- **No other external integrations**

## Ecosystem Research

**Web_Discovery**: Graphite CLI (`gt`) workflow documentation retrieved via `context query graphite.com@latest`.

### Core Graphite Workflow

- **Create + Submit Single PR**:
  ```bash
  gt create --all --message "feat(api): Add new API method"
  gt submit
  ```
  - `gt create` combines `git checkout -b` + `git add` + `git commit` into one step
  - `gt submit` pushes branch + creates/updates PR via GitHub

- **Stacking Multiple PRs**:
  ```bash
  gt checkout           # interactive branch picker
  gt create --all --message "feat(frontend): Load users"
  gt submit --stack     # push all branches in stack, create/update PRs
  ```

- **Sync & Cleanup**:
  ```bash
  gt sync               # pull trunk, clean merged branches, restack
  ```

### Key Commands Table

| Task | Command | Short Form |
|:---|---:|:---|
| Create branch + commit | `gt create --all --message "..."` | `gt c -am "..."` |
| Amend staged changes | `gt modify --all` | `gt m -a` |
| Submit current branch PR | `gt submit` | |
| Submit entire stack PRs | `gt submit --stack` | `gt ss` |
| Sync trunk + cleanup | `gt sync` | |
| Checkout branch (interactive) | `gt checkout` | |

### Important Details

- `gt create` automatically names the branch from the commit message — no manual branch naming
- `gt submit` only pushes branches and creates/updates PRs; it does NOT merge
- `gt modify --all` amends to the current branch (replaces `git commit --amend --no-edit`)
- `gt fold` merges a child branch into its parent (useful for checkpoint cleanup)
- `gt MCP` server available in beta for AI agent integration
- Branch naming convention follows from the `--message` flag; conventional commit format recommended

### Relevance to This Feature

The `gt create --all --message "..."` command directly replaces the micro-layer pattern of `git checkout -b <branch>` + `git add` + `git commit`. The `gt submit` command replaces `git push -u origin HEAD` + `gh pr create` in the PR phase. When `graphite=True` is set, the DeviaTDD pipeline should:

1. Replace `git checkout -b` / `git branch` calls with `gt create --all -m "type(scope): desc"`
2. Replace `gh pr create` in `_pr_run()` with `gt submit` (or `gt submit --stack` for multi-task issues)
3. Add `gt init` to the init scaffold if graphite is enabled
4. Update CLAUDE.md seed to mandate `gt` usage for branch/PR operations

## File Registry

| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/__init__.py` | Codebase_File | CLI root — `init` command, config scaffolding, governance upsert | `@cli.command()\ndef init(\n    agent_export_mode: str = typer.Option(\n        "local", "--agent-export-mode", help="Export mode for agent commands"\n    ),\n    generate_constitution: bool = typer.Option(\n        False, "--generate-constitution", help="Generate constitution boilerplate"\n    ),\n    agent: str | None = typer.Option(\n        None, "--agent", help="Override auto-detected agent platform"\n    ),\n) -> None:` |
| `src/deviate/state/config.py` | Codebase_File | Pydantic `DeviateConfig` — config model serialized to TOML | `class DeviateConfig(BaseModel):\n    profile: str = "default"\n    llm_backend: str = "droid"\n    timeout_seconds: int = Field(default=300, gt=0)\n    agent_export_mode: Literal["local", "global"] = "local"\n    agent: AgentConfig = Field(default_factory=AgentConfig)\n    models: dict[str, str] = Field(default_factory=dict)\n    model_config = {"extra": "forbid"}` |
| `src/deviate/cli/meso.py` | Codebase_File | PR phase — `_pr_pre()` and `_pr_run()` | `def pr(\n    action: str = typer.Argument(..., help="Action: pre (validate) or run (create PR)"),\n    body_file: Path | None = typer.Option(None, "--body-file"),\n    merge: bool = typer.Option(False, "--merge"),\n    auto_merge: bool = typer.Option(False, "--auto-merge"),\n) -> None:` |
| `src/deviate/prompts/governance/claudemd_seed.md` | Config | Governance seed — `## DeviaTDD Orchestration Rules` section appended to CLAUDE.md | `## DeviaTDD Orchestration Rules\n\n### Three-Layer Architecture\n- **Macro Layer** — Feature scoping: /explore → /research → /prd → /shard\n- **Meso Layer** — Issue engineering: /specify → /tasks\n- **Micro Layer** — TDD sandbox: RED → GREEN → YELLOW → JUDGE → REFACTOR` |
| `src/deviate/prompts/skills/deviate-pr/SKILL.md` | Config | PR skill — instructs the agent on PR creation workflow | `CRITICAL INVARIANTS:\n1. **Ledger Update Rule**: Append COMPLETED event after PR is successfully created\n2. **Worktree Context**: The script runs from within the worktree.\n3. **Idempotency**: If the issue already has a COMPLETED event, do not append.\n4. **GitHub CLI Required**: Requires \`gh\` for PR operations.` |
| `.deviate/config.toml` | Config | Current runtime config — no graphite field | `profile = "default"\nllm_backend = "opencode"\ntimeout_seconds = 300\nagent_export_mode = "local"` |
| `pyproject.toml` | Manifest | Project metadata and dependencies | `[project]\nname = "deviate"\nversion = "0.1.0"\ndescription = "DeviaTDD CLI — agent orchestration framework"\nrequires-python = ">=3.13"\ndependencies = [\n    "typer>=0.12",\n    "rich>=13.0",\n    "pydantic>=2.0",\n    "pyyaml>=6.0.3",\n]` |
| `mise.toml` | Manifest | Task runner definitions | `[tasks]\ntest = "uv run pytest tests/ -v"\ntest-e2e = "bats tests/e2e/"\nlint = "uv run ruff check ."\nlint-fix = "uv run ruff check --fix ."\ncheck = { depends = ["lint", "format-check", "test"] }` |
| `src/deviate/core/_shared.py` | Codebase_File | Git isolation — `_git_env()` strips GIT_* env vars | `def _git_env() -> dict[str, str]:\n    env = os.environ.copy()\n    for key in list(env):\n        if key.startswith("GIT_") or key.startswith("GH_"):\n            del env[key]\n    return env` |
| `src/deviate/cli/micro.py` | Codebase_File | Micro-layer TDD commands — RED/GREEN/REFACTOR phase wrappers | (Micro layer invokes aider/agents with git branch management) |
| `tests/test_cli/test_init.py` | Test | Init command tests — dotfile scaffolding, constitution, governance | `class TestInitCommand:\n    def test_init_creates_dotfile_structure(self, tmp_path):` |
| `tests/test_state/test_config.py` | Test | Config model tests — schema validation, serialization, model resolution | `class TestDeviateConfig:\n    def test_defaults(self):\n        c = DeviateConfig()\n        assert c.profile == "default"` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Low |
| Files Likely Modified | 5-7 key files |
| New Modules Required | No |
| New Persistence / Data Models | No (single boolean field on existing model) |
| New External Integrations | No (Graphite is optional, existing git/gh workflows preserved) |
| Upstream / Cross-Cutting Concerns | Skill files (deviate-pr, deviatdd-red, deviatdd-green, deviatdd-refactor) may need conditional Graphite instructions; CLAUDE.md seed needs conditional block |
| Rationale | Adding a `graphite: bool` field to `DeviateConfig`, a `--graphite` flag to `init`, and conditional branches in `_pr_run()` and CLAUDE.md seed are localized changes. All modifications touch existing files (no new modules, no persistence changes). The Graphite CLI is an optional drop-in for git/gh commands — existing workflows remain unchanged when `graphite=False`. |

**Classification**: Low — localized changes to 5-7 existing files, no new modules, no new persistence, no new external integrations required.

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| FEATURE_SLUG | `graphite-cli-integration` |
| GIT_BRANCH | `main` |
| SPEC_TARGET | `specs/003-graphite-cli-integration/explore.md` |
| EPIC_ID | `graphite-cli-integration` |
| NEXT_ACTION | Run the `deviate-research` skill |
