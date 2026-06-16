# DeviaTDD CLI Endpoint Architecture

This document describes the `deviate` CLI — the unified Python command-line application
(`src/deviate/`) that drives all DeviaTDD operations. All legacy shell scripts have been
phased out in favor of a deterministic pre/post subcommand pattern powered by Typer.

---

## Part 1: Unified CLI Endpoints (`deviate`)

The `deviate` command-line application decouples the execution environments from raw machine
scripts. All commands are registered in `src/deviate/cli/__init__.py` using Typer's
`add_typer` and `command` decorators.

### 1. Bootstrap & Governance

#### `deviate init`

* **Source:** `src/deviate/cli/__init__.py`
* **Description:** Initializes a standard project-level DeviaTDD compliance framework. Builds
  `.deviate/` dot directory, establishes a default tracking layer, injects project-wide
  rules inside `specs/constitution.md`, and installs DeviaTDD prompt skills into detected
  agent runtime directories (`.claude/skills/`, `.opencode/skills/`, `.factory/skills/`).
* **Execution Modes:**
  * **Offline Mode (Default):** Scans root project files using regex to resolve `${VARIABLE}`
    placeholders in constitution boilerplate. Completes in L_max <= 50ms. All 6 variables
    are resolved via `_resolve_placeholder()` (`src/deviate/cli/__init__.py`): `PROJECT_NAME`,
    `REPO_ROOT`, `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`,
    `TARGET_COVERAGE_MINIMUM`. Unresolvable vars fall back to `"UNKNOWN"` with stderr warning.
  * **Onboard Prompt Mode (Aspirational):** `deviate init --generate-constitution` flag is
    declared but the LLM runner invocation is not yet wired. When implemented, it will invoke
    an authorized LLM runner via the configured agent backend to analyze project state and
    generate a tailored constitution.
* **Tokenized Placeholder Resolution:**
  | Variable | Source File | Detection Pattern |
  | --- | --- | --- |
  | `${PROJECT_NAME}` | `pyproject.toml`, `package.json` | Project name extraction |
  | `${REPO_ROOT}` | Filesystem | Absolute path of git root |
  | `${TARGET_BACKEND_FRAMEWORK}` | `pyproject.toml`, `package.json`, `mix.exs` | Framework name regex |
  | `${TARGET_PACKAGE_MANAGER}` | `pyproject.toml`, `package.json`, `Cargo.toml` | Package manager detection |
  | `${TARGET_TEST_RUNNER}` | `pyproject.toml`, `package.json` | Test framework detection |
  | `${TARGET_COVERAGE_MINIMUM}` | Default: `80%` | Configurable via profile |
* **Input Parameters:**
  * `--agent-export-mode [local|global]` (Defaults to `local`)
  * `--generate-constitution` (Flag: declared, LLM runner not yet wired)
  * `--agent [claude|opencode|droid]` (Override auto-detect)
* **Output Artifacts:**
  * `.deviate/config.toml` — Persisted configuration profile
  * `.deviate/session.json` — Current session state snapshot
  * `.deviate/.gitignore` — Excludes session.json from version control
  * `specs/constitution.md` — Resolved boilerplate constitution
  * Agent skill directories — DeviaTDD prompt skills installed per-agent
* **Governance File Provisioning:** Writes `## DeviaTDD Orchestration Rules` block to both
  `CLAUDE.md` and `AGENTS.md`. Idempotent: replaces existing block if present, appends if
  file exists without the block, creates if absent.
* **Common Flags:** `deviate init` currently does not accept `--json`/`--quiet`. The
  `@with_json_quiet` decorator (in `cli/_common.py`) is applied to all `pre` subcommands
  in macro, meso, and micro layers — emitting JSON contracts on stdout when `--json` is
  passed and suppressing Rich output when `--quiet` is passed.
* **Constitution Governance:** The `/deviate-constitution` skill (prompt skill, not a CLI
  command) handles governance artifact generation — initialize or update `specs/constitution.md`
  as an authoritative document defining architectural standards, tech stack constraints,
  testing mandates, and completion criteria.

#### `/deviate-shard` (Macro Layer)

* **Objective:** Decomposes the PRD into standalone, testable issue files.
* **Granularity Guidelines:**
  * **Target:** Average of 5 issues per feature shard
  * **Each issue must be a vertical slice:** Delivers a complete, testable behavior end-to-end
  * **Independence:** Each issue should be independently implementable and testable
  * **Scope bounds:** No issue should require <3 tasks or >10 tasks
  * **Testability:** Each issue must have clear acceptance criteria

---

### 2. Macro Layer: Feature Scoping (pre/post)

All macro-layer commands follow the `pre`/`post` subcommand pattern (except `init`).
Every `pre` subcommand accepts `--json` (emit JSON contract to stdout) and `--quiet`
(suppress diagnostic output).

