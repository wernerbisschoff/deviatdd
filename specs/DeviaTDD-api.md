# DeviaTDD Framework Migration & Endpoint Architecture Blueprint

This document details the transition from legacy Spec-Driven Development (SDD) scripts and `.rgr/` directory structures to a unified python CLI binary called `deviate`. This architecture abstracts system shell utilities into programmatically enforced CLI commands, introduces a deterministic prefix-invariant document hierarchy within `.deviate/`, and explicitly charts prompt ownership throughout the macroscopic development lifecycle.

---

## Part 1: Unified CLI Endpoints (`deviate`)

The `deviate` command-line application decouples the execution environments (Claude Code, Factory Droid) from raw machine scripts. It consolidates runtime context gathering, structural static analysis, configuration discovery, task state mutations, and the micro-sandbox test loop into an atomic, platform-agnostic engine.

### 1. Environment & Context Discovery Primitives

#### `deviate context`

* **Legacy Mapping:** `get-spec-context.sh`
* **Scope:** Bootstrap phase — implemented
* **Description:** Performs an ascending directory crawl starting at the active working directory to find a root `.deviate/config.toml` file. It automatically discovers the current working git branch name, parses it to derive the active feature slug, computes absolute paths to files, and formats all discovered environment data into structured key-value maps.
* **Input Parameters:**
  * `--json` (Optional flag: outputs raw serialized data for direct machine injection)
  * `--quiet` (Optional flag: silences verbose diagnostic output stream)
* **Execution Steps** (all local, zero network):
  1. Directory escalation: walk up from CWD until `.deviate/config.toml` is found
  2. Feature slug resolution: invoke `git branch --show-current`, map to `specs/{FEATURE_SLUG}/`
  3. In-memory file aggregation: read `specs/{FEATURE_SLUG}/design.md` and `specs/constitution.md`
  4. Merge rules: iterate required keys (`[Language]`, `[Dependencies]`, `[Testing]`, `[Runtime]`); prioritize design.md; fill blanks from constitution.md
  5. Regex block replacement: find `## Technical Execution Context` block in `CLAUDE.md`, replace with compiled context
  6. Symlink enforcement: remove existing `AGENTS.md`, symlink to `CLAUDE.md`
  7. Git auto-stage: `git add -A && git commit --no-verify -m "docs({NNN}): sync agent context"`
* **Output Example (`--json`):**
```json
{
  "project_root": "/workspace/project",
  "git_branch": "feature/auth-jwt-refresh",
  "feature_slug": "auth-jwt-refresh",
  "specs_directory": "/workspace/project/specs/features/auth-jwt-refresh",
  "issues_ledger": "/workspace/project/specs/issues.jsonl",
  "constitution_path": "/workspace/project/specs/constitution.md"
}

```



#### `deviate ast parse <path>`

* **Legacy Mapping:** `sdd-parse-ast.sh`
* **Description:** Reads source code files or directory trees down a targeted file path and generates a non-evaluated, compile-safe interface representation. It extracts public modules, package imports, declared classes, public/private methods, variable signatures, and type annotations. This provides structural bounds verification without executing foreign code blocks.
* **Input Parameters:**
* `<path>` (Required target positional argument)
* `--format [json|markdown]` (Defaults to json)



#### `deviate test-config`

* **Legacy Mapping:** `get-test-config.sh`
* **Description:** Queries the current project `.deviate/config.toml` file to resolve operational defaults for the local ecosystem runtime execution block. It yields test commands, isolation arguments, runtime timeout windows, and explicit test marker filter flags.
* **Output Format:** Plaintext environmental strings or a JSON map matching system execution environments.

---

### 2. Workspace & Lifecycle Operations

#### `deviate init`

