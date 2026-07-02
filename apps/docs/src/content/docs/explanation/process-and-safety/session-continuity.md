---
title: "Why Session Continuity Across the Micro-Loop"
description: "Why DeviaTDD pins RED, GREEN, and REFACTOR to one LLM session, where the boundary at JUDGE is drawn, and what changes when the cached model is reset."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: false
next: false
---

A micro-task is a tight conversation. RED writes a failing test against a frozen spec; GREEN writes the minimum implementation that satisfies it; REFACTOR restructures without changing what the test asserts. Each phase asks the model a slightly different question, but they refer back to one another — RED's "here is the assertion" is GREEN's "here is what I have to satisfy", and GREEN's "here is the structure I chose" is REFACTOR's "here is what I can safely rename". The architecture's job is to keep that conversation alive across the slash commands that delimit the phases, and to break it deliberately where breaking it is the whole point.

## Context

Multi-phase agent pipelines are usually implemented as a sequence of independent prompts. Each `/deviate-red` is its own chat; each `/deviate-green` is its own chat; the slash command boundary is the session boundary. That is convenient to build — every command is a self-contained prompt with a self-contained context window — but it discards the most valuable intermediate state of a micro-task: the model's reasoning trace. The trace is what lets a GREEN rewrite make sense in light of RED's choice of test name, assertion shape, and mocked collaborators. After a session break the model re-derives the trace from the diff, the test, and the spec, which costs tokens and occasionally produces a GREEN that contradicts RED's framing without either phase noticing.

DeviaTDD's constitution makes the opposite choice explicit. RED, GREEN, and REFACTOR share one LLM session so the reasoning cached inside RED is available to GREEN and REFACTOR without re-derivation. JUDGE, the fourth phase of the loop, breaks the rule on purpose: it runs in an isolated V4 Pro session so its verdict is not contaminated by the model's prior defence of its own code. The same principle that argues for continuity inside the loop argues for isolation at the compliance gate; the design reconciles the two by drawing the boundary at JUDGE, not at GREEN or REFACTOR.

## Rationale

The decision binds the three inner-loop phases to a single agent session because the reasoning cache is the most valuable artifact a micro-task produces — more valuable than the failing test in isolation, more valuable than the GREEN diff in isolation, more valuable than the refactor diff in isolation. The same model that chose the test name in RED is the model that picks the variable names in GREEN and the rename strategy in REFACTOR; splitting the session splits the cache, and the cache is what lets a 90-second GREEN produce a result that is internally consistent with a 90-second RED. Continuity is not a performance optimisation; it is the precondition for the loop to converge.

The boundary is JUDGE. JUDGE runs in an isolated V4 Pro session precisely so its verdict is not contaminated by the model's prior defence of its own code. The same line of reasoning that argues for cache reuse inside the loop argues for cache isolation at the gate; the design reconciles the two by drawing the seam at JUDGE, not at GREEN or REFACTOR. The model tiering reference calls this "the cache-sacrifice compliance gate", and it is the deliberate inversion of the rule that holds the three inner-loop phases together.

Persistence anchors the in-memory cache to disk so the next slash command can resume it. `src/deviate/state/config.py::SessionState` carries `red_commit_sha` across the three phases, written after the RED commit lands (`src/deviate/cli/micro.py:951`), consulted by GREEN's diff base (`micro.py:1123`), and used by JUDGE's rollback anchor (`micro.py:1299`). The on-disk file (`.deviate/session.json`) is the durable side of continuity; the LLM session is the in-memory side. Lose either one and the contract degrades: lose the LLM session and the next phase re-derives; lose session.json and the next phase starts cold even if the agent session survived.

## Mental Model

Picture one agent session wrapping the three inner-loop phases, with the session.json file as its seam to disk. JUDGE sits outside the bubble, looking in.

