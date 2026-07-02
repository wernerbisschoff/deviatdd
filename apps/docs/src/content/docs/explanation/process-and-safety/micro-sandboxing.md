---
title: "Why the Micro Layer Resets Tests"
description: "Why the Micro sandbox is enforced at the git tree (Tamper Guard + tests/ reset) rather than at the OS layer — and what that choice costs the system."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: explanation/process-and-safety/git-isolation.md
next: explanation/process-and-safety/session-continuity.md
---

The Micro layer is where DeviaTDD lets a model run code. That is also where an LLM agent — operating in long, unsupervised loops on real production code — is most likely to drift: softening a failing assertion, enlarging the scope of the change it was dispatched to make, or quietly rewriting its own contract. The Micro sandbox is the set of mechanisms that constrain what an agent is allowed to do during a single RED/GREEN/YELLOW/JUDGE/REFACTOR cycle. The question worth sitting with is: what is the right shape of that constraint?

## Context

The Micro layer's core risk is not that the agent writes bad code — any cycle can be retried — but that the agent mutates the contract it is being measured against. A TDD loop has three actors: the test that defines acceptance, the implementation that satisfies it, and the judge that decides whether the implementation is correct. If any of the three can rewrite either of the others, the loop becomes circular: the agent passes its own test by softening the assertion, or "fixes" the verifier by patching it out. The traditional answer — a kernel-level sandbox, a container, a restricted shell — prevents general harm but not the specific harm that defeats TDD.

DeviaTDD's answer is that the sandbox is not a process isolation boundary but a content boundary enforced at git's ledger. `specs/DeviaTDD-architecture.md` §2.3 calls the Micro layer "the automated sandbox" but the mechanism is `git diff --name-only` followed by `git restore <path>` on any unauthorized modification, not a container runtime. The architecture is explicit (architecture §2.3) that this is a deliberate trade-off: passive detection and roll-forward rejection, not active prevention.

## Rationale

The Tamper Guard sits at the boundary between the agent's session and the durable state of the working tree. Each phase entry calls `TamperGuard.evaluate(context, repo_path, approved_mods)`, which strips `GIT_*` environment variables (so the subprocess cannot lie about which commit is HEAD), enumerates the files the agent has touched, and classifies each one against the context's protected set.

In `RED_TEST_CREATION` nothing is protected — RED is the only phase that may legitimately create or modify `tests/`. In every other phase, three prefixes are protected: `tests/` (the agent cannot soften its own test), `specs/` (the agent cannot rewrite its own contract), and `.deviate/` (the agent cannot lower its own constraints by editing config). Any protected path the agent modified is reverted via `git restore`, and a `TAMPER_DETECTED` verdict is returned. The architecture maps that verdict to a phase transition: GREEN → YELLOW (where the agent proposes a justified amendment) or, on a JUDGE violation, to the Green → Judge → Green loop where the suspect implementation is rolled back to the RED-boundary SHA recorded at the end of RED.

The principle is older than the tool: the *audited* boundary is the one that survives model upgrades, prompt-template changes, and the inevitable drift of an LLM's behavior over time. The same Tamper Guard catches an agent that has been told not to touch tests and an agent that has been told to touch tests but went one file too far — the *content* of the protected set is what changes between phases, the *mechanism* does not.

## Mental Model

Picture the working tree as the agent's workshop, and the Tamper Guard as the night-shift custodian who walks the floor at every phase boundary. The custodian does not lock the doors — the agent is free to take any tool off any shelf — but at the end of every shift the custodian walks the floor and puts back anything that landed in the wrong room. The rooms are defined by their *content*, not their location: `tests/` is private during GREEN and shared during RED, `specs/` is read-only in every Micro phase, `.deviate/` is read-only in every Micro phase.

