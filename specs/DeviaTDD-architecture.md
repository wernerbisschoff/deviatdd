# DeviaTDD: Dual Engine Verification Infrastructure for Agentic Test-Driven Development
## Core Architecture, Lifecycle, and Engineering Specification

---

## 1. Architectural Overview & Philosophy
The architecture operates as a hierarchical lifecycle that shifts from human-driven macroscopic scoping to machine-orchestrated, deterministic microscopic execution loops. It is founded on the principle that Large Language Models (LLMs) are probabilistic, optimization-seeking actors that require structured infrastructure containment rather than implicit alignment trust. First-hour setup lives in `README.md`; the research-backed rationale for why each layer, gate, ledger, and TDD phase exists lives in `docs/rationale.md`.

```plaintext
                          ┌──────────────┐
                          │ /deviate-adhoc│  (complexity gate: low/medium only)
                          │ Condensed    │
                          │ E+P+S→ Issue │  (acceptance outline; no Gherkin)
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ specs/adhoc/ │ → single issue, prd.md, issues.jsonl
                          └──────┘

[ MACRO LAYER: Scoping ]    Explore → Research → PRD → Shard
                                                         │ acceptance outlines
                                                         ▼
[ MESO LAYER: Contracts ]    Plan (final Gherkin) → Tasks ─────────► Micro
                                                                  │
                                                                  ▼
[ MICRO LAYER: TDD Loop ] ──> Red ──> Green ──> Judge/Train ──> Refactor
                                │  ▲    ▲                  ▲     │
                                ▼  │    │                  │     │
                                   │    │  next_action on   │     │
                                   │    │  HandoverManifest │     │
                                   │    │  (5-way routing)  │     │
                                   │    │                  │     │
              ┌────────────────────┘    └──────────────────┘     │
              │  Green → Judge → Green loop (TRAIN):             │
              │  JUDGE_REJECTED → git reset --hard <red_sha>      │
              │  + git clean -fd + feedback commit + advance      │
              │  session.red_commit_sha → force_transition       │
              │  ("GREEN") → re-run GREEN with <train_feedback>  │
              │  injected (green_attempts max 3, then escalate)  │
              │                                                   │
              │  next_action=revert_red → escalate now:       │
              │  red_commit_sha^, green_attempts=0,              │
              │  increment red_attempts, force_transition("RED") │
              │  TRAIN_EXHAUSTED after 3 RED escalates           │
              │  next_action=continue_refactor → no rollback,    │
              │  pending_judge_action → _finish_tdd_cycle         │
              │  enters REFACTOR regardless of --no-refactor      │
              │  next_action=proceed_to_refactor_no_diff → no    │
              │  rollback, pending_judge_action → _finish_tdd_   │
              │  cycle enters REFACTOR regardless of --no-       │
              │  refactor (empty-diff sign-off; GREEN had         │
              │  nothing to do)                                  │
              │  next_action=skip_refactor → no rollback,         │
              │  pending_judge_action → _finish_tdd_cycle         │
              │  marks COMPLETED and stops                       │
[ MICRO ALTERNATE ]      /deviate-execute (direct: boilerplate, config, trivial)
                          → skips TDD cycle; runs its own JUDGE pass
```

---

## 1.5 Non-Goals: What DeviaTDD Is Not

To maintain strict operational focus and establish explicit boundaries of responsibility, DeviaTDD defines the following items as out-of-scope:

* **Not an Agent Substrate Optimizer:** This framework does not attempt to solve the fundamental reasoning, planning, or context-handling limitations of underlying LLM models. If an execution agent aggressively deviates from its instructions, hallucinates runtime workarounds, or behaves erratically, it is categorized as a failure of model capability rather than an infrastructural flaw.
* **Not a Kernel-Level Sandbox Engine:** DeviaTDD does not implement operating system-level virtualization, container runtimes, or syscall write blocking to actively intercept filesystem manipulation during execution. Instead, it relies on deterministic Git-ledger audits and target-path diff monitoring to passively catch, reject, and roll back invalid agent states.
* **Not a Cost-Optimized Prototyping Utility:** Agentic software verification with multi-stage evaluation loops is inherently token-expensive. DeviaTDD does not prioritize absolute token reduction at the expense of governance. Every validation cycle is treated as a necessary investment for maintaining long-term code integrity.
* **Not an Autonomous, Closed-Loop Software Factory:** This framework completely rejects the premise of unsupervised, self-validating AI development systems. DeviaTDD is explicitly anchored on structured Human-in-the-Loop (HITL) specification boundaries and contract alignment gates.
* **Not a Markdown→HTML Auto-Renderer:** Spec HTML pages (`plan.html`, `prd.html`) are authored by the agent running the phase, not auto-translated from the corresponding `.md` files. Auto-translation caps the HTML surface at what CommonMark can express; agent authoring lets the page carry diagrams, ER graphs, sequence diagrams, and layout primitives that markdown cannot. The `deviate html <phase>` CLI subcommand emits an empty starter scaffold (section anchors + `TODO` placeholders + the canonical stylesheet); the agent fills in the body from the `.md` content using the full HTML surface. `deviate html prd --bucket <slug>` targets a specific epic when more than one owns a `prd.md` (the plain form exits `HTML_AMBIGUOUS_PRD` on multiple candidates). **HTML authorship is a manual, on-demand step** owned by the `/deviate-html` slash command (`src/deviate/prompts/commands/deviate-html.md`) — the phase prompts (`/deviate-prd`, `/deviate-plan`, `/deviate-research`) carry an optional pointer to it but never auto-invoke it. The user decides when to ship the HTML counterpart for a given phase.

---

## 2. Hierarchical Architectural Layers

### 2.1 The Macro Layer: Feature Scoping
Breaks a business goal down into standard development project containers.
* **Explore (Cheap Context Gathering):** Fast, inexpensive scan of codebase structure, dependencies, existing patterns, and tech stack. Runs on a cheap model (V4 Flash). Outputs raw factual context to `explore.md` — what exists, not what to do. When a nearest existing user flow exists, catalog a short sibling-flow inventory (amount vs fee, lock vs reserve, vendor call in HTTP vs job, idempotency, destination shape) with quoted paths and no recommendations. Ecosystem research stays catalog only. Initial output lands in `specs/explore/<slug>.md`; `deviate research pre` **moves** that file into the numbered epic directory at `specs/{NNN}-<slug>/explore.md` so every artifact for one feature lives under a single directory. `allocate_feature_bucket()` numbers an unnumbered slug from `max(local numbered specs dirs ∪ remote feat/<NNN>-* prefixes) + 1`; a numbered slug stays idempotent. The move is recorded as a tracked rename (usually rendered as `R100` in `git show`) inside the same atomic commit that `deviate research post` produces for `design.md` + `data-model.md` — the source path `specs/explore/<slug>.md` is `git rm`-ed and the destination `specs/{NNN}-<slug>/explore.md` is `git add`-ed, so the working tree never carries a tracked-but-deleted or untracked residue from the move. The source path is persisted on `SessionState.research_explore_source` at pre time so the post-script can `git rm` the right path even when `allocate_feature_bucket` short-circuits on an already-numbered slug.
* **Research (Architectural Design):** Consumes `explore.md` (at `specs/{NNN}-<slug>/explore.md` after the research pre move) and performs high-level architectural analysis as a **range**, not a maxed design. One agent writes the floor (constitution + sibling parity + authorization/money safety/provider correctness/data integrity) then attacks it in the same prompt — no sequential AlphaBeta/Gamma sub-agent spawns. Schema tables are floor only; named extras live in a Deferred / maximal bracket list. Existing constitutions stay read-only except greenfield bootstrap or an explicit HITL amendment. Runs on a reasoning model (Qwen thinking or V4 Pro). Outputs `design.md` (architecture and decisions) and `data-model.md` (entity relationships, schemas), both inside the same numbered epic directory.
* **PRD:** Translates the human-selected point on the research bracket into immutable FR/AC tokens plus implementation-independent `AO-NNN` acceptance outlines. AC names the criterion; AO names its observable outline. Each FR must pair its AC and AO in the Acceptance Outline. In-scope is the floor plus promoted extras; unused Recommended/Deferred extras stay in Out-of-Scope Boundaries. Halt with `UPSTREAM_INCONSISTENT` when `design.md` and `data-model.md` disagree on a field, state, or storage type, and `SCOPE_DRIFT` when a required item has no approved upstream Required source. Given/When/Then is forbidden here; Plan owns final Gherkin.
* **Shard:** Breaks down the PRD into standalone technical issue files (GitHub Issues). Each issue must be a **vertical slice** — a complete, testable behavior end-to-end (not a horizontal layer like "add database"). Emit as few independently shippable user-visible verticals as the PRD needs, with no fixed count cap. Each issue must be independently implementable and testable, with clear acceptance criteria. Shard carries covered AC/AO pairs and maps each AC to an executable Verification Command. **Slicing rules live entirely in the `deviate-shard` prompt**; the PRD prompt never pre-decides groupings.
* **Adhoc (Fast-Path):** A condensed single-command shortcut (`/deviate-adhoc`) that compresses Explore + Research + PRD + Shard into one operation for low-to-medium complexity tasks. Performs proportional exploration (lightweight file scanning, dependency mapping), synthesizes a condensed PRD entry, and emits a single vertical-slice issue directly into `specs/adhoc/`. Appends to the aggregated `specs/adhoc/prd.md` and registers the issue in the global `specs/issues.jsonl` append-only ledger with an `ISS-NNN` / `ISS-ADH-NNN` identifier (one adhoc series). The compiler allocates `NNN` as `max(origin ledger, current ledger, remote feat/adhoc/<NNN>-*) + 1`. Local-only unpushed feat branches do not reserve. A **Complexity Gate** evaluates the task description before proceeding: high-complexity tasks (multi-module coordination, state management, new architecture) are rejected with a directive to run `/deviate-explore` to initiate a full epic workflow instead. This gate prevents scope-creep and ensures adhoc remains a true fast-path, not a bypass for complex engineering.
* **Greenfield bootstrap:** `deviate explore pre` and `deviate research pre` are the two
  points at which a fresh project's `specs/constitution.md` is created. On a project with
  no existing constitution, `explore pre` skips `_validate_constitution` and emits
  `is_greenfield=true` in its JSON contract; `research pre` then bootstraps the
  placeholder scaffold from `src/deviate/prompts/constitution_seed.md` before
  validation, so a brand-new repo is greenfield exactly once (through explore) and
  becomes governed at the first research invocation. `deviate setup` deliberately does
  NOT scaffold the constitution — keeping setup constitution-agnostic preserves the
  greenfield signal for the orchestrator and downstream phases. The new-user path is
  two steps: `deviate setup` (writes `.deviate/`, persists the agent, installs the
  default execution-layer packs — `macro` + `meso` + `micro`, including `deviate-init` —
  and the shared `deviatdd` skill) then `/deviate-init`
  as the first agent prompt (Codex: the `deviate-init` skill). `/deviate-init` runs
  `deviate init pre` / `deviate init post` and scaffolds `specs/constitution.md`,
  `mise.toml`, and `specs/issues.jsonl`, skipping anything already present.

* **Active Domain Discipline (HITL gates):** `/deviate-research` Gate 1 and `/deviate-prd` Ambiguity Interrogation actively challenge terms and edge cases. Plan + Tasks produce the current acceptance contract and decomposition; the system auto-advances from Tasks into Micro with no human-approval step.

### 2.2 The Meso Layer: Issue Engineering
Creates formal contracts for an issue via CLI slash commands. The workflow was restructured
(ADHOC-003) to merge `/deviate-specify` into `/deviate-shard` and introduce a dedicated
`/deviate-plan` phase for per-issue localized research. Gate 3 PR review is
handled by the `/deviate-review` skill (`/deviate-review` **is** the PR review;
there is no `pr-review` pack). Default behavior is comments only. `deviate
review pre` requires this issue's brief to contain named-check tokens; otherwise
it emits exactly `brief incomplete` and stops (no Explore hunt). When the brief
is complete, `evaluate_review_coverage` (`src/deviate/core/review_coverage.py`)
still lists unclaimed this-issue `plan.md` `AC-PLAN-NNN` tokens in `uncovered`
as **comment input** — not an apply gate and not a merge gate. Missing
`plan.md` or missing plan tokens are vacuously complete. PENDING, FAILED, and
sibling-issue rows do not claim. The skill comments (stdout and/or GitHub PR
review event `COMMENT`). It must not emit `REQUEST_CHANGES` or merge, and must
not assume JUDGE already ran (coworker path is often `--profile fast`).
`--apply` is opt-in: the agent may apply CRITICAL findings only (security /
data loss / broken build / named-check fail with a concrete FIX) and commit
only when such a fix landed. Never auto-apply SUGGESTION or OPPORTUNITY. There
is no always-on STEP 4.

Alongside the review, `/deviate-walkthrough` (see `src/deviate/cli/walkthrough.py`)
is the four-look map of the same this-issue read set: (a) where the brief is
plus this issue's plan AC lines if `plan.md` exists; (b) which hunks are the
test diff; (c) which production hunks claim which named check; (d) the command
to run those checks. `deviate walkthrough pre` emits `issue_brief_path`,
`plan_path` (null if absent), and classified `test_files` / `production_files`.
It does not send constitution/prd as default inputs unless this brief names
those paths. The walkthrough must not reimplement, approve, hide hunks, tell
the human to skip a look, auto-edit, or apply fixes. Both commands stay
optional packs (`review`, `walkthrough`); default setup does not install them.

