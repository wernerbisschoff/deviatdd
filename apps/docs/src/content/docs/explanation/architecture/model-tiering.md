---
title: "Why Model Tiering: Routing Phases to LLM Tiers"
description: "Why DeviaTDD assigns each phase a different LLM tier, how resolve_phase_model reads .deviate/config.toml, and the trade-offs we accept."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: explanation/architecture/starter-architecture.md
next: false
---

DeviaTDD runs thirteen distinct phases, but it does not ask every phase of the same model. A RED micro-loop and a PRD shard phase pay different prices for a wrong answer: RED can be re-run in seconds with a stronger model; a PRD that hallucinates a data model can corrupt ten downstream tasks. Routing each phase to a tier that matches its blast radius is the design.

## Context

LLM-as-agent workflows are billed per token, but their cost is not uniform. The plan-and-tasks phase tolerates a 30-second stall while reasoning over an architecture; the red phase runs in a tight inner loop where latency dominates the developer's perception of "is this working?" If every phase used the same frontier model, a single feature would burn through tokens that cheaper tiers can deliver just as well — and a slow frontier model would block a fast micro-loop for no benefit. The taxonomy of phase roles in `AGENTS.md` (Macro / Meso / Micro) hints at the answer: each layer has a different price-of-failure, so each deserves a different price-of-reasoning.

## Rationale

The decision is to map each phase to one of three named tiers and let the contributor override the mapping per phase. `src/deviate/state/config.py::resolve_phase_model` walks the `[models]` table in `.deviate/config.toml` in a fixed order: first a phase-specific key (e.g. `judge = "opencode/deepseek-v4-pro"`), then `default`, then `None` so the backend falls back to its native model. Resolution is case-insensitive and silently drops empty values so a commented-out line cannot poison the lookup. The mapping itself is opinionated: V4 Flash handles the inner loop (`explore`, `red`, `green`, `refactor`) where cost and latency matter most; V4 Pro handles the bookkeeping phases (`plan`, `tasks`, `yellow`, `judge`) where cached context and audit-friendly behaviour matter; Qwen 3.7+ [Thinking] handles the speculative phases (`research`, `prd`, `shard`, `adhoc`) where a longer reasoning trace is worth its latency.

## Mental Model

Think of the phase pipeline as a relay where each leg hands a baton to a different runner. The contributor's `.deviate/config.toml` is the lane assignment; `resolve_phase_model` is the referee that decides who runs which leg.

```
.deviate/config.toml          resolve_phase_model(phase)
┌──────────────────────┐       ┌──────────────────────────┐
│ [models]             │       │ 1. lookup phase key      │
│   default = "..."    │ ───▶  │ 2. fallback "default"    │
│   judge  = "..."     │       │ 3. None → backend default│
│   red    = "..."     │       └──────────────────────────┘
└──────────────────────┘
```

The mapping is *additive*: removing a phase key does not break the runner, it just lets the default apply. The `claude` backend ignores the resolved value silently (it has no `--model` flag), so the table is portable across backends even when its effects are not.

## Trade-Offs

We rejected three alternatives before settling on tiered routing.

- **Single-frontier-model-for-everything.** Predictable quality, but pays frontier prices for inner-loop RED/GREEN where a smaller model suffices; commits the project to one provider's rate limits.
- **Auto-route by prompt complexity.** The model picks itself based on heuristics. We rejected this because it puts the routing decision inside an opaque model call, defeats per-phase overrides, and makes the *human's* verification role harder (the contributor cannot reason about "which model just made this call?").
- **No model field at all — every backend uses its native default.** Cheapest to maintain, but locks the contributor out of cost control and makes tiered caching impossible.

The cost we accept is that contributors must understand which tier each phase uses; the `AGENTS.md` table is the cheat sheet. We also accept that the V4 Pro / Qwen / V4 Flash labels are tied to one provider's naming and may need re-labelling as providers change.

## Implications

Per-phase routing makes cost visible: a heavy use of the `prd` phase shows up on the bill as Qwen tokens, not V4 Flash tokens, and the contributor can dial it down by overriding `prd` to a cheaper tier. It also makes *session continuity* a first-class concern — `AGENTS.md` mandates that a micro-task reuses one LLM session across RED → GREEN → REFACTOR, because model switches mid-loop reset reasoning caches. JUDGE, in contrast, runs in an isolated V4 Pro session so its verdict is not contaminated by the model's prior defence of its own code. The Tier table is therefore both a cost dial and a *separation-of-concerns* dial; changing a tier is a meaningful design choice, not a knob to twist casually.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — see the tier table in action across one full cycle.
- [How-To → DeviaTDD Config → Set Up Model Tiering](/how-to/config/deviate-config-model-tiering) — the operator recipe for editing `.deviate/config.toml`.
- [Reference → Config Schema → Config Field Reference](/reference/config/deviate-config) — every `[models]` key documented.