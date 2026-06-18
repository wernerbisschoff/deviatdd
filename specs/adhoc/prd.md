# ADHOC_REQUIREMENTS_LEDGER
> Append-only. Managed automatically by /deviate-adhoc. Do not edit manually.

## FR-ADHOC-001: Streaming Pipeline Monitor with Task Status Display

- **Description**: Implement a live-updating task status dashboard that renders during automated `deviate run --all` execution, showing task list with completion markers, a 5-line rolling agent output buffer, and current phase/status indicator.
- **Preconditions**: At least one task exists in `specs/**/tasks.jsonl`. Rich is installed (already a dependency). Terminal is interactive (TTY) or `--json` fallback is active.
- **Inputs/Outputs**: Input: JSONL task ledger, agent subprocess stdout/stderr. Output: Rich `Live` display with formatted task table, agent output buffer, and status bar.

### Acceptance Criteria
1. **AC-ADHOC-001-01**: Given `deviate run --all` with 5 tasks, When tasks are processed sequentially through RED→GREEN→REFACTOR, Then the display shows `[X]` for completed, `[/]` for in-progress, `[ ]` for pending tasks, updated in real-time.
2. **AC-ADHOC-001-02**: Given an agent is executing a phase, When the agent emits stdout/stderr lines, Then the last 5 lines are displayed in a rolling buffer section below the task list, each truncated to one terminal-width line, with newest at the bottom.
3. **AC-ADHOC-001-03**: Given the agent completes a phase transition, When the task record is updated in the ledger, Then the display refreshes the task marker and the status bar reflects the new phase (RED→GREEN→REFACTOR→COMPLETED) within one render cycle.
4. **AC-ADHOC-001-04**: Given stdout is not a TTY (piped or redirected), When `deviate run --all` executes, Then the Live display is disabled and plain-status JSONL events are emitted instead.
5. **AC-ADHOC-001-05**: Given the agent subprocess exits with a non-zero code, When the failure is detected, Then the task marker changes to `[✗]` with the error reason appended, the agent output buffer preserves the failing output, and remaining tasks continue processing.

## FR-ADHOC-003: Meso-Layer Restructuring — Merge Specify into Shard, Introduce Plan Phase

- **Description**: Restructure the DeviaTDD meso-layer workflow by merging the `/deviate-specify` step into `/deviate-shard` and `/deviate-adhoc` (so issues are born as full specs with Gherkin AC, user stories, and edge cases), deprecating `/deviate-specify` as a standalone step, and introducing a new `/deviate-plan` skill that performs per-issue localized research and planning before task decomposition.
- **Preconditions**: Existing DeviaTDD skill infrastructure (`src/deviate/prompts/skills/`), architecture docs (`specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`), and constitution (`specs/constitution.md`).
- **Inputs/Outputs**: Input: Current skill SKILL.md files, architecture docs, API docs. Output: Updated skill files (shard, adhoc, plan, tasks), updated architecture/API docs, deprecated specify skill.

### Acceptance Criteria
1. **AC-ADHOC-003-01**: Given the `/deviate-shard` skill is invoked, When it produces issue files, Then each issue file contains full spec-level detail including user stories (US-NNN), Gherkin acceptance criteria (Given/When/Then), edge cases, and scope boundaries — not just high-level descriptions.
2. **AC-ADHOC-003-02**: Given the `/deviate-adhoc` skill is invoked, When it produces an issue file, Then the issue file uses the same spec-enriched format as shard (user stories, Gherkin AC, edge cases).
3. **AC-ADHOC-003-03**: Given the `/deviate-specify` skill exists, When a user attempts to invoke it, Then the skill is marked as deprecated and redirects to the new workflow (shard produces specs directly).
4. **AC-ADHOC-003-04**: Given a new `/deviate-plan` skill, When invoked on a specified issue, Then it performs localized codebase research (what changed since epic-level explore), analyzes prior issue implementations, and produces a planning document that contextualizes the issue for current codebase state before `/deviate-tasks` runs.
5. **AC-ADHOC-003-05**: Given the architecture docs (`DeviaTDD-api.md`, `DeviaTDD-architecture.md`), When updated, Then the workflow diagrams reflect the new flow: Macro(Explore→Research→PRD→Shard+Specify) → Meso(Plan→Tasks) → Micro(RED→GREEN→JUDGE→REFACTOR), with HITL Gate 2 moved to after shard.
6. **AC-ADHOC-003-06**: Given the `/deviate-tasks` skill, When it reads an issue for decomposition, Then it consumes the spec-enriched issue format directly (no separate spec.md lookup needed).

## FR-ADHOC-004: DeviaTDD Code Review Skill — /deviate-review with Constitution & PRD Anchoring

- **Description**: Create a `deviate`-integrated `/deviate-review` code review skill that performs structured multi-domain code review over a defined git scope, with mandatory constitution compliance checking and PRD anchoring. The skill follows the DeviaTDD pre/post command pattern and always references either the epic PRD (`specs/{EPIC_SLUG}/prd.md`) or the adhoc PRD (`specs/adhoc/prd.md`).
- **Preconditions**: Git repository with `specs/constitution.md` present. At least one PRD exists (epic or adhoc). `deviate` CLI is installed.
- **Inputs/Outputs**: Input: git diff scope, constitution, PRD. Output: structured review report in markdown (report in `review-report.md`, machine-parseable `Fix Instructions` block).

