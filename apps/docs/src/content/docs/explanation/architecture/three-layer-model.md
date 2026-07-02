---
title: "Why the Three-Layer Model"
description: "Why DeviaTDD splits work into Macro, Meso, and Micro layers, the rejected alternatives, and the cost of phase gates."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: explanation/architecture/model-tiering.md
next: false
---

DeviaTDD operates across very different timescales. A product team sketching a new authentication system thinks in weeks and works from fuzzy requirements; an automated agent writing one test for one function thinks in minutes and operates on a frozen specification. The architecture has to answer one question: how can a single toolchain host both modes without collapsing one into the other, and how can a piece of work be scoped, planned, and executed without ever confusing the operator's job with the agent's job.

## Context

Most agentic development tools answer that question by running one loop. The same prompt template is invoked for "design me a feature" and "write me a test"; the model that runs the loop is the model that does everything, and the human either micromanages every turn or steps away entirely. That symmetry is convenient but it leaks risk: the cheap model acceptable for "write a test" is the cheap model that gets asked to "design the data model", and the expensive model that should design the data model is the one being asked to write the test. The phases blur, the prompts blur, and the costs blur.

The constitution makes the timescale separation explicit. It declares three layers — **Macro**, **Meso**, **Micro** — each with its own phases, its own artifacts, its own HITL gates, and its own model tier. The separation is not a UI nicety; it is the contract that lets the operator and the agent work in their respective registers without one drowning the other. Before DeviaTDD, attempts to combine planning and execution inside a single prompt produced templates that were either too vague for a planning phase or too brittle for an execution phase — and the human gate that was supposed to catch drift either fired too often (micro-managing every test) or too rarely (catching architectural mistakes after they had been coded).

## Rationale

The decision to lock the architecture at three layers — no more, no fewer — comes from two constraints. The first is the operator's mental bandwidth: a contributor working in Meso mode should not have to remember the contents of Micro's RED phase to make a planning decision. The second is the model's contextual scope: a reasoning-class model asked to do exploratory context-gathering in Macro is overpaying for the task, while a flash-class model asked to synthesise a PRD is underspecifying it.

Macro, Meso, and Micro each have a stable artifact contract. Macro ends in sharded issue files; Meso ends in `plan.md` and `tasks.md`; Micro ends in a passing test plus an append-only ledger entry. The artifacts are the boundaries that let one layer hand work to the next without re-explaining the world. When Macro hands a sharded issue to Meso, the issue already carries user stories, acceptance criteria, and edge cases — the planner does not have to re-derive them. When Meso hands a task to Micro, the task already declares its file boundaries, its mock surfaces, and its test fixture expectations. Each handoff is a contract, not a narrative.

The HITL gates are what make the contracts enforceable. Gate 1 sits between research and PRD; Gate 2 sits between shard and plan; Gate 3 sits after all tasks before merge. Each gate is a no-bypass checkpoint: the human must approve before the next layer begins. That is why Macro can hand a frozen spec to Meso, and why Meso can hand a frozen plan to Micro — because at every boundary, a human has read the artifact and signed it. The three layers are not just a decomposition; they are a chain of custody.

## Mental Model

Picture the work as a downward funnel: a fuzzy goal at the top, a passing test at the bottom, and three filters in between, each filter narrowing scope and increasing precision.

```
+---------------------------+
|     Feature / Epic        |  <- operator's question
+-------------+-------------+
              v  Macro (explore -> research -> prd -> shard)
+---------------------------+
|  Spec-enriched issue      |  <- horizontal slices banned;
|  files                    |     vertical slices only
+-------------+-------------+
              v  Meso (plan -> tasks)
+---------------------------+
|  plan.md / tasks.md /     |  <- one functional unit per entry
|  tasks.jsonl              |
+-------------+-------------+
              v  Micro (red -> green -> [yellow?] -> judge -> refactor)
+---------------------------+
|  passing test +           |  <- ledger append, branch commit
|  ledger entry             |
+---------------------------+
```

The diagonal line from top-left to bottom-right is the **scope** of the work; the vertical drop is the **rigour** applied to it. Scope shrinks at every handoff; rigour increases. The HITL gates are the horizontal bars that hold the funnel in shape — without them, scope could silently re-expand (a Micro agent re-deciding the spec) and rigour could silently collapse (a Macro agent skipping a criterion).

## Trade-Offs

Three alternatives were considered and rejected.

A **single-layer loop** — one prompt template that takes a goal and produces a patch — was rejected because it forces every layer's question to be answered by the same model in the same session. The cost of model switching is high enough that operators would either always use the expensive model (wasteful for "write me a test") or always use the cheap model (unsafe for "design the data model"). The three-layer split pays an upfront context cost (the planner must read the spec, the executor must read the task) to keep model choices independent.

A **five-layer decomposition** — splitting Macro into Product/Strategy/Design, splitting Micro into Write/Verify/Polish — was rejected because it added handoffs without adding rigour. Every handoff is a place where context can be lost or re-litigated; a five-layer model had twice as many handoffs without a corresponding gain in human checkpoints. The two extra layers collapsed under their own ceremony.

A **two-layer decomposition** — strategy and execution only — was rejected because the planning artefact (task list, file boundaries, mock fixtures) was too large to fit inside a single execution session and too small to require full architectural reasoning. The Meso layer exists because the work between "approved spec" and "executable task" is real work that benefits from its own model tier, its own contract (`plan.md` plus `tasks.md`), and its own review.

## Implications

The shape of the three layers constrains what DeviaTDD can evolve toward. A new phase that does not fit Macro, Meso, or Micro has nowhere to land; either it is rejected, or one of the three layers absorbs it and the layer's contract changes. The Micro layer's strict write boundary (`src/**/*.py` only) is enforced because Micro is a sandbox; the same boundary would be wrong for Meso, which legitimately writes to `specs/` and `tests/`. The model tiering is locked at the layer level: a phase cannot opt out of its layer's tier without rewriting the constitution.

What becomes easier: a contributor who has read this page can predict where any new skill will land. A skill that takes a goal and produces design options is Macro; a skill that takes a spec and produces a task list is Meso; a skill that takes a task and writes code is Micro. The classification is mechanical, and the model cost is mechanical with it. What becomes harder: cross-cutting concerns that span all three layers (e.g., a new tamper-guard rule that affects Macro ledger validation and Micro test reset) must be specified at each layer's contract and ratified by each gate. There is no shortcut through the architecture.

## See Also

- [Why Diátaxis: The Architecture Behind This Docs Site](./starter-architecture) — sibling rationale for the docs site itself
- [Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — end-to-end tutorial that exercises all three layers
- [How-To: TDD Micro-Cycle](/how-to/tdd-micro-cycle/red) — operator recipes for the Micro layer's RED/GREEN/YELLOW/JUDGE/REFACTOR phases
- [Reference: Config Schema](/reference/config/deviate-config) — per-phase model routing under `[models]`