#### `deviate feature create <title-or-issue-id>`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Creates a new feature workspace. Consumes a raw title string, derives a
  URL-friendly kebab-case slug, creates the git branch or worktree, scaffolds the feature
  subdirectory under `specs/{FEATURE_SLUG}/`, and sets it as the active workspace in
  `.deviate/session.json`. Returns the slug and directory path.
* **Input Parameters:**
  * `<title-or-issue-id>` (Positional: freeform description or ticket ID)
  * `--slug <slug>` (Optional: explicit slug override)
* **Common Flags:** `--json`, `--quiet`

#### `deviate explore pre <problem> [--slug]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Allocate a feature bucket and register a scratch ledger entry. Validates
  the constitution, transitions session to EXPLORE, allocates the bucket via
  `allocate_feature_bucket()`, appends a DRAFT issue record, and emits a JSON contract to
  stdout (spec_target, feature_dir, issue_id, etc.).
* **Common Flags:** `--json`, `--quiet`

#### `deviate explore post`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validate `explore.md` output. Reads the artifact, validates required
  sections via `validate_artifact()`, runs pre-commit hooks, commits with `docs({NNN}):
  create explore.md`, and saves the session.

#### `deviate research pre [<epic>]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validates that `explore.md` exists and constitution passes, then transitions
  session to RESEARCH and emits the JSON contract (design_target, data_model_target, etc.).
* **Common Flags:** `--json`, `--quiet`

#### `deviate research post`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Scans for constitutional violations, validates both `design.md` and
  `data-model.md` with `validate_artifact()`, runs pre-commit hooks, commits both artifacts,
  and saves session.

#### `deviate prd pre [--dry-run]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Discovers the active epic slug, validates `design.md` and `data-model.md`
  exist, transitions session to PRD (or dry-run), and emits JSON contract.
* **Common Flags:** `--json`, `--quiet`

#### `deviate prd post <manifest>`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Loads the manifest JSON, validates `prd.md` sections against
  `ARTIFACT_VALIDATORS`, checks FR requirement traceability with `extract_prd_requirements()`,
  runs pre-commit hooks, commits, and saves session.

#### `deviate shard pre [--dry-run]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Discovers epic, validates `prd.md` exists, computes the next `ISS-{NNN}`
  issue ID from the ledger, transitions session to SHARD, and emits JSON contract with
  `next_issue_id`.
* **Common Flags:** `--json`, `--quiet`

#### `deviate shard post <manifest>`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validates shard output (YAML frontmatter, empty files), registers each
  issue as `BACKLOG` status in `issues.jsonl`, runs pre-commit hooks, and resets session to
  `IDLE`.

#### `deviate feature create <title-or-issue-id>`

* **Source:** `src/deviate/cli/feature.py`
* **Description:** Creates a new feature workspace. Consumes a raw title string, derives a
  URL-friendly kebab-case slug, creates the git branch (`feat/{SLUG}`), scaffolds the feature
  subdirectory under `specs/{FEATURE_SLUG}/`, and sets it as the active workspace in
  `.deviate/session.json`. Returns the slug and directory path.
* **Input Parameters:**
  * `<title-or-issue-id>` (Positional: freeform description or ticket ID)
  * `--slug <slug>` (Optional: explicit slug override)
* **Common Flags:** `--json`, `--quiet`

#### `deviate adhoc pre <task-description>`

* **Source:** `src/deviate/cli/adhoc.py`
* **Description:** Compressed fast-path for low/medium complexity tasks. Runs a complexity
  gate evaluation (`ComplexityGate.classify()` in `core/complexity.py`) before proceeding.
  On acceptance, performs proportional lightweight codebase exploration, emits a JSON
  contract with `next_ADH_num`, `adhoc_dir`, and `prd_path` for the agent to synthesize a
  single vertical-slice issue.
* **Complexity Gate:**
  * **Low (1-2 files, localized):** Proceed. Minimal exploration.
  * **Medium (2-5 files, bounded):** Proceed. Bounded exploration + abbreviated PRD.
  * **High (5+ files, new modules):** Halt with `COMPLEXITY_GATE_REJECTION`. Direct user
    to run `/deviate-explore` for a full epic workflow.
* **Common Flags:** `--json`, `--quiet`

#### `deviate adhoc post <manifest>`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validates the issue markdown, appends a condensed FR entry to
  `specs/adhoc/prd.md`, registers the issue in `specs/issues.jsonl` with an `ADH-{NNN}`
  identifier, runs pre-commit hooks, and commits.

---

### 3. Meso Layer: Issue Engineering (pre/post)

All meso-layer commands follow the `pre`/`post` subcommand pattern. Every `pre` subcommand
accepts `--json` (emit JSON contract to stdout) and `--quiet` (suppress output).

> **Deprecated:** Specify functionality is absorbed into shard. Shard now produces spec-enriched issue files with full Gherkin AC, user stories, and edge cases — no separate specify step. The `/deviate-tasks` skill reads these embedded specs directly. See `deviate shard pre/post` and `deviate plan pre/post` below.

