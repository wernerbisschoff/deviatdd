---
title: "Why HITL Gates"
description: "Why DeviaTDD pauses the agent at three specific moments (after research, after shard, before merge) and what the human decides at each."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: explanation/architecture/starter-architecture.md
next: false
---

DeviaTDD's agent can run for tens of minutes across phases. Without checkpoints, a single misread at the start — say, a research note that mistakes the user's domain — propagates through every subsequent phase and lands as an "AI did the wrong thing" failure at the end. **HITL gates** are the three deliberate pauses that force the human to inspect the agent's reasoning *before* it is allowed to compound. Each gate is a moment of accountability, not a moment of code review.

## Context

The phases that DeviaTDD runs (explore → research → prd → shard, then plan → tasks, then red → green → refactor) are not a uniform pipeline. They sit at three layers — Macro, Meso, Micro — and each layer makes progressively smaller commitments. The first phase, `/research`, decides *what to build*. The next, `/prd`, decides *what success looks like*. By the time `/shard` runs, the agent has already produced dozens of pages of context that downstream phases will treat as ground truth. If a human looks at the work only at the end, errors have already been baked into the ledger.

## Rationale

We chose three gates because three is the smallest number that puts a checkpoint *between* every layer transition *and* at the highest-leverage within-layer moment. Gate 1 sits inside Macro: between `/research` (the design exploration) and `/prd` (the acceptance contract). Gate 2 sits at the Macro → Meso boundary: after `/shard` has registered spec-enriched issues, before `/plan` consumes them. Gate 3 sits at the end of the entire loop: after all tasks have shipped green tests, before the final merge.

We chose *gates* (not *reviews* or *comments*) because each one is an absolute stop. A review can be deferred, ignored, or rubber-stamped; a gate cannot proceed without an explicit human decision. The phrasing is intentional — "no programmatic bypass" appears in the project contract so that future automation cannot quietly route around the human.

## Mental Model

```
   ┌────────── Macro ─────────┐   ┌──── Meso ────┐
   │  explore → research      │   │  plan →      │
   │            ↓             │   │   tasks →    │
   │  Gate 1 ← design/model   │   │   review     │
   │            ↓             │   │              │
   │         prd → shard      │   │              │
   │              ↓           │   │              │
   │  Gate 2 ← issue sign-off │   │              │
   └──── each task loop ─────►│   │              │
                              ◄─── Gate 3 ─── final merge audit
```

Picture each gate as a fence that the agent cannot cross without an explicit hand-off. The agent writes a summary, names the decisions it made, and waits. The human either opens the fence or sends the agent back. No amount of agent confidence, prompt pressure, or "just this once" rationale opens the fence.

## Trade-Offs

We chose three named, mandatory gates over a *single end-of-loop review*. The single-review design was rejected because it lets errors compound across phases; by the time the human looks, the cost of redoing the work is prohibitive. We also rejected a *gate at every phase* (a more conservative design) because it makes the human a per-phase reviewer, which produces rubber-stamping and turns the human into a bottleneck without improving quality. We considered a *confidence-based auto-pass* (skip the gate if the agent reports high confidence) and rejected it because confidence scores are not calibrated — they describe the agent's confidence in its answer, not the answer's correctness.

We accepted latency. Three gates per cycle add wall-clock time, and a slow human response stalls the agent. We accepted the discipline cost: a developer who skips a gate because "the agent's output looked right" defeats the design. The cost is paid for by the alternative — silent error propagation into the append-only ledgers, where the next phase treats bad context as ground truth and the error becomes invisible.

## Implications

Gates make early error detection cheap and late error detection expensive — the opposite of a single end-of-loop review, where detection is uniformly late. They formalize the human's role as the *decision authority*, not the *code reviewer*; the agent reviews its own code (via the red → green → refactor loop and the JUDGE phase), and the human reviews the agent's decisions. The contract is explicit: "never delete a branch unless the user explicitly requests it," "no programmatic bypass," and the gate phrasing all say the same thing — the human owns the high-stakes moments.

The hard constraint is that gates depend on a human who reads the gate summary before opening the fence. A gate surfaced mid-cycle that gets rubber-stamped is worse than no gate, because it gives false assurance that the work has been checked. Future iterations that introduce automated gate helpers must preserve the human's veto.

## See Also

- [Tutorial: Run Your First DeviaTDD Cycle](../../tutorials/starter-first-run.md) — first cycle that crosses Gate 3
- [How-To: Shard the PRD into issues](../../how-to/feature-lifecycle/shard.md) — the macro phase that ends at Gate 2
- [Reference: tasks.jsonl](../../reference/state-and-ledger/tasks-jsonl.md) — the append-only ledger the gates protect