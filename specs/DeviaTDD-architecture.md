# DeviaTDD: Dual Engine Verification Infrastructure for Agentic Test-Driven Development
## Core Architecture, Lifecycle, and Engineering Specification

---

## 1. Architectural Overview & Philosophy
The architecture operates as a hierarchical lifecycle that shifts from human-driven macroscopic scoping to machine-orchestrated, deterministic microscopic execution loops. It is founded on the principle that Large Language Models (LLMs) are probabilistic, optimization-seeking actors that require structured infrastructure containment rather than implicit alignment trust.

```plaintext
                          ┌──────────────┐
                          │ /deviate-flows│  (optional, FLOW-01 — customer flows)
                          │ FLOW-01      │
                          │ Actor/Domain │
                          └──────┬───────┘
                                 ▼
[ PRODUCT LAYER: Framing ] /deviate-architecture /deviate-release
                          (FLOW-02 cross-epic contract)   (FLOW-03 next release)
                          → specs/_product/architecture.md (includes ADRs) → specs/_product/release-next.md
                                 │
                                 ▼  (downstream shard/adhoc read flow_refs: from issue frontmatter)
                          ┌──────────────┐
                          │ /deviate-adhoc│  (complexity gate: low/medium only)
                          │ Condensed    │
                          │ E+P+S→ Issue │  (spec-enriched with Gherkin)
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ specs/adhoc/ │ → single issue, prd.md, issues.jsonl
                          └──────┘

[ MACRO LAYER: Scoping ]    Explore → Research → PRD → Shard+Specify
                                                          │
                                                          ▼
[ MESO LAYER: Contracts ]    [HITL Gate 2] → Plan → Tasks
                                                       │
                                                       ▼
[ MICRO LAYER: TDD Loop ] ──> Red ──> Green ──> Judge/Train ──> Refactor
                                │  ▲    ▲                  ▲     │
                                ▼  │    │                  │     │
                                   │    │  next_action on   │     │
                                   │    │  HandoverManifest │     │
                                   │    │  (4-way routing)  │     │
                                   │    │                  │     │
              ┌────────────────────┘    └──────────────────┘     │
              │  Green → Judge → Green loop (TRAIN):             │
              │  JUDGE_REJECTED → git reset --hard <red_sha>      │
              │  + git clean -fd + feedback commit + advance      │
              │  session.red_commit_sha → force_transition       │
              │  ("GREEN") → re-run GREEN with <train_feedback>  │
              │  injected (up to max_train_attempts = 3)         │
              │                                                   │
              │  next_action=revert_before → reset to            │
              │  red_commit_sha^, clear red_commit_sha,           │
              │  force_transition("RED") → re-author RED         │
              │  next_action=continue_refactor → no rollback,    │
              │  pending_judge_action → _finish_tdd_cycle         │
              │  enters REFACTOR regardless of --no-refactor      │
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

---

## 2. Hierarchical Architectural Layers

### 2.1 The Macro Layer: Feature Scoping
Breaks a business goal down into standard development project containers.
* **Explore (Cheap Context Gathering):** Fast, inexpensive scan of codebase structure, dependencies, existing patterns, and tech stack. Runs on a cheap model (V4 Flash). Outputs raw factual context to `explore.md` — what exists, not what to do.
* **Research (Architectural Design):** Consumes `explore.md` and performs high-level architectural analysis: trade-offs, options matrix, design decisions, and data modeling. Runs on a reasoning model (Qwen thinking or V4 Pro). Outputs `design.md` (architecture and decisions) and `data-model.md` (entity relationships, schemas).
* **PRD:** Translates `design.md` into a clear, feature-wide requirement set of immutable user requirements and acceptance criteria.
* **Shard:** Breaks down the PRD into standalone technical issue files (GitHub Issues). Each issue must be a **vertical slice** — a complete, testable behavior end-to-end (not a horizontal layer like "add database"). Target 4-8 issues per feature shard. Enforce bounds: minimum 1 issue, maximum 10 issues. A single-issue shard is valid (the option to have used `/deviate-adhoc` has passed by the time shard runs). Each issue must be independently implementable and testable, with clear acceptance criteria. **Slicing rules live entirely in the `deviate-shard` prompt** (Pass 1 flow-anchored clustering, Pass 1.5 hard cap with `SLICE_CAP_EXCEEDED`, Pass 3.5 horizontal-slice merging); the PRD prompt only shapes FRs via flow-segment authoring guidance, never pre-decides groupings.
* **Adhoc (Fast-Path):** A condensed single-command shortcut (`/deviate-adhoc`) that compresses Explore + Research + PRD + Shard into one operation for low-to-medium complexity tasks. Performs proportional exploration (lightweight file scanning, dependency mapping), synthesizes a condensed PRD entry, and emits a single vertical-slice issue directly into `specs/adhoc/`. Appends to the aggregated `specs/adhoc/prd.md` and registers the issue in the global `specs/issues.jsonl` append-only ledger with an `ADH-{NNN}` identifier. A **Complexity Gate** evaluates the task description before proceeding: high-complexity tasks (multi-module coordination, state management, new architecture) are rejected with a directive to run `/deviate-explore` to initiate a full epic workflow instead. This gate prevents scope-creep and ensures adhoc remains a true fast-path, not a bypass for complex engineering.

* **Active Domain Discipline (HITL gates):** The macro phases that interact with the human (`/deviate-research` Gate 1, `/deviate-prd` Ambiguity Interrogation, `/deviate-shard` Gate 2) actively term-challenge against the upstream glossary, sharpen fuzzy language, stress-test with concrete edge-case scenarios, and update the relevant artifact (`design.md`, `data-model.md`, `prd.md`) inline as terms resolve — not as a passive sign-off step.

### 2.2 The Meso Layer: Issue Engineering
Creates formal contracts for an issue via CLI slash commands. The workflow was restructured
(ADHOC-003) to merge `/deviate-specify` into `/deviate-shard` and introduce a dedicated
`/deviate-plan` phase for per-issue localized research. A lightweight PR/merge review is handled by the `/deviate-review` skill using
runs a fast single-pass scan (V4 Flash) over ledger integrity, cross-task
consistency, and security surface — surfacing findings in chat for human
judgment rather than persisting report files.

Alongside the review, `/deviate-walkthrough` (see `src/deviate/cli/walkthrough.py`)
provides a human-guided architectural tour of the same diff. Unlike the review's
structured seven-domain scan, the walkthrough curates the diff into a narrative
— spotlighting architectural decisions the automated phases (JUDGE, REFACTOR,
REVIEW) missed, grouping changes by concern rather than file path, and letting
the user control depth. It is the more human counterpart to the review, designed
to build codebase comprehension and surface hidden trade-offs.

* **Shard+Specify (merged):** The `/deviate-shard` skill now produces issue files with full
  spec-level detail: user stories (US-NNN), Gherkin acceptance criteria (Given/When/Then),
  edge cases, performance constraints, and scope boundaries. Issues are born as full
  specifications — no separate `/deviate-specify` step required. The legacy
  `/deviate-specify` skill is marked deprecated and redirects to the new workflow.
* **[HITL Gate 2]:** Human reviews all sharded issues for completeness, edge cases, and
  scope correctness. Moved from after `/deviate-specify` to after `/deviate-shard` to
  match the new workflow. Catches spec errors at the shard boundary before per-issue
  planning and task decomposition proceed.
* **Plan (`deviate plan pre` / `deviate plan post`):** Per-issue localized research phase
  that performs fresh codebase scanning (what exists now, not at epic-explore time),
  analyzes what prior issues implemented (via the `specs/issues.jsonl` ledger), and
  parses workstation file paths from the issue's `## System Topology Mapping` section
  (calling `extract_file_structure()` from `deviate/core/treesitter.py` on each
  existing workstation file). The `pre` subcommand is dual-mode: outside a linked
  worktree it auto-discovers the next claimable unblocked BACKLOG issue, creates the
  worktree, claims the issue, force-transitions the session to `PLAN`, and syncs
  `.deviate/` into the new worktree; inside a linked worktree it emits a `plan_pre`
  JSON contract for the agent. The `post` subcommand validates `plan.md` is non-empty
  and commits it with a convention-aware message (emoji-prefixed when the project's
  CONTRIBUTING.md or git history indicates emoji usage), then transitions the
  session to `TASKS`. Addresses the problem that epic-level explore/research artifacts
  become stale by the time later issues are worked on.