#### `deviate specify pre [--issue <id>] [--force] [--dry-run]` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Selects and claims an issue. If `--issue` is given, selects that specific
  issue and fails if unclaimable. If omitted, iterates `select_unblocked_candidates()` in a
  try-claim loop. Each claim creates a git worktree at `.worktrees/feat/{epic}/{issue}/`,
  runs mise setup, writes the claim to the worktree's ledger, pushes the branch to remote,
  and emits a JSON contract with spec_target, worktree_path, branch_name, traceability
  status, constitution commands, etc. If no feature workspace exists yet, invokes
  `deviate feature create` internally to scaffold it.
* **PRD Traceability:** Validates that FR references in the issue body exist in the PRD.
* **Session:** Transitions to SPECIFY with `active_issue_id` set.
* **Common Flags:** `--json`, `--quiet`

#### `deviate specify post [--force]` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Validates `spec.md` Gherkin syntax via `validate_gherkin_syntax()`,
  commits the spec, and transitions session to TASKS.

#### `deviate specify <issue-id>` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Direct positional-argument interface. Validates the issue exists, creates
  the spec directory, forces session to SPECIFY with `active_issue_id` set.

#### `deviate plan pre [--issue <id>] [--dry-run]` (Planned — CLI not yet created)

* **Source:** `src/deviate/cli/meso.py` (planned)
* **Description:** NEW per-issue localized research phase. Loads the spec-enriched issue file (scanning `## [USER_STORIES_LEDGER]` and `## [ATDD_ACCEPTANCE_CRITERIA]` sections), scans current codebase state via git log and issue ledger, analyzes what prior issues have implemented, and identifies integration points, dependencies, and potential conflicts. Emits a JSON contract for the agent to produce `plan.md` with implementation strategy, file mappings, and risk assessment.
* **Session:** Transitions to PLAN with `active_issue_id` set.
* **Common Flags:** `--json`, `--quiet`

#### `deviate plan post [--force]` (Planned — CLI not yet created)

* **Source:** `src/deviate/cli/meso.py` (planned)
* **Description:** Validates `plan.md` exists and is non-empty, runs pre-commit hooks, commits `docs({scope}): add plan.md`, and transitions session to TASKS.

#### `deviate tasks pre [--force] [--dry-run]`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Loads session (accepts PLAN or TASKS), resolves the spec-enriched issue file
  (reads embedded `## [USER_STORIES_LEDGER]` and `## [ATDD_ACCEPTANCE_CRITERIA]` sections; falls
  back to `spec.md` when absent), detects worktree and branch, resolves constitution commands,
  and emits JSON contract with spec_path, plan_path, tasks_target, worktree info. The agent
  decomposes the spec into `tasks.md` (the *what/why/how* document) and the CLI writes the
  corresponding rows to `tasks.jsonl` (the *append-only event ledger*). See §3 for the
  `tasks.md` vs `tasks.jsonl` distinction.
* **Common Flags:** `--json`, `--quiet`

#### `deviate tasks post [--force] [--issue-id]`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Validates `tasks.md` exists and is non-empty, runs pre-commit hooks,
  commits, and transitions session to IDLE.

#### `deviate tasks <issue-id>` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Direct positional-argument interface. Generates a single `TaskRecord`
  with `TSK-{NNN}-{NN}` id, appends to `tasks.jsonl`, transitions through TASKS -> IDLE.

#### `deviate pr pre`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Loads session (TASKS), resolves active issue, gathers git state via
  `gather_git_state()`, derives PR metadata (title, body, base_branch), and emits JSON
  contract with branch_name and PR details.

#### `deviate pr run --body-file <path> [--merge] [--auto-merge]`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Creates a GitHub PR via `gh pr create`. If `--merge` is passed, also
  merges immediately and marks the issue as COMPLETED in `issues.jsonl`. If `--auto-merge`,
  enables auto-merge on the PR.

---

### 4. Micro Layer: TDD Sandbox (Manual Phase Commands)

All micro-layer commands follow the `pre`/`post` subcommand pattern. Every `pre` subcommand
accepts `--json` and `--quiet`. `pre` emits a JSON contract describing the environment.
`post` runs validation, ledger updates, and git commits.

#### `deviate red pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves the task context from `tasks.jsonl`, emits JSON contract with
  `task_id`, `test_command`, `lint_command`, and `spec_dir`.

#### `deviate red post`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Runs `pytest -v` on all test files. Validates the test fails explicitly
  (ASSERTION_FAILURE, not PASS or SYNTAX_ERROR). Appends RED status transition to task
  ledger, forces session to RED, commits with `test({scope}): RED phase - failing test`.

#### `deviate green pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves task context, emits JSON contract with `test_file` and
  `implementation_targets` (all `src/**/*.py` files).

