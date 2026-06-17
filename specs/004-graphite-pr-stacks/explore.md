# Exploration: Graphite PR Stacks Integration

## Problem Definition
[Statement]: Integrate Graphite (`gt` CLI) into DeviaTDD workflow to create PR stacks for every task — after execute, or at the end of a TDD cycle that optionally includes refactor. Also evaluate creating or updating a `/deviate-pr-review` phase that handles reviewing PR stacks.
[Scope]: Existing PR/review workflow components, TDD phase structure, state management models, Graphite ecosystem capabilities and best practices for agentic development.
[Exclusions]: Architectural decisions, design trade-offs, risk analysis, data modeling, failure-mode speculation — all deferred to the `deviate-research` skill.

## Discovery Audit Results

### Verified Dependencies
- **typer>=0.12**: `src/deviate/cli/` — all CLI command definitions
- **rich>=13.0**: `src/deviate/cli/_common.py` — terminal I/O (`console` singleton)
- **pydantic>=2.0**: `src/deviate/state/config.py`, `src/deviate/state/ledger.py` — all Pydantic models
- **pyyaml>=6.0.3**: declared in pyproject.toml (not observed in current code paths)
- **pytest>=8.0** (dev): `tests/` — test framework
- **ruff>=0.4** (dev): lint settings in pyproject.toml
- **hatchling**: build backend in pyproject.toml
- **bats**: E2E testing (`mise run test-e2e` → `bats tests/e2e/`)
- **mise**: task runner (all tasks defined in `.mise.toml`)
- **uv**: package manager

### Ghost Dependencies
- **gh (GitHub CLI)**: Referenced in `src/deviate/prompts/skills/deviate-pr/SKILL.md` as the PR creation mechanism, but NOT listed in pyproject.toml or any dependency manifest. Required at runtime for PR operations.
  > `"GitHub CLI Required: Requires gh for PR operations. If unavailable, surface clear error."`
- **aider**: Referenced in constitution as micro-sandbox LLM execution substrate, but NOT listed in pyproject.toml. Required at runtime for TDD micro-layer phases.
  > `"Micro-sandbox: Aider Python API (aider.coders.Coder) as LLM execution substrate"`

### Manifest Files Observed
- **pyproject.toml**: Package metadata (40 lines). Runtime deps: typer, rich, pydantic, pyyaml. Dev deps: pytest, ruff. Build: hatchling. Dependency groups (PEP 735): pytest>=9.0.3, ruff>=0.15.16, typer>=0.26.7.
- **mise.toml**: Task definitions (58 lines). Tools: python=3.13, uv=latest. Tasks: test, test-e2e, lint, lint-fix, format, format-check, check-types, check, fix, setup, clean, dev, help.

### Test Runner Configuration
- **pytest**: `pytest tests/ -v` (from constitution `[3_TESTING_PROTOCOLS]`)
- **bats**: `bats tests/e2e/` (from constitution `[3_TESTING_PROTOCOLS]`)

### Manifest-Constitution Divergence
- None observed. The constitution's `[2_5_TOOLING]` references (uv, pytest, ruff, bats, mise, aider) match observed manifests except aider and gh, which are ghost dependencies (called at runtime, not in pyproject.toml). `[2_1_BACKEND]` (Python 3.13, Typer) matches pyproject.toml. `[2_3_DATABASE]` (JSONL, TOML) matches observed state implementation.

## Constitution Quotes
Constitution excerpts quoted verbatim from `specs/constitution.md`. No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.
- **Architectural Principles**: `"Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."`
- **Tech Stack Standards**: `"Python 3.13\nCLI application (deviate)\nFramework: Typer (CLI entry points) with Rich for terminal I/O"`
- **Testing Protocols**: `"TEST_FRAMEWORK: pytest\nTEST_ROOT: tests\nTEST_EXT: .py\nTEST_COMMAND: pytest tests/ -v\nLINT_COMMAND: ruff check .\nTYPE_CHECK_COMMAND: (none — mypy is not yet configured)\nE2E_COMMAND: bats tests/e2e/"`
- **Definition of Done**: `"Code implemented (satisfies acceptance criteria from spec.md)\nTests passing (pytest with clean exit code 0)\nLint passing (ruff check with no violations)\nJudge phase passed (git diff validated against spec.md invariants)\nE2E tests passing (if applicable; bats for CLI integration)\nDocumentation updated (spec.md and design.md reflect final implementation)\nNo governance violations (constitution rules upheld, no HITL gates bypassed)\nCommitted with conventional message format (test:, feat:, refactor:, docs:)"`