* **Legacy Mapping:** New programmatic replacement for project bootstrap.
* **Scope:** Bootstrap phase — implemented
* **Description:** Initializes a standard project-level DeviaTDD compliance framework. It builds out a baseline `.deviate/` dot directory, establishes a default global tracking layer, injects project-wide rules inside `specs/constitution.md`, and safely deploys client configuration hooks (e.g., `.claudecode.json` or `.factory/commands/`) containing the interface definitions for interactive macro flows.
* **Execution Modes:**
  * **Offline Mode (Default):** Scans root project files (e.g., `pyproject.toml`, `package.json`, `mix.exs`) using regular expressions to resolve `${VARIABLE}` placeholders in the constitution boilerplate. Completes in L_max <= 50ms.
  * **Onboard Prompt Mode:** `deviate init --generate-constitution` invokes an authorized LLM runner (e.g., `droid`, `claude`, `agy`) to analyze project state and generate a tailored constitution.
* **Tokenized Placeholder Resolution:**
  | Variable | Source File | Detection Pattern |
  | --- | --- | --- |
  | `${TARGET_BACKEND_FRAMEWORK}` | `pyproject.toml`, `package.json`, `mix.exs` | Framework name regex |
  | `${TARGET_PACKAGE_MANAGER}` | `pyproject.toml`, `package.json`, `Cargo.toml` | Package manager detection |
  | `${TARGET_TEST_RUNNER}` | `pyproject.toml`, `package.json` | Test framework detection |
  | `${TARGET_COVERAGE_MINIMUM}` | Default: `80%` | Configurable via profile |
* **Output Artifacts:**
  * `.deviate/config.toml` — Persisted configuration profile storage
  * `.deviate/session.json` — Current session state snapshot
  * `.deviate/prompts.log` — Execution audit trail log
  * `.deviate/prompts/` — Agent-tailored prompt template vault (`/explore`, `/research`, `/prd`, `/shard`, `/specify`, `/tasks`)
  * `specs/constitution.md` — Global technical rules anchor (authoritative architectural gatekeeper)
* **Agent Export:** Supports `--agent claude` and `--agent droid` formatting variants. `ExportMode.local` routes to `{repo_root}/.claude/commands/`; `ExportMode.global` routes to `$HOME/.claude/commands/`. Completes in L_max <= 200ms per agent platform.
* **Governance File Provisioning:** `deviate init` checks for `CLAUDE.md` or `AGENTS.md` at repository root. If present, appends DeviaTDD behavioral block idempotently; if absent, creates `CLAUDE.md` with authoritative micro-sandbox policy rules.

#### `deviate feature create <title-or-issue-id>`

* **Legacy Mapping:** `create-new-feature.sh`, `assign-next-issue.sh`
* **Description:** Consumes a raw system ticket description or numeric string parameter, strips volatile non-alphanumeric text nodes, and transforms it into a URL-friendly lowercase string layout (`feature-slug`). It switches the local working tree over to a clean, isolated git branch or worktree, initializes the feature subdirectory framework inside `specs/{FEATURE_SLUG}/`, and marks that specific slug as the active workspace target within `.deviate/session.json`.
* **Input Parameters:**
* `<title-or-issue-id>` (Positional string match argument)

#### `/shard` Command (Macro Layer)

* **Objective:** Decomposes the PRD into standalone, testable issue files.
* **Granularity Guidelines:**
  * **Target:** Average of 5 issues per feature shard
  * **Each issue must be a vertical slice:** Delivers a complete, testable behavior end-to-end (not a horizontal layer like "add database")
  * **Independence:** Each issue should be independently implementable and testable
  * **Scope bounds:** No issue should require <3 tasks (merge with another issue) or >10 tasks (split into multiple issues)
  * **Testability:** Each issue must have clear acceptance criteria that can be validated with automated tests
* **Action Logic:**
  1. Reads `prd.md` and identifies distinct user-facing behaviors or system capabilities
  2. Groups related requirements into vertical slices that deliver tangible value
  3. Validates granularity: warns if any issue is too broad (>10 tasks estimated) or too narrow (<3 tasks)
  4. Creates issue stub files at `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/`
  5. Appends issue records to `specs/issues.jsonl` with initial `BACKLOG` status



#### `deviate feature sync`

