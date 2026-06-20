# DeviaTDD: Dual Engine Verification Infrastructure for Agentic Test-Driven Development
## Core Architecture, Lifecycle, and Engineering Specification

---

## 1. Architectural Overview & Philosophy
The architecture operates as a hierarchical lifecycle that shifts from human-driven macroscopic scoping to machine-orchestrated, deterministic microscopic execution loops. It is founded on the principle that Large Language Models (LLMs) are probabilistic, optimization-seeking actors that require structured infrastructure containment rather than implicit alignment trust.

```plaintext
                          ┌──────────────┐
                          │ /deviate-adhoc│  (complexity gate: low/medium only)
                          │ Condensed    │
                          │ E+P+S→ Issue │  (spec-enriched with Gherkin)
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ specs/adhoc/ │ → single issue, prd.md, issues.jsonl
                          └──────────────┘

[ MACRO LAYER: Scoping ]    Explore → Research → PRD → Shard+Specify
                                                          │
                                                          ▼
[ MESO LAYER: Contracts ]    [HITL Gate 2] → Plan → Tasks
                                                       │
                                                       ▼
[ MICRO LAYER: TDD Loop ] ──> Red ──> Green ──> Judge/Train ──> Refactor
                                │  ▲
                                ▼  │
                     [ YELLOW: Conditional Amend Gate ]
                     (only triggered by TamperGuard between GREEN and JUDGE)
```

---

## 1.5 Non-Goals: What DeviaTDD Is Not

To maintain strict operational focus and establish explicit boundaries of responsibility, DeviaTDD defines the following items as out-of-scope:

* **Not an Agent Substrate Optimizer:** This framework does not attempt to solve the fundamental reasoning, planning, or context-handling limitations of underlying LLM models. If an execution agent aggressively deviates from its instructions, hallucinates runtime workarounds, or behaves erratically, it is categorized as a failure of model capability rather than an infrastructural flaw.
* **Not a Kernel-Level Sandbox Engine:** DeviaTDD does not implement operating system-level virtualization, container runtimes, or syscall write blocking to actively intercept filesystem manipulation during execution. Instead, it relies on deterministic Git-ledger audits and target-path diff monitoring to passively catch, reject, and roll back invalid agent states.
* **Not a Cost-Optimized Prototyping Utility:** Agentic software verification with multi-stage evaluation loops is inherently token-expensive. DeviaTDD does not prioritize absolute token reduction at the expense of governance. Every validation cycle is treated as a necessary investment for maintaining long-term code integrity.
* **Not an Autonomous, Closed-Loop Software Factory:** This framework completely rejects the premise of unsupervised, self-validating AI development systems. DeviaTDD is explicitly anchored on structured Human-in-the-Loop (HITL) specification boundaries and contract alignment gates.

---

## 2. Hierarchical Architectural Layers

### 2.1 The Macro Layer: Feature Scoping
Breaks a business goal down into standard development project containers.
* **Explore (Cheap Context Gathering):** Fast, inexpensive scan of codebase structure, dependencies, existing patterns, and tech stack. Runs on a cheap model (V4 Flash). Outputs raw factual context to `explore.md` — what exists, not what to do.
* **Research (Architectural Design):** Consumes `explore.md` and performs high-level architectural analysis: trade-offs, options matrix, design decisions, and data modeling. Runs on a reasoning model (Qwen thinking or V4 Pro). Outputs `design.md` (architecture and decisions) and `data-model.md` (entity relationships, schemas).
* **PRD:** Translates `design.md` into a clear, feature-wide requirement set of immutable user requirements and acceptance criteria.
* **Shard:** Breaks down the PRD into standalone technical issue files (GitHub Issues). Each issue must be a **vertical slice** — a complete, testable behavior end-to-end (not a horizontal layer like "add database"). Target ~5 issues per feature shard. Enforce bounds: minimum 3 issues, maximum 10 issues. Each issue must be independently implementable and testable, with clear acceptance criteria.
* **Adhoc (Fast-Path):** A condensed single-command shortcut (`/deviate-adhoc`) that compresses Explore + Research + PRD + Shard into one operation for low-to-medium complexity tasks. Performs proportional exploration (lightweight file scanning, dependency mapping), synthesizes a condensed PRD entry, and emits a single vertical-slice issue directly into `specs/adhoc/`. Appends to the aggregated `specs/adhoc/prd.md` and registers the issue in the global `specs/issues.jsonl` append-only ledger with an `ADH-{NNN}` identifier. A **Complexity Gate** evaluates the task description before proceeding: high-complexity tasks (multi-module coordination, state management, new architecture) are rejected with a directive to run `/deviate-explore` to initiate a full epic workflow instead. This gate prevents scope-creep and ensures adhoc remains a true fast-path, not a bypass for complex engineering.

### 2.2 The Meso Layer: Issue Engineering
Creates formal contracts for an issue via CLI slash commands. The workflow was restructured
(ADHOC-003) to merge `/deviate-specify` into `/deviate-shard` and introduce a dedicated
`/deviate-plan` phase for per-issue localized research. A lightweight PR/merge review is handled by the `/deviate-review` skill using
`deviate review pre` (see `src/deviate/cli/review.py`) at HITL Gate 3. It
runs a fast single-pass scan (V4 Flash) over ledger integrity, cross-task
consistency, and security surface — surfacing findings in chat for human
judgment rather than persisting report files.

