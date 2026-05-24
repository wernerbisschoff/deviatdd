# DeviaTDD: Dual Engine Verification Infrastructure for Agentic Test-Driven Development
## Core Architecture, Lifecycle, and Engineering Specification

---

## 1. Architectural Overview & Philosophy
The architecture operates as a hierarchical lifecycle that shifts from human-driven macroscopic scoping to machine-orchestrated, deterministic microscopic execution loops. It is founded on the principle that Large Language Models (LLMs) are probabilistic, optimization-seeking actors that require structured infrastructure containment rather than implicit alignment trust.

```plaintext
                          ┌──────────────┐
                          │   /adhoc     │  (complexity gate: low/medium only)
                          │ Condensed    │
                          │ E+P+S → Issue│
                          └──────┬───────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ specs/adhoc/ │ → single issue, prd.md, issues.jsonl
                          └──────────────┘

[ MACRO LAYER: Scoping ]  ──> Explore ──> Research ──> PRD ──> Shard
                                                                 │
                                                                 ▼
[ MESO LAYER: Contracts ] ──> Specify ──> [HITL] ──> Tasks
                                                       │
                                                       ▼
[ MICRO LAYER: TDD Loop ] ──> Red ──> Green ──> Judge/Train ──> Refactor
                                │  ▲
                                ▼  │
                     [ YELLOW: Amend Gate ]
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
* **Adhoc (Fast-Path):** A condensed single-command shortcut (`/adhoc`) that compresses Explore + Research + PRD + Shard into one operation for low-to-medium complexity tasks. Performs proportional exploration (lightweight file scanning, dependency mapping), synthesizes a condensed PRD entry, and emits a single vertical-slice issue directly into `specs/adhoc/`. Appends to the aggregated `specs/adhoc/prd.md` and registers the issue in the global `specs/issues.jsonl` append-only ledger with an `ADH-{NNN}` identifier. A **Complexity Gate** evaluates the task description before proceeding: high-complexity tasks (multi-module coordination, state management, new architecture) are rejected with a directive to run `/explore` to initiate a full epic workflow instead. This gate prevents scope-creep and ensures adhoc remains a true fast-path, not a bypass for complex engineering.

### 2.2 The Meso Layer: Issue Engineering
Creates formal contracts for an issue via CLI slash commands.
* **Specify (`/spec:core:specify`):** Generates a structured functional contract (`spec.md`).
* **[HITL GATE]:** Human reviews the functional contract before task decomposition proceeds. Catches spec errors early when they're cheap to fix.
* **Tasks (`/spec:core:tasks`):** Merges the former `/plan` role. Decomposes the specification into a trackable execution blueprint with implementation hints, stored in `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`. Each task entry is assigned a unique `TSK-{ISSUE_ID}-{NN}` identifier, typed as `tdd`, `direct`, or `e2e`, and includes file locations, mock boundaries, and fixture requirements. Automatically appends a terminal `type: "e2e"` task at the bottom of every issue's task ledger.
  * **Granularity:** Target ~5 tasks per issue. Each task must be a complete functional unit implementable in a single TDD cycle (15-60 min). Avoid "create one file" granularity — group related functions into a cohesive unit. Enforce bounds: minimum 3 tasks per issue, maximum 10 tasks per issue.
* **Context (`/spec:core:context`):** Synchronizes dependencies and historical constitution constraints.
* **Session Continuity (KV Cache Optimization):** `/specify` and `/tasks` execute in a single continuous LLM session — not as separate invocations. The system prompt, tool definitions, and `spec.md` content form a stable prefix that achieves 90%+ KV cache hit rates after the first turn. DeepSeek V4 Flash bills cache-hit input at $0.0028/M tokens versus $0.14/M for cache-miss input (98% discount). V4 Pro applies a similar ratio ($0.003625/M hit vs $0.435/M miss). Architectural rationale: task decomposition is cheap to regenerate (~30s); the cost of a cache miss from restarting the session dwarfs the cost of keeping it alive. This is the primary cost lever in the Meso layer.

### 2.3 The Micro Layer: The Automated Sandbox (Python CLI)
The executor agent targets a task by looking up its current state in `tasks.jsonl`. The state ledger is pure — only event type, worker, and timestamp are stored. The agent is trapped inside a strict state machine governed by Git, deterministic parsing, and defensive operational safeguards. **Task execution type determines the applicable phase gates and file-write boundaries.**

### Execution Engine

The Micro layer execution engine uses **Aider's Python API** (`aider.coders.Coder`) rather than raw `claude -p` or `droid exec` subprocess calls. Three architectural advantages drive this decision:

1. **SEARCH/REPLACE diff format**: TDD edits are typically 5–20 lines. Aider sends only the changed lines as SEARCH/REPLACE blocks, not full file rewrites. This yields ~10x token savings on output per turn compared to whole-file formats used by other engines.

2. **Architect/Editor two-model routing**: Aider's `--architect` mode maps directly to DeviaTDD's model tiering. Complex RED phases can route V4 Pro as Architect (reasoning) and V4 Flash as Editor (code generation). Standard GREEN/REFACTOR phases use V4 Flash for both roles.

3. **Single-session KV cache preservation**: A single `Coder` object is reused across RED → GREEN → REFACTOR turns within a task. The system prompt, repo map, and read-only test files form a stable prefix that hits the KV cache on every turn after the first. Test files that do not change during a cycle are loaded as read-only context rather than appended as conversation turns (which would break the cache prefix).

The JUDGE and YELLOW phases run in isolated, zero-shared-history sessions (different model and/or fresh context) to break recursive subjectivity — this is a deliberate cache sacrifice for compliance integrity.

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
* **YELLOW (The Amendment Protocol - Conditional):**
    * **Action:** If the agent realizes during Green that the Red test is architecturally flawed, it cannot secretly alter it. It must output a `<propose_test_amendment>` block.
    * **Process:** The CLI pauses the Green phase and sends the original test, proposed test, and `spec.md` to an isolated Yellow Judge.
    * **If Approved:** The CLI overwrites the test, locks the new state (`git commit -m "test(amend): ..."`), and resumes Green.
    * **If Rejected:** The CLI rejects the proposal, updates `<judge_feedback>`, and forces the agent back to Green under original constraints.
* **JUDGE / TRAIN (The Compliance Gate):**
    * **The Judge:** The CLI evaluates `git diff HEAD~1 HEAD` (only the implementation) against `spec.md` for invariant/security violations. This judge operates in a clean, zero-shared-history session to break recursive subjectivity.
    * **The Train (Ephemeral Rollback):** If rejected, the CLI safely resets without destroying task progress:
        1. Derive current task states from `tasks.jsonl` into memory.
        2. Rollback via `git reset --hard HEAD~1` (wipes bad implementation, preserves Red test).
        3. Synthesize a destructive update (replace old failure with new context) to the `<judge_feedback>` tag in memory.
        4. Append new state events to `tasks.jsonl` as needed; route the agent back to Green.
* **REFACTOR (The Polish Gate):**
    * **Action:** If the Judge accepts the work, the workspace unlocks for an isolated run to polish readability.
    * **Regression Gate:** Post-refactor, the CLI re-runs the test suite. If the tests fail (agent broke code), the CLI safely discards the refactor (`git reset --hard`) and successfully completes the task using the verified Green commit.

---

## 3. Mapping of Architectural Fulfillment

This closed-loop lifecycle converts high-level human intent into strict machine-level invariants. The framework satisfies core development methodologies as follows:

### 3.1 Spec-Driven Development (SDD)
* **How it is fulfilled:** Executed directly via the Macro Layer and Meso Layer.
* **Mechanisms:** The workflow prohibits "vibe coding" or jumping straight into implementation. The framework enforces an artifact-centric approach where a feature must be systematically defined via research, design analysis, Product Requirement Documents (PRDs), and issue sharding. The Macro Layer separates context gathering (`/explore` — cheap) from architectural reasoning (`/research` — expensive), then synthesizes requirements (`/prd`) and decomposes issues (`/shard`). Slash commands like `/spec:core:specify` and `/spec:core:tasks` lock down the functional intent (`spec.md`) and execution blueprint (`tasks.jsonl`) before a single line of feature code can legally be written.

### 3.2 Test-Driven Development (TDD)
* **How it is fulfilled:** Executed via the Micro Layer: Automated Sandbox.
* **Mechanisms:** This layer implements a pure, unyielding RED-GREEN-REFACTOR loop. The Python CLI enforces that the agent first writes a unit or integration test. It then parses the test runner's JSON output (`pytest --json-report`) to programmatically verify that the test failed due to a missing implementation rather than a syntax crash. The code cannot move forward until a successful Green implementation is verified and locked using atomic Git commits at every step boundary.

### 3.3 Test-Driven Agentic Development (TDAD)
* **How it is fulfilled:** Executed via defensive safeguards embedded in the Micro Layer Sandbox.
* **Mechanisms:** Standard TDD assuming human developers falls short with LLM agents, which are prone to bypassing tests, creating infinite loops, or rewriting assertions to pass falsely. This architecture addresses TDAD directly by adding a Tamper Guard (automatically running `git checkout HEAD -- <test_target_file>` to revert unauthorized test edits) and hard timeout limits. It isolates agent behavior to keep the model strictly trapped within the bounds of deterministic software verification.

### 3.4 Acceptance Test-Driven Development (ATDD)
* **How it is fulfilled:** Achieved through bidirectional requirement traceability and the Meso/Micro Layer transition.
* **Mechanisms:** During the Meso phase, `/spec:core:tasks` translates high-level customer requirements, user stories, and acceptance criteria into explicit target mapping tags inside `tasks.md` (descriptions, `blocked_by` DAG dependencies, `verifiable_sandbox_target`). In the Micro phase, the Judge Gate evaluates the collective task execution delta directly against the overarching functional constraints of `spec.md`. This guarantees that passing unit tests mathematically equal a passed business acceptance spec.

### 3.5 Evaluation-Driven Development (EDD)
* **How it is fulfilled:** Realized via the Yellow Amend Gate and the Judge/Train Compliance Gate.
* **Mechanisms:** This architecture shifts validation from basic functional checks to prompt optimization and alignment validation. If the execution agent attempts to bend architectural constraints, the isolated Judge evaluates the `git diff` against code-level invariants. When a violation occurs, the Train Gate initiates an ephemeral rollback (`git reset --hard HEAD~1`), writes diagnostic adjustments to the `<judge_feedback>` tag, and feeds that fresh context back into the agent's prompt context. This treats the agent's context window as an iteratively trained parameter optimized for perfect execution compliance.

---

## 4. Core State Machine Engine

The execution state transitions must follow a strict non-bypassable sequence. Backward paths are structurally impossible unless triggered by the programmatic Yellow Amendment or Train Rollback protocols.

```
   ┌─────────┐      /spec:core:specify     ┌───────────┐
   │  IDLE   │ ──────────────────────────> │ SPECIFIED │
   └─────────┘                             └───────────┘
        ▲                                        │
        │                                  [HITL GATE]
        │                                        │
        │                                        │ /spec:core:tasks
        │                                        ▼
        │   ┌──────────────┐
        └── │ TASKS_READY  │
            └──────────────┘
                   │
                   │ rgr run [TASK_ID]
                   ▼
            ┌──────────────┐
            │  PHASE_RED   │ ──(Test Failure Verified)──┐
            └──────────────┘                            │
                   ▲                                    │
                   │ (Invalid Red/Syntax Error)         ▼
                   └───────────────────────────── ┌───────────┐
                                                  │ PHASE_GREEN│ <──────────┐
                                                  └───────────┘            │
                                                        │                  │
                                           Proposed     │    Judge         │ Train
                                           Amendment    │  Violation       │ Rollback
                                                        ▼                  │
                                                  ┌───────────┐            │
                                                  │ PHASE_AMEND│           │
                                                  └───────────┘ ───────────┘
                                                        │
                                           Approved     │
                                           Amendment    ▼
                                                  ┌───────────┐
                                                  │PHASE_JUDGE│
                                                  └───────────┘
                                                        │
                                                Passed  │
                                                Judge   ▼
                                                  ┌───────────┐
                                                  │ PHASE_REFA│
                                                  └───────────┘
                                                        │
                                                        │ Regression check
                                                        ▼
                                                  ┌───────────┐
                                                  │ TASK_DONE │
                                                  └───────────┘
