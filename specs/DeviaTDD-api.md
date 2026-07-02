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

#### `deviate init` and `deviate setup`

* **Sources:** `src/deviate/cli/init.py` (Typer sub-group) and `src/deviate/cli/__init__.py`
  (flat `deviate setup` command, defined at `cli/__init__.py:555-627`). Both entry points
  are equivalent in behavior — `deviate setup` is the legacy flat alias and `deviate init`
  is the Typer sub-group registered via `cli.add_typer(init_app, name="init")` at
  `cli/__init__.py:669`.
* **Description:** Initializes a standard project-level DeviaTDD compliance framework. Builds
  the `.deviate/` directory (containing `config.toml`, `session.json`, `.gitignore`, and an
  empty `artifacts/` workspace), detects the project type (`python`, `node`, `rust`, `go`,
  `elixir_phoenix`, or `unknown`) and writes a `specs/constitution.md` populated with
  project-specific test/lint/format/setup/dev commands, applies the `## DeviaTDD
  Orchestration Rules` and `## Libref Usage` governance blocks to `CLAUDE.md` and
  and installs the DeviaTDD prompt commands (currently
  24 flat `.md` files: 24 `deviate-*`) into **all five** supported agent
  directories — `.claude/commands/`, `.opencode/commands/`,
  `.factory/commands/`, `.pi/prompts/`, `.omp/prompts/` — in a single invocation, regardless of which agent was passed
  via `--agent`. Each command is a flat `<name>.md` file with a minimal YAML
  frontmatter (`name:` + `description:`). The agent backend selected via `--agent`
  (`opencode`, `claude`, `droid`, `factory`, `pi`, `omp`) is persisted to `[agent].backend` in
  `config.toml` for use by the meso/micro layers; it does **not** gate which agent
  directories receive commands.
  **Agent-to-commands-directory mapping:** `.claude/` → `.claude/commands/`;
  `.opencode/` → `.opencode/commands/`; `.factory/` (shared by both `--agent
  factory` and `--agent droid` — the Factory Droid IDE owns that directory;
  `droid` is the underlying backend binary both user-facing names dispatch to,
  so there is no `.droid/commands/`) → `.factory/commands/`; `.pi/` →
  `.pi/prompts/` (Pi discovers slash commands from `<workdir>/.pi/prompts/*.md`
  per the platform's documented convention; DeviaTDD file-copies the project
  command vault `src/deviate/prompts/commands/<name>.md` into
  `<workdir>/.pi/prompts/<name>.md`, so the project vault remains the single
  source of truth. DeviaTDD does **not** write to `~/.pi/agent/` and does **not**
  generate a `settings.json` — model/provider selection is the operator's
  responsibility via Pi's own configuration mechanism); `.omp/` →
  `.omp/prompts/` (OMP is an extensible wrapper around the Pi executor; it
  discovers slash commands from `.omp/prompts/`). All five command
  directories are excluded from version control via the project-root
  `.gitignore` (see `_ensure_root_gitignore` at `src/deviate/cli/__init__.py:653`).
  Additionally, both `deviate setup` and `deviate init pre` provision a project-root
  `.gitattributes` declaring `merge=union` for `specs/issues.jsonl` and
  `specs/**/tasks.jsonl` (see `_ensure_root_gitattributes` at
  `src/deviate/cli/__init__.py:675` and the `DEVIATE_GITATTRIBUTES_SEED`
  constant). This implements the cross-branch merge strategy declared in
  `specs/constitution.md` §1 Append-Only Ledger Protocol — concurrent
  appends to the append-only JSONL ledgers on parallel feature branches
  merge without conflict markers; the union driver keeps every unique
  line across all sides. Behaviour: idempotent (re-running setup never
  duplicates rules), preserves user-authored `.gitattributes` content,
  and stages the file via `deviate init post` alongside the other
  scaffolded artifacts.
* **Agent Selection:** Accepts `--agent [claude|opencode|droid|factory|pi]` to override
  auto-detect. If omitted, the persisted value is reused; if no persisted value exists and
  the session is interactive, a Rich `Prompt.ask` menu is shown. In non-interactive mode
  the command halts with `NO_AGENT_SELECTED` and a directive to re-run with `--agent`.
* **Execution Modes:**
  * **Offline Mode (Default):** `_scaffold_constitution()` writes
    `src/deviate/prompts/constitution_seed.md` verbatim to `specs/constitution.md`. The
    seed contains `TBD` placeholders rather than runtime-resolved `${VARIABLE}` tokens;
    `TBD` fields are populated later by `/deviate-research` (which writes `design.md` and
    `data-model.md`) and by the LLM-driven `constitution` command. The offline path
    completes in well under 50ms.
  * **Onboard Prompt Mode (Aspirational):** `deviate constitution generate` is the
    dedicated command for LLM-driven constitution tailoring. The legacy
    `--generate-constitution` flag on init is not wired in the current implementation.
    When invoked, `deviate constitution generate` resolves the agent backend from
    `.deviate/config.toml` (or the `LLMBACKEND` environment variable, defaulting to
    `droid`) and dispatches the constitution-generation prompt.
* **Tokenized Placeholder Resolution:** Constitution placeholders in the current
  implementation are static `TBD` tokens, not runtime-resolved variables. The
  `${VARIABLE}` resolver described in earlier revisions of this spec has been removed.
* **Input Parameters:**
  * `--agent-export-mode [local|global]` (Defaults to `local`)
  * `--agent [claude|opencode|droid|factory|pi]` (Override auto-detect)
  * `--graphite` (Enable Graphite CLI integration; merges `graphite = true` into
    existing `config.toml` and installs the Graphite governance block)
  * `--libref` (Force-enable `libref` CLI integration; merges `use_libref = true` into
    `config.toml`)
* **Output Artifacts:**
  * `.deviate/config.toml` — Persisted configuration profile (includes
    `[agent].backend` set from `--agent` for meso/micro dispatch)
  * `.deviate/session.json` — Current session state snapshot
  * `.deviate/.gitignore` — Excludes session.json and runtime state
    directories from version control
  * `<workdir>/.gitignore` — Updated with four concise DeviaTDD
    agent-command exclusions: `*/commands/deviate-*.md`,
    `*/prompts/deviate-*.md` (covers every supported agent directory
    — ``.claude/commands/``, ``.opencode/commands/``,
    ``.factory/commands/``, ``.pi/prompts/`` — and any future agent
    that follows the same flat-file convention). The single-level
    ``*/`` prefix is deliberate: a broader ``**/deviate-*.md`` would
    silently ignore the deviatdd project's own command sources at
    ``src/deviate/prompts/commands/deviate-*.md`` (three directories
    deep) and break ``deviate setup`` in this repo itself.
  * `specs/constitution.md` — Resolved boilerplate constitution
  * `.claude/commands/`, `.opencode/commands/`, `.factory/commands/`,
    `.pi/prompts/` — DeviaTDD prompt commands installed for every
    supported agent (24 flat `.md` files total, split across the four
    dirs)

#### `deviate constitution`

* **Source:** `src/deviate/cli/constitution.py`
* **Description:** Three sub-commands for managing `specs/constitution.md`:
  * **`deviate constitution generate` (`--force`):** Writes
    `src/deviate/prompts/constitution_seed.md` verbatim to `specs/constitution.md`.
    Idempotent: skips if the file already exists unless `--force` is passed. Replaces
    the aspirational `deviate init --generate-constitution` flag — the LLM-driven
    constitution tailoring is dispatched through `deviate constitution generate` once
    the LLM runner is wired.
  * **`deviate constitution pre`:** Validates that `specs/constitution.md` exists,
    passes `validate_constitution()`, and contains the required `## TESTING_PROTOCOLS`
    section. Emits a JSON `{"status": "FAILURE", "reason": ...}` envelope on any
    failure. No side effects on success — outputs a contract that the agent consumes.
  * **`deviate constitution post <manifest>`:** Reads a manifest JSON containing a
    `sections` array and an optional `constitution_path` (default
    `specs/constitution.md`), validates that each named section is present via
    `validate_sections()`, then commits the constitution file via `commit_artifact()`
    with the message `Update constitution`. Emits `{"status": "SUCCESS"}` on success.
* **Common Flags:** None (each sub-command exposes its own options).

### 1.5 Product Layer *(optional, sits above Macro)*

The Product layer ships as **agent skills** (no dedicated CLI subcommands) — the prompts live at `src/deviate/prompts/commands/deviate-{flows,architecture,release}.md` and are installed to all four agent directories alongside the rest. They are **not** wired into the `deviate` CLI's `pre`/`post` subcommand pattern: the agent invokes them directly as `/deviate-flows`, `/deviate-architecture`, `/deviate-release`, and the conversation produces the artifact. The CLI's only involvement is installing the skill files during `deviate setup` and (via `deviate-shard` / `deviate-adhoc`) consuming the `flow_refs:` frontmatter those artifacts emit.

| Command | Source skill | Artifact committed | Notes |
|---------|--------------|--------------------|-------|
| `/deviate-flows` | `src/deviate/prompts/commands/deviate-flows.md` (FLOW-01) | `specs/_product/flows/flows-<domain>.md` + updated `specs/_product/flows/index.md` | Conversational; the agent must surface clarifying questions when actor, job-to-be-done, or trigger is ambiguous. FLOW-NN IDs use `^FLOW-\d{2,}$`. |
| `/deviate-architecture` | `src/deviate/prompts/commands/deviate-architecture.md` (FLOW-02) | `specs/_product/architecture.md` + `specs/_product/domain-model.md` | **Precondition:** at least one flow file under `specs/_product/flows/` must exist; otherwise the skill must surface `[red]FLOWS_MISSING[/]` and recommend `/deviate-flows` first. |
| `/deviate-release` | `src/deviate/prompts/commands/deviate-release.md` (FLOW-03) | `specs/_product/release-next.md` (overrides previous) | **Precondition:** both `specs/_product/architecture.md` and at least one flow file must exist; otherwise `[red]ARCH_OR_FLOWS_MISSING[/]`. The release goal (free-text user input) drives the Included Flows / Included Work / Acceptance tables. |

**Downstream consumption:** `deviate-shard` and `deviate-adhoc` SKILL.md bodies read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, and `specs/_product/domain-model.md` as authoritative context. Each sharded or adhoc issue emits a `flow_refs: [FLOW-XX, ...]` field in its YAML frontmatter and in the `IssueRecord.flow_refs` ledger entry (validated against `^FLOW-\d{2,}$`), so vertical slices stay traceable back to the flow that motivated them. `deviate adhoc pre` accepts a `--flow-ref FLOW-01,FLOW-02` CLI override to set the flow refs explicitly when the agent's natural-language inference is ambiguous.

#### `/deviate-shard` (Macro Layer)

* **Objective:** Decomposes the PRD into standalone, testable issue files.
* **Granularity Guidelines:**
  * **Target:** 4-8 issues per feature shard
  * **Each issue must be a vertical slice:** Delivers a complete, testable behavior end-to-end
  * **Independence:** Each issue should be independently implementable and testable
  * **Scope bounds:** No issue should require <1 task or >10 tasks
  * **Testability:** Each issue must have clear acceptance criteria

---

### 2. Macro Layer: Feature Scoping (pre/post)

All macro-layer commands follow the `pre`/`post` subcommand pattern (except `init`).
Every `pre` subcommand accepts `--json` (emit JSON contract to stdout) and `--quiet`
(suppress diagnostic output).

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

* **Source:** `src/deviate/cli/adhoc.py`
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

#### `deviate plan pre [--issue <id>] [--dry-run]`

* **Source:** `src/deviate/cli/meso.py` (`_plan_pre`)
* **Description:** Per-issue localized research phase. Two operating modes:
  * **Outside a linked worktree (auto-claim):** When `_is_linked_worktree()` returns
    `False`, the command auto-discovers the next claimable unblocked BACKLOG issue (or
    uses the provided `--issue`), calls `_specify_pre` to create the worktree and claim
    the issue, force-transitions the session to `PLAN`, and copies `.deviate/` into the
    new worktree. Exits 0 once the worktree is ready.
  * **Inside a linked worktree (contract mode):** Loads the session (accepts `SPECIFY` or
    `PLAN` phases), resolves the spec-enriched issue file by reading
    `record.source_file` from the ledger, parses workstation file paths from the issue's
    `## System Topology Mapping` section, and calls `extract_file_structure()` on each
    existing workstation file (via `deviate/core/treesitter.py`). Emits a JSON contract
    containing `issue_id`, `spec_path`, `plan_target`, `worktree_full`, `branch_name`,
    constitution paths, and the optional `file_structure` appendix.
* **Input Parameters:** `--issue <id>` (override auto-discovered), `--force`,
  `--dry-run` (emits the contract with `dry_run: true` but does not skip side effects)
* **Session:** Force-transitions to `PLAN` with `active_issue_id` set.
* **Common Flags:** `--json`, `--quiet`

#### `deviate plan post [--force] [--issue-id]`

* **Source:** `src/deviate/cli/meso.py` (`_plan_post`)
* **Description:** Resolves the active issue from the session (or `--issue-id` override),
  reads `specs/{epic}/{issue}/plan.md`, validates that the file exists and is non-empty
  (unless `--force`), commits via `commit_artifact()` with the message
  `docs({epic}-{issue}): create plan.md`, and `transition_to("TASKS")`. Skips the commit
  silently when there are no changes to stage.

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
  requires returncode 0. Appends GREEN transition to ledger, forces session to GREEN,
  commits with `feat({scope}): GREEN phase - implementation passes tests`.

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
* **Description:** DIRECT execution mode for `direct`/`immediate`-typed tasks — boilerplate, config, asset syncs, trivial fixes, or refactors with existing test coverage. Bypasses the RED phase entirely. Emits JSON contract with completion criteria; the agent runs once and the result is committed.

#### `deviate execute post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, then runs `_run_execute_phase()` which invokes the EXECUTE agent and follows with a JUDGE pass against `spec.md`. On `COMPLIANCE_VIOLATION`, `_execute_rollback()` resets the implementation and the phase is retried with `<train_feedback>` injected (up to `max_judge_attempts = 3`). The EXECUTE → JUDGE → EXECUTE iteration mirrors the Green → Judge → Green loop in shape but skips the RED boundary: the EXECUTE phase is allowed to start from any clean working tree and the JUDGE pass evaluates the diff post-hoc. Exhaustion raises `PhaseFailedError`. The task is marked `COMPLETED` only on `COMPLIANCE_PASS`; the result is committed with the manifest's `commit_message` (or a default `chore({scope}): execute`).

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

* **Source:** `src/deviate/cli/micro.py` (`_run_single`, `_dispatch_task`)
* **Description:** Triggers the automated execution cycle for a single task node. Routes by
  `execution_mode` (TDD or non-TDD). TDD mode runs the RED -> GREEN -> JUDGE -> REFACTOR
  cycle. Non-TDD (`DIRECT` or `E2E`) runs `_run_execute_phase`, which
  commits the work, then optionally runs a JUDGE pass against `spec.md` and rolls back
  on `COMPLIANCE_VIOLATION` (up to `max_judge_attempts = 3`).
* **Green → Judge → Green loop (TDD only):** `_run_tdd_cycle` wraps the GREEN→JUDGE pair in a `while not judge_passed` loop with up to `max_train_attempts = 3`. On test failure or `COMPLIANCE_VIOLATION`, `_execute_rollback()` runs `git reset --hard <red_sha>` against the RED-boundary SHA stored in `session.red_commit_sha` (captured at the end of the RED phase), the session is `force_transition_to("GREEN")`, and the previous attempt's feedback is injected as `<train_feedback>` into the next GREEN prompt via `_build_auto_prompt("green", ...) + "\n\n<train_feedback>\n{...}\n</train_feedback>\n"`. The cycle retries from GREEN. After 3 attempts the task is marked `FAILED` and the pipeline halts with `PhaseFailedError`. The feedback source precedence is `train_feedback` (preferred) → `violations` (structured list) → `rationale` → `summary` → fallback string.
* **Resume from Mid-Phase:** If `session.current_phase` is `JUDGE` or
  `REFACTOR` when invoked, the cycle resumes from that phase via the `start_phase`
  parameter. IDLE / RED trigger a fresh cycle from RED.
* **Input Parameters:**
  * `<task-id>` (Positional: `TSK-NNN-NN` format; omit to auto-select the first PENDING
    task for the active issue)
  * `--profile [full|fast|secure]` (Defaults to `full`):
    * `full` — RED + GREEN + JUDGE + REFACTOR (complete cycle)
    * `fast` — RED + GREEN only (skip JUDGE + REFACTOR)
    * `secure` — RED + GREEN + JUDGE (skip REFACTOR)
    * Boolean flags `--no-judge` / `--no-refactor` retained as composable overrides
  * `--agent` (Override agent backend; falls back to `[agent].backend` in
    `.deviate/config.toml`)
  * `--dry-run` (Print the resolved task and exit without dispatching)
* **Common Flags:** `--json`, `--quiet`

#### `deviate run --all`

* **Source:** `src/deviate/cli/micro.py` (`_run_all`)
* **Description:** **Issue-scoped** task sweep. Resolves the active issue from
  `session.active_issue_id` (falling back to branch-derived detection via the
  `feat/{epic}/{issue}` regex against `specs/issues.jsonl`), then dispatches **every
  PENDING task for that issue** sequentially. Each task gets up to **2 retry attempts**
  (`_execute_task_with_retry`, `for attempt in range(2)`) before being marked `FAILED` in
  the issue-scoped `tasks.jsonl`. The pipeline **halts on the first failure**
  (`any_failed = True; break`) and exits with code `1`. If no `active_issue_id` is set
  and the branch cannot resolve an issue, no tasks are dispatched.
* **Train Retry Loop (per task):** Inside each task's TDD cycle, `_run_tdd_cycle` allows
  up to **3 train attempts** (`max_train_attempts = 3`) when GREEN tests fail or JUDGE
  returns `COMPLIANCE_VIOLATION`. Each train attempt injects `<train_feedback>` from
  the previous attempt's failure output back into the GREEN prompt and re-runs GREEN.
  Exhaustion raises `PhaseFailedError`.
* **Graphite Integration:** If `.deviate/config.toml` contains `graphite = true`, after
  each successful task the runner invokes `gt create -m "feat({TSK}): {description}"`
  to spin up a stacked branch for the next task.
* **Dashboard / Output:** Constructs an `OrchestrationMonitor` with `total_tasks` set to
  the pending count. The monitor emits live Rich dashboard events (task markers, phase
  transitions) in TTY mode and JSONL events (`task_started`, `phase_change`,
  `task_completed`, `task_failed`, `pipeline_halted`, `pipeline_complete`) when
  `--json` is passed. Agent output is forwarded to the monitor via a streaming callback.
* **Accepts:** `--profile [full|fast|secure]`, `--agent <name>`, `--json`, `--quiet`,
  `--dry-run` (prints all resolved pending tasks and exits without dispatching).

#### `deviate meso run` (Automated Meso Pipeline)

* **Source:** `src/deviate/cli/meso.py` (`_meso_run`, `meso_run_command`)
* **Description:** Automates the per-issue meso pipeline: SPECIFY (claim) → PLAN → TASKS → IDLE.
  When invoked without `--issue`, calls `_discover_claimable_issue()` to find the next
  unblocked BACKLOG issue whose branch is **not** already on the remote (claimed-elsewhere
  skip). When invoked with `--issue`, validates the issue, resets it to BACKLOG if it is in
  any later state, and fails if `blocked_by` dependencies are not COMPLETED (unless `--force`).
* **Pipeline Steps (in order):**
  1. **Claim (SPECIFY):** Calls `_specify_pre(issue_id, force, dry_run)`, which creates a
     linked worktree at `.worktrees/feat/{epic}/{issue}/`, runs `mise trust && mise install
     && mise run setup`, copies `.claude/`, `.opencode/`, `.factory/` agent skill directories
     into the worktree, claims the issue via `claim_issue()`, commits the claim to the
     worktree's `specs/issues.jsonl`, and pushes the branch to origin.
  2. **Plan:** `chdir`s into the worktree, calls `_plan_pre()` (emits a `plan_pre` JSON
     contract), invokes the agent with the slim `plan` prompt and the per-phase model from
     `.deviate/config.toml` via `resolve_model_for_phase("plan", root)`, then calls
     `_plan_post()` to validate that `plan.md` is non-empty, commit it as
     `docs({epic}-{issue}): create plan.md`, and `transition_to("TASKS")`.
  3. **Tasks:** Calls `_tasks_pre()` (emits a `tasks_pre` JSON contract), invokes the agent
     with the slim `tasks` prompt (with the plan content appended to the contract), then
     calls `_tasks_post()` to validate `tasks.md`, commit it as
     `docs({epic}-{issue}): create tasks.md`, and `transition_to("IDLE")`.
* **Side Effects:** `.deviate/session.json` is copied from the parent repo into the worktree
  after claim so downstream phase functions find the session. The session is force-transitioned
  to `PLAN` (then `TASKS`, then `IDLE`) — the Meso pipeline uses `force_transition_to()`,
  bypassing `_MACRO_TRANSITION_MAP` validation.
* **Input Parameters:**
  * `--issue <id>` (Target a specific issue; default: next claimable unblocked BACKLOG)
  * `--dry-run` (Emit only the `tasks` slim prompt; no claim, no worktree, no agent call,
    no commits, no session transitions)
  * `--force` (Bypass `blocked_by` dependency check)
  * `--quiet/--verbose` (Default: `--quiet`)
* **Error Recovery:** Agent non-zero exit (`AgentSubprocessError`) or `manifest.status != "PASS"`
  aborts with `<PHASE>_FAILED`. Re-running the pipeline re-processes plan.md and tasks.md
  (no phase-skip logic); commits are skipped when there are no changes. The
  `UPSTREAM_MISSING` token is **not** emitted by the current implementation.

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

#### `deviate tasks list [--status <status>]`

* **Source:** `src/deviate/cli/inspect.py` (`tasks_list_command`)
* **Description:** Reads the root-level `tasks.jsonl` ledger and derives current task
  states by parsing the append-only ledger sequentially via `filter_tasks()` and
  `LedgerFilter` (`deviate/state/ledger.py`). Outputs a Rich `Table` summary of tasks
  (ID, Issue ID, Description, Status, Mode) filtered by `--status`. The `--json` flag
  emits a JSON array; `--quiet` suppresses output.
* **Common Flags:** `--json`, `--quiet`
* **Note:** This command reads from `tasks.jsonl` at the project root, not from
  issue-scoped ledgers. The issue-scoped task ledger query surface is intentionally
  minimal — task work is normally dispatched via `deviate run` and `deviate run --all`.

#### `deviate issues list [--type <type>] [--status <status>]`

* **Source:** `src/deviate/cli/inspect.py` (`issues_list_command`)
* **Description:** Reads and parses `specs/issues.jsonl` to derive real-time issue states.
  State is computed by deduplicating records (latest entry per `issue_id` wins) via
  `_deduplicate_issues()`. For each `SPECIFIED` issue, also calls
  `_check_orphan_claim()` to query the remote for the deterministic branch
  `feat/{epic}/{issue}` — if the branch does not exist remotely, the issue is flagged
  `ORPHAN_CLAIM` in the output table (indicating the claim was lost or never pushed).
  Renders a Rich `Table` (ID, Type, Title, Status, Orphan) with optional filtering by
  `--type` and `--status`. The `--json` flag emits the parsed record array.
* **Common Flags:** `--json`, `--quiet`

---

### 7. Code Review & Quality Gates

#### `deviate review pre [--base <branch>] [--branch <branch>]`

* **Source:** `src/deviate/cli/review.py`
* **Description:** Gathers git state and governance context for a lightweight PR/merge
  review at HITL Gate 3. Computes the unified diff between the merge-base of `--base`
  (default: `main`) and `--branch` (default: `HEAD`), resolves the constitution path,
  resolves the PRD path from the branch name, and checks for existing review reports.
  Emits a JSON contract for consumption by the review skill (V4 Flash, single-pass).
  No report file is persisted — findings are surfaced in chat for human judgment.
* **Input Parameters:**
  * `--base <branch>` (Base branch for merge-base computation; default: `main`)
  * `--branch <branch>` (Target branch for self-contained review; default: `HEAD`)
* **Output Artifacts:** JSON contract with `diff`, `constitution_path`, `prd_path`,
  `constitution_warning`, `prd_warning`, `base_branch`, `report_exists`, `timestamp`.

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
│   ├── micro.py              # red, green, judge, refactor, execute, e2e, hotfix, run
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
│   │   ├── red.md, green.md, judge.md, refactor.md
│   │   └── plan.md (planned)
│   ├── governance/           # claudemd_seed.md, agents_seed.md
│   └── commands/             # 23 DeviaTDD slash commands (flat *.md): deviate-{adhoc, architecture, constitution, e2e, execute, explore, flows, green, hotfix, init, judge, plan, pr, prd, prune, red, refactor, release, research, review, shard, tasks, triage} (23)
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

Macroscopic commands are user-facing interactive slash commands registered as prompt files
in agent runtime directories during `deviate setup`. Commands live in `src/deviate/prompts/commands/`
and are installed to `.{agent}/commands/<name>.md` per workspace (or `.pi/prompts/<name>.md` for Pi).

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
- **Micro layer** (RED -> GREEN -> JUDGE -> REFACTOR): Task execution reuses
  the same in-process state via `force_transition_to()`. The `deviate run <task-id>` command
  dispatches through the full cycle programmatically.

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
| `flow_refs` | `list[str]` | Product-layer FLOW-NN IDs this issue implements (e.g. `["FLOW-01", "FLOW-04"]`). Defaults to `[]`. Populated by `deviate-shard` and `deviate-adhoc` from `specs/_product/flows/` so vertical slices stay traceable back to the Product-layer flows that motivated them. Validated against `^FLOW-\d{2,}$` on `--flow-ref` CLI overrides. |
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

The `AgentBackend` class (`src/deviate/core/agent.py`) supports `opencode`, `claude`,
`droid`, and `pi` backends with configurable timeout. Output is parsed as YAML
`HandoverManifest`. Pi uses print mode (`pi -p`) by default and accepts the
`--model <id>` CLI flag (the `provider/model` string from `[models]` is passed
verbatim). RPC mode (`pi --mode rpc --no-session`) is opt-in via `agent.pi_rpc = true` in
`.deviate/config.toml` and streams JSONL events so `pi.session_stats`
(`tokens.input`/`output`/`cacheRead`/`cacheWrite`) can be appended to the
`AGENT_RESULT` event in `.deviate/prompts.log` for cost observability. See
DeviaTDD-architecture.md §10 for the full Pi customization contract.

### 5. DeepSeek V4 Pricing Reference (June 2026)

Cache-hit tokens are billed when a request's prefix matches a previously cached prefix.
The architecture optimizes for cache-hit pricing wherever feasible.

| Model | Cache-Hit Input (1M tokens) | Cache-Miss Input (1M tokens) | Output (1M tokens) | Cache Discount |
|---|---|---|---|---|
| V4 Flash | $0.0028 | $0.14 | $0.28 | 98.0% |
| V4 Pro (discounted) | $0.003625 | $0.435 | $0.87 | 99.17% |

Context length: 1M tokens. See `api-docs.deepseek.com/quick_start/pricing` for current rates.
~85% of all recommended LLM turns target V4 Flash at cache-hit rates.