* **Shard+Specify (merged):** The `/deviate-shard` skill now produces issue files with full
  spec-level detail: user stories (US-NNN), Gherkin acceptance criteria (Given/When/Then),
  edge cases, performance constraints, and scope boundaries. Issues are born as full
  specifications — no separate `/deviate-specify` step required. The legacy
  `/deviate-specify` skill is marked deprecated and redirects to the new workflow.
* **[HITL Gate 2]:** Human reviews all sharded issues for completeness, edge cases, and
  scope correctness. Moved from after `/deviate-specify` to after `/deviate-shard` to
  match the new workflow. Catches spec errors at the shard boundary before per-issue
  planning and task decomposition proceed.
* **Plan (`deviate plan pre` / `deviate plan post`** — **planned, CLI not yet created):** NEW
  per-issue localized research phase. Performs fresh codebase scanning (what exists now,
  not at epic-explore time), analyzes what prior issues implemented (git log, completed
  issues), identifies integration points, dependencies, and potential conflicts. Produces
  a `plan.md` in the issue workspace with implementation strategy, file mappings, and
  risk assessment. Addresses the problem that epic-level explore/research artifacts become
  stale by the time later issues are worked on.
* **Tasks (`deviate tasks pre` / `deviate tasks post`):** Decomposes the spec-enriched issue
  (plus `plan.md` when available) into a trackable execution blueprint with implementation
  hints, stored in `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.md`. The `pre` subcommand
  resolves the spec-enriched issue for the active work. The `post` subcommand validates and
  commits tasks.md. Each task entry is assigned a unique `TSK-{ISSUE_ID}-{NN}` identifier,
  typed as `tdd`, `direct`, or `e2e`, and includes file locations, mock boundaries, and
  fixture requirements. Automatically appends a terminal `type: "e2e"` task at the bottom
  of every issue's task ledger.
  * **Granularity:** Target ~5 tasks per issue. Each task must be a complete functional unit
    implementable in a single TDD cycle (15-60 min). Avoid "create one file" granularity —
    group related functions into a cohesive unit. Enforce bounds: minimum 3 tasks per issue,
    maximum 10 tasks per issue.
* **PR (`deviate pr pre` / `deviate pr run`):** Creates a GitHub pull request from the current
  worktree branch. The `pre` subcommand validates PR metadata; the `run` subcommand executes
  `gh pr create` and optionally merges upon completion. PR titles are generated in
  conventional-commit format for squash-merge compatibility.
* **Context Sync (Removed):** The `deviate context` command was evaluated and removed.
  Reasoning: every phase/prompt already injects the constitution and relevant specs, making
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
boundaries.** Execution profile (`--profile [full|fast|secure]`) determines which phases are
enforced, replacing the older `--no-judge`/`--no-refactor` boolean flags (retained as
composable overrides).

### Execution Engine

The Micro layer execution engine is implemented as an in-process Python function dispatch
via `src/deviate/cli/micro.py`. The `deviate run <task-id>` command resolves a task by its
`TSK-NNN-NN` identifier from the ledger and dispatches through the phase cycle based on
`execution_mode`:

- **TDD tasks** (`execution_mode: "TDD"`): Full RED -> GREEN -> [TamperGuard gate → YELLOW?]
  -> JUDGE -> REFACTOR cycle via `_run_tdd_cycle()`. YELLOW is NOT in `_PHASE_MAP` — it is
  a conditional branch in the cycle body between GREEN and JUDGE.
- **Non-TDD tasks** (`execution_mode: "DIRECT" | "E2E"`): Immediate completion via
  `_run_execute_phase()`, which marks the task COMPLETED without test generation.

Each phase transition appends a status record to the append-only task ledger using
`append_task_transition()` with compound-key idempotency on `(id, status)`. The JUDGE
phase (`deviate judge pre`) performs compliance verification by comparing changed files
against protected modules declared in `spec.md` `Module:` declarations.

Manual phase execution is supported via individual `pre`/`post` subcommands:
`deviate red pre/post`, `deviate green pre/post`, etc. These are used for interactive
or agent-driven TDD where full automation is not desired.

All `pre` subcommands accept `--json` (emit the phase contract as JSON to stdout) and
`--quiet` (suppress rich console diagnostic output). These flags enable programmatic
consumption by agent runtimes that parse JSON contracts rather than reading human-facing
console output.

Cache optimization strategies (prefix caching, session continuity) are defined as
recommended patterns in `specs/constitution.md` seeds but are **not enforced programmatically**
by the `deviate` CLI. The `--agent` flag on `deviate run` configures which agent backend
to invoke, but model selection is delegated to the calling environment.

#### Task Execution Types

| Type | Description | Phase Gates | Allowed File-Write Boundaries |
| :--- | :--- | :--- | :--- |
| **`tdd`** | Standard TDD loop with RED → GREEN → [YELLOW?] → JUDGE → REFACTOR. Strict assertion failure verification. YELLOW is a conditional branch triggered by TamperGuard when unauthorized test edits are detected during GREEN. | Full state machine with conditional YELLOW branch | RED: `tests/` only. GREEN: `src/` or core modules only. |
| **`direct`** | Bypasses RED phase. Used for boilerplate, dependency config, or asset syncing. No test generation. | GREEN → JUDGE only | Scoped tightly to targeted files (e.g., `pyproject.toml`, config assets). |
| **`e2e`** | End-to-end integration validation. Orchestrates external runtime environments, databases, or client-server loops. Verified via exit codes. | GREEN → JUDGE only | Production lines frozen; no business logic modifications allowed. System-level behavioral evaluation only. |

#### E2E Execution Boundaries