```

---

## 5. Phase Prompts & System Context Injection Boundaries

Agents are bound into specialized operational scopes by context restrictions. Open-ended instructions are forbidden.

### 5.1 Meso Layer Phase Prompts
* **`/spec:core:specify` Context:** Issue Data + Raw Architectural Guidelines.
    * *System Directives:* Analyze raw input requirements. Synthesize the deterministic functional specification (`spec.md`). Express logic entirely in business behavior boundaries, edge states, and data models. Exclude engineering syntax or syntax paradigms.
* **[HITL GATE]:** Human reviews `spec.md` for completeness, edge cases, scope correctness. Catches spec errors before task decomposition proceeds. Task decomposition is cheap to regenerate; spec errors cascade.
* **`/spec:core:tasks` Context:** `spec.md` + Codebase Layout Map + `deviate test-config` output.
    * *System Directives:* Decompose `spec.md` directly into discrete task entries within `tasks.jsonl` (issue-scoped at `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`). This command merges the former `/plan` role — each task must include implementation hints (file locations, mock boundaries, fixture requirements) alongside the decomposition. Every entry must be assigned a unique tracking identifier (`TSK-{ISSUE_ID}-{NN}`) and must map cleanly to an acceptance criterion in `spec.md`. Encode DAG dependencies via `blocked_by` arrays in each task entry. Assign each task an execution type: `tdd` (standard TDD loop), `direct` (boilerplate/config, no RED phase), or `e2e` (end-to-end integration). **Automatically append a terminal `type: "e2e"` task at the bottom of the ledger** to validate the issue's holistic system flow. Target ~5 tasks per issue; enforce 3-10 bounds.

### 5.2 Micro Layer Sandbox Prompts

### Model Routing & Cache Discipline

| Phase | Model | Session | Cache Strategy |
|---|---|---|---|
| RED | V4 Flash (default) or V4 Pro (complex tasks) | Task session | Stable prefix: system prompt + repo map + read-only test files |
| GREEN | V4 Flash | Same task session | Cache hit on prefix from RED turn |
| YELLOW | V4 Pro | Isolated session | No cache sharing — compliance requires fresh context |
| JUDGE | V4 Pro | Isolated session | No cache sharing — breaks recursive subjectivity |
| REFACTOR | V4 Flash | Same task session | Cache hit on prefix from GREEN turn |

**Cache-breaking actions prohibited during Micro loops:**
- Switching the model identifier mid-cycle (each model has its own KV cache)
- Adding or removing tool definitions
- Modifying the system prompt
- Appending read-only test files as conversation turns instead of prefix-stable context

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
[Macro /research] ──> ( GATE 1: Design Approval ) ──> [PRD ──> Shard]
                                  │
                                  ▼
[Meso /specify]  ──>  ( GATE 2: Contract Sign-Off )  ──> [/tasks Decomposition]
                                  │
                                  ▼
[Meso /tasks]    ──>  ( GATE 2b: Task Review — opt-in for complex features )
                                  │
                                  ▼
[Micro Success] ──>  ( GATE 3: Final Merge Audit )   ──> [Production Deployment]
```