* **Legacy Mapping:** New programmatic context maintenance routine.
* **Description:** Automatically rebases the current feature branch against the project's upstream default integration branch (`main`/`master`), evaluates file trees for merge conflicts inside the `specs/` layout, and warns if structural interface changes invalidate current active technical plans.

#### `deviate adhoc <task-description>`

* **Legacy Mapping:** New condensed macro-layer shortcut replacing manual explore → prd → shard for single-issue tasks.
* **Scope:** Macro layer fast-path — condenses Explore, PRD, and Shard into a single operation.
* **Description:** Evaluates a freeform task description, performs proportional exploration based on task complexity, and directly creates a single self-contained issue in `specs/adhoc/`. Appends a condensed PRD entry to the aggregated `specs/adhoc/prd.md` and registers the issue in the global `specs/issues.jsonl` append-only ledger with an `ADH-{NNN}` identifier. If the task is too complex for ad-hoc treatment (multi-module coordination, state management, new architecture), the command halts and directs the user to run `/explore` to initiate a full epic workflow instead.
* **Complexity Gate:** Before proceeding, the prompt performs a lightweight complexity evaluation:
  * **Low (1-2 files, localized change, simple logic):** Minimal exploration — scan the immediate file and its imports. Proceed directly to single-shard issue creation.
  * **Medium (2-5 files, cross-module but well-bounded, moderate logic):** Bounded exploration — scan relevant modules, identify dependencies, produce abbreviated PRD with 1-3 requirements. Emit one vertical-slice issue.
  * **High (5+ files, new modules, state management, architectural decisions):** Halt with a `COMPLEXITY_GATE_REJECTION`. Guide the user: _"This task requires a full epic workflow. Run `/explore` to establish a feature branch and comprehensive exploration."_
* **Execution Steps** (all local, zero network):
  1. Ensure `specs/adhoc/` directory exists (create on first use)
  2. Evaluate task complexity against the project constitution and codebase structure
  3. If complexity gate rejects → emit guidance and exit
  4. If accepted → perform proportional exploration (file scanning, dependency mapping)
  5. Synthesize a condensed PRD entry and append to `specs/adhoc/prd.md`
  6. Generate a single issue file at `specs/adhoc/issues/{ADH-NNN}-{kebab-slug}.md`
  7. Append issue record to `specs/issues.jsonl` with `type: "adhoc"`, `issue_id: "ADH-{NNN}"`, `feature_slug: "adhoc"`
  8. Run `deviate context` to synchronize agent context with the new issue
* **Input Parameters:**
  * `<task-description>` (Positional string: freeform natural-language description of the task)
* **Output Artifacts:**
  * `specs/adhoc/prd.md` — Aggregated PRD with condensed entries for all adhoc issues (append-only)
  * `specs/adhoc/issues/{ADH-NNN}-{kebab-slug}.md` — Single vertical-slice issue file
  * `specs/issues.jsonl` — Append-only global issue ledger entry with `issue_id: "ADH-{NNN}"`

---

### 3. Task & Tracking Mutations

#### `deviate tasks parse`

* **Legacy Mapping:** `manage-tasks.sh` (structural validations)
* **Description:** Scans `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` and applies a strict schema validator. Validates task nodes contain compliant tracking indicators, valid type enums (`tdd`, `direct`, `e2e`), and well-formed JSON.
* **Returns:** Exit code `0` on validation pass. Exit code `1` with localized file diagnostics on failure.

#### `deviate tasks list`

* **Legacy Mapping:** Custom system dashboard visualizations.
* **Description:** Reads `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` and derives current task states by parsing the append-only ledger sequentially. Converts to tabular summary of current, completed, pending, or blocked tasks. Supports `--type [tdd|direct|e2e]` filtering.
* **Output Format:** Tabular console output via `deviate` CLI dashboard, or `--json` for machine injection.

#### `deviate tasks update <task-id> <event>`

