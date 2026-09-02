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
  empty `artifacts/` workspace); ensures a symlink relationship between `CLAUDE.md` and
  `AGENTS.md` (via `_linkify_governance_files`); applies governance blocks to the canonical
  file; and installs the DeviaTDD prompt commands. `deviate setup` does **not** scaffold
  `specs/constitution.md` — that bootstrap is owned by `deviate research pre` (see below),
  so a fresh project reports `is_greenfield=true` until `/research` populates the
  constitution. `deviate init pre` continues to scaffold the constitution independently.
  Successful `deviate setup` prints a next-step hint to run `/deviate-init` as the
  first agent prompt (Codex: the `deviate-init` skill) and notes that init is a
  no-op if the repo is already scaffolded.
  slash commands + 1 standalone `tools-mcp-servers` command (for Factory Droid)
  — 25 flat `.md` files total in the Factory install; 24 in every other agent
  `.{agent}/prompts/` for Pi) during `deviate setup`. Commands land only in the
  one agent directory resolved by `_resolve_install_agents` (always a
  one-element list): `.claude/commands/`, `.opencode/commands/`,
  `.factory/commands/`, `.pi/prompts/`, `.omp/prompts/`, or Codex skills under
  `.agents/skills/<name>/SKILL.md`. Leftover agent directories are never
  re-sprayed. `--agent <name>` pins that target without prompting. On a TTY,
  omitted `--agent` always shows a Rich `Prompt.ask` menu of `AGENT_CHOICES`
  (existing `[agent].backend` is the default highlight, not an auto-skip).
  Non-TTY without `--agent` reuses a persisted backend or fail-closes with
  `NO_AGENT_SELECTED`. An unknown `--agent` fails closed and writes nothing.
  Each command is a flat `<name>.md` file (or a Codex `SKILL.md`) with a
  minimal YAML frontmatter (`name:` + `description:`). The selected agent
  (`opencode`, `claude`, `droid`, `factory`, `pi`, `omp`, `codex`) is persisted
  to `[agent].backend` in `config.toml` and is the sole install target.
  `--agent codex` additionally seeds `[models].default = "gpt-5.6-luna"` and
  `[agent].reasoning_effort = "high"` when those keys are missing or empty; a
  user-set `[models].default` or `[agent].reasoning_effort` is left untouched.
  Non-Codex setup does not write Luna or a reasoning key.

  **Single-source prompt derivation:** for each of the 11 overlapping phases
  (`explore`, `research`, `prd`, `shard`, `plan`, `tasks`, `red`, `green`,
  `refactor`, `judge`, `execute`) the installed manual slash-command body is
  derived at install time from the canonical `auto/{phase}.md` middle body plus a
  per-phase manual overlay — it is NOT a hand-maintained duplicate. The derivation
  path is `compose_command_body()` / `install_command()` in
  `src/deviate/core/commands.py`: `install_command` reads the canonical
  `auto/{phase}.md` core, `compose_command_body` splices the platform frontmatter
  and the core/layer/lifecycle-manual/style prefix around it, and the per-phase
  manual overlay (pre/post-script lifecycle steps, rich handover manifest,
  `<context><user_input>` block) is appended from the reduced
  `commands/deviate-{phase}.md` source. `auto/{phase}.md` is the single source of
  truth; the 12 commands-only prompts (adhoc, constitution, e2e,
  hotfix, html, init, merge, pr, prune, review, triage,
  walkthrough) have no auto counterpart and stay hand-maintained. A drift guard
  pins the identical-middle invariant across all 11 phases (see section 2).

  **Constitution embedding is install-mode-dependent:** project-local installs
  bake `<workdir>/specs/constitution.md` verbatim into each prompt (tier 0,
  when the file exists) for parity with the auto path. Global installs
  (`--agent-export-mode global`) never embed a constitution — the prompt is
  project-agnostic and shared across every repo, so the core block's
  Constitution Compliance Mandate (invariant #10) directs the agent to read
  `specs/constitution.md` at runtime instead.
  manual overlay (pre/post-script lifecycle steps, rich handover manifest,
  `<context><user_input>` block) is appended from the reduced
  `commands/deviate-{phase}.md` source. `auto/{phase}.md` is the single source of
  truth; the 12 commands-only prompts (adhoc, constitution, e2e,
  hotfix, html, init, merge, pr, prune, review, triage,
  walkthrough) have no auto counterpart and stay hand-maintained. A drift guard
  pins the identical-middle invariant across all 11 phases (see section 2).
  **Agent-to-commands-directory mapping:** `.claude/` → `.claude/commands/`;
  `.opencode/` → `.opencode/commands/`; `.factory/` (shared by both `--agent
  factory` and `--agent droid` — the Factory Droid IDE owns that directory;
  `droid` is the underlying backend binary both user-facing names dispatch to,
  so there is no `.droid/commands/`) → `.factory/commands/`; `.pi/` →
  `.pi/prompts/` (Pi discovers slash commands from `<workdir>/.pi/prompts/*.md`
  per the platform's documented convention; DeviaTDD file-copies the project
  command vault `src/deviate/prompts/commands/<name>.md` into
  `<workdir>/.pi/prompts/<name>.md`, so the project vault remains the single
  source of truth. In project-local mode DeviaTDD does **not** write to
  `~/.pi/agent/` and does **not** generate a `settings.json` — model/provider
  selection is the operator's responsibility via Pi's own configuration
  mechanism); `.omp/` →
  `.omp/prompts/` (OMP is an extensible wrapper around the Pi executor; it
  discovers slash commands from `.omp/prompts/`). All five command
  directories are excluded from version control via the project-root
  `.gitignore` (see `_ensure_root_gitignore` at `src/deviate/cli/__init__.py:905`),
  which also ignores `.deviate/` and `.worktrees/` by default.
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
* **Agent Selection:** Accepts `--agent [claude|opencode|droid|factory|pi|omp|codex]` to pin
  the install target and persisted backend without prompting. On a TTY, omitted `--agent`
  always shows a Rich `Prompt.ask` menu of `AGENT_CHOICES` (existing `[agent].backend` is
  the default highlight, not an auto-skip). Non-TTY without `--agent` reuses a persisted
  backend or fail-closes with `NO_AGENT_SELECTED` and a directive to re-run with `--agent`.
  Install is always exactly one agent; leftover `.claude/` / `.opencode/` / … dirs are
  never a fan-out target. On a TTY the remaining prompts are, in order: prompt/skill
  install `[l]ocal/[g]lobal` (default `l`; this-run only, not persisted),
  claim-remote `[y]es/[n]o`, then the
  optional-pack checkbox. `global` installs commands/skills under the user-level
  tree. Pi's global prompt templates live at `~/.pi/agent/prompts/` and its
  global skills at `~/.pi/agent/skills/` (per `pi@latest` `getPromptsDir()` /
  `getAgentDir()`); the other agents use `~/.{agent}/commands|prompts` +
  `skills` (Codex `~/.agents/skills`); `local` stays project-local.
* **Optional pack selection:** `--packs none|all-optional|<comma-separated names>` selects
  optional command packs for scripts. Default layer packs are the three execution layers
  (`macro` + `meso` + `micro`, including `/deviate-init`). On a TTY, omitted `--packs`
  shows a Rich checkbox list (one pack per row: `merge`, `pr`, `review`, `walkthrough`,
  `html`, `hotfix`, `triage`, `prune`, `e2e`). Space toggles; Enter confirms; default is
  nothing selected (execution layers only). The slash-separated `Prompt.ask` list is
  not used. Non-interactive sessions skip the prompt and install default-only.
  `--packs all-optional` includes every individual extra. Pack picks are not written
  to `config.toml`.
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
  * `--agent-export-mode [local|global]` (Omitted on a TTY prompts `[l]ocal/[g]lobal`,
    default `l`. Applies to this run's install only — the key is not written.
    Non-TTY omitted installs local. Explicit flag skips the prompt.)
  * `--base-branch <name>` (Optional script write-override. Omitted does not
    write `base_branch`; runtime uses `resolve_base_branch`: hand-set key,
    else `origin/HEAD`, else `main`. A hand-set key is not stripped on re-run.)
  * `--agent [claude|opencode|droid|factory|pi|omp|codex]` (Pin install target and persisted backend)
  * `--packs none|all-optional|<comma-separated optional names>` (Scripted optional-pack
    selection; omitted on a TTY shows the checkbox list, default nothing selected)
  * `--libref` (Force-enable `libref` CLI integration; merges `use_libref = true` into
    `config.toml`)
  * `--claim-remote` (Enable push-as-lock; merges `claim_remote = true` into
    `config.toml` without dropping `[models]`, `timeout_seconds`, or `[agent]`.)
  * `--no-claim-remote` (Disable push-as-lock; merges `claim_remote = false` into
    `config.toml` without dropping `[models]`, `timeout_seconds`, or `[agent]`.
    Fresh setup without either flag writes `claim_remote = false`. On a TTY with
    the flags omitted, setup always prompts `[y]es/[n]o` (including re-runs); default
    is the current file value (`y` if `claim_remote = true`, `n` if false or
    missing). Accepts `y`/`n`/`yes`/`no`. The answer is upserted. A non-interactive
    session does not prompt: fresh
    config writes `false`; an existing file is left alone unless a flag was passed.)
* **Output Artifacts:**
  * `.deviate/config.toml` — Runner configuration only (`profile`,
    `timeout_seconds`, `claim_remote`, `[agent].backend`,
    plus `transport` for pi/omp). Inline comments sit on the same line as
    each key. Does not persist `agent_export_mode`, `base_branch`, or
    `[agent].timeout`. `resolve_base_branch` reads a hand-set `base_branch`
    if present, otherwise `origin/HEAD`, otherwise `main`.
    Codex setup also seeds
    `[models].default = "gpt-5.6-luna"` and `[agent].reasoning_effort = "high"`
    when missing/empty so spawned `codex exec` receives `--model gpt-5.6-luna`
    and `-c model_reasoning_effort=high` without a repo-wide `.codex/config.toml`.
  * `.deviate/session.json` — Current session state snapshot
  * `.deviate/.gitignore` — Excludes session.json and runtime state
    directories from version control
  * `<workdir>/.gitignore` — Updated with five concise DeviaTDD
    exclusions: `*/commands/deviate-*.md`,
    `*/prompts/deviate-*.md` (covers every supported agent directory
    — ``.claude/commands/``, ``.opencode/commands/``,
    ``.factory/commands/``, ``.pi/prompts/`` — and any future agent
    that follows the same flat-file convention), `*/skills/deviatdd/`,
    `.worktrees/`, and `.deviate/`. The single-level
    ``*/`` prefix is deliberate: a broader ``**/deviate-*.md`` would
    silently ignore the deviatdd project's own command sources at
    ``src/deviate/prompts/commands/deviate-*.md`` (three directories
    deep) and break ``deviate setup`` in this repo itself.
  * `specs/constitution.md` — Resolved boilerplate constitution
  * `AGENTS.md` — Symlink to `CLAUDE.md` (or vice-versa if only `AGENTS.md`
    existed pre-setup). Created by `_linkify_governance_files`; idempotent.
    Fresh `CLAUDE.md` is empty (governance seeds are empty); an empty pair
    after setup is expected. First-hour README points at `/deviate-init`;
    the research rationale lives in `docs/rationale.md`.
    When `export_mode=global`, setup prints the command dest path on the
    `INSTALL N commands → <agent>` line (same dest style as the skill
    INSTALL line).
  * Selected-agent command install only: `.claude/commands/`,
    `.opencode/commands/`, `.factory/commands/`, `.pi/prompts/`,
    `.omp/prompts/`, or `.agents/skills/<name>/SKILL.md` for Codex.
    Factory also receives the standalone `tools-mcp-servers` command.

#### `deviatdd` Skill (Project-Local Single Skill)

* **Source:** `src/deviate/prompts/skills/deviatdd/SKILL.md`
  (package resource, loaded via `importlib.resources`).
* **Installer:** new `_install_deviatdd_skill(workdir, agents)` +
  `_get_agent_skill_dir(workdir, agent)` + `_resolve_skill_source()` in
  `src/deviate/cli/__init__.py`, called from `setup()` after
  `_install_commands_to_agents(...)`. Idempotent (content-equality skip
  mirrors `install_command`'s contract).
* **Install targets (resolved install agents):** the skill is written
  to `<workdir>/.<agent>/skills/deviatdd/SKILL.md` for the single agent
  in `_resolve_install_agents` — always a one-element list of the
  `--agent` pin or the TTY/persisted selection. Leftover agent
  directories are never a fan-out target. Mirrors
  `_install_commands_to_agents`. An unknown `--agent` fails closed.
  * `claude` -> `<workdir>/.claude/skills/deviatdd/SKILL.md`
    (verified — same form as user-level `~/.claude/skills/<name>/SKILL.md`).
  * `opencode` -> `<workdir>/.opencode/skills/deviatdd/SKILL.md`
    (no documented project-local skills convention; file on disk for
    forward-compat).
  * `factory` -> `<workdir>/.factory/skills/deviatdd/SKILL.md`
    (same as opencode; `--agent droid` uses this path).
  * `pi` -> `<workdir>/.pi/skills/deviatdd/SKILL.md`
    (verified — `pi@latest` docs at
    `packages/coding-agent/docs/skills.md` list `.pi/skills/` as a
    project-local skill discovery path; global mode writes
    `~/.pi/agent/skills/deviatdd/SKILL.md`).
  * `omp` -> `<workdir>/.omp/skills/deviatdd/SKILL.md`
    (libref documents omp skills at user-level
    `~/.omp/agent/managed-skills/<name>/SKILL.md` and via a
    settings-driven `skills` array; operators can register the
    project-local file via OMP's settings).
  * `codex` -> `<workdir>/.agents/skills/deviatdd/SKILL.md`
    (Codex CLI 0.117+ official project-local discovery). Each packaged
    slash command is also installed as `.agents/skills/<name>/SKILL.md`.
* **Scope:** Unified Meso and Micro orchestration. The skill first runs
  `deviate meso run`. In an existing feature worktree, the runner validates
  `plan.md` and `tasks.md`, skips completed phases, and resumes at Tasks when
  only Plan is ready. Invalid existing artifacts stop without overwrite.
  After Meso succeeds, the skill runs bare `deviate micro run` one task at a
  time and keeps the existing failure-triage and clean-slate safety flow.
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
  `INVOKE_AGENT` (short line: `task_id=`, `phase=`, `backend=`,
  `model=` — no prompt body), `AGENT_RESULT`
  (summary: `status=`, `verdict=`, `next_action=` when present —
  not the full manifest JSON), `AGENT_TIMEOUT` (carries `error=`, `partial_stderr=`, and
  `partial_stdout=`; harness verdict for a hung RED or hung GREEN), `AGENT_ERROR`, `AGENT_NOT_AVAILABLE`,
  `JUDGE_REJECTED`, `JUDGE_AGENT_NO_FEEDBACK`,
  `JUDGE_REFACTOR_NOTE` (carries `note=`, the refactor hint),
  `TASKS_MD_NO_MATCH`, `TASKS_MD_FEEDBACK`, `TASKS_MD_SKIP`,
  `FEEDBACK_COMMIT_FAILED`, `POST_CMD_FAILURE` (carries
  `uncommitted_count=` and `files=`, the dirty files the hook
  refused — NOT `returncode=` / `stderr=`),
  `CYCLE_END` (emitted when a task leaves `_run_tdd_cycle` —
  complete, fail, or skip; carries `task_id=`, `completed=`,
  `phase_decisions=` (PHASE_DECISION `action=` values in order
  this run), `reject_count=`, `last_blast=` (`red` / `green` /
  `none`), `max_streak=`), `LOOP_DETECTED` (same-blast reject
  streak >= 2; carries `blast=` and `streak=`).
  Transcripts are for diagnosis, not a dump: verbatim agent stdout
  and the prompt body live in
  `.deviate/logs/<ISSUE_ID>/<TASK_ID>.raw/<phase>-<n>.log` (optional
  `<phase>-<n>.prompt.log`), not in the run/task transcript.
  **Per-task JUDGE postmortem** (structured JSONL, not the
  transcript format): `.deviate/logs/<ISSUE_ID>/<TASK_ID>.verdicts.jsonl`.
  One JSON object per JUDGE application (pass and reject), written
  from `_apply_judge_verdict` so auto and `judge post` share it.
  Fields: `ts` (UTC ISO), `task_id`, `issue_id`, `verdict` (raw),
  `next_action` (after coerce / GH-149 / GH-158), `next_action_raw`
  (agent-declared; empty if omitted), `coerced` (bool),
  `blast` (`red` / `green` / `none` — `revert_red` → red,
  `revert_green` → green, forward/pass → none), `feedback` (the
  reason string actually used), `feedback_source`, `violations`
  (category strings, else `[]`), `test_integrity` (from
  `evaluation` if present, else `null`), `failure_kind` (session
  at judge time), `streak` (consecutive same-blast rejects on this
  task), `loop` (`true` when `streak >= 2`). On a revert that rolls
  back: `head_sha` (HEAD before reset), `reset_to` (blast-radius SHA),
  `recovery_ref` (`tmp/deviate-agent-work/<task>/attempt-<N>`, empty
  when HEAD already equaled the boundary). When the cycle leaves, one
  `{"event":"cycle_end", ...}` object is appended to the same
  file with `completed`, `phase_decisions`, `reject_count`,
  `last_blast`, and `max_streak`. Do not put the full prompt or raw
  agent stdout in this file. Local file only — no dashboard, no
  `inspect postmortem`, no upload.
  **`[log].agent_reasons`** (`.deviate/config.toml`, default
  `false`): when `true`, assembled auto/manual phase prompts gain a
  short block asking for a one-line handover `rationale` (especially
  JUDGE `revert_red` vs `revert_green`). When `false`, prompts must
  not mention logging, `deviate log`, or writing a reason file.
  Setup does not write this key. Pre/post/runner logging never
  checks the flag.
  Skill frontmatter version is `3.0.0`. The drift-check test
  `test_deviatdd_skill_troubleshooting_section_matches_logger` parses
  `micro.py` for `_log_run("<NAME>", ...)` calls and asserts every
  backticked event name in the Troubleshooting section is a real
  emitted event — guards against invented event names. Per-event
  field schemas are documented in `micro.py`, not duplicated here.
* **`.gitignore` exclusions:** `_ensure_root_gitignore` adds
  `*/skills/deviatdd/` to the entries tuple alongside
  `*/commands/deviate-*.md` and `*/prompts/deviate-*.md`. The
  single-level wildcard covers every selected-agent skill install
  (`.claude/`, `.opencode/`, `.factory/`, `.pi/`, `.omp/`, `.agents/`)
  with one pattern. `*/skills/deviate-*/` covers Codex per-command
  skill dirs. The entries tuple also carries `.worktrees/` and
  `.deviate/` so per-project runtime state is untracked by default
  for new consumer setups. The single-level prefix (`*/`, not `**/`) is critical: it
  scopes the pattern to the project root, never matching the
  source-of-truth at `src/deviate/prompts/skills/deviatdd/` (three
  directories deep).
* **Tests:** `TestInstallDeviatddSkill` in `tests/test_cli/test_init.py` and
  `TestSetupSelectedAgentIsolation` / `TestSetupCodex` /
  `TestSetupPerAgentInstall` in `tests/test_cli/test_setup.py` cover
  selected-agent-only install (TTY pick / `--agent` pin; leftover dirs are not sprayed), Codex skills +
  `backend = "codex"`, Luna + `reasoning_effort = "high"` upsert
  (fresh, existing, no-clobber),
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

#### `/deviate-shard` (Macro Layer)

* **Objective:** Decomposes the PRD into standalone, testable issue files.
* **Granularity Guidelines:**
  * **Target:** as few independently shippable user-visible verticals as the PRD needs; no fixed minimum or maximum
  * **Each issue must be a vertical slice:** Delivers a complete, testable behavior end-to-end
  * **Independence:** Each issue should be independently implementable and testable
  * **Scope bounds:** No issue should require <1 task or >10 tasks
  * **Testability:** Each issue must have clear acceptance criteria
  * **Enforcement:** The shard prompt owns all slicing rules. Pass 1 slices by observable behavior, not by FR. Pass 1.5 confirms independent verticals without a count cap. Pass 3.5 merges only invalid horizontal splits or artifact-dependent slices. The PRD prompt owns FR/AC/AO traceability and does not prescribe topology.

---

### 2. Macro Layer: Feature Scoping (pre/post)

All macro-layer commands follow the `pre`/`post` subcommand pattern (except `init`).
Every `pre` subcommand accepts `--json` (emit JSON contract to stdout) and `--quiet`
(suppress diagnostic output).

**Active Domain Discipline** is enforced at HITL gates: the macro phases that interact with the human (`/deviate-research` Gate 1, `/deviate-prd` Ambiguity Interrogation) actively term-challenge against the upstream glossary, sharpen fuzzy language, stress-test with concrete edge-case scenarios, and update the relevant artifact (`design.md`, `data-model.md`, `prd.md`) inline as terms resolve — not as a passive sign-off step.

#### `deviate explore pre <problem> [--slug]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Allocate a feature bucket and register a scratch ledger entry. On a
  non-greenfield project (constitution present), validates the constitution. Transitions
  session to EXPLORE, allocates the bucket via `allocate_feature_bucket()`, appends a DRAFT
  issue record, and emits a JSON contract to stdout (spec_target, feature_dir, issue_id,
  `is_greenfield`, etc.). For an unnumbered slug, `allocate_feature_bucket()` sets the next
  epic number to `max(local numbered specs dirs ∪ remote feat/<NNN>-* prefixes) + 1` from
  already-fetched `refs/remotes/origin/feat`. A numbered slug such as `005-acceptance-gates`
  stays idempotent. Local-only unpushed feat branches do not reserve. On a **greenfield**
  project (no `specs/constitution.md`), `_validate_constitution` is skipped — the contract
  reports `is_greenfield=true` so the downstream `/research` phase knows to bootstrap the
  constitution.
* **Common Flags:** `--json`, `--quiet`

#### `deviate explore post`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validate `explore.md` output. Reads the artifact, validates required
  sections via `validate_artifact()`, runs pre-commit hooks, commits with `docs({NNN}):
  create explore.md`, and saves the session.

#### `deviate research pre [<epic>]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Validates that `specs/explore/<slug>.md` exists. If `specs/constitution.md`
  is missing, bootstraps it from the `constitution_seed.md` package resource (the macro
  layer owns the placeholder scaffold — `deviate setup` does NOT touch the constitution),
  then validates the freshly-scaffolded constitution. **Moves** the explore artifact into
  the new numbered epic directory at `specs/{NNN}-<slug>/explore.md`, transitions session
  to RESEARCH, and emits the JSON contract (`explore_md_path` pointing at the moved
  location, `design_target`, `data_model_target`, `is_greenfield`, etc.).
  `specs/explore/<slug>.md` is removed on success — there is no orphan staging copy.
* **Common Flags:** `--json`, `--quiet`

#### `deviate research post`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Discovers the active epic slug, validates that `explore.md`, `design.md`, and `data-model.md` all exist inside the numbered epic directory (the explore.md artifact must have been moved here by `deviate research pre` — `specs/explore/<slug>.md` is no longer the canonical location), runs `git ls-files --error-unmatch` on the source path persisted by `research_pre` on `SessionState.research_explore_source`, then commits **all four state changes** in a single atomic commit: `git add`s the moved `explore.md`, `design.md`, and `data-model.md`; `git rm`s the original `specs/explore/<slug>.md` (git's rename detection usually surfaces this as an `R100` rename line in `git show`); also includes `constitution.md` if it was created or modified during greenfield bootstrap. The commit message is `docs({epic}): add research artifacts (explore.md, design.md, data-model.md)`. When `research_pre` never ran (manual escape hatch), the source-path field is empty and only `design.md` + `data-model.md` are committed — same behavior as before the move-atomicity fix.

#### `deviate prd pre [--dry-run]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Discovers the active epic slug, validates that `explore.md`, `design.md`, and `data-model.md` all exist inside the numbered epic directory (the explore.md artifact must have been moved here by `deviate research pre` — `specs/explore/<slug>.md` is no longer the canonical location), transitions session to PRD (or dry-run), and emits a JSON contract that includes `explore_md_path` pointing at `specs/{NNN}-<slug>/explore.md`.
* **Common Flags:** `--json`, `--quiet`

#### `deviate prd post <manifest>`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Loads the manifest JSON, validates `prd.md` sections against
  `ARTIFACT_VALIDATORS`, checks FR requirement traceability with `extract_prd_requirements()`,
  runs pre-commit hooks, commits, and saves session.

#### `deviate shard pre [--dry-run]`

* **Source:** `src/deviate/cli/macro.py`
* **Description:** Discovers epic, validates `prd.md` exists, computes the next issue ID,
  transitions session to SHARD, and emits JSON contract with `next_issue_id`. Numbered epics
  emit `<epic-prefix>-<ordinal>`. Adhoc emits `ISS-NNN`. Next `NNN` is `max(ordinals) + 1`
  over the current `specs/issues.jsonl`, the `origin/<base_branch>:specs/issues.jsonl` blob
  when present, and already-fetched remote `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*` refs.
  `ISS-ADH-NNN` and `ISS-NNN` share one adhoc series. Local-only unpushed feat branches do
  not reserve.
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
  single vertical-slice issue. The `/deviate-adhoc` compiler and `_compute_next_issue_id`
  share one remote-aware rule: next `NNN` is `max(current ledger, origin ledger, remote
  feat/adhoc/<NNN>-*) + 1`. `ISS-ADH-NNN` and `ISS-NNN` share that series. Local-only
  unpushed feat branches do not reserve.
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

> **Deprecated:** Standalone Specify no longer owns acceptance criteria. PRD/shard/adhoc emit `AO-NNN` acceptance outlines; `deviate plan` writes the authoritative `AC-PLAN-NNN` Gherkin contract after fresh research.

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

#### `deviate specify [<issue-id>] [--local] [--branch <name>]` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Claim an issue and create its worktree. With an explicit `<issue-id>`,
  claims that specific issue. With **no argument**, auto-discovers the next claimable
  BACKLOG issue via `_discover_claimable_issue()` (the same discovery `deviate meso run`
  uses) and claims it. Default discovery skips issues whose `feat/{epic}/{issue}` branch
  already exists on remote (treated as claimed elsewhere). In any mode it also skips
  issues whose `feat/{epic}/{issue}` branch already has a local worktree (treated as claimed
  here) — that local-worktree guard is what lets two parallel terminals claim two different
  BACKLOG issues without re-claiming the same one. Local mode does not skip those
  origin branches. Stops after the worktree is created and the claim is committed — does
  NOT advance session state and does NOT run plan or tasks. To continue, run
  ``deviate plan pre`` or invoke the ``/deviate-plan`` slash command inside the new
  worktree.
* `--local`: claim the issue locally only. Creates the worktree, writes the CLAIM row, and commits. Skips the remote-branch pre-check and `git push`. If the local branch `feat/<epic>/<slug>` already exists, returns success with `ALREADY_CLAIMED_LOCAL` and reuses the existing worktree (no ledger re-write). Useful for air-gapped or no-remote workflows. Tradeoff: local branch is the only claim signal, so a manual `git checkout -b feat/<epic>/<slug>` will also short-circuit as already-claimed. Omitted `--local` honors `.deviate/config.toml` `claim_remote` (default `false`; absent file or absent key resolves to `false`). Explicit `--local` always wins over `claim_remote = true`. Existing `claim_remote = true` configs still push. Local mode is distinct from `--no-setup`: it still creates the worktree and writes the ledger claim. When push-as-lock is on (`claim_remote = true`, no `--local`) and `git push` of `feat/<epic>/<NNN>-*` or `feat/adhoc/<NNN>-*` is rejected because the name exists, `_try_claim_issue` increments the ordinal and retries the push, at most 3 times. Collision retry does not set `--local`. Non-name-collision push errors still print `PUSH_STDERR` and follow `--force` or rollback.
* `--branch <name>` / `--base <name>`: use the named branch as the start point for the new worktree. If omitted, use the current branch.

#### `deviate plan pre [--issue <id>] [--dry-run]`

* **Source:** `src/deviate/cli/meso.py` (`_plan_pre`)
* **Description:** Per-issue localized research phase with two operating modes:
  * **Outside a linked worktree:** auto-discovers or uses `--issue`, creates/claims the worktree through `_specify_pre`, force-transitions to PLAN, and syncs `.deviate/`.
  * **Inside a linked worktree:** accepts SPECIFY or PLAN, resolves `record.source_file`, parses `## System Topology Mapping`, and emits `issue_id`, `spec_path`, `plan_target`, `worktree_full`, `branch_name`, and constitution paths. The issue is resolved from `session.active_issue_id`, falling back to a branch-derived lookup via the `feat/{epic}/{issue}` regex against `specs/issues.jsonl` so a fresh worktree with an empty session still targets the branch's own issue.
* **Acceptance ownership:** The issue supplies stories, scope, topology, `AO-NNN` outlines, edge cases, and performance constraints. Plan reconciles each outline into complete `AC-PLAN-NNN` scenarios with Source Outline, upstream traceability, current-code evidence, and Given/When/Then. This contract is authoritative for Tasks, RED, and JUDGE.
  * **Per-scenario required fields** (every `AC-PLAN-NNN` MUST contain all five):
    1. **Scenario header** — `**Scenario AC-PLAN-NNN: <observable behaviour, imperative present tense>**`. Sequential, zero-padded, unique.
    2. **Source Outline** — `**Source Outline**: \`AO-NNN\`[, \`AO-MMM\`…]`. MUST be a literal AO token literally present in the issue's `## Acceptance Outline`. A comma-separated list is allowed for cross-cutting scenarios.
    3. **Upstream Traceability** — `**Upstream Traceability**: \`US-NNN-NN\`, \`FR-NNN-ID\`, \`AC-NNN-ID-NN\`. At minimum one `US-`, one `FR-`, and one `AC-` token, comma-separated, drawn from the issue's `## Upstream Requirement Tracing` and `## User Stories Ledger`.
    4. **Current-Code Evidence** — `**Current-Code Evidence**: \`<relative path>:<symbol or line>\``. At least one concrete path reference grounded in the codebase scan.
    5. **Given / When / Then** — exactly three bold-labelled clauses in this order: `**Given**:`, `**When**:`, `**Then**:`. Each clause is a single imperative sentence and MUST NOT embed additional `**Given**` / `**When**` / `**Then**` markers. The `**Then**` clause MUST state a verifiable observable outcome.
  * **Required sections in canonical order**: `## Plan Summary` → `## Acceptance Contract` → `## Workstation Mapping` → `## Implementation Strategy` → `## Data Flow Analysis` → `## Risk Assessment` → `## Security Profile` → `## Integration Points` → `## Constitutional Alignment`.
  * **Acceptance Coverage Invariant:** Every AO from the issue's `## Acceptance Outline` MUST appear as the Source Outline of at least one AC-PLAN scenario. Behavioural coverage that does not map cleanly to a single AO (e.g. an HMAC failure, an RLS isolation invariant, a defensive boundary) belongs under an existing AO's Error Category or Boundary Category. If no existing AO fits, the issue's outline is incomplete — halt with `INCOMPLETE_ISSUE_OUTLINE` and request that shard/adhoc regenerate the issue.
  * **Forbidden patterns** (any one triggers `PLAN_ACCEPTANCE_CONTRACT_INVALID` from `deviate plan post`): Source Outline labelled `Edge Cases`, `Boundary`, `Constitutional §…`, `RLS`, `Tenant Isolation`, `Hardening`, `Security`, or any non-AO string; missing `**Source Outline**` / `**Upstream Traceability**` / `**Current-Code Evidence**` / any of `**Given**` / `**When**` / `**Then**`; a repeated or illegal `**Verification Mode**: <automated|manual|deferred>` literal (a scenario MUST carry exactly one legal mode line; an empty or non-alphabetic value is treated as missing); an issue AO not used by any AC-PLAN scenario; duplicate or non-sequential `AC-PLAN-NNN` identifiers; wrapping the plan body in any XML tag / code fence / preamble. A *missing* mode line is not a stopping error: the meso gates auto-fill the default `automated` value into the scenario body (see `deviate plan post`). The validator lives at `src/deviate/core/validation.py::validate_acceptance_contract`; the repair helper is `repair_missing_verification_mode`.
* **Input Parameters:** `--issue`, `--force`, `--dry-run`; common `--json` / `--quiet` wrappers apply.
* **Session:** force-transitions to PLAN with `active_issue_id` set.

#### `deviate plan post [--force] [--issue-id]`

Validates plan.md exists, is non-empty, and contains a valid Acceptance Contract; auto-renders HTML when changed, commits with convention-aware messaging, and transitions to TASKS. Missing/malformed contracts fail as `PLAN_ACCEPTANCE_CONTRACT_MISSING` / invalid contract diagnostics. When the contract fails *only* because scenarios lack the `**Verification Mode**:` line, the gate auto-fills `automated` into each affected scenario body, persists the repaired `plan.md` (`PLAN_MODE_REPAIR` banner), and proceeds; an existing invalid or duplicated mode literal still blocks with `PLAN_ACCEPTANCE_CONTRACT_INVALID`.

#### `deviate tasks pre [--force] [--dry-run]`

* **Source:** `src/deviate/cli/meso.py`
* **Two-source input:** `spec_path` supplies macro intent; `plan_path` supplies strategy and authoritative scenarios. Plan wins over legacy issue/spec Gherkin.
* **Contract:** detects worktree/branch, resolves constitution commands, and emits `spec_path`, `plan_path`, `tasks_target`, worktree metadata, status, and flags. The issue is resolved from `session.active_issue_id`, falling back to a branch-derived lookup via the `feat/{epic}/{issue}` regex against `specs/issues.jsonl`.
* **Plan digest:** TASKS receives a bounded 16 KiB UTF-8 `plan_digest` plus `plan_path`; truncation inserts `PLAN_DIGEST_TRUNCATED`, requiring a full read.
* **Validation:** reports PLAN_NOT_FOUND, PLAN_ACCEPTANCE_CONTRACT_MISSING, or PLAN_ACCEPTANCE_CONTRACT_INVALID; no Gherkin fallback. A contract that fails only for a missing `**Verification Mode**:` line is auto-repaired in place (default `automated`) before the status is computed.
* **Common Flags:** `--json`, `--quiet`.

#### `deviate tasks post [--force] [--issue-id]`

Validates tasks.md exists and is non-empty, commits it, and transitions session to IDLE. There is no human-approval step between Tasks and Micro — the system auto-advances. Tasks map work to `AC-PLAN-NNN` scenario IDs.

#### `deviate run [--issue] [--force]`

Runs setup → Plan → Tasks and chains into `deviate micro run --all` to drain the task queue. There is no human-approval step between meso and micro — the system never blocks on human approval. The former Micro-related flags (`--profile`, `--no-judge`, `--no-refactor`, `--agent`, `--json`) are removed; use them on `deviate micro run` directly if you only want to drain pending tasks.

#### `deviate tasks <issue-id>` (Legacy)

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Direct positional-argument interface. Generates a single `TaskRecord`
  with `TSK-{NNN}-{NN}` id, appends to `tasks.jsonl`, transitions through TASKS -> IDLE.

#### `deviate pr pre`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Loads session (TASKS), resolves active issue, gathers git state via
  `gather_git_state()`, derives PR metadata (title, body, base_branch), and emits JSON
  contract with branch_name and PR details.

#### `deviate pr run --body-file <path> [--merge] [--auto-merge] [--no-pr] [--platform github|gitlab]`

* **Source:** `src/deviate/cli/meso.py`
* **Description:** Appends the COMPLETED transition to `issues.jsonl`, stages and commits it
  with the PR body, pushes the branch, then optionally opens a PR/MR. Platform is detected
  from the `origin` remote hostname (`github` → `gh pr create`; `gitlab` → `git push`
  `-o merge_request.create` push options). `--merge` / `--auto-merge` apply to GitHub only.
  `--no-pr` marks COMPLETED and pushes without opening a PR/MR.
  `--platform` forces `github` or `gitlab`.
  No Graphite path exists.
---


---

#### `deviate merge [pre] [--issue <id>] [--stage-only] [-m <msg> ...] [--delete-branch] [--delete-worktree]`

* **Source:** `src/deviate/cli/meso.py` (`_merge_pre`, `_merge_run`)
* **Description:** `deviate merge pre` emits a JSON contract with `base_branch` resolved
  from `resolve_base_branch` (hand-set `config.toml` key, else `origin/HEAD`, else
  `main`). The
  `/deviate-merge` skill uses that value as the squash target. The run path (no `pre`
  argument) marks an issue COMPLETED in the ledger with a full Pydantic-validated
  `IssueRecord`.  Two-phase squash-merge flow used by the `/deviate-merge` slash command:

  - `--stage-only` writes the COMPLETED transition to `specs/issues.jsonl` and `git add`-s
    it, but does NOT commit.  The caller is expected to fold this into a squash-merge
    commit.  When called a second time (e.g. after the user has already staged the
    ledger), the transition write is idempotent — `LEDGER_IDEMPOTENT` is printed and
    the function proceeds to the commit step instead of short-circuiting.
  - `-m <subject> -m <body> ...` performs the combined commit: `git add -A` picks up
    the staged feature changes, the first `-m` is routed through `format_commit_message`
    (which detects the project's emoji convention from
    ``CONTRIBUTING.md`` / ``.commit-convention.md`` and prepends the matching gitmoji),
    remaining `-m` values are passed verbatim as body paragraphs. The `/deviate-merge`
    skill mandates reading the convention file before drafting the subject (see
    `commit_message_generation` Step 0) so the operator can confirm or override the
    detected convention in the confirmation step.
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
    recoverable from the base branch alone.
  - `--delete-worktree` removes the worktree at `cwd` if the current directory is itself
    a linked worktree for the issue.

  The function is fully idempotent: re-running with no staged work prints
  `LEDGER_UNCHANGED` and exits cleanly without leaving stray commits.

- **`/deviate-merge` push behavior (v2.4.0):** after the squash-merge commit lands on
  `{base_branch}`, the slash command runs an inline copy of `.githooks/pre-push` (lint +
  format-check + testmon-driven affected tests, with the warm-cache / full-suite
  fallback) as a `push_gate` step, then asks the operator whether to `git push` (which
  fires the real `pre-push` hook and re-runs the gate) or stop and push manually. The
  gate body must stay byte-equivalent to `.githooks/pre-push` — divergence is pinned by
  `tests/test_meso/test_auto_prompt_templates.py::TestMergePromptPushGate::test_hook_and_prompt_agree_on_gate_body`.
  The squash-merge commit and the ledger transition inside it are durable on `{base_branch}`
  regardless of the push outcome; only the network push is opt-in. Failure states:
  `Push_Gate_Failed` (gate non-zero), `Push_Failed` (`git push` non-zero, raw stderr
  surfaced), `Push_Deferred` (user chose "Stop — I'll push manually").


---

### 4. Micro Layer: TDD Sandbox (Manual Phase Commands)
All micro-layer commands follow the `pre`/`post` subcommand pattern. Every `pre` subcommand
accepts `--json` and `--quiet`. `pre` emits a JSON contract describing the environment.
`post` runs validation, ledger updates, and git commits.

**Auto this-task card (GH-150):** Auto `_build_auto_prompt` for `red`, `green`,
`judge`, and `refactor` injects **this task's** markdown card from `tasks.md`
as `{task_content}` — the `TSK-NNN-NN` bullet and its body until the next
task bullet or heading. Sibling cards are never included. Plan, issue spec,
data-model, PRD, constitution, and the JUDGE `<diff>` stay as they are
(those are not other tasks). `{task_content}` is the card, not the ledger
JSON row. JUDGE still receives the GH-118 Judge-Feedback-stripped card so
prior-round `**Judge Feedback**` prose cannot bias AC-token matching; RED,
GREEN, and REFACTOR receive the raw card (including Judge Feedback history).
When the runner passes `train_feedback=...`, that string is present in the
assembled prompt (`{train_feedback}` / the GREEN-style `<train_feedback>`
block). Agents must not open `tasks.md` for this-task fields (Flow
References, AC-PLAN ids, Judge Feedback); they use the injected card.
Manual `deviate red|green|refactor pre` resolve the queued/pinned task via
`_resolve_task_context` (correct `task_id`, not a sibling). `deviate judge
pre` remains a protected-module scan and does not emit `task_id`; JUDGE
uses the same `_resolve_task_context` selector as the other micro pres.

#### `deviate red pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves the task context from `tasks.jsonl`, emits JSON contract with
  `task_id`, `test_command`, `lint_command`, `spec_dir`, and `task_entry` (this task's
  `tasks.md` card via `_task_card_text`, mirroring `green_pre` — it carries persisted
  `**Judge Feedback**` bullets so the manual RED agent receives correction history that
  manual mode cannot inject as `<train_feedback>`).

#### `deviate red post [--task-id <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Runs the project's resolved test command (language-agnostic: `mix test`,
  `cargo test`, `npm test`, `go test ./...`, or `pytest` chosen via `_resolve_verification_command`
  — the same resolver used by `deviate red|green|refactor pre`, `_build_auto_prompt` `{test_command}`,
  and `_run_test_cmd`. Resolution order: (1) if the declared verification is **partial** (a file,
  `-k` / `--keyword`, or node id) and the repo has `mise.toml` / `.mise.toml`, wrap it as
  `mise exec -- <declared>` so the command still uses the repo `.venv`; never expand a partial run
  into `mise test` / `mise unit` / `mise e2e`; (2) if the command is a **full suite**, pick an
  allowlisted named mise task that actually exists (`doctor` is preflight only): unit markers →
  `mise unit`, integration markers → `mise integ` or `mise integration` (the name the repo defines),
  e2e **only** when the task/verification explicitly says e2e → `mise e2e`, otherwise `mise test`
  when `[tasks.test]` exists; if unit vs integ is ambiguous and both exist, prefer `mise test` else
  `mise unit` (never default e2e); (3) mise present but no matching named task → `mise exec --
  <declared>`; (4) no mise → task `verification`, constitution `test_command`, manifest table,
  Python fallback, unchanged. Pre JSON also lists the allowlisted tasks that exist
  (`doctor`, `test`, `unit`, `integ`/`integration`, `e2e`) and does not dump unrelated mise tasks.
  When `[tasks.doctor]` exists, the runner and pre run `mise doctor` before verification (deps,
  ports, DB up). Doctor failure is `ENV_NOT_READY` — not RED established, GREEN fail, or
  `failure_kind: mechanical`. Absence of doctor skips preflight. The exact command string is
  logged (`TEST_COMMAND`) and injected into the phase prompt; agents must not invent a bare
  `pytest` / `mix test` when mise was resolved. Validates the test fails explicitly (ASSERTION_FAILURE, not PASS or
  SYNTAX_ERROR), runs the test command, and reports whether the test failed as expected.
  Optional ``--task-id`` is compared to the resolved pending record
  (``session.active_issue_id`` → first PENDING) **before** the ledger transition
  and commit. Mismatch prints ``TASK_ID_MISMATCH`` and exits 1 with no ledger
  write and no commit. Match, or an omitted ``--task-id``, keeps the existing
  post behavior.
  `deviate micro run`'s internal RED phase (`_run_red_phase`) applies the same contract: when the
  test command exits 0 (all tests passed), collects no tests (pytest exit 5), or resolves to no
  command at all (returncode 127), it does NOT die — it routes the decision to JUDGE
  (``failure_kind: no_failing_test``). On a test-bearing TDD task, already-exists COMPLETE
  requires a non-empty ``files`` set and/or ``test_file`` that names regression tests present
  in the injected ``<diff>`` or HEAD (constitution §3 Testing Protocols; §5 Definition of Done).
  Empty ``files`` / ``test_file`` is a RED defect (``PhaseFailedError``); the ledger writes no
  COMPLETED row. JUDGE ``skip_refactor`` / bare ``COMPLIANCE_PASS`` keeps those declared tests
  on disk via ``_restore_worktree_to_baseline(..., keep_paths=declared)``. On the already-exists
  route (``session.red_commit_sha == ''``), a ``no_failing_test`` ``COMPLIANCE_PASS`` with any
  ``next_action`` completes via ``skip_refactor`` even when the evidence cites only part of the
  task's ``AC-PLAN-NNN`` tokens: ``_apply_judge_verdict`` skips the unmatched-PASS rewrite for
  this route, and ``_require_tdd_completed_evidence`` relaxes the AC-token citation check while
  keeping the declared regression-path presence gate. ``ROLLBACK_BOUNDARY_MISSING`` applies only
  to a genuine TDD ``revert_green`` with an empty ``red_commit_sha`` — never on the
  already-exists pass path. A declared path missing from the snapshot rewrites PASS to
  ``revert_red`` / ``revert_green``. JUDGE still rules a wrong test as ``revert_red`` so
  RED re-authors a genuinely failing test. EXECUTE,
  IMMEDIATE, and DIRECT stay ungated by this files rule. After ``revert_red`` / cycle
  ``no_failing_test_adjudicated``, the next ``INVOKE_AGENT`` is RED, or the loop raises
  ``TRAIN_EXHAUSTED`` / ``PhaseFailedError``. It never invokes GREEN while
  ``session.red_commit_sha`` is empty. The RED gate does not require a Python
  ``tests/**/test_*.py`` glob — test discovery follows the project's own convention (e.g.
  ``test/**/*_test.exs`` for Elixir). On a genuine failing test it appends the RED status
  transition to the task ledger, forces session to RED, and commits with
  `test({scope}): RED phase - failing test`.
  Commit messages are convention-aware: when the project declares an emoji convention in
  ``CONTRIBUTING.md`` / ``.commit-convention.md``, the appropriate gitmoji is prepended
  automatically. RED phase `test:` commits are prefixed with 🚨 to flag the failing test (see
  `format_commit_message(..., phase="red")` in `core/convention.py`); GREEN phase `test:`
  commits use ✅. `feat:` commits always use ✨ regardless of phase.

#### `deviate green pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves task context, emits JSON contract with `test_file` and
  `implementation_targets` (all `src/**/*.py` files).

#### `deviate green post`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies a RED transition exists for the active issue. Runs the project's
  resolved test command (language-agnostic, e.g. `mix test` / `cargo test` / `pytest`), requires
  returncode 0. Appends GREEN transition to ledger, forces session to GREEN,
  commits with `feat({scope}): GREEN phase - implementation passes tests`.

#### `deviate judge pre`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Detects phase changes, finds protected modules from `spec.md` `Module:`
  lines, checks for compliance violations, and emits JSON verdict
  (`COMPLIANCE_VIOLATION` or `COMPLIANCE_PASS`).

#### `deviate judge post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py` (`judge_post` on `judge_app`)
* **Description:** Manual-mode counterpart to the auto JUDGE side effects. Reads the JUDGE handover (manifest path or stdin YAML) and applies the same post-verdict work `_run_judge_phase` owns after the agent returns. Coerces `next_action` via `_coerce_judge_action`, the unmatched-PASS rewrite, and the GREEN TEST_FAILURE remap from GH-100. `revert_green` rolls GREEN back to `session.red_commit_sha`; `revert_red` rolls RED+GREEN back to `red_commit_sha^`. Both reuse `_execute_rollback` / `_resolve_pre_red_sha` — there is no second rollback path. Train feedback is appended to the rejected task card in `tasks.md` and committed by `_commit_judge_feedback_and_advance`, which advances `red_commit_sha` past that feedback commit when a real RED SHA exists. Forward routes (`continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff`) do not revert; they update session/ledger the same way auto does. Rejection without actionable feedback is `JUDGE_AGENT_NO_FEEDBACK`. A missing RED boundary on `revert_green` is fatal (`ROLLBACK_BOUNDARY_MISSING`). Prints the route and returns. The agent does not `git reset` or edit `tasks.md` itself. Auto `micro run` stays on `_run_judge_phase` and does not shell out to this command. Cycle regressions for this handover (and the matching auto `_run_tdd_cycle` path) go in `tests/helpers/cycle_driver.py` fixtures — same YAML on both entrypoints; new coerce branches alone are not enough.

#### `deviate refactor pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Resolves task context via `_resolve_task_context` and emits a JSON
  contract. `files_to_refactor` is the production-file set from `HEAD~2..HEAD`
  (the RED+GREEN commits). When that git range is empty or unavailable, it
  falls back to the task `Files:` list minus tests. Test files are never
  included. The contract also carries the documented handover fields:
  `status`, `task_id`, `task_title`, `task_type`, `test_command`,
  `lint_command`, `spec_dir`, `verification`, `repo_root`, `git_branch`,
  `timestamp`. Auto `_build_auto_prompt("refactor")` injects the same scoped
  list; it does not glob `src/**/*.py`.

#### `deviate refactor post`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies a GREEN transition exists. Appends REFACTOR transition, runs
  the AST-based return type mismatch check (Python only), runs the resolved test command
  before/after to detect regression. On regression, restores via `git restore .` and halts.
  Commits with `refactor({scope}): REFACTOR phase - code cleanup`.

#### `deviate execute pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** DIRECT execution mode for `direct`/`immediate`-typed tasks — boilerplate, config, asset syncs, trivial fixes, or refactors with existing test coverage. Bypasses the RED phase entirely. Emits JSON contract with completion criteria; the agent runs once and the result is committed.

#### `deviate execute post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, then runs `_run_execute_phase()` which invokes the EXECUTE agent and follows with a JUDGE pass against `spec.md`. On `COMPLIANCE_VIOLATION`, `_execute_rollback()` resets the implementation and the phase is retried with `<train_feedback>` injected (up to `max_judge_attempts = 3`). The EXECUTE → JUDGE → EXECUTE iteration mirrors the Green → Judge → Green loop in shape but skips the RED boundary: the EXECUTE phase is allowed to start from any clean working tree and the JUDGE pass evaluates the diff post-hoc. Exhaustion raises `PhaseFailedError`. The task is marked `COMPLETED` only on `COMPLIANCE_PASS`; the result is committed with the manifest's `commit_message` (or a default `chore({scope}): execute`).

#### `deviate e2e pre`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Verifies the branch's issue tasks are COMPLETED, then emits the E2E contract. The active issue is resolved from `session.active_issue_id`, falling back to a branch-derived lookup via the `feat/{epic}/{issue}` regex against `specs/issues.jsonl` (same resolution as `deviate micro run`). When no issue resolves (plain dir / non-feature branch) it fall-backs to a repo-wide completeness check for backward compatibility. When an issue resolves, completeness is scoped to that issue's own `tasks.jsonl` so an unrelated issue's incomplete tasks do not block the run. The emitted contract adds `issue_id`, `tasks_file`, `spec_dir`, and `git_branch` alongside `test_paths` (the `/deviate-e2e` skill consumes these to read the issue spec and task ledger).

#### `deviate e2e post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, commits E2E verification results.

#### `deviate hotfix pre [--task <id>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Bug fix mode - always bypasses RED phase.

#### `deviate hotfix post [<manifest>]`

* **Source:** `src/deviate/cli/micro.py`
* **Description:** Validates manifest, commits HOTFIX result.

#### `deviate prune pre [--issue <id>] [intent…]`

* **Source:** `src/deviate/cli/prune.py` (`prune_app`), engine `src/deviate/core/prune.py`
* **Description:** Inventory contract for `/deviate-prune`, the manual honeycomb
  test-thinning surface. Resolves **one** issue (`--issue`, else
  `session.active_issue_id`). Classifies issue-scoped tests: prefer pytest
  marks and name tags (`spy` / `impl` drop, `behavioral` / `ac` keep). Untagged
  tests are classified from the body (drop internal spies/mocks/private state;
  keep public input-to-output / AC) and must not auto-keep. `spec_deletes` is
  always empty — prune never schedules deletion of `plan.md`, `tasks.md`,
  `explore.md`, `prd.md`, issue md, or ledgers. In-flight (non-COMPLETED)
  issues emit `IN_FLIGHT` and still classify tests. Compact / squash / rewrite
  intent is `LEDGER_REWRITE_REJECTED`. Manual invoke only: not hooked into
  micro COMPLETED, `--all`, or the `deviatdd` skill success loop.
* **Input Parameters:**
  * `--issue <id>` (optional; one issue per invocation)
  * trailing `intent` words (rejected when they ask to compact/squash/rewrite)
* **Output Artifacts:** JSON contract with `status`, `issue_id`, `issue_status`,
  `spec_deletes` (always `[]`), `spec_keeps`, `test_drop`, `test_keep`,
  `unmatched_acs`, `ledger_untouched`, `reason`, `repo_root`.

#### `deviate prune post [--issue <id>] [intent…]`

* **Source:** `src/deviate/cli/prune.py`
* **Description:** Applies honeycomb thinning (deletes tagged `spy` / `impl`
  tests and untagged internal probes; keeps `behavioral` / `ac` and public
  I/O). Never unlinks `plan.md`, `tasks.md`, `explore.md`, `prd.md`,
  `specs/**/issues/*.md`, leftover cycle markdown, constitution,
  or any JSONL ledger. READY and `IN_FLIGHT` both thin tests and leave specs
  in place. Does not commit — the slash command commits the cleanup.
* **Input Parameters:** Same as `deviate prune pre`.
* **Output Artifacts:** Same JSON contract; filesystem mutations as above.

---

### 5. Automated Pipeline Orchestration

#### `deviate run` (Meso → Micro Chain)

* **Source:** `src/deviate/cli/__init__.py` (top-level `run_command`)
* **Description:** Canonical "go do the next thing" entry point. Runs `deviate meso run` end-to-end (SPECIFY setup → PLAN → TASKS) and then **chains** into `deviate micro run --all` to drain the task queue. There is no human-approval step between meso and micro — the system auto-advances. Discovers the next unblocked BACKLOG issue, claims it (creating the per-issue worktree), runs the meso pipeline in the worktree, then dispatches the micro drain. Internally:
  1. Calls `_meso_run(issue_id=...)` from `src/deviate/cli/meso.py`, which returns the created worktree path on success (`str(worktree_path)`).
  2. `chdir`s into that worktree, updates `.deviate/session.json` to record the handoff.
  3. Invokes `_run_all(root, console)` from `src/deviate/cli/micro.py` against the worktree, draining every PENDING task for the active issue.
* **Input Parameters:**
  * `--issue <ISS_ID>` (Target a specific BACKLOG issue; e.g. `002-001` for new work, `ISS-019` for grandfathered ids. Default: next unblocked.)
  * `--force` (Bypass `blocked_by` pre-flight guards; forwarded to meso)
  * `--local` (Claim locally only: create worktree, write ledger, commit; skip remote check and `git push`. Distinct from `--no-setup`. Omitted flag honors `claim_remote` config. Forwarded to `_meso_run`.)
  * `--model <id>` (Override default model for RED/GREEN/REFACTOR/EXECUTE phases;
    resolution: phase-specific config &gt; CLI `--model` &gt; default config &gt; backend native;
    JUDGE is excluded from CLI override to preserve model tiering)
* **Exit Codes:** 0 on meso + micro success; 1 if meso reports failure (`RUN_NO_WORKTREE` / `RUN_WORKTREE_MISSING`).
* **Replaces:** The old task-dispatch surface. The per-task and `--all` dispatches live at `deviate micro run <task-id>` and `deviate micro run --all`; the former `--profile` / `--no-judge` / `--no-refactor` / `--agent` / `--json` flags were removed from `deviate run` and remain available on `deviate micro run`.

#### `deviate micro run [task-id]` / `deviate micro run --all`

* **Source:** `src/deviate/cli/micro.py` (`run_command` decorated by `micro_app`)
* **Description:** The per-task / queue-drain dispatcher that used to live as the
  top-level `deviate run`. Routes each task by `execution_mode` to the TDD cycle
  (RED → GREEN → JUDGE → REFACTOR) or to the execute phase. Single-task by
  default; `--all` drains every PENDING task for the active issue (or all
  issues if no active issue is set).
* **`--review` (optional per-phase commit pause, GH-101):** After the agent
  finishes a phase and tests/lint have run, `deviate micro run --review`
  (and `--all --review`) halt **before** `_commit_phase` /
  `_commit_phase_with_recovery` (`git add -A`). The runner prints
  `REVIEW_PAUSE <phase> <task_id>`, leaves the worktree dirty for
  herdr/hunk, and waits for TTY confirmation (`Enter` / yes). Then it
  commits as today and continues. Pause applies to RED, GREEN, REFACTOR,
  and EXECUTE. JUDGE feedback commits (`_commit_judge_feedback_and_advance`)
  are not paused. After REFACTOR is reviewed and committed the task is
  marked COMPLETED; `--all` pauses the same way on the next task. RED is
  still committed before GREEN so `session.red_commit_sha` is available
  for JUDGE `revert_green`. Non-TTY / `--json` / missing stdin fail
  closed with `REVIEW_REQUIRES_TTY` and never auto-commit past the flag.
  Off by default; no config key in this slice. The pause lives in one
  helper (`_maybe_review_pause`) in front of `_commit_phase`, not copied
  into each phase.
* **Single-Task (`deviate micro run <task-id>`):** Triggers the automated
  execution cycle for a single task node. A pinned `task-id` stays in the
  active issue's namespace when the branch or re-keyed session issue is
  known. Same-number `TSK-NNN-NN` ids are a per-issue namespace. A sibling
  COMPLETED row for the same number is not a hit and does not print
  `TASK_ALREADY_DONE`. TDD mode runs the RED → GREEN →
  JUDGE → REFACTOR cycle. Non-TDD (`DIRECT` or `E2E`) runs `_run_execute_phase`,
  which commits the work, then optionally runs a JUDGE pass against `spec.md`
  and rolls back on `COMPLIANCE_VIOLATION` (up to `max_judge_attempts = 3`).
  Implements `_run_single` / `_dispatch_task` from `src/deviate/cli/micro.py`.
  * **Green → Judge → Green loop (TDD only):** `_run_tdd_cycle` wraps the
    GREEN → JUDGE pair in a `while not judge_passed` loop with two
    persisted `SessionState` counters: `green_attempts` (max 3) and
    `red_attempts` (max 3). `revert_green` trains GREEN against one
    standing RED contract and increments `green_attempts`; when
    `green_attempts` reaches 3 the runner escalates instead of printing
    `TRAIN_EXHAUSTED`. `revert_red` escalates now. `TRAIN_EXHAUSTED`
    prints only after three RED escalates. On test failure or `COMPLIANCE_VIOLATION`,
    `_execute_rollback()` runs `git reset --hard <boundary_sha>` against
    the boundary the caller threads in: TDD JUDGE's `revert_green`
    passes `session.red_commit_sha`, TDD JUDGE's `revert_red` resolves
    `red_commit_sha^` via `_resolve_pre_red_sha`, and EXECUTE JUDGE
    passes the pre-EXECUTE `pre_execute_sha`. `_execute_rollback` requires
    the boundary explicitly — it no longer falls back to
    `session.red_commit_sha` or `HEAD~1`, and raises
    `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")` BEFORE any
    `git reset` / `git clean` when the caller forgets to thread the
    boundary or the boundary is empty/whitespace. The rejected-commit
    snapshot lands on a per-task, per-attempt recovery ref
    `tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>` (one
    attempt per rollback fired inside a single JUDGE-phase call, threaded
    via `_recovery_branch_for`) so a second rollback never clobbers the
    first attempt's recovery handle. A fresh RED attempt clears any
    boundary retained by a prior task before invoking the agent, then
    records its own boundary only after the RED commit lands. Agent startup
    failures therefore leave no cross-task rollback anchor. TDD
    `revert_green` with an empty `session.red_commit_sha` raises
    `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")`. `_run_judge_phase`
    does not catch that error, print `ROLLBACK_FAILED`, commit a
    `docs(...): add judge feedback` marker, or `force_transition_to("GREEN")`.
    When a RED-phase SHA exists, the runner commits a feedback marker and
    advances `session.red_commit_sha` past it so a second rejection can roll
    back only the subsequent GREEN. GREEN entry requires that SHA to be a
    standing RED-phase failing-test commit. After `no_failing_test` /
    `revert_red` / `no_failing_test_adjudicated`, the next `INVOKE_AGENT`
    is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`.
    `_run_green_phase` raises `GREEN_ENTRY_REFUSED` and does not invoke the
    GREEN agent when `session.red_commit_sha` is empty or a
    `docs(...): add judge feedback` SHA that does not rest on a RED-phase
    ancestor. The session is
    `force_transition_to("GREEN")`, and the
    previous attempt's feedback is injected as `<train_feedback>` into the next
    GREEN prompt via `_build_auto_prompt("green", ..., train_feedback=...)`.
    The cycle retries from

  * **EXECUTE commit-failure recovery (terminal contract):** The single
    EXECUTE-phase commit at `micro.py:2857` is the only `_commit_phase`
    call site that intentionally lets the project's pre-commit hook
    gate the commit. To keep routine `no_verify=True` RED/GREEN/REFACTOR
    commits behaving exactly as before, the EXECUTE site was switched
    to a separate helper, `_commit_phase_with_recovery(message, root, *,
    task_id, attempt, phase="EXECUTE")`. The new helper:
    - Runs `git commit` with combined `stdout+stderr` captured.
    - Treats the benign clean-worktree case as a successful no-op:
      when `git commit` exits 1 and the combined output contains
      "nothing to commit" (a message git only emits AFTER the hook
      chain passes, so it cannot mask a hook-blocked commit), the
      helper returns `True` without creating a recovery ref or
      raising `CommitFailedError`. The caller's no-diff branch
      (`JUDGE_SKIP`) then completes the task — the EXECUTE agent
      legitimately made zero changes (deliverable already exists).
      `_git_env()` pins `LC_ALL=C` so the detection is independent
      of the operator's locale.
    - On non-zero, builds a recovery commit from the existing staged
      index via `git write-tree` / `git commit-tree -p HEAD` /
      `git update-ref`. No `git add`, no `git reset`, no `git clean`,
      no `git stash` — the operator's index and worktree are
      unchanged after preservation.
    - Asserts `git rev-parse <sha>^{tree} == <write-tree>` to catch
      merge-driver / intent-to-add / submodule mismatches before the
      recovery ref is created.
    - Reserves a per-task attempt number ONCE before plumbing via
      `_next_recovery_attempt(task_id, root=root)`; the same integer is
      used in BOTH the commit message and the recovery ref name
      (`refs/deviate/recovery/<sanitized-task-id>/attempt-<N>`). This
      is a SEPARATE namespace from the rollback preservation ref
      `tmp/deviate-agent-work/<task>/attempt-<N>` defined by the
      round-1 rollback fix; the two namespaces are kept distinct so a
      reader can tell rollback-snapshot evidence from commit-hook-block
      evidence at a glance.
    - Sanitizes the task id with the allow-list `[A-Za-z0-9_-]`
      (length cap 64; rejects empty / leading-`.` / `..` / too long).
      Sanitize failures surface as `CommitFailedError(reason=sanitize_*, recovery_ref=None)`,
      translated at the call site so they do not collapse into
      `commit_failed_plumbing`.
    - Prints a recovery banner with the combined output, the
      `recovery_ref`, and TWO recovery options: (a) fix the failure
      in the target repo and re-run `git commit`; (b) restore the
      rejected work with `git cherry-pick
      refs/deviate/recovery/<task>/attempt-<N>` after the operator
      has explicitly restored or removed the current changes. The
      banner does NOT prescribe `git reset` or `git clean -fd` —
      those are dangerous generalities the operator must decide
      themselves.
    - Raises `CommitFailedError(PhaseFailedError, terminal=True)`. The
      exception subclasses `PhaseFailedError` so the existing
      `PhaseFailedError` catch sites in `_run_execute_phase` and
      `_run_single` continue to match without code changes; the task
      is marked FAILED with reason `commit_failed`. The failure is
      terminal for the current run (no automatic retry atop the
      rejected staged tree).
    - On plumbing failure (corrupt index, broken worktree), raises
      `CommitFailedError(recovery_ref=None, reason=commit_failed_plumbing)`
      with the plumbing stderr in `output` so the operator sees the
      underlying cause instead of a misleading hook-blocked banner.
  When session feedback is unavailable, auto GREEN and auto RED read the matching task's persisted `**Judge Feedback**` bullets from `tasks.md` as `<persisted_judge_feedback>` (`_run_red_phase` applies the same fallback as `_run_green_phase`; the RED prompt's `<step id="feedback_ingestion">` documents the same precedence — session `train_feedback` wins, persisted bullets are stale history). Session `train_feedback` remains authoritative when present, preventing duplicate or stale feedback; the reader is scoped to the exact task block. `_append_judge_feedback` locates that block with `_TASK_BULLET_HEAD_RE` exact-id match (same regex as `_read_judge_feedback_from_tasks_md`) and inserts the bullet under the rejected card only — it does not walk past a later `##` / `###` phase heading onto the next task (GH-102).
    GREEN. After 3 attempts the task is marked `FAILED` and the pipeline halts
    with `PhaseFailedError`. The feedback source precedence is `train_feedback`
    on the manifest → `_extract_judge_feedback(...)` from `tasks.md` → verbatim
    verdict / rationale.
  * **JUDGE `next_action` routing:** After the TDD mechanical evidence gate accepts a forward PASS, the runner honors `HandoverManifest.next_action`
    for the five supported values (`revert_red`, `revert_green`,
    `continue_refactor`, `skip_refactor`, `proceed_to_refactor_no_diff`). See the
    **JUDGE `next_action` Routing Table** in this document for rollback anchors
    and boundary-advance rules per route, and the runner fallbacks when the
    field is absent (default: `revert_green` on violation). A clean
    `COMPLIANCE_PASS` (no compliance / Test Integrity failure) ignores revert
    `next_action` values, including the legacy `revert_to_red` alias — a
    `REFACTOR NOTE:` in `train_feedback` is advice for REFACTOR, not a reject
    (GH-158). Omitted / ignored-revert pass actions default to
    `continue_refactor`, or `skip_refactor` when `--no-refactor`. The note is
    injected into the REFACTOR `{train_feedback}` placeholder; it is not sent
    as GREEN/RED train feedback. After GREEN PASS (empty `session.failure_kind`),
    a `COMPLIANCE_VIOLATION` with structured Test Integrity
    (`violations[].category` matching Test Integrity / `Test Integrity Violation`,
    and/or `evaluation.test_integrity: FAIL`) is coerced to `revert_red`
    even when `next_action` is omitted or `revert_green`. An honest-test
    implementation/scope gap (`test_integrity: PASS`, Spec Non-Compliance)
    stays `revert_green`. Mechanical overlay is not coerced by Test Integrity.
    The runner does not parse `train_feedback` for routing (only to extract a
    pass-path `REFACTOR NOTE:` for REFACTOR). EXECUTE and
    IMMEDIATE judge paths stay ungated.
  * **Resume from Mid-Phase:** If `session.current_phase` is `JUDGE` or
    `REFACTOR` when invoked, the cycle resumes from that phase via the
    `start_phase` parameter. IDLE / RED trigger a fresh cycle from RED.
  * **GREEN-resume `start_phase=JUDGE` honors `revert_green` as TRAIN GREEN:** Ledger status GREEN maps to `start_phase="JUDGE"` (`_start_phase_from_status`). After that JUDGE, `pending_judge_action == revert_green` (or `judge_rejected` with that action) falls through into the GREEN train loop — discard GREEN, keep RED, re-run GREEN with the stored `train_feedback`. The runner must not call `_finish_tdd_cycle` / REFACTOR / COMPLETED on that path. When the session already holds `pending_judge_action == revert_green` plus `train_feedback` (JUDGE already applied the verdict), skip a second JUDGE and train GREEN immediately. `_finish_tdd_cycle` also refuses REFACTOR and COMPLETED while pending is `revert_green` or `revert_red` (defense in depth). The in-loop TRAIN GREEN path and `revert_red` escalate-to-RED are unchanged. Pinned by `tests/test_micro/test_revert_green_resume.py`.
  * **Cross-task forward-route resume (GH-148):** `.deviate/session.json` is gitignored and can keep a previous task's `pending_judge_action` (`skip_refactor` / `continue_refactor` / `proceed_to_refactor_no_diff`) plus `last_judge_verdict` / `validated_evidence`. Ledger status RED maps to `start_phase="GREEN"` (`_start_phase_from_status`). `_tdd_pre_green_decision` (and `_run_tdd_cycle` on dispatch) treats that forward route as complete only when `judge_task_id` and `judge_red_commit_sha` match the active task and standing RED SHA. A leftover from another task, a different RED SHA, or a pre-fix unbound route once a RED SHA exists is cleared (`pending_judge_action`, `last_judge_verdict`, `validated_evidence`, `train_feedback`) so GREEN and JUDGE run. Same-task `skip_refactor` from this task's JUDGE still completes; `--no-refactor` after a fresh this-task pass still completes. No `SESSION_STALE` HITL prompt; the session file is not deleted. GH-158 Pass+`REFACTOR NOTE` forwarding is unchanged. Pinned by `tests/test_micro/test_stale_session_forward_route.py`.
* **Queue Drain (`deviate micro run --all`):** **Issue-scoped** task sweep.
  A known `feat/{bucket}/{slug}` issue from `specs/issues.jsonl` beats a leftover
  `session.active_issue_id`. The leftover issue does not keep the queue even when
  it still has a `tasks.md` in this checkout. The resolver writes the
  authoritative id to the worktree `.deviate/session.json`. An empty session
  falls back to the branch. When the branch does not resolve, a valid session
  id stays in place. Bare `deviate micro run` uses the same rule. The runner
  then dispatches **every PENDING task for that issue** sequentially. Each
  task gets up to **2 retry attempts** (`_execute_task_with_retry`,
  `for attempt in range(2)`) before being marked `FAILED` in the
  issue-scoped `tasks.jsonl`. The pipeline **halts on the first failure**
  (`any_failed = True; break`) and exits with code `1`. When the branch
  issue has no PENDING tasks, the command prints `NO_PENDING_TASKS` and
  exits `0`. Meso claim and `MESO_ALREADY_COMPLETE` rewrite the worktree
  session to the claimed issue.
* **Test-command deadline (`_run_test_cmd` → `_execute_test_command`):**
  Every test command is run through `run_safe_command(command, cwd,
  timeout=...)` (`src/deviate/cli/_safe_commands.py`). The deadline
  resolves as `DEVIATE_TEST_TIMEOUT_SECONDS` (env override) →
  `DeviateConfig.timeout_seconds` (`.deviate/config.toml`, default
  `1800`) → `1800`; an unparseable env value or a `gt=0`-violating
  config value falls through to the next source so the timeout
  binding can never be silently disabled. When the deadline lapses
  the orchestrator runs SIGTERM, waits a 5s grace window, then
  SIGKILL on the **process group** (`start_new_session=True` →
  `os.killpg`) so every descendant of the test command — e.g.
  `cargo test` spawning `gloss serve` parked on stdin EOF — is
  reaped alongside the immediate child. The wrapper returns a
  deterministic `subprocess.CompletedProcess` with
  `returncode == 124` (GNU `timeout(1)`-compatible) and preserves
  partial stdout/stderr captured before the deadline. Fixes the
  GREEN-phase hang observed when the inner child caught SIGTERM but
  refused to exit (e.g. tokio's signal drain). Tighten the deadline
  via `DEVIATE_TEST_TIMEOUT_SECONDS=300` (env) or
  `timeout_seconds = 300` (`.deviate/config.toml`) for CI runs
  where short-deadline failure is preferable to a slow green.
* **Train Retry Loop (per task):**
  Same two-counter contract as **Green → Judge → Green loop (TDD only)**
  above. `_run_tdd_cycle` persists ``green_attempts`` (GREEN train,
  max 3, then escalate) and ``red_attempts`` (RED escalate, max 3).
  ``TRAIN_EXHAUSTED`` prints only after three RED escalates.
  The loop never invokes the agent twice in a row for the same
  phase; on the final failure it surfaces the captured manifest's
  ``rationale`` (with an attached agent-stdout tail when
  ``rationale`` is empty) and marks the task FAILED.
* **Agent Backend Hardening (v2.9.x):** `AgentBackend` enforces four
  dispatch contracts. (1) **Prompt cap** — every prompt is capped at
  `MAX_PROMPT_CHARS = 80,000` by `_truncate_prompt`; oversized
  prompts preserve head + tail and are marked with a
  `PROMPT_TRUNCATED` comment so the agent knows the payload was
  sliced. (2) **Streaming stall watchdog** — the streaming dispatch
  path (`_invoke_streaming`) uses stdout as the only liveness
  source. Stderr is diagnostic capture and does not reset the
  hard stall clock. Periodic stdout keeps the watchdog warm.
  The default budget is `STREAM_STALL_TIMEOUT_SECONDS = 900`.
  GREEN, RED, JUDGE, and REFACTOR use that default. EXECUTE
  passes `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600).
  A stdout-silent stall raises `AgentTimeoutError` with
  `STALL_DETECTED`. The same poll loop also honors
  `timeout_secs` from the single consolidated `DeviateConfig.timeout_seconds`
  (default 1800s), resolved by `resolve_agent_deadline`
  (`src/deviate/state/config.py`) — the same value governing test-command
  deadlines. The removed `AgentConfig.timeout` field no longer exists.
  A RED child that writes files or trickles stdout and never
  returns a handover manifest still raises `AgentTimeoutError`
  inside that wall-clock. `invoke` re-raises stall and
  wall-clock timeout and does not sleep 30s for a second
  budget. `_invoke_agent` logs `AGENT_TIMEOUT` with `error=`,
  `partial_stderr=`, and `partial_stdout=` for a hung RED or
  hung GREEN. `_run_red_phase` then restores `red_baseline` via
  `_restore_worktree_to_baseline` and raises `PhaseFailedError`
  that names timeout. The operator does not wait for an outer
  ~1800s bash kill. (3) **Manifest retry-with-context** — a malformed
  or empty manifest triggers one additional `subprocess.Popen`
  whose prompt includes the previous parse error and an explicit
  `strict YAML block delimited by ```yaml ... ``` only` directive.
  Subprocess failures (`AgentSubprocessError`) are NOT retried as
  manifest failures. (4) **YAML hint widening** — the parser's hint
  engine now detects backslash-escaped quotes inside double-quoted
  scalars, unbalanced `"` counts, and mis-indented ``|`` block
  scalars. (5) **Schema recovery** — missing `phase` / `status`
  fields surface as `UNKNOWN` instead of raising
  `MalformedHandoverManifestError`; recovered manifests carry a
  populated `parse_errors` list and
  `HandoverManifest.is_success` returns `False` so existing
  `manifest.status.upper() in (...)` success gates keep rejecting them.
  (6) **Stricter mapping fallback** — the `_YAML_MAPPING_START_RE` fallback (`src/deviate/core/agent.py`) routes the candidate text through a `_looks_like_manifest` helper that requires `yaml.safe_load(candidate)` to return a `dict` with at least 2 keys before accepting. Single-key dicts (e.g. a stray `Status: complete` line in a JUDGE verdict with a verification matrix) look like prose, not manifests; the fallback now rejects them and the parser raises `MalformedHandoverManifestError` with the existing "No YAML handover manifest detected in agent output" hint. Multi-key partial dicts still flow through to schema recovery unchanged, so the existing `test_missing_phase_and_status_recover_as_unknown` contract is preserved. (6b) **Unescaped evidence-quote recovery (GH-116)** — when `yaml.safe_load` rejects a handover because an evidence `quote` / `test_quote` / `impl_quote` double-quoted scalar embeds raw `"`, `parse_output` rewrites those lines as `|` block scalars and reloads. Well-formed YAML is unchanged. Truly malformed YAML still raises `MalformedHandoverManifestError`. Verdict and evidence semantics are unchanged.
  (7) **Lean Pi spawn** — `AgentBackend.invoke` appends a lean tool policy after the existing Pi transport prefix. Print mode keeps `BACKEND_COMMANDS["pi"]` as `pi -p` (AC-009-07). RPC keeps `PI_RPC_COMMAND` as `pi --mode rpc --no-session` (AC-009-10). The helper `_pi_lean_flags` then adds `--tools read,bash,edit,write` and `--no-skills`. It does not add `--no-extensions`: extension-registered providers (such as a custom provider package) must load so a saved default model from that provider resolves. Without them, pi silently falls back to the first model the operator's environment keys authenticate. When `.pi/skills/deviatdd/SKILL.md` exists under the invoke `cwd` (or `Path.cwd()`), it also adds `--skill` to that relative path. A missing skill file keeps the four coding tools. The argv omits `--no-tools` and `--no-builtin-tools`. Non-Pi backends skip these flags.
  (8) **Schema-rejection fail-fast** — `_invoke_streaming`, `_invoke_blocking`, and `_invoke_rpc_blocking` scan each stderr and stdout line. The first line that contains `tool_count_limit` or `unsupported_tool_schema` kills the child. The helper raises `AgentSubprocessError` whose message carries those tokens. This path does not wait for `STREAM_STALL_TIMEOUT_SECONDS` (900s). It does not start the 30s timeout retry. It does not start the `EmptyOutputError` manifest retry. Schema tokens do not reset the stall clock. Stderr stays diagnostic for stall liveness (ISS-ADH-025). `_invoke_agent` logs `AGENT_ERROR` with the exception text. `_raise_schema_limit_phase_error` then raises `PhaseFailedError` so `deviate micro run` RED, GREEN, and REFACTOR include the tokens. The operator does not see only `agent returned no manifest`. EXECUTE stall stays 3600s (GH-53).
* **GREEN Stub-PASS Guard (REMOVED):** An earlier revision of this spec
  described a guard that rejected ``status: PASS`` manifests with zero
  observed source changes. That implementation was rolled back:
  deciding whether a task is done is JUDGE's job (the TDD JUDGE
  evidence gate requires a dirty-diff ``test_quote`` on
  ``proceed_to_refactor_no_diff`` for empty GREEN), not GREEN's. GREEN's only invariant is "make tests
  pass"; a feature that already works (e.g. landed in a prior
  session, a docs/rename task) is a legitimate zero-change PASS. The
  field that remains is ``HandoverManifest.files: list[str] | None``
  — declared optionally by the agent and recorded for operator
  cross-check only.
* **JUDGE Failed-GREEN Worktree Visibility:** When GREEN leaves production changes uncommitted because its test command failed, JUDGE evaluates both the committed RED-parent-to-HEAD diff and the current staged, unstaged, and untracked worktree diff. Untracked files are rendered with `git diff --no-index /dev/null <path>`. This preserves the implementation for compliance assessment instead of presenting JUDGE with a false RED-only view.
* **GREEN TEST_FAILURE must not complete:** When GREEN implements (agent SUCCESS) and the suite is still red, `_run_green_phase` logs `TEST_FAILURE` and keeps the implementation for JUDGE. Detection is precise: the distinctive test-dump prefix plus empty `session.failure_kind` — not "any `train_feedback` on GREEN", which also matches mechanical / test_defect `status: FAILURE`. JUDGE may still run. Only `revert_green` (TRAIN / retry GREEN) and `revert_red` (escalate RED) change the route. `continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff` / bare `COMPLIANCE_PASS` remap to TRAIN with the test dump. `_finish_tdd_cycle` refuses REFACTOR and COMPLETED while that TEST_FAILURE is in effect. Mechanical / test_defect GREEN `status: FAILURE` routing is unchanged. Pinned by `tests/test_micro/test_orchestration.py::TestMicroOrchestration::test_green_test_failure_compliance_pass_continue_refactor_retrains`.
* **GREEN Entry Invariant:** `_run_green_phase` (`src/deviate/cli/micro.py`) invokes the GREEN agent only when `session.red_commit_sha` is a standing RED-phase failing-test boundary. Empty or whitespace SHA raises `PhaseFailedError` carrying `GREEN_ENTRY_REFUSED`. A `docs(...): add judge feedback for retry` SHA is refused unless it rests on a RED-phase ancestor (TRAIN). After JUDGE `revert_red` / cycle `no_failing_test_adjudicated` / `escalate_to_red`, `_tdd_pre_green_decision` returns `escalate` and `_run_tdd_cycle` re-dispatches RED or raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. It never calls `_run_green_phase` on that path. `_consume_retry_gate_after_red` (called from `_escalate_to_new_red`) consumes `revert_red` only after `_has_red_commit_boundary` is true. `skip_refactor` / bare `COMPLIANCE_PASS` still complete without GREEN via `_NO_FAILING_TEST_FORWARD_ROUTES`. TDD `revert_green` with an empty SHA raises `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING` and must not print `ROLLBACK_FAILED` and proceed.
* **GREEN Rollback Retry Context:** After `revert_green`, the next GREEN prompt includes a `<rollback_context>` block stating that rollback discarded prior committed, uncommitted, and untracked GREEN artifacts. GREEN must verify referenced artifacts on disk and recreate missing files before reporting success.
* **Resumable JUDGE Feedback Commit:** Before attempting the hook-enabled feedback-marker commit, the runner persists the exact task id, feedback text, and feedback source in `SessionState.pending_judge_feedback`. A failed or timed-out hook leaves `red_commit_sha` unchanged and retains this payload. The next explicit task run or `--all` drain selects the task even when its latest ledger status is `FAILED`, retries the same marker commit without rerunning JUDGE, clears the payload only after success, advances `red_commit_sha`, and resumes GREEN with the original feedback.
* **GREEN Retry State-Drift Guard:** A first-pass zero-change GREEN remains valid and proceeds to JUDGE for empty-GREEN `test_quote` classification. On a JUDGE-directed retry, however, if the ledger already records GREEN, `train_feedback` is present, and `_commit_phase()` reports no new commit, `_run_green_phase()` raises `PhaseFailedError` with `GREEN_STATE_DRIFT`. This prevents JUDGE from evaluating feedback-only diffs and requires the operator to verify the existing implementation and reconcile the append-only task ledger.
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
* **GREEN Phase Layer Discipline (mechanical scope, no drift judgment):** GREEN's only invariant is "make the RED test pass via the library/API surface declared in scope." When a RED test cannot be satisfied within that mechanical scope (the test exercises a CLI surface that is out of scope, requires a tool the slice does not own, or depends on a fixture not in the workspace), GREEN emits ``status: FAILURE`` with a concrete ``rationale:`` naming the exact test path and why it cannot be satisfied — it does NOT opine on spec scope, drift, or HITL routing. ``status: "ERROR"`` is reserved strictly for tool/orchestration failure (test_command crash, lint binary missing, subprocess IO error). Spec-scope conflict, slice-boundary violation, and contract drift detection belong to JUDGE, surfaced via the manifest's ``next_action`` (``revert_red`` / ``revert_green`` / ``continue_refactor`` / ``skip_refactor``) and persisted to ``tasks.md`` via ``_append_judge_feedback`` so the next GREEN attempt re-reads it through ``_read_judge_feedback_from_tasks_md``. The runner's ``_is_hitl_escalation`` check stays narrow as a defensive fallback — it ONLY promotes a GREEN manifest to ``HITL_PENDING`` when structured ``contract_drift`` / ``escalates_to`` / ``hitl_options`` keys are present at the top level. Loose-string ``error_kind`` discriminators (``error_kind: contract_drift`` and similar) and free-form ``rationale:`` text describing a scope conflict do NOT trigger HITL escalation — they surface as a plain ``PhaseFailedError`` whose message carries the mechanical rationale. Regression pins: ``tests/test_micro/test_orchestration.py::test_micro_green_phase_mechanical_failure_does_not_escalate_to_hitl`` (runner narrowness) plus the prompt-content pin in the same file.
* **GREEN Mechanical Failure → JUDGE Routing:** When GREEN emits ``status: FAILURE`` with a concrete ``rationale:`` (the mechanical scope-boundary case from the GREEN Phase Layer Discipline paragraph above), the runner does NOT raise ``PhaseFailedError`` and does NOT short-circuit the cycle to FAILED. Instead, ``_run_green_phase`` (src/deviate/cli/micro.py) sets ``session.train_feedback = rationale`` + ``session.failure_kind = "mechanical"``, advances the phase to GREEN via ``force_transition_to``, and returns the session so the TDD loop's existing ``green_tests_failed`` branch routes control to ``_run_judge_phase``. ``_run_judge_phase`` then injects a ``<failure_kind>mechanical</failure_kind>`` discriminator block into the JUDGE prompt that instructs the agent to emit ``verdict: COMPLIANCE_VIOLATION`` + one of three ``next_action`` values (``revert_red`` / ``revert_green`` / ``skip_refactor``) instead of attempting to satisfy the test itself.
* **GREEN Test-Defect Failure → JUDGE Routing:** A second routable failure class. When GREEN observes that the RED test itself is wrong — it asserts behavior the spec does not require, exercises the wrong abstraction, or encodes an assumption that contradicts ``<spec_content>`` / ``<data_model_content>`` — GREEN emits ``status: FAILURE`` with a concrete ``rationale:`` naming the offending assertion and citing the FR/AC it contradicts, plus ``failure_kind: test_defect`` on the manifest. The runner sets ``session.failure_kind = "test_defect"`` and ``_run_judge_phase`` injects a ``<failure_kind>test_defect</failure_kind>`` discriminator block into the JUDGE prompt that pre-decides the routing: ``verdict: COMPLIANCE_VIOLATION`` + ``next_action: revert_red`` (re-run RED with the GREEN rationale as feedback). Test defect has only one sensible outcome — the test itself must be re-authored — so the discriminator intentionally narrows the JUDGE routing vocabulary compared to the mechanical case (no ``revert_green`` / ``skip_refactor`` branch). ``HandoverManifest.failure_kind`` is ``Literal["mechanical", "test_defect"] | None`` (see ``src/deviate/core/agent.py``); ``SessionState.failure_kind`` mirrors it with an additional empty-string default for the no-failure case.
* **Dashboard / Output:** Constructs an `OrchestrationMonitor` (in
  `src/deviate/ui/monitor.py`) wired to a `RunBoard`
  (`src/deviate/ui/pipeline.py`) with `total_tasks` set to the pending count.
* **Input Parameters:**
  * `[task-id]` (Positional: `TSK-NNN-NN` format; omit to auto-select the first
    PENDING task for the active issue; mutually exclusive with `--all`)
  * `--all` (Drain every PENDING task for the active issue)
  * `--profile [full|fast]` (Defaults to `full`):
    * `full` — RED + GREEN + JUDGE + REFACTOR (complete cycle)
    * `fast` — RED + GREEN only (skip JUDGE + REFACTOR)
    * Boolean flags `--no-judge` / `--no-refactor` retained as composable overrides
  * `--agent <name>` (Override agent backend; falls back to `[agent].backend` in
    `.deviate/config.toml`)
  * `--model <id>` (Override default model for RED/GREEN/REFACTOR/EXECUTE phases;
    resolution: phase-specific config &gt; CLI `--model` &gt; default config &gt; backend native;
    JUDGE is excluded from CLI override to preserve model tiering)
  * `--dry-run` (Print the resolved task and exit without dispatching)
  * `--json`, `--quiet`, `--verbose`
  * `--auto` (Spawn the configured agent with the deviatdd skill slash command as
    the prompt instead of running an internal micro phase. Skips the normal
    RED/GREEN/JUDGE/REFACTOR orchestration. The agent runs the skill, which itself
    drives ``deviate micro run`` per task until the queue drains. Agent-agnostic:
    the runner maps the configured backend to its canonical slash command —
    ``/deviatdd`` for Claude Code (which exposes skills under their bare name),
    ``/skills:deviatdd`` for Pi and OMP. Falls back to ``AUTO_NO_SLASH_COMMAND`` +
    exit 1 when the configured backend has no documented slash command form,
    e.g. ``opencode`` / ``droid`` / ``stub`` — operators on those backends must
    invoke the agent manually with the skill installed by ``deviate setup``.)

> **Note on the `last_command` field:** When the orchestrator hands off to
> `micro run --all`, the session's `last_command` is rewritten to
> `micro run [task-id] --all` (i.e. the micro subcommand path, not the
> top-level `deviate run`), so the session always records the most
> specific command that last touched it.

#### `deviate meso run` (Automated Meso Pipeline)

* **Source:** `src/deviate/cli/meso.py` (`_meso_run`, `meso_run_command`)
* **Description:** Automates the per-issue Meso pipeline: SPECIFY (claim) → PLAN → TASKS → IDLE.
  Without `--issue`, it discovers the next unblocked BACKLOG issue. Inside a linked feature
  worktree, it resolves the issue from the branch and resumes idempotently. It fails when
  `blocked_by` dependencies are not COMPLETED unless `--force` is set.
* **Pipeline Steps (in order):**
  1. **Claim (SPECIFY):** Calls `_specify_pre(issue_id, force, dry_run, local)`, which creates a
     linked worktree at `.worktrees/feat/{epic}/{issue}/`, copies `.claude/`, `.opencode/`,
     `.factory/`, `.pi/`, `.omp/` agent skill directories and `.env` (if present) into the
     worktree, runs `mise trust && mise install && mise run setup` (`.env` is now available
     during setup), claims the issue via `claim_issue()`, and commits the claim to the
     worktree's `specs/issues.jsonl`. Default claim (`claim_remote = false` / absent key,
     no `--local`) stays local-only and does not `git push`. When push-as-lock is on
     (`claim_remote = true`, no `--local`) the branch is pushed to origin as a distributed
     lock. If that push is rejected because the `feat/.../NNN-*` name exists,
     `_try_claim_issue` increments the ordinal and retries (cap 3). Collision retry does
     not set `--local`. Non-name-collision push errors still print `PUSH_STDERR` and
     follow `--force` or rollback. Local mode (`--local` or `claim_remote = false` /
     absent key) keeps that worktree and ledger claim and skips the remote-branch
     pre-check and `git push`. `_specify_pre` resolves effective local as `--local` OR
     `claim_remote = false`, so `deviate plan pre` outside a worktree inherits the same rule.
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
  after claim so downstream phase functions find the session. After that copy, the worktree
  session `active_issue_id` is rewritten to the claimed issue so a leftover main-repo id
  does not stick. The session is force-transitioned
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
    the worktree-per-issue model. `--local` does not imply `--no-setup`. Combining
    `--no-setup` with `--local` still skips SPECIFY because `--no-setup` wins for
    setup skipping.
  * `--local` *(optional)* — Claim locally only. Creates the worktree, writes the ledger
    claim, and commits. Skips the remote-branch pre-check and `git push`. Omitted
    `--local` honors `.deviate/config.toml` `claim_remote` (default `false`). Explicit
    `--local` always wins over `claim_remote = true`. Auto-discovery in local mode does
    not treat an origin `feat/{epic}/{issue}` branch as claimed-elsewhere.