#### `deviate green post`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies a RED transition exists for the active issue. Runs `pytest -v`,
  requires returncode 0. Evaluates `TamperGuard` in `GREEN_IMPLEMENTATION` context (resets
  test/spec/config file edits). Appends GREEN transition to ledger, forces session to GREEN,
  commits with `feat({scope}): GREEN phase - implementation passes tests`.

#### `deviate yellow pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Detects phase changes via `git status --porcelain`, emits JSON contract
  with `proposed_changes`, `rationale`, and `test_files`.

#### `deviate yellow post --approved | --rejected`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** If `--approved`, commits the amendments and forces session to GREEN. If
  `--rejected`, restores all changes via `git restore .` and forces session back to GREEN.

#### `deviate judge pre`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Detects phase changes, finds protected modules from `spec.md` `Module:`
  lines, checks for compliance violations, and emits JSON verdict
  (`COMPLIANCE_VIOLATION` or `COMPLIANCE_PASS`).

#### `deviate refactor pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves task context, emits JSON contract with all `src/**/*.py` files.

#### `deviate refactor post`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies a GREEN transition exists. Appends REFACTOR transition, runs
  AST-based return type mismatch check, runs pytest before/after to detect regression.
  On regression, restores via `git restore .` and halts. Commits with
  `refactor({scope}): REFACTOR phase - code cleanup`.

#### `deviate execute pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** DIRECT mode (bypasses RED/GREEN/REFACTOR). Emits completion criteria.

#### `deviate execute post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, commits DIRECT execution result.

#### `deviate e2e pre`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies ALL tasks across all ledgers are COMPLETED. If not, halts.

#### `deviate e2e post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, commits E2E verification results.

#### `deviate hotfix pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Bug fix mode - always bypasses RED phase.

#### `deviate hotfix post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, commits HOTFIX result.

---

### 5. Automated Pipeline Orchestration

#### `deviate run <task-id>`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Triggers the automated execution cycle for a single task node. Routes by
  `execution_mode` (TDD or non-TDD). TDD mode runs the RED -> GREEN -> [TamperGuard gate
  → YELLOW?] → JUDGE → REFACTOR cycle. YELLOW is a conditional branch (not a fixed phase
  in `_PHASE_MAP`) triggered only when TamperGuard detects unauthorized test edits during
  the GREEN phase. Non-TDD (DIRECT, E2E) runs `_run_execute_phase` which immediately marks
  COMPLETED.
* **Input Parameters:**
  * `<task-id>` (Positional: TSK-NNN-NN format)
  * `--profile [full|fast|secure]` (Defaults to `full`):
    * `full` — RED + GREEN + JUDGE + REFACTOR (complete cycle)
    * `fast` — RED + GREEN only (skip JUDGE + REFACTOR)
    * `secure` — RED + GREEN + JUDGE (skip REFACTOR)
    * Boolean flags `--no-judge` / `--no-refactor` retained as composable overrides
  * `--agent` (Override agent backend)
* **Common Flags:** `--json`, `--quiet`

#### `deviate run --all`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Finds all PENDING tasks and dispatches them sequentially. Each task gets
  up to 2 retry attempts before being marked FAILED. Halts on first failure. Displays a
  live-updating Rich dashboard with task markers (`[X]` completed, `[/]` in-progress,
  `[ ]` pending) and a 5-line rolling agent output buffer. Non-TTY mode emits JSONL events
  instead of dashboard.
* **Accepts:** `--profile`, `--agent`, `--json`, `--quiet`

#### `deviate meso run` (Automated Meso Pipeline)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Automates the specify→tasks pipeline. Discovers next unblocked BACKLOG
  issue (or targets `--issue ISS-NNN`), runs each phase's pre-flight checks, builds slim
  prompt templates from `src/deviate/prompts/auto/`, invokes the agent via `AgentBackend`,
  validates outputs, commits artifacts, and advances session state through SPECIFY → TASKS → IDLE.
* **Input Parameters:**
  * `--issue <id>` (Target specific issue; default: next unblocked BACKLOG)
  * `--dry-run` (Emit contracts + prompts without invoking agent or committing)
  * `--force` (Bypass pre-flight guards)
* **Error Recovery:** Upstream artifact missing at any phase boundary halts with
  `UPSTREAM_MISSING`. Agent non-zero exit aborts pipeline. Completed phases skipped
  idempotently on re-run.

#### `deviate macro run` (Automated Macro Pipeline)

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Automates the explore→research→prd→shard pipeline. Runs each phase's
  pre-flight checks, builds slim prompt templates, invokes the agent, validates outputs,
  commits artifacts, and registers shard issues. Session advances through EXPLORE → RESEARCH
  → PRD → SHARD → IDLE.
* **Input Parameters:**
  * `--target <slug>` (Target feature bucket slug)
  * `--from <phase>` (Resume from specific phase: explore|research|prd|shard)
  * `--dry-run` (Emit contracts + prompts without side effects)
  * `--force` (Bypass pre-flight guards)