* **Shard + acceptance outline:** `/deviate-shard` produces vertical issue packets with user stories, `AO-NNN` outcomes, edge cases, performance constraints, and scope boundaries. `GHERKIN_LEAK_DETECTED` rejects Given/When/Then in macro artifacts. Standalone `/deviate-specify` remains deprecated.
* **[HITL Gate 2 (REMOVED)]:** The post-Tasks approval hard gate was removed. The system never blocks on human approval. `deviate run` chains meso into micro end-to-end; plan and tasks artifacts are committed to the worktree and may be reviewed out-of-band, but execution does not wait on the human.
* **Plan (`deviate plan pre` / `deviate plan post`):** Per-issue localized research phase
  that performs fresh codebase scanning (what exists now, not at epic-explore time),
  analyzes what prior issues implemented (via the `specs/issues.jsonl` ledger), and
  parses workstation file paths from the issue's `## System Topology Mapping` section.
  The `pre` subcommand is dual-mode: outside a linked worktree it auto-discovers the next
  claimable unblocked BACKLOG issue, creates the worktree, claims the issue,
  force-transitions the session to `PLAN`, and syncs
  `.deviate/` into the new worktree; inside a linked worktree it emits a `plan_pre`
  JSON contract for the agent. The `post` subcommand validates `plan.md` is non-empty and contains complete `AC-PLAN-NNN` scenarios with AO/upstream/current-code traceability, commits it with a convention-aware message, then transitions to TASKS. This current-code-informed Acceptance Contract is authoritative for Tasks, RED, and JUDGE, addressing stale macro context.
  Tasks emits a trackable execution blueprint in `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.md`; post validates and commits it, then `deviate run` chains directly into `deviate micro run --all`. Each entry has a unique `TSK-{ISSUE_ID}-{NN}` identifier, type (`tdd`, `direct`, or `e2e`), file locations, mock boundaries, and fixture requirements. Type `Verification_Batch` is locked to `execution_mode: IMMEDIATE` (EXECUTE path — never TDD); `src/deviate/core/tasks_ledger.py::resolve_execution_mode` enforces the mapping when parsing `tasks.md`. A terminal `Verification_Batch`/`[E2E]` task is emitted automatically for issues with a user-facing workflow (CLI/Web/API surface); it authors the consumer's E2E tests and runs last. Issues touching only library/config internals with no user-facing surface omit it.
  * **Plan digest data flow:** After PLAN commits `plan.md`, the meso orchestrator builds
    a 16 KiB UTF-8 digest (`_build_plan_digest` in `src/deviate/cli/meso.py`). The digest
    keeps the head + tail of the plan and inserts a `PLAN_DIGEST_TRUNCATED` marker when
    the source plan exceeds 16 KiB. The auto prompt `src/deviate/prompts/auto/tasks.md`
    exposes the digest as a `<plan_digest>` literal block (a leading template with
    `{plan_digest}` would re-inject the payload) plus a `<plan_path>` pointer the agent
    uses as a fallback when the marker is present. This bounds the per-phase prompt
    size so a runaway plan cannot stall the TASKS agent (Gloss 009).
  * **Granularity:** One fail-to-pass contract per task (one observable behavior the JUDGE can still see). Avoid "create one file" granularity —
    group related functions into a cohesive unit. Enforce bounds: minimum 1 task per issue,
    maximum 10 tasks per issue. Split a mixed 10-file / >400 LOC GREEN packet; keep the JUDGE packet default ≲2 files / ≲3 hunks / ≲30 production LOC with review ceiling <200 LOC typical / 400 max.
* **PR (`deviate pr pre` / `deviate pr run`):** Marks the issue COMPLETED in the ledger, pushes the
  worktree branch, then optionally opens a GitHub pull request (`gh pr create`) or GitLab merge
  request (`git push -o merge_request.create`). The `pre` subcommand validates PR metadata; the
  `run` subcommand executes the ledger update + push, opening a PR/MR unless `--no-pr` is set.
  Platform is auto-detected from the `origin` remote and overridable via `--platform`.
  PR titles use conventional-commit format for squash-merge compatibility. There is no Graphite path.