E2E tests are elevated to explicit phases in the state machine, executed at two specific boundaries:
* **Issue Gate (Meso-to-Micro):** When an individual issue's micro-tasks are successfully greened, refactored, and judged, an E2E pass validates that the localized issue changes did not fracture the broader system flow.
* **Feature Branch Gate (Micro-to-Idle):** Before the feature branch merges back into `main`, the orchestrator sweeps the entire system's E2E suite to guarantee holistic compliance.

#### Phase Descriptions

* **RED (The Contract):**
    * **Action:** The agent writes a unit/integration test.
    * **Verification:** The Python runner executes `pytest --json-report`. It parses the JSON to verify the failure is due to missing implementation (`AssertionError`, `NotImplementedError`) and not a syntax crash.
    * **State Lock:** `git add . && git commit -m "test: [TASK-ID] Red phase complete"`.
* **GREEN (The Execution):**
    * **Action:** The agent iterates on production code to pass the test.
    * **Tamper Guard:** Before evaluating the test suite, the CLI runs `git checkout HEAD -- <test_target_file>` to revert any unauthorized modifications the agent made to the test file. (See Section 8.2 for downstream scope auditing).
    * **Timeout Guard:** The runner enforces a hard timeout (e.g., `--timeout=10`) to kill infinite loops.
    * **State Lock:** Upon a valid Green pass, `git add . && git commit -m "feat: [TASK-ID] Green phase complete"`.
* **YELLOW (The Amendment Protocol — Conditional, TamperGuard-Triggered):**
    * **Action:** When TamperGuard detects unauthorized test edits during GREEN (`TamperGuard.evaluate(GREEN_IMPLEMENTATION) == TAMPER_DETECTED`), the CLI transitions session to YELLOW. The agent outputs a `<propose_test_amendment>` block.
    * **Process:** The `yellow_pre` command emits a `YELLOWSkillManifest` contract. The `deviate-yellow` skill guides the agent through the review workflow. An isolated Yellow Judge (V4 Pro) evaluates the amendment against spec.md.
    * **If Approved:** `deviate yellow post --approved` commits the amendments, transitions session to JUDGE (not GREEN), and appends YELLOW_APPROVED to the ledger.
    * **If Rejected:** `deviate yellow post --rejected` runs `git restore .` to revert test changes, transitions session back to GREEN, and appends YELLOW_REJECTED to the ledger.
    * **In auto cycle:** YELLOW is NOT in `_PHASE_MAP`. The conditional branch lives in the `_run_tdd_cycle()` loop body between GREEN and JUDGE phase calls.
* **JUDGE / TRAIN (The Compliance Gate):**
    * **The Judge:** The CLI evaluates `git diff HEAD~1 HEAD` (only the implementation) against `spec.md` for invariant/security violations. Uses `_detect_phase_changes()` and `_find_protected_modules()` from `spec.md` `Module:` declarations. This judge operates in a clean, zero-shared-history session to break recursive subjectivity. A `deviate-judge` skill (loaded from `_SKILL_NAMES["JUDGE"]`) guides the agent through supplementary compliance evaluation.
    * **The Train (Ephemeral Rollback):** If rejected, the CLI safely resets without destroying task progress:
        1. Derive current task states from `tasks.jsonl` into memory. Track the GREEN commit SHA.
        2. Rollback via `git revert --no-edit <green_sha>` (uses precise SHA tracking — never `git reset --hard` which could destroy YELLOW-phase amendments).
        3. Persist a `RollbackSnapshot` to the task ledger.
        4. Inject `<judge_feedback>` into session state via `session.train_feedback`.
        5. Append new state events to `tasks.jsonl` as needed; route the agent back to GREEN.
* **REFACTOR (The Polish Gate):**
    * **Action:** If the Judge accepts the work, the workspace unlocks for an isolated run to polish readability.
    * **Regression Gate:** Post-refactor, the CLI re-runs the test suite. If the tests fail (agent broke code), the CLI safely discards the refactor (`git reset --hard`) and successfully completes the task using the verified Green commit.

---

## 3. Mapping of Architectural Fulfillment

This closed-loop lifecycle converts high-level human intent into strict machine-level invariants. The framework satisfies core development methodologies as follows:

### 3.1 Spec-Driven Development (SDD)
* **How it is fulfilled:** Executed directly via the Macro Layer and Meso Layer.
* **Mechanisms:** The workflow prohibits "vibe coding" or jumping straight into implementation. The framework enforces an artifact-centric approach where a feature must be systematically defined via research, design analysis, Product Requirement Documents (PRDs), and issue sharding. The Macro Layer separates context gathering (`/deviate-explore` — cheap) from architectural reasoning (`/deviate-research` — expensive), then synthesizes requirements (`/deviate-prd`) and decomposes issues (`/deviate-shard`) — shard now produces spec-enriched issue files with full Gherkin acceptance criteria, eliminating the need for a separate `/deviate-specify` step. The Meso Layer adds a per-issue `/deviate-plan` phase for localized research before task decomposition. The CLI commands `deviate tasks pre/post` lock down the execution blueprint (`tasks.md` / `tasks.jsonl`) before a single line of feature code can legally be written.

### 3.2 Test-Driven Development (TDD)
* **How it is fulfilled:** Executed via the Micro Layer: Automated Sandbox.
* **Mechanisms:** This layer implements a pure, unyielding RED-GREEN-REFACTOR loop. The Python CLI enforces that the agent first writes a unit or integration test. It then parses the test runner's JSON output (`pytest --json-report`) to programmatically verify that the test failed due to a missing implementation rather than a syntax crash. The code cannot move forward until a successful Green implementation is verified and locked using atomic Git commits at every step boundary.