* **Error Recovery:** Same as meso pipeline. Idempotent phase skip.
* **Common Flags (both meso & macro):** `--json`, `--quiet`

---

### 6. Inspection & Diagnostics

#### `deviate tasks list [--type tdd|direct|e2e] [--status <status>]` (Aspirational — CLI not yet created)

* **Source:** `src/deviate/cli/inspect.py` (planned)
* **Description:** Reads the issue-scoped `tasks.jsonl` ledger and derives current task states
  by parsing the append-only ledger sequentially. Outputs a tabular summary of current,
  completed, pending, or failed tasks. Supports `--type` and `--status` filtering.
* **Common Flags:** `--json` (outputs raw parsed ledger data), `--quiet`

#### `deviate issues list [--type feature|adhoc] [--status <status>]` (Aspirational — CLI not yet created)

* **Source:** `src/deviate/cli/inspect.py` (planned)
* **Description:** Reads and parses `specs/issues.jsonl` to derive real-time issue states.
  State is computed by scanning the ledger bottom-up: the latest entry for an `issue_id`
  defines its current status. Renders a tabular summary filtered by `type`, `feature_slug`,
  or `status`.
* **Common Flags:** `--json`, `--quiet`

---

### 7. Code Review & Quality Gates

#### `deviate review pre [--base <branch>] [--branch <branch>]`

* **Source:** `src/deviate/cli/review.py`
* **Description:** Gathers git state and governance context for code review. Computes the
  unified diff between the merge-base of `--base` (default: `main`) and `--branch` (default:
  `HEAD`), resolves the constitution path, resolves the PRD path from the branch name,
  and checks for existing review reports. Emits a JSON contract with all gathered context
  for consumption by the review skill.
* **Input Parameters:**
  * `--base <branch>` (Base branch for merge-base computation; default: `main`)
  * `--branch <branch>` (Target branch for self-contained review; default: `HEAD`)
* **Output Artifacts:** JSON contract with `diff`, `constitution_path`, `prd_path`,
  `constitution_warning`, `prd_warning`, `base_branch`, `report_exists`, `timestamp`.

#### `deviate review post [<content>]`

* **Source:** `src/deviate/cli/review.py`
* **Description:** Persists a review report markdown file and marks the review as complete.
  If no content argument is provided, reads from stdin (supports pipe-mode for programmatic
  usage). Writes the report to `.deviate/review/reports/review-report-{timestamp}.md`.
* **Input Parameters:**
  * `<content>` (Optional positional: report markdown content. If omitted, reads from stdin.)
* **Output Artifacts:** `.deviate/review/reports/review-report-{timestamp}.md`

---

### 8. (Removed — Context Sync)

The `deviate context` concept was evaluated and removed. Reasoning:
- Every phase/prompt already injects the constitution and relevant specs, making redundant
  context injection into `CLAUDE.md`/`AGENTS.md` unnecessary.
- Mutating `CLAUDE.md` mid-cycle would invalidate LLM KV caches, defeating the cache
  optimization strategy.
- The `/deviate-context` skill was deleted in commit `b7057e2`.

---

### 8. Cache Discipline Rules (Micro Layer)

During any Micro-layer TDD cycle (RED → GREEN → JUDGE → REFACTOR), the following actions are
**prohibited** to preserve KV cache hit rates across phase turns:

1. **No model switching mid-cycle.** Each model maintains its own KV cache. Switching the
   model identifier mid-cycle forces full context recomputation at cache-miss pricing.
2. **No tool definition changes.** Adding or removing tool definitions invalidates the
   cached prefix.
3. **No system prompt mutation.** Modifying the system prompt between phases breaks the
   stable prefix.
4. **No appending read-only test files as conversation turns.** Test files that do not
   change during a cycle must be loaded as prefix-stable context, not appended as
   conversation turns (which would break the cache prefix).

The `CacheDiscipline` module in `src/deviate/core/cache_discipline.py` is specified as the
enforcement mechanism but has **not yet been implemented**. Cache discipline validation
is currenty aspirational — the rules serve as guidance for agent implementers.

---

## Part 2: Document Architecture & Prompt Ownership

### 1. File Tree Blueprint