* **Tasks (`deviate tasks pre` / `deviate tasks post`):** Decomposes the spec-enriched issue
  (plus `plan.md` when available) into a trackable execution blueprint with implementation
  hints, stored in `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.md`. The `pre` subcommand
  resolves the spec-enriched issue for the active work. The `post` subcommand validates and
  commits tasks.md. Each task entry is assigned a unique `TSK-{ISSUE_ID}-{NN}` identifier,
  typed as `tdd`, `direct`, or `e2e`, and includes file locations, mock boundaries, and
  fixture requirements. An agent MAY append a terminal `type: "e2e"` task for issues
  modifying user-facing behavior, but it is no longer mandatory.
  * **Plan digest data flow:** After PLAN commits `plan.md`, the meso orchestrator builds
    a 16 KiB UTF-8 digest (`_build_plan_digest` in `src/deviate/cli/meso.py`). The digest
    keeps the head + tail of the plan and inserts a `PLAN_DIGEST_TRUNCATED` marker when
    the source plan exceeds 16 KiB. The auto prompt `src/deviate/prompts/auto/tasks.md`
    exposes the digest as a `<plan_digest>` literal block (a leading template with
    `{plan_digest}` would re-inject the payload) plus a `<plan_path>` pointer the agent
    uses as a fallback when the marker is present. This bounds the per-phase prompt
    size so a runaway plan cannot stall the TASKS agent (Gloss 009).
  * **Granularity:** Target 4-8 tasks per issue. Each task must be a complete functional unit
    implementable in a single TDD cycle (15-60 min). Avoid "create one file" granularity —
    group related functions into a cohesive unit. Enforce bounds: minimum 1 task per issue,
    maximum 10 tasks per issue.
* **PR (`deviate pr pre` / `deviate pr run`):** Creates a GitHub pull request from the current
  worktree branch. The `pre` subcommand validates PR metadata; the `run` subcommand executes
  `gh pr create` and optionally merges upon completion. PR titles are generated in
  conventional-commit format for squash-merge compatibility.
* **Merge (`deviate merge` + `/deviate-merge` skill):** Final meso-layer gate that performs
  the squash-merge into `main` and writes a full Pydantic-validated `IssueRecord` (not a
  bare transition). The CLI is intentionally two-phase: `--stage-only` writes the COMPLETED
  transition to `specs/issues.jsonl` and stages it; `-m <subject> -m <body>` then commits
  the feature changes + ledger in a single atomic commit. The transition write is idempotent
  so re-running `--stage-only` before `--message` is safe. `--delete-branch` owns the full
  post-merge lifecycle in a single call: tags the pre-squash branch tip with
  `archive/{ISSUE_ID}/{YYYY-MM-DD}` (preserving the per-commit graph that
  `git merge --squash` collapses into a single main commit), pushes the tag to `origin`,
  `git push origin --delete <branch>`-es the remote, removes any active worktree that holds
  the branch, and runs `git branch -D`. Tag push and remote branch delete are best-effort:
  no `origin` → silent skip; unreachable remote → `PUSH_WARN` and local cleanup proceeds,
  so a transient network blip never strands work on disk. Invariant: exactly one commit on
  `main` per issue, containing both the feature code and the COMPLETED ledger entry; the
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
boundaries.** Execution profile (`--profile [full|fast|secure]`) determines which phases are
enforced, replacing the older `--no-judge`/`--no-refactor` boolean flags (retained as
composable overrides).

### Execution Engine

The Micro layer execution engine is implemented as an in-process Python function dispatch
via `src/deviate/cli/micro.py`. The `deviate micro run <task-id>` command (the per-task
dispatcher that used to live as top-level `deviate run`) resolves a task by its
`TSK-NNN-NN` identifier from the ledger and dispatches through the phase cycle based on
`execution_mode`. The top-level `deviate run` orchestrator (`src/deviate/cli/__init__.py`)
chains `deviate meso run` with `deviate micro run --all` inside the created worktree;
see `DeviaTDD-api.md` §5 for the orchestration contract.:

- **TDD tasks** (`execution_mode: "TDD"`): Full RED -> GREEN -> JUDGE -> REFACTOR cycle via `_run_tdd_cycle()`.
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
by the `deviate` CLI. The `--agent` flag on `deviate micro run` (and on the top-level
`deviate run` orchestrator, which forwards it to micro) configures which agent backend
to invoke, but model selection is delegated to the calling environment.

#### Task Execution Types

| Type | Description | Phase Gates | Allowed File-Write Boundaries |
| :--- | :--- | :--- | :--- |
| **`tdd`** | Standard TDD loop with RED → GREEN → JUDGE → REFACTOR. Strict assertion failure verification. | Full state machine | RED: `tests/` only. GREEN: `src/` or core modules only. |
| **`direct`** | Bypasses RED phase. Used for boilerplate, dependency config, or asset syncing. No test generation. | GREEN → JUDGE only | Scoped tightly to targeted files (e.g., `pyproject.toml`, config assets). |
| **`e2e`** | End-to-end integration validation. Orchestrates external runtime environments, databases, or client-server loops. Verified via exit codes. | GREEN → JUDGE only | Production lines frozen; no business logic modifications allowed. System-level behavioral evaluation only. |

#### E2E Execution Boundaries

E2E tests are elevated to explicit phases in the state machine, executed at two specific boundaries:
* **Issue Gate (Meso-to-Micro):** When an individual issue's micro-tasks are successfully greened, refactored, and judged, an E2E pass validates that the localized issue changes did not fracture the broader system flow.
* **Feature Branch Gate (Micro-to-Idle):** Before the feature branch merges back into `main`, the orchestrator sweeps the entire system's E2E suite to guarantee holistic compliance.
    * **The Train (Green → Judge → Green loop):** On `COMPLIANCE_VIOLATION` or test failure, the CLI safely resets without destroying task progress. The JUDGE phase honors `HandoverManifest.next_action` (see [specs/DeviaTDD-api.md](./DeviaTDD-api.md) for the routing table). The four routes:
        1. **`revert_before`** — discard this task's GREEN **and** its RED. `_resolve_pre_red_sha()` derives the SHA from `red_commit_sha^` (defended by a subject-match regex on the parent's commit message; logs `PRE_RED_AMBIGUOUS` when the parent isn't a RED-phase convention). `git reset --hard <pre_red>` + `git clean -fd`. `session.red_commit_sha` is cleared (the boundary was discarded) and `pending_judge_action = "revert_before"`. `force_transition_to("RED")` so the task retries from scratch.
        2. **`revert_to_red`** — discard GREEN, preserve RED. `_execute_rollback(root, reason)` (`src/deviate/cli/micro.py`) runs `git reset --hard <red_sha>` + `git checkout -- .deviate/` + `git clean -fd` (line 1262/1319), persisting a `RollbackSnapshot` (branch, current SHA, red SHA, reason) to the task ledger via `append_rollback_snapshot()`. The runner then unconditionally appends a feedback commit (`_commit_judge_feedback_and_advance`) and advances `session.red_commit_sha` to that commit so a second rollback only kills the subsequent GREEN. `force_transition_to("GREEN")` and re-runs GREEN with `<train_feedback>` injected. **Default on `COMPLIANCE_VIOLATION` when `next_action` is absent.**
        3. **`continue_refactor`** — JUDGE passed. No rollback. `pending_judge_action = "continue_refactor"`; `_finish_tdd_cycle` enters REFACTOR regardless of `--no-refactor`.
        4. **`skip_refactor`** — JUDGE passed, refactor not wanted. No rollback. `pending_judge_action = "skip_refactor"`; `_finish_tdd_cycle` marks the task `COMPLETED` and returns to `IDLE`.
        After up to `max_train_attempts = 3` rollbacks the loop raises `PhaseFailedError` and marks the task `FAILED`. The runner honors the manifest verbatim — no interactive prompt. The legacy single-commit fallback (`verdict == COMPLIANCE_VIOLATION` without `next_action`) maps to `revert_to_red`.
  If the session loses `train_feedback`, auto GREEN falls back to the exact task's persisted `**Judge Feedback**` bullets in `tasks.md`, wrapped as `<persisted_judge_feedback>`. When both sources exist, session feedback wins and the persisted history is not injected twice.
* **GREEN (The Execution):**
    * **Action:** The agent iterates on production code to pass the test.
    * **Timeout Guard:** The runner enforces a hard timeout (e.g., `--timeout=10`) to kill infinite loops.
    * **State Lock:** Upon a valid Green pass, `git add . && git commit -m "feat: [TASK-ID] Green phase complete"`.
    * **Layer discipline:** GREEN's only invariant is "make the RED test pass via the library/API surface declared in scope." It does NOT make scope, spec-drift, or HITL-routing judgments — those belong to JUDGE. When a RED test cannot be satisfied within GREEN's mechanical scope, GREEN emits `status: FAILURE` with a concrete `rationale:` naming the test path and why; `status: "ERROR"` is reserved strictly for tool/orchestration failure. The runner's `_is_hitl_escalation` is a narrow defensive fallback that ONLY promotes structured `contract_drift` / `escalates_to` / `hitl_options` dict keys to `HITL_PENDING` — loose-string `error_kind` discriminators and free-form scope-conflict text do NOT trigger HITL escalation.