* **Legacy Mapping:** `manage-tasks.sh` (state updates)
* **Description:** Appends a new state transition event to the append-only `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` ledger. Events are restricted to the `TaskEvent` enum: `CREATED`, `CLAIMED`, `RELEASED`, `COMPLETED`, `FAILED`. Status derivation is computed dynamically by parsing the ledger sequentially — no existing line is ever modified or overwritten.
* **Security & Governance Constraint:** This endpoint enforces programmatic access restrictions. An executive agent running inside an interactive chat layout **cannot** directly append events to the ledger unless the request is cryptographically signed or directly spawned by the trusted internal `deviate run` micro-sandbox automated loop engine. Concurrent claim attempts are resolved via atomic Git reference pushes (see Atomic Concurrency Protocol in DeviaTDD-architecture.md).
* **Input Parameters:**
* `<task-id>` (Target sequence identifier, e.g., `TSK-001-01`)
* `<event>` (`CREATED` / `CLAIMED` / `RELEASED` / `COMPLETED` / `FAILED`)
* `--worker <name>` (Optional worker identifier for `CLAIMED` events)

#### `deviate issues create <title> --type [feature|adhoc]`

* **Description:** Creates a new issue record in the global append-only `specs/issues.jsonl` ledger. Assigns a deterministic `ISS-{NNN}` identifier for `type: "feature"` or `ADH-{NNN}` for `type: "adhoc"`, derives a URL-friendly `feature_slug`, and appends the initial `BACKLOG` status entry. For `type: "feature"`, scaffolds the feature workspace directory tree under `specs/{FEATURE_SLUG}/`. For `type: "adhoc"`, creates `specs/adhoc/` workspace and appends a condensed PRD entry to `specs/adhoc/prd.md`.
* **Input Parameters:**
* `<title>` (Positional string: issue title or ticket description)
* `--type [feature|adhoc]` (Defaults to `feature`)
* **Ad-Hoc Shortcut:** `deviate adhoc "Fix broken pydantic mapping types"` condenses explore + prd + shard into a single operation. See `deviate adhoc` below for the full complexity-gated flow.

#### `deviate issues list`

* **Description:** Reads and parses `specs/issues.jsonl` to derive real-time issue states. State is computed by scanning the ledger bottom-up: the first entry found for an `issue_id` defines its current status. Renders a tabular summary filtered by `type`, `feature_slug`, or `status`.
* **Output Format:** Tabular console output or `--json` for machine injection.

#### `deviate issues update <issue-id> <event>`

* **Description:** Appends a status transition event to `specs/issues.jsonl`. Events are restricted to the `IssueEvent` enum: `CREATED`, `CLAIMED`, `RELEASED`, `COMPLETED`, `FAILED`. No existing line is ever modified.
* **Input Parameters:**
* `<issue-id>` (Target issue identifier, e.g., `ISS-001`)
* `<event>` (`CREATED` / `CLAIMED` / `RELEASED` / `COMPLETED` / `FAILED`)
* `--worker <name>` (Optional worker identifier)



---

### 4. Micro-Sandbox Execution Loops & VCS Gates

#### `deviate run <task-id>`

* **Legacy Mapping:** Integrated RGR core runtime framework.
* **Description:** Triggers the deterministic, automated execution cycle for a singular decomposed task node. It traps the probabilistic agent substrate within a rigid state machine cycle (`IDLE` -> `RED` -> `GREEN` -> `REFACTOR` -> `JUDGE` -> `IDLE`). It handles file tamper guards, monitors the file system, executes test runner parameters retrieved from `deviate test-config`, applies Train Gate resets on assertion compilation breaks, and auto-commits the diff tree on verified loop steps.
* **Execution Engine:** The Micro sandbox uses **Aider's Python API** (`aider.coders.Coder`) as its LLM execution substrate. A single `Coder` object is instantiated per task and reused across RED, GREEN, and REFACTOR phases to preserve KV cache across turns. Aider's SEARCH/REPLACE diff format sends only changed lines, not full file rewrites — yielding ~10x output token savings per turn. The JUDGE and YELLOW phases spawn isolated sessions (fresh `Coder` instances, different model) to break recursive subjectivity. Model routing follows the tiering defined in DeviaTDD-architecture.md Section 5.2.
* **Cache Optimization:** Test files that do not change during a cycle are loaded as Aider `--read` (read-only) context, keeping them in the stable cache prefix. Only the implementation file being edited is in the mutable file set. This maximizes the stable prefix size and KV cache hit rate. The system prompt, repo map, and read-only test files form a prefix that achieves 90%+ cache hit rates after the first turn.
* **Input Parameters:**
* `<task-id>` (Positional sequence hash target identifier)
* `--profile <name>` (Overrides default runtime engine constraints, e.g., `fast`, `secure`)