```text
.deviate/
├── config.toml               # Test parameters, target models, execution config
├── session.json              # State tracker (current_phase, active_issue_id, last_command)
├── .gitignore                # Excludes session.json from version control
└── prompts.log               # Append-only raw agent stdout log (CLI-managed)
specs/
├── constitution.md           # Absolute project invariants and architectural constraints
├── issues.jsonl              # Global append-only issue registry
├── adhoc/                    # Ad-hoc issue workspace
│   ├── prd.md                # Aggregated PRD entries (append-only)
│   └── issues/               # Adhoc-scoped issue files
│       └── {ADH-NNN}-{kebab-slug}.md
└── {FEATURE_SLUG}/           # Feature workspace bucket
    ├── explore.md            # Raw codebase context (cheap scan - what exists)
    ├── design.md             # Architectural decisions and trade-offs
    ├── data-model.md         # Entity relationships, schemas, data flow
    ├── prd.md                # Product requirement documents
    ├── spec.md               # Functional contract ("What & Why" system bounds) — deprecated, shard now embeds specs in issues
    └── issues/               # Issue sub-workspaces
        └── {ISSUE_ID}/
            ├── spec.md       # Issue-level functional specification (shard-produced, with Gherkin AC)
            ├── plan.md       # ← NEW: per-issue localized research report (deviate-plan output)
            ├── tasks.md      # Task decomposition (human-authored, what/why/how)
            └── tasks.jsonl   # Append-only task event ledger (CLI-managed)

src/deviate/
├── __init__.py
├── main.py                   # Entry point: from .cli import cli; app = cli
├── cli/
│   ├── __init__.py           # Main CLI: deviate init, typer command registration
│   ├── _common.py            # Shared helpers (_halt, _extract_epic_num, with_json_quiet)
│   ├── macro.py              # explore, research, prd, shard (pre/post), macro run
│   ├── meso.py               # specify, tasks, pr (pre/post/run), meso run
│   ├── micro.py              # red, green, yellow, judge, refactor, execute, e2e, hotfix, run
│   ├── adhoc.py              # adhoc pre/post (complexity gate, ad-hoc issues)
│   ├── feature.py            # feature create (slug, branch, directory)
│   └── inspect.py            # (planned) tasks list, issues list
├── core/
│   ├── agent.py              # AgentBackend, HandoverManifest, BACKEND_COMMANDS
│   ├── commit.py             # stage_and_commit, commit_artifact
│   ├── complexity.py         # ComplexityGate.classify() — adhoc task complexity
│   ├── constitution.py       # resolve_constitution, extract_commands, validate
│   ├── contract.py           # emit_contract, load_contract
│   ├── epic.py               # allocate_feature_bucket, discover_epic, resolve_active_feature
│   ├── issues.py             # claim_issue
│   ├── prd.py                # extract_prd_requirements
│   ├── profile.py            # ExecutionProfile (full/fast/secure), resolve_profile()
│   ├── repo.py               # find_repo_root, gather_git_state
│   ├── skills.py             # detect_agents, discover_skills, install_skill
│   ├── tamper.py             # TamperGuard, TamperContext, TamperVerdict
│   ├── validation.py         # validate_artifact, validate_gherkin, YAML frontmatter
│   ├── worktree.py           # create_worktree, remove_worktree, branch detection
│   ├── cache_discipline.py   # (planned) CacheDiscipline — 4 validation rules
│   ├── tasks_ledger.py       # (planned) generate_jsonl_from_md, validate_tasks_jsonl
│   └── _shared.py            # git_env
├── prompts/
│   ├── __init__.py
│   ├── assembly.py           # PromptAssembly — builds slim prompts from templates
│   ├── constitution_seed.md  # Template with ${VARIABLE} placeholders
│   ├── auto/                 # explore, research, prd, shard, specify, tasks, plan (planned)
│   │   ├── explore.md, research.md, prd.md, shard.md, specify.md, tasks.md
│   │   ├── red.md, green.md, yellow.md, judge.md, refactor.md
│   │   └── plan.md (planned)
│   ├── governance/           # claudemd_seed.md, agents_seed.md
│   └── skills/               # 19 DeviaTDD skill directories (18 + deviate-plan planned)
└── state/
    ├── __init__.py
    ├── config.py             # DeviateConfig, SessionState, TransitionViolationError, _MACRO_TRANSITION_MAP
    └── ledger.py             # IssueRecord, TaskRecord, append_issue_transition, append_task_transition
```

**Artifact Convention — `tasks.md` vs `tasks.jsonl`:**

- **`tasks.md`** — Human-authored decomposition document. Contains the *what/why/how*:
  task descriptions, implementation hints, file locations, mock boundaries, fixture
  requirements, DAG dependencies. Written by the agent during the `/deviate-tasks` skill
  invocation. Lives at `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.md`.
- **`tasks.jsonl`** — Machine-managed append-only event ledger. Contains only status
  transitions (`PENDING`, `RED`, `GREEN`, `REFACTOR`, `COMPLETED`, `FAILED`) and
  execution metadata. Written exclusively by the `deviate` CLI. Lives at
  `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`. Agents **cannot** write to
  this file directly — only the CLI may append events via `append_task_transition()`.

**Global Issue Ledger (`specs/issues.jsonl`):**
```json
{"issue_id": "ISS-001-001", "type": "feature", "title": "Implement JWT validation", "status": "DRAFT", "source_file": "specs/auth-jwt/explore.md", "timestamp": "2026-05-31T10:00:00Z"}
{"issue_id": "ISS-001-002", "type": "feature", "title": "Refresh token rotation", "status": "BACKLOG", "source_file": "specs/auth-jwt/issues/ISS-002-spec.md", "timestamp": "2026-05-31T10:05:00Z"}
{"issue_id": "ISS-001-001", "status": "SHARDED", "timestamp": "2026-06-01T12:00:00Z"}
{"issue_id": "ISS-001-001", "status": "COMPLETED", "timestamp": "2026-06-02T15:30:00Z"}
```