## Architectural Baselines
[Pattern_Over_Instance]: Only representative examples or base classes are listed, not every instance. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: Three-layer agent orchestration. Macro (`src/deviate/cli/macro.py`) — explore/research/prd/shard. Meso (`src/deviate/cli/meso.py`) — plan/tasks/pr. Micro (`src/deviate/cli/micro.py`) — red/green/judge/refactor/execute/e2e. Each phase follows pre/post contract pattern.
  > `cli.command(name="pr")(pr)` and `cli.add_typer(review_app, name="review")` from `src/deviate/cli/__init__.py`
  - **PR flow**: Split across two layers. CLI commands in `meso.py::_pr_pre()` (line 906) and `_pr_run()` (line 953) read session state, compute git metadata, and update the issue ledger. Orchestration in `deviate-pr/SKILL.md` calls `gh` CLI for actual PR creation. No PR stack support.
  - **Review flow**: `src/deviate/cli/review.py` — `review pre` (line 17) gathers git diff + governance context; `review post` (line 146) persists report markdown. `deviate-review/SKILL.md` performs lightweight scan over 3 areas (ledger integrity, cross-file consistency, security surface). Chat-only output, no file persistence.
  - **Execute flow**: `deviate-execute/SKILL.md` — direct task execution (not TDD). Pre-script discovers task ID → implement → run checks → post-script commits and updates ledger.

- **Infrastructure & Operations**: Git-based isolation. All subprocess git calls use `env=_git_env()` to strip inherited `GIT_*` env vars. Pre-commit: `mise run check`. Pre-push: `mise run test`. No containerization. Local execution on host.
  > `.githooks/pre-commit`: `#!/bin/bash\nunset GIT_DIR\nmise run check`
  > `.githooks/pre-push`: `mise run test`

- **Data & State Management**: Session state as `SessionState` Pydantic model → `.deviate/session.json`. Issue ledger → `specs/issues.jsonl` (append-only JSONL with `IssueRecord`). Task ledger → `specs/**/tasks.jsonl` (append-only JSONL with `TaskRecord`). Config → `.deviate/config.toml`. No persistent database runtime.
  > `src/deviate/state/ledger.py`: `IssueRecord: issue_id, type, title, status (DRAFT/BACKLOG/SPECIFIED/SHARDED/COMPLETED), source_file, blocked_by, coordinates_with`
  > `TaskRecord: id (TSK-\\d{3}-\\d{2}), issue_id, description, status (PENDING/RED/GREEN/YELLOW/.../COMPLETED/FAILED), execution_mode (TDD/DIRECT/E2E/IMMEDIATE)`

- **Quality, Safety & Observability**: Testing via pytest (unit) + bats (E2E). Lint via ruff. Type checking not yet configured (mypy absent). TamperGuard for micro-sandbox test protection. Judge phase for compliance gate. Chat-only review output.
  > Constitution `[3_2_COVERAGE]`: "RED phase tests must fail with AssertionError or NotImplementedError — syntax crashes are rejected"

- **External Integrations**: GitHub CLI (`gh`) — used at skill layer for PR creation (ghost dependency). Aider — used at micro layer for LLM execution (ghost dependency). No Graphite, no `gt` CLI, no stack-based branching. Zero references to Graphite anywhere in source or configuration.

## Ecosystem Research
[Web_Discovery]: Factual cataloging of industry best practices, common use cases, and standard tools relevant to integrating PR stacks via Graphite into DeviaTDD.

