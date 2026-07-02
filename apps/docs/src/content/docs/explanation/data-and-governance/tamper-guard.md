---
title: "Why the Tamper Guard"
description: "Why DeviaTDD auto-restores unauthorized edits to tests/, specs/, and .deviate/ during the GREEN and YELLOW phases — and what that procedural checkpoint costs the cycle."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues:
  - ISS-001-004
  - ISS-002-005
prev: apps/docs/src/content/docs/explanation/data-and-governance/sha-anchored-verification.md
next: false
---

Why does the micro layer refuse to trust the GREEN agent's working tree even when its tests pass? Because an LLM agent that wrote a passing test can also amend a passing test, falsify a failing one, or quietly rewrite the spec the next phase is going to validate against. A green CI badge is not a guarantee that the *contract* the agent committed to is the contract the human signed off on; it is only a guarantee that the files pytest happens to read at this moment produce exit code 0. The Tamper Guard closes the gap between "the test passes" and "the contract is intact" by treating any modification to `tests/`, `specs/`, or `.deviate/` during a non-RED phase as presumptive evidence of compromise — and reverting the file before the cycle can advance.

## Context

The micro layer (`src/deviate/cli/micro.py`) wraps an LLM-driven TDD cycle around a git worktree: RED writes a failing test, GREEN writes the minimum implementation, JUDGE reviews the diff against `spec.md`, and REFACTOR polishes. Every phase except RED is, in principle, *adversarial* — the agent is asked to solve a problem without being trusted to redefine it. The constitution (`specs/constitution.md` §1) makes this explicit: "Micro-layer LLM execution … is strictly sandboxed: it is granted write access **only** to files matching `src/**/*.py`." The filesystem sandbox the LLM backend offers is the first line of defence; the Tamper Guard (`src/deviate/core/tamper.py`) is the second, and the only one the system fully controls. It runs `git diff --name-only` against the worktree, classifies each changed file by its first path part, and dispatches `git restore` on anything outside the allowlist. Because git is the substrate that records the cycle's commitments, the guard uses git's own bookkeeping to decide what to roll back — no parallel state model, no chance for the two to disagree.

The guard is invoked at three points: never during `RED_TEST_CREATION` (the agent must be allowed to write tests there), always during `GREEN_IMPLEMENTATION` (the agent must not touch the contract), and again during `YELLOW_AMENDMENT` (the second look arrives after a GREEN-attempted edit has been approved by the human). Each invocation sees the same allowlist — files whose first path part is `tests`, `specs`, or contains `.deviate` — and each returns one of two verdicts: `TAMPER_PASS` or `TAMPER_DETECTED`. The verdict is the *only* signal the rest of the system reads; the agent never gets to argue about whether its edit "really" changed the contract.

## Rationale

The decision is to make the guard a procedural checkpoint, not a model-level filter. Two predicates do the work: `_is_test_file`, `_is_spec_file`, and `_is_config_file` map a filepath to a boolean by inspecting its first path part, and `_is_protected` short-circuits to `False` when the context is `RED_TEST_CREATION`. That short-circuit is the only context-sensitive rule; everything else is a directory-prefix test, deliberately. A pure-path predicate survives any agent that learns to disguise its edits through filename tricks but cannot disguise its parent directory. The guard also strips `GIT_*` from the environment before invoking `git diff`, so the agent cannot poison the diff by writing to `GIT_DIR` or `GIT_INDEX_FILE` — the subprocess sees exactly what a clean check-out would see.

The verdict is the unit of policy. `TAMPER_PASS` means "proceed; commit what you have"; `TAMPER_DETECTED` means "I have restored the protected files; you may now run YELLOW." There is no third state and no override path. If the agent believes its edit was legitimate, the cycle routes it through `/deviate-yellow` (`src/deviate/prompts/commands/deviate-yellow.md`), where a human — and only a human — sees the diff, decides whether to keep it, and either re-runs GREEN (`--rejected`) or advances to JUDGE (`--approved`). The guard never gives the agent a way to talk itself out of the verdict, because the failure mode the guard exists to prevent is precisely the agent rationalising a falsified contract.

## Mental Model