* **Worktree Auto-Detect:** When invoked from inside a linked git worktree (``.git``
  is a file containing ``/worktrees/``), the pipeline automatically behaves as if
  ``--no-setup`` were passed: it skips the SPECIFY step, resolves the active issue
  from the current branch's ``feat/{epic}/{issue}`` slug, and continues with PLAN +
  TASKS in the existing worktree. This makes ``deviate meso run`` a safe continuation
  command after re-entering a worktree (e.g. ``cd .worktrees/feat/<epic>/<issue>``
  followed by ``deviate meso run`` resumes the pipeline for that issue). Operators
  who want to force the SPECIFY cycle can pass ``--issue <other-id>`` (which bypasses
  the auto-detect branch entirely) or invoke ``deviate meso run`` from outside the
  worktree.
* **Idempotent Resume:** In an existing linked worktree or with `--no-setup`, `_meso_run`
  validates the canonical issue artifacts before agent dispatch:
  * No `plan.md`: run Plan and Tasks.
  * Valid `plan.md` and no `tasks.md`: emit `MESO_RESUME`, skip Plan, and run Tasks.
  * Valid `plan.md` and non-empty `tasks.md`: emit `MESO_ALREADY_COMPLETE`, skip both agents,
    rewrite worktree `session.active_issue_id` to the claimed issue, preserve ledger progress,
    and return the current worktree path.
  * Existing `plan.md` valid only after repair: when the contract fails solely for a missing `**Verification Mode**:` line, it is auto-filled (`PLAN_MODE_REPAIR`) and treated as valid; a genuinely invalid `plan.md` (missing clauses, bad AO traceability, illegal/duplicated mode) emits `MESO_PLAN_INVALID` and stops without overwrite.
  * Existing empty `tasks.md`: emit `MESO_TASKS_INVALID` and stop without overwrite.
  A fresh claim does not use inherited main-branch artifacts as resume evidence. It runs Plan
  and Tasks in the new worktree.