### 3.3 Test-Driven Agentic Development (TDAD)
* **How it is fulfilled:** Executed via defensive safeguards embedded in the Micro Layer Sandbox.
* **Mechanisms:** Standard TDD assuming human developers falls short with LLM agents, which are prone to bypassing tests, creating infinite loops, or rewriting assertions to pass falsely. This architecture addresses TDAD directly by adding a Tamper Guard (automatically running `git checkout HEAD -- <test_target_file>` to revert unauthorized test edits) and hard timeout limits. It isolates agent behavior to keep the model strictly trapped within the bounds of deterministic software verification.

### 3.4 Acceptance Test-Driven Development (ATDD)
* **How it is fulfilled:** Achieved through bidirectional requirement traceability and the Meso/Micro Layer transition.
* **Mechanisms:** During the Meso phase, `deviate tasks pre/post` translates high-level customer requirements, user stories, and acceptance criteria into explicit target mapping tags inside `tasks.md` (descriptions, `blocked_by` DAG dependencies, `verifiable_sandbox_target`). In the Micro phase, the Judge Gate evaluates the collective task execution delta directly against the overarching functional constraints of `spec.md`. This guarantees that passing unit tests mathematically equal a passed business acceptance spec.

### 3.5 Evaluation-Driven Development (EDD)
* **How it is fulfilled:** Realized via the Yellow Amend Gate and the Judge/Train Compliance Gate.
* **Mechanisms:** This architecture shifts validation from basic functional checks to prompt optimization and alignment validation. If the execution agent attempts to bend architectural constraints, the isolated Judge evaluates the `git diff` against code-level invariants. When a violation occurs, the Train Gate initiates an ephemeral rollback (`git reset --hard HEAD~1`), writes diagnostic adjustments to the `<judge_feedback>` tag, and feeds that fresh context back into the agent's prompt context. This treats the agent's context window as an iteratively trained parameter optimized for perfect execution compliance.

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
         │                                              │ SHARD+   │  ← merged with Specify
         │                                              │ SPECIFY  │
         │                                              └──────────┘
         │                                                    │
         │                                              shard post
         │                                          (HITL Gate 2)
         │                                                    ▼
         │                                              ┌──────────┐
         │                                              │   PLAN   │  ← NEW per-issue phase
         │                                              └──────────┘
         │                                                    │
         │                                              plan post
         │                                                    ▼
         │   ┌────────────┐   tasks post (loops back)   ┌──────────┐
         ├── │   TASKS    │ <────────────────────────── │  (PLAN)  │
         │   └────────────┘                              └──────────┘
         │         │
         │         │  pr pre/run
         │         ▼
         │   ┌──────────┐
         └── │ IDLE     │
             └──────────┘

NOTE: SPECIFY is deprecated as standalone phase. The merged SHARD+SPECIFY
phase produces spec-enriched issue files directly during shard. PLAN is a new
phase (CLI not yet created). The legacy SPECIFY → TASKS transition still
exists for backward compatibility but routes through the new merged path.
```

**Micro layer TDD cycle** (per task, dispatched by `deviate run <task-id>`):

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
                                                         │                  │
                                              TamperGuard│                  │
                                              TAMPER_DET.│                  │ git
                                              (conditional)                 │ restore
                                                         ▼                  │
                                                   ┌───────────┐            │
                                                   │  YELLOW   │────────────┘
                                                   └───────────┘ (rejected)
                                                         │
                                             Approved    │
                                             Amendment   ▼
                                                   ┌────────────┐
                                                   │   JUDGE    │
                                                   └────────────┘
                                                         │
                                              Compliance │  Violation
                                              Pass       │  (TRAIN: git revert)
                                                         ▼
                                                   ┌──────────────┐
                                                   │  REFACTOR    │─┐
                                                   └──────────────┘ │
                                                         │          │ Regression
                                                         │ git      │ rollback
                                                         ▼ restore  ▼
                                                   ┌──────────────┐
                                                   │  COMPLETED   │
                                                   └──────────────┘

NOTES:
- YELLOW is NOT a fixed phase in _PHASE_MAP — it is a conditional branch
  in the _run_tdd_cycle() loop body between GREEN and JUDGE.
- YELLOW only triggers when TamperGuard.evaluate(GREEN_IMPLEMENTATION)
  returns TAMPER_DETECTED.
- TRAIN rollback uses `git revert --no-edit <green_sha>` (precise SHA tracking)
  — never `git reset --hard` to avoid destroying YELLOW-phase amendments.
```

---

## 5. Phase Prompts & System Context Injection Boundaries

Agents are bound into specialized operational scopes by context restrictions. Open-ended instructions are forbidden.

### 5.1 Meso Layer Phase Prompts
* **`/deviate-specify` (Deprecated):** Merged into `/deviate-shard`. Shard now produces spec-enriched issue files directly. The legacy skill remains for backward compatibility with a redirect notice.
* **[HITL Gate 2]:** Human reviews all sharded issue files (with embedded spec content) for completeness, edge cases, scope correctness. Moved from after `/deviate-specify` to after `/deviate-shard`.
* **`/deviate-plan` Context (planned — CLI not yet created):** Spec-enriched issue file + Current Codebase State + Completed Issues History.
    * *System Directives:* Perform fresh localized research for this specific issue. Read the spec-enriched issue, scan current codebase state (what exists now, not at epic-explore time), analyze what prior issues implemented via git log. Identify integration points, dependencies, potential conflicts. Produce `plan.md` with implementation strategy, file mappings, and risk assessment. Contextualize the issue for downstream task decomposition.