Picture the guard as a customs checkpoint between the LLM's working tree and git's commit log. Every file the agent wants to ship into history has to pass through it; the customs officer knows three forbidden categories (test files, spec files, project configuration) and one allowed category (production source). The officer cannot read the content of the luggage — the predicate is purely on the label, the directory prefix — which is intentional: content-aware inspection would let a well-crafted edit slip through, and a directory-prefix test never does.

```
GREEN agent finishes ─▶ git diff --name-only ─▶ per-file predicate
│                      │
│   tests/specs/.deviate/ → git restore (TAMPER_DETECTED)
│   src/                  → keep           (TAMPER_PASS)
▼
TAMPER_DETECTED     TAMPER_PASS
│                  │
▼                  ▼
YELLOW phase       commit + JUDGE
```

The guard is silent by design. When the verdict is `TAMPER_PASS`, no message is logged, no hook fires, and the cycle proceeds exactly as if the guard did not exist — the only way to tell the guard ran at all is by reading the ledger, which records `TAMPER_DETECTED` as the YELLOW trigger. Silence is the property: the happy path is silent, the unhappy path is loud, and the operator learns to read the ledger for the one signal the guard ever emits.

## Trade-Offs

Three alternatives were considered before the guard took its current shape. A **content-aware classifier** — read each modified file, hash its semantics, and decide whether the change really altered the contract — was rejected because it is exactly the work the agent is being trusted to do anyway, and the trust is what the guard exists to revoke. A small textual edit can rewrite a test in a way the diff sees as a single line and a content classifier sees as a contract change; a directory-prefix predicate sees both as "this is in `tests/`" and reverts both. The cost we accept is false positives — a legitimate rename of `tests/test_foo.py` to `tests/test_bar.py` is reverted the same as a malicious rewrite — but the cost of a false negative is a falsified contract, and the constitution ranks that cost infinitely higher.

A **model-side sandbox only** — rely on the LLM backend (Aider, Claude Code, opencode) to enforce the `src/**/*.py` allowlist at the tool layer — was rejected because the backend is replaceable. DeviaTDD treats the backend as a black-box subprocess (`specs/DeviaTDD-api.md` §3), and the design's central claim is that no agent runtime is trustworthy enough to be the only enforcement. The guard is the wrapper-level safety net; it is the part of the system that survives a future migration to a backend that does not yet exist, and that is why Pi — which has no built-in permission system — still runs the same Tamper Guard on every GREEN invocation (`specs/adhoc/009-pi-agent-backend-integration/spec.md` §9.1.6).

An **advisory-only guard** — emit a warning, log to `.deviate/`, and trust the operator to read the log — was rejected because advisory enforcement is no enforcement at all. A warning the system can ignore is a permission slip, and a permission slip is the entire class of bug the guard exists to prevent. The verdict has to be procedurally binding; the only question worth asking is whether the binding is reversible, and the answer is yes — via `/deviate-yellow`, with a human in the loop.

## Implications

The guard changes what GREEN means. A GREEN commit is no longer "the agent's last diff was accepted"; it is "the agent's last diff, after the guard stripped every protected-path mutation, was accepted." That distinction is load-bearing for `/deviate-judge`: the JUDGE phase runs its compliance check on the diff the guard produced, not the diff the agent emitted, and the two are equivalent only because the guard restored the latter into the former. It is also what makes HITL Gate 3 (Final Merge Audit) tractable: the human reviewing the PR sees a diff in which every `tests/` line came from the RED commit, every `specs/` line came from the human's contract sign-off, and every `.deviate/` line came from `deviate init` — the guard has filtered out the noise that would otherwise make the review unreviewable. The guard also constrains future protocol designs: any new workflow that wants to let the agent write tests outside RED (a REFACTOR phase that rewrites test helpers, a documentation phase that adds examples to `specs/`) has to declare its own `TamperContext` and its own predicate path, because `_is_protected` short-circuits on `RED_TEST_CREATION` only. That constraint is the price of the procedural-binding design: new flows are not free, they are gated on declaring what they are allowed to mutate, and the gate is the same gate that protects the rest of the cycle.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — observe the guard emit `TAMPER_DETECTED` when an over-eager GREEN agent edits a fixture
- [How-To → Run /deviate-yellow](/how-to/tdd-micro-cycle/yellow) — the operator recipe that takes a `TAMPER_DETECTED` verdict and decides whether the amendment survives
- [Reference → CLI index](/reference/cli/index) — the `deviate green post` and `deviate yellow post` entries that wire the guard into the cycle body