* **Error Recovery:** Agent non-zero exit (`AgentSubprocessError`) or
  `manifest.status != "PASS"` aborts with `<PHASE>_FAILED`. Re-running from the linked
  worktree uses the idempotent resume rules above. The `UPSTREAM_MISSING` token is not
  emitted by the current implementation.
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
* **Description:** Aggregates tasks from every per-issue append-only ledger at
  `specs/<bucket>/<slug>/tasks.jsonl`. The set of ledgers is derived from the
  `source_file` of each issue in `specs/issues.jsonl`; the `issues/` segment is
  dropped when mapping to the tasks directory (see the Append-Only Ledger
  Protocol in `DeviaTDD-architecture.md`). Each per-issue ledger is parsed
  sequentially and reduced to one record per task id with `COMPLETED` treated
  as terminal (mirrors `_deduplicate_issues`). Outputs a Rich `Table` summary
  (ID, Issue ID, Description, Status, Mode) filtered by `--status`. The
  `--json` flag emits a JSON array; `--quiet` suppresses output.
* **Common Flags:** `--json`, `--quiet`
* **Note:** A stray top-level `specs/tasks.jsonl` is **not** consulted — task
  state lives under each issue directory.


#### `deviate inspect tasks show <TSK-ID>`

* **Source:** `src/deviate/cli/inspect.py` (`tasks_show_command`)
* **Description:** Looks up one task by ID across all aggregated per-issue ledgers (`specs/<bucket>/<slug>/tasks.jsonl`) and emits a single JSON object with `--json`, or a readable record without it. When the latest COMPLETED row carries persisted `evidence` (GH-84 citations + `red`/`green`/`head` SHAs), that field is included so a later human can read the proof after the session is gone. Unknown IDs fail with a parameter error.
#### `deviate inspect issues show <ISS-ID>`