* **`/deviate-tasks` Context (via `deviate tasks pre`):** Spec-enriched issue file + `plan.md` (if available) + Codebase Layout Map + constitution command output.
    * *System Directives:* Decompose the spec-enriched issue directly into discrete task entries written to `tasks.md` (the human-authored decomposition document). The CLI subsequently registers these as rows in `tasks.jsonl` (the append-only event ledger). Each task must include implementation hints (file locations, mock boundaries, fixture requirements) alongside the decomposition. Every entry must be assigned a unique tracking identifier (`TSK-{ISSUE_ID}-{NN}`) and must map cleanly to an acceptance criterion in the issue file. Encode DAG dependencies via `blocked_by` arrays in each task entry. Assign each task an execution type: `tdd` (standard TDD loop), `direct` (boilerplate/config, no RED phase), or `e2e` (end-to-end integration). **Automatically append a terminal `type: "e2e"` task at the bottom of the ledger** to validate the issue's holistic system flow. Target ~5 tasks per issue; enforce 3-10 bounds. When `plan.md` is available, consume its implementation strategy and risk assessment as input to task granularity decisions.

### 5.2 Micro Layer Sandbox Prompts (Reference)

The following system prompt templates are stored in `src/deviate/prompts/auto/` as `.md`
files. They are provided as reference templates — the `deviate` CLI emits context contracts
via JSON at each `pre` subcommand, which the calling agent or skill can use to construct
its own prompts. The exact prompt text is not hard-coded in the CLI source; agent
implementations may choose their own framing as long as the behavioral invariants are
preserved.

### Model Routing & Cache Discipline (Guidance)

The model routing table below is documented as a recommended strategy in the
`specs/constitution.md` seeds and prompt skills. It is **not enforced programmatically**
by the `deviate` CLI. The `--agent` flag on `deviate run` and the `DeviateConfig.agent.backend`
field configure which agent backend to target, but model selection within the backend is
delegated to the calling environment.

| Phase | Recommended Model | Session | Cache Strategy |
|---|---|---|---|---|
| RED | V4 Flash (default) or V4 Pro (complex tasks) | Task session | Stable prefix |
| GREEN | V4 Flash | Same task session | Cache hit on prefix from RED turn |
| YELLOW | V4 Pro | Isolated session | No cache sharing |
| JUDGE | V4 Pro | Isolated session | No cache sharing |
| REFACTOR | V4 Flash | Same task session | Cache hit on prefix from GREEN turn |
| `/deviate-explore` | V4 Flash | Single invocation | One-shot |
| `/deviate-research` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-prd` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-shard` | Qwen 3.7+ | Single invocation | One-shot |
| `/deviate-adhoc` | V4 Flash | Single invocation | One-shot |
| `/deviate-plan` (new) | V4 Pro | Single invocation (issue-scoped) | One-shot |
| `/deviate-tasks` | V4 Pro | Single invocation (issue-scoped) | 90%+ cache hit after turn 1 when paired with `/deviate-plan` |
| EXECUTE / E2E / HOTFIX | V4 Flash | Single invocation | One-shot |

**Cache Discipline — Prohibited Actions During Micro Loops (Aspirational — not yet enforced):**

To preserve KV cache hit rates across the RED → GREEN → [YELLOW?] → JUDGE → REFACTOR cycle:

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
    1. You may not edit any test files. The Tamper Guard automatically resets any mutations to tests.
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
* **`PHASE_AMEND` (Yellow Judge) System Prompt:**
    ```text
    You are the isolated Yellow Gate Auditor. Review the active spec.md, the original failing test structure, and the agent's amendment block request.
    
    Determine if the revision fixes an invalid test assumption or if the agent is trying to escape strict constraints. Output exclusively <status>APPROVED</status> or <status>REJECTED</status> with structured technical analysis.
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
[Macro /research] ──> ( GATE 1: Design Approval ) ──> [PRD ──> Shard+Specify]
                                  │
                                  ▼
[Meso /shard]    ──>  ( GATE 2: Contract Sign-Off )  ──> [/plan → /tasks]
                                  │
                                  ▼
[Meso /tasks]    ──>  ( GATE 2b: Task Review — opt-in for complex features )
                                  │
                                  ▼
[Micro Success] ──>  ( GATE 3: Final Merge Audit )   ──> [Production Deployment]
```

* **Gate 1: Blueprint Approval (After `/deviate-research`, Before `/deviate-prd`)**
    * *Trigger:* Triggered when `design.md` and `data-model.md` are generated by the Research phase.
    * *Action:* Human reviews core architectural selections, design decisions, data models, and tech stacks. PRD and Shard execution remain locked until an approval flag is written.
* **Gate 2: Contract Sign-Off (After `/deviate-shard`, Before `/deviate-plan`) — PRIMARY GATE**
    * *Trigger:* Triggered when shard produces spec-enriched issue files (with Gherkin AC, user stories, edge cases) for all issues in the feature.
    * *Rationale:* Spec errors are the most expensive to fix downstream. Task decomposition is cheap to regenerate (~30s). Catch functional contract errors here before they cascade into 25+ task implementations. Moved from after `/deviate-specify` to after `/deviate-shard` as part of the Meso-Layer Restructuring (ADHOC-003).
    * *Question Budget Rule:* The agent can prompt the user with targeted clarity questions (max 4 per interaction) to resolve functional ambiguity before locking.
    * *Action:* Human reviews each issue file for completeness, edge cases, scope correctness, and architectural alignment. Approval is required before `/deviate-plan` will execute.