#### `deviate run --all`

* **Legacy Mapping:** Automated multi-step orchestration.
* **Description:** Sequences and triggers the sequential resolution of all unblocked, incomplete items defined inside the target feature matrix until it hits a task block or error condition.

#### `deviate commit --stage <phase>`

* **Legacy Mapping:** `git-commit.sh`
* **Description:** Enforces pre-commit invariants before finalizing a git change tracking step. It ensures that modified file boundaries match allowed code paths, validates that no files inside the `specs/` root folder have been changed by an execution agent, sets standardized prefixes matching the current execution phase, and commits the code.
* **Input Parameters:**
* `--stage [RED|GREEN|REFACTOR|E2E]`



---

## Part 2: Document Architecture & Prompt Ownership

To enforce inference path consistency and maximize KV caching efficiency, files are split into cross-project constraints and feature buckets. Volatile data arrays, state history flags, and configuration profiles are hosted cleanly within the `.deviate/` metadata directory.

### 1. File Tree Blueprint

```text
.deviate/
├── config.toml               # Test parameters, target models, environment execution configurations
├── session.json              # State tracker file mapping active branch and lock metrics
└── prompts.log               # Append-only execution record storing runtime loop diagnostic trails
specs/
├── constitution.md           # Absolute project invariants and architectural constraints
├── issues.jsonl              # Global append-only issue registry (features + ad-hoc hotfixes)
├── adhoc/                    # Ad-hoc issue workspace (condensed explore+prd+shard for single issues)
│   ├── prd.md                # Aggregated PRD with condensed entries for all adhoc issues (append-only)
│   └── issues/               # Adhoc-scoped issue files
│       └── {ADH-NNN}-{kebab-slug}.md
└── features/
    └── {FEATURE_SLUG}/       # Isolated feature workspace bucket
        ├── explore.md        # Raw codebase context (cheap scan — what exists)
        ├── design.md         # Architectural decisions and trade-offs (smart design)
        ├── data-model.md     # Entity relationships, schemas, data flow
        ├── prd.md            # System-level product requirement documents
        ├── spec.md           # Pure functional contract ("What & Why" system bounds)
        ├── issues/           # Feature-scoped issue sub-workspaces
        │   └── {ISSUE_ID}/
        │       ├── spec.md   # Issue-level functional specification
        │       └── tasks.jsonl  # Issue-scoped append-only micro-task ledger (with implementation hints)
        └── tasks.jsonl      # Legacy feature-level append-only micro-task ledger (DEPRECATED)
```

**Global Issue Ledger (`specs/issues.jsonl`):**
```json
{"issue_id": "ISS-001", "type": "feature", "feature_slug": "auth-jwt", "title": "Implement JWT validation", "status": "BACKLOG", "timestamp": "2026-05-31T10:00:00Z"}
{"issue_id": "ISS-002", "type": "feature", "feature_slug": "auth-jwt", "title": "Refresh token rotation", "status": "BACKLOG", "timestamp": "2026-05-31T10:05:00Z"}
{"issue_id": "ISS-001", "type": "feature", "feature_slug": "auth-jwt", "status": "CLAIMED", "worker_id": "macbook-pro", "timestamp": "2026-05-31T12:30:00Z"}
{"issue_id": "ADH-001", "type": "adhoc", "feature_slug": "adhoc", "title": "Fix broken pydantic mapping types", "status": "CLAIMED", "worker_id": "wsl-terminal", "timestamp": "2026-05-31T17:15:00Z"}
```