### Acceptance Criteria
1. **AC-ADHOC-004-01**: Given a git diff scope (working tree or branch), When `deviate review pre` is invoked, Then it emits a JSON contract containing git state, diff files, constitution path, and resolved PRD path (epic first, adhoc fallback).
2. **AC-ADHOC-004-02**: Given a review report is generated with `Fix Instructions`, When `deviate review post` is invoked with the report path, Then it is saved as a timestamped `review-report-{timestamp}.md` under `.deviate/review/reports/`, and the post status is `SUCCESS`. Reports are advisory artifacts — never committed or staged.

## FR-ADHOC-005: Per-Phase Model Configuration with Configurable Model Routing

- **Description**: Introduce a per-phase model configuration layer that allows users to specify which LLM model each DeviaTDD phase uses. The configuration lives in `.deviate/config.toml` under a `[models]` section with a reserved `default` key (applies to all phases) and per-phase override keys. Both `opencode` and `droid` backends receive `--model <id>`. The `claude` backend ignores model config. Phases without an explicit entry fall through to `default`, and when neither exists no `--model` flag is emitted.
- **Preconditions**: `.deviate/config.toml` exists (created by `deviate init`). Both `opencode run --model` and `droid exec --model` flags are validated. Constitution §`Model Tiering` already documents the intended routing.
- **Inputs/Outputs**: Input: `[models]` section in config with optional `default` key and phase-specific keys. Output: model-aware agent invocation that resolves `phase → override → default → none` and passes `--model <id>` when resolved.

### Acceptance Criteria
1. **AC-ADHOC-005-01**: Given `.deviate/config.toml` contains `[models]\ndefault = "opencode/deepseek-v4-flash"`, When any phase invokes the agent, Then the command includes `--model opencode/deepseek-v4-flash`.
2. **AC-ADHOC-005-02**: Given `.deviate/config.toml` has `[models]\ndefault = "opencode/deepseek-v4-flash"\njudge = "opencode/deepseek-v4-pro"`, When the JUDGE phase invokes the agent, Then the command includes `--model opencode/deepseek-v4-pro` (override wins), and when RED invokes, Then the command includes `--model opencode/deepseek-v4-flash` (default applies).
3. **AC-ADHOC-005-03**: Given `.deviate/config.toml` has no `[models]` section, When any phase invokes the agent, Then no `--model` flag is appended.
4. **AC-ADHOC-005-04**: Given `.deviate/config.toml` has `[models]\nplan = "deepseek-v4-pro"`, When the PLAN phase uses the `droid` backend, Then the command includes `["droid", "exec", "--model", "deepseek-v4-pro"]`.
5. **AC-ADHOC-005-05**: Given `.deviate/config.toml` has `[models]\nred = "opencode/deepseek-v4-flash"`, When the RED phase uses the `claude` backend, Then the command is `["claude", "-p"]` without `--model`.
6. **AC-ADHOC-005-06**: Given the constitution documents the default model tiering, When `deviate init` generates `.deviate/config.toml`, Then the `[models]` section is absent.
7. **AC-ADHOC-005-07**: Given a TDD cycle with different models configured per phase, When the cycle runs, Then each phase invocation uses the resolved model for that phase and the handover manifest is parsed consistently.

## FR-ADHOC-006: Offline Context Documentation System — Integrate `context` CLI into DeviaTDD Framework

- **Description**: Integrate the `context` offline documentation CLI into the DeviaTDD framework across all layers — detect the binary at init time, set a config boolean, inject governance mandates into CLAUDE.md/AGENTS.md, and thread `context add` / `context query` instructions through all phase skill prompts so that AI agents use local, version-pinned documentation as their primary reference source instead of web fetching.
- **Preconditions**: `context` binary on `$PATH` (optional — system works without it). `.deviate/config.toml` exists (created by `deviate init`). Existing prompt templates under `src/deviate/prompts/`.
- **Inputs/Outputs**: Input: `context` binary. Output: Updated `DeviateConfig` with `use_context` boolean; updated governance seeds (`claudemd_seed.md`, `agents_seed.md`) with context mandate section; updated `core.md` universal invariants with context reference; updated skill prompts for explore, adhoc, research, plan, and layer preambles with `context add` / `context query` instructions.

### Acceptance Criteria
1. **AC-ADHOC-006-01**: Given the `context` binary is present on `$PATH`, When `deviate init` runs, Then `.deviate/config.toml` contains `use_context = true`.
2. **AC-ADHOC-006-02**: Given the `context` binary is NOT on `$PATH`, When `deviate init` runs, Then `.deviate/config.toml` contains `use_context = false` (or the field is absent, defaulting to false).
3. **AC-ADHOC-006-03**: Given `context` is detected during init, When `deviate init` completes, Then `CLAUDE.md` and `AGENTS.md` both contain a `## Offline Context Documentation System` section with `context query`, `context list`, and `context add` instructions.
4. **AC-ADHOC-006-04**: Given a `/research` phase execution with `context` available, When the architecture subagents perform library-specific analysis, Then the skill prompt instructs using `context query <source> <topic>` as the primary documentation mechanism, with web fetch as last resort.
5. **AC-ADHOC-006-05**: Given a `/plan` phase execution with `context` available, When the planning analyst performs localized codebase research, Then the skill prompt instructs using `context query` for understanding library APIs and framework conventions.
6. **AC-ADHOC-006-06**: Given an `/explore` or `/adhoc` phase execution, When the subagent identifies the project's dependency ecosystem, Then the skill prompt instructs running `context add <source>` for detected frameworks to index their documentation.