* **Source:** `src/deviate/cli/inspect.py` (`issues_show_command`)
* **Description:** Looks up one issue by ID in `specs/issues.jsonl` and emits a single JSON object with `--json`, or a readable record without it. Unknown IDs fail with a parameter error.
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

#### `deviate review pre [--base <branch>] [--branch <branch>] [--apply]`

* **Source:** `src/deviate/cli/review.py`
* **Description:** Gathers this-issue brief + merge-base diff for Gate 3 review.
  `/deviate-review` **is** the PR review. **Default is comments only** (no edits,
  no `git add`, no commit). Resolves the current `feat/<bucket>/<slug>` issue,
  requires a brief that itself contains named-check tokens (`AC-ADHOC-NNN-NN`,
  `AC-PLAN-NNN`, or `AC-NNN-NN`), and emits exactly `brief incomplete` (exit 1)
  when those tokens are missing — it does not hunt Explore. When the brief is
  complete, computes the unified diff between the merge-base of `--base`
  (default: `main`) and `--branch` (default: `HEAD`), includes `issue_brief_path`
  and `plan_path` (null if absent), and runs a runner-owned plan-AC coverage
  scan (`evaluate_review_coverage` in `src/deviate/core/review_coverage.py`) with
  no agent call. The `uncovered` list is **comment input**, not an apply gate
  and not a merge gate: `coverage_complete` may be false while `status` stays
  `READY`. PENDING, FAILED, and sibling-issue rows do not claim tokens. Missing
  `plan.md` or missing plan tokens are vacuously complete. The skill comments
  (stdout and/or GitHub PR review event `COMMENT` if a PR exists). It must not
  emit `REQUEST_CHANGES` or merge. It must not assume JUDGE already ran.
  `--apply` is **opt-in**: the contract then sets `apply: true` and
  `apply_scope: CRITICAL`. The agent may apply CRITICAL findings only
  (security / data loss / broken build / named-check fail with a concrete FIX)
  and commit only when such a fix landed. Never auto-apply SUGGESTION or
  OPPORTUNITY. Without `--apply`, `apply` is `false` and the agent prints/posts
  comments and stops. There is no always-on STEP 4. `deviate review --apply pre`
  is equivalent to `deviate review pre --apply`.