**Issue-Scoped Micro-Task Ledger (`specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`):**
```json
{"task_id": "TSK-001-01", "type": "tdd", "action": "create_jwt_validator_class", "status": "CREATED", "timestamp": "2026-05-31T10:00:05Z"}
{"task_id": "TSK-001-01", "type": "tdd", "action": "create_jwt_validator_class", "status": "CLAIMED", "worker_id": "droid-alpha", "timestamp": "2026-05-31T10:00:10Z"}
{"task_id": "TSK-001-01", "type": "tdd", "action": "create_jwt_validator_class", "status": "COMPLETED", "timestamp": "2026-05-31T10:15:30Z"}
{"task_id": "TSK-001-02", "type": "e2e", "action": "integration_token_flow", "status": "CREATED", "timestamp": "2026-05-31T10:16:00Z"}
```

---

### 2. Prompt Matrix & File Generation Lifecycle

Macroscopic commands represent user-facing conversational routines registered as interactive slash commands inside client execution configurations during the `deviate init` process.

| Client Command Trigger | Responsible Persona Role | Targets Created / Mutated | Internal CLI Endpoints Executed |
| --- | --- | --- | --- |
| `/explore` | Context Scanner (Cheap) | `specs/{FEATURE_SLUG}/explore.md` | `deviate feature create`, `deviate context` |
| `/research` | Architect (Expensive) | `specs/{FEATURE_SLUG}/design.md`, `specs/{FEATURE_SLUG}/data-model.md` | `deviate context` |
| `/prd` | Product Owner Proxy | `specs/{FEATURE_SLUG}/prd.md` | `deviate context` |
| `/adhoc` | Condensed Scoper | `specs/adhoc/issues/{ADH-NNN}-{slug}.md`, `specs/adhoc/prd.md`, `specs/issues.jsonl` | `deviate adhoc`, `deviate context` |
| `/specify` | Systems Architect | `specs/{FEATURE_SLUG}/spec.md` | `deviate ast parse` |
| **[HITL GATE]** | Human Reviewer | — | — |
| `/tasks` | Technical Lead + Decomposition Parser | `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl` | `deviate test-config`, `deviate tasks parse` |

**Session Continuity Strategy:**
- **Meso layer** (`/specify` → `/tasks`): Single continuous LLM session. The system prompt, tool definitions, and `spec.md` content form a stable prefix cached after turn 1, achieving 90%+ KV cache hit rates on subsequent turns.
- **Micro layer** (RED → GREEN → REFACTOR): Single Aider `Coder` session per task. Read-only test files live in the cached prefix; only the implementation file varies. Model switching mid-task is prohibited.
- **Compliance gates** (JUDGE, YELLOW): Isolated sessions with no cache sharing. Compliance integrity takes precedence over cost savings.

#### 1. Command Definition: `/explore` (Cheap Context Gathering)

* **Objective:** Fast, inexpensive scan of codebase structure, dependencies, existing patterns, and tech stack.
* **Model:** Cheap model (V4 Flash) — deterministic, mechanical context extraction.
* **Output:** `explore.md` — raw factual context (what exists, not what to do).
* **Action Logic:**
1. Spawns the feature directory layout and sets up working git states by running:
```bash
deviate feature create "auth logging overhaul"
```
2. Resolves global project environment mappings by calling:
```bash
deviate context --json
```
3. Scans codebase structure: directory tree, dependencies (pyproject.toml, package.json, etc.), existing patterns, tech stack, configuration files.
4. Extracts factual context without analysis or recommendations.
5. Writes concise `explore.md` to `specs/{FEATURE_SLUG}/explore.md`.

#### 1.5. Command Definition: `/research` (Architectural Design)

* **Objective:** Consumes `explore.md` and performs high-level architectural analysis: trade-offs, options matrix, design decisions, and data modeling.
* **Model:** Reasoning model (Qwen thinking or V4 Pro) — abstract reasoning and design.
* **Output:** `design.md` (architecture decisions, trade-offs, options) and `data-model.md` (entity relationships, schemas).
* **Action Logic:**
1. Reads `explore.md` (raw context from previous phase).
2. Analyzes architectural options and trade-offs.
3. Produces design decisions with rationale in `design.md`.
4. Defines entity relationships, schemas, and data flow in `data-model.md`.
5. Writes both files to `specs/{FEATURE_SLUG}/`.