* **Gate 2b: Task Review (After `/deviate-tasks` — Opt-in)**
    * *Trigger:* Only for complex features (>7 issues or highly interdependent tasks).
    * *Action:* Human reviews task granularity, DAG dependencies, and implementation hints. Skipped for standard features.
* **Gate 3: Final Merge Audit (Micro-to-Idle Boundary)**
    * *Trigger:* Triggered when all task entries in all issue-scoped `tasks.jsonl` ledgers have reached terminal states (`COMPLETED` or `FAILED`) and all DAG dependencies are satisfied.
    * *Action:* Human evaluates the full atomic Git commit history, total testing metrics, and approves merging the feature branch into main.

---

## 7. Multi-Framework Testing Abstraction

DeviaTDD's current implementation (`src/deviate/cli/micro.py`) supports **pytest** as its
test runner via `_run_pytest()`. The abstraction layer is designed to be extensible to other
frameworks through the `_classify_pytest_outcome()` pattern, which parses stdout/stderr for
syntax errors, assertion failures, and pass states. Currently, `_run_pytest()` collects all
`tests/**/test_*.py` files and runs them with `python -m pytest -v`.

| Testing Framework | CLI Invocation Strategy | Success Validation | Error Parse Pattern | Tamper Guard Reset Path |
| :--- | :--- | :--- | :--- | :--- |
| **Python / pytest** | `python -m pytest tests/ -v` | `returncode == 0` | `_classify_pytest_outcome()`: checks `SYNTAX_ERROR` markers (SyntaxError, IndentationError, etc.), `ASSERTION_FAILURE`, `PASS`, `UNKNOWN_FAILURE`. | `TamperGuard.evaluate(GREEN_IMPLEMENTATION)` — restores `tests/`, `specs/`, `.deviate/` files. |
| **Node.js / Jest** | (Not implemented) | — | — | — |
| **Go / testing** | (Not implemented) | — | — | — |

---

## 8. Core Architectural Invariants & Guardrails

The orchestrator must maintain and enforce these structural constraints across all operations:

1. **The Git Isolation Principle:** Every isolated task loop must be executed on a clean git branch or worktree environment. Commits are made automatically at each phase boundary via `_commit_phase()` in `micro.py` (`test: [{scope}]: RED phase`, `feat: [{scope}]: GREEN phase`, `refactor({scope}): REFACTOR phase`). Worktrees are created via `deviate specify pre` using `create_worktree()` and removed via `remove_worktree()`.

2. **The Tamper Guard & Scope Audit Law:** When entering or running the `GREEN` execution phase, `TamperGuard.evaluate(TamperContext.GREEN_IMPLEMENTATION)` checks for unauthorized changes to test, spec, and config directories. Protected files are reverted via `git restore <filepath>`. If tampering is detected, the session transitions to YELLOW (conditional branch). The JUDGE phase (`deviate judge pre`) additionally performs compliance verification by detecting changes to protected modules declared in `spec.md` `Module:` lines.

3. **Append-Only Ledger Protocol (issues.jsonl + tasks.jsonl):** All state transitions are append-only. The global `specs/issues.jsonl` serves as the authoritative issue registry. Issue-scoped micro-task ledgers live at `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`. Agents cannot edit any status fields directly — only the CLI may append events via `append_issue_transition()` and `append_task_transition()`. No existing line is ever modified or overwritten. Canonical state is derived by parsing each ledger using compound-key idempotency (bottom-up for `issues.jsonl`; `(id, status)` compound key for `tasks.jsonl`). Ad-hoc issues bypass macro planning and route directly to isolated execution workspaces.

4. **Deterministic Test Failure Check:** For a `RED` phase to be valid (`deviate red post`), `_classify_pytest_outcome()` must return `ASSERTION_FAILURE`. Return codes of `PASS` or `SYNTAX_ERROR` (SyntaxError, IndentationError, TabError, ImportError, ModuleNotFoundError) are rejected. Current implementation uses string-based parsing of `pytest -v` output; `pytest --json-report` migration is specified but not yet implemented.

5. **Memory Preservation via Train Gates:** The `deviate yellow post --rejected` path restores changes via `git restore .` without losing session state. The JUDGE phase implements Train rollback on compliance violations: `git revert --no-edit <green_sha>` with precise SHA tracking (never `git reset --hard` to avoid destroying unrelated amendments), then injects `<judge_feedback>` context into the session for the agent's next GREEN attempt. A `RollbackSnapshot` is persisted to the task ledger. The `deviate refactor post` regression check runs `git restore .` on type mismatch or test regression.

6. **The Elastic Governance Rule:** The `deviate run` command supports `--profile [full|fast|secure]` to control which phases execute. `full` runs the complete RED → GREEN → [YELLOW?] → JUDGE → REFACTOR cycle. `fast` runs RED + GREEN only (skip JUDGE + REFACTOR). `secure` runs RED + GREEN + JUDGE (skip REFACTOR). Boolean `--no-judge`/`--no-refactor` flags are retained as composable overrides that take precedence over profile defaults. Execution profiles and agent backends are configured via `DeviateConfig.agent.backend`.

7. **Atomic Concurrency Protocol (Git Reference Locks):** To eliminate TOCTOU race conditions across distributed terminal instances, the issue claim workflow (formerly `deviate specify pre`, now part of the Plan phase orchestration) uses try-claim semantics: `select_unblocked_candidates()` returns all available BACKLOG issues, and the worker iterates through them attempting `claim_issue()` combined with `create_worktree()` and `git push -u <remote> <branch>`. The server serializes concurrent pushes; the first successful push wins. The `tasks.jsonl` ledger records the authoritative outcome.