* **Input Parameters:**
  * `--base <branch>` (Base branch for merge-base computation; default: `main`)
  * `--branch <branch>` (Target branch for self-contained review; default: `HEAD`)
  * `--apply` (Opt-in: apply CRITICAL findings only after comments; default: off)
* **Output Artifacts:** On incomplete brief: the exact line `brief incomplete`.
  Otherwise a JSON contract with `status`, `diff`, `issue_brief_path`, `plan_path`,
  `constitution_path`, `prd_path`, `constitution_warning`, `prd_warning`,
  `base_branch`, `report_exists`, `timestamp`, `uncovered`, `coverage_complete`,
  `apply` (default `false`), `apply_scope` (`CRITICAL` when `--apply`, else null).

#### `deviate review post [content]`

* **Source:** `src/deviate/cli/review.py`
* **Description:** Persists a comments-only review report under `.deviate/review/reports/`.
  Emits `brief incomplete` and exits 1 when this issue's brief has no named checks.
  Does not require `coverage_complete`. Does not stage or commit (`post` is never
  the apply path; apply is agent-driven and only when `--apply` landed a CRITICAL
  fix).
* **Input Parameters:**
  * `content` (Optional markdown report. When omitted, the command reads stdin.)
* **Output Artifacts:** A timestamped `review-report-*.md` file when a named-check brief exists.