**Issue-Scoped Task Ledger (`specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`):**
```json
{"id": "TSK-001-01", "issue_id": "ISS-001-001", "description": "create_jwt_validator_class", "status": "PENDING", "execution_mode": "TDD"}
{"id": "TSK-001-01", "issue_id": "ISS-001-001", "description": "create_jwt_validator_class", "status": "RED"}
{"id": "TSK-001-01", "issue_id": "ISS-001-001", "description": "create_jwt_validator_class", "status": "GREEN"}
{"id": "TSK-001-01", "issue_id": "ISS-001-001", "description": "create_jwt_validator_class", "status": "COMPLETED"}
{"id": "TSK-001-02", "issue_id": "ISS-001-001", "description": "integration_token_flow", "status": "PENDING", "execution_mode": "E2E"}
```

---

### 2. Prompt Matrix & File Generation Lifecycle

Macroscopic commands are user-facing interactive slash commands registered as prompt skills
in agent runtime directories during `deviate init`. Skills live in `src/deviate/prompts/skills/`
and are installed to `.{agent}/skills/` per workspace.

| Client Command Trigger | Responsible Persona Role | Targets Created / Mutated | Internal CLI Endpoints | Action Logic Steps |
| --- | --- | --- | --- | --- |
| `/deviate-explore` | Context Scanner (Cheap) | `specs/{FEATURE_SLUG}/explore.md` | `deviate feature create`, `deviate explore pre/post` | 6 steps: feature create, constitution validate, bucket allocate, codebase scan, write explore.md, commit |
| `/deviate-research` | Architect (Expensive) | `specs/{FEATURE_SLUG}/design.md`, `data-model.md` | `deviate research pre/post` | 5 steps: read explore.md, analyze options, produce design.md, produce data-model.md, commit |
| `/deviate-prd` | Product Owner Proxy | `specs/{FEATURE_SLUG}/prd.md` | `deviate prd pre/post` | 4 steps: read design.md, synthesize requirements, write prd.md, commit |
| `/deviate-shard` | Decomposition Engine | `specs/{FEATURE_SLUG}/issues/{ISS-NNN}-*.md` | `deviate shard pre/post` | 5 steps: read prd.md, identify vertical slices, validate granularity, create issue stubs (with Gherkin AC, user stories, edge cases), register in ledger |
| `/deviate-adhoc` | Condensed Scoper | `specs/adhoc/` | `deviate adhoc pre/post` | 8 steps: complexity gate, codebase scan, PRD append, issue generation (spec-enriched with Gherkin), ledger registration, commit |
| **[HITL GATE 2]** | Human Reviewer | --- | --- | Review all sharded issues for completeness and edge cases before `/deviate-plan` proceeds |
| `/deviate-plan` **← NEW** | Localized Researcher | `specs/{FEATURE_SLUG}/issues/{ISS-NNN}/plan.md` | `deviate plan pre/post` (planned) | 4 steps: read spec-enriched issue, scan current codebase, analyze prior issues, produce plan.md with implementation strategy |
| `/deviate-tasks` | Technical Lead | `specs/{FEATURE_SLUG}/issues/{ISS-NNN}/tasks.md` | `deviate tasks pre/post` | 6 steps: consume spec-enriched issue + plan.md, decompose into tasks, assign execution modes, encode DAG deps, append terminal E2E task, validate granularity + commit |
| `/deviate-pr` | Release Engineer | GitHub PR | `deviate pr pre/run` | 3 steps: gather git state, derive PR metadata, create PR via `gh pr create` |

> **Deprecation Notice:** `/deviate-specify` is deprecated as a standalone step. Shard
> now produces issues with full spec-level detail (Gherkin AC, user stories, edge cases).
> The `/deviate-specify` skill remains for backward compatibility but redirects to the
> new workflow. This is part of the Meso-Layer Restructuring (ADHOC-003).

**Session Continuity Strategy:**
- **Macro layer** (explore -> research -> prd -> shard+specify): Sequential CLI invocations,
  each persisting session to `.deviate/session.json`. Phase transitions validated by
  `SessionState`. Shard now produces spec-enriched issue files (no separate specify step).
- **Meso layer** (`/deviate-plan` -> `/deviate-tasks`): Single continuous LLM session per issue.
  The system prompt, tool definitions, issue content, and `constitution.md` form a stable
  prefix cached after turn 1.
- **Micro layer** (RED -> GREEN -> [YELLOW?] -> JUDGE -> REFACTOR): Task execution reuses
  the same in-process state via `force_transition_to()`. The `deviate run <task-id>` command
  dispatches through the full cycle programmatically. YELLOW is a conditional branch in the
  cycle body between GREEN and JUDGE, not a `_PHASE_MAP` entry.