8. **The Session Continuity Principle:** Session state is persisted to `.deviate/session.json` after each CLI command. The `SessionState` class tracks `current_phase`, `active_issue_id`, and `last_command`. Macro and meso phases transition through `transition_to()` with validation from `_MACRO_TRANSITION_MAP`. Micro phases use `force_transition_to()`. The `_run_single()` function checks `session.current_phase` and supports resume from YELLOW/JUDGE/REFACTOR via optional `start_phase` parameter. Model continuity and KV cache management are delegated to the calling environment.

9. **The Model Tiering Constraint:** Model selection is defined as a recommended strategy in `specs/constitution.md` seeds and prompt skills. The `deviate` CLI does **not** enforce model selection programmatically. The `--agent` flag and `DeviateConfig.agent.backend` field configure agent backends (`opencode`, `claude`, `droid`), but the specific model used within each backend is chosen by the calling environment. The `_SKILL_NAMES` dict in `micro.py` maps `YELLOW → "deviate-yellow"` and `JUDGE → "deviate-judge"` for skill-based agent guidance (both previously missing).

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
| YELLOW | V4 Pro | $0.003625 | Conditional | Premium, rare |
| `/deviate-research`, `/deviate-prd`, `/deviate-shard` | Qwen 3.7+ | varies | Once/feature | Premium, infrequent |
| `/deviate-adhoc` | V4 Flash | $0.0028 | As needed | Cheap |
| EXECUTE / E2E / HOTFIX | V4 Flash | $0.0028 | As needed | Cheap |
| `/deviate-adhoc` | V4 Flash | $0.0028 | As needed | Cheap |
| EXECUTE / E2E / HOTFIX | V4 Flash | $0.0028 | As needed | Cheap |

Model routing is **guidance, not enforcement** — the `deviate` CLI does not select models.
~85% of all recommended LLM turns use V4 Flash at cache-hit rates.

### 9.2 Continuous-Thread Caching

`/deviate-plan` and `/deviate-tasks` share a single continuous session per issue (replacing the deprecated `/deviate-specify` + `/deviate-tasks` pairing). The system prompt, tool definitions, issue content, and `constitution.md` are written to the KV cache once (first turn, cache-miss pricing) and read at 98%+ discount on every subsequent turn. Without this, each turn would re-send the full context at full price.

Micro-layer tasks dispatched via `deviate run <task-id>` reuse the same in-process state
through `SessionState.force_transition_to()`. Each phase is a synchronous function call
within the same process — there is no subprocess or LLM session restart between phases.
The `_commit_phase()` function handles automatic git commits between phase transitions.

### 9.3 In-Process Dispatch

The `deviate run` command avoids subprocess overhead entirely by dispatching phase transitions
in-process via `_PHASE_MAP` function calls. Each phase transition is a single Python function
call that reads session state, appends to the ledger, and runs synchronous verification
(`_run_pytest`, `TamperGuard.evaluate`, `_detect_phase_changes`, `_check_return_type_mismatch`).
There are no subprocess round-trips between phases within a single `deviate run` invocation.

### 9.4 HITL Gate Prevention

Each HITL gate prevents wasted downstream compute. A design error caught at Gate 1 saves all `/deviate-prd`, `/deviate-shard`, `/deviate-plan`, `/deviate-tasks`, and Micro cycles. A spec error caught at Gate 2 saves all per-issue planning, task decomposition, and Micro cycles. Each gate is a cheap human check that prevents expensive LLM work.

### 9.5 Task Isolation

Failed RED/GREEN cycles are scoped to a single task. A failed task loses only that task's compute, not the entire feature's. Each task gets a fresh cache — there is no accumulated context debt from prior failures. Module boundary violations are caught by the JUDGE phase and trigger Train rollback without cascading into other task implementations.

---

## 10. Tree-Sitter AST Integration (ISS-ADH-008)

### 10.1 Module: `src/deviate/core/treesitter.py`

A new Python AST parsing module built on `tree-sitter` (v0.24+) with the `tree-sitter-python`
bundled grammar. Provides deterministic, incremental structural analysis with no runtime
grammar compilation. The module caches a singleton `Parser` instance at import time via
`_get_parser()`.

**Public API:**

| Function | Signature | Purpose |
|---|---|---|
| `extract_changed_symbols()` | `(diff_text: str) -> list[dict]` | Parse `git diff` output; return changed `FunctionDef`/`ClassDef` nodes with `type`, `file`, `old_signature`, `new_signature`. Empty input → empty list. |
| `extract_file_structure()` | `(source: str) -> dict` | Parse a source string; return `{functions, classes, imports}` with parameter lists, return type annotations, and method decompositions. Invalid input → empty structure (graceful degradation). |
| `incremental_parse()` | `(source: str, old_tree) -> Tree` | Parse source bytes, optionally reusing an existing `Tree` — tree-sitter re-parses only changed byte ranges (TS incremental parsing). |

**Performance budgets** (per AC-ADHOC-008): `extract_file_structure()` ≤200ms initial,
≤20ms incremental; `extract_changed_symbols()` ≤100ms; all refactor checks ≤300ms initial,
≤50ms incremental.

### 10.2 JUDGE Phase Integration

**File:** `src/deviate/cli/micro.py:1151-1154`