---

#### `deviate walkthrough pre [--base <branch>] [--branch <branch>]`

* **Source:** `src/deviate/cli/walkthrough.py`
* **Description:** Gathers the four-look map inputs for THIS issue/PR at HITL Gate 3:
  this issue's brief path, this issue's `plan.md` path (null if absent), the
  merge-base diff, and changed files classified into `test_files` vs
  `production_files`. Does **not** send `constitution_path` or `prd_path` as
  default inputs; those keys appear only when this brief names those files.
  Complements default comments-only `deviate review pre`. The `/deviate-walkthrough`
  skill must emit (a) brief location + this issue's plan AC lines if present,
  (b) test hunks, (c) which production hunks claim which named check, (d) the
  command to run those checks. It must not reimplement, approve, hide hunks,
  tell the human to skip a look, auto-edit, or apply fixes.
* **Input Parameters:**
  * `--base <branch>` (Base branch for merge-base computation; default: `main`)
  * `--branch <branch>` (Target branch for self-contained walkthrough; default: `HEAD`)
* **Output Artifacts:** JSON contract with `diff`, `issue_brief_path`, `plan_path`,
  `base_branch`, `commit_messages`, `changed_files`, `changed_files_count`,
  `test_files`, `production_files`, `timestamp`. Optional `constitution_path` /
  `prd_path` only when the brief names those paths.