* **Gate 1: Blueprint Approval (After `/research`, Before `/prd`)**
    * *Trigger:* Triggered when `design.md` and `data-model.md` are generated by the Research phase.
    * *Action:* Human reviews core architectural selections, design decisions, data models, and tech stacks. PRD and Shard execution remain locked until an approval flag is written.
* **Gate 2: Contract Sign-Off (After `/specify`, Before `/tasks`) — PRIMARY GATE**
    * *Trigger:* Triggered when `spec.md` is generated for all issues in the feature.
    * *Rationale:* Spec errors are the most expensive to fix downstream. Task decomposition is cheap to regenerate (~30s). Catch functional contract errors here before they cascade into 25+ task implementations.
    * *Question Budget Rule:* The agent can prompt the user with targeted clarity questions (max 4 per interaction) to resolve functional ambiguity before locking.
    * *Action:* Human reviews each issue's `spec.md` for completeness, edge cases, scope correctness, and architectural alignment. Approval is required before `/tasks` will execute.
* **Gate 2b: Task Review (After `/tasks` — Opt-in)**
    * *Trigger:* Only for complex features (>7 issues or highly interdependent tasks).
    * *Action:* Human reviews task granularity, DAG dependencies, and implementation hints. Skipped for standard features.
* **Gate 3: Final Merge Audit (Micro-to-Idle Boundary)**
    * *Trigger:* Triggered when all task entries in all issue-scoped `tasks.jsonl` ledgers have reached terminal states (`COMPLETED` or `FAILED`) and all DAG dependencies are satisfied.
    * *Action:* Human evaluates the full atomic Git commit history, total testing metrics, and approves merging the feature branch into main.