After collecting `git diff RED..HEAD` output, `_run_judge_phase()` calls
`extract_changed_symbols(diff)` and formats the result via `_build_structured_diff_summary()`
into a `## Structured Diff Summary` markdown block. This block is injected between the
base prompt (from `/judge.md` template) and the raw `<diff>` block.

**Token savings:** The structured summary is ≤500 tokens (only changed FunctionDef/ClassDef
signatures with file paths) vs. the raw diff which can be 3000+ tokens for files with
unchanged boilerplate. Since JUDGE runs on V4 Pro ($0.435/M cache-miss input), this
achieves ~15x token reduction on the diff portion.

**Graceful degradation:** If `diff` is empty or contains no parseable Python symbols,
the structured section is skipped and only the raw diff appears.

### 10.3 PLAN Phase Integration

**File:** `src/deviate/cli/meso.py:1081-1162`

During `_invoke_agent_phase("plan", ...)`, the helper `_enrich_plan_prompt()` calls
`_build_file_structure_appendix(contract)` which:

1. Reads the issue spec file from `contract["spec_path"]`
2. Scans for the `## System Topology Mapping` section and extracts file paths from
   `Primary Architectural Workstations` bullet items (regex: `` `path/to/file.py` ``)
3. For each existing `.py` file, calls `extract_file_structure()` and formats signatures
4. Injects the result as `## Target File Structure` appendix into the agent prompt

**Token savings:** Pre-scanned file structure (function signatures, class methods, imports)
replaces the need for the V4 Pro agent to read entire target files to find insertion points.
For a typical 200-line file with 5 functions, ~15 tokens of signatures replace ~200 tokens
of full source.

**Edge cases:** Missing `System Topology Mapping` → empty appendix; file listed but absent →
skipped with warning; non-Python files → skipped silently.

### 10.4 REFACTOR Phase Integration

**File:** `src/deviate/cli/micro.py:2599-2700`

The legacy `_check_return_type_mismatch()` (stdlib `ast.parse`) was replaced entirely with
tree-sitter-based checks. The stdlib `ast` import was removed. New checks:

| Check | Function | Detection | Issue Prefix |
|---|---|---|---|
| Return type mismatch | `_ts_check_return_type()` | Validates `str`/`int`/`float`/`bool`/`list`/`dict`/`tuple`/`set` annotated returns match actual `return` expression types via tree-sitter query | None |
| Dead code | `_ts_check_dead_code()` | Flags private functions (prefixed `_`) with zero call-site references in the same file | `DEAD_CODE:` |
| Cyclomatic complexity | `_ts_check_cyclomatic_complexity()` | Counts `if`/`elif`/`for`/`while`/`except`/`with`/boolean_operator nodes; warns at ≥10 | `COMPLEXITY:` |

All checks use `incremental_parse()` when an `old_tree` is available (passed from the
previous REFACTOR cycle), re-parsing only changed byte ranges for large files.

### 10.5 SHARD Phase Integration

**File:** `src/deviate/cli/macro.py:543-571`

`_build_codebase_structure_appendix()` in `shard_pre()` scans the entire `src/` directory
for Python files, calls `extract_file_structure()` on each, and formats the result as a
`## Codebase Structure` appendix. This is injected into the shard contract under the
`codebase_structure_appendix` key and consumed by the shard agent prompt template
(`src/deviate/prompts/auto/shard.md` via `${codebase_structure_appendix}`).

The appendix covers imports, top-level function signatures, and class hierarchy (class
names with their method lists). Missing `src/` directory or empty scan yields an empty
string (no appendix), preserving existing behavior.

### 10.6 ADHOC Flow Integration

**File:** `src/deviate/cli/adhoc.py:94-119`

`_build_codebase_structure_artifact()` in `adhoc pre` (after complexity gate) scans the
`--scan-dir` directory (default `src/`) for Python files, calls `extract_file_structure()`,
and writes a persisted `specs/adhoc/codebase_structure.md` markdown artifact. The artifact
path is emitted in the contract as `codebase_structure_path`.

The `/deviate-adhoc` skill prompt (`src/deviate/prompts/skills/deviate-adhoc/SKILL.md`)
step 3 was updated to read this artifact first for pre-extracted file signatures before
falling back to grep/glob.

**Staleness note:** The artifact is generated at `adhoc pre` time and may become stale if
source files are modified between `adhoc pre` and agent execution. The skill prompt
documents this limitation and instructs the agent to verify critical file positions.

### 10.7 Dependencies & Grammar Loading

- `tree-sitter>=0.24` — core parsing library (declared in `pyproject.toml`)
- `tree-sitter-python` — pre-built Python grammar (bundled, no compilation step)
- Grammar loaded at module import time: `Language(tree_sitter_python.language())`
- Singleton parser cached in `_PARSER` module variable (thread-safe for CLI use)
- If grammar cannot be loaded, `ImportError` with clear diagnostic message — no silent
  fallback to stdlib `ast`

### 10.8 Defensive Exclusions

Per the Pareto analysis in `issues/008-ast-phase-prioritization.md`, the following phases
do NOT invoke tree-sitter:
- **RED** (V4 Flash: test stubs need no AST)
- **GREEN** (V4 Flash: implementation writes, not analysis)
- **YELLOW** (V4 Pro: fires rarely, low aggregate ROI)
- **TASKS** (V4 Pro: text decomposition, no code to parse)
- **MACRO** explore/research/prd (V4 Flash/Qwen: operate on markdown, not Python code)
- **TamperGuard** (file hashing already catches unauthorized edits)