* **Merge (`deviate merge` / `deviate merge pre` + `/deviate-merge` skill):** Final meso-layer gate that performs
  the squash-merge into the configured `base_branch` (from `resolve_base_branch`: hand-set `.deviate/config.toml` key, else `origin/HEAD`, else `main`) and writes a full Pydantic-validated `IssueRecord` (not a
  bare transition). `deviate merge pre` emits a JSON contract with `base_branch` so the skill
  does not hardcode `main`. The CLI run path is intentionally two-phase: `--stage-only` writes the COMPLETED
  transition to `specs/issues.jsonl` and stages it; `-m <subject> -m <body>` then commits
  the feature changes + ledger in a single atomic commit. The transition write is idempotent
  so re-running `--stage-only` before `--message` is safe. `--delete-branch` owns the full

  * **Push gate + opt-in push (v2.4.0):** after the squash-merge commit lands on `{base_branch}`,
    the `/deviate-merge` skill runs an inline copy of `.githooks/pre-push` (lint + format-check
    + testmon-driven affected tests, with the warm-cache / full-suite fallback) as a
    `push_gate` step, then asks the operator whether to `git push` (which fires the real
    `pre-push` hook and re-runs the gate) or stop and push manually. The gate body must stay
    byte-equivalent to `.githooks/pre-push` — divergence is pinned by
    `tests/test_meso/test_auto_prompt_templates.py::TestMergePromptPushGate::test_hook_and_prompt_agree_on_gate_body`.
    The squash-merge commit and the ledger transition inside it are durable on `{base_branch}`
    regardless of the push outcome; only the network push is opt-in.

  post-merge lifecycle in a single call: tags the pre-squash branch tip with
  `archive/{ISSUE_ID}/{YYYY-MM-DD}` (preserving the per-commit graph that
  `git merge --squash` collapses into a single squash commit), pushes the tag to `origin`,
  `git push origin --delete <branch>`-es the remote, removes any active worktree that holds
  the branch, and runs `git branch -D`. Tag push and remote branch delete are best-effort:
  no `origin` → silent skip; unreachable remote → `PUSH_WARN` and local cleanup proceeds,
  pass the convention file before drafting the title, and explicitly forbids bypassing `deviate merge --messag…
  archive tag is the only path back to the pre-squash per-commit history.
  redundant context injection into CLAUDE.md/AGENTS.md unnecessary. Mutating CLAUDE.md
  mid-cycle would invalidate LLM KV caches, defeating the cache optimization strategy.
  The `/deviate-context` skill was deleted in commit `b7057e2`.
* **Session Continuity (KV Cache Optimization):** `/deviate-plan` and `/deviate-tasks` execute
  in a single continuous LLM session per issue — not as separate invocations. The system
  prompt, tool definitions, issue content, and `constitution.md` form a stable prefix that
  achieves 90%+ KV cache hit rates after the first turn. DeepSeek V4 Flash bills cache-hit
  input at $0.0028/M tokens versus $0.14/M for cache-miss input (98% discount). V4 Pro
  applies a similar ratio ($0.003625/M hit vs $0.435/M miss).

### 2.3 The Micro Layer: The Automated Sandbox (Python CLI)
The executor agent targets a task by looking up its current state in `tasks.jsonl`. The state
ledger is pure — only event type, worker, and timestamp are stored. The agent is trapped inside
a strict state machine governed by Git, deterministic parsing, and defensive operational
safeguards. **Task execution type determines the applicable phase gates and file-write
boundaries.** Execution profile (`--profile [full|fast]`) determines which phases are
enforced, replacing the older `--no-judge`/`--no-refactor` boolean flags (retained as
composable overrides).

### Execution Engine

The Micro layer execution engine is implemented as an in-process Python function dispatch
via `src/deviate/cli/micro.py`. The `deviate micro run <task-id>` command (the per-task
dispatcher that used to live as top-level `deviate run`) resolves a task by its
`TSK-NNN-NN` identifier from the ledger. Resolution is issue-scoped when the
branch or re-keyed session issue is known; same-number TSK ids remain a
per-issue namespace. It then dispatches through the phase cycle based on
`execution_mode`. The top-level `deviate run` orchestrator (`src/deviate/cli/__init__.py`)
chains `deviate meso run` with `deviate micro run --all` inside the created worktree;
see `DeviaTDD-api.md` §5 for the orchestration contract.:

- **TDD tasks** (`execution_mode: "TDD"`): Full RED -> GREEN -> JUDGE -> REFACTOR cycle via `_run_tdd_cycle()`. C1 (`deviate` CLI) owns GREEN entry: `_run_green_phase` invokes the GREEN agent only when `session.red_commit_sha` is a standing RED-phase failing-test commit. After `no_failing_test` / `revert_red` / `no_failing_test_adjudicated`, the next `INVOKE_AGENT` is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. TDD `revert_green` with an empty SHA is fatal (`ROLLBACK_BOUNDARY_MISSING`) and does not train GREEN.
- **Non-TDD tasks** (`execution_mode: "DIRECT" | "E2E"`): Immediate completion via
  `_run_execute_phase()`, which marks the task COMPLETED without test generation.

Cycle regressions (wild JUDGE/GREEN/RED handovers such as GH-158 pass+`REFACTOR NOTE` and GH-148 stale `skip_refactor`) go in scripted fixtures (`tests/helpers/cycle_driver.py`), not new `_coerce_judge_action` branches only. The same handover YAML is replayed on **both** invocation styles: auto `_run_tdd_cycle` (patch `_invoke_agent` only; `_run_*_phase` and `_apply_judge_verdict` stay real) and manual `deviate <phase> pre` → scripted files on disk → `deviate <phase> post`. Auto does not shell out to pre/post. A payload that only exists on one path is a missed bug.

Each phase transition appends a status record to the append-only task ledger using
`append_task_transition()` with compound-key idempotency on `(id, status)`. The JUDGE
phase (`deviate judge pre`) performs compliance verification by comparing changed files
against protected modules declared in `spec.md` `Module:` declarations.

Manual phase execution is supported via individual `pre`/`post` subcommands:
`deviate red pre/post`, `deviate green pre/post`, `deviate judge pre/post`, etc. These are used for interactive
or agent-driven TDD where full automation is not desired. `deviate judge post [<manifest>]` reads the JUDGE handover and applies the same rollback / `tasks.md` feedback / session-ledger updates as `_run_judge_phase` (`_apply_judge_verdict`); auto `micro run` does not shell out to the new CLI.

All `pre` subcommands accept `--json` (emit the phase contract as JSON to stdout) and
`--quiet` (suppress rich console diagnostic output). These flags enable programmatic
consumption by agent runtimes that parse JSON contracts rather than reading human-facing
console output.

Cache optimization strategies (prefix caching, session continuity) are defined as
recommended patterns in `specs/constitution.md` seeds but are **not enforced programmatically**
by the `deviate` CLI. The `--agent` flag on `deviate micro run` (and on the top-level
`deviate run` orchestrator, which forwards it to micro) configures which agent backend
to invoke, but model selection is delegated to the calling environment.

#### Task Execution Types

| Type | Description | Phase Gates | Allowed File-Write Boundaries |
| :--- | :--- | :--- | :--- |
| **`tdd`** | Standard TDD loop with RED → GREEN → JUDGE → REFACTOR. Strict assertion failure verification. | Full state machine | RED: `tests/` only. GREEN: `src/` or core modules only. |
| **`direct`** | Bypasses RED phase. Used for boilerplate, dependency config, or asset syncing. No test generation. | GREEN → JUDGE only | Scoped tightly to targeted files (e.g., `pyproject.toml`, config assets). |
| **`e2e`** | End-to-end integration validation. Orchestrates external runtime environments, databases, or client-server loops. Verified via exit codes. | GREEN → JUDGE only | Production lines frozen; no business logic modifications allowed. System-level behavioral evaluation only. |

* **GREEN (The Execution):**
    * **Action:** The agent iterates on production code to pass the test.
    * **GREEN-entry invariant:** `_run_green_phase` (`src/deviate/cli/micro.py`) invokes the GREEN agent only when `session.red_commit_sha` is a standing RED-phase failing-test boundary. Empty SHA and a `docs(...): add judge feedback` SHA that does not rest on a RED ancestor raise `PhaseFailedError` carrying `GREEN_ENTRY_REFUSED`. After JUDGE `revert_red` / cycle `no_failing_test_adjudicated`, `_run_tdd_cycle` re-dispatches RED or raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. It never enters GREEN on that path. C1 (`deviate` CLI) owns this gate. `skip_refactor` / bare `COMPLIANCE_PASS` still complete without GREEN. `_coerce_judge_action` and the 3/3 caps from ISS-ADH-017 stay unchanged.
    * **Test-command Deadline:** Every test invocation flows through
      ``run_safe_command`` (``src/deviate/cli/_safe_commands.py``).
      The deadline resolves as ``DEVIATE_TEST_TIMEOUT_SECONDS`` (env
      override) → ``DeviateConfig.timeout_seconds``
      (``.deviate/config.toml``, default ``300``) → ``300``; an
      unparseable env value or a ``gt=0``-violating config value
      falls through to the next source so the timeout binding can
      never be silently disabled. On expiry the orchestrator runs
      SIGTERM, waits a 5s grace, then SIGKILL on the **process
      group** (``start_new_session=True`` + ``os.killpg``) so every
      descendant of the test command is reaped alongside the
      immediate child. Returned
      ``CompletedProcess.returncode == 124`` (GNU ``timeout(1)``
      convention) — never an indefinite hang.
    * **State Lock:** Upon a valid Green pass, `git add . && git commit -m "feat: [TASK-ID] Green phase complete"`.
    * **Layer discipline:** GREEN's only invariant is "make the RED test pass via the library/API surface declared in scope." It does NOT make scope, spec-drift, or HITL-routing judgments — those belong to JUDGE. When a RED test cannot be satisfied within GREEN's mechanical scope, GREEN emits `status: FAILURE` with a concrete `rationale:` naming the test path and why; `status: "ERROR"` is reserved strictly for tool/orchestration failure. The runner's `_is_hitl_escalation` is a narrow defensive fallback that ONLY promotes structured `contract_drift` / `escalates_to` / `hitl_options` dict keys to `HITL_PENDING` — loose-string `error_kind` discriminators and free-form scope-conflict text do NOT trigger HITL escalation.
    * **Mechanical Failure → JUDGE Routing:** When GREEN emits `status: FAILURE` with a concrete `rationale:` (the mechanical scope-boundary case above), the runner routes control to JUDGE instead of raising `PhaseFailedError`. `_run_green_phase` sets `session.train_feedback = rationale` + `session.failure_kind = "mechanical"` and returns the session; `_run_judge_phase` injects a `<failure_kind>mechanical</failure_kind>` discriminator block into the JUDGE prompt that instructs the agent to emit `verdict: COMPLIANCE_PASS` + `next_action: proceed_to_refactor_no_diff` (when the slice is intrinsically RED-only and REFACTOR's no-op commit + COMPLETED transition is the right termination) OR `verdict: COMPLIANCE_VIOLATION` + one of three `next_action` values (`revert_red` / `revert_green` / `skip_refactor`) instead of attempting to satisfy the test itself. This closes the loop where mechanical FAILURE (e.g. slice-scope conflict, CLI-surface-out-of-sco…
    * **Test-Defect Failure → JUDGE Routing:** A second routable failure class, parallel to mechanical but pre-decided. When GREEN observes that the RED test itself is wrong (it asserts behavior the spec does not require, exercises the wrong abstraction, or encodes an assumption that contradicts spec/data-model), GREEN emits `status: FAILURE` with a concrete `rationale:` citing the FR/AC the test contradicts, plus `failure_kind: test_defect` on the manifest (`HandoverManifest.failure_kind: Literal["mechanical", "test_defect", "already_satisfied"] | None` in `src/deviate/core/agent.py` — session mirrors the discriminator as `SessionState.failure_kind: Literal["", "mechanical", "test_defect", "no_failing_test"]` in `src/deviate/state/config.py`). `_run_green_phase` reads the manifest's discriminator, sets `session.failure_kind = "test_defect"`, and routes to JUDGE. `_run_judge_phase` injects a `<failure_kind>test_defect</failure_kind>` discriminator block that pre-decides the routing — `verdict: COMPLIANCE_VIOLATION` + `next_action: revert_red` (re-run RED with the GREEN rationale as feedback) — because test defect has only one sensible outcome: the test itself must be re-authored. The discriminator intentionally narrows the JUDGE routing vocabulary compared to mechanical (`revert_green` / `skip_refactor` / `proceed_to_refactor_no_diff` are NOT options in the test_defect block). Default `manifest.failure_kind = None` falls through to `"mechanical"` in the runner to preserve prior behavior.
    * **RED No-Failing-Test → JUDGE Adjudication (RED → JUDGE direct route):** When RED completes but its test command exits 0 (all tests passed), collects no tests (pytest exit 5), or resolves to no command at all (returncode 127 from `_run_test_cmd`), `_run_red_phase` does NOT raise a raw `PhaseFailedError` and does NOT let GREEN run against a vacuous test. It calls `_adjudicate_red_no_failing_test` (`src/deviate/cli/micro.py`), which sets `session.failure_kind = "no_failing_test"`, injects a `<failure_kind>no_failing_test</failure_kind>` discriminator block into the JUDGE prompt, and dispatches `_run_judge_phase(...)`. The judge diff spans the uncommitted RED test (the `red_baseline` parameter makes `_run_judge_phase` skip the `RED→HEAD` committed diff and surface the agent's uncommitted test through the dirty-parts scan) so JUDGE reviews what the agent actually wrote. On a test-bearing TDD task, `_require_tdd_declared_regression_files` requires a non-empty `files` set and/or `test_file` before this COMPLETE route (constitution §3 Testing Protocols; §5 Definition of Done). Empty declared files raise `PhaseFailedError`. JUDGE decides between two outcomes: `verdict: COMPLIANCE_PASS` + `next_action: skip_refactor` (or a bare PASS verdict, or any `next_action` on the already-exists route) when the required behavior already exists and every declared regression path sits in the injected `<diff>` or `_evidence_head_contents` — `_apply_judge_verdict` then coerces the action to `skip_refactor`, skips the `_rewrite_unmatched_tdd_pass` AC-token citation rewrite for this route, and `_require_tdd_completed_evidence` relaxes the AC-token citation check while retaining the declared-path presence gate, so partial evidence completes instead of rewriting to `revert_green`; the runner then calls `_restore_worktree_to_baseline(..., keep_paths=declared)` so those tests stay on disk, and marks the task COMPLETED. `_require_revert_green_boundary` is never invoked on this already-exists pass path, so `ROLLBACK_BOUNDARY_MISSING` applies only to a genuine TDD `revert_green` with an empty `red_commit_sha`. A declared path missing from that snapshot still fails closed via `_require_tdd_declared_regression_files` (rewriting PASS to `revert_red` / `revert_green` with runner-authored feedback and writing no COMPLETED row); or `verdict: COMPLIANCE_VIOLATION` + `next_action: revert_red` (forced by the `_coerce_judge_action` runner-level override for `failure_kind` `no_failing_test`/`test_defect`) when the test is wrong — the runner resets to the RED baseline and re-dispatches RED so a fresh genuinely-failing test is authored. EXECUTE, IMMEDIATE, and DIRECT stay ungated by the files rule. The next `INVOKE_AGENT` is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. It never invokes GREEN while `session.red_commit_sha` is empty. `--no-judge` makes the no-failing-test outcome a hard failure (adjudication disabled). Test discovery is language-agnostic: the RED gate no longer globs Python `tests/**/test_*.py` (`_find_test_files`); the project's own convention is honored through the resolved test command (e.g. `mix test` collecting `test/**/*_test.exs` for Elixir/Phoenix), so a correctly authored non-Python test is neither rejected up front nor silently conflated with "no test framework" — a project with no resolvable test command routes to the same JUDGE adjudication instead of failing. This closes the prior stall where an empty `_find_test_files` let RED silently commit a vacuous 'failing test' and GREEN die in `TRAIN_EXHAUSTED`. The RED agent may steer the adjudication by declaring `failure_kind: already_satisfied` (behavior exists) with a non-empty `files` set and/or `test_file`, or `failure_kind: test_defect` (test wrong) with a `rationale` on its handover manifest. A passing suite with no named test files is not a COMPLETE.
* **JUDGE / TRAIN (The Compliance Gate) — with Green → Judge → Green loop:**
    * **The Judge:** The CLI evaluates the committed RED-parent-to-HEAD diff against `spec.md` for invariant/security violations. When `session.red_commit_sha` has advanced onto a `docs(...): add judge feedback for retry` commit, `_assemble_judge_injected_diff` calls `_resolve_judge_diff_base` to walk back to the RED-phase failing-test commit before running `git diff {red_sha}^..HEAD`, so RED tests stay visible to the evidence gate (GH-88 / GH-90). If GREEN tests failed before the implementation commit, `_run_judge_phase` also appends staged/unstaged `git diff HEAD` output and per-file `git diff --no-index /dev/null <path>` output for untracked files, so JUDGE assesses the retained implementation rather than a false RED-only snapshot. This judge operates in a clean, zero-shared-history session to break recursive subjectivity. A `deviate-judge` skill (loaded from `_SKILL_NAMES["JUDGE"]`) guides the agent through supplementary compliance evaluation. TDD JUDGE evidence is task-scoped: `_run_judge_phase` resolves required `AC-PLAN-NNN` tokens via `resolve_task_ac_tokens` (non-empty `acceptance_criteria` `criterion_id`s, else this task's `tasks.md` card minus `**Judge Feedback**` bullets and their continuation lines, else none) and does not fall back to every token in `plan.md`. Auto `_build_auto_prompt` for red/green/judge/refactor injects this task's `tasks.md` card only as `{task_content}` plus `train_feedback` when the runner has any (GH-150); agents must not open `tasks.md` for this-task fields. JUDGE's card is Judge-Feedback-stripped so prior-round prose cannot bias the next judge (GH-118); `_task_card_text` remains raw. TDD `_run_judge_phase` then rejects `COMPLIANCE_PASS` unless `HandoverManifest.evidence` quotes for those task tokens match the injected diff (or HEAD file contents on the already-exists `skip_refactor` edge) and every declared `files` / `test_file` path exists in that snapshot. Unmatched PASS rewrites to `revert_green` / `revert_red`. On a forward PASS the runner stashes those citations on `SessionState.validated_evidence` (transient only) and writes them onto the COMPLETED `tasks.jsonl` row as `TaskRecord.evidence` (`items` plus `red` / `green` / `head` SHAs) so `deviate inspect tasks show` can display the proof after the session is gone (GH-84). TDD COMPLETE with `AC-PLAN-NNN` tokens refuse when that bundle is missing or does not cover the tokens (`evaluate_judge_evidence`). `.deviate/` session files are not the proof store. Earlier RED/GREEN/JUDGE rows stay lean. Persist the judge's own `train_feedback` / `violations` when present (GH-103 citation strip still applies); attach the generic missing-evidence string only when the judge emitted none (GH-102). `_append_judge_feedback` keys the card with `_TASK_BULLET_HEAD_RE` exact-id match and inserts under that card only (does not walk past a later phase heading). Gate 3 review (`deviate review`) owns plan-wide AC coverage. EXECUTE, IMMEDIATE, and DIRECT judge paths stay ungated.
    * **The Train (Green → Judge → Green loop):** On `COMPLIANCE_VIOLATION` or test failure, the CLI safely resets without destroying task progress. The JUDGE phase honors `HandoverManifest.next_action` (see [specs/DeviaTDD-api.md](./DeviaTDD-api.md) for the routing table). The five routes:
        1. **`revert_red`** — discard this task's GREEN **and** its RED. `_resolve_pre_red_sha()` derives the SHA from `red_commit_sha^` (defended by a subject-match regex on the parent's commit message; logs `PRE_RED_AMBIGUOUS` when the parent isn't a RED-phase convention). The pre-RED anchor is threaded into `_execute_rollback(boundary_sha=<pre_red>, task_id=<tid>, attempt=<rollback_attempts>)`; the agent's pre-reset HEAD is captured on the per-attempt recovery ref `tmp/deviate-agent-work/<sanitized-task-id>/attempt-<rollback_attempts>` so a parent SIGTERM between `git reset` and `git clean` doesn't strand the discarded commit. `session.red_commit_sha` is cleared (the boundary was discarded) and `pending_judge_action = "revert_red"`. `force_transition_to("RED")` so the task retries from scratch. `_escalate_to_new_red` consumes `revert_red` only after a RED-phase `red_commit_sha` lands. While that SHA is empty, the next `INVOKE_AGENT` stays RED (or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`). **No implicit fallback**: if `_resolve_pre_red_sha` returns empty AND `session.red_commit_sha` is empty, the runner raises `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")` rather than fall back to `HEAD~1`. When `pre_red` is unresolvable but `session.red_commit_sha` is known, that cached SHA is used as the explicit boundary.
           **Runner-level override on `failure_kind=test_defect`:** when `session.failure_kind == "test_defect"` and JUDGE emits `COMPLIANCE_VIOLATION`, `_coerce_judge_action` (`src/deviate/cli/micro.py`) forces `next_action="revert_red"` regardless of what the JUDGE manifest declared or omitted. The override reflects a contract invariant: when the RED test itself is wrong, looping back to GREEN with the same test is futile. After GREEN PASS (`failure_kind` empty / not `mechanical`), a `COMPLIANCE_VIOLATION` with structured Test Integrity (`violations[].category` matching Test Integrity / `Test Integrity Violation`, and/or `evaluation.test_integrity: FAIL`) also forces `revert_red` even when `next_action` is omitted or `revert_green`. Honest-test implementation/scope gaps stay `revert_green`. Mechanical overlay keeps the agent's three-way choice. The runner does not parse `train_feedback` for routing. `_run_tdd_cycle` honours the resulting `pending_judge_action == "revert_red"` by escalating now. It resets `green_attempts` to 0, increments `red_attempts`, and persists both on `.deviate/session.json`. It then dispatches `_run_red_phase(task, ..., bypass_phase_done=True)` so a fresh RED record appends to the append-only ledger (never rewriting prior entries). The retry RED prompt receives a short `previous cycle failed because …` note, not the raw GREEN dump. `TRAIN_EXHAUSTED` prints only after three RED escalates. The override is silenced on `COMPLIANCE_PASS` verdicts; JUDGE's outcome remains authoritative when the implementation is sound. The override preserves the legacy resolution for `revert_green`, `continue_refactor`, `proceed_to_refactor_no_diff`, and `skip_refactor` except the test_defect / no_failing_test / GREEN-PASS Test Integrity cases.
        2. **`revert_green`** — discard GREEN, preserve RED. `_run_judge_phase` threads `session.red_commit_sha` into `_execute_rollback`. When that SHA is empty, the runner raises `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")`. It does not print `ROLLBACK_FAILED … proceeding with train feedback`. It does not call `_commit_judge_feedback_and_advance`. It does not `force_transition_to("GREEN")`. When a RED-phase SHA exists, rollback still trains GREEN. `_commit_judge_feedback_and_advance` advances `red_commit_sha` onto the docs-feedback commit only when the pre-call SHA is already a RED-phase failing-test commit. That advanced SHA remains the GREEN-entry / rollback boundary; the injected JUDGE diff base stays at the walked-back RED-phase commit (`_resolve_judge_diff_base`). GREEN-resume (`start_phase=JUDGE` after ledger GREEN) must honor `revert_green` as TRAIN GREEN: fall through into the GREEN train loop, or skip a second JUDGE when the session already holds that pending action plus `train_feedback`. Never enter REFACTOR or COMPLETED. `_finish_tdd_cycle` refuses both while pending is `revert_green` or `revert_red`. The in-loop TRAIN GREEN path and `revert_red` escalate-to-RED are unchanged.
        After this rollback, the retried GREEN prompt carries a `<rollback_context>` clean-slate notice: previous GREEN commits and uncommitted/untracked artifacts were discarded, so every feedback-referenced artifact must be verified on disk and recreated when absent.
        3. **`continue_refactor`** — JUDGE passed. No rollback. `pending_judge_action = "continue_refactor"`; `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`. A clean `COMPLIANCE_PASS` (no compliance / Test Integrity failure) that omitted `next_action` or emitted a revert (`revert_red` / `revert_green` / legacy `revert_to_red`) is coerced here (or `skip_refactor` when `--no-refactor`). A `REFACTOR NOTE:` in `train_feedback` is optional advice for REFACTOR, injected via `{train_feedback}`; it is not a reason to revert and must not set `JUDGE_REJECTED` (GH-158).
        4. **`skip_refactor`** — JUDGE passed, refactor not wanted. No rollback. `pending_judge_action = "skip_refactor"`; `_apply_judge_verdict` stamps `judge_task_id` + `judge_red_commit_sha`. `_finish_tdd_cycle` marks the task `COMPLETED` and returns to `IDLE`. Re-appending COMPLETED after JUDGE or an adjudicated already-exists write is a no-op (GH-146); the COMPLETED evidence gate does not re-run. A leftover forward route (`skip_refactor` / `continue_refactor` / `proceed_to_refactor_no_diff`) from another task or a different RED SHA — including a pre-fix unbound `session.json` once a RED SHA exists — is cleared on dispatch / `_tdd_pre_green_decision` so GREEN and JUDGE run (GH-148). Same-task `skip_refactor` from this task's JUDGE still completes. No `SESSION_STALE` HITL prompt; `.deviate/` is not deleted (GH-145/146 leave it after revert). GH-158 Pass+`REFACTOR NOTE` forwarding is unchanged.
        5. **`proceed_to_refactor_no_diff`** — JUDGE passed on a slice whose production-code scope is intrinsically nil (RED-only deliverable, fixture file, generated types, doc-only slice, or any task whose `failure_kind: mechanical` rationale asserts "no production code expected"). No rollback. `pending_judge_action = "proceed_to_refactor_no_diff"`; `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`. REFACTOR's commit + COMPLETED transition is the only way to terminate a slice whose git diff is empty (the GREEN-empty branch never enters the rejection cascade). Distinct from `continue_refactor` (which signals a substantive refactor pass on a non-empty diff).
    * **Retry state-drift guard:** First-pass zero-diff GREEN continues to JUDGE for empty-GREEN `test_quote` classification. A feedback-driven retry is different: if the task ledger already contains GREEN, `session.train_feedback` is populated, and the retry creates no implementation commit, `_run_green_phase()` raises `GREEN_STATE_DRIFT` instead of sending JUDGE a feedback-only diff. Recovery is explicit verification of the existing implementation followed by append-only ledger reconciliation.
        After `green_attempts` reaches 3 the runner escalates (new RED) instead of raising `TRAIN_EXHAUSTED`. `revert_red` escalates immediately. After three RED escalates (`red_attempts >= 3`) the loop prints `TRAIN_EXHAUSTED`, raises `PhaseFailedError`, and marks the task `FAILED`. The runner honors the manifest verbatim — no interactive prompt. The legacy single-commit fallback (`verdict == COMPLIANCE_VIOLATION` without `next_action`) maps to `revert_green`.
    * **Feedback-commit timeout:** The "append a feedback commit past RED" step in the TRAIN rollback loop runs `_commit_judge_feedback_and_advance` (`src/deviate/cli/micro.py`), which executes a `git commit` that inherits the active repository's configured pre-commit hooks (resolved via `core.hooksPath` and `.git/hooks/`). The orchestrator bounds this commit with `JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS = 300` (defined in `src/deviate/core/_shared.py`). Observed hook chains on some projects can exceed 30s; the constant gives them room to complete while still detecting a genuine hang. A `subprocess.TimeoutExpired` handler wraps the commit and raises `PhaseFailedError` so a stuck hook chain surfaces as a documented phase failure rather than a raw traceback. See `specs/DeviaTDD-api.md` for the corresponding feedback-commit timeout note alongside the JUDGE `next_action` Routing Table.
    * **Feedback-commit recovery:** The TRAIN loop writes `{task_id, feedback, feedback_source}` to `SessionState.pending_judge_feedback` before the hook-enabled marker commit. Startup session updates preserve this payload. If hooks reject or time out, the task remains resumable without advancing `red_commit_sha`; a later explicit run or `--all` drain reselects the matching task even after a `FAILED` ledger transition, retries the same commit without invoking JUDGE again, then clears the payload and enters GREEN only after the boundary commit succeeds.
* **REFACTOR (The Polish Gate):**
    * **Action:** If the Judge accepts the work, the workspace unlocks for an isolated run to polish readability.
    * **Regression Gate:** Post-refactor, the CLI re-runs the test suite. If the tests fail (agent broke code), the CLI safely discards the refactor (`git reset --hard`) and successfully completes the task using the verified Green commit.


### 3.1 Spec-Driven Development (SDD)
* **How it is fulfilled:** Executed directly via the Macro Layer and Meso Layer.
* **Mechanisms:** The workflow prohibits "vibe coding" or jumping straight into implementation. The framework enforces an artifact-centric approach where a feature must be systematically defined via research, design analysis, Product Requirement Documents (PRDs), and issue sharding. The Macro Layer separates context gathering (`/deviate-explore` — cheap) from architectural reasoning (`/deviate-research` — expensive), then synthesizes requirements (`/deviate-prd`) and decomposes issues (`/deviate-shard`) — shard now emits vertical issue packets with `AO-NNN` acceptance outlines and rejects Given/When/Then clauses with `GHERKIN_LEAK_DETECTED`, so Plan can own the current-code-informed `AC-PLAN-NNN` Gherkin contract before `/deviate-tasks` decomposes it. The Meso Layer adds a per-issue `/deviate-plan` phase for localized research before task decomposition. The CLI

### 3.2 Test-Driven Development (TDD)
* **How it is fulfilled:** Executed via the Micro Layer: Automated Sandbox.
* **Mechanisms:** This layer implements a pure, unyielding RED-GREEN-REFACTOR loop. The Python CLI enforces that the agent first writes a unit or integration test. It then parses the test runner's JSON output (`pytest --json-report`) to programmatically verify that the test failed due to a missing implementation rather than a syntax crash. The code cannot move forward until a successful Green implementation is verified and locked using atomic Git commits at every step boundary.

### 3.3 Test-Driven Agentic Development (TDAD)
* **How it is fulfilled:** Executed via defensive safeguards embedded in the Micro Layer Sandbox.
* **Mechanisms:** Standard TDD assuming human developers falls short with LLM agents, which are prone to bypassing tests, creating infinite loops, or rewriting assertions to pass falsely. This architecture addresses TDAD directly through hard timeout limits and automated test file protection. It isolates agent behavior to keep the model strictly trapped within the bounds of deterministic software verification.

### 3.4 Acceptance Test-Driven Development (ATDD)
* **How it is fulfilled:** Achieved through bidirectional requirement traceability and the Meso/Micro Layer transition.
* **Mechanisms:** During the Meso phase, `deviate tasks pre/post` translates high-level customer requirements, user stories, and acceptance criteria into explicit target mapping tags inside `tasks.md` (descriptions, `blocked_by` DAG dependencies, `verifiable_sandbox_target`). In the Micro phase, the Judge Gate checks task-scoped `AC-PLAN-NNN` evidence against the injected RED+GREEN diff. HITL Gate 3 (`deviate review`) comments by default: unclaimed this-issue `plan.md` tokens appear in `uncovered` as comment input. Review is not a merge gate and never emits `REQUEST_CHANGES`. Apply is opt-in (`--apply`) and CRITICAL-only. This keeps mid-plan TDD honest at JUDGE while Gate 3 maps and comments on this issue's named checks.

### 3.5 Evaluation-Driven Development (EDD)
* **How it is fulfilled:** Realized via the Compliance Gate and the **Green → Judge → Green loop**.
* **Mechanisms:** This architecture shifts validation from basic functional checks to prompt optimization and alignment validation. If the execution agent attempts to bend architectural constraints, the isolated Judge evaluates the `git diff` against code-level invariants. When `COMPLIANCE_VIOLATION` fires, the TRAIN protocol executes: `_execute_rollback()` runs `git reset --hard <boundary_sha>` against the boundary the runner threads in (`session.red_commit_sha` for TDD JUDGE `revert_green`, the resolved pre-RED SHA for TDD JUDGE `revert_red`, `pre_execute_sha` for EXECUTE JUDGE) — the function no longer reads session state or falls back to `HEAD~1` to discover the boundary; missing/empty/whitespace `boundary_sha` raises `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")` BEFORE any reset so the worktree is never wiped without an explicit anchor. The discarded agent commit is captured on the per-task, per-attempt recovery ref `tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>` (via `_recovery_branch_for(task_id, attempt)`) so a parent SIGTERM between `git reset` and `git clean` doesn't strand the discarded work, and a second rollback inside the same phase call preserves earlier attempts at distinct refs instead of clobbering one global handle. After the reset, `git clean -fd` (without `-x`) wipes untracked artifacts left behind by the failed GREEN attempt while preserving gitignored state such as `.deviate/`. The session is then `force_transition_to("…
---

## 4. Core State Machine Engine

The execution state transitions follow a strict sequence enforced by `SessionState.transition_to()` in `src/deviate/state/config.py`. Macro and meso phases use the `_MACRO_TRANSITION_MAP` to validate forward transitions. Micro phases use `force_transition_to()` which bypasses transition validation (micro phases are driven by the TDD cycle dispatcher).

**Macro/Meso valid transitions** (defined in `_MACRO_TRANSITION_MAP`):

```
    ┌─────────┐  explore pre   ┌──────────┐  explore post  ┌───────────┐
    │  IDLE   │ ─────────────> │ EXPLORE  │ ─────────────> │ RESEARCH  │
    └─────────┘                └──────────┘                └───────────┘
         ▲                                                    │
         │                                          research post
         │                                                    ▼
         │                                              ┌─────────┐
         │                                              │   PRD   │
         │                                              └─────────┘
         │                                                    │
         │                                              prd post
         │                                                    ▼
         │                                              ┌──────────┐
         │                                              │  SHARD   │  ← acceptance outlines
         │                                              └──────────┘
         │                                                    │
         │                                              shard post
         │                                                    ▼
         │                                              ┌──────────┐
         │                                              │   PLAN   │  ← final Gherkin
         │                                              └──────────┘
         │                                                    │
         │                                              plan post
         │                                                    ▼
         │   ┌────────────┐  tasks post
         │   │   TASKS    │ ───────────► micro run --all
         │   └────────────┘     (no Gate 2 — system auto-advances)
         │   ┌──────────┐  pr pre/run
         │   │  IDLE    │ <─────────────────────────────┘
         └── └──────────┘

NOTE: SPECIFY is deprecated as an acceptance-authoring phase. SHARD emits issue outlines; PLAN authors the current-code-informed Gherkin contract; TASKS maps that contract. The post-Tasks `deviate meso approve` hard gate was removed — the system never blocks on human approval. `deviate run` chains meso into micro end-to-end (SPECIFY setup → PLAN → TASKS → micro drain), preserving existing worktree and plan-digest behavior. The legacy SPECIFY → TASKS path remains for backward compatibility but routes through the new merged flow. The SPECIFY step can be bypassed with `--no-setup` (skip worktree + ledger claim); the pipeline then runs in the current working directory on whatever branch is checked out, bypassing the Git Isolation Principle.
```

**Micro layer TDD cycle** (per task, dispatched by `deviate micro run <task-id>` or `deviate micro run --all`):

```
             ┌──────────────┐
             │  PENDING     │   (initial ledger status)
             └──────────────┘
                    │
                    │ red post
                    ▼
             ┌──────────────┐
             │     RED      │ ──(Test Failure Verified)──┐
             └──────────────┘                            │
                    ▲                                    │
                    │ (invalid: PASS/SYNTAX_ERROR)       ▼
                    └───────────────────────────── ┌────────────┐
                                                   │   GREEN    │ <──────────┐
                                                   └────────────┘            │
                                                         ▼                  │
                                                   ┌────────────┐          │
                                                   │   JUDGE    │──────────┘
                                                   └────────────┘ (TRAIN:  │
                                                         │   rejected;   │
                                              Compliance  │   git reset   │
                                              Pass        │   --hard      │
                                                         ▼   <red_sha>)   │
                                                   ┌──────────────┐
                                                   │  REFACTOR    │─┐
                                                   └──────────────┘ │
                                                         │          │ Regression
                                                         │ git      │ rollback
                                                         ▼ restore  ▼
                                                   ┌──────────────────┐
                                                   │   COMPLETED      │
                                                   └──────────────────┘

NOTES:
- The **Green → Judge → Green loop** is the JUDGE → GREEN arrow at the top of
  the GREEN box: on `JUDGE_REJECTED` (or test failure), `_execute_rollback()`
  runs `git reset --hard <red_sha>` against `session.red_commit_sha` followed
  by `git clean -fd` (no `-x`, so gitignored state such as `.deviate/` is
  preserved) and `force_transition_to("GREEN")` sends the session back to
  GREEN with `<train_feedback>` injected — only when that SHA is a standing
  RED-phase failing-test commit. Empty `session.red_commit_sha` on TDD
  `revert_green` is fatal (`ROLLBACK_BOUNDARY_MISSING`) and does not train
  GREEN. GREEN entry without that SHA raises `GREEN_ENTRY_REFUSED`.
  `green_attempts` trains GREEN up to 3 times then escalates; `TRAIN_EXHAUSTED`
  prints after three RED escalates (`red_attempts`).
- RED rollback boundaries are task-local: each fresh RED entry clears any
  boundary retained by a completed prior task before invoking the agent, and
  stores a replacement only after the RED commit succeeds. A pre-manifest
  agent failure cannot expose earlier completed commits to a later rollback.
- TRAIN rollback uses `git reset --hard <boundary_sha>` followed by `git clean -fd` (caller-supplied boundary + untracked cleanup) — never `git revert`, because resetting to the verified-good boundary discards the suspect GREEN cleanly, and `git clean -fd` (without `-x`) removes untracked artifacts that the failed GREEN may have left behind while preserving gitignored state such as `.deviate/`. The boundary is threaded explicitly: TDD JUDGE `revert_green` passes `session.red_commit_sha`; TDD JUDGE `revert_red` derives `red_commit_sha^` via `_resolve_pre_red_sha` (falling back to `session.red_commit_sha` when known, otherwise raising `PhaseFailedError("ROLLBACK_BOUNDARY_MISSING ...")`); EXECUTE JUDGE passes `pre_execute_sha`. Each discard is also captured on a per-task, per-attempt recovery ref `tmp/deviate-agent-work/<sanitized-task-id>/attempt-<N>` so a parent SIGTERM between `git reset` and `git clean` doesn't strand the discarded work and a second rollback cannot clobber the first attempt's recovery handle.
- **EXECUTE commit-failure recovery (terminal contract):** The single
  EXECUTE-phase commit at `src/deviate/cli/micro.py:2857` is the
  only `_commit_phase` call site that intentionally lets the
  project's pre-commit hook gate the commit. To keep routine
  `no_verify=True` RED/GREEN/REFACTOR commits behaving exactly as
  before, the EXECUTE site was switched to
  `_commit_phase_with_recovery(message, root, *, task_id, attempt,
  phase="EXECUTE")`. On `git commit` non-zero, the helper first
  detects the benign clean-worktree case (`git commit` exit 1 with
  "nothing to commit", a message git only emits AFTER the hook chain
  passes, so it cannot mask a hook-blocked commit) and treats it as a
  successful no-op: it returns `True` without creating a recovery ref
  or raising, and the caller's no-diff branch (`JUDGE_SKIP`) completes
  the task (the EXECUTE agent legitimately made zero changes, e.g.
  the deliverable already exists). `_git_env()` pins `LC_ALL=C` so
  the detection is locale-independent. On other non-zero exits, the
  helper
  preserves the staged tree on a per-task recovery ref
  `refs/deviate/recovery/<sanitized-task-id>/attempt-<N>` (a SEPARATE
  namespace from the rollback preservation ref
  `tmp/deviate-agent-work/<task>/attempt-<N>`), prints a recovery
  banner offering two operator-driven recovery options, and raises
  `CommitFailedError(PhaseFailedError, terminal=True)`. The
  exception subclasses `PhaseFailedError` so existing catch sites
  match without code changes; the task is marked FAILED with
  reason `commit_failed`. No `git add`, `git reset`, `git clean`, or
  `git stash` runs after preservation — the operator's index and
  worktree are intact so they can either re-run `git commit` after
  fixing the hook, or `git cherry-pick` the recovery ref after
  explicit cleanup of their own. The banner does NOT prescribe
  `git reset` or `git clean -fd`. The reservation of the attempt
  number is performed ONCE, before any plumbing call, so the
  commit message and the recovery ref name cannot disagree even
  under concurrent failures.
```

---

## 5. Phase Prompts & System Context Injection Boundaries

Agents are bound into specialized operational scopes by context restrictions. Open-ended instructions are forbidden.

### 5.1 Meso Layer Phase Prompts
* **`/deviate-specify` (Deprecated):** Merged into `/deviate-shard`. Shard now emits vertical issue packets carrying `AO-NNN` acceptance outlines; Gherkin belongs to Plan. The legacy skill remains for backward compatibility with a redirect notice.
* **[HITL Gate 2 (REMOVED)]:** The post-Tasks `deviate meso approve` hard gate was removed. Plan authors the Gherkin contract and Tasks decomposes it; the system auto-advances from Tasks into Micro with no human-approval step. Plan and Tasks still commit their artifacts to the worktree for out-of-band review, but execution no longer waits on the human.

* **`/deviate-plan` Context (via `deviate plan pre`):** Spec-enriched issue file (intent + outlines) + Current Codebase State + workstation file paths parsed from the `## System Topology Mapping` section of the issue.
    * *System Directives:* Perform fresh localized research for this specific issue. Read the issue file, scan current codebase state (what exists now, not at epic-explore time), analyze what prior issues implemented via the `specs/issues.jsonl` ledger. Identify integration points, dependencies, potential conflicts. Produce `plan.md` containing the authoritative `## Acceptance Contract` section: every `AO-NNN` from the issue must be reconciled into one or more complete `AC-PLAN-NNN` Given/When/Then scenarios with `Source Outline`, `Upstream Traceability`, `Current-Code Evidence`, and `Verification Mode` blocks (each scenario carries exactly one `**Verification Mode**: automated|manual|deferred` line). Contextualize the issue for downstream task decomposition.
      * **Per-scenario required fields** (every `AC-PLAN-NNN` MUST contain all six): (1) `**Scenario AC-PLAN-NNN: <observable behaviour, imperative present tense>**` header; (2) `**Source Outline**: \`AO-NNN\`[, \`AO-MMM\`…]` — a literal AO token from the issue's `## Acceptance Outline` (comma-separated list allowed for cross-cutting scenarios); (3) `**Upstream Traceability**: \`US-NNN-NN\`, \`FR-NNN-ID\`, \`AC-NNN-ID-NN\`` — at minimum one US, one FR, one AC token from the issue's `## Upstream Requirement Tracing` and `## User Stories Ledger`; (4) `**Current-Code Evidence**: \`<relative path>:<symbol or line>\`` — at least one concrete path reference grounded in the codebase scan; (5) `**Verification Mode**: automated|manual|deferred` — exactly one legal literal (case-insensitive); a missing, repeated, or illegal mode reports a named error; (6) `**Given**:` / `**When**:` / `**Then**:` in that order, each a single imperative sentence with no embedded Gherkin markers, the `**Then**` clause stating a verifiable observable outcome.
      * **Source Outline discipline:** the `**Source Outline**:` value MUST be an AO token literally present in the issue's `## Acceptance Outline`. Ad-hoc labels (`Edge Cases`, `Boundary`, `Constitutional §…`, `RLS`, `Tenant Isolation`, `Hardening`, `Security`) are forbidden and rejected by `deviate plan post` with `missing Source Outline AO-NNN traceability`. Behavioural coverage that does not map cleanly to a single AO (HMAC failure, RLS isolation, defensive boundaries) folds into an existing AO's Error Category or Boundary Category. If no existing AO fits, the issue's outline is incomplete — halt with `INCOMPLETE_ISSUE_OUTLINE` and request that shard/adhoc regenerate the issue rather than inventing a non-AO source.
      * **Acceptance Coverage Invariant:** every AO from the issue's `## Acceptance Outline` MUST appear as the Source Outline of at least one AC-PLAN scenario. An unused AO is a contract defect.
      * **Required sections in canonical order:** `## Plan Summary` → `## Acceptance Contract` → `## Workstation Mapping` → `## Implementation Strategy` → `## Data Flow Analysis` → `## Risk Assessment` → `## Security Profile` → `## Integration Points` → `## Constitutional Alignment`. `AC-PLAN-NNN` identifiers MUST be sequential, zero-padded, and unique. The validator lives at `src/deviate/core/validation.py::validate_acceptance_contract` and the full schema block at `src/deviate/prompts/commands/deviate-plan.md` (mirrored in `src/deviate/prompts/auto/plan.md` for the runtime template).
* **`/deviate-tasks` Context (via `deviate tasks pre`):** Spec-enriched issue file (stories, scope, constraints) + authoritative `plan.md` Acceptance Contract + Codebase Layout Map + constitution command output.
    * *System Directives:* Tasks consumes two sources: the issue for intent and scope, `plan.md` for finalized Gherkin. Legacy issue/spec Gherkin is non-authoritative — the Tasks prompt halts with `PLAN_ACCEPTANCE_CONTRACT_MISSING`/`PLAN_ACCEPTANCE_CONTRACT_INVALID` when `plan.md` is absent or malformed, refusing to fall back to the issue's own Gherkin. Decompose the contract into discrete task entries written to `tasks.md` (the human-authored decomposition document). The CLI subsequently registers these as rows in `tasks.jsonl` (the append-only event ledger). Each task must include implementation hints (file locations, mock boundaries, fixture requirements) alongside the decomposition. Every entry must be assigned a unique tracking identifier (`TSK-{ISSUE_ID}-{NN}`) and must map cleanly to an `AC-PLAN-NNN` scenario in the plan contract. Encode DAG dependencies via `blocked_by` arrays in each task entry. Assign each task an execution type: `tdd` (standard TDD loop), `direct` (boilerplate/config, no RED phase), or `e2e` (end-to-end integration). Type `Verification_Batch` is locked to `IMMEDIATE` (never TDD) — the planner decision tree and `resolve_execution_mode` both enforce this; other types still pick TDD vs IMMEDIATE. For issues with a user-facing workflow (CLI/Web/API surface), emit a terminal `e2e`/`Verification_Batch` task (`IMMEDIATE`, tagged `[E2E]`) that authors `tests/e2e/` user-facing scenarios and runs last; omit it for library/config-internal issues. After Tasks commits `tasks.md`, `deviate run` chains directly into `deviate micro run --all` — no human-approval step.
* **`/deviate-prune` (operational, manual honeycomb thinning):** Single surface for classifying and thinning spy/impl tests. `deviate prune pre` / `post` (`src/deviate/cli/prune.py`, engine `src/deviate/core/prune.py`) resolve one issue per invocation. Prefer test markers/annotations/tags (language-native) and name tags: drop `spy` / `impl`; keep `behavioral` / `ac`. Untagged tests are classified from the body (drop internal spies/mocks/private state; keep public input-to-output / AC) and must not auto-keep. Never unlinks `plan.md`, `tasks.md`, leftover cycle markdown, epic `explore.md` / `prd.md`, shared `specs/adhoc/prd.md`, `specs/**/issues/*.md`, or JSONL ledgers. Manual invoke only — not hooked into micro COMPLETED, `--all`, or the `deviatdd` skill success loop. RED stamps a language-native honeycomb marker (`@pytest.mark.behavioral` / `@pytest.mark.spy` / `@pytest.mark.impl` in Python; `#[behavioral]` in Rust; name segment in Go) on each new test (most are behavioral). Does not change Gate 1, explore, research, review, or ponytail-in-review.

### 5.2 Micro Layer Sandbox Prompts (Reference)

The following system prompt templates are stored in `src/deviate/prompts/auto/` as `.md`
files. They are provided as reference templates — the `deviate` CLI emits context contracts
via JSON at each `pre` subcommand, which the calling agent or skill can use to construct
its own prompts. The exact prompt text is not hard-coded in the CLI source; agent
implementations may choose their own framing as long as the behavioral invariants are
preserved.

**ASD-STE100 writing directive (`src/deviate/prompts/core/style-ste.md`).** Both prompt
composers — `load_template()` (`src/deviate/prompts/assembly.py`, auto mode) and
`compose_command_body()` (`src/deviate/core/commands.py`, manual slash-command mode) —
inject a shared ASD-STE100 Simplified Technical English directive as the last prefix
part, before the phase-specific body. It is self-scoping across two tracks:
**Track A** (prose rules: one idea per sentence, active voice, present tense, ≤~20-word
sentences, one qualifier per noun, approved/concrete vocabulary, explicit quantities,
consistent terminology) applies ONLY when the agent authors natural-language prose in
documents (PRD, design, data-model, architecture, domain-model, flows, release notes, PR
bodies, ADRs, review HTML). **Track B** (structured discipline: exact token preservation,
one semantic per field, no synonym fields, explicit conditions/quantities) applies always,
including to handover manifests and structured output. Neither track rewrites code,
identifiers, file paths, command names, JSON/YAML keys, or quoted structure — when a Track
A rule and a structural constraint collide, the structural constraint wins. This mirrors
STE100's controlled-vocabulary design: clear prose for humans, unambiguous fixed tokens
for machines.

**Single-source prompt derivation (v2.21.0):** the 11 overlapping phase bodies
(`explore`, `research`, `prd`, `shard`, `plan`, `tasks`, `red`, `green`,
`refactor`, `judge`, `execute`) live only in `src/deviate/prompts/auto/{phase}.md`, the
canonical middle bodies. The manual slash commands in `commands/deviate-{phase}.md` were
reduced to frontmatter plus a per-phase manual overlay (pre/post-script lifecycle steps,
rich handover manifest, `<context><user_input>` block), deleting duplicated middle
bodies that had drifted 17-68% from the auto semantics
(`compose_command_body()` / `install_command()` in `src/deviate/core/commands.py`
derive the installed manual body at setup time by splicing the canonical
`auto/{phase}.md` middle verbatim between the platform frontmatter and the overlay —
there is no hand-maintained duplicate middle file to drift from the auto semantics).
`load_template()` (`src/deviate/prompts/assembly.py`, auto mode) keeps
emitting the auto core only; the manual overlay never leaks into the auto path. The
drift-guard tests `TestManualDerivationFromAutoCore` and `TestManualDerivationDriftGuard`
pin the identical-middle invariant across all 11 overlapping phases. The 15
commands-only prompts (adhoc, architecture, constitution, e2e, flows, hotfix, html,
init, merge, pr, prune, release, review, triage, walkthrough) have no auto counterpart
and stay hand-maintained.

### Model Routing & Cache Discipline (Guidance)

The model routing table below is documented as a recommended strategy in the
`specs/constitution.md` seeds and prompt skills. It is **not enforced programmatically**
by the `deviate` CLI. The `--agent` flag on `deviate micro run` (and on the top-level
`deviate run` orchestrator, which forwards it) and the `DeviateConfig.agent.backend`
field configure which agent backend to target, but model selection within the backend is
delegated to the calling environment.

| Phase | Recommended Model | Session | Cache Strategy |
|---|---|---|---|---|
| RED | V4 Flash (default) or V4 Pro (complex tasks) | Task session | Stable prefix |
| GREEN | V4 Flash | Same task session | Cache hit on prefix from RED turn |
| JUDGE | V4 Pro | Isolated session | No cache sharing |
| REFACTOR | V4 Flash | Same task session | Cache hit on prefix from GREEN turn |
| `/deviate-explore` | V4 Flash | Single invocation | One-shot |
| `/deviate-research` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-prd` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-shard` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-adhoc` | V4 Flash | Single invocation | One-shot |
| `/deviate-plan` | V4 Pro | Single invocation (issue-scoped) | One-shot |
| `/deviate-tasks` | V4 Pro | Single invocation (issue-scoped) | 90%+ cache hit after turn 1 when paired with `/deviate-plan` |
| EXECUTE / E2E / HOTFIX | V4 Flash | Single invocation | One-shot |
| `/deviate-prune` | V4 Flash | Single invocation (one issue, manual) | One-shot |

**Cache Discipline — Prohibited Actions During Micro Loops (Aspirational — not yet enforced):**

To preserve KV cache hit rates across the RED → GREEN → JUDGE → REFACTOR cycle:

1. **No model switching mid-cycle.** Each model maintains its own KV cache. Switching the
   model identifier mid-cycle forces full context recomputation at cache-miss pricing.
2. **No tool definition changes.** Adding or removing tool definitions invalidates the
   cached prefix.
3. **No system prompt mutation.** Modifying the system prompt between phases breaks the
   stable prefix.
4. **No appending read-only test files as conversation turns.** Test files that do not
   change during a cycle must be loaded as prefix-stable context (e.g., via `--read` mode),
   not appended as conversation turns (which would push them past the cache prefix boundary).

The `CacheDiscipline` module (`src/deviate/core/cache_discipline.py`) is specified as the
enforcement mechanism but has **not yet been implemented**. These rules currently serve as
guidance for agent implementers and prompt engineers.

* **`PHASE_RED` System Prompt (for `tdd` tasks):**
    ```text
    You are running in DeviaTDD PHASE_RED. Your execution block is write-locked to the test directory for [TASK_ID].
    
    INVARIANTS:
    1. You may only modify or create code files within the designated test paths.
    2. Do not write, patch, or amend any production/business logic directories.
    3. The test code must fail gracefully via AssertionError or NotImplementedError.
    4. Code introducing syntax crashes, import failures, or compile faults will be rejected by the runtime evaluator.
    ```
* **`PHASE_GREEN` System Prompt (for `tdd` and `e2e` tasks):**
    ```text
    You are running in DeviaTDD PHASE_GREEN. Your objective is to pass the test block validated during the RED phase.
    
    INVARIANTS:
    1. You may not edit any test files. Scope audit — you may not modify files outside src/.
    2. Write the clean, optimal production logic required to pass the test assertions.
    3. If you encounter an un-passable design flaw in the test structure, you must immediately halt and declare a structural modification request inside a `<propose_test_amendment>` block.
    ```
* **`PHASE_DIRECT` System Prompt (for `direct` tasks):**
    ```text
    You are running in DeviaTDD PHASE_DIRECT. This task bypasses the RED phase test generation. Your objective is to execute the targeted boilerplate, configuration, or asset synchronization operation.
    
    INVARIANTS:
    1. Write access is scoped tightly to the targeted configuration files (e.g., pyproject.toml, config assets).
    2. Do not generate or modify test files.
    3. Complete the operation cleanly; the Judge phase will verify the change against spec.md.
    ```
* **`PHASE_E2E` System Prompt (for `e2e` tasks):**
    ```text
    You are running in DeviaTDD PHASE_E2E. This task validates end-to-end system integration. Production lines are frozen; no business logic modifications are allowed.
    
    INVARIANTS:
    1. System production files are read-only during this phase.
    2. Orchestrate external runtime environments, databases, or client-server loops as needed.
    3. Verification is performed via exit codes only — assertion failures in business logic constitute a FAIL, not a pass with modifications.
    4. The Judge phase evaluates holistic system flow compliance against spec.md.
    ```
* **`PHASE_JUDGE` (Compliance Gate) System Prompt:**
    ```text
    You are the Compliance Gate Judge. Analyze the production `git diff` for [TASK-ID] against the rules in spec.md.
    
    Verify that no undocumented assumptions, security holes, or structural drift were introduced. If valid, output <verdict>PASS</verdict>. If a violation is present, output <verdict>FAIL</verdict> and include explicit corrections for the execution agent.
    ```

---

## 6. Human-in-the-Loop (HITL) Checkpoint Gates

The framework prevents total autonomy drift by enforcing non-bypassable verification steps where a human supervisor must unlock the transition.

```
[Macro /research]   ──> ( GATE 1: Design Approval ) ──> [PRD ──> Shard (acceptance outlines)]
                                  │
                                  ▼