- **Best Practices**:
  - **Stack atomicity**: Each PR in a stack must be independently reviewable — "If the PR doesn't make sense without a lot of additional context from the stack, request that the author split up the stack differently to make each change more atomic." [Source: https://graphite-58cc94ce.mintlify.dev/docs/best-practices-for-reviewing-stacks.md]
  - **Bottom-up review**: "Start from the bottom: review from the bottom of the stack (closest to main) upwards." [Source: https://graphite-58cc94ce.mintlify.dev/docs/best-practices-for-reviewing-stacks.md]
  - **Early submission**: "Submit PRs as soon as they're ready to review: Even if you plan to stack additional changes on top, you should submit your changes for review." [Source: https://graphite-58cc94ce.mintlify.dev/docs/best-practices-for-reviewing-stacks.md]
  - **Stack splitting strategies**: Five methods from Graphite blog — functional component-based, iterative improvement, refactor/change separation, version bumps/generated code isolation, riskiness-based isolation. [Source: https://graphite.dev/blog/five-methods-for-stacking]

- **Common Use Cases & Pitfalls**:
  - **Stack size**: No fixed number; each PR should be atomic and reviewable independently. Typical stacks range 2-5 PRs.
  - **Iterative stack pitfall**: "One mode to watch out for with this type of stack is waiting too long before merging any of the PRs. Remember until a PR is merged, there is a risk that conflicting changes could be made that require the PR to be reworked." [Source: https://graphite.dev/blog/five-methods-for-stacking]
  - **Merge queue bottleneck**: Traditional merge queues treat each PR independently, breaking with stacks. Graphite's stack-aware merge queue uses speculative execution and bisection algorithm. "74% faster merge times at Ramp, 7 hours saved per engineer per week at Asana." [Source: https://graphite.dev/blog/the-first-stack-aware-merge-queue]
  - **Configure-once trunk**: Graphite init prompts for trunk branch selection, stored in `.git/.graphite_repo_config`. [Source: https://graphite-58cc94ce.mintlify.dev/docs/cli-quick-start.md]

- **Standard Tooling**:
  - **Graphite CLI (`gt`)**: Core workflow — `gt create` (new branch), `gt submit` (push + create/update PRs), `gt submit --stack` (push all PRs in stack), `gt sync` (pull trunk + clean up + restack), `gt log` (visualize stack), `gt up`/`gt down` (navigate stack). [Source: https://graphite-58cc94ce.mintlify.dev/docs/cheatsheet.md]
  - **GT MCP (for AI agents)**: "We built the GT MCP to capture this workflow and make it so any agent can follow stacking best practices. The GT MCP allows AI agents to automatically generate stacked PRs and transform large, AI-generated diffs into a sequence of smaller, focused pull requests." [Source: https://graphite.dev/blog/how-i-got-claude-to-write-better-code]
  - **Graphite AI Review** (Diamond → Graphite Agent): "Focuses on real bugs — not just style issues or best practices. Understands context — analyzes your entire codebase to provide relevant feedback." Supports custom rules and exclusions. [Source: https://graphite-58cc94ce.mintlify.dev/docs/ai-reviews.md]
  - **Graphite Agent** (Oct 2025): Unified AI reviewer + chat assistant. "Other AI reviewers stop at comments, but developers need more than just async feedback from a bot; they need a true collaborator that helps them create, edit, and merge AI-generated PRs." [Source: https://graphite.dev/blog/introducing-graphite-agent-and-pricing]
  - **Cursor Cloud Agents in Graphite** (Mar 2026): Dedicated Agents tab for creating, reviewing, refining, and merging agent-generated PRs. [Source: https://graphite.dev/blog/cursor-cloud-agents]
  - **Graphite + Cursor**: Graphite acquired by Cursor in Dec 2025. Continues as independent product. [Source: https://graphite.dev/blog/graphite-joins-cursor]
  - **Alternatives**: GitHub native `gh stack` (limited), `git-branchstack` (less mature). Graphite is the most mature PR stacking tool for CLI workflows.
  - **CodeRabbit**: AI-native code review — "In the agentic SDLC, code generation is becoming commoditized. Trusted verification is becoming the moat." [Source: https://coderabbit.ai/blog]
  - **The bottleneck thesis**: "Previously, we were limited by how quickly we could write code, but now the bottleneck is how quickly we can review it." [Source: https://graphite.dev/blog/introducing-graphite-agent-and-pricing]

## File Registry
| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | Manifest | Package metadata, runtime and dev dependencies | `dependencies = ["typer>=0.12", "rich>=13.0", "pydantic>=2.0", "pyyaml>=6.0.3"]` |
| `mise.toml` | Config | Task definitions (test, lint, format, check, etc.) | `tasks.test = "pytest tests/ -v"` |
| `.githooks/pre-commit` | Config | Pre-commit hook running lint + format + test | `mise run check` |
| `.githooks/pre-push` | Config | Pre-push hook running tests | `mise run test` |
| `src/deviate/cli/__init__.py` | Codebase_File | CLI command registration, init command | `cli.command(name="pr")(pr)` |
| `src/deviate/cli/macro.py` | Codebase_File | Macro-layer phase commands (explore, research, prd, shard) | `explore_app = typer.Typer(no_args_is_help=True)` |
| `src/deviate/cli/meso.py` | Codebase_File | Meso-layer commands (plan, pr, specify) | `def pr(action: str = ..., body_file: Path \| None = ..., merge: bool = ..., auto_merge: bool = ...):` |
| `src/deviate/cli/micro.py` | Codebase_File | TDD micro-layer phases (red, green, yellow, judge, refactor, execute) | `red_app = typer.Typer(no_args_is_help=True)` |
| `src/deviate/cli/review.py` | Codebase_File | Review pre/post CLI commands | `@review_app.command()\ndef pre(base: str = ..., branch: str \| None = ...):` |
| `src/deviate/state/config.py` | Codebase_File | SessionState, DeviateConfig, AgentConfig, ProfileConfig Pydantic models | `class SessionState(BaseModel): ... phase: Literal["IDLE","EXPLORE","RESEARCH","PRD","SHARD",...]` |
| `src/deviate/state/ledger.py` | Codebase_File | IssueRecord, TaskRecord, JSONL ledger persistence | `class IssueRecord(BaseModel): issue_id, type, title, status, source_file, blocked_by, coordinates_with` |
| `src/deviate/prompts/skills/deviate-pr/SKILL.md` | Skill | PR creation orchestration skill (5-step workflow) | `"Creates a PR from the current worktree branch"` |
| `src/deviate/prompts/skills/deviate-review/SKILL.md` | Skill | HITL Gate 3 lightweight review skill | `"Your job is a lightweight single-pass scan over the PR's diff, flagging cross-cutting issues that no single TDD cycle catches."` |
| `src/deviate/prompts/skills/deviate-execute/SKILL.md` | Skill | Direct task execution skill (non-TDD) | `"Use when executing a single task directly (without TDD cycle)"` |
| `specs/constitution.md` | Config | Project constitution with architecture, tech stack, testing, DoD | `"Three-Layer Architecture: Macro... Meso... Micro."` |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| FEATURE_SLUG | graphite-pr-stacks |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/004-graphite-pr-stacks/explore.md |
| EPIC_ID | graphite-pr-stacks |
| NEXT_ACTION | Run the `deviate-research` skill |