```
                ┌─────────────────────────────────┐
   RED:         │   tests/  (write)               │   agent writes
                │   src/     (no)                 │   only here
                ├─────────────────────────────────┤
   GREEN:       │   tests/  (PROTECTED  ↻ restore)│   agent writes
                │   specs/  (PROTECTED  ↻ restore)│   only to src/
                │   .deviate/(PROTECTED  ↻ restore)│
                ├─────────────────────────────────┤
   YELLOW?:     │   same as GREEN + propose       │   amendment
                │   amendment block               │   request
                └─────────────────────────────────┘
                    ▲
                    │ TamperGuard.evaluate(context)
                    │ strips GIT_* env, diffs tree,
                    │ restores any protected path
```

The "?" after YELLOW matters: the YELLOW phase is conditional. The Tamper Guard only routes the agent there when it has *already* violated the boundary. A well-behaved agent never enters YELLOW; the phase exists for the agent that misbehaves and is given one structured chance to propose a justified amendment rather than be silently rolled back.

## Trade-Offs

A kernel-level sandbox — `bwrap`, `landlock`, a Docker container with `tests/` mounted read-only — would make the protected set unenforceable at the filesystem layer: the agent could not modify a file it cannot see. We rejected that shape because it would force every contributor onto a specific kernel or container runtime, and it would prevent useful cross-boundary work like reading the test file while writing the implementation. The Tamper Guard instead puts the boundary at the git tree, which is the same boundary the rest of the system already trusts, and accepts that for the few seconds between an agent's write and the Tamper Guard's restore, the file on disk may briefly be wrong.

A permissive sandbox — let the agent edit any file and rely on JUDGE to catch bad changes — was rejected because the verifier and the test are not interchangeable protections. JUDGE evaluates functional compliance against `spec.md`; it does not evaluate "did the agent soften its own assertion?" or "did the agent rewrite the spec?" Those checks belong in the Tamper Guard because they are the checks that keep TDD from collapsing into "the agent passes whatever it wants."

A blocklist-of-paths sandbox was rejected because it scales with the codebase, not with the role of the agent. The Tamper Guard's protected set is derived from the *phase context*, not from a list of filenames: the same `tests/` directory is writable in RED and read-only in GREEN, and the rule that derives the protected set is six lines long.

## Implications

The Micro sandbox is what makes the rest of the architecture's invariants provable. The append-only ledger gains its "no agent can rewrite its own past" property because the Tamper Guard reverts unauthorized spec edits before they reach the parser. HITL Gate 3 (final merge audit) can trust the diff because the diff is constrained to be a green implementation against an unchanged red test. Session continuity — RED → GREEN → REFACTOR in a single LLM session — is safe because the session's view of the tree is the same as the operator's view.

What becomes easier: contributors can write prompts that assume the agent is well-behaved only *most of the time*. The prompt does not have to enumerate every file the agent might touch; the Tamper Guard catches the cases the prompt missed. What becomes harder: adding a new protected path (e.g., a `fixtures/` directory that should be read-only during GREEN) is a one-line change with global consequences — it changes both `TamperGuard._is_protected()` and the rollback procedure, and it must be reasoned about across every phase.

The sharpest edge is the gap between write and detect. Between the moment an agent edits a protected file and the moment the Tamper Guard restores it, the file is briefly wrong on disk. DeviaTDD accepts this race because the window is sub-second and because the append-only ledger's projection is what downstream phases read, not the working tree. The audit is the contract; the working tree is the cache.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — see the Tamper Guard fire (or stay quiet) across RED and GREEN.
- [How-To → Micro-Cycle: GREEN](/how-to/tdd-micro-cycle/green) — the recipe that invokes `TamperGuard.evaluate(GREEN_IMPLEMENTATION)` on every entry.
- [How-To → Micro-Cycle: YELLOW](/how-to/tdd-micro-cycle/yellow) — the amendment path that the guard routes to on `TAMPER_DETECTED`.
- [Reference → Config Schema](/reference/config/deviate-config) — the `[phases]` configuration that names the protected-set derivation rule.