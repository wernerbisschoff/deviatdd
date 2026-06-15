# FEATURE_SPECIFICATION: specs/adhoc/004-deviate-review-skill/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Issue**: ISS-ADH-004 — DeviaTDD Code Review Skill
- **Epic Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/004-deviate-review-skill.md`
- **Primary Architectural Workstation**:
  - `src/deviate/prompts/skills/deviate-review/SKILL.md` — NEW: prompt skill for structured code review
  - `src/deviate/cli/review.py` — NEW: Typer subcommand module with review pre/post commands
  - `src/deviate/cli/__init__.py` — MODIFY: register review subcommand
  - `.claude/skills/deviate-review/SKILL.md` — installed via `deviate init` skill discovery
- **Review Report Storage**: `.deviate/review/reports/` — reports are advisory artifacts, never committed

## THE_PROBLEM_CONTRACT

The existing code review workflow (`~/.claude/skills/tools-review/`) relies on a standalone bash orchestrator decoupled from the DeviaTDD governance stack. When reviewing DeviaTDD-managed code, the review must verify constitution compliance and PRD traceability — domains the generic `tools-review` skill does not enforce. A new `deviate-review` skill is needed that:

1. Follows the DeviaTDD pre/post CLI command pattern
2. Always reads `specs/constitution.md` and enforces its invariants
3. Resolves and reads the appropriate PRD (epic-level first, adhoc fallback)
4. Produces structured reports with machine-parseable `Fix Instructions` for cheaper model handoff
5. Auto-discovers via `discover_skills()` into agent directories during `deviate init`
6. Stores reports in `.deviate/review/reports/` (advisory scope — no commit, no ledger mutation)

## SCOPE_BOUNDARIES

### Hard Inclusions

- `src/deviate/prompts/skills/deviate-review/SKILL.md` — full prompt skill with system instructions, execution sequence (pre → domain analysis → report generation → user selection → fix implementation → post), domain rubrics (Security, Pragmatism, Idiomacy, Clean Code, Constitution, PRD), output schemas, edge case handling, and DeviaTDD ecosystem integration
- `src/deviate/cli/review.py` — `deviate review pre` (git state gathering, diff generation against merge-base with `main`, governance file discovery with PRD resolution: epic first, adhoc fallback, JSON contract emission, duplicate-report warning) and `deviate review post` (review report persistence to `.deviate/review/reports/`, no commit/stage)
- `src/deviate/cli/__init__.py` — add `cli.add_typer(review_app, name="review")` to register the review subcommand
- PRD anchoring logic: resolves PRD in priority order — (1) branch-derived epic PRD at `specs/{EPIC}/prd.md`, (2) adhoc PRD at `specs/adhoc/prd.md`. Warnings emitted when no PRD found.
- Review domains must include `Constitution` and `PRD` alongside Security, Pragmatism, Idiomacy, and Clean Code
- Diff computation: compare current branch against merge-base with `main` (default); user may override target via `--base` flag
- Pre command always emits a contract even if diff is empty — user input is the final decider on whether to proceed
- Post command writes report to `.deviate/review/reports/review-report-{timestamp}.md` — no commit, no staging, no ledger mutation
- Pre command checks `.deviate/review/reports/` for existing reports and emits a `report_exists` warning field in the contract

### Defensive Exclusions

- Do NOT modify any existing phase skills (red, green, yellow, judge, refactor, prune, e2e, execute, hotfix)
- Do NOT modify `specs/constitution.md` — review is advisory, not a governance phase
- Do NOT modify agent backend, prompt assembly, or the TDD cycle body in `micro.py`
- Do NOT add review as a phase in `_PHASE_MAP` or `_SKILL_NAMES` — review is a standalone skill, not a TDD cycle phase
- Do NOT modify `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md` — review is an optional tool, not part of the core pipeline
- Do NOT create new data models or ledger entries for review — the output is a plain markdown report file in `.deviate/review/reports/`
- Do NOT add dependencies beyond what's already in `pyproject.toml`
- Do NOT commit or stage review reports — reports live in `.deviate/` and are advisory only

## PERFORMANCE_CONSTRAINTS

- `deviate review pre` — L_max <= 500ms (git diff, PRD resolution, file discovery)
- `deviate review post` — L_max <= 200ms (write report to `.deviate/review/reports/`)
- No model invocation during pre or post — review model invocation is the agent's responsibility via the SKILL.md prompt
- Review report persistence is filesystem-only — no network, no API calls

## MULTI_TIERED_VERIFICATION_TARGETS

### Unit Sandbox Targets

| Test ID | Test Name | Verification |
|---------|-----------|-------------|
| UT-01 | `test_review_pre_emits_contract` | `deviate review pre` emits valid JSON contract on stdout |
| UT-02 | `test_review_pre_finds_constitution` | Contract contains `constitution_path` pointing to `specs/constitution.md` |
| UT-03 | `test_review_pre_resolves_prd_epic_first` | When epic `specs/{epic}/prd.md` exists, contract `prd_path` points to it (not adhoc fallback) |
| UT-04 | `test_review_pre_falls_back_to_adhoc_prd` | When epic PRD absent, contract `prd_path` points to `specs/adhoc/prd.md` |
| UT-05 | `test_review_pre_no_prd_warning` | When no PRD found, contract emits `prd_warning: true` (no error exit) |
| UT-06 | `test_review_pre_diff_against_main` | `diff` field in contract is computed against merge-base with `main` |
| UT-07 | `test_review_pre_empty_diff` | When no changes vs base, contract still emitted with empty `diff` field |
| UT-08 | `test_review_pre_custom_base` | `--base custom-branch` overrides default `main` merge-base |
| UT-09 | `test_review_pre_existing_report_warning` | When `.deviate/review/reports/` already contains a report, contract includes `report_exists: true` warning |
| UT-10 | `test_review_post_persists_report` | Post writes report to `.deviate/review/reports/review-report-{timestamp}.md` |
| UT-11 | `test_review_post_no_artifact` | Graceful handling when no report data provided in contract |
| UT-12 | `test_review_post_no_commit` | After post, `git status` shows no staged/committed changes |
| UT-13 | `test_review_skill_discovery` | `discover_skills()` returns path to `deviate-review` skill |
| UT-14 | `test_cli_registration` | `deviate review --help` shows pre and post subcommands |

### Integration Sandbox Targets

- `tests/test_integration/test_review_cycle.py::test_review_full_cycle` — full pre→(agent review)→post cycle with mock agent

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-PRE_COMMAND: `deviate review pre` contract emission

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION — no formal PRD found for adhoc epic; requirement token FR-ADHOC-004 inferred from issue body]

1. **Given** a DeviaTDD worktree with uncommitted changes
   **When** `deviate review pre` is invoked
   **Then** a valid JSON contract is emitted on stdout containing fields: `status`, `diff`, `constitution_path`, `prd_path`, `base_branch`, `report_exists`, and `timestamp`

2. **Given** a branch `feat/adhoc/004-deviate-review-skill` ahead of `main`
   **When** `deviate review pre` is invoked
   **Then** the `diff` field contains the unified diff between merge-base(`main`, HEAD) and HEAD

3. **Given** a branch with no changes relative to merge-base with `main`
   **When** `deviate review pre` is invoked
   **Then** the contract is still emitted with `diff` set to empty string and `status` set to `"READY"`

4. **Given** an existing PRD at `specs/adhoc/prd.md` and no epic PRD at `specs/{epic}/prd.md`
   **When** `deviate review pre` is invoked
   **Then** the contract's `prd_path` resolves to `specs/adhoc/prd.md`

5. **Given** an existing epic PRD at `specs/{epic}/prd.md` and an adhoc PRD at `specs/adhoc/prd.md`
   **When** `deviate review pre` is invoked
   **Then** the contract's `prd_path` resolves to `specs/{epic}/prd.md` (epic priority)

6. **Given** no PRD at either `specs/{epic}/prd.md` or `specs/adhoc/prd.md`
   **When** `deviate review pre` is invoked
   **Then** the contract's `prd_warning` is `true`, `prd_path` is `null`, and exit code is 0

7. **Given** a `.deviate/review/reports/` directory already containing review artifacts
   **When** `deviate review pre` is invoked
   **Then** the contract includes `report_exists: true` as a warning field

8. **Given** the flag `--base develop`
   **When** `deviate review pre --base develop` is invoked
   **Then** the diff is computed against merge-base(`develop`, HEAD) instead of `main`

9. **Given** `specs/constitution.md` exists at the repo root
   **When** `deviate review pre` is invoked
   **Then** the contract's `constitution_path` field points to the resolved absolute path of `specs/constitution.md`

### US-002-SKILL_PROMPT: Structured review prompt with domain rubrics

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION]

1. **Given** the SKILL.md at `src/deviate/prompts/skills/deviate-review/SKILL.md`
   **When** the prompt is loaded
   **Then** it contains domain rubrics for all six domains: Security, Pragmatism, Idiomacy, Clean Code, Constitution, and PRD

2. **Given** the SKILL.md execution sequence
   **When** a review is initiated
   **Then** the sequence executes: pre → domain analysis → report generation → user selection → fix implementation → post

3. **Given** a review report with identified issues
   **When** the report is generated
   **Then** each issue has a machine-parseable `Fix Instructions` block with deterministic commands a cheaper model can execute

4. **Given** a review report
   **When** the report is generated
   **Then** it contains a mandatory `Constitution Compliance` section evaluating the diff against each constitutional invariant in `specs/constitution.md`

5. **Given** a review report and a resolved PRD path
   **When** the report is generated
   **Then** it contains a mandatory `PRD Traceability` section mapping changed code areas to upstream PRD requirements

6. **Given** the review post phase is reached
   **When** the user selects specific fix suggestions from the report
   **Then** the model implements only the selected fixes (user-prompted, not automatic)

### US-003-REPORT_FORMAT: Structured report with machine-parseable fix instructions

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION]

1. **Given** a completed domain analysis
   **When** the review report is written
   **Then** the report follows the schema: `# Review Report: {issue_id}` → `## Files Reviewed` → `## Constitution Compliance` → `## PRD Traceability` → `## Domain Findings` → `## Fix Instructions` → `## Summary`