[Meso /plan → /tasks]  (GATE 2 REMOVED: auto-advance into Micro)  ──> [micro run --all]
                                  │
                                  ▼
[Micro complete]    ──> ( GATE 3: Final Merge Audit ) ──> [review / walkthrough]
```

The remaining HITL gates are Gate 1 and Gate 3 (Gate 2 was removed).

* **Gate 1: Blueprint Approval (After `/deviate-research`, Before `/deviate-prd`)**
    * *Trigger:* Triggered when `design.md` and `data-model.md` are generated by the Research phase.
    * *Action:* Human reviews core architectural selections, design decisions, data models, and tech stacks. PRD and Shard execution remain locked until an approval flag is written.
* **Gate 2: Acceptance & Task Review (REMOVED)**
    * Was: post-`/deviate-tasks`, pre-micro approval enforced via `deviate meso approve` recording `hitl_gate_2_*_sha256` hashes of `plan.md` and `tasks.md` against the active issue. Micro failed closed on missing (`HITL_GATE_2_APPROVAL_REQUIRED`) or stale (`HITL_GATE_2_APPROVAL_STALE`) approval.
    * Rationale for removal: the system never blocks on human approval. Plan and Tasks still commit their authored artifacts to the worktree for out-of-band review, but execution auto-advances into Micro.
* **Gate 3: Final Merge Audit (After micro, via `deviate review` / `deviate walkthrough`)**
    * *Trigger:* The operator (or agent) runs the optional `review` / `walkthrough` packs after micro. Coworker path is one issue = one PR, often `--profile fast` (JUDGE skipped).
    * *Action:* `/deviate-walkthrough` emits the four-look map for THIS issue/PR. `/deviate-review` comments only (stdout and/or GitHub `COMMENT`): named-check checklist + test-weakening + this-issue cross-task drift. A brief with no named checks emits exactly `brief incomplete`. Unclaimed plan-AC tokens are comment input via `uncovered`. Neither command applies, commits, `REQUEST_CHANGES`, or merges.

---

## 7. Multi-Framework Testing Abstraction

DeviaTDD's current implementation (`src/deviate/cli/micro.py`) runs tests through the
language-agnostic `_run_test_cmd()` → `_resolve_verification_command()` (shared with
`deviate red|green|refactor pre` and `_build_auto_prompt` `{test_command}`): a partial
declared verification (file / `-k` / node id) becomes `mise exec -- <command>` when
`mise.toml` / `.mise.toml` is present; a full suite picks an allowlisted named mise
task (`mise unit` / `mise integ` or `mise integration` / `mise test`; `mise e2e` only
when the task says e2e); `mise doctor` is preflight only when defined. Without mise the
order is unchanged: task `verification`, constitution `test_command`, then the
`_MANIFEST_TEST_COMMANDS` manifest table (`mix.exs` → `mix test`, `Cargo.toml` → `cargo test`,
`go.mod` → `go test ./...`, `package.json` → `npm test`, `pyproject.toml` → `pytest`), with a
Python-only fallback (`_find_test_files` globbing `tests/**/test_*.py` → `pytest`) used only
when no other framework is detected. Test discovery follows each project's own convention
(e.g. `test/**/*_test.exs` for Elixir) — the RED gate does not require a Python-style
`tests/**/test_*.py` file. Outcome classification is shared: a red/green phase is decided by
the command's exit code plus `_is_no_tests_collected` (pytest exit 5) and `_is_no_test_command`
(returncode 127) sentinels. `_run_pytest()` remains the Python-specific subprocess runner
(`tests/**/test_*.py` + `python -m pytest -v`), used where a Python command was resolved.

| Testing Framework | CLI Invocation Strategy | Success Validation | Error Parse Pattern | Scope Protection |
| :--- | :--- | :--- | :--- | :--- |
| **Python / pytest** | `python -m pytest tests/ -v` via `_run_pytest()` | `returncode == 0` | `_classify_pytest_outcome()`: checks `SYNTAX_ERROR` markers (SyntaxError, IndentationError, etc.), `ASSERTION_FAILURE`, `PASS`, `UNKNOWN_FAILURE`. | Reverts unauthorized test edits before running suite. |
| **Elixir / ExUnit** | `mix test` (via `_MANIFEST_TEST_COMMANDS`) | `returncode == 0` | exit code + `_is_no_tests_collected` / `_is_no_test_command` | Same. |
| **Rust / cargo** | `cargo test` (via `_MANIFEST_TEST_COMMANDS`) | `returncode == 0` | exit code + `_is_no_tests_collected` / `_is_no_test_command` | Same. |
| **Go / testing** | `go test ./...` (via `_MANIFEST_TEST_COMMANDS`) | `returncode == 0` | exit code + `_is_no_tests_collected` / `_is_no_test_command` | Same. |
| **Node.js / Jest** | `npm test` (via `_MANIFEST_TEST_COMMANDS`) | `returncode == 0` | exit code + `_is_no_tests_collected` / `_is_no_test_command` | Same. |

---

## 8. Core Architectural Invariants & Guardrails

The orchestrator must maintain and enforce these structural constraints across all operations:

1. **The Git Isolation Principle:** Every isolated task loop must be executed on a clean git branch or worktree environment. Commits are made automatically at each phase boundary via `_commit_phase()` in `micro.py` (`test: [{scope}]: RED phase`, `feat: [{scope}]: GREEN phase`, `refactor({scope}): REFACTOR phase`). `deviate micro run --review` (and `--all --review`) inserts an optional HITL pause via `_maybe_review_pause` immediately in front of `_commit_phase` / `_commit_phase_with_recovery` (`git add -A`) on RED, GREEN, REFACTOR, and EXECUTE: the runner prints `REVIEW_PAUSE <phase> <task_id>`, leaves the worktree dirty, and waits for TTY confirmation (`Enter` / yes) before committing. JUDGE feedback commits are not paused. Non-TTY / `--json` / missing stdin fail closed with `REVIEW_REQUIRES_TTY`. Off by default; no config key. This is not Gate 1 or Gate 3 and does not restore Gate 2. Worktrees are created via `deviate specify pre` using `create_worktree()` and removed via `remove_worktree()`. When creating a worktree, after `git worktree add` the orchestrator copies agent skill directories (`.claude/`, `.opencode/`, `.factory/`, `.pi/`, `.omp/`) and `.env` (if present) from the repo root into the worktree so that skills and local configuration are available without re-running `deviate setup`.

2. **The Scope Audit Law:** When entering or running the `GREEN` execution phase, the system checks for unauthorized changes to test, spec, and config directories. Protected files are reverted via `git restore <filepath>`. The JUDGE phase (`deviate judge pre`) additionally performs compliance verification by detecting changes to protected modules declared in `spec.md` `Module:` lines. Complements the GREEN stub-PASS guard in `_run_green_phase` (see `DeviaTDD-api.md` § GREEN Stub-PASS Guard): scope rejects writes the agent shouldn't have made; the stub-PASS guard rejects passes the agent shouldn't have emitted.

3. **Append-Only Ledger Protocol (issues.jsonl + tasks.jsonl):** All state transitions are append-only. Append helpers (`_append_record`, `_append_with_compound_key`) insert a leading newline when a non-empty ledger does not already end in `\n`, so a missing trailing newline cannot fuse two records onto one line; every successful write leaves a trailing newline. `claim_issue` writes through `append_issue_transition`. The global `specs/issues.jsonl` serves as the authoritative issue registry. Issue-scoped micro-task ledgers live at `specs/{FEATURE_SLUG}/{ISSUE_ID}/tasks.jsonl` — the bucket directory (`{FEATURE_SLUG}`) is the epic scope (e.g. `001-…`, `002-…`, or `adhoc`); `{ISSUE_ID}` is the per-epic ordinal matching the issue markdown filename. The `source_file` recorded in `specs/issues.jsonl` follows `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}.md` and the CLI strips the `issues/` segment when mapping to the tasks directory. Agents cannot edit any status fields directly — only the CLI may append events via `append_issue_transition()` and `append_task_transition()`. No existing line is ever modified or overwritten. Canonical state is derived by parsing each ledger using compound-key idempotency (bottom-up for `issues.jsonl`; `(id, status)` compound key for `tasks.jsonl`). For per-issue task ledgers, `COMPLETED` is terminal: once captured, no later non-`COMPLETED` transition may override it; among non-terminal entries, the last by file position wins. Ad-hoc issues bypass macro planning and route directly to isolated execution workspaces.

4. **Deterministic Test Failure Check:** For a `RED` phase to be valid (`deviate red post`), `_classify_pytest_outcome()` must return `ASSERTION_FAILURE`. Return codes of `PASS` or `SYNTAX_ERROR` (SyntaxError, IndentationError, TabError, ImportError, ModuleNotFoundError) are rejected. Current implementation uses string-based parsing of `pytest -v` output; `pytest --json-report` migration is specified but not yet implemented.

5. **Memory Preservation via Train Gates (Green → Judge → Green loop) with 5-way routing:** The JUDGE phase implements Train routing on compliance outcomes. Routing is gated by `HandoverManifest.next_action` (see [specs/DeviaTDD-api.md](./DeviaTDD-api.md) for the routing table): the three rejection routes (`revert_red`, `revert_green`, `skip_refactor`) handle GREEN-test/scope failures, while the two forward routes (`continue_refactor`, `proceed_to_refactor_no_diff`) cover substantive-refactor sign-off and empty-diff GREEN sign-off respectively. `revert_green` (default on violation) preserves RED and advances `session.red_commit_sha` past a feedback commit so a second rejection only kills the subsequent GREEN — only when a RED-phase SHA already exists. Empty `session.red_commit_sha` makes TDD `revert_green` fatal (`PhaseFailedError` carrying `ROLLBACK_BOUNDARY_MISSING`); C1 does not print `ROLLBACK_FAILED` and does not train GREEN. GREEN entry requires a standing RED-phase failing-test SHA; empty SHA or a bare `docs(...): add judge feedback` SHA raises `GREEN_ENTRY_REFUSED`. After `no_failing_test` / `revert_red` / `no_failing_test_adjudicated`, the next `INVOKE_AGENT` is RED, or the loop raises `TRAIN_EXHAUSTED` / `PhaseFailedError`. `revert_red` extends the rollback to past RED (`red_commit_sha^`, defended by a subject-match regex; logs `PRE_RED_AMBIGUOUS` when the parent isn't a RED-phase convention), clears the boundary, and reissues the task from RED via `force_transition_to("RED")`. `proceed_to_refactor_no_diff` is the empty-diff sign-off case — GREEN's diff is intrinsically empty (RED-only deliverable, fixture file, generated types, doc-only slice) and the runner honors `pending_judge_action = "proceed_to_refactor_no_diff"` by entering REFACTOR regardless of the `--no-refactor` CLI flag, where REFACTOR's no-op commit + COMPLETED transition is the only path that terminates the slice. All forward routes skip rollback and route control to `_finish_tdd_cycle` via `session.pending_judge_action` (consumed there), overriding the `--no-refactor` CLI flag — except after a GREEN TEST_FAILURE (implementation ran; suite still red): `continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff` / bare `COMPLIANCE_PASS` remap to TRAIN with the test dump, and `_finish_tdd_cycle` refuses REFACTOR and COMPLETED while that TEST_FAILURE is in effect. Mechanical / test_defect GREEN `status: FAILURE` routing is unchanged. `_execute_rollback()` runs `git reset --hard <red_sha>` followed by `git clean -fd` (without `-x`) to remove untracked artifacts the failed GREEN attempt may have left behind; this discards the suspect GREEN implementation and clears any untracked residue so the next attempt starts from a verified-good test. `_execute_rollback()` persists a `RollbackSnapshot` (branch, current SHA, red SHA, reason) to the task ledger via `append_rollback_snapshot()`. The session is `force_transition_to("GREEN")` and the next GREEN attempt re-runs with `<train_feedback>` injected. On `revert_red` / `revert_green`, `_judge_feedback_from_manifest` strips discarded-commit `path:line` citations from persisted `train_feedback` (session and `tasks.md`) so the next agent is not pointed at lines rollback deleted (GH-103); rollback SHA selection is unchanged. `green_attempts` (max 3) trains GREEN against one RED contract then escalates; `revert_red` escalates now; `TRAIN_EXHAUSTED` prints after three RED escalates (`red_attempts` max 3) and the loop raises `PhaseFailedError` and marks the task `FAILED`.

6. **The Elastic Governance Rule:** The `deviate micro run` command (and the
   top-level `deviate run` orchestrator, which forwards the flag) supports
   `--profile [full|fast]` to control which phases execute. `full` runs
   the complete RED → GREEN → JUDGE → REFACTOR cycle. `fast` runs RED + GREEN
   only (skip JUDGE + REFACTOR). Boolean `--no-judge`/`--no-refactor` flags are retained as
   composable overrides that take precedence over profile defaults. Execution
   profiles and agent backends are configured via `DeviateConfig.agent.backend`.

7. **Atomic Concurrency Protocol (Git Reference Locks):** To eliminate TOCTOU race conditions across distributed terminal instances, the issue claim workflow (formerly `deviate specify pre`, now part of the Plan phase orchestration) uses try-claim semantics. `select_unblocked_candidates()` returns all available BACKLOG issues. The worker iterates through them and attempts `claim_issue()` combined with `create_worktree()`. `_discover_claimable_issue` skips a candidate both when its `feat/<epic>/<slug>` branch already exists on origin (claimed elsewhere) and when that branch already has a local worktree (claimed here) — the local-worktree guard is what lets two parallel terminals on the same checkout claim two different BACKLOG issues even though each claim's SPECIFIED row lives on the feature branch and stays invisible to the main checkout's ledger. Next `NNN` is max(origin ledger, current ledger, remote `feat/<epic>/<NNN>-*` / `feat/adhoc/<NNN>-*`) + 1. Unmerged remote feat refs feed that max. Local-only unpushed feat branches do not reserve. The default claim is local-only: worktree + ledger SPECIFIED + local claim commit, no `git push`. Push-as-lock (`git push -u <remote> <branch>`) is opt-in via `claim_remote = true` in `.deviate/config.toml` (or `deviate setup --claim-remote`). When push-as-lock is on, the server serializes concurrent pushes. The first successful push wins. When `git push` of `feat/.../NNN-*` is rejected because the name exists, the claim path increments the ordinal and retries (cap 3). Collision retry does not set `--local`. Local mode (`--local` on `deviate specify`, `deviate meso run`, or `deviate run`, or `claim_remote = false` / absent key / absent file) keeps the worktree and the ledger claim and skips the remote lock. Existing `claim_remote = true` configs keep pushing. Local mode is not a collision winner. The `tasks.jsonl` ledger records the authoritative outcome.

8. **The Session Continuity Principle:** Session state is persisted to `.deviate/session.json` after each CLI command. The `SessionState` class tracks `current_phase`, `active_issue_id`, and `last_command`. Macro and meso phases transition through `transition_to()` with validation from `_MACRO_TRANSITION_MAP`. Micro phases use `force_transition_to()`. The `_run_single()` function checks `session.current_phase` and supports resume from JUDGE/REFACTOR via optional `start_phase` parameter. Model continuity and KV cache management are delegated to the calling environment.

9. **The Model Tiering Constraint:** Model selection is defined as a recommended strategy in `specs/constitution.md` seeds and prompt skills. The `deviate` CLI does **not** enforce model selection programmatically. The `--agent` flag and `DeviateConfig.agent.backend` field configure agent backends (`opencode`, `claude`, `droid`), but the specific model used within each backend is chosen by the calling environment. The `_SKILL_NAMES` dict in `micro.py` maps `JUDGE → "deviate-judge"` for skill-based agent guidance.

10. **The Issue-Scoped Resolution & Sweep:** task-resolution across micro, e2e, and meso is
    **issue-scoped**, not global. The active issue is resolved from `session.active_issue_id`,
    falling back to a branch-derived lookup via the `feat/{epic}/{issue}` regex against
    `specs/issues.jsonl`. A leftover session id that conflicts with a known feature-branch
    issue yields to the branch, even when the leftover issue still has a `tasks.md` in this
    checkout. The worktree `.deviate/session.json` is rewritten to that branch issue. An
    unresolved non-`feat/` branch keeps a valid session id. This fallback is shared by
    `deviate micro run` (single-task and `--all`), `deviate e2e pre`, and the meso
    `plan`/`tasks` pre/post contract emit, so every command run inside a feature-branch
    worktree targets the branch's own issue even when `.deviate/session.json` has no
    `active_issue_id` or still names a previous issue. Meso claim and `MESO_ALREADY_COMPLETE`
    write the claimed issue into the worktree session. If neither resolves, no micro tasks are
    dispatched (single-task and `--all` emit NO tasks; `e2e pre` and meso either emit an
    issue-less contract or raise `NO_ACTIVE_ISSUE`). Once the issue is
    resolved, only the PENDING tasks for that issue (`_find_all_pending_tasks(root,
    issue_id=...)`) are swept. `NO_PENDING_TASKS` exit 0 is reserved for an empty
    branch-issue queue. Tasks are dispatched sequentially; each task gets up to
    **2 retry attempts** (`_execute_task_with_retry`, `for attempt in range(2)`) before
    being marked `FAILED`. The pipeline **halts on the first failure** (`any_failed = True;
    break`) and exits with code `1`.



11. **The Pipeline Output Discipline:** `_run_all` constructs an `OrchestrationMonitor`
    (`src/deviate/ui/monitor.py`) with `total_tasks` set to the pending count. In TTY mode
    the monitor renders a live Rich dashboard (task markers `[X]` completed, `[/]`
    in-progress, `[ ]` pending, phase transitions). When `--json` is passed, the monitor
    emits JSONL events (`task_started`, `phase_change`, `task_completed`, `task_failed`,
    `pipeline_halted`, `pipeline_complete`) to stdout instead. The `OrchestrationMonitor`
    owns a streaming agent-output callback that forwards each line emitted by the agent
    backend to the dashboard in real time. KeyboardInterrupt triggers
    `monitor.signal_keyboard_interrupt()` and exits with code `130`.

---

## 9. Cost Architecture

DeviaTDD's phase structure is also a cost-optimization architecture. Three mechanisms compound to achieve ~10–30x cost reduction versus naive agentic development approaches:

### 9.1 Model Tiering

| Phase | Recommended Model | 1M Input (cached hit) | Frequency | Cost Profile |
|---|---|---|---|---|---|---|
| `/deviate-explore` | V4 Flash | $0.0028 | Once/feature | Cheap scan |
| RED | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| GREEN | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| REFACTOR | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| `/deviate-plan` + `/deviate-tasks` | V4 Pro | $0.003625 | Once/issue | Premium, cached |
| JUDGE | V4 Pro | $0.003625 | ~5/task | Premium, sparse |
| `/deviate-research`, `/deviate-prd`, `/deviate-shard` | Qwen 3.7+ | varies | Once/feature | Premium, infrequent |
| `/deviate-adhoc` | V4 Flash | $0.0028 | As needed | Cheap |
| EXECUTE / E2E / HOTFIX | V4 Flash | $0.0028 | As needed | Cheap |

Model routing is **guidance, not enforcement** — the `deviate` CLI does not select models.

**Model Resolution Priority Chain:** Both `deviate micro run` and the top-level
`deviate run` accept a `--model <id>` CLI flag. The resolved model ID for each
phase follows this priority (highest first):

1. **Phase-specific config** — `[models].red`, `[models].green`, etc.
2. **CLI `--model` flag** — overrides default config but not phase-specific keys
3. **Default config** — `[models].default` in `.deviate/config.toml`
4. **Backend native default** — no model override passed

**JUDGE phase is excluded from CLI override** to preserve the V4 Pro tiering
mandated by the model routing table above. Phase-specific and default config
keys still apply to JUDGE; only the `--model` flag is blocked.
~85% of all recommended LLM turns use V4 Flash at cache-hit rates.

### 9.2 Continuous-Thread Caching

`/deviate-plan` and `/deviate-tasks` share a single continuous session per issue (replacing the deprecated `/deviate-specify` + `/deviate-tasks` pairing). The system prompt, tool definitions, issue content, and `constitution.md` are written to the KV cache once (first turn, cache-miss pricing) and read at 98%+ discount on every subsequent turn. Without this, each turn would re-send the full context at full price.

Micro-layer tasks dispatched via `deviate micro run <task-id>` reuse the same
in-process state through `SessionState.force_transition_to()`. Each phase is a
synchronous function call within the same process — there is no subprocess or LLM
session restart between phases. The `_commit_phase()` function handles automatic
git commits between phase transitions.
All commit messages are routed through `format_commit_message()` from `src/deviate/core/convention.py`,
which detects the project's emoji convention from ``CONTRIBUTING.md`` / ``.commit-convention.md``
and prepends the appropriate gitmoji when applicable (e.g. `✨ feat(TSK-001-01): add implementation`).
For the red-green TDD cycle, `_commit_phase` accepts an optional `phase` argument; RED phase
`test:` commits are prefixed with 🚨 (siren) and GREEN phase `test:` commits with ✅ (check
mark) via the `PHASE_TEST_EMOJI` map. `feat:` commits always use ✨ regardless of phase, and
unknown `phase` values fall back to `TYPE_EMOJI_MAP["test"]` (✅).

### 9.3 In-Process Dispatch

The `deviate micro run` command avoids subprocess overhead entirely by dispatching
phase transitions in-process via `_PHASE_MAP` function calls. Each phase transition
is a single Python function call that reads session state, appends to the ledger,
and runs synchronous verification (`_run_pytest`, `_detect_phase_changes`,
`_check_return_type_mismatch`). There are no subprocess round-trips between phases
within a single `deviate micro run` invocation. The top-level `deviate run`
orchestrator chains two in-process calls (meso, then micro) but does not add
subprocess overhead beyond what each already does.

### 9.4 HITL Gate Prevention

Each remaining HITL gate prevents wasted downstream compute. A design error caught at Gate 1 saves all `/deviate-prd`, `/deviate-shard`, `/deviate-plan`, `/deviate-tasks`, and Micro cycles. Gate 2 was removed — there is no longer a human check between Tasks and Micro. Each remaining gate is a cheap human check that prevents expensive LLM work.

### 9.5 Task Isolation

Failed RED/GREEN cycles are scoped to a single task. A failed task loses only that task's compute, not the entire feature's. Each task gets a fresh cache — there is no accumulated context debt from prior failures. Module boundary violations are caught by the JUDGE phase and trigger Train rollback without cascading into other task implementations.

---

## 10. Backend Architecture

### 10.0 Agent Dispatch Resilience (v2.9.x)

`AgentBackend.invoke()` adds four dispatch contracts (in order) before
handing the manifest to the rest of the pipeline:

1. **Prompt cap** — `_truncate_prompt` caps every backend prompt at
   `MAX_PROMPT_CHARS = 80,000`, preserving the head + tail and inserting
   a `PROMPT_TRUNCATED` marker. Catches the Gloss 009 failure mode
   where unbounded `plan_content` pushed the TASKS prompt past the
   agent's effective working window.
2. **Streaming stall watchdog** — the streaming path polls
   `time.monotonic()` between chunks. Only stdout resets the hard
   stall clock. Stderr is diagnostic and does not reset the clock.
   The default budget is `STREAM_STALL_TIMEOUT_SECONDS = 900`.
   Periodic stdout keeps the watchdog warm. A few minutes of
   stdout silence inside that 900s budget does not trip the
   detector. EXECUTE passes `stall_timeout=3600`. A stdout-silent
   stall raises `AgentTimeoutError(STALL_DETECTED)`. The same
   poll loop honors `timeout_secs` from the single consolidated
   `DeviateConfig.timeout_seconds` (default 1800s, resolved by
   `resolve_agent_deadline` in `src/deviate/state/config.py`) beside
   the stall detector — the removed `AgentConfig.timeout` field no
   longer exists. A RED child that
   never returns a manifest raises `AgentTimeoutError` inside
   that wall-clock. `invoke` re-raises stall and wall-clock
   timeout. `_invoke_agent` logs `AGENT_TIMEOUT` for a hung RED
   or hung GREEN. `_run_red_phase` restores `red_baseline` with
   `_restore_worktree_to_baseline`. The operator does not wait
   for an outer ~1800s bash kill.
3. **Manifest retry-with-context** — `MalformedHandoverManifestError`
   and `EmptyOutputError` trigger one extra `subprocess.Popen` whose
   prompt embeds the previous parse error and an explicit
   `strict YAML block delimited by ```yaml ... ``` only` directive.
   `AgentSubprocessError` is NOT retried as a manifest failure — it
   is logged and propagated to the micro layer.
4. **YAML hint widening** — `_yaml_error_hint` matches three more
   patterns: backslash-escaped quotes inside double-quoted scalars,
   unbalanced `"` counts, and mis-indented `|` block scalars. The
   original "double-quote your strings" hint is preserved as a
   fallback.