```
+--------------------- One Agent Session ---------------------+
|                                                              |
|  /deviate-red       /deviate-green         /deviate-refactor |
|  +----------+       +------------+         +--------------+   |
|  | red(TSK) | ----> | green(TSK) |  ---->  | refactor(TSK)|   |
|  |  failing |  diff |  passing   |  diff   | still passes |   |
|  +----+-----+       +-----+------+         +-------+------+   |
|       |                  |                      |           |
|       +-- shared cache --+------ shared cache --+           |
|                                                              |
+--- session.json: red_commit_sha, active_issue_id, ... -------+
                              |
                              v
                isolated V4 Pro session for /deviate-judge
```

The shared cache is the continuity contract; the on-disk seam is the resume contract. Together they let a slash command resume the previous phase's reasoning instead of re-deriving it from scratch.

## Trade-Offs

Three alternative continuity models were considered and rejected. A **one-session-per-slash-command** model — the default of most agent tools — was rejected because it forces the model to re-read the spec, re-derive the task, and treat the previous phase's diff as foreign context. Three phases times the re-derivation cost is wasted tokens at every micro-task, plus a measurable risk that RED's framing and GREEN's reading of RED drift apart in ways neither phase can detect.

A **one-session-per-issue** model — shared across all phases including JUDGE — was rejected because it lets the compliance gate inherit the model's prior defence of its own code, which biases verdicts toward `COMPLIANCE_PASS`. The whole point of JUDGE is impartiality; continuity to GREEN contaminates it. The same reasoning that argues for cache reuse inside the loop argues against it at the gate.

A **one-session-per-workspace** model — long-running across many tasks — was rejected because the context window is bounded. A long-running session would either evict early reasoning about earlier tasks (cache thrashing) or blow token budgets on tasks unrelated to the current micro-loop. Per-task continuity is the smallest unit that benefits from caching and the largest unit that still fits in a window.

The cost we accept is that contributors cannot switch model tiers mid-micro-loop. If the `[models]` table is edited and the `green` tier changes while RED is mid-flight, the session terminates and the next `/deviate-green` runs cold. That is deliberate — the design treats tier switches as the operator's signal that a deliberate handoff is required, not a dial to nudge between phases. The model-tiering reference documents the constraint, and the session-continuity design assumes the tier table is stable for the duration of a task loop.

## Implications

The session.json file becomes load-bearing for any phase that needs to know "where did RED leave off?". GREEN diffs against `red_commit_sha`; JUDGE rolls back to it; REFACTOR's lint baseline is anchored at it. Lose the file and continuity is gone even if the git history is intact — the agent session may have survived, but the next phase that re-reads session.json will treat it as initialised and silently drop the anchor. Tamper-evidence for the session file is therefore part of the same contract as tamper-evidence for the append-only ledgers.

A future change that wants to skip a phase (e.g., "if the assertion already exists, skip RED") has to decide whether continuity survives the skip or terminates. The architecture's answer is that continuity is preserved as long as the cached model session is intact — a `green` invocation after a no-op `red` is still inside the same session. Skipping a phase in code (a `--skip-red` flag) without terminating the session violates the contract that RED is the anchor; skipping a phase in conversation is the human's call, and the human accepts the consequence.

The design co-evolves with model tiering. Contributors who configure `[models]` such that `red` and `green` route to different providers accidentally terminate the session between phases, and the failure mode is silent — the next phase starts cold and the loss is invisible until a later phase depends on the cached reasoning. The tiering reference is therefore not a separate page; it is one of two dials whose coincidence determines whether a micro-task benefits from continuity or pays for it twice.

## See Also

- [Tutorial: Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — see session continuity in action across one full cycle.
- [How-To: Run /deviate-red](/how-to/tdd-micro-cycle/red) — the operator recipe that anchors `red_commit_sha` and opens the session.
- [Reference: Deviate Config Schema](/reference/config/deviate-config) — the `[models]` table whose tier routing must hold steady across the loop.
