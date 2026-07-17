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
  project-specific test/lint/format/setup/dev commands, ensures a symlink
  relationship between `CLAUDE.md` and `AGENTS.md` (via
  `_linkify_governance_files`), applies governance blocks to the canonical
  file, and installs the DeviaTDD prompt commands. Currently 25 `deviate-*`
  slash commands + 1 standalone `tools-mcp-servers` command (for Factory Droid)
  — 26 flat `.md` files total — are installed to `.{agent}/commands/` (or
  `.{agent}/prompts/` for Pi) during `deviate setup`. Commands land in all agent
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
  * `AGENTS.md` — Symlink to `CLAUDE.md` (or vice-versa if only `AGENTS.md`
    existed pre-setup). Created by `_linkify_governance_files`; idempotent.
  * `.claude/commands/`, `.opencode/commands/`, `.factory/commands/`,
    `.pi/prompts/` — DeviaTDD prompt commands installed for every
    supported agent (24 flat `.md` files total, split across the four
    dirs)

#### `deviatdd` Skill (Project-Local Single Skill)

* **Source:** `src/deviate/prompts/skills/deviatdd/SKILL.md`
  (package resource, loaded via `importlib.resources`).
* **Installer:** new `_install_deviatdd_skill(workdir, agents)` +
  `_get_agent_skill_dir(workdir, agent)` + `_resolve_skill_source()` in
  `src/deviate/cli/__init__.py`, called from `setup()` after
  `_install_commands_to_agents(...)`. Idempotent (content-equality skip
  mirrors `install_command`'s contract).
* **Install targets (all five `active_agents`):** the skill is written
  to `<workdir>/.<agent>/skills/deviatdd/SKILL.md` for every agent
  platform that `setup` provisions commands for, regardless of whether
  each platform documents a project-local skills convention. Mirrors
  `_install_commands_to_agents`'s write-everywhere policy — every
  operator using `--agent <platform>` gets the skill at the canonical
  skills directory for their platform, ready to be picked up if/when
  that platform ships a discovery convention.
  * `claude` -> `<workdir>/.claude/skills/deviatdd/SKILL.md`
    (verified — same form as user-level `~/.claude/skills/<name>/SKILL.md`).
  * `opencode` -> `<workdir>/.opencode/skills/deviatdd/SKILL.md`
    (no documented project-local skills convention; file on disk for
    forward-compat).
  * `factory` -> `<workdir>/.factory/skills/deviatdd/SKILL.md`
    (same as opencode).
  * `pi` -> `<workdir>/.pi/skills/deviatdd/SKILL.md`
    (verified — `pi@latest` docs at
    `packages/coding-agent/docs/skills.md` list `.pi/skills/` as a
    project-local skill discovery path).
  * `omp` -> `<workdir>/.omp/skills/deviatdd/SKILL.md`
    (libref documents omp skills at user-level
    `~/.omp/agent/managed-skills/<name>/SKILL.md` and via a
    settings-driven `skills` array; operators can register the
    project-local file via OMP's settings).
* **Scope:** Micro-layer only. The skill orchestrates `deviate micro
  run --all`, triages every error class micro can surface, and runs
  a four-step safety-gated `git reset --hard && git clean -fd`
  clean-slate retry (ledger sanity -> workspace inventory -> typed
  user confirmation -> reset; matches `_execute_rollback`'s
  `git clean -fd` contract — `without -x`, so `.deviate/`, `.mise/`,
  `.venv/` survive). Meso orchestration is out of scope — operators
  use `/deviate-meso`, `/deviate-plan`, `/deviate-tasks`. A Dispatch
  section points the agent to those canonical slash commands when a
  failure escapes micro's scope; the skill never invokes them inline.
* **`## Troubleshooting failed runs` (skill v1.1.0):** before guessing
  at a fix, the skill directs the agent to the two complementary
  `.deviate/logs/` sinks wired through
  `src/deviate/core/run_logger.py::_LogRegistry.dispatch`:
  * `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log` — per-task transcript;
    append-mode history across retries of one task. Created only
    inside `_execute_task_with_retry` when both `issue_id` and a
    known `task_id` resolve; tasks missing either never get a
    per-task file.
  * `.deviate/logs/run_<UTC>.log` — per-run chronological log;
    one file per invocation, always written.
  Each event line is `[<UTC iso>] <EVENT>\n  <kwarg>: <value>\n`
  (multi-line values are indented four-space under a `key:` header).
  The authoritative event inventory is the set of
  `_log_run("<NAME>", ...)` calls in `src/deviate/cli/micro.py`.
  Canonical events for triage: `TASK_FAILED` (carries `error=`;
  post-cycle failure — read first), `PHASE_START`, `PHASE_DECISION`
  (NOT necessarily terminal — emitted for both intermediate JUDGE
  routing decisions and the final CYCLE outcome; interpret via
  `decision=` / `reroute=` / `action=` plus `phase=`), `PHASE_SKIP`,
  `INVOKE_AGENT` (names `backend=` and `model=`), `AGENT_RESULT`
  (carries `status=`, `verdict=`, full `manifest=`; the manifest
  contains `files=`, not the event itself), `AGENT_RAW_OUTPUT`
  (full stdout in a single `raw_output=` field; stderr is NOT
  captured), `AGENT_TIMEOUT` (carries `error=` and
  `partial_stderr=`), `AGENT_ERROR`, `AGENT_NOT_AVAILABLE`,
  `JUDGE_REJECTED`, `JUDGE_AGENT_NO_FEEDBACK`,
  `JUDGE_REFACTOR_NOTE` (carries `note=`, the refactor hint),
  `TASKS_MD_NO_MATCH`, `TASKS_MD_FEEDBACK`, `TASKS_MD_SKIP`,
  `FEEDBACK_COMMIT_FAILED`, `POST_CMD_FAILURE` (carries
  `uncommitted_count=` and `files=`, the dirty files the hook
  refused — NOT `returncode=` / `stderr=`).
  Skill frontmatter version is `1.1.0`. The drift-check test
  `test_deviatdd_skill_troubleshooting_section_matches_logger` parses
  `micro.py` for `_log_run("<NAME>", ...)` calls and asserts every
  backticked event name in the Troubleshooting section is a real
  emitted event — guards against invented event names. Per-event
  field schemas are documented in `micro.py`, not duplicated here.
* **`.gitignore` exclusions:** `_ensure_root_gitignore` adds
  `*/skills/deviatdd/` to the entries tuple alongside
  `*/commands/deviate-*.md` and `*/prompts/deviate-*.md`. The
  single-level wildcard covers all five agent platforms
  (`.claude/`, `.opencode/`, `.factory/`, `.pi/`, `.omp/`) with one
  pattern. The single-level prefix (`*/`, not `**/`) is critical: it
  scopes the pattern to the project root, never matching the
  source-of-truth at `src/deviate/prompts/skills/deviatdd/` (three
  directories deep).
* **Tests:** `TestInstallDeviatddSkill` (8 tests) in
  `tests/test_cli/test_init.py` covers install-to-all-five-agents,
  idempotence, gitignore entry presence + idempotence, safety-gate
  fragments in the SKILL.md body, well-formed frontmatter, and the
  dispatch table's canonical slash-command references.


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
    with a convention-aware message (`🔧 chore(constitution): update constitution` when
    emoji conventions are detected, otherwise `chore(constitution): update constitution`).
    Emits `{"status": "SUCCESS"}` on success.
* **Common Flags:** None (each sub-command exposes its own options).

### 1.5 Product Layer *(optional, sits above Macro)*

The Product layer ships as **agent skills** (no dedicated CLI subcommands) — the prompts live at `src/deviate/prompts/commands/deviate-{flows,architecture,release}.md` and are installed to all four agent directories alongside the rest. They are **not** wired into the `deviate` CLI's `pre`/`post` subcommand pattern: the agent invokes them directly as `/deviate-flows`, `/deviate-architecture`, `/deviate-release`, and the conversation produces the artifact. The CLI's only involvement is installing the skill files during `deviate setup` and (via `deviate-shard` / `deviate-adhoc`) consuming the `flow_refs:` frontmatter those artifacts emit.

| Command | Source skill | Artifact committed | Notes |
|---------|--------------|--------------------|-------|
| `/deviate-flows` | `src/deviate/prompts/commands/deviate-flows.md` (FLOW-01) | `specs/_product/flows/flows-<domain>.md` + updated `specs/_product/flows/index.md` | Conversational; the agent must surface clarifying questions when actor, job-to-be-done, or trigger is ambiguous. FLOW-NN IDs use `^FLOW-\d{2,}$`. **Commit protocol (v1.4.0):** Phase A drafts every flow file + index row to disk as the conversation progresses (no commit). Phase B fires exactly one `stage_and_commit` after the user explicitly signs off ("commit", "looks good", "done", "ship it", "approve", "lgtm", "yes"), passing every session-authored flow file plus `index.md` in `files=`. The pre-commit `git diff --cached --name-only` audit must confirm the staged set is a subset of the session-owned files; any extras halt the commit. Silence is not sign-off. |
| `/deviate-architecture` | `src/deviate/prompts/commands/deviate-architecture.md` (FLOW-02) | `specs/_product/architecture.md` (includes `## Architectural Decision Records` when qualifying decisions exist) + `specs/_product/domain-model.md` | **Precondition:** at least one flow file under `specs/_product/flows/` must exist; otherwise the skill must surface `[red]FLOWS_MISSING[/]` and recommend `/deviate-flows` first. ADRs are one-paragraph entries appended inline when a decision is hard to reverse, surprising without context, and the result of a real tradeoff. **Commit protocol (v1.3.0):** Phase A drafts `specs/_product/architecture.md` and `specs/_product/domain-model.md` to disk as the conversation progresses and stages them via `deviate.core.commit.stage_files` so the user can `git diff --cached` while iterating — no commit fires mid-conversation. Phase B fires exactly one `stage_and_commit` after the user explicitly signs off ("commit", "looks good", "done", "ship it", "approve", "lgtm", "yes" — silence is not sign-off), passing every session-authored architecture and domain-model file in `files=`. The pre-commit `git diff --cached --name-only` audit must confirm the staged set is a subset of the session-owned files; any extras halt the commit and surface the discrepancy (no auto-unstage). The skill no longer calls `commit_artifact(path, msg)` — that helper emits one commit per path and would reproduce the v1.2.0 split-across-N-commits regression. `git add -A` and `git commit --only` are also forbidden. The classification banner (`Local` / `Context-Bridging` / `Context-Creating`) rides in the commit body. Never pass `no_verify=True`; if a pre-commit hook fails, surface stderr verbatim and stop — do not retry with `--no-verify`. |
| `/deviate-release` | `src/deviate/prompts/commands/deviate-release.md` (FLOW-03) | `specs/_product/release-next.md` (overrides previous) | **Precondition:** both `specs/_product/architecture.md` and at least one flow file must exist; otherwise `[red]ARCH_OR_FLOWS_MISSING[/]`. The release goal (free-text user input) drives the Included Flows / Included Work / Acceptance tables. |

**Downstream consumption:** `deviate-shard` and `deviate-adhoc` SKILL.md bodies read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, and `specs/_product/domain-model.md` as authoritative context. Each sharded or adhoc issue emits a `flow_refs: [FLOW-XX, ...]` field in its YAML frontmatter and in the `IssueRecord.flow_refs` ledger entry (validated against `^FLOW-\d{2,}$`), so vertical slices stay traceable back to the flow that motivated them. `deviate adhoc pre` accepts a `--flow-ref FLOW-01,FLOW-02` CLI override to set the flow refs explicitly when the agent's natural-language inference is ambiguous.

**Active Domain Discipline** is enforced at HITL gates: the Product-layer discovery steps (`/deviate-flows`, `/deviate-architecture`) follow a structured 7–8 bullet active discipline — one question at a time with a recommended answer, dependency-ordered, read-first, term-challenge against the glossary, sharpen fuzzy language, stress-test with scenarios, and update the artifact (`flows-<domain>.md` or `domain-model.md`) inline as terms resolve.

#### `/deviate-shard` (Macro Layer)

* **Objective:** Decomposes the PRD into standalone, testable issue files.
* **Granularity Guidelines:**
  * **Target:** 4-8 issues per feature shard
  * **Each issue must be a vertical slice:** Delivers a complete, testable behavior end-to-end
  * **Independence:** Each issue should be independently implementable and testable
  * **Scope bounds:** No issue should require <1 task or >10 tasks
  * **Testability:** Each issue must have clear acceptance criteria
  * **Enforcement:** The shard prompt owns all slicing rules. Pass 1 (Topological Layout + Flow Anchor) partitions by primary `FLOW-XX`, not by FR. Pass 1.5 (Slice Cap Gate) hard-enforces the 4–8 / max-10 cap with `SLICE_CAP_EXCEEDED`. Pass 3.5 (Merge Pass) collapses adjacent horizontal slices that share workstations or demo paths. The PRD prompt no longer carries §Issue Sharding Strategy; it shapes FRs via flow-segment authoring guidance only.

---

### 2. Macro Layer: Feature Scoping (pre/post)

All macro-layer commands follow the `pre`/`post` subcommand pattern (except `init`).
Every `pre` subcommand accepts `--json` (emit JSON contract to stdout) and `--quiet`
(suppress diagnostic output).

**Active Domain Discipline** is enforced at HITL gates: the macro phases that interact with the human (`/deviate-research` Gate 1, `/deviate-prd` Ambiguity Interrogation, `/deviate-shard` Gate 2) actively term-challenge against the upstream glossary, sharpen fuzzy language, stress-test with concrete edge-case scenarios, and update the relevant artifact (`design.md`, `data-model.md`, `prd.md`) inline as terms resolve — not as a passive sign-off step.

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
  (unless `--force`), commits via `commit_artifact()` with a convention-aware message
  (`📚 docs({epic}-{issue}): create plan.md` when emoji conventions are detected),
  and `transition_to("TASKS")`. Skips the commit silently when there are no changes to stage.

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

#### `deviate merge --issue <id> [--stage-only] [-m <msg> ...] [--delete-branch] [--delete-worktree]`

* **Source:** `src/deviate/cli/meso.py` (`_merge_run`)
* **Description:** Marks an issue COMPLETED in the ledger with a full Pydantic-validated
  `IssueRecord`.  Two-phase squash-merge flow used by the `/deviate-merge` slash command:

  - `--stage-only` writes the COMPLETED transition to `specs/issues.jsonl` and `git add`-s
    it, but does NOT commit.  The caller is expected to fold this into a squash-merge
    commit.  When called a second time (e.g. after the user has already staged the
    ledger), the transition write is idempotent — `LEDGER_IDEMPOTENT` is printed and
    the function proceeds to the commit step instead of short-circuiting.
  - `-m <subject> -m <body> ...` performs the combined commit: `git add -A` picks up
    the staged feature changes, the first `-m` is routed through `format_commit_message`
    (applying the project's emoji convention), and remaining `-m` values are passed
    verbatim as body paragraphs.
  - `--delete-branch` removes the local feature branch
    (`feat/{bucket}/{slug}` derived from the issue's `source_file`), tags the
    pre-squash branch tip with `archive/{ISSUE_ID}/{YYYY-MM-DD}` (UTC date) so
    the full commit history survives the squash, pushes the tag to `origin`,
    then `git push origin --delete <branch>`-es the remote branch. Before
    running `git branch -D` the CLI inspects `git worktree list --porcelain`
    and removes any worktree that holds the branch — so an active pre-squash
    worktree does not block cleanup. Tag push and remote branch delete are
    best-effort: if `origin` is not configured they are skipped silently; if
    the remote is unreachable they print `PUSH_WARN` and local cleanup still
    proceeds. The archive tag is always created locally first, even when no
    remote is configured, because losing the squash-merged history is not
    recoverable from `main` alone.
  - `--delete-worktree` removes the worktree at `cwd` if the current directory is itself
    a linked worktree for the issue.

  The function is fully idempotent: re-running with no staged work prints
  `LEDGER_UNCHANGED` and exits cleanly without leaving stray commits.

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
  Commit messages are convention-aware: when the project uses emoji prefixes (detected via
  CONTRIBUTING.md or git history), the appropriate emoji is prepended automatically. RED
  phase `test:` commits are prefixed with 🚨 to flag the failing test (see
  `format_commit_message(..., phase="red")` in `core/convention.py`); GREEN phase `test:`
  commits use ✅. `feat:` commits always use ✨ regardless of phase.

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

#### `deviate run` (Full-Pipeline Orchestrator)

* **Source:** `src/deviate/cli/__init__.py` (top-level `run_command`)
* **Description:** Canonical "go do the next thing" entry point. Chains the meso
  pipeline (`deviate meso run`) with the micro drain (`deviate micro run --all`)
  inside the worktree the meso step just created. Discovers the next unblocked
  BACKLOG issue, claims it (creating the per-issue worktree), runs SPECIFY →
  PLAN → TASKS in the worktree, then drains every PENDING task through the TDD
  cycle (or the direct-execute phase for IMMEDIATE-typed tasks). Internally:
  1. Calls `_meso_run(issue_id=...)` from `src/deviate/cli/meso.py`, which returns
     the created worktree path on success (`str(worktree_path)`).
  2. `chdir`s into that worktree, updates `.deviate/session.json` to record the
     `run --all` handoff, and calls `_run_all()` from `src/deviate/cli/micro.py`
     to drain every PENDING task.
  3. On hard failure (no worktree returned, worktree missing) prints a structured
     error (`RUN_NO_WORKTREE` / `RUN_WORKTREE_MISSING`) and exits non-zero.
* **Input Parameters:**
  * `--issue <ISS-NNN-NN>` (Target a specific BACKLOG issue; default: next unblocked)
  * `--force` (Bypass `blocked_by` pre-flight guards; forwarded to meso)
  * `--profile [full|fast|secure]` (Forwarded to the micro drain; resolved via
    `resolve_profile()` from `src/deviate/core/profile.py`)
  * `--no-judge`, `--no-refactor` (Composable boolean overrides for the profile;
    forwarded to the micro drain)
  * `--agent <name>` (Override agent backend for the micro phase)
  * `--json` (Forward JSONL monitor events to stdout; suppresses Rich UI)
* **Exit Codes:** 0 on full success; 1 if meso or micro reports failure.
* **Replaces:** The old `deviate run <task-id>` and `deviate run --all`
  task-dispatch surface. The per-task and `--all` dispatches now live at
  `deviate micro run <task-id>` and `deviate micro run --all` respectively.

#### `deviate micro run [task-id]` / `deviate micro run --all`

* **Source:** `src/deviate/cli/micro.py` (`run_command` decorated by `micro_app`)
* **Description:** The per-task / queue-drain dispatcher that used to live as the
  top-level `deviate run`. Routes each task by `execution_mode` to the TDD cycle
  (RED → GREEN → JUDGE → REFACTOR) or to the execute phase. Single-task by
  default; `--all` drains every PENDING task for the active issue (or all
  issues if no active issue is set).
* **Single-Task (`deviate micro run <task-id>`):** Triggers the automated
  execution cycle for a single task node. TDD mode runs the RED → GREEN →
  JUDGE → REFACTOR cycle. Non-TDD (`DIRECT` or `E2E`) runs `_run_execute_phase`,
  which commits the work, then optionally runs a JUDGE pass against `spec.md`
  and rolls back on `COMPLIANCE_VIOLATION` (up to `max_judge_attempts = 3`).
  Implements `_run_single` / `_dispatch_task` from `src/deviate/cli/micro.py`.
  * **Green → Judge → Green loop (TDD only):** `_run_tdd_cycle` wraps the
    GREEN → JUDGE pair in a `while not judge_passed` loop with up to
    `max_train_attempts = 3`. On test failure or `COMPLIANCE_VIOLATION`,
    `_execute_rollback()` runs `git reset --hard <red_sha>` against the
    RED-boundary SHA stored in `session.red_commit_sha` (captured at the end of
    the RED phase), followed by `git clean -fd` to remove untracked files
    and directories created during the failed GREEN attempt (preserving
    gitignored state such as `.deviate/` by omitting `-x`); the runner
    commits a feedback marker unconditionally and advances
    `session.red_commit_sha` past it so a second rejection can roll back
    only the subsequent GREEN, the session is
    `force_transition_to("GREEN")`, and the
    previous attempt's feedback is injected as `<train_feedback>` into the next
    GREEN prompt via `_build_auto_prompt("green", ...) +
    "\n\n<train_feedback>\n{...}\n</train_feedback>\n"`. The cycle retries from
  When session feedback is unavailable, auto GREEN reads the matching task's persisted `**Judge Feedback**` bullets from `tasks.md` as `<persisted_judge_feedback>`. Session `train_feedback` remains authoritative when present, preventing duplicate or stale feedback; the reader is scoped to the exact task block.
    GREEN. After 3 attempts the task is marked `FAILED` and the pipeline halts
    with `PhaseFailedError`. The feedback source precedence is `train_feedback`
    on the manifest → `_extract_judge_feedback(...)` from `tasks.md` → verbatim
    verdict / rationale.
  * **JUDGE `next_action` routing:** The runner honors `HandoverManifest.next_action`
    verbatim. See the **JUDGE `next_action` Routing Table** in this document for
    the four supported values (`revert_before`, `revert_to_red`,
    `continue_refactor`, `skip_refactor`), the rollback anchors and
    boundary-advance rules per route, and the runner fallbacks when the field
    is absent (default: `revert_to_red` on violation, legacy behavior on pass).
  * **Resume from Mid-Phase:** If `session.current_phase` is `JUDGE` or
    `REFACTOR` when invoked, the cycle resumes from that phase via the
    `start_phase` parameter. IDLE / RED trigger a fresh cycle from RED.
* **Queue Drain (`deviate micro run --all`):** **Issue-scoped** task sweep.
  Resolves the active issue from `session.active_issue_id` (falling back to
  branch-derived detection via the `feat/{epic}/{issue}` regex against
  `specs/issues.jsonl`), then dispatches **every PENDING task for that issue**
  sequentially. Each task gets up to **2 retry attempts**
  (`_execute_task_with_retry`, `for attempt in range(2)`) before being marked
  `FAILED` in the issue-scoped `tasks.jsonl`. The pipeline **halts on the first
  failure** (`any_failed = True; break`) and exits with code `1`. If no
  `active_issue_id` is set and the branch cannot resolve an issue, no tasks are
  dispatched. Implements `_run_all` from `src/deviate/cli/micro.py`.
  * **Train Retry Loop (per task):** Inside each task's TDD cycle,
    `_run_tdd_cycle` allows up to **3 train attempts** (`max_train_attempts = 3`)
    when GREEN tests fail or JUDGE returns `COMPLIANCE_VIOLATION`. Each train
    attempt injects `<train_feedback>` from the previous attempt's failure
    output back into the GREEN prompt and re-runs GREEN. Exhaustion raises
    `PhaseFailedError`.
  * **Graphite Integration:** If `.deviate/config.toml` contains
    `graphite = true`, after each successful task the runner invokes
    `gt create -m "feat({TSK}): {description}"` to spin up a stacked branch for
    the next task.
  * **GREEN Failure Diagnostic Payload:** When the GREEN phase raises
    `PhaseFailedError` due to a manifest with `status ∈ {FAILURE, ERROR, FAIL}`
    and empty rationale (the prior `: unknown` symptom), the message includes
    the agent's captured stdout tail — the last 50 lines emitted by the agent
    during the failed invocation, propagated through `_invoke_agent`'s second
    tuple slot. Other phase callsites ignore that slot via `manifest, _ = ...`,
    so the change is local to `_run_green_phase`. Retry cap (2 attempts) and
    halt-on-first-failure semantics are unchanged; this is purely an
    observability improvement for the previously opaque "unknown" failure.
  * **GREEN Stub-PASS Guard (REMOVED):** An earlier revision of this spec
    described a guard that rejected ``status: PASS`` manifests with zero
    observed source changes. That implementation was rolled back:
    deciding whether a task is done is JUDGE's job (the JUDGE prompt's
    edge case table emits ``COMPLIANCE_PASS`` with note ``NO_DIFF`` for
    empty diffs), not GREEN's. GREEN's only invariant is "make tests
    pass"; a feature that already works (e.g. landed in a prior
    session, a docs/rename task) is a legitimate zero-change PASS. The
    field that remains is ``HandoverManifest.files: list[str] | None``
    — declared optionally by the agent and recorded for operator
    cross-check only.
  * **GREEN Failure Diagnostic Payload:** When the GREEN phase raises
    ``PhaseFailedError`` because the agent emitted
    ``status ∈ {FAILURE, ERROR, FAIL}`` and the manifest's ``rationale``
    is empty (the prior ``: unknown`` symptom) the message includes
    the agent's captured stdout tail — the last 50 non-blank lines
    emitted during the failed invocation, propagated through
    ``_invoke_agent``'s second tuple slot on the success path. The
    tail is also surfaced when ``rationale`` is non-empty (the section
    is appended unconditionally to make operator log-grepping
    uniform across phases). Every call to ``_invoke_agent`` returns
    ``(manifest, agent_tail_str)``: the timeout branch returns the
    subprocess partial stdout; the success branch returns the last
    50 non-blank lines from the streaming collector
    (``micro.py::_invoke_agent`` lines ~417-455). RED, REFACTOR, and
    EXECUTE sites adopt the same convention so the four ``or 'unknown'``
    fallbacks all carry the same diagnostic surface.
  * **Dashboard / Output:** Constructs an `OrchestrationMonitor` (in
    `src/deviate/ui/monitor.py`) wired to a `RunBoard`
    (`src/deviate/ui/pipeline.py`) with `total_tasks` set to the pending count.
    The RunBoard renders as a multi-column Rich `Table` whose rows are updated
    in place via the monitor's event stream (`task_started` / `phase_change` /
    `task_completed` / `task_failed`). Output structure:
    * **Run header panel** — `RUN <issue_id> N pending task(s)` in a framed panel.
    * **Per-phase callouts** — Each `RED` / `GREEN` / `JUDGE` / `REFACTOR` /
      `EXECUTE` phase emits a `PhaseCallout` (rounded `╭─╮` panel) with the
      phase tag, task ID, status marker (`◐` in-progress, `●` completed,
      `✗` failed), and elapsed time. The original token-bearing line
      (`RED →`, `GREEN →`, etc.) is preserved alongside for backwards-compat
      with existing tooling.
    * **Train retry indicator** — On each `_run_tdd_cycle` retry, a
      `TrainIndicator` renders the current attempt against the maximum
      (`● 1/3 ─▶─ ◐ 2/3 ─▶─ ○ 3/3`). The literal `TRAIN` token is preserved.
    * **Final RunBoard snapshot** — A full re-render of the board reflecting the
      post-run state of every task (markers + per-row error reasons).
    * **Pipeline summary** — A `PipelineSummary` panel with totals
      (`Total tasks`, `Completed`, `Failed`, `Duration`, `Status`).
    In `--json` mode the same monitor emits JSONL events
    (`task_started`, `phase_change`, `task_completed`, `task_failed`,
    `pipeline_halted`, `pipeline_complete`); the rich board panels are
    suppressed in JSON mode. Agent output is forwarded to the monitor via a
    streaming callback.
* **Input Parameters:**
  * `[task-id]` (Positional: `TSK-NNN-NN` format; omit to auto-select the first
    PENDING task for the active issue; mutually exclusive with `--all`)
  * `--all` (Drain every PENDING task for the active issue)
  * `--profile [full|fast|secure]` (Defaults to `full`):
    * `full` — RED + GREEN + JUDGE + REFACTOR (complete cycle)
    * `fast` — RED + GREEN only (skip JUDGE + REFACTOR)
    * `secure` — RED + GREEN + JUDGE (skip REFACTOR)
    * Boolean flags `--no-judge` / `--no-refactor` retained as composable overrides
  * `--agent <name>` (Override agent backend; falls back to `[agent].backend` in
    `.deviate/config.toml`)
  * `--dry-run` (Print the resolved task and exit without dispatching)
  * `--json`, `--quiet`, `--verbose`

> **Note on the `last_command` field:** When the orchestrator hands off to
> `micro run --all`, the session's `last_command` is rewritten to
> `micro run [task-id] --all` (i.e. the micro subcommand path, not the
> top-level `deviate run`), so the session always records the most
> specific command that last touched it.

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
  * `--no-setup` *(optional, advanced)* — Skip the SPECIFY step entirely (no worktree
    created, no ledger claim written). The pipeline runs in the current directory,
    so `_plan_post` and `_tasks_post` will commit `plan.md` / `tasks.md` to whatever
    branch is currently checked out. The pipeline renders `PLAN ▶ TASKS` in the
    `PipelineBanner` (the `SPECIFY` step is dropped) and prints a yellow `[bold]WARN[/]`
    note above the banner calling out the Git Isolation Principle bypass. Intended for
    ephemeral runs where the operator has already prepared a branch manually; the
    default `deviate meso run` flow remains the canonical entry point that respects
    the worktree-per-issue model.
* **Error Recovery:** Agent non-zero exit (`AgentSubprocessError`) or `manifest.status != "PASS"`
  aborts with `<PHASE>_FAILED`. Re-running the pipeline re-processes plan.md and tasks.md
  (no phase-skip logic); commits are skipped when there are no changes. The
  `UPSTREAM_MISSING` token is **not** emitted by the current implementation.
* **Output:** The pipeline prints a `PipelineBanner` (`src/deviate/ui/pipeline.py`)
  framed opening panel showing `MESO <issue_id> <issue_title>`, the epic / issue
  slugs, and a horizontal step indicator (`SPECIFY ▶ PLAN ▶ TASKS`). On
  completion it prints a `PipelineSummary` (totals + duration + `Status` row)
  followed by a footer line `MESO pipeline complete - session at IDLE`. The
  literal tokens `MESO`, `IDLE`, `DISCOVERED`, `INVOKE_AGENT`, `DRY_RUN`,
  `NO_CLAIMABLE_ISSUES`, `ISSUE_COMPLETED`, `INVALID_ISSUE_ID`, `BLOCKED`,
  `PROGRESS_RESET`, and `<PHASE>_FAILED` are all preserved in the output
  for backwards-compat with existing tooling and the test suite.

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

#### `deviate inspect flows coverage [--release <release.md>]`

* **Source:** `src/deviate/cli/inspect.py` (`flows_coverage_command`)
* **Description:** Read-only query surface that joins three inputs — `specs/_product/flows/index.md` (the flows catalog), `specs/_product/flows.jsonl` (the append-only events ledger seeded by `deviate explore post`), and `specs/issues.jsonl` (for issue linkage) — via `load_flow_coverage()` (`src/deviate/state/ledger.py`) to emit one `FlowCoverage` row per `FLOW-NN` with a populated `drift_flag` drawn from the seven-value taxonomy (`OK`, `STALE_DRIFT`, `ORPHANED_FLOW`, `PROMPT_ONLY_NO_CODE`, `DOC_ARTIFACT_ONLY`, `DOCUMENTED_BUT_NOT_IMPLEMENTED`, `IMPLEMENTED_BUT_UNDOCUMENTED`). Renders a Rich `Table` (Flow ID, Title, Drift Flag, Last Event) — these are STATE 3 surface rows, not banners. The command distinguishes two missing-input states with different remediation, and operators must read the banner to know which case they are in:
  * **STATE 1 — configuration error:** `specs/_product/flows/index.md` is absent. The command emits a `[red]FLOWS_INDEX_MISSING[/]` banner on stderr and exits with code `2`. Remediation: run `/deviate-flows` to populate the catalog before any ledger can be meaningful. The catalog is a hard prerequisite.
  * **STATE 2 — normal first-run:** `flows/index.md` exists but `specs/_product/flows.jsonl` has not yet been seeded (typical on a fresh checkout before the first `deviate explore post` has run). The command emits a `[yellow]NO_FLOWS_LEDGER[/]` banner on stderr, exits with code `0`, and renders an empty Rich table. Remediation: run `deviate explore post` (or any explore cycle) to seed the ledger; "no rows" is the correct answer, not an error.
  * **STATE 3 — live drift:** the ledger is present and the catalog has entries. Every cataloged `FLOW-NN` shows up as a normal table row whose `drift_flag` column carries one of the seven taxonomy values above. No banner — drift surfaces row-by-row.
* **Input Parameters:**
  * `--release <release.md>` (Path to the active release-next Markdown file. When supplied, parses the `Included Flows` table (rows beginning with `| FLOW-`) and narrows the rendered coverage to only those `FLOW-NN` IDs explicitly listed for the release. Header markers and rows with an empty first cell are skipped silently — so the operator sees "what is still incomplete for THIS release" instead of "what is incomplete globally.")
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

#### `deviate walkthrough pre [--base <branch>] [--branch <branch>]`

* **Source:** `src/deviate/cli/walkthrough.py`
* **Description:** Gathers git state and governance context for a human-guided
  architectural walkthrough at HITL Gate 3, complementing `deviate review pre`.
  Computes the unified diff and file list (via `git diff --name-only`) between
  the merge-base of `--base` (default: `main`) and `--branch` (default: `HEAD`),
  resolves governance paths, and collects commit messages for decision traceability.
  Emits a JSON contract for consumption by the walkthrough skill.
* **Input Parameters:**
  * `--base <branch>` (Base branch for merge-base computation; default: `main`)
  * `--branch <branch>` (Target branch for self-contained walkthrough; default: `HEAD`)
* **Output Artifacts:** JSON contract with `diff`, `constitution_path`, `prd_path`,
  `constitution_warning`, `prd_warning`, `base_branch`, `commit_messages`,
  `changed_files`, `changed_files_count`, `timestamp`.
* **Token Budget:** Contract is lighter than review's — no per-file AST parsing.
  The skill reads the raw diff and file list; structured diff is available via
  `deviate review pre` if deeper analysis is needed.

---

#### `deviate walkthrough post <status>`

* **Source:** `src/deviate/cli/walkthrough.py`
* **Description:** Placeholder for future walkthrough summary persistence.
  Currently records the outcome (CLEAN or FLAGGED) with a timestamp.
* **Input Parameters:**
  * `status` (Positional: CLEAN or FLAGGED)
* **Output Artifacts:** JSON contract with `status`, `phase`, `timestamp`.

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
└── logs/                     # Structured run/task logs (CLI-managed; not user-edited)
    ├── run_<UTC>.log         # Per-run chronological event log — every task in the run
    └── <ISSUE_ID>/           # Per-issue directory, one file per task
        └── <TASK_ID>.log     # Per-task transcript: full prompt + agent stdout
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
│   ├── convention.py         # detect_uses_emojis, format_commit_message, TYPE_EMOJI_MAP, PHASE_TEST_EMOJI
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
| `/deviate-walkthrough` | Architectural Walkthrough Guide | (none — conversation only) | `deviate walkthrough pre/post` | 5 steps: gather, sweep, curate, walk (conversational), synthesize |

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



#### SessionState (Pydantic -- `src/deviate/state/config.py`)

| Field | Type | Description |
|-------|------|-------------|
| `current_phase` | Literal | `IDLE`, `RED`, `GREEN`, `JUDGE`, `REFACTOR` (see `_VALID_PHASES`) |
| `active_issue_id` | `str` (optional) | Issue the session is bound to (`--issue` selection survives across `--all` runs) |
| `last_command` | `str` | Last CLI command the user invoked (for resume/messaging) |
| `train_feedback` | `str` | Last failure feedback injected as `<train_feedback>` into the next GREEN prompt |
| `judge_rejected` | `bool` | `True` while the JUDGE verdict on the current cycle is a rejection |
| `pending_judge_action` | `str` (default `""`) | The JUDGE-supplied routing directive (`revert_before`, `revert_to_red`, `continue_refactor`, `skip_refactor`); consumed by `_finish_tdd_cycle` after the JUDGE phase hands off |
| `red_commit_sha` | `str` | SHA of the task's RED commit; anchors `_execute_rollback` (set at end of RED phase) and advances past each feedback commit on `revert_to_red` rejections |
| `timestamp` | `datetime` | Auto-set on each transition (`force_transition_to`/`transition_to` rebuilds) |


#### JUDGE `next_action` Routing Table

`HandoverManifest.next_action` (`src/deviate/core/agent.py`) carries the JUDGE agent's
decision on how to route the runner. Four values, each honored verbatim by
`_run_judge_phase` and the EXECUTE equivalent inside `_run_execute_phase`:

| `next_action` | Required verdict | Runner behavior |
|---|---|---|
| `revert_before` | `COMPLIANCE_VIOLATION` (or any) | Discard this task's GREEN **and** its RED. Reset to `red_commit_sha^` (the parent of the RED commit, defended by a subject-match regex; logs `PRE_RED_AMBIGUOUS` if the parent is not a RED-phase convention). Clear `session.red_commit_sha` so RED re-anchors. Transition to RED with the feedback in `train_feedback`. Used when the test itself is wrong. |
| `revert_to_red` | `COMPLIANCE_VIOLATION` (default on violation when field omitted) | Discard GREEN, preserve RED. Reset to `red_sha`, append a feedback commit past RED, advance `session.red_commit_sha` to that commit. Transition to GREEN with feedback in `train_feedback`. The previous-round feedback commit is preserved so a second rollback only kills the subsequent GREEN. |
| `continue_refactor` | `COMPLIANCE_PASS` (or any) | Skip the rollback (GREEN is intact). Set `pending_judge_action="continue_refactor"`. `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`. |
| `skip_refactor` | `COMPLIANCE_PASS` (or any) | Skip the rollback. Set `pending_judge_action="skip_refactor"`. `_finish_tdd_cycle` marks the task `COMPLETED` and returns to `IDLE`, regardless of `--no-refactor`. |

Unknown `next_action` values are logged (`JUDGE_UNKNOWN_ACTION`) and the runner falls
back to the legacy verdict-based default (rollback on violation, continue on pass).

There is no interactive prompt; the manifest is the source of truth. A future `--judge-action`
CLI flag (operator escape hatch) can override the manifest per-invocation.

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
| `/deviate-walkthrough` | V4 Flash | Single invocation | One-shot |
| `/deviate-adhoc` | V4 Flash | Single invocation | One-shot |
| EXECUTE / E2E / HOTFIX | V4 Flash | Single invocation | One-shot |

The `AgentBackend` class (`src/deviate/core/agent.py`) supports `opencode`, `claude`,
`droid`, and `pi` backends with configurable timeout. Output is parsed as YAML
`HandoverManifest`. Pi uses print mode (`pi -p`) by default and accepts the
`--model <id>` CLI flag (the `provider/model` string from `[models]` is passed
verbatim). RPC mode (`pi --mode rpc --no-session`) is opt-in via `agent.pi_rpc = true` in
`.deviate/config.toml` and streams JSONL events so `pi.session_stats`
(`tokens.input`/`output`/`cacheRead`/`cacheWrite`) can be appended to the
`AGENT_RESULT` event in `.deviate/logs/run_<UTC>.log` (and the per-task
`.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`) for cost observability. See

### 5. DeepSeek V4 Pricing Reference (June 2026)

Cache-hit tokens are billed when a request's prefix matches a previously cached prefix.
The architecture optimizes for cache-hit pricing wherever feasible.

| Model | Cache-Hit Input (1M tokens) | Cache-Miss Input (1M tokens) | Output (1M tokens) | Cache Discount |
|---|---|---|---|---|
| V4 Flash | $0.0028 | $0.14 | $0.28 | 98.0% |
| V4 Pro (discounted) | $0.003625 | $0.435 | $0.87 | 99.17% |

Context length: 1M tokens. See `api-docs.deepseek.com/quick_start/pricing` for current rates.
~85% of all recommended LLM turns target V4 Flash at cache-hit rates.