5. **Schema recovery** — missing `phase` / `status` fields are filled
   with `UNKNOWN`, the recovered manifest is annotated with
   `parse_errors`, and `HandoverManifest.is_success` returns `False`
   so the existing `manifest.status.upper() in (...)` gates cannot
   pass a recovered manifest. `HandoverManifest` is imported by
   `scripts/verify_install.py` (the post-install smoke verifier)
   which checks the new constants and the recovery behaviour.
6. **Unescaped evidence-quote recovery (GH-116)** — when
   `yaml.safe_load` fails because an evidence `quote` /
   `test_quote` / `impl_quote` double-quoted scalar embeds raw
   `"`, `_safe_load_handover_yaml` rewrites those lines as `|`
   block scalars and reloads. Well-formed YAML is unchanged.
   Truly malformed YAML still raises
   `MalformedHandoverManifestError`. Verdict and evidence
   semantics are unchanged.
7. **Schema-rejection fail-fast** — the first stderr or stdout line
   that contains `tool_count_limit` or `unsupported_tool_schema`
   kills the child. `invoke` raises `AgentSubprocessError` with those
   tokens. This path does not wait for the 900s stall clock. It does
   not start the 30s timeout retry or the `EmptyOutputError` manifest
   retry. Schema tokens do not reset the stall clock. Stderr stays
   diagnostic for stall liveness (ISS-ADH-025). EXECUTE stall stays
   3600s (GH-53). `_invoke_agent` logs `AGENT_ERROR` with the tokens.
   `deviate micro run` then raises `PhaseFailedError` that includes
   the tokens instead of only `agent returned no manifest`.

