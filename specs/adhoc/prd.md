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