---

## 7. Multi-Framework Testing Abstraction

DeviaTDD standardizes framework outputs into its state engine using a unified driver specification.

| Testing Framework | CLI Invocation Strategy | Success Validation | Error Parse Pattern | Tamper Guard Reset Path |
| :--- | :--- | :--- | :--- | :--- |
| **Python / pytest** | `pytest --json-report` | `exit_code == 0` | Inspect JSON for `outcome == "failed"` matching an explicit `AssertionError` / `NotImplementedError`. | `git checkout HEAD -- tests/` |
| **Node.js / Jest** | `jest --json` | `success == true` | Inspect JSON for failed assertions; ensure zero runtime or module import failures. | `git checkout HEAD -- __tests__/` |
| **Go / testing** | `go test -json` | `Action == "pass"` | Parse output stream lines for `Action == "fail"` with explicit testing log assertions. | `git checkout HEAD -- *_test.go` |

---

## 8. Core Architectural Invariants & Guardrails

The orchestrator must maintain and enforce these structural constraints across all operations:

1. **The Git Isolation Principle:** Every isolated task loop must be executed on a clean git branch or worktree environment. Commits must be made automatically at each phase boundary (`test: [TASK-ID]`, `feat: [TASK-ID]`).
2. **The Test Reversion & Scope Audit Law (Tamper Guard Upgrade):** When entering or running the `GREEN` execution phase, the testing directories must be programmatically forced back to their post-`RED` commit status via a hard checkout hook. To prevent optimization-seeking agents from circumventing execution parameters, the host CLI executes a passive `git diff` audit prior to processing any `GREEN` phase evaluation. If changes are detected outside the designated implementation targets (e.g., configurations, environment components, shared mocks, or parent infrastructure paths), the transaction is immediately invalidated, rolled back, and thrown as an execution error.
3. **Append-Only Ledger Protocol (issues.jsonl + tasks.jsonl):** All state transitions are append-only. The global `specs/issues.jsonl` serves as the authoritative issue registry (features + ad-hoc hotfixes). Issue-scoped micro-task ledgers live at `specs/features/{FEATURE_SLUG}/issues/{ISSUE_ID}/tasks.jsonl`. Agents cannot edit any status fields directly — only the CLI may append events. No existing line in any ledger is ever modified or overwritten. Canonical state is derived by parsing each ledger sequentially (bottom-up for `issues.jsonl` to find latest entry per issue_id; sequential for `tasks.jsonl` to derive task status). Ad-hoc issues bypass macro planning and route directly to isolated execution workspaces.
4. **Deterministic Test Failure Check:** For a `RED` phase to be valid, the test must crash explicitly due to missing code logic (assertions). Runtime engine issues, bad imports, typos, or script failures are caught and handled as execution errors, returning the file to the agent without committing.
5. **Memory Preservation via Train Gates:** When the code fails a compliance check, the workspace is safely reset to the last valid commit via a hard reset (`git reset --hard HEAD~1`) to remove code rot. However, the generated failure logs must be preserved and injected directly into the agent's context window. The agent's contextual understanding must expand systematically even when bad files are dropped.
6. **The Elastic Governance Rule:** The operational overhead and token consumption of the micro-execution loop can be scaled dynamically using project-level Execution Profiles configured in `.deviate/config.toml`. While the baseline state machine path remains unyielding, specific semantic phases—such as the independent Judge Phase, automated Refactoring routines, or long-running Train loops—can be scaled back, bypassed, or attached to higher/lower model thresholds depending on the target task's explicit risk or temperature tier (e.g., `--profile fast` versus `--profile secure`).
7. **Atomic Concurrency Protocol (Git Reference Locks):** To eliminate TOCTOU race conditions across distributed terminal instances, task claim and reservation are combined into a single atomic server-side write via Git branch reference creation. A worker atomically creates a branch `deviatdd/lock/<task-id>`, attempts `git push --set-upstream origin <branch>`. The server serializes concurrent claims; the first successful push wins. Rejected push attempts abort cleanly without modifying local state. The `tasks.jsonl` ledger records the authoritative outcome.
8. **The Session Continuity Principle:** Each Micro-layer task executes in a single LLM session, reusing the same connection across RED, GREEN, and REFACTOR phases. Test files that do not change during a cycle must be loaded as read-only prefix context, not appended as conversation turns. Switching the model identifier mid-task is prohibited — each model maintains its own KV cache, and a switch forces full context recomputation at cache-miss pricing.
9. **The Model Tiering Constraint:** Model selection follows a cost-appropriateness ladder: V4 Flash for high-frequency, low-complexity phases (RED, GREEN, REFACTOR, `/explore`); V4 Pro for infrequent compliance phases (JUDGE, YELLOW, `/specify`, `/tasks`); reasoning-tier models (Qwen 3.7+) for architectural phases (`/research`, `/prd`, `/shard`). The vast majority of turns (~85%) use the cheapest model. No phase may use a model more expensive than its task complexity warrants.