| :--- | :--- | :--- | :--- | :--- |
| `opencode` | `opencode run` | Commands copied into `.opencode/commands/` (flat `.md`) | `--model <id>` flag | Default backend |
| `claude` | `claude -p --permission-mode auto` | Commands copied into `.claude/commands/` (flat `.md`) | `--model <id>` flag (may be ignored by host env) | Print mode, auto permission |
| `droid` | `droid exec` | Commands copied into `.factory/commands/` (flat `.md`) | `--model <id>` flag | Factory Droid IDE-owned commands dir |
| `pi` | `pi -p` | Commands file-copied into `<workdir>/.pi/prompts/<name>.md` (project-local; flat top-level only per Pi's documented slash-command convention) | `--model <id>` flag (accepts `provider/model` shorthand) | Lean spawn after `pi -p` / RPC `--no-session`: `--tools read,bash,edit,write`, `--no-skills`, optional `--skill` (no `--no-extensions`, so extension-registered providers load); schema-limit tokens abort as `AGENT_ERROR` |
| `codex` | `codex exec --sandbox workspace-write --ask-for-approval never` | Skills written to `<workdir>/.agents/skills/<name>/SKILL.md` (Codex CLI 0.117+ dropped `.codex/prompts`). Packaged `deviatdd` skill plus one skill folder per slash command. | `--model <id>` flag; when `[agent].reasoning_effort` is set, also `-c model_reasoning_effort=<value>` (official values `minimal\|low\|medium\|high\|xhigh`). `deviate setup --agent codex` seeds `[models].default = "gpt-5.6-luna"` and `[agent].reasoning_effort = "high"` if those keys are missing/empty, and does not clobber a user-set default or thinking level. No repo-wide `.codex/config.toml`. | CLI transport only (no Codex RPC). Prompt via stdin. Do not use `--full-auto` or `--dangerously-bypass-approvals-and-sandbox`. |

Pi implements slash-command discovery natively — `pi -p` loads commands from
`~/.pi/agent/`, `.pi/prompts/`, and `.agents/` on startup, parses the
`name:` + `description:` YAML frontmatter from each `<name>.md` flat file,
and registers them as slash commands. DeviaTDD integrates Pi on top of the
standard `AgentBackend.invoke()` contract with these customisations:

1. **Command file-copy strategy (project-local, flat).** `deviate setup`
   file-copies each project command to `<workdir>/.pi/prompts/<name>.md`
   via the existing `install_command` pipeline — the same code path used
   for `.claude/commands/`, `.opencode/commands/`, and `.factory/commands/`.
   A this-run `global` install (TTY `[g]lobal` or `--agent-export-mode global`)
   writes that layout under `~/.{agent}/…` (Codex: `~/.agents/skills`)
   instead of the project; the choice is not persisted in `config.toml`.
   Pi discovers commands from `.pi/prompts/` natively per its documented
   slash-command convention. The corresponding project-root `.gitignore`
   entries (``*/commands/deviate-*.md``, ``*/prompts/deviate-*.md``) are added by
   `_ensure_root_gitignore` (see `src/deviate/cli/__init__.py:638`),
   preventing the file-copied commands from being committed. The
   single-level ``*/`` prefix scopes each pattern to one directory
   before ``commands/`` or ``prompts/`` — broad enough to cover every
   supported agent (`.claude/commands/`, `.opencode/commands/`,
   `.factory/commands/`, `.pi/prompts/`) plus any future agent, but
   tight enough NOT to match the deviatdd project's own command
   sources at ``src/deviate/prompts/commands/deviate-*.md`` (three
   directories deep). The root gitignore is the single source of
   truth for all agent-platform exclusions; per-agent `.gitignore`
   files were consolidated.
   **DeviaTDD does NOT write to `~/.pi/agent/`** — the operator's global Pi config
   is out of scope. Idempotency: re-running setup with identical command content
   is a no-op (`install_command` compares file content before writing). Total cost
   ≤ 200ms for 31 commands on macOS/Linux.
2. **No `settings.json` generation.** DeviaTDD does not generate a `settings.json`
   file (neither project-local nor under `~/.pi/agent/`). Model/provider selection
   is the operator's responsibility and is configured via Pi's own configuration
   mechanism. The operator's existing `~/.pi/agent/settings.json` is preserved
   across all `deviate setup` runs. This keeps DeviaTDD's blast radius minimal:
   selecting `pi` as a backend does not overwrite or merge into the operator's
   global Pi configuration.
3. **Model flag injection.** Pi print mode (`pi -p`) accepts the
   `--model <id>` flag directly (e.g. `pi --model minimax/MiniMax-M3`) — same
   as `opencode` and `droid`. DeviaTDD therefore injects `--model` for the Pi
   backend via the per-backend `MODEL_FLAGS` map;
   the `provider/model` string from `[models]` is passed verbatim. This is identical
   to `opencode` / `droid` behavior. RPC mode additionally supports Pi's `set_model`
   JSONL command for per-invocation swaps. `claude` uses print mode
   but ignores `--model`).
4. **RPC mode opt-in.** Pi's RPC mode (`pi --mode rpc --no-session`) exposes a
   JSONL-over-stdin/stdout protocol with streaming events (`agent_start`,
   `message_update`, `agent_end`) and a `get_session_stats` command returning
   `tokens.input`, `tokens.output`, `tokens.cacheRead`, `tokens.cacheWrite`. RPC mode
   is **opt-in** via `agent.pi_rpc = true` in `.deviate/config.toml`; default behavior
   is print mode (single-shot, exits after the first assistant turn). When RPC mode is
   active, the `AGENT_RESULT` event in
   `.deviate/logs/run_<UTC>.log` (and the per-task
   `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`) is enriched with a
   observability across repeated phase invocations within the same session.
5. **Lean tool policy.** After the print-mode prefix (`pi -p`) or the
   RPC prefix (`pi --mode rpc --no-session`), `invoke` appends
   `--tools read,bash,edit,write` and `--no-skills`. It omits
   `--no-extensions`: extension-registered providers must load so a saved
   default model from them resolves. When `.pi/skills/deviatdd/SKILL.md` exists under the invoke working
   directory, `invoke` also appends `--skill` to that relative path. A
   missing skill file still keeps the four coding tools. The child does
   not load the operator's global extension or MCP stack.
   `BACKEND_COMMANDS["pi"]` stays `pi -p`. RPC still includes
   `--no-session`. `--model` injection stays on the print-mode path.
6. **Schema-rejection abort.** If child stderr or stdout contains
   `tool_count_limit` or `unsupported_tool_schema`, `invoke` kills the
   child on the first matching line. It raises `AgentSubprocessError`
   with those tokens. `_invoke_agent` logs `AGENT_ERROR` with the same
   text. `deviate micro run` raises `PhaseFailedError` that includes
   the tokens. This path does not wait 900s. It does not treat those
   tokens as stall liveness. EXECUTE stall stays 3600s.

### 10.2.5 Project-Local `deviatdd` Skill (Single Skill, Selected Agent)

In addition to the 25 `deviate-*` slash commands under
`<workdir>/.<agent>/commands/` and `<workdir>/.pi/prompts/`, `deviate setup`
provisions exactly **one** project-local skill named `deviatdd` at
`<workdir>/.<agent>/skills/deviatdd/SKILL.md` for each resolved install agent
(`claude`, `opencode`, `factory`, `pi`, `omp`).
`_resolve_install_agents` (`src/deviate/cli/__init__.py`) always returns a
one-element list of the selected agent. `--agent <name>` pins that target
without prompting. On a TTY, omitted `--agent` always shows the agent
selector (existing `[agent].backend` is the default highlight). Non-TTY
without `--agent` reuses a persisted backend or fail-closes with
`NO_AGENT_SELECTED`. Leftover agent directories are never sprayed.
Codex receives the same skill at
`<workdir>/.agents/skills/deviatdd/SKILL.md` plus one
`.agents/skills/<command>/SKILL.md` per packaged slash command.
`--agent` gates both command and skill install. The skill body is identical
across platforms — only the
destination directory differs.

**Auto-discovery status per platform (informational, does not gate the
write):**

- `claude` — verified. Same form as the user-level
  `~/.claude/skills/<name>/SKILL.md` Agent Skills convention.
- `pi` — verified. `pi@latest` docs at
  `packages/coding-agent/docs/skills.md` list `.pi/skills/` as a
  project-local skill discovery path.
- `opencode` / `factory` — no documented project-local skills
  convention. The file is on disk at
  `<workdir>/.{opencode,factory}/skills/deviatdd/SKILL.md` for
  forward-compat if/when those platforms ship a convention.
- `omp` — libref documents omp skills at user-level
  `~/.omp/agent/managed-skills/<name>/SKILL.md` and via a
  settings-driven `skills` array. Operators register the
  project-local file via OMP's `skills` array in settings.
- `codex` — official project-local discovery is
  `.agents/skills/<name>/SKILL.md`. Codex CLI 0.117+ dropped
  `.codex/prompts` and `/prompts:`.

**Source of truth:** `src/deviate/prompts/skills/deviatdd/SKILL.md`
(package resource, loaded via `importlib.resources`).

**Installer:** `_install_deviatdd_skill(workdir, agents)` in
`src/deviate/cli/__init__.py`, called from `setup()` after
`_install_commands_to_agents`. Idempotent (content-equality skip
mirrors `install_command`'s contract). The skill has no siblings —
there is no `discover_skills()` abstraction.

**Scope:** Unified Meso and Micro orchestration. The skill first invokes
`deviate meso run`. In a linked feature worktree, Meso validates existing
`plan.md` and `tasks.md`, skips completed phases, resumes at Tasks when only
Plan is ready, auto-repairs a plan whose acceptance scenarios lack the
`**Verification Mode**:` line (default `automated`, `PLAN_MODE_REPAIR`), and
stops on genuinely invalid artifacts without overwrite. After Meso
succeeds, the skill invokes bare `deviate micro run` one task at a time.
The existing failure triage and clean-slate safety flow remains. **v1.1.0 added a
`## Troubleshooting failed runs` section** documenting the two
`.deviate/logs/` sinks wired through
`src/deviate/core/run_logger.py::_LogRegistry.dispatch`:
`.deviate/logs/<ISSUE_ID>/<TASK_ID>.log` (per-task transcript;
append-mode history across retries; created only inside
`_execute_task_with_retry` when both `issue_id` and a known
`task_id` resolve — tasks missing either never get a per-task file)
and `.deviate/logs/run_<UTC>.log` (per-run chronological log; one
file per invocation, always written). Each line is `[<UTC iso>]
<EVENT>\n  <kwarg>: <value>\n` (multi-line values indented four-space
under a `key:` header). The authoritative event inventory is the set
of `_log_run("<NAME>", ...)` calls in `src/deviate/cli/micro.py`.
Canonical events for triage: `TASK_FAILED` (carries `error=`;
post-cycle failure — read first), `PHASE_START`, `PHASE_DECISION`
(NOT necessarily terminal — emitted for both intermediate JUDGE
routing decisions and the final CYCLE outcome; interpret via
`decision=` / `reroute=` / `action=` plus `phase=`), `PHASE_SKIP`,
`INVOKE_AGENT` (short line: `task_id=`, `phase=`, `backend=`,
`model=` — no prompt body), `AGENT_RESULT`
(summary: `status=`, `verdict=`, `next_action=` when present —
not the full manifest JSON), `AGENT_TIMEOUT` (carries `error=`, `partial_stderr=`, and `partial_stdout=`; harness verdict for a hung RED or hung GREEN),
`AGENT_ERROR`, `AGENT_NOT_AVAILABLE`, `JUDGE_REJECTED`,
`JUDGE_AGENT_NO_FEEDBACK`, `JUDGE_REFACTOR_NOTE` (carries `note=`,
the refactor hint), `TASKS_MD_NO_MATCH`, `TASKS_MD_FEEDBACK`,
`TASKS_MD_SKIP`, `FEEDBACK_COMMIT_FAILED`, `POST_CMD_FAILURE`
(carries `uncommitted_count=` and `files=`, the dirty files the
hook refused — NOT `returncode=` / `stderr=`), `CYCLE_END`
(emitted when a task leaves `_run_tdd_cycle` — complete, fail,
or skip; carries `task_id=`, `completed=`, `phase_decisions=`
(PHASE_DECISION `action=` values in order this run),
`reject_count=`, `last_blast=` (`red` / `green` / `none`),
`max_streak=`), `LOOP_DETECTED` (same-blast reject streak >= 2).
Transcripts are for diagnosis, not a dump: verbatim agent stdout
and the prompt body live in
`.deviate/logs/<ISSUE_ID>/<TASK_ID>.raw/<phase>-<n>.log` (optional
`<phase>-<n>.prompt.log`).
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
at judge time), `streak` (consecutive same-blast rejects),
`loop` (`true` when `streak >= 2`). When the cycle leaves, one
`{"event":"cycle_end", ...}` object is appended to the same
file with `completed`, `phase_decisions`, `reject_count`,
`last_blast`, and `max_streak`. Do not put the full prompt or raw
agent stdout in this file. Local file only — no dashboard, no
`inspect postmortem`, no upload.
**`[log].agent_reasons`** (`.deviate/config.toml`, default `false`)
gates a short assembled-prompt block asking for a one-line handover
`rationale`. Setup does not write the key. Pre/post/runner logging
never checks the flag.
Skill frontmatter version is `3.0.0`; its description covers Meso preparation and Micro
queue draining. The drift-check test
`test_deviatdd_skill_troubleshooting_section_matches_logger` parses
`micro.py` for `_log_run("<NAME>", ...)` calls and asserts every
backticked event name in the Troubleshooting section is a real
emitted event — guards against invented event names. Per-event
field schemas live in `micro.py` itself, not duplicated here.

**`.gitignore` exclusions:** `_ensure_root_gitignore` adds
`*/skills/deviatdd/` to the entries tuple alongside
`*/commands/deviate-*.md` and `*/prompts/deviate-*.md`. The
single-level wildcard covers every selected-agent skill install
(`.claude/`, `.opencode/`, `.factory/`, `.pi/`, `.omp/`, `.agents/`)
with one pattern. `*/skills/deviate-*/` covers Codex per-command
skill dirs. The single-level prefix (`*/`, not `**/`) is critical: it
scopes the pattern to the project root, never matching the
deviatdd project's own source at
`src/deviate/prompts/skills/deviatdd/` (three directories deep).

**Tests:** `TestInstallDeviatddSkill` in `tests/test_cli/test_init.py`
and `TestSetupSelectedAgentIsolation` / `TestSetupCodex` /
`TestSetupPerAgentInstall` in `tests/test_cli/test_setup.py` cover
selected-agent-only install (TTY pick / `--agent` pin; leftover dirs are not sprayed), Codex skills +
`backend = "codex"` + Luna/`reasoning_effort` upsert, idempotence,
gitignore entry presence + idempotence, the safety-gate fragments in
the SKILL.md body, well-formed frontmatter, and the dispatch table's
canonical slash-command references.


### 10.3 Pi Sandbox Boundary

Pi has no built-in permission system — `pi` runs with the invoking user's full
permissions (per Pi's containerization guidance). DeviaTDD's scope audit restriction
to writes against `src/**/*.py` only therefore applies at the wrapper / pre-commit
hook layer, not at the Pi runtime layer. The micro-sandbox enforcement is identical
to the `opencode` / `claude` / `droid` backends — backend choice is orthogonal to
the enforcement mechanism.

Pi's philosophy of "no sub-agents, no plan mode, no MCP" is compatible with
DeviaTDD's external orchestration model: DeviaTDD orchestrates multiple Pi
invocations externally, one phase per subprocess, with no internal delegation inside
Pi itself. The JUDGE phase's isolation model (running in an isolated V4 Pro session)
is preserved — backend choice is orthogonal to session isolation.

### 10.4 Pi Layer Scope

Pi is registered as a backend for the **micro layer** (RED, GREEN, JUDGE,
REFACTOR) and the **meso layer** (plan, tasks). Macro-layer phases (explore,
research, prd, shard, adhoc) continue to use `opencode` / `claude` / `droid` for this
issue — macro support is deferred to a follow-up if token savings are observed in
practice.
