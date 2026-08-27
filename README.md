<p align="center">
<img src="deviatdd.png" alt="DeviaTDD logo" width="435"/>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20with-uv-purple.svg)](https://docs.astral.sh/uv/)
[![PyPI](https://img.shields.io/pypi/v/deviatdd)](https://pypi.org/project/deviatdd/)

# DeviaTDD

> **An agent-orchestration framework that runs your entire TDD loop — explore, spec, red, green, refactor — with two hard human-in-the-loop gates (design/contract review and merge review); shard is a soft review.**

DeviaTDD is a CLI that coordinates AI coding agents across the full Test-Driven Development lifecycle, from problem framing through documentation. It ships with a four-layer architecture (Product · Macro · Meso · Micro), append-only ledgers, worktree isolation, and path-scoped GREEN writes. The system is **agent-agnostic** — Claude Code, OpenCode, Pi, Droid, the Factory Droid IDE, and Oh-My-Pi are first-class backends today.

---

## Why DeviaTDD?

Most AI coding agents stop at "write code that passes." DeviaTDD goes further — it runs the entire engineering loop with verification, not just generation:

| Without DeviaTDD | With DeviaTDD |
|------------------|---------------|
| Agent writes code, you review after | Two hard human gates (design/contract review, merge); shard is a soft review |
| Test edits slip in silently during "GREEN" | JUDGE flags out-of-scope writes to `tests/`, `specs/`, or protected modules as `COMPLIANCE_VIOLATION` |
| Lost track of which task is in which state | Append-only JSONL ledgers derive canonical state |
| Branch drift between parallel features | Worktree isolation + append-only ledger merge driver |
| Locked to one agent vendor | First-class support for Claude, OpenCode, Pi, Droid, Factory, and OMP |
| Specs drift from implementation | Spec-enriched issue files with FR traceability |

---

## Quickstart

```bash
# Install (requires Python 3.13+ and uv).
# The PyPI package is `deviatdd`; the CLI binary it installs is `deviate`.

uv tool install deviatdd
deviate --version                # confirm install

# Bootstrap a new project + install slash commands into your agent of
# choice. Does it all in one shot: scaffolds .deviate/, specs/constitution.md,
# governance blocks, and installs /deviate-* slash commands for the
# selected agent only. The --agent flag picks the backend persisted to
# .deviate/config.toml and is the only install target (`droid` writes
# `.factory/`; `codex` writes `.agents/skills/`).
deviate setup --agent claude     # or: opencode | pi | droid | factory | omp | codex
```

Once setup is done, drive the entire lifecycle from inside your agent. Each phase emits a single artifact, commits it, and (at the two gates) pauses for human review.

**Product layer** *(optional, for cross-product framing — skip if your repo only ships single features):*

```
/deviate-flows         "Onboard a new tenant"      # FLOW-01 customer flow → specs/_product/flows/
/deviate-architecture                                # FLOW-02 cross-epic architecture → specs/_product/architecture.md
/deviate-release        "Ship the v2 onboarding"    # FLOW-03 release plan → specs/_product/release-next.md
```

**Macro** — pick one of two paths. Full path for new features, the `adhoc` shortcut for low/medium-complexity tasks:

```
# Full path: feature scoping with a Gate 1 design review
/deviate-explore "Add user authentication via OAuth2"
/deviate-research                          # ← Gate 1: review design.md + data-model.md
/deviate-prd
/deviate-shard                             # ← review every ISS-NNN spec-enriched issue (soft review — system auto-advances to Meso; not a hard HITL gate)

# — or — Adhoc shortcut for low/medium-complexity work
/deviate-adhoc "Add a /healthz endpoint"   # condenses explore+research+prd+shard into one issue
```

**Meso — claim the issue and enter its worktree.** Meso slash commands run inside the per-issue worktree; claim first, then `cd` in:

```
# From the main checkout (NOT inside a worktree):
deviate specify                            # auto-claim the next unblocked BACKLOG issue, create .worktrees/<branch>/, print the path
#   or, to claim a specific issue by ID:
deviate specify ISS-001-007                # claim that exact issue; same worktree creation
cd $(deviate specify ISS-001-007 2>&1 | grep '^WORKTREE' | awk '{print $2}')
                                           # then re-open the agent inside the worktree
```

**Meso** — with the worktree active, decompose into tasks. `tasks.md` is the human's execution blueprint:

```
# Now INSIDE the worktree:
/deviate-plan                              # per-issue localized research → plan.md
/deviate-tasks                             # → tasks.md: 4-8 tasks, each with Verification CLI
                                           #   TDD tasks flow to the Red→Green→Judge→Refactor loop;
                                           #   IMMEDIATE tasks flow to /deviate-execute
```

**Micro** — for each task, pick the loop that fits:

```
# TDD cycle (default for TDD-typed tasks)
/deviate-red      T001                   # write a failing test
/deviate-green    T001                   # implement it; GREEN is bounded to src/ + permitted paths
/deviate-judge    T001                   # Gate decision; on rejection, the
                                         # Green → Judge → Green loop kicks in
                                         # (revert + <train_feedback> → re-GREEN, up to 3x)
/deviate-refactor T001                   # only on JUDGE_PASS

# — or — Direct path for low-complexity tasks (boilerplate, config, trivial fixes)
/deviate-execute  T002                   # skips the TDD cycle; still has its own JUDGE pass
```

**Release** — close the loop:

```
/deviate-pr       T001                   # conventional-commit PR; merge appends COMPLETED
/deviate-review                          # ← Gate 3: final PR scan; merge or request changes
```

**Or, run the unattended one-shot pipeline** — the top-level
`deviate run` is the unattended drain that *replaces* the Meso · Claim,
Meso · Plan, Meso · Tasks, and Micro steps above with a single command.
It discovers the next BACKLOG issue, claims it (creating the per-issue
worktree), runs SPECIFY → PLAN → TASKS in the worktree, then drains
every PENDING task through the TDD cycle. Under the hood it chains
`deviate meso run` with `deviate micro run --all` inside the created
worktree. Use it when you trust the agent to run end-to-end; use the
manual Meso + Micro blocks above when you want to review plan.md and
tasks.md between phases:

```
deviate run                              # full pipeline (meso + micro --all)
deviate run --issue ISS-001-007          # target a specific BACKLOG issue
deviate run --profile fast               # skip JUDGE + REFACTOR in the micro drain
deviate run --no-judge --no-refactor     # same, via boolean overrides
```

For per-task or `deviate micro run --all` invocations inside an
already-claimed worktree, see [`deviate micro run`](https://github.com/werner-bisschoff/deviatdd):
top-level `run` does both meso and micro for you; the per-task
dispatcher is `deviate micro run <task-id>` and the queue drain is
`deviate micro run --all`.

The full lifecycle takes you from a problem statement to merged, tested code with a documented audit trail.
---

## Architecture: Four Layers, Two Gates

```mermaid
flowchart TB
subgraph Product["Product Layer — Customer & Release Framing (optional)"]
  F[flows] --> A[architecture]
  A --> R[release]
end

subgraph Macro["Macro Layer — Feature Scoping"]
  E[explore] --> Re[research]
  Re --> P[prd]
  P --> S[shard]
  E -.->|low/medium complexity| Ad[adhoc]
end

subgraph Meso["Meso Layer — Issue Engineering"]
  Pl[plan] --> T[tasks]
end

subgraph Micro["Micro Layer — Per-Task Loop"]
  T --> Re1[red]
  Re1 --> G1[green]
  G1 --> J{judge}
  J -->|violation| G1
  J -->|pass| Rf[refactor]
  Rf -.->|HITL Gate 3| Done[merged]
end

subgraph MicroAlt["Micro Layer — Direct Path (low-complexity tasks)"]
  T -.->|complexity ≤ 3| Ex[execute]
end

style F fill:#f5e1f5
style A fill:#f5e1f5
style R fill:#f5e1f5
style E fill:#e1f5e1
style Re fill:#e1f5e1
style P fill:#e1f5e1
style S fill:#e1f5e1
style Ad fill:#e1f5e1
style Pl fill:#e1e7f5
style T fill:#e1e7f5
style Re1 fill:#f5e1e1
style G1 fill:#f5e1e1
style J fill:#f5e1e1
style Rf fill:#f5e1e1
style Ex fill:#f5e1e1
```

### Workflow at a Glance

| Phase | Slash command | Artifact committed | What the human reviews / decides |
|-------|---------------|--------------------|----------------------------------|
| **Bootstrap** | `deviate setup --agent <name>` | `.deviate/config.toml`, `specs/constitution.md`, governance blocks, installed `/deviate-*` slash commands | Sanity-check the constitution and the agent skills list; commit. |
| **Product · Flows** | `/deviate-flows` | `specs/_product/flows/flows-<domain>.md` + updated `specs/_product/flows/index.md` | Confirm the actor, job-to-be-done, and trigger are right; commit the flow file when asked. |
| **Product · Architecture** | `/deviate-architecture` | `specs/_product/architecture.md`, `specs/_product/domain-model.md` | Reads existing flows; classify the change as Local / Context-Bridging / Context-Creating; commit when satisfied. |
| **Product · Release** | `/deviate-release` | `specs/_product/release-next.md` (overrides previous) | Supply a release-goal sentence; confirm the Included Flows / Included Work / Acceptance tables reflect that goal; commit. |
| **Macro · Explore** | `/deviate-explore` | `specs/{epic}/explore.md` (raw codebase scan — what exists, not what to do) | Does the scan cover the right subsystems? Commit to advance. |
| **Macro · Research** *(Gate 1)* | `/deviate-research` | `specs/{epic}/design.md`, `specs/{epic}/data-model.md` | **Gate 1**: approve the design + data-model before PRD synthesis. |
| **Macro · PRD** | `/deviate-prd` | `specs/{epic}/prd.md` (FR list + acceptance criteria) | Verify each FR is testable; commit. |
| **Macro · Shard** | `/deviate-shard` | `specs/{epic}/issues/ISS-NNN-*.md` (one file per vertical slice), with `flow_refs:` frontmatter and embedded `## User Stories Ledger` / `## ATDD Acceptance Criteria` sections | Review every sharded issue for completeness, edge cases, and scope (soft review — the system auto-advances to Meso and does not block). Issues are born as full specs — the user-facing *spec content* is embedded here, but **claiming and worktree creation is a separate CLI step (`deviate specify`)** that runs after `/deviate-shard` and before the meso slash commands below. |
| **Meso · Specify** | `deviate specify [ISS-NNN-NNN]` | A git worktree at `.worktrees/<branch>/`, a claim entry appended to `specs/issues.jsonl`, and the branch pushed to remote | The setup step before plan/tasks. With no argument, auto-claims the next unblocked BACKLOG issue; with an explicit ID, claims that issue. Stops after the worktree is created — does NOT advance session state and does NOT run plan or tasks. `cd` into the printed worktree path before running any other meso slash command. |
| **Run** *(full pipeline, end-to-end)* | `deviate run` | Worktree at `.worktrees/<branch>/`, `tasks.md`, `tasks.jsonl`, then completed task commits | The canonical "go do the next thing" command. Discovers the next BACKLOG issue, claims it (creating a per-issue worktree), runs SPECIFY → PLAN → TASKS in that worktree, then drains every PENDING task through the TDD cycle. Forwards `--profile` / `--no-judge` / `--no-refactor` / `--agent` / `--json` to the micro drain. Internally calls `deviate meso run` then `deviate micro run --all` inside the created worktree. |
| **Meso · Plan** | `/deviate-plan` | `specs/{epic}/issues/ISS-NNN/plan.md` (per-issue localized research, workstation file structure) | **Must be invoked inside the worktree that `deviate specify` created.** Review the workstation mapping and the integration surface listed; commit. Optional when shard already embedded spec sections. |
| **Meso · Tasks** | `/deviate-tasks` | `specs/{epic}/issues/ISS-NNN/tasks.md` + `specs/{epic}/tasks.jsonl` (append-only ledger) | **Must be invoked inside the same worktree.** The `tasks.md` artifact is the human's execution blueprint. Verify: 4–8 tasks per issue, every task has a Verification CLI command, each task declares a Mode (`TDD` or `IMMEDIATE`) and Type, DAG `blocked_by` deps are right. TDD tasks flow to red→green→judge→refactor; IMMEDIATE tasks route to `/deviate-execute`. |
| **Micro · Red** | `/deviate-red <task-id>` | A failing test (no production code) | Agent-internal; you see the test on commit. |
| **Micro · Green** | `/deviate-green <task-id>` | Production code that passes the test | Agent-internal; GREEN is constrained to `src/` + permitted paths, and JUDGE checks scope before advancing. |
| **Micro · Judge** | `/deviate-judge <task-id>` | A `JUDGE_PASS` or `JUDGE_REJECTED` verdict over the GREEN diff | On rejection, the **Green → Judge → Green loop** rolls back to the RED commit, injects `<train_feedback>` into the next GREEN, and retries (up to 3 attempts). Read the feedback — it's the only signal you'll get for what the compliance checker objected to. |
| **Micro · Refactor** | `/deviate-refactor <task-id>` | Polished, behavior-preserving code (only on `JUDGE_PASS`) | If the refactor breaks tests, the CLI discards it and the task completes on the verified GREEN. |
| **Micro · Execute** | `/deviate-execute <task-id>` | A targeted change for `direct` / `e2e` tasks | Skips the TDD cycle; still has its own JUDGE pass. |
| **Micro · Run** *(agent-internal drain)* | `deviate micro run [task-id] --all` | Completed task commits per the cycle | Agent-internal dispatch — `deviate micro run <task-id>` runs a single task; `deviate micro run --all` drains every PENDING task. Top-level `deviate run` invokes this with `--all` inside the worktree the meso step just created. Forwards `--profile` / `--no-judge` / `--no-refactor` / `--agent` / `--json`. |
| **Release** | `/deviate-pr <task-id>` | A conventional-commit PR | Open the PR; on merge, the issue ledger is appended with `COMPLETED`. |
| **Release** *(Gate 3)* | `/deviate-review` | Final PR scan | **Gate 3**: merge or request changes. |

Operational tools (no gate, no commit): `/deviate-triage`, `/deviate-constitution`, `/deviate-hotfix`, `/deviate-prune`.

---

## Why Each Phase Exists

DeviaTDD's phase structure is not arbitrary. Each phase exists because the alternative — an agent that skips it — produces a documented failure mode. The rationale below is split into five parts: why the four layers exist, why each Product / Macro / Meso phase exists, why the two hard human gates exist (design/contract review and merge; shard is soft), why the append-only ledgers exist, and why the TDD micro-loop is `Red → Green → Judge/Train → Refactor`. Direct article citations appear inline in italics; consolidated URLs are listed under [References](#references) below.

### Why the four layers

- **Each layer matches a different model strength and a different cost profile.** Spec authoring, issue decomposition, and isolated judgement are high-judgment, low-frequency tasks best suited to a strong model. Test writing, implementation, and refactor are high-frequency, low-judgment tasks that a cheap model can perform with the right context. Splitting them into layers routes each turn to the appropriate model. *_(UCCI's 31% cost cut is a NER cascade, not coding-agent layer routing; RoBatch is batch prompting for data-management ICL. Neither paper is evidence that Product/Macro/Meso/Micro exist.)_*
- **Layering converts a monolithic chat into a chain of accountable artifacts.** Each phase commits a single artifact (an exploration note, a design doc, an issue file, a test, a commit). A chain of small, committed artifacts is auditable, recoverable, and parallelizable; a single long conversation is none of those *(SDD stages Specify → Plan → Implement → Validate; Spec Kit stages Specify/Plan/Tasks/Implement. Agile-V has two layers — Agile-V lifecycle + SCOPE-V task loop — and argues for a reviewed brief rather than a long chat. None of these papers define Product/Macro/Meso/Micro)*.
- **The Product layer is optional because most repos only ship one feature stream at a time.** A team maintaining ten products needs cross-product framing; a team shipping one web app does not. Making the Product layer optional means DeviaTDD does not impose ceremony on teams that do not need it. *_(Design proposal — closest supporting evidence is Agile-V's R0–R3 risk-adaptive framing, which is about gate strictness, not layer optionality.)_*
- **The Macro / Meso / Micro split separates *what to build* from *how to build it* from *how to verify it*.** Macro is intent. Meso is structure. Micro is verification. SDD separates *what* from *how* at the feature level (Specify vs Plan); Spec Kit uses the same feature stages. That is not a documented finding that conflating what/how/verify in one prompt is an agent failure — the Survey is a neural-vs-symbolic architecture review and does not make that claim.
- **Escalation between layers is risk-gated, not always-on.** The strong model intervenes as judge or verifier when the repair budget exhausts or when the change touches protected modules. Routine work stays in the cheap layer; high-risk work escalates automatically *(Agile-V — R0–R3 risk-adaptive acceptance. TDDev studies protocol–model fit for web-app TDD, not layer escalation; UCCI is NER cascade routing.)*

### Why the Product layer phases exist

- **The Product layer is the only place where the *product*, not the *feature*, is defined.** Features can each be correct in isolation and still contradict each other at the system level. Without a layer above the feature, there is no place where cross-feature coherence is reviewed. *_(Design proposal — supported generally by multi-agent coordination framing, but the specific "Product layer to coordinate features" argument is DeviaTDD-original.)_*
- **Splitting Flows, Architecture, and Release into three artifacts is what lets each answer a different question and be revised on a different cadence.** *Flows* answer "what is the customer's job." *Architecture* answers "how do the pieces fit together at the product level." *Release* answers "what did we promise to ship." Conflating them makes each harder to review and revise independently *(parallel: SDD — DeviaTDD extends SDD's spec/plan/implementation split to the Product level)*.
- **A flow is what prevents the agent's mental model of "what the product is" from drifting toward "what the latest spec says."** A flow defines an actor, a job-to-be-done, and a trigger — the minimum information an agent needs to evaluate whether a feature is on-strategy or off-strategy. Less than this and every feature is equally valid; more and the framework becomes bureaucratic. *_(Design proposal — the "actor / job-to-be-done / trigger" triad is structurally similar to BDD's user-story pattern [LLM BDD; Acceptance Test Gen] but the specific triad is DeviaTDD-original.)_*
- **A single-sentence release goal is the only mechanism that prevents the release from drifting into "whatever happened to be ready."** A release is a contract with users — the set of things they will get and the acceptance bar for each. A list of merged PRs is a history, not a release. Without a release goal, the release is whatever the agents produced, and there is no way to scope, evaluate, or descope it when priorities change. *_(Design proposal — the principle is supported generally by Agile-V's evidence-based acceptance and Vibe vs Agentic Coding's framework, but no specific source makes the "single-sentence release goal" argument.)_*

### Why the Macro layer phases exist

- **The Macro layer is the only place where a business goal is decomposed into spec-enriched issues at the right granularity.** Without a dedicated decomposition layer, the agent either ships the goal as one monolithic change (too large to review) or as ad-hoc task lists (too small to be independently testable). The Macro layer is where the granularity decision is made *(SDD decomposes a feature through Specify → Plan → Implement → Validate; Spec Kit through Specify/Plan/Tasks/Implement — neither is Product/Macro/Meso/Micro; Agile-V has two layers — lifecycle + SCOPE-V)*.
- **Splitting Explore and Research is what lets a cheap model do the cheap work and a strong model do the strong work.** Explore is a factual codebase scan; Research is an architectural reasoning task. A combined phase would either over-pay for trivial scans or under-pay for critical design decisions. The split routes each turn to the appropriate model and gives the human a cheaper artifact to review at the cheap stage. *(Spec Kit's discovery/validation hooks ground Specify/Plan/Tasks/Implement in repository evidence; they are not an Explore/Research cheap-vs-strong model split. Spec Kit plan-review is optional; a 40-minute arm skips intermediate artifacts.)*
- **Keeping Explore a *what exists* artifact, not a *what to do* artifact, is what lets the research phase build on it without inheriting the scan's biases.** A factual scan is the only input a research phase can build on without smuggling in design recommendations. Conflated "scan and recommend" phases lock the research phase into a direction before the human has reviewed anything. *(Spec Kit discovery hooks collect repository evidence before a stage; they do not name an Explore-as-inventory phase. Agile-V treats conversation as discovery and structured artifacts as the implementation contract.)*
- **Splitting the PRD, the design, and the data-model into three artifacts is what lets each be reviewed by a different lens and revised on a different cadence.** The PRD is *what* the system must do (requirements); the design is *how* (architecture); the data-model is *what shape the information takes* (entities, relations). Conflated artifacts force joint review and weaken every review *(SDD separates Specify (what) from Plan (how) at the feature level; Agile-V's two layers are lifecycle + SCOPE-V, not PRD/design/data-model)*.
- **Testable acceptance criteria are the requirement for a requirement to enter the PRD.** A requirement without criteria is a wish; a PRD full of wishes cannot be sharded because there is nothing for the issues to test against. The criterion test is what turns a wishlist into a PRD *(SDD — "passing spec tests only guarantee the code matches the spec"; BCMS vendor blog — "~3–10× higher first-pass success rate … according to early adopter reports," not the SDD paper; Acceptance Test Gen — LLM-generated acceptance tests are usable in production at 60% as-generated, 92% after fixes; LLM BDD)*.
- **Decomposing a feature into vertical slices, not horizontal layers, is what makes each issue independently shippable.** A vertical slice is a complete, testable behavior end-to-end; a horizontal layer is a file or module. Vertical slices can be reviewed for missing behavior; horizontal layers hide integration risk until merge. *_(TDFlow and TDDev do not use the word "vertical." TDFlow is forced-decoupled sub-agents on SWE-bench given human-written tests; TDDev compares TDD protocols by model generation style. The vertical-slice wording is DeviaTDD's.)_*
- **A complexity gate (low / medium → proceed, high → reject) is what makes Adhoc safe to expose as a shortcut.** Without the gate, "adhoc" becomes a workaround for skipping ceremony on work that needs the full Macro chain. The gate is the structural mechanism that prevents the shortcut from being misused. *_(Adaptive-enforcement concept is parallel to TDDev's protocol-model fit and TDD Governance's N=3 repair cap; the specific "low/medium → proceed, high → reject" classifier is DeviaTDD-original.)_*

### Why the Meso layer phases exist

- **The Meso layer is the only place where a spec-enriched issue is decomposed into TDD-executable tasks at the right granularity.** A spec is too coarse for a single TDD cycle; a task list is too fine for a human to review coherently. The Meso layer is where the granularity decision is made. *(TDAID describes Plan → Red → Green → Refactor → Validate. It does not give a 15–60 minute cycle time.)*
- **Re-running Plan per issue is what keeps the "what exists now" context fresh within a sprint.** Epic-level Explore becomes stale within days — by the time the fifth issue of a feature is being planned, the codebase has changed and prior issues have shipped. Per-issue Plan reads what prior issues implemented via the issues ledger, so the context reflects the current state, not the state at the start of the epic. *_(Parallel: Mise en Place's three preparation phases — contextual grounding, collaborative specification, task decomposition — and Runtime Decomp's runtime branching. Mise en Place does not name a "fresh-context per task" phase. The specific "per-issue Plan reads prior issues via the issues ledger" pattern is DeviaTDD-original.)_*
- **Human review of decomposition and machine execution of decomposition require different formats and must be separate files.** `tasks.md` is the only surface a human can read, amend, and approve task decomposition against; `tasks.jsonl` is the only surface a CLI can parse deterministically and replay across parallel branches. Combining them forces one format to compromise on both readers *(TDAD — `test_map.txt` vs `SKILL.md` separation: shrinking `SKILL.md` 107 → 20 lines raised resolution 12% → 50%; the 70% regression cut (6.08% → 1.82%) is an impact-map / `test_map.txt` result, not a red-first result)*.
- **The 4–8 tasks-per-issue target is the granularity DeviaTDD uses so each task stays reviewable and independently testable — outside that range, decomposition becomes either fragmented or bloated.** More tasks force micro-decomposition that fragments the acceptance criteria; fewer tasks hide integration risk. *_(The specific 4–8 count is DeviaTDD-original. TDAID does not state a 15–60 minute cycle.)_*
- **Explicit DAG `blocked_by` dependencies are what make the parallel work graph visible to both the CLI and the human reviewer.** A flat list of tasks with implicit order is invisible to a parallelizing CLI and uninspectable to a human looking for the critical path. The DAG is the only structure that supports parallel-execution scheduling and critical-path reasoning *(Runtime Decomp — on the Kubernetes RCA workload (N=10, simulated failure), static decomposition's retry cost exceeded monolithic by 80.5%; runtime-branched vs monolithic was 51.7% lower retry cost and vs static 73.2%. The 80.5% figure is static *worse than monolithic*, not a win for runtime vs static)*.
- **Treating the GitHub PR as a structural merge boundary, not a code-formatting step, is what gives reviewers a single artifact to review (title, body, diff, review surface).** A list of commits is a history; a PR is the unit of *what we are about to merge* *(Agile-V — SCOPE-V's verify step at "before / during / before-merge / after-deployment", treating the merge boundary as a discrete verification point)*.
- **Gate 3 (final PR review) is the only audit over the full atomic git history of a feature.** Per-task review sees a slice; Gate 3 sees the whole. A final human audit catches the long-tail issues — integration regressions, doc drift, scope creep — that escaped per-task validation *(extension of Agile-V's verify-step pattern)*.

### Why two non-bypassable human gates

- **Spec errors are the most expensive to fix downstream.** A bug in a contract caught at the post-shard review saves the plan, the tasks, and every TDD cycle that would have implemented the bug. The same bug caught after merge costs the bug report, the rollback, the post-mortem, and the customer trust. Task decomposition is cheap to regenerate; cascades of implemented tasks are not *(Agile-V — SCOPE-V's evidence-based acceptance. The 3–10× first-pass figure is a BCMS early-adopter report, not a finding in the SDD paper)*.
- **An LLM cannot self-verify its own output.** Every frontier model is a stochastic generator with zero internal semantic verification capability — the tool is irrelevant, the process is determinative. The same agent that produces a plausible design or plausible code will produce a plausible-looking review of them. A human gate at design and merge is the only verification mechanism with the necessary independence *(IACDM — "verification gap"; State Contamination — memory laundering can preserve adversarial influence below classifier threshold. PRIME's executor/verifier agents are for algorithmic reasoning — sorting, automata — not TDD judge wiring)*.
- **Gates are cheap; the work that gates prevent is expensive.** A five-minute human check at Gate 1 prevents a multi-day agent cycle that would have built the wrong thing. The economics favor verification early (Gate 1, design) and at the merge boundary (Gate 3, final audit) — but not in between, where a working agent loop is already verifiable on its own *(Agile-V — risk-adaptive acceptance at discrete levels rather than everywhere, always)*.
- **"Do not let an agent implement from a long chat. Let it implement from a reviewed brief."** Gates are the mechanism that converts a long conversation into a reviewed brief. The contract is what the agent implements against; the chat is at most a source of the contract. Without gates, the implementation drifts away from the original intent as the chat lengthens *(Agile-V / SCOPE-V — direct quote from the paper)*.
- **Two gates, not one and not ten.** One gate at the end is too late — errors have already cascaded. A gate at every micro-step is bureaucracy. Two gates correspond to the two failure modes that compound across the lifecycle: bad design (caught at Gate 1) and bad merge (caught at Gate 3). Each gate catches the class of error that the prior phases are most likely to produce. *_(The risk-adaptive framing is supported by Agile-V's R0–R3 acceptance levels; the specific count of two is DeviaTDD-original.)_

### Why the append-only ledgers exist

- **Append-only is the merge strategy DeviaTDD uses to let parallel feature branches share state without coordination or a database.** Mutable state files would require lock-step coordination; a `.jsonl` file with `merge=union` declared in `.gitattributes` lets concurrent appends on parallel branches merge without conflict markers. The state machine scales beyond a single branch because the state format is append-only. *_(Git's `merge=union` is the structural basis. TDFlow does not discuss worktrees, isolation, immutability, or branches — it is forced-decoupled sub-agents on SWE-bench given human-written tests. The "only viable strategy" claim is a software-engineering argument, not a research finding — see References §Gaps.)_*
- **Deriving CLI state from the ledger, rather than caching it in a separate file, is what prevents state drift between the CLI and the repo.** The CLI's view of current task, active issue, completed work, and FR traceability is computed by sequential parsing of the ledger on demand. A separate state file would be a cache that could disagree with the source; a derived state cannot disagree with itself. *_(Design proposal — derived-state-from-log is a general software-engineering principle; no direct source supports the specific "sequential parse on demand, no cache" pattern.)_*
- **Recording transitions as events, rather than mutating state in place, is what makes the ledger re-derivable from history.** An event can be replayed; a mutation cannot. A corrupted state file can be reconstructed by re-running the event stream, and the canonical state can always be recomputed by re-parsing the ledger. *_(Design proposal — PRIME's opened abstract is algorithmic reasoning with an executor/verifier/coordinator, not an event-replayable git State Stack.)_*
- **Deriving issue IDs from the ledger, rather than assigning them externally, is what makes them collision-free across parallel branches.** Externally-assigned IDs require coordination to avoid duplicates; ledger-derived IDs compute the next ID from the current ledger state and encode the issue's lineage by construction. The `next_issue_id` field on each shard contract is computed by parsing the ledger, not from a counter file. *_(Design proposal — the collision-free argument is a software-engineering claim, not a research finding.)_*
- **`flow_refs:` in each issue's frontmatter is the only mechanism that connects a code change back to the customer flow that motivated it.** Without the trace, a refactor that "improves" a vertical slice may break the flow that motivated it without anyone noticing. The trace is what makes the issue→flow→release chain auditable. *_(The traceability principle is supported by SDD's spec-first case studies; the specific `flow_refs:` frontmatter convention is DeviaTDD-original.)_*
- **A review surface and an execution surface serve different readers and must be separate files.** `tasks.md` is the only artifact a human can read, amend, and approve task decomposition against; `tasks.jsonl` is the only artifact a CLI can parse deterministically and replay across parallel branches. Combining them forces one format to compromise on both readers — a human-readable markdown becomes hard to parse, or a parseable JSONL becomes hard to review *(TDAD — `test_map.txt` vs `SKILL.md` separation)*.

### Why the TDD micro-loop is `Red → Green → Judge/Train → Refactor`

The TDD micro-loop is what makes agent-written code trustworthy. Each phase exists because the agent has a documented failure mode that the phase structurally prevents.

#### Why Red (write a failing test first)

- **Tests written after implementation tend to reflect what the code does, not what it should do.** When the same agent writes both test and implementation in one session, the implementation bleeds into the test — a failure mode known as *context pollution*. The test ends up passing trivially because it asserts whatever the implementation does, not whatever the spec requires. Forcing the test to be written first, in a session with no implementation, is DeviaTDD's structural counter to that bleed *(TDD Agent Dev; Refactor Pattern — context pollution when test and implementation share a session)*. TDAD is not evidence for red-first: its 70% regression cut (6.08% → 1.82%) and `SKILL.md` 107 → 20 / 12% → 50% are impact-map / `test_map.txt` results. The same paper's TDD Prompting Paradox: TDD instructions without a targeted test map *raised* regressions to 9.94%.
- **A test that passes immediately is not a test.** Confirming the test fails before any production code exists verifies that the test actually exercises the new behavior. Skipping this step risks shipping a test that exercises nothing — green by construction, useless by construction.
- **The test is the agent's only objective specification.** An agent given "make this work" produces plausible-looking code; an agent given "make this test pass" produces code whose correctness is mechanically checkable. The test is the only artifact in the loop that the agent cannot rationalize its way past *(TDD Agent Dev — tests as spec and guardrail)*.

#### Why Green (write the minimum code to pass)

- **"Do not change the tests" must be structurally enforced, not just instructed.** When an agent is given a failing test and a goal of making it pass, the cheapest path is often to weaken the test — delete an assertion, catch an exception, return a hard-coded value. Without a structural constraint, the green phase collapses into test-hacking. Documented frontier-model failures include deleting scoring code and calling `sys.exit(0)` to make all tests appear to pass. DeviaTDD enforces this by constraining GREEN writes to `src/` (and a small permitted-paths list) and surfacing out-of-scope modifications to `tests/`, `specs/`, or protected modules as `COMPLIANCE_VIOLATION` from JUDGE *(TDD Governance — proposal-execution separation; TDD Agent Dev)*.
- **The minimum code to pass is the only code that is verifiably correct.** Any code beyond the minimum introduces the possibility of bugs the tests do not cover. Constraining green to the minimum keeps the implementation close to the specification and the test surface meaningful *(parallel: TDAD — "regression as first-class metric")*.
- **Green is bounded by the test.** The red test is the agent's goal; the implementation is just a means to that goal. Removing the test as the goal removes the only objective success criterion in the loop and replaces it with the agent's own judgment of "looks right" — which is exactly the failure mode the loop exists to prevent *(Refactor Pattern — refactor is safe only while the test suite passes; failing tests roll back the change)*.

#### Why Judge / Train (the Green → Judge → Green loop)

- **The same agent that wrote the green code cannot reliably review it.** A self-review inherits the biases and blind spots of the producer — the same hallucinations, the same shortcuts, the same rationalizations. The Judge phase runs in an isolated session with a fresh context, breaking the recursive subjectivity of "did I do what I would have approved?" *(IACDM — external verification agents at discrete gates. PRIME's executor/verifier split is algorithmic-reasoning constraint checking, not a TDD judge)*.
- **Tests passing is necessary but not sufficient.** A green test suite verifies the implementation matches the test; it does not verify the implementation matches the spec, the architecture, the security model, the performance budget, or the protected-module list. Judge evaluates the production diff against the contract for invariant, security, and structural violations the test cannot express. A separate human-style validation step at the end of an agentic session is required even when tests are green *(IACDM — verification gap; State Contamination — even classifier-cleaned memory can carry adversarial influence)*.
- **Bounded repair with feedback injection converts failure into a learning signal.** When Judge rejects, the CLI rolls the task back to the RED commit (a known-good state), injects the failure feedback into the next GREEN prompt, and retries — up to three times. The next attempt has the same context plus the explicit feedback of why the previous attempt failed. This is the "Train" half: the failure is preserved as a constraint on the next attempt, not discarded as a dead end *(TDD Governance — N=3 GREEN repair cap, a chosen bound; the paper has four *stages* — planning, generation, repair, validation — not "4 validation gates." Parallel: TDAD treats regression as a first-class metric via a targeted test map, not via red-first prompting)*.
- **Three retries is enough; more would be a sign of a wrong test or a wrong spec.** A green implementation that fails Judge three times is unlikely to converge on the fourth. The bound forces escalation back to the human (an amendment, a new plan, or a spec revision) rather than burning compute on a fundamentally misaligned task. The empirical cap `N=3` is consistent with documented multi-agent TDD governance practice *(TDD Governance)*.
- **Rollback is to a known-good commit, not a fresh start.** The RED commit is the verified-good test boundary. Resetting to it discards the suspect GREEN cleanly, but preserves all prior work — the test, the spec, the agent session, the audit trail. Starting from a fresh checkout would also discard the test, which is the only artifact whose correctness has actually been confirmed *(TDD Governance — proposal-execution separation. TDFlow does not discuss worktrees, isolation, or immutable branch state)*.

#### Why Refactor (behavior-preserving improvement)

- **Refactor's benefits are delayed and invisible, so without an explicit phase it gets skipped.** The same agent that just got a green test is heavily biased to commit and move on. A dedicated refactor phase, gated on Judge's `JUDGE_PASS`, structurally separates "make it work" from "make it clean" *(TDAID — Refactor is a discrete phase; TDD Governance — design hygiene principle)*.
- **The green test suite enables aggressive restructuring.** Refactoring is safe only while the test suite passes. After Judge, the test suite is the refactor's safety net — any behavior change breaks a test, which is caught immediately and rolled back. Without the green gate in front of the refactor, no refactor is safe *(Refactor Pattern)*.
- **Refactor must be behavior-preserving — never test-preserving.** The discipline of "tests must still pass when you're done" is the refactor's definition. If a refactor requires changing a test, the original code was wrong, not just ugly — and that is a Judge issue, not a refactor issue. Conflating the two erodes the test's role as the contract *(Refactor Pattern; TDD Governance)*.
- **Refactor that breaks tests is discarded, not debugged.** A failed refactor means the agent misjudged the surface area of the change. The safe outcome is to fall back to the verified GREEN — the user gets a working implementation either way, and the diff stays minimal *(Refactor Pattern; TDAID)*.

---

## References

The rationale above grounds each architectural choice in published agentic-engineering research. Direct claims are cited inline; every citation resolves to the primary article URL — no internal research notes are linked from this README. Where a claim has no direct source in the corpus, the rationale flags it as a _design proposal_ and lists it under "Gaps" below.

### Methodology (de jure) — frameworks and governance

- [**Agile-V / SCOPE-V**](https://arxiv.org/abs/2605.20456) — Agentic-Agile vs Vibe-Coding: Verified Engineering. Two layers (Agile-V lifecycle + SCOPE-V task loop), not Product/Macro/Meso/Micro. Defines R0–R3 risk-adaptive acceptance; SCOPE-V's verify step at "before / during / before-merge / after-deployment"; "Do not let an agent implement from a long chat. Let it implement from a reviewed brief."
- [**IACDM**](https://arxiv.org/abs/2604.16399) — Interactive Adversarial Convergence Development Methodology. 8-phase framework with external verification agents at discrete gates; "the tool is irrelevant, the process is determinative"; foundational source for the "verification gap" rationale.
- [**PRIME**](https://doi.org/10.20944/preprints202601.1479.v1) — Policy-Reinforced Iterative Multi-Agent Execution for Algorithmic Reasoning. Crossref abstract: executor / verifier / coordinator agents for sorting, automata, and state-machine tasks. Full text 403 on preprints.org. Not a git ledger or TDD judge paper.
- [**State Contamination**](https://arxiv.org/abs/2605.16746) — State Contamination in Memory-Augmented LLM Agents. Memory laundering can preserve adversarial influence below classifier thresholds.
- [**Survey**](https://doi.org/10.1007/s10462-025-11422-4) — Agentic AI: A Comprehensive Survey of Architectures, Applications, and Future Directions ([arXiv:2510.25445](https://arxiv.org/abs/2510.25445)). Dual-paradigm review of neural vs symbolic agent architectures. Not a source for "conflating what/how/verify in one prompt."
- [**UCCI**](https://arxiv.org/abs/2605.18796) — Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing. 31% cost reduction at micro-F1 = 0.91 on a production NER workload (4B/12B cascade). Not coding-agent layer routing.
- [**RoBatch**](https://doi.org/10.14778/3734839.3734853) — Optimized Batch Prompting for Cost-Effective LLMs. Batch prompting for data-management in-context learning. Not cascade routing of spec vs implement.

### Methodology (de jure) — process and decomposition

- [**SDD**](https://arxiv.org/abs/2602.00180) — Spec-Driven Development: From Code to Contract. Feature stages Specify → Plan → Implement → Validate (tools often add Tasks). "A passing spec test doesn't guarantee correct software—it only guarantees that the software matches the spec." Does **not** contain a 3–10× first-pass figure.
- [**Spec Kit**](https://arxiv.org/abs/2604.05278) — Spec-Kit Agents: Context-Grounded Agentic Workflows. Feature stages Specify/Plan/Tasks/Implement with discovery/validation hooks; SPEC.md + PLAN.md + TASKS.md intermediate artifacts. Plan-review is optional (auto-approved in the study); a 40-minute arm skips those artifacts.
- [**Mise en Place**](https://arxiv.org/abs/2605.05400) — Mise en Place for Agentic Coding. Three named phases: contextual grounding, collaborative specification, task decomposition. Does not name a "fresh-context per task" phase.
- [**Runtime Decomp**](https://arxiv.org/abs/2605.15425) — Runtime-Structured Task Decomposition for Agentic Coding Systems. N=10, simulated failure: static retry cost exceeded monolithic by 80.5% (RCA); runtime-branched vs monolithic 51.7% lower retry cost, vs static 73.2%.

### Implementation (de facto) — TDD, agents, and refactor

- [**TDAD**](https://arxiv.org/abs/2603.17973) — Test-Driven Agentic Development. Impact-map / `test_map.txt` results: 70% regression reduction (6.08% → 1.82%); shrinking `SKILL.md` 107 → 20 lines raised resolution 12% → 50%. TDD Prompting Paradox: TDD instructions without a targeted test map raised regressions to 9.94%. Not a red-first proof.
- [**TDFlow**](https://arxiv.org/abs/2510.23761) — TDFlow: Agentic Workflows for Test-Driven Development. Forced-decoupled sub-agents (propose / debug / revise / optional test generation) on SWE-bench given human-written tests. Does not discuss worktrees, isolation, immutability, branches, or append-only ledgers.
- [**TDDev**](https://arxiv.org/abs/2605.17242) — From Runnable to Shippable: Multi-Agent TDD. Protocol-model fit: holistic models benefit from agentic TDD; conservative read-then-extend models benefit from incremental TDD. Does not use the word "vertical."
- [**TDD Governance**](https://arxiv.org/abs/2604.26615) — TDD Governance for Multi-Agent Code Generation. N=3 GREEN repair cap (chosen bound); four *stages* (planning, generation, repair, validation); design hygiene (refactor continuously while green); proposal-execution separation.
- [**TDAID**](https://www.awesome-testing.com/2025/10/test-driven-ai-development-tdaid) — Test-Driven AI Development. Plan → Red → Green → Refactor → Validate; local commits after each TDD phase. Does not state a 15–60 minute cycle.
- [**Refactor Pattern**](https://agentpatterns.ai/verification/red-green-refactor-agents/) — Red-Green-Refactor with Agents: Tests as the Spec. Refactor must be behavior-preserving, never test-preserving; failed refactors are discarded.
- [**TDD Agent Dev**](https://agentpatterns.ai/verification/tdd-agent-development/) — Test-Driven Agent Development: Tests as Spec and Guardrail. Tests-as-spec-guardrail pattern; structural enforcement against test-hacking.

### Specification and acceptance

- [**Definitive SDD**](https://thebcms.com/blog/spec-driven-development) — Spec-Driven Development: The Definitive 2026 Guide. EARS notation (Ubiquitous / Event-driven / State-driven / Unwanted / Optional). "~3–10× higher first-pass success rate from AI agents on non-trivial tasks, according to early adopter reports from GitHub and AWS."
- [**Acceptance Test Gen**](https://arxiv.org/abs/2504.07244) — Acceptance Test Generation with LLMs (Industrial Case Study). 95% helpfulness, 92% semantic relevance, 60% directly usable as generated.
- [**LLM BDD**](https://arxiv.org/abs/2403.14965) — Comprehensive Evaluation: LLMs for BDD Acceptance Test Formulation. Comprehensive evaluation of GPT-3.5/4, Llama-2, PaLM-2 on BDD generation.

### Strategic framing

- [**Vibe vs Agentic**](https://arxiv.org/abs/2505.19443) — Vibe Coding vs. Agentic Coding: Fundamentals and Practical Implications. Foundational framing of agentic coding vs vibe coding.

### Gaps and design proposals

Claims in this README flagged with an italic _design proposal_ note have **no direct source** in the agentic-engineering literature at the time of writing. They are explicit gaps in the evidence chain; treat them as DeviaTDD design choices, not research findings:

- **Append-only JSONL over mutable state** — the "only viable merge strategy across parallel branches" claim is a software-engineering argument supported by git's `merge=union` semantics, not a research finding (TDFlow does not discuss isolation or ledgers).
- **Product layer optionality; Flows / Architecture / Release triad; single-sentence release goal** — DeviaTDD-original; closest support is SDD's spec-from-plan-from-implementation separation at the feature level.
- **4–8 tasks per issue** — DeviaTDD-original; TDAID does not state a 15–60 minute cycle.
- **Per-issue Plan cadence; Adhoc complexity classifier; ledger-derived issue IDs; `flow_refs:` frontmatter convention; deriving CLI state from the ledger** — DeviaTDD-original; parallel support from adjacent work exists but does not directly cover these patterns.
- **Two gates, not one and not ten** — the risk-adaptive framing is supported (Agile-V R0–R3); the specific count of two is DeviaTDD-original. Design/contract review and merge review are the hard gates; shard is a soft review.

---

## Troubleshooting

**`uv: command not found`** — Install [uv](https://docs.astral.sh/uv/) first
(it's the project's mandated package manager per
[`specs/constitution.md`](specs/constitution.md)). macOS / Linux:
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

**`deviate: command not found` after `uv tool install deviatdd`** — Verify
the install landed: `uv tool list | grep deviatdd`. Reinstall if missing:
`uv tool install --reinstall deviatdd`. The PyPI package name and the CLI
binary name differ — that's intentional (see [Quickstart](#quickstart)).

**`deviate setup` runs but `/deviate-*` commands don't appear in the
agent** — Slash commands are installed to `<workdir>/.claude/commands/`,
`.opencode/commands/`, `.omp/commands/`, `.factory/commands/`, and
`.pi/prompts/`. Verify the directory exists and is readable, then restart
the agent so it picks up the new commands.
**`/deviate-plan` (or `/deviate-tasks`) picks up the wrong issue, claims
"no active issue", or shows stale context** — Meso slash commands must be
invoked from inside the per-issue worktree that `deviate specify` (or
`deviate run`) created. From the main checkout, run `deviate specify`
(or `deviate specify ISS-NNN-NNN` for a specific issue), `cd` into the
`.worktrees/<branch>/` path it prints, and re-open the agent there
before running `/deviate-plan` or `/deviate-tasks`.


**`mise run publish` fails with `PYPI_API_TOKEN is not set`** — The task
loads `.env` from the project root. `.env` must contain
`PYPI_API_TOKEN=pypi-...`. `.env.example` documents the variable name;
`.env` itself is gitignored.

**Agent backend not installed** — `deviate setup --agent <name>` scaffolds
the project without the agent present, but invoking `/deviate-*` slash
commands requires the agent to be installed. Install Claude Code / OpenCode
/ Pi / Droid / Factory / OMP first per their respective install
instructions.

For development-setup details, see
[`CONTRIBUTING.md`](CONTRIBUTING.md#development-setup) and
[`specs/constitution.md`](specs/constitution.md).

## License

[MIT](LICENSE) © 2026 Werner Bisschoff