2. **Given** a `## Fix Instructions` section
   **When** the section is rendered
   **Then** each instruction is a deterministic CLI command or file edit directive prefixed with a step number and enclosed in a code block

3. **Given** a `## Domain Findings` section
   **When** the section is rendered
   **Then** each domain (Security, Pragmatism, Idiomacy, Clean Code, Constitution, PRD) has its own subsection with a PASS/WARN/FAIL verdict and supporting evidence from the diff

### US-004-POST_COMMAND: Report persistence to `.deviate/review/reports/`

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION]

1. **Given** a review report string in the contract
   **When** `deviate review post` is invoked
   **Then** the report is written to `.deviate/review/reports/review-report-{timestamp}.md`

2. **Given** a successful report write
   **When** `deviate review post` completes
   **Then** `git status` shows zero staged or committed changes — the report is advisory only

3. **Given** no report data in the contract
   **When** `deviate review post` is invoked
   **Then** the command exits gracefully with a no-op message (exit code 0)

4. **Given** the `.deviate/review/reports/` directory does not exist
   **When** `deviate review post` is invoked
   **Then** the directory is created automatically before the report is written

### US-005-CLI_REGISTRATION: Standalone subcommand registration

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION]

1. **Given** the DeviaTDD CLI (`src/deviate/cli/__init__.py`)
   **When** the review subcommand is registered
   **Then** `cli.add_typer(review_app, name="review")` is present in the module