* **Token Budget:** Contract is a map, not a curator — file lists + diff, no
  per-file AST parsing. The agent reads this issue's brief + named checks + this diff.

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
└── {FEATURE_SLUG}/           # Feature workspace bucket (e.g. ``001-...``, ``002-...``, ``adhoc``)
    ├── explore.md            # Raw codebase context (cheap scan - what exists)
    ├── design.md             # Architectural decisions and trade-offs
    ├── data-model.md         # Entity relationships, schemas, data flow
    ├── prd.md                # Product requirement documents
    ├── spec.md               # Functional contract ("What & Why" system bounds) — deprecated, shard now embeds specs in issues
    ├── issues/               # Issue source markdown files (``source_file`` in ``issues.jsonl``)
    │   └── {ISSUE_ID}.md     # Per-issue markdown: scope, Gherkin AC, edge cases
    └── {ISSUE_ID}/           # Per-issue workspace (sibling to ``issues/``, not nested)
        ├── spec.md           # Issue-level functional specification (shard-produced, with Gherkin AC)
        ├── plan.md           # Per-issue localized research report (deviate-plan output)
        ├── tasks.md          # Task decomposition (human-authored, what/why/how)
        └── tasks.jsonl       # Per-issue append-only task event ledger (CLI-managed)

src/deviate/
├── __init__.py
├── main.py                   # Entry point: from .cli import cli; app = cli
├── cli/
│   ├── __init__.py           # Main CLI: deviate init, typer command registration
│   ├── _common.py            # Shared helpers (_halt, _extract_epic_num, with_json_quiet)
│   ├── macro.py              # explore, research, prd, shard (pre/post), macro run
│   ├── meso.py               # specify, tasks, pr (pre/post/run), meso run
│   ├── micro.py              # red, green, judge, refactor, execute, e2e, hotfix, run
│   ├── prune.py              # prune pre/post (manual honeycomb test thinning)
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
│   ├── epic.py               # allocate_feature_bucket, discover_epic, remote-aware feat ordinals
│   ├── issues.py             # claim_issue
│   ├── prune.py              # manual honeycomb keep/drop inventory + apply
│   ├── prd.py                # extract_prd_requirements
│   ├── profile.py            # ExecutionProfile (full/fast), resolve_profile()
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
│   ├── core/                 # shared prefix injected by load_template() + compose_command_body()
│   │   ├── core.md             # universal invariants (all phases)
│   │   ├── macro-shared.md / meso-shared.md / micro-shared.md   # layer preambles
│   │   ├── lifecycle-auto.md / lifecycle-manual.md             # mode lifecycle blocks
│   │   └── style-ste.md        # ASD-STE100 Simplified Technical English directive
│   ├── auto/                 # canonical per-phase middle bodies — the single source of truth
│   │   ├── explore.md, research.md, prd.md, shard.md, tasks.md
│   │   ├── red.md, green.md, judge.md, refactor.md, plan.md, execute.md
│   │   └── (11 overlapping phases above)
│   ├── governance/           # claudemd_seed.md, agents_seed.md
│   └── commands/             # 23 DeviaTDD slash commands (flat *.md): 11 derive their body from auto/{phase}.md + a manual overlay ({execute, explore, green, judge, plan, prd, red, refactor, research, shard, tasks}); 12 hand-maintained commands-only prompts (adhoc, constitution, e2e, hotfix, html, init, merge, pr, prune, review, triage, walkthrough)
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
{"id": "TSK-001-01", "issue_id": "001-001", "description": "create_jwt_validator_class", "status": "PENDING", "execution_mode": "TDD"}
{"id": "TSK-001-01", "issue_id": "001-001", "description": "create_jwt_validator_class", "status": "RED"}
{"id": "TSK-001-01", "issue_id": "001-001", "description": "create_jwt_validator_class", "status": "GREEN"}
{"id": "TSK-001-01", "issue_id": "001-001", "description": "create_jwt_validator_class", "status": "COMPLETED"}
{"id": "TSK-001-02", "issue_id": "001-001", "description": "integration_token_flow", "status": "PENDING", "execution_mode": "E2E"}
```

---

### 2. Prompt Matrix & File Generation Lifecycle

Macroscopic commands are user-facing interactive slash commands registered as prompt files
in agent runtime directories during `deviate setup`. Commands live in `src/deviate/prompts/commands/`
and are installed to `.{agent}/commands/<name>.md` per workspace (or `.pi/prompts/<name>.md` for Pi).

| Client Command Trigger | Responsible Persona Role | Targets Created / Mutated | Internal CLI Endpoints | Action Logic Steps |
| --- | --- | --- | --- | --- |
| `/deviate-explore` | Context Scanner (Cheap) | `specs/{FEATURE_SLUG}/explore.md` | `deviate feature create`, `deviate explore pre/post` | 6 steps: feature create, constitution validate, bucket allocate, codebase scan (plus sibling-flow inventory when a nearest user flow exists), write explore.md, commit |
| `/deviate-research` | Architect (Expensive) | `specs/{FEATURE_SLUG}/design.md`, `data-model.md` | `deviate research pre/post` | 5 steps: read explore.md, write the floor then attack it in one agent / two ordered jobs (no sequential sub-agent spawn), produce design.md + data-model.md (schema = floor only), commit. Existing constitutions stay read-only except greenfield bootstrap. |
| `/deviate-prd` | Product Owner Proxy | `specs/{FEATURE_SLUG}/prd.md` | `deviate prd pre/post` | 4 steps: read design.md + data-model.md, halt on `UPSTREAM_INCONSISTENT` / `SCOPE_DRIFT`, synthesize floor + promoted extras (unused Recommended/Deferred stay out of scope), write prd.md, commit |
| `/deviate-shard` | Decomposition Engine | `specs/{FEATURE_SLUG}/issues/{ORDINAL}-{slug}.md` (filenames use the per-epic ordinal; the ledger id is `{epic-prefix}-{ORDINAL}`, e.g. `002-001`) | `deviate shard pre/post` | 5 steps: read prd.md, identify vertical slices, validate granularity, create issue stubs with `AO-NNN` acceptance outlines (no Gherkin), register in ledger. PRD/Shard/Adhoc halt with `GHERKIN_LEAK_DETECTED` on bold `**Given**`/`**When**`/`**Then**`; final Gherkin belongs to Plan. New issues emit `{epic-prefix}-{ordinal}` ids; legacy `ISS-NNN` ids still resolve. |
| `/deviate-adhoc` | Condensed Scoper | `specs/adhoc/` | `deviate adhoc pre/post` | 8 steps: complexity gate, codebase scan, PRD append, issue generation with remote-aware `NNN` (`max(origin ledger, current ledger, remote feat/adhoc/<NNN>-*) + 1`; `ISS-ADH-NNN` and `ISS-NNN` are one series; local-only branches do not reserve), ledger registration, commit, Gherkin-leak guard |
| **[REMOVED]** | --- | --- | --- | HITL Gate 2 (post-Tasks `deviate meso approve` approval) was removed. The system never blocks on human approval; `deviate run` chains meso into micro end-to-end. Plan and Tasks still commit authored artifacts to the worktree, but the human can review them on their own schedule without gating execution. |
| `/deviate-plan` | Localized Researcher / Contract Author | `specs/{FEATURE_SLUG}/{ORDINAL}-{slug}/plan.md` | `deviate plan pre/post` | 5 steps: read issue (intent + outlines), scan current codebase, analyze prior issues, author authoritative `## Acceptance Contract` with `AC-PLAN-NNN` Given/When/Then scenarios (Source Outline, Upstream Traceability, Current-Code Evidence), commit. The contract is authoritative for Tasks, RED, and JUDGE. |
| `/deviate-tasks` | Technical Lead | `specs/{FEATURE_SLUG}/{ORDINAL}-{slug}/tasks.md` | `deviate tasks pre/post` | 6 steps: consume issue intent + authoritative `plan.md` Acceptance Contract, decompose into `AC-PLAN-NNN`-aligned tasks, assign execution modes (`Verification_Batch` is locked to `execution_mode: IMMEDIATE` / EXECUTE — never TDD; incl. a terminal `[E2E]`/`Verification_Batch` `IMMEDIATE` task that authors `tests/e2e/` user-facing scenarios and runs last when a user-facing workflow exists; other types still pick TDD vs IMMEDIATE), encode DAG deps, halt on `PLAN_ACCEPTANCE_CONTRACT_MISSING`/`INVALID` (no legacy issue Gherkin fallback), commit. After Tasks, `deviate run` chains directly into `deviate micro run --all` — no human-approval step. |
| `/deviate-walkthrough` | Four-Look Map | (none — conversation only) | `deviate walkthrough pre/post` | 4 looks: brief + plan AC lines, test hunks, production-hunk→named-check claims, check command. HITL `ask` per look. Must not approve, hide hunks, skip a look, or auto-edit. |
| `/deviate-review` | Gate 3 PR Reviewer | advisory `.deviate/review/reports/` (never staged) | `deviate review pre/post` (`--apply` opt-in) | Default: comments only (stdout and/or GitHub `COMMENT`). Named-check checklist + test-weakening + this-issue cross-task drift. `brief incomplete` when named checks are missing. No always-on apply; no `REQUEST_CHANGES`; no merge. `--apply` may land CRITICAL-only fixes (security / data loss / broken build / named-check fail with a concrete FIX) and commit only if a CRITICAL fix landed. |
| `/deviate-html` | HTML Author (manual, on-demand) | (none — consumes existing `.md` files) | `deviate html <phase>` *(for `prd`, `deviate html prd --bucket <slug>` targets a specific epic when more than one owns a `prd.md`; `--force` overwrites an existing `.html`)* | 5 steps: read phase `.md`, emit starter scaffold via `deviate html`, author HTML body section-by-section using the full HTML surface (diagrams, tables, callouts — no markdown→HTML auto-translation), validate lockstep with the source markdown (FR/AC tokens), commit `.html` alongside the `.md` per STEP_5. **Manual-only** — phase prompts (`/deviate-prd`, `/deviate-plan`, `/deviate-research`) carry an optional pointer but never auto-invoke this command. The user decides when to ship the HTML counterpart (typically end-of-session, or per-phase immediately after the markdown lands). |

> **Deprecation Notice:** `/deviate-specify` is deprecated as a standalone acceptance-authoring step. Shard now emits issues carrying `AO-NNN` acceptance outlines only; Plan authors the current-code-informed Gherkin contract. The `/deviate-specify` skill remains for backward compatibility but redirects to the new workflow (Plan owns Gherkin). This replaces the older "Meso-Layer Restructuring (ADHOC-003)" wording that placed spec detail in Shard.

**Session Continuity Strategy:**
- **Macro layer** (explore -> research -> prd -> shard): Sequential CLI invocations, each persisting session to `.deviate/session.json`. Phase transitions validated by `SessionState`. Shard now emits issue outlines only; final Gherkin lands in Plan.
- **Meso layer** (`/deviate-plan` -> `/deviate-tasks`): Single continuous LLM session per issue. The system prompt, tool definitions, issue content, and `constitution.md` form a stable prefix cached after turn 1. Tasks now reads the authoritative `plan.md` Acceptance Contract rather than the issue's own Gherkin.
- **Gate 2 (REMOVED):** The post-Tasks `deviate meso approve` hard gate was removed. The system never blocks on human approval. Plan and Tasks still commit authored artifacts to the worktree, but review happens out-of-band without gating execution.
- **Micro layer** (RED -> GREEN -> JUDGE -> REFACTOR): Task execution reuses the same in-process state via `force_transition_to()`. Dispatch through `deviate micro run <task-id>` or `deviate micro run --all`; no approval prerequisite.
---

### 3. Issue & Task Status Models

#### IssueRecord (Pydantic -- `src/deviate/state/ledger.py`)

| Field | Type | Description |
|-------|------|-------------|
| `issue_id` | `str` | Unique ID — `<epic-prefix>-<ordinal>` for new work in numbered epics (e.g. `002-001`); adhoc uses one series (`ISS-NNN` / `ISS-ADH-NNN`); next adhoc `NNN` includes the origin ledger and remote `feat/adhoc/<NNN>-*` refs |
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
| `evidence` | `TaskEvidenceBundle \| None` | Optional. Present only on the `COMPLETED` row (GH-84). Default absent so legacy rows still parse. `TaskEvidenceBundle` holds `items` (`list` of `{ac, test_path, test_quote, impl_path, impl_quote}` copied from the runner-validated `HandoverManifest.evidence`) plus commit provenance `red` (`session.red_commit_sha` when present), `green`, and `head` (`HEAD` at the COMPLETED write). Earlier RED/GREEN/JUDGE rows stay lean. `.deviate/` session files are not the proof store. |
| `judge_action` | `Literal["revert_red", "revert_green"] \| None` | Optional. Present on the post-reset JUDGE revert row. Omitted on earlier rows. |
| `judge_feedback` | `str \| None` | Optional. The reason string persisted with `judge_action`. Omitted when empty. |
| `head_sha` | `str \| None` | Optional. Full SHA of HEAD **before** the blast-radius reset (the discarded GREEN / RED+GREEN tree). |
| `reset_to` | `str \| None` | Optional. Full SHA the runner reset to (`red_commit_sha` or its parent). |
| `recovery_ref` | `str \| None` | Optional. `tmp/deviate-agent-work/<task>/attempt-<N>` from `_preserve_agent_work`. Empty when HEAD already equaled the boundary (nothing preserved). |


#### Append-Only Ledger Protocol

All state transitions are append-only. No existing line is ever modified or overwritten.
- `append_issue_transition()`: Idempotent on `(issue_id, status)` compound key
- `append_task_transition()`: Idempotent on `(id, status)` compound key
- `append_task_event()`: always appends (JUDGE revert may repeat `PENDING` / `RED`)
- `_append_record()` / `_append_with_compound_key()`: Use `fcntl.flock` for file-level
  locking on platforms that support it. If the ledger is non-empty and the last
  line has no trailing newline, a leading `\n` is written before the new record
  so two JSON objects never share a line. Every successful write leaves a trailing
  newline. `claim_issue` writes through `append_issue_transition` (not a raw `"a"`
  append).
- Canonical state: Issues derived bottom-up (latest entry per `issue_id`); tasks derived
  sequentially (latest entry per `(id, status)` compound key)


