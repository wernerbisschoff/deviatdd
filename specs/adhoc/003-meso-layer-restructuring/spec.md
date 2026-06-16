# FEATURE_SPECIFICATION: specs/adhoc/003-meso-layer-restructuring/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Target Domain**: `specs/adhoc/`
- **Issue**: ISS-ADH-003 — Meso-Layer Restructuring
- **Branch**: `feat/adhoc/003-meso-layer-restructuring`
- **Primary Workstations**:
  - `src/deviate/prompts/skills/deviate-shard/SKILL.md` — enhance to produce spec-level issue files
  - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` — enhance to produce spec-level issue files
  - `src/deviate/prompts/skills/deviate-plan/SKILL.md` — NEW skill for per-issue research/planning
  - `src/deviate/prompts/skills/deviate-specify/SKILL.md` — REMOVED (Plan phase absorbs its role)
  - `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — update to consume spec-enriched issues with embedded-first fallback
  - `src/deviate/cli/meso.py` — update CLI subcommand routing (remove specify, add plan)
  - `specs/DeviaTDD-api.md` — update endpoint architecture and workflow descriptions
  - `specs/DeviaTDD-architecture.md` — update layer diagrams and phase descriptions
  - `specs/constitution.md` — update three-layer architecture and HITL gate descriptions

## THE_PROBLEM_CONTRACT

The current meso-layer has a redundant `/deviate-specify` step that merely reformats what `/deviate-shard` already produces. By the time a developer reaches issue #5 in an epic, the original explore/research artifacts have drifted from current codebase reality. The workflow must be restructured to:

1. Merge specify into shard — issue files are born as full specs (user stories, Gherkin AC, edge cases) with no separate spec.md generation step.
2. Remove `/deviate-specify` entirely — the Plan phase absorbs the role of reviewing and contextualizing the spec-enriched issue.
3. Introduce `/deviate-plan` — a per-issue localized research phase that scans current codebase state, analyzes prior implementations, and produces a planning document before task decomposition.
4. Update `/deviate-tasks` to consume spec-enriched issues directly with embedded-first fallback (check issue file for `USER_STORIES_LEDGER` / `ATDD_ACCEPTANCE_CRITERIA` sections; fall back to `spec.md` if absent).
5. Update architecture documentation and constitution to reflect the new workflow topology.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `/deviate-shard` skill produces issue files with full spec-level detail: user stories (`US-NNN`), Gherkin acceptance criteria (`Given`/`When`/`Then`), edge cases, performance constraints, scope boundaries, and upstream requirement traceability
- `/deviate-adhoc` skill produces issue files in the same spec-enriched format as shard
- New `/deviate-plan` skill performs per-issue localized codebase research and produces a planning document (`plan.md`) contextualizing the issue for the current codebase state
- `/deviate-specify` skill is removed (both `SKILL.md` and its CLI entry points in `meso.py`)
- `/deviate-tasks` skill updated to consume spec-enriched issue format with embedded-first fallback: reads `## [USER_STORIES_LEDGER]` and `## [ATDD_ACCEPTANCE_CRITERIA]` from the issue file; if absent, falls back to `spec.md`
- Architecture docs (`DeviaTDD-api.md`, `DeviaTDD-architecture.md`) updated to reflect new workflow
- Constitution updated: HITL Gate 2 moves to after shard (not after specify), new Plan phase added

### Defensive Exclusions

- No modifications to micro-layer skills (red, green, yellow, judge, refactor, prune, e2e)
- No modifications to macro-layer skills (explore, research, prd)
- No modifications to CLI Python source code in `src/deviate/cli/` or `src/deviate/core/` except removing specify entry points in `meso.py`
- No changes to the append-only ledger protocol or issue/task record schemas
- No new CLI subcommands — Plan is a skill-only addition, not a new CLI entry

## PERFORMANCE_CONSTRAINTS

- `/deviate-plan` research scan completes in L_max <= 200ms (scans git log + issue ledger only; no network calls)
- `/deviate-shard` issue enrichment adds no more than 5% additional latency over the current shard execution time
- Embedded spec parsing in `/deviate-tasks` adds L_max <= 10ms overhead per call

## MULTI_TIERED_VERIFICATION_TARGETS

- **Unit**: N/A — this is a prompt/skill-only change
- **Integration**: Manual verification that each skill file parses as valid Markdown with required sections
- **E2E**: Run `deviate shard post` on a mock PRD and verify the output issue file contains `USER_STORIES_LEDGER`, `ATDD_ACCEPTANCE_CRITERIA`, and `EDGE_CASES_AND_BOUNDARIES` sections
- **Regression**: Run full test suite (`uv run pytest tests/ -v`) — must pass 430+ tests unchanged

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-Shard: Shard produces spec-enriched issue files

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: Shard enriches with user stories**
  **Given** a PRD with FR definitions
  **When** `deviate shard post` executes
  **Then** each generated issue file contains a `## [USER_STORIES_LEDGER]` section with one or more `US-NNN` entries
  **And** each `US-NNN` entry references an upstream `FR-NNN` from the PRD