---

## 9. Cost Architecture

DeviaTDD's phase structure is also a cost-optimization architecture. Three mechanisms compound to achieve ~10–30x cost reduction versus naive agentic development approaches:

### 9.1 Model Tiering

| Phase | Model | 1M Input (cached hit) | Frequency | Cost Profile |
|---|---|---|---|---|
| `/explore` | V4 Flash | $0.0028 | Once/feature | Cheap scan |
| RED | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| GREEN | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| REFACTOR | V4 Flash | $0.0028 | ~5/task | Cheap gen |
| `/specify` + `/tasks` | V4 Pro | $0.003625 | Once/issue | Premium, cached |
| JUDGE | V4 Pro | $0.003625 | ~5/task | Premium, sparse |
| YELLOW | V4 Pro | $0.003625 | Conditional | Premium, rare |
| `/research`, `/prd`, `/shard` | Qwen 3.7+ | varies | Once/feature | Premium, infrequent |

~85% of all LLM turns use V4 Flash at cache-hit rates.

### 9.2 Continuous-Thread Caching

`/specify` and `/tasks` share a single session. The system prompt, tool definitions, and `spec.md` content are written to the KV cache once (first turn, cache-miss pricing) and read at 98%+ discount on every subsequent turn. Without this, each turn would re-send the full context at full price.

Micro-layer tasks similarly reuse a single Aider session across RED → GREEN → REFACTOR. The system prompt, repo map, and read-only test files form a stable prefix; only the new instruction and previous turn output are uncached.

### 9.3 Diff-Format Editing

Aider's SEARCH/REPLACE diff format sends only changed lines (~200 tokens for a typical TDD edit) versus full file rewrites (~2,000+ tokens). Over 15 turns per task, this compounds. The Architect/Editor mode further optimizes by letting a cheap model (V4 Flash Editor) produce the precise edits from a reasoning model's (V4 Pro Architect) solution description.

### 9.4 HITL Gate Prevention

Each HITL gate prevents wasted downstream compute. A design error caught at Gate 1 saves all `/prd`, `/shard`, `/specify`, `/tasks`, and Micro cycles. A spec error caught at Gate 2 saves all task decomposition and Micro cycles. Each gate is a cheap human check that prevents expensive LLM work.

### 9.5 Task Isolation

Failed RED/GREEN cycles are scoped to a single task. A failed task loses only that task's compute, not the entire feature's. Each task gets a fresh cache — there is no accumulated context debt from prior failures. Module boundary violations are caught by the JUDGE phase and trigger Train rollback without cascading into other task implementations.