2. **Given** a registered review subcommand
   **When** `deviate review --help` is invoked
   **Then** the output lists `pre` and `post` subcommands

3. **Given** the review SKILL.md at `src/deviate/prompts/skills/deviate-review/SKILL.md`
   **When** `discover_skills()` is called
   **Then** the returned list includes the `deviate-review` skill

### US-006-SELF_CONTAINED_MODE: Branch-targeted review outside DeviaTDD context

* **Upstream Requirement Traceability**: FR-ADHOC-004 [NEEDS_CLARIFICATION]

1. **Given** a target branch `feature/foo` specified via `deviate review pre --branch feature/foo`
   **When** the pre command executes
   **Then** it diffs `feature/foo` against its merge-base with `main`

2. **Given** a self-contained review outside the DeviaTDD directory structure
   **When** no `specs/constitution.md` is found
   **Then** the contract's `constitution_path` is `null` and a `constitution_warning: true` field is emitted (review continues without constitution domain)

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| **STATUS** | SPECIFIED |
| **EPIC_SLUG** | adhoc |
| **BRANCH_NAME** | feat/adhoc/004-deviate-review-skill |
| **SPEC_PATH** | specs/adhoc/004-deviate-review-skill/spec.md |
| **ISSUE_ID** | ISS-ADH-004 |
| **TRACEABILITY** | WARN — `prd_requirements` array empty; `FR-ADHOC-004` inferred from issue body, no formal PRD artifact |
| **NEXT_ACTION** | `/deviate-tasks` — decompose into Red-Green-Refactor task units |