#### 2. Command Definition: `/prd`

* **Objective:** Transforms architectural design into immutable user requirements.
* **Action Logic:**
1. Requests environment parameters:
```bash
deviate context --json
```
2. Reads `design.md` (architectural decisions from Research phase).
3. Produces a detailed requirements layout inside `prd.md`, specifying structural user goals, performance constraints, user behavior limits, and validation parameters.



#### 3. Command Definition: `/specify`

* **Objective:** Converts product goals into absolute system interfaces.
* **Action Logic:**
1. Scans the codebase to discover module configurations and API definitions by calling:
```bash
deviate ast parse ./src/core/auth

```


2. Compiles functional interfaces, schema objects, route patterns, and system edge cases into `spec.md`, defining the architectural boundary contract.



#### 4. Command Definition: `/tasks` (Merged with former `/plan`)

* **Objective:** Decomposes the functional specification into sequential, testable tasks with implementation hints.
* **Granularity Guidelines:**
  * **Target:** Average of 5 tasks per issue
  * **Functional unit:** Each task represents a complete functional unit that can be implemented and tested in a single TDD cycle (RED → GREEN → JUDGE → REFACTOR)
  * **Not too granular:** Avoid "create one file" or "add one function" tasks — these waste tokens on context switching
  * **Not too broad:** Each task should be completable in 15-60 minutes of focused work
  * **Bounds:** No issue should have <3 tasks (issue too narrow) or >10 tasks (issue too broad, should be split)
  * **Test-first:** Each `tdd` task must map to a specific test assertion in `spec.md`
* **Action Logic:**
1. Collects system runtime execution targets:
```bash
deviate test-config

```


2. Reads `spec.md` (functional contract) and generates task decomposition with implementation hints
3. Each task includes:
   - `task_id`: Unique identifier (`TSK-{ISSUE_ID}-{NN}`)
   - `type`: `tdd` (full TDD loop), `direct` (boilerplate/config), or `e2e` (integration)
   - `action`: Description of what to implement
   - `implementation_hints`: File locations, mock boundaries, fixture requirements
   - `acceptance_criteria`: Specific test assertions this task must satisfy
   - `blocked_by`: DAG dependencies on other tasks (if any)
4. Automatically appends a terminal `type: "e2e"` task to validate the issue's holistic system flow
5. Validates granularity: warns if task count is outside 3-10 range
6. Writes to `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`
7. Asserts structural integrity:
```bash
deviate tasks parse

```





Once the macroscopic loops finalize `tasks.md` inside the feature directory, control shifts from the interactive conversation space back to the developer's local terminal. The developer passes task tracking indices over to the automated local execution runner loop:

```bash
deviate run task-001

```

This structural division keeps project directories clean, guarantees reproducible prompt execution flows, and traps untrusted code changes within a protected, programmatically validated micro-sandbox test loop.

---

### 3. Model Pricing Reference (DeepSeek V4, June 2026)

The model routing decisions throughout this architecture are grounded in DeepSeek V4's
KV-cache-aware pricing structure:

| Model | Cache-Hit Input (1M tokens) | Cache-Miss Input (1M tokens) | Output (1M tokens) | Cache Discount |
|---|---|---|---|---|
| V4 Flash | $0.0028 | $0.14 | $0.28 | 98.0% |
| V4 Pro (discounted) | $0.003625 | $0.435 | $0.87 | 99.17% |

Context length: 1M tokens. Cache-hit tokens are billed when a request's prefix matches a
previously cached prefix. See `api-docs.deepseek.com/quick_start/pricing` for current rates.

The architecture optimizes for cache-hit pricing wherever possible: continuous-thread sessions
for Meso `/specify` + `/tasks`, single-session reuse for Micro RED → GREEN → REFACTOR, and
read-only file loading for stable prefix maximization.