#### SessionState (Pydantic -- `src/deviate/state/config.py`)
| Field | Type | Description |
|-------|------|-------------|
| `current_phase` | `str` (default `"IDLE"`) | Current phase in the TDD cycle; one of `IDLE`, `RED`, `GREEN`, `JUDGE`, `REFACTOR` (see `_VALID_PHASES`) |
| `active_issue_id` | `str` (optional) | Issue the session is bound to (`--issue` selection survives across `--all` runs) |
| `last_command` | `str` (default `""`) | Last CLI command the user invoked (for resume/messaging) |
| `train_feedback` | `str` (default `""`) | Last failure feedback injected as `<train_feedback>` into the next GREEN prompt. Escalate RED receives a short `previous cycle failed because …` note, not the raw GREEN dump. |
| `green_attempts` | `int` (default `0`) | GREEN-train count against the standing RED contract; max 3; persist via `save()` to `.deviate/session.json`; copied through `transition_to` / `force_transition_to` |
| `red_attempts` | `int` (default `0`) | RED-escalate count for the current task; max 3; `TRAIN_EXHAUSTED` after three escalates; persist via `save()`; copied through transitions |
| `failure_kind` | `Literal["", "mechanical", "test_defect", "no_failing_test"]` (default `""`) | Discriminator set by GREEN on failure-class routing, or by RED no-failing-test adjudication; cleared on each GREEN exit (`""` = clean run, `mechanical` = scope-boundary failure, `test_defect` = RED test itself wrong, `no_failing_test` = RED test command exited 0 / collected no tests / resolved to no command) |
| `judge_rejected` | `bool` (default `False`) | `True` while the JUDGE verdict on the current cycle is a rejection |
| `pending_judge_action` | `str` (default `""`) | The JUDGE-supplied routing directive (`revert_red`, `revert_green`, `continue_refactor`, `skip_refactor`, `proceed_to_refactor_no_diff`); consumed by `_finish_tdd_cycle` after the JUDGE phase hands off. A forward route is valid only for the task + RED SHA recorded in `judge_task_id` / `judge_red_commit_sha` (GH-148). |
| `red_commit_sha` | `str` (default `""`) | SHA of the task's RED-phase failing-test commit. GREEN entry (`_require_green_entry_red_sha`) refuses empty or whitespace SHA (`GREEN_ENTRY_REFUSED`) and refuses a `docs(...): add judge feedback` SHA that does not rest on a RED-phase ancestor. A `test(...): RED phase` subject, a TRAIN feedback SHA that rests on that ancestor, and any other resolvable non-empty SHA may enter GREEN. The TDD JUDGE runner reads it and threads it into `_execute_rollback(boundary_sha=..., task_id=..., attempt=...)` on `revert_green`. After a TRAIN feedback commit, this field may point at that docs-feedback SHA (rollback / GREEN-entry boundary). The injected JUDGE diff does not use that SHA as the range base: `_resolve_judge_diff_base` walks back through `_JUDGE_FEEDBACK_SUBJECT_RE` subjects to the RED-phase failing-test commit and diffs `{red_sha}^..HEAD` (GH-88 / GH-90). Each phase records its own boundary only after the commit lands. The runner no longer reads this field implicitly inside `_execute_rollback`; the boundary MUST be supplied by the caller. EXECUTE JUDGE uses `pre_execute_sha` (captured before the first EXECUTE attempt) instead. |
| `judge_task_id` | `str` (default `""`) | Task id a JUDGE forward route belongs to. `_apply_judge_verdict` stamps it when setting `continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff`. Empty on pre-fix `session.json` files. |
| `judge_red_commit_sha` | `str` (default `""`) | `red_commit_sha` the forward route was judged against. A mismatch with the standing RED SHA, or an unbound leftover once a RED SHA exists, clears the forward route so GREEN/JUDGE run (GH-148). |
| `timestamp` | `datetime` (auto-set on each transition via `force_transition_to`/`transition_to`) | Wall-clock record of last phase change |


#### JUDGE `next_action` Routing Table

`HandoverManifest.next_action` (`src/deviate/core/agent.py`) carries the JUDGE agent's
decision on how to route the runner. Five values. TDD `_run_judge_phase` runs a
mechanical evidence gate on forward PASS routes (`continue_refactor`,
`skip_refactor`, `proceed_to_refactor_no_diff`, and legacy PASS) before it honors
the action. EXECUTE `_run_execute_phase` and IMMEDIATE judge stay ungated.

| `next_action` | Required verdict | Runner behavior |
|---|---|---|
| `revert_red` | `COMPLIANCE_VIOLATION` (or any) | Discard this task's GREEN **and** its RED. Reset to `red_commit_sha^` (the parent of the RED commit, defended by a subject-match regex; logs `PRE_RED_AMBIGUOUS` if the parent is not a RED-phase convention). **After** that reset, `_commit_judge_feedback_and_advance` appends a `tasks.jsonl` row (`judge_action=revert_red`, `judge_feedback`, status `PENDING`) plus the `tasks.md` Judge Feedback bullet and commits both in one `docs(<tid>): add judge feedback for retry` commit (`git add` those paths only; not `session.json`). Clear `session.red_commit_sha` so RED re-anchors. Escalate now: reset `green_attempts` to 0, increment `red_attempts`, persist both on `.deviate/session.json`, and dispatch a retry RED with a short `previous cycle failed because …` note in `train_feedback` (not the raw GREEN dump). Before persist, the runner strips discarded-commit `path:line` citations from JUDGE feedback (GH-103); rollback SHA selection is unchanged. The next `INVOKE_AGENT` is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. It never invokes GREEN while `session.red_commit_sha` is empty. `TRAIN_EXHAUSTED` prints after three RED escalates. Used when the test itself is wrong. |
| `revert_green` | `COMPLIANCE_VIOLATION` (default on violation when field omitted) | Discard GREEN, preserve RED. Reset to `red_sha`, **then** append a feedback commit past RED that contains both the `tasks.jsonl` revert row (`judge_action=revert_green`, status `RED`) and `tasks.md` Judge Feedback. Advance `session.red_commit_sha` to that commit only when the pre-call SHA is already a RED-phase failing-test commit. Transition to GREEN with feedback in `train_feedback` after stripping discarded-commit `path:line` citations (GH-103). The previous-round feedback commit is preserved so a second rollback only kills the subsequent GREEN. Empty `session.red_commit_sha` is fatal: raise `PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING`. Do not print `ROLLBACK_FAILED`, do not stamp a docs-feedback SHA, and do not train GREEN. |
| `continue_refactor` | `COMPLIANCE_PASS` (or any) | Skip the rollback (GREEN is intact). Set `pending_judge_action="continue_refactor"`. `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`. A clean `COMPLIANCE_PASS` that omitted `next_action` or emitted a revert (`revert_red` / `revert_green` / legacy `revert_to_red`) is coerced to this route (or `skip_refactor` when `--no-refactor`). A `REFACTOR NOTE:` in `train_feedback` is kept as REFACTOR-phase `{train_feedback}` and is not a `JUDGE_REJECTED` (GH-158). |
| `skip_refactor` | `COMPLIANCE_PASS` (or any) | Skip the rollback. Set `pending_judge_action="skip_refactor"`. `_finish_tdd_cycle` marks the task `COMPLETED` and returns to `IDLE`, regardless of `--no-refactor`. A later `_append_status_transition(..., "COMPLETED")` is a no-op when the ledger already has COMPLETED for this task (GH-146); the COMPLETED evidence gate runs only on the first write. |
| `proceed_to_refactor_no_diff` | `COMPLIANCE_PASS` (or any) | Forward route for the empty-diff sign-off case. Set `pending_judge_action="proceed_to_refactor_no_diff"`. `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`. REFACTOR's commit + COMPLETED transition is the only way to terminate a slice whose git diff is empty (RED-only deliverable, fixture file, generated types, doc-only slice, or any task whose production-code scope is intrinsically nil). Distinct from `continue_refactor` (signals a substantive refactor pass on a non-empty diff). |

**Empty-diff sign-off:** `proceed_to_refactor_no_diff` (`src/deviate/cli/micro.py::_run_judge_phase`) is the forward-route escape for slices whose production-code scope is intrinsically nil — RED-only deliverable, fixture file, generated types, doc-only slice, or any task whose `failure_kind: mechanical` rationale asserts "no production code expected." The TDD evidence gate still requires a dirty-diff `test_quote` and omits `impl_quote`. The JUDGE-side responsibility is to emit the action on a `COMPLIANCE_PASS` verdict when the in-scope rationale is valid but the production diff cannot grow. The action lands the task at REFACTOR's no-op commit + COMPLETED transition in one step; unmatched empty-GREEN PASS does not COMPLETE.

**TDD mechanical evidence gate:** `HandoverManifest.evidence` is a first-class list of nested citations (`ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`) in `src/deviate/core/agent.py`. After `_coerce_judge_action`, TDD `_run_judge_phase` (`src/deviate/cli/micro.py`) resolves this task's required `AC-PLAN-NNN` tokens via `resolve_task_ac_tokens` (`src/deviate/core/judge_evidence.py`) and passes that list as `required_tokens` to `evaluate_judge_evidence`. First hit wins: non-empty `TaskRecord.acceptance_criteria` `criterion_id`s; else `AC-PLAN-NNN` tokens named in this task's `tasks.md` card after dropping `**Judge Feedback**` bullets and their continuation lines; else no AC tokens. Auto `_build_auto_prompt("judge")` injects that same stripped card as `{task_content}` (GH-118 / GH-150); `_task_card_text` still returns the raw card for token resolution, GREEN `<persisted_judge_feedback>`, and file-list parsing. Sibling cards are never injected. The gate does not fall back to every token in `<authoritative_acceptance_contract source="plan.md">`. Omitting a later-shard plan token is legal at JUDGE. Auto and manual judge prompts require `evidence` only for the resolved task tokens. Quotes must copy from the already-built `<diff>` (`git diff <red>^..HEAD` where `<red>` is `_resolve_judge_diff_base(session.red_commit_sha)` — the RED-phase failing-test commit after walking back through `docs(...): add judge feedback for retry` subjects — plus dirty `git diff HEAD` and untracked `--no-index` hunks) or allowed HEAD files. ISS-ADH-020 quote checks still apply to that task set: missing this-task tokens, empty quotes, hallucinated paths, quotes below the uniqueness floor (≥ 12 non-whitespace characters, or the full added line if shorter), or quotes that are not exact substrings of the named file hunk rewrite the action to `revert_green` with runner-authored feedback in the `JUDGE_AGENT_NO_FEEDBACK` family. When the judge already emitted `train_feedback` or `violations`, persist that text (after the GH-103 citation strip) instead of replacing it with the generic missing-evidence string (GH-102). The task does not COMPLETE. `skip_refactor` on the already-exists path may quote HEAD file contents for this-task tokens; a named test file absent on disk fails. On a test-bearing TDD already-exists claim, every declared `files` / `test_file` path (and evidence `test_path`) must appear in `_assemble_judge_injected_diff` or `_evidence_head_contents`. The membership check runs even when the resolved set has no `AC-PLAN-*` tokens. Empty declared files remain a RED defect, not a COMPLETE. Tasks with no resolved `AC-PLAN-*` tokens may emit empty evidence quotes, but they still need named present test paths. `COMPLIANCE_VIOLATION` skips the quote gate. After the gate returns no feedback and the action is a completion path (`skip_refactor` / bare `COMPLIANCE_PASS` / post-REFACTOR complete / adjudicated already-exists), `_append_status_transition(..., "COMPLETED")` copies the validated `HandoverManifest.evidence` onto that COMPLETED `TaskRecord` as `evidence.items` and stamps `red` / `green` / `head` from `session.red_commit_sha` and `HEAD` (GH-84). TDD complete fail-closes when the injected plan contract has `AC-PLAN-NNN` tokens and the persisted bundle is missing or does not cover them — the same `evaluate_judge_evidence` matcher, with `use_head=True` so quotes resolve against HEAD at the COMPLETED write. Plans with no `AC-PLAN-*` tokens may complete with empty evidence. The COMPLETED evidence gate runs only on the first COMPLETED write; `_append_status_transition(..., "COMPLETED")` is a no-op when the task is already COMPLETED (GH-146). EXECUTE, IMMEDIATE, and DIRECT judge paths stay ungated.

**Feedback-commit timeout:** The `revert_green` step's "append a feedback
commit past RED" runs `_commit_judge_feedback_and_advance`
(`src/deviate/cli/micro.py`), which executes a `git commit` that inherits
the active repository's configured pre-commit hooks (resolved via
`core.hooksPath` and `.git/hooks/`). The orchestrator bounds this commit
with `JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS = 300` (defined in
`src/deviate/core/_shared.py`). Observed hook chains on some projects
can exceed 30s; the constant gives them room to complete while still
detecting a genuine hang. A `subprocess.TimeoutExpired` handler wraps
the commit and raises `PhaseFailedError` so a stuck hook chain surfaces
as a documented phase failure rather than a raw traceback. Operators
diagnose a timeout by inspecting the active repository's configured
Git hooks.

Unknown `next_action` values are logged (`JUDGE_UNKNOWN_ACTION`) and the runner falls
back to the legacy verdict-based default (rollback on violation, continue on pass).

**Runner-level override on `failure_kind=test_defect`:** When `_run_judge_phase`
(`src/deviate/cli/micro.py`) routes a JUDGE manifest whose `failure_kind ==
"test_defect"` against a `COMPLIANCE_VIOLATION` verdict, the runner-level
override in `_coerce_judge_action` (`src/deviate/cli/micro.py`) forces
`next_action="revert_red"` regardless of what `next_action` the agent declared
or omitted. The override reflects a contract invariant: when the RED test itself
is wrong, the runner must restart RED with the GREEN's rationale injected, not
loop back into GREEN with the same test. `_coerce_judge_action` accepts a
keyword-only `failure_kind` parameter (default `""`) and is the single source of
truth for the override (`test_defect` / `no_failing_test` on a violation map to
`revert_red`; the 3/3 caps from ISS-ADH-017 stay). After GREEN PASS
(`failure_kind` empty / not `mechanical`), a `COMPLIANCE_VIOLATION` with
structured Test Integrity (`violations[].category` matching Test Integrity,
including `Test Integrity Violation`, and/or `evaluation.test_integrity: FAIL`)
also forces `revert_red` even when the agent omitted `next_action` or set
`revert_green`. Honest-test implementation/scope gaps stay `revert_green`.
Mechanical overlay keeps the agent's three-way choice. The runner does not
parse `train_feedback` for routing. `_run_tdd_cycle` honours
`pending_judge_action == "revert_red"` (set by JUDGE or the override) by
escalating now: reset `green_attempts` to 0, increment `red_attempts`, persist
both on `.deviate/session.json`, dispatch `_run_red_phase(task, ...,
bypass_phase_done=True)`, and `continue`-ing the loop. The next `INVOKE_AGENT`
is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. It never
invokes GREEN while `session.red_commit_sha` is empty. The bypass preserves the
append-only ledger — a
fresh RED record appends rather than rewriting the previous one — and a short
`previous cycle failed because …` note in `session.train_feedback` is threaded
into the retry RED prompt so the agent sees why the previous cycle failed, not
the raw GREEN dump. `TRAIN_EXHAUSTED` prints only after three RED escalates.
`revert_red` judgments on `COMPLIANCE_PASS`
verdicts do NOT trigger the override; JUDGE's outcome is final on PASS.

There is no interactive prompt; the manifest is the source of truth. A future `--judge-action`

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
| `/deviate-html` | V4 Pro | Single invocation | One-shot — default per `deviate-html.md` Tier Classification; per-phase fallback applies (`/deviate-html architecture` / `domain-model` / `flows` may use Qwen thinking for diagrammatic reasoning; `/deviate-html prd` may use Qwen thinking for structured spec rendering) |

The `AgentBackend` class (`src/deviate/core/agent.py`) supports `opencode`, `claude`,
`droid`, and `pi` backends with configurable timeout. Output is parsed as YAML
`HandoverManifest`. Pi uses print mode (`pi -p`) by default and accepts the
`--model <id>` CLI flag (the `provider/model` string from `[models]` is passed
verbatim). After that prefix, default Pi spawn adds `--tools read,bash,edit,write`, `--no-skills`, and optional `--skill` to
`.pi/skills/deviatdd/SKILL.md` when that file exists. The first
`tool_count_limit` or `unsupported_tool_schema` line aborts the child.
`_invoke_agent` logs `AGENT_ERROR` with those tokens. RPC mode
(`pi --mode rpc --no-session`) is opt-in via `agent.pi_rpc = true` in
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