**Scenario 2: Shard enriches with Gherkin acceptance criteria**
  **Given** a PRD with FR definitions
  **When** `deviate shard post` executes
  **Then** each generated issue file contains a `## [ATDD_ACCEPTANCE_CRITERIA]` section
  **And** each scenario block contains bold `**Given**` / `**When**` / `**Then**` clauses

**Scenario 3: Shard enriches with edge cases and performance constraints**
  **Given** a PRD with FR definitions
  **When** `deviate shard post` executes
  **Then** each generated issue file contains `## [EDGE_CASES_AND_BOUNDARIES]` and `## [PERFORMANCE_CONSTRAINTS]` sections

### US-002-Adhoc: Adhoc produces spec-enriched issue files

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: Adhoc enriches with full spec sections**
  **Given** a natural language feature description
  **When** the adhoc skill generates an issue file
  **Then** the issue file contains `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[EDGE_CASES_AND_BOUNDARIES]`, and `[PERFORMANCE_CONSTRAINTS]` sections

**Scenario 2: Adhoc format matches shard format**
  **Given** a spec-enriched issue file from adhoc
  **And** a spec-enriched issue file from shard
  **When** comparing the section structures
  **Then** both files contain the same required section headers in the same order

### US-003-Specify-Removal: Specify skill removed, Plan phase absorbs its role

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: Specify SKILL.md removed**
  **Given** the repository source tree
  **When** checking for `src/deviate/prompts/skills/deviate-specify/SKILL.md`
  **Then** the file does not exist

**Scenario 2: Specify CLI entry removed**
  **Given** the `deviate` CLI source
  **When** checking `src/deviate/cli/meso.py` for the `specify` command handler
  **Then** the `def specify(` function and all `_specify_*` helpers are removed or replaced with a stub that routes to Plan

**Scenario 3: Plan absorbs what Specify did**
  **Given** a spec-enriched issue file
  **When** the Plan phase executes
  **Then** it reads the issue's embedded spec sections (user stories, AC, edge cases)
  **And** produces `plan.md` contextualizing the issue

### US-004-Plan: Plan skill performs per-issue localized research

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: Plan scans codebase state**
  **Given** a spec-enriched issue file
  **When** `/deviate-plan` executes
  **Then** it reads the current codebase state via `git log` and the issue ledger
  **And** identifies what prior issues have implemented that are relevant

**Scenario 2: Plan produces plan.md**
  **Given** a spec-enriched issue file
  **When** `/deviate-plan` completes
  **Then** a `plan.md` file exists in the issue workspace directory
  **And** it contains an implementation strategy with file mappings and risk assessment

**Scenario 3: Plan completes within performance constraints**
  **Given** a spec-enriched issue file
  **When** `/deviate-plan` executes
  **Then** the full research scan completes in under 200ms
  **And** no network calls are made

### US-005-Tasks: Tasks consumes spec-enriched issues with embedded-first fallback

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: Tasks reads embedded spec from issue file**
  **Given** an issue file containing `## [USER_STORIES_LEDGER]` and `## [ATDD_ACCEPTANCE_CRITERIA]` sections
  **When** `/deviate-tasks` executes
  **Then** it reads user stories and acceptance criteria from the issue file
  **And** does not look for a separate `spec.md` file

**Scenario 2: Tasks falls back to spec.md**
  **Given** an issue file WITHOUT `[USER_STORIES_LEDGER]` or `[ATDD_ACCEPTANCE_CRITERIA]` sections
  **When** `/deviate-tasks` executes
  **Then** it falls back to reading from the adjacent `spec.md` file

**Scenario 3: Embedded parsing adds negligible overhead**
  **Given** a spec-enriched issue file
  **When** `/deviate-tasks` parses the embedded spec
  **Then** the parsing overhead is under 10ms

### US-006-Docs: Architecture docs reflect new workflow

* **Upstream Requirement Traceability**: FR-ADHOC-003

**Scenario 1: DeviaTDD-api.md updated**
  **Given** the file `specs/DeviaTDD-api.md`
  **When** checking for references to the new workflow
  **Then** it describes the state flow: `Explore → Research → PRD → Shard+Specify → [HITL Gate 2] → Plan → Tasks → Micro`
  **And** it no longer references `specify` as a separate phase

**Scenario 2: DeviaTDD-architecture.md updated**
  **Given** the file `specs/DeviaTDD-architecture.md`
  **When** checking for layer diagrams
  **Then** the meso-layer diagram shows `Plan` phase and merged `Shard+Specify` block

**Scenario 3: Constitution updated**
  **Given** the file `specs/constitution.md`
  **When** checking for HITL gates and phase descriptions
  **Then** HITL Gate 2 is described as occurring after shard
  **And** the meso-layer section includes the Plan phase

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| STATUS | SHARD_PENDING_COMMIT |
| EPIC_SLUG | adhoc |
| BRANCH_NAME | feat/adhoc/003-meso-layer-restructuring |
| SPEC_PATH | specs/adhoc/003-meso-layer-restructuring/spec.md |
| ISSUE_ID | ISS-ADH-003 |
| NEXT_ACTION | Run `deviate plan pre` to begin the localized research phase |