* **JUDGE / TRAIN (The Compliance Gate) — with Green → Judge → Green loop:**
    * **The Judge:** The CLI evaluates `git diff HEAD~1 HEAD` (only the implementation) against `spec.md` for invariant/security violations. Uses `_detect_phase_changes()` and `_find_protected_modules()` from `spec.md` `Module:` declarations. This judge operates in a clean, zero-shared-history session to break recursive subjectivity. A `deviate-judge` skill (loaded from `_SKILL_NAMES["JUDGE"]`) guides the agent through supplementary compliance evaluation.
    * **The Train (Green → Judge → Green loop):** On `COMPLIANCE_VIOLATION` or test failure, the CLI safely resets without destroying task progress:
        1. Derive current task states from `tasks.jsonl` into memory. Resolve the RED-boundary SHA from `session.red_commit_sha`.
        2. Rollback via `git reset --hard <red_sha>` followed by `git clean -fd` (line 1246 / 1258 of `src/deviate/cli/micro.py`). The RED boundary is the precise commit SHA captured at the end of the RED phase; resetting to it discards the suspect GREEN implementation, and `git clean -fd` (without `-x`) removes untracked artifacts the failed GREEN may have left behind while preserving gitignored state such as `.deviate/`.
        3. Persist a `RollbackSnapshot` (branch, current SHA, red SHA, reason) to the task ledger via `append_rollback_snapshot()`.
        4. `force_transition_to("GREEN")` returns the session to GREEN, populating `session.train_feedback` with the previous failure output (extracted from the JUDGE manifest's `train_feedback` / `violations` / `rationale` / `summary` fields in that priority order).
        5. The `_run_tdd_cycle()` loop re-runs GREEN, appending `<train_feedback>` to the prompt. The cycle retries up to **`max_train_attempts = 3`** times before raising `PhaseFailedError` and marking the task `FAILED`. The JUDGE → GREEN → JUDGE → … iteration is the Green → Judge → Green loop.
  If the session loses `train_feedback`, auto GREEN falls back to the exact task's persisted `**Judge Feedback**` bullets in `tasks.md`, wrapped as `<persisted_judge_feedback>`. When both sources exist, session feedback wins and the persisted history is not injected twice.
* **REFACTOR (The Polish Gate):**
    * **Action:** If the Judge accepts the work, the workspace unlocks for an isolated run to polish readability.
    * **Regression Gate:** Post-refactor, the CLI re-runs the test suite. If the tests fail (agent broke code), the CLI safely discards the refactor (`git reset --hard`) and successfully completes the task using the verified Green commit.


### 3.1 Spec-Driven Development (SDD)
* **How it is fulfilled:** Executed directly via the Macro Layer and Meso Layer.
* **Mechanisms:** The workflow prohibits "vibe coding" or jumping straight into implementation. The framework enforces an artifact-centric approach where a feature must be systematically defined via research, design analysis, Product Requirement Documents (PRDs), and issue sharding. The Macro Layer separates context gathering (`/deviate-explore` — cheap) from architectural reasoning (`/deviate-research` — expensive), then synthesizes requirements (`/deviate-prd`) and decomposes issues (`/deviate-shard`) — shard now produces spec-enriched issue files with full Gherkin acceptance criteria, eliminating the need for a separate `/deviate-specify` step. The Meso Layer adds a per-issue `/deviate-plan` phase for localized research before task decomposition. The CLI commands `deviate tasks pre/post` lock down the execution blueprint (`tasks.md` / `tasks.jsonl`) before a single line of feature code can legally be written.

### 3.2 Test-Driven Development (TDD)
* **How it is fulfilled:** Executed via the Micro Layer: Automated Sandbox.
* **Mechanisms:** This layer implements a pure, unyielding RED-GREEN-REFACTOR loop. The Python CLI enforces that the agent first writes a unit or integration test. It then parses the test runner's JSON output (`pytest --json-report`) to programmatically verify that the test failed due to a missing implementation rather than a syntax crash. The code cannot move forward until a successful Green implementation is verified and locked using atomic Git commits at every step boundary.

### 3.3 Test-Driven Agentic Development (TDAD)
* **How it is fulfilled:** Executed via defensive safeguards embedded in the Micro Layer Sandbox.
* **Mechanisms:** Standard TDD assuming human developers falls short with LLM agents, which are prone to bypassing tests, creating infinite loops, or rewriting assertions to pass falsely. This architecture addresses TDAD directly through hard timeout limits and automated test file protection. It isolates agent behavior to keep the model strictly trapped within the bounds of deterministic software verification.

### 3.4 Acceptance Test-Driven Development (ATDD)
* **How it is fulfilled:** Achieved through bidirectional requirement traceability and the Meso/Micro Layer transition.
* **Mechanisms:** During the Meso phase, `deviate tasks pre/post` translates high-level customer requirements, user stories, and acceptance criteria into explicit target mapping tags inside `tasks.md` (descriptions, `blocked_by` DAG dependencies, `verifiable_sandbox_target`). In the Micro phase, the Judge Gate evaluates the collective task execution delta directly against the overarching functional constraints of `spec.md`. This guarantees that passing unit tests mathematically equal a passed business acceptance spec.

### 3.5 Evaluation-Driven Development (EDD)
* **How it is fulfilled:** Realized via the Compliance Gate and the **Green → Judge → Green loop**.
* **Mechanisms:** This architecture shifts validation from basic functional checks to prompt optimization and alignment validation. If the execution agent attempts to bend architectural constraints, the isolated Judge evaluates the `git diff` against code-level invariants. When `COMPLIANCE_VIOLATION` fires, the TRAIN protocol executes: `_execute_rollback()` runs `git reset --hard <red_sha>` against the precise RED-boundary SHA stored in `session.red_commit_sha` (set at the end of the RED phase), discarding the suspect GREEN implementation and any post-RED state, then `git clean -fd` (without `-x`) wipes untracked artifacts left behind by the failed GREEN attempt while preserving gitignored state such as `.deviate/`. The session is then `force_transition_to("GREEN")` and a `RollbackSnapshot` is appended to the task ledger. The previous failure output is injected as `<train_feedback>` into the next GREEN prompt. `_run_tdd_cycle()` allows up to **`max_train_attempts = 3`** retries (re-running GREEN with refreshed feedback) before raising `PhaseFailedError` and marking the task `FAILED`. The agent's context window is treated as an iteratively trained parameter optimized for perfect execution compliance.
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
          │                                              │   PLAN   │  ← per-issue phase
          │                                              └──────────┘
          │                                                    │
          │                                              plan post
          │                                                    ▼
          │   ┌────────────┐  tasks post                    ┌──────────┐
          │   │   TASKS    │ ──────────────────────────> │  (TASKS) │
          │   └────────────┘                               └──────────┘
          │         │
          │         │  pr pre/run
          │         ▼
          │   ┌──────────┐
          └── │ IDLE     │
              └──────────┘

NOTE: SPECIFY is deprecated as a standalone phase. The merged SHARD+SPECIFY
phase produces spec-enriched issue files directly during shard. PLAN is a
newly added per-issue phase (CLI registered as `deviate plan`, implemented in
`src/deviate/cli/meso.py:_plan_pre` / `_plan_post`). The `deviate meso run`
pipeline executes SPECIFY (claim + worktree) → PLAN → TASKS → IDLE in a
single invocation. The legacy SPECIFY → TASKS transition still exists for
backward compatibility but routes through the new merged path. The SPECIFY
step can be bypassed with `--no-setup` (skip worktree + ledger claim); the
banner then renders `PLAN ▶ TASKS` and the pipeline runs in the current
working directory on whatever branch is checked out, bypassing the Git
Isolation Principle.
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
  GREEN with `<train_feedback>` injected. Up to `max_train_attempts = 3`
  retries; exhaustion raises `PhaseFailedError`.
- TRAIN rollback uses `git reset --hard <red_sha>` followed by `git clean -fd`
  (precise RED-boundary SHA + untracked cleanup) — never `git revert`, because
  resetting to the verified-good RED boundary discards the suspect GREEN
  cleanly, and `git clean -fd` (without `-x`) removes untracked artifacts
  that the failed GREEN may have left behind while preserving gitignored
  state such as `.deviate/`.
```

---

## 5. Phase Prompts & System Context Injection Boundaries

Agents are bound into specialized operational scopes by context restrictions. Open-ended instructions are forbidden.

### 5.0 Product Layer Phase Prompts *(optional, sits above Macro)*

The Product layer captures cross-product framing (FLOW-01..FLOW-03). It is optional — repositories that only ship single features can skip it and route `/deviate-shard` and `/deviate-adhoc` directly to the Macro layer.

* **`/deviate-flows` (FLOW-01, `deviatdd-product-layer`):** Conversational flow authoring. Reads `specs/_product/flows/flows-product.md` as the seed catalog; converses with the user to identify actor, domain, job-to-be-done, trigger, and success state; writes a new `flows-<domain>.md` under `specs/_product/flows/`; appends a row to `specs/_product/flows/index.md` (Flow ID, Name, Actor, Domain, Status, Source).
    * *System Directives:* Extend the seed (never regenerate); preserve the FLOW-NN ID format `^FLOW-\d{2,}$`; every flow block must carry a `## FLOW-NN <Name>` header; the agent must ask clarifying questions when the actor, job, or trigger is ambiguous before writing the flow file. **Commit protocol (v1.4.0):** Phase A drafts every flow file + index row to disk as the conversation progresses (no commit). Phase B fires exactly one `stage_and_commit` after the user explicitly signs off ("commit", "looks good", "done", "ship it", "approve", "lgtm", "yes"), passing every session-authored flow file plus `index.md` in `files=`. The pre-commit `git diff --cached --name-only` audit must confirm the staged set is a subset of the session-owned files; any extras halt the commit. Silence is not sign-off. The skill MUST NOT call `commit_artifact(path, msg)` (one commit per call) or `git add -A`.
* **`/deviate-architecture` (FLOW-02, `deviatdd-product-layer`):** Cross-epic architecture authoring. **Precondition:** at least one flow file must already exist under `specs/_product/flows/` (FLOW-02 Preconditions Gate); if absent, the skill must surface `[red]FLOWS_MISSING[/]` and recommend `/deviate-flows` first.
    * *System Directives:* Produce or maintain `specs/_product/architecture.md` and the supporting `specs/_product/domain-model.md`; classify the requested change as Local (epic-bounded), Context-Bridging (spans two epics), or Context-Creating (defines a new product surface); route local changes to the Meso layer. **Commit protocol (v1.3.0):** Phase A drafts `specs/_product/architecture.md` and `specs/_product/domain-model.md` to disk as the conversation progresses and stages them via `deviate.core.commit.stage_files` so the user can `git diff --cached` while iterating — no commit fires mid-conversation. Phase B fires exactly one `stage_and_commit` after the user explicitly signs off ("commit", "looks good", "done", "ship it", "approve", "lgtm", "yes" — silence is not sign-off), passing every session-authored architecture and domain-model file in `files=`. The pre-commit `git diff --cached --name-only` audit must confirm the staged set is a subset of the session-owned files; any extras halt the commit and surface the discrepancy (no auto-unstage). The skill no longer calls `commit_artifact(path, msg)` — that helper emits one commit per path and would reproduce the v1.2.0 split-across-N-commits regression. `git add -A` and `git commit --only` are also forbidden. The classification banner (`Local` / `Context-Bridging` / `Context-Creating`) rides in the commit body. Never pass `no_verify=True`; if a pre-commit hook fails, surface stderr verbatim and stop — do not retry with `--no-verify`.
* **`/deviate-release` (FLOW-03, `deviatdd-product-layer`):** Release planning. **Precondition:** both `specs/_product/architecture.md` and at least one flow file under `specs/_product/flows/` must exist (FLOW-03 Preconditions Gate); if either is absent, surface `[red]ARCH_OR_FLOWS_MISSING[/]`.
    * *System Directives:* Accept a release-goal description from the user; compile the next coherent product release from the existing flows and architecture; write or override `specs/_product/release-next.md` (Included Flows table, Included Work table, Acceptance Criteria). Downstream `/deviate-explore` and other prompts treat `specs/_product/release-next.md` as the guiding compass when deciding what the next epic should be.
* **Downstream consumption:** `deviate-shard` and `deviate-adhoc` SKILL.md bodies read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, and `specs/_product/domain-model.md` as authoritative context. Each sharded issue emits a `flow_refs: [FLOW-XX, ...]` field in its YAML frontmatter (and in the `IssueRecord.flow_refs` ledger entry), so vertical slices stay traceable back to the flow that motivated them.

* **Active Domain Discipline:** Both `/deviate-flows` and `/deviate-architecture` discovery steps use a structured 7–8 bullet active discipline — one question at a time with a recommended answer, dependency-ordered, read-first, term-challenge against the glossary, sharpen fuzzy language, stress-test with scenarios, and update the artifact (`flows-<domain>.md` or `domain-model.md`) inline as terms resolve. Enforced as a mandatory pass before writing the flow file or architecture entry.

### 5.1 Meso Layer Phase Prompts
* **`/deviate-specify` (Deprecated):** Merged into `/deviate-shard`. Shard now produces spec-enriched issue files directly. The legacy skill remains for backward compatibility with a redirect notice.
* **[HITL Gate 2]:** Human reviews all sharded issue files (with embedded spec content) for completeness, edge cases, scope correctness. Moved from after `/deviate-specify` to after `/deviate-shard`.
* **`/deviate-plan` Context (via `deviate plan pre`):** Spec-enriched issue file + Current Codebase State + workstation file structures extracted via `deviate/core/treesitter.py` from the `## System Topology Mapping` section of the issue.
    * *System Directives:* Perform fresh localized research for this specific issue. Read the spec-enriched issue, scan current codebase state (what exists now, not at epic-explore time), analyze what prior issues implemented via the `specs/issues.jsonl` ledger. Identify integration points, dependencies, potential conflicts. Produce `plan.md` with implementation strategy, file mappings, and risk assessment. Contextualize the issue for downstream task decomposition. The plan pre contract includes an optional `file_structure` appendix keyed by workstation path, pre-extracted symbols/imports per file.
* **`/deviate-tasks` Context (via `deviate tasks pre`):** Spec-enriched issue file + `plan.md` (if available) + Codebase Layout Map + constitution command output.
    * *System Directives:* Decompose the spec-enriched issue directly into discrete task entries written to `tasks.md` (the human-authored decomposition document). The CLI subsequently registers these as rows in `tasks.jsonl` (the append-only event ledger). Each task must include implementation hints (file locations, mock boundaries, fixture requirements) alongside the decomposition. Every entry must be assigned a unique tracking identifier (`TSK-{ISSUE_ID}-{NN}`) and must map cleanly to an acceptance criterion in the issue file. Encode DAG dependencies via `blocked_by` arrays in each task entry. Assign each task an execution type: `tdd` (standard TDD loop), `direct` (boilerplate/config, no RED phase), or `e2e` (end-to-end integration). **An agent MAY append a terminal `type: "e2e"` task** for issues modifying user-facing behavior, but it is no longer mandatory. Target 4-8 tasks per issue; enforce 1-10 bounds. When `plan.md` is available, consume its implementation strategy and risk assessment as input to task granularity decisions.

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
[Product /flows]     ──> ( FLOW GATE: actor / job-to-be-done approval ) ──> [/architecture]
[Product /architecture] (GATE P2: cross-epic contract sign-off — only when Product layer in use) ──> [/release]
                                  │
                                  ▼
[Macro /research]   ──> ( GATE 1: Design Approval ) ──> [PRD ──> Shard+Specify]
                                  │
                                  ▼
[Meso /shard]       ──>  ( GATE 2: Contract Sign-Off )  ──> [/plan → /tasks]
                                  │
                                  ▼
[Meso /tasks]       ──>  ( GATE 2b: Task Review — opt-in for complex features )
                                  │
                                  ▼
[Micro Success]     ──>  ( GATE 3: Final Merge Audit )   ──> [Production Deployment]

NOTE: The Product-layer gates (FLOW-01 actor sign-off, FLOW-02 cross-epic contract
sign-off) are **soft gates** — they are conversational checkpoints inside
`/deviate-flows` and `/deviate-architecture` and do not block Macro-layer
phases. They are listed above to show the full dependency chain; the
framework's three non-bypassable HITL gates remain Gate 1, Gate 2, and Gate 3.
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

| Testing Framework | CLI Invocation Strategy | Success Validation | Error Parse Pattern | Scope Protection |
| :--- | :--- | :--- | :--- | :--- |
| **Python / pytest** | `python -m pytest tests/ -v` | `returncode == 0` | `_classify_pytest_outcome()`: checks `SYNTAX_ERROR` markers (SyntaxError, IndentationError, etc.), `ASSERTION_FAILURE`, `PASS`, `UNKNOWN_FAILURE`. | Reverts unauthorized test edits before running suite. |
| **Node.js / Jest** | (Not implemented) | — | — | — |
| **Go / testing** | (Not implemented) | — | — | — |

---

## 8. Core Architectural Invariants & Guardrails

The orchestrator must maintain and enforce these structural constraints across all operations:

1. **The Git Isolation Principle:** Every isolated task loop must be executed on a clean git branch or worktree environment. Commits are made automatically at each phase boundary via `_commit_phase()` in `micro.py` (`test: [{scope}]: RED phase`, `feat: [{scope}]: GREEN phase`, `refactor({scope}): REFACTOR phase`). Worktrees are created via `deviate specify pre` using `create_worktree()` and removed via `remove_worktree()`.

2. **The Scope Audit Law:** When entering or running the `GREEN` execution phase, the system checks for unauthorized changes to test, spec, and config directories. Protected files are reverted via `git restore <filepath>`. The JUDGE phase (`deviate judge pre`) additionally performs compliance verification by detecting changes to protected modules declared in `spec.md` `Module:` lines. Complements the GREEN stub-PASS guard in `_run_green_phase` (see `DeviaTDD-api.md` § GREEN Stub-PASS Guard): scope rejects writes the agent shouldn't have made; the stub-PASS guard rejects passes the agent shouldn't have emitted.

3. **Append-Only Ledger Protocol (issues.jsonl + tasks.jsonl):** All state transitions are append-only. The global `specs/issues.jsonl` serves as the authoritative issue registry. Issue-scoped micro-task ledgers live at `specs/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`. Agents cannot edit any status fields directly — only the CLI may append events via `append_issue_transition()` and `append_task_transition()`. No existing line is ever modified or overwritten. Canonical state is derived by parsing each ledger using compound-key idempotency (bottom-up for `issues.jsonl`; `(id, status)` compound key for `tasks.jsonl`). Ad-hoc issues bypass macro planning and route directly to isolated execution workspaces.

4. **Deterministic Test Failure Check:** For a `RED` phase to be valid (`deviate red post`), `_classify_pytest_outcome()` must return `ASSERTION_FAILURE`. Return codes of `PASS` or `SYNTAX_ERROR` (SyntaxError, IndentationError, TabError, ImportError, ModuleNotFoundError) are rejected. Current implementation uses string-based parsing of `pytest -v` output; `pytest --json-report` migration is specified but not yet implemented.

5. **Memory Preservation via Train Gates (Green → Judge → Green loop) with 4-way routing:** The JUDGE phase implements Train rollback on compliance violations. The rollback is gated by `HandoverManifest.next_action` (see [specs/DeviaTDD-api.md](./DeviaTDD-api.md) for the routing table): `revert_to_red` (default on violation) preserves RED and advances `session.red_commit_sha` past a feedback commit so a second rejection only kills the subsequent GREEN. `revert_before` extends the rollback to past RED (`red_commit_sha^`, defended by a subject-match regex; logs `PRE_RED_AMBIGUOUS` when the parent isn't a RED-phase convention), clears the boundary, and reissues the task from RED via `force_transition_to("RED")`. The pass routes (`continue_refactor`, `skip_refactor`) skip the rollback and route control to `_finish_tdd_cycle` via `session.pending_judge_action` (consumed there), overriding the `--no-refactor` CLI flag. `_execute_rollback()` runs `git reset --hard <red_sha>` followed by `git clean -fd` (without `-x`) to remove untracked artifacts the failed GREEN attempt may have left behind; this discards the suspect GREEN implementation and clears any untracked residue so the next attempt starts from a verified-good test. `_execute_rollback()` persists a `RollbackSnapshot` (branch, current SHA, red SHA, reason) to the task ledger via `append_rollback_snapshot()`. The session is `force_transition_to("GREEN")` and the next GREEN attempt re-runs with `<train_feedback>` injected. Up to `max_train_attempts = 3` rollbacks before the loop raises `PhaseFailedError` and marks the task `FAILED`.

6. **The Elastic Governance Rule:** The `deviate micro run` command (and the
   top-level `deviate run` orchestrator, which forwards the flag) supports
   `--profile [full|fast|secure]` to control which phases execute. `full` runs
   the complete RED → GREEN → JUDGE → REFACTOR cycle. `fast` runs RED + GREEN
   only (skip JUDGE + REFACTOR). `secure` runs RED + GREEN + JUDGE (skip
   REFACTOR). Boolean `--no-judge`/`--no-refactor` flags are retained as
   composable overrides that take precedence over profile defaults. Execution
   profiles and agent backends are configured via `DeviateConfig.agent.backend`.

7. **Atomic Concurrency Protocol (Git Reference Locks):** To eliminate TOCTOU race conditions across distributed terminal instances, the issue claim workflow (formerly `deviate specify pre`, now part of the Plan phase orchestration) uses try-claim semantics: `select_unblocked_candidates()` returns all available BACKLOG issues, and the worker iterates through them attempting `claim_issue()` combined with `create_worktree()` and `git push -u <remote> <branch>`. The server serializes concurrent pushes; the first successful push wins. The `tasks.jsonl` ledger records the authoritative outcome.

8. **The Session Continuity Principle:** Session state is persisted to `.deviate/session.json` after each CLI command. The `SessionState` class tracks `current_phase`, `active_issue_id`, and `last_command`. Macro and meso phases transition through `transition_to()` with validation from `_MACRO_TRANSITION_MAP`. Micro phases use `force_transition_to()`. The `_run_single()` function checks `session.current_phase` and supports resume from JUDGE/REFACTOR via optional `start_phase` parameter. Model continuity and KV cache management are delegated to the calling environment.

9. **The Model Tiering Constraint:** Model selection is defined as a recommended strategy in `specs/constitution.md` seeds and prompt skills. The `deviate` CLI does **not** enforce model selection programmatically. The `--agent` flag and `DeviateConfig.agent.backend` field configure agent backends (`opencode`, `claude`, `droid`), but the specific model used within each backend is chosen by the calling environment. The `_SKILL_NAMES` dict in `micro.py` maps `JUDGE → "deviate-judge"` for skill-based agent guidance.

10. **The Issue-Scoped Task Sweep:** `deviate micro run --all` is **issue-scoped**, not
    global. The active issue is resolved from `session.active_issue_id`, falling
    back to a branch-derived lookup via the `feat/{epic}/{issue}` regex against
    `specs/issues.jsonl`. If neither resolves, no tasks are dispatched. Once the issue is
    resolved, only the PENDING tasks for that issue (`_find_all_pending_tasks(root,
    issue_id=...)`) are swept. Tasks are dispatched sequentially; each task gets up to
    **2 retry attempts** (`_execute_task_with_retry`, `for attempt in range(2)`) before
    being marked `FAILED`. The pipeline **halts on the first failure** (`any_failed = True;
    break`) and exits with code `1`. When `.deviate/config.toml` contains `graphite = true`,
    the runner invokes `gt create -m "feat({TSK}): {description}"` between tasks to spin
    up a stacked branch for the next pending task.

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
~85% of all recommended LLM turns use V4 Flash at cache-hit rates.

### 9.2 Continuous-Thread Caching

`/deviate-plan` and `/deviate-tasks` share a single continuous session per issue (replacing the deprecated `/deviate-specify` + `/deviate-tasks` pairing). The system prompt, tool definitions, issue content, and `constitution.md` are written to the KV cache once (first turn, cache-miss pricing) and read at 98%+ discount on every subsequent turn. Without this, each turn would re-send the full context at full price.

Micro-layer tasks dispatched via `deviate micro run <task-id>` reuse the same
in-process state through `SessionState.force_transition_to()`. Each phase is a
synchronous function call within the same process — there is no subprocess or LLM
session restart between phases. The `_commit_phase()` function handles automatic
git commits between phase transitions.
All commit messages are routed through `format_commit_message()` from `src/deviate/core/convention.py`,
which detects the project's emoji convention (via CONTRIBUTING.md or git history) and prepends
the appropriate gitmoji when applicable (e.g. `✨ feat(TSK-001-01): add implementation`).
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

Each HITL gate prevents wasted downstream compute. A design error caught at Gate 1 saves all `/deviate-prd`, `/deviate-shard`, `/deviate-plan`, `/deviate-tasks`, and Micro cycles. A spec error caught at Gate 2 saves all per-issue planning, task decomposition, and Micro cycles. Each gate is a cheap human check that prevents expensive LLM work.

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
   `time.monotonic()` between chunks and raises
   `AgentTimeoutError(STALL_DETECTED)` once no output has arrived for
   `STREAM_STALL_TIMEOUT_SECONDS = 60` (≤ 120 by spec). Periodic
   stdout keeps the watchdog warm, so healthy agents are unaffected.
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

| :--- | :--- | :--- | :--- | :--- |
| `opencode` | `opencode run` | Commands copied into `.opencode/commands/` (flat `.md`) | `--model <id>` flag | Default backend |
| `claude` | `claude -p --permission-mode auto` | Commands copied into `.claude/commands/` (flat `.md`) | `--model <id>` flag (may be ignored by host env) | Print mode, auto permission |
| `droid` | `droid exec` | Commands copied into `.factory/commands/` (flat `.md`) | `--model <id>` flag | Factory Droid IDE-owned commands dir |
| `pi` | `pi -p` | Commands file-copied into `<workdir>/.pi/prompts/<name>.md` (project-local; flat top-level only per Pi's documented slash-command convention) | `--model <id>` flag (accepts `provider/model` shorthand) | Native slash-command discovery via `.pi/prompts/`; opt-in RPC mode available |

Pi implements slash-command discovery natively — `pi -p` loads commands from
`~/.pi/agent/`, `.pi/prompts/`, and `.agents/` on startup, parses the
`name:` + `description:` YAML frontmatter from each `<name>.md` flat file,
and registers them as slash commands. DeviaTDD integrates Pi on top of the
standard `AgentBackend.invoke()` contract with three customisations:

1. **Command file-copy strategy (project-local, flat).** `deviate setup`
   file-copies each project command to `<workdir>/.pi/prompts/<name>.md`
   via the existing `install_command` pipeline — the same code path used
   for `.claude/commands/`, `.opencode/commands/`, and `.factory/commands/`.
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

### 10.2.5 Project-Local `deviatdd` Skill (Single Skill, Write-Everywhere)

In addition to the 25 `deviate-*` slash commands under
`<workdir>/.<agent>/commands/` and `<workdir>/.pi/prompts/`, `deviate setup`
provisions exactly **one** project-local skill named `deviatdd` at
`<workdir>/.<agent>/skills/deviatdd/SKILL.md` for every agent platform
in `active_agents` (`claude`, `opencode`, `factory`, `pi`, `omp`).
This mirrors `_install_commands_to_agents`'s write-everywhere policy:
the skill body is identical across platforms, only the destination
directory differs, and the write is unconditional — every operator
using `--agent <platform>` gets the skill at the canonical skills
directory for their platform.

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

**Source of truth:** `src/deviate/prompts/skills/deviatdd/SKILL.md`
(package resource, loaded via `importlib.resources`).

**Installer:** `_install_deviatdd_skill(workdir, agents)` in
`src/deviate/cli/__init__.py`, called from `setup()` after
`_install_commands_to_agents`. Idempotent (content-equality skip
mirrors `install_command`'s contract). The skill has no siblings —
there is no `discover_skills()` abstraction.

**Scope:** Micro-layer only. The skill orchestrates `deviate micro run
--all`, triages every error class micro can surface, and runs a
four-step safety-gated `git reset --hard && git clean -fd` clean-slate
retry (ledger sanity → workspace inventory → typed user confirmation →
reset, matching `_execute_rollback`'s `git clean -fd` contract so
`.deviate/`, `.mise/`, `.venv/` survive). Meso orchestration is out of
scope — operators use `/deviate-meso`, `/deviate-plan`, `/deviate-tasks`
for that. A Dispatch section in SKILL.md points the agent to those
canonical slash commands when a failure escapes micro's scope; the
skill never invokes them inline. **v1.1.0 added a
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
`INVOKE_AGENT` (names `backend=` and `model=`), `AGENT_RESULT`
(carries `status=`, `verdict=`, full `manifest=`; the manifest
contains `files=`, not the event itself), `AGENT_RAW_OUTPUT`
(full stdout in a single `raw_output=` field; stderr is NOT
captured), `AGENT_TIMEOUT` (carries `error=` and `partial_stderr=`),
`AGENT_ERROR`, `AGENT_NOT_AVAILABLE`, `JUDGE_REJECTED`,
`JUDGE_AGENT_NO_FEEDBACK`, `JUDGE_REFACTOR_NOTE` (carries `note=`,
the refactor hint), `TASKS_MD_NO_MATCH`, `TASKS_MD_FEEDBACK`,
`TASKS_MD_SKIP`, `FEEDBACK_COMMIT_FAILED`, `POST_CMD_FAILURE`
(carries `uncommitted_count=` and `files=`, the dirty files the
hook refused — NOT `returncode=` / `stderr=`). Skill frontmatter
version is `1.1.0`; the `description` field was updated to include
"troubleshoot from logs". The drift-check test
`test_deviatdd_skill_troubleshooting_section_matches_logger` parses
`micro.py` for `_log_run("<NAME>", ...)` calls and asserts every
backticked event name in the Troubleshooting section is a real
emitted event — guards against invented event names. Per-event
field schemas live in `micro.py` itself, not duplicated here.

**`.gitignore` exclusions:** `_ensure_root_gitignore` adds
`*/skills/deviatdd/` to the entries tuple alongside
`*/commands/deviate-*.md` and `*/prompts/deviate-*.md`. The
single-level wildcard covers all five agent platforms (`.claude/`,
`.opencode/`, `.factory/`, `.pi/`, `.omp/`) with one pattern. The
single-level prefix (`*/`, not `**/`) is critical: it scopes the
pattern to the project root, never matching the deviatdd project's
own source at `src/deviate/prompts/skills/deviatdd/` (three
directories deep).

**Tests:** `TestInstallDeviatddSkill` (8 tests) in
`tests/test_cli/test_init.py` covers install-to-all-five-agents,
idempotence, gitignore entry presence + idempotence, the safety-gate
fragments in the SKILL.md body, well-formed frontmatter, and the
dispatch table's canonical slash-command references.


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