---

### 3. Issue & Task Status Models

#### IssueRecord (Pydantic -- `src/deviate/state/ledger.py`)

| Field | Type | Description |
|-------|------|-------------|
| `issue_id` | `str` | Unique ID (`ISS-NNN`) |
| `type` | `str` | Issue type (`feature`, `adhoc`, etc.) |
| `title` | `str` | Human-readable title |
| `status` | Literal | `DRAFT`, `BACKLOG`, `SPECIFIED`, `SHARDED`, `COMPLETED` |
| `source_file` | `str` | Path to the issue's source file |
| `blocked_by` | `list[str]` | DAG dependency issue IDs |
| `coordinates_with` | `list[str]` | Related issue IDs |
| `timestamp` | `datetime` | When the record was created |
| `created_at` | `datetime` | When the issue was first created |

#### TaskRecord (Pydantic -- `src/deviate/state/ledger.py`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique ID (`TSK-NNN-NN` format, validated via regex) |
| `issue_id` | `str` | Parent issue ID |
| `description` | `str` | Task description |
| `status` | Literal | `PENDING`, `RED`, `GREEN`, `JUDGE`, `REFACTOR`, `COMPLETED`, `FAILED` |
| `execution_mode` | Literal | `TDD`, `DIRECT`, `E2E` |
| `created_at` | `datetime` | When the task was created |

> **Note:** `JUDGE` is a first-class status in `TaskRecord.status`. `YELLOW` is a
> conditional branch phase that does not map to a `TaskRecord.status` literal — it exists
> only as a session phase and is gated by the TamperGuard in the TDD cycle body. The
> `_SKILL_NAMES` dict maps `"YELLOW"` to `"deviate-yellow"` and `"JUDGE"` to
> `"deviate-judge"` for agent skill resolution.

#### Append-Only Ledger Protocol

All state transitions are append-only. No existing line is ever modified or overwritten.
- `append_issue_transition()`: Idempotent on `(issue_id, status)` compound key
- `append_task_transition()`: Idempotent on `(id, status)` compound key
- `_append_record()` / `_append_with_compound_key()`: Use `fcntl.flock` for file-level
  locking on platforms that support it
- Canonical state: Issues derived bottom-up (latest entry per `issue_id`); tasks derived
  sequentially (latest entry per `(id, status)` compound key)

---

### 4. Model Routing & Cache Strategy (Guidance, Not Enforced)

The architecture defines a model routing strategy in `specs/constitution.md` seeds, but the
`deviate` CLI does **not** enforce model selection programmatically. The `--agent` flag on
`deviate run` is optional and agent backends are configured via `DeviateConfig.agent.backend`.

| Phase | Recommended Model | Session | Cache Strategy |
|---|---|---|---|---|---|
| RED | V4 Flash (or V4 Pro for complex) | Same task session | Stable prefix: system prompt + test files + repo map |
| GREEN | V4 Flash | Same task session | Cache hit on prefix from RED turn (~98% discount) |
| YELLOW | V4 Pro | Isolated session | No cache sharing — compliance requires fresh context |
| JUDGE | V4 Pro | Isolated session | No cache sharing — breaks recursive subjectivity |
| REFACTOR | V4 Flash | Same task session | Cache hit on prefix from GREEN turn |
| `/deviate-explore` | V4 Flash | Single invocation | One-shot |
| `/deviate-research` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-prd` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-shard` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-plan` (new) | V4 Pro | Single invocation | One-shot — fresh localized research per issue |
| `/deviate-tasks` | V4 Pro | Single invocation (issue-scoped) | 90%+ cache hit after turn 1 when paired with `/deviate-plan` |
| `/deviate-adhoc` | V4 Flash | Single invocation | One-shot |
| EXECUTE / E2E / HOTFIX | V4 Flash | Single invocation | One-shot |

The `AgentBackend` class (`src/deviate/core/agent.py`) supports `opencode`, `claude`, and
`droid` backends with configurable timeout. Output is parsed as YAML `HandoverManifest`.

### 5. DeepSeek V4 Pricing Reference (June 2026)

Cache-hit tokens are billed when a request's prefix matches a previously cached prefix.
The architecture optimizes for cache-hit pricing wherever feasible.

| Model | Cache-Hit Input (1M tokens) | Cache-Miss Input (1M tokens) | Output (1M tokens) | Cache Discount |
|---|---|---|---|---|
| V4 Flash | $0.0028 | $0.14 | $0.28 | 98.0% |
| V4 Pro (discounted) | $0.003625 | $0.435 | $0.87 | 99.17% |

Context length: 1M tokens. See `api-docs.deepseek.com/quick_start/pricing` for current rates.
~85% of all recommended LLM turns target V4 Flash at cache-hit rates.
