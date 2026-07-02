---
title: "Why Git Isolation"
description: "Why every DeviaTDD task runs in its own worktree, why micro-layer agents never branch, and how a stripped subprocess environment keeps the agent out of the operator's way."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: false
next: false
---

DeviaTDD's micro-cycle (red → green → yellow? → judge → refactor) is a small, fast, deterministic state machine. The operator's environment is the opposite: long-lived, multi-branch, full of in-flight work. Running the agent on the same checkout the operator is sitting on — same working tree, same `HEAD`, same `GIT_AUTHOR_*` — is the failure mode the **Git Isolation Principle** is built to prevent. The principle is short ("every task runs in its own worktree; micro-layer agents never run branch-mutating git commands") but the design that enforces it is the difference between a TDD loop that compounds cleanly across an epic and one that silently corrupts its own history.

## Context

Most agentic TDD tools run their loop on whatever checkout the operator happens to be holding. That feels ergonomic — the agent is right there, the operator can watch — and it produces the same failure mode every time: a long-running agent mutates a branch the operator was reserving for unrelated work, drops commits where they do not belong, and leaves behind a working tree that no longer matches the ledger that records it. The agent's job (mutate the codebase to satisfy one test) and the operator's job (curate many parallel branches across many issues) need the same filesystem but they do not need the same *branch*.

The constitution makes the separation explicit. `src/deviate/core/_shared.py::git_env` strips every `GIT_*` and `GH_*` variable from the subprocess environment before any CLI call runs `git`, so child processes cannot read the operator's git identity, remotes, or auth state. `src/deviate/cli/feature.py::_create_feature_branch` is the *only* sanctioned entry point for branch creation, and it deliberately uses `git branch <name>` (which writes a ref) rather than `git checkout -b` (which switches the working tree). The asymmetry is the design: feature branches are created as refs; the working tree stays where the operator put it.

## Rationale

The decision is to treat the worktree as a per-task execution sandbox and to make every branch mutation go through a single audited helper. Tests demonstrate the contract: `tests/conftest.py::_git_env` strips the same environment variables for the test runtime, and the `tmp_git_repo` fixture insists that every test git call passes both `cwd=<tmp_git_repo>` and `env=_git_env()`. Production and test environments converge on the same rule: the git subprocess sees a world that contains only what the test or the operation gave it. That rule is what lets a micro-layer agent run hundreds of cycles across an epic without ever touching the operator's `HEAD`.

The second decision is that branch creation is a CLI command, never an agent action. An agent running a red step is a *consumer* of a branch, not its creator; if the branch does not exist, the agent fails fast with a recoverable error rather than mutating state to fix its own setup. The CLI's job is to provision the worktree (`deviate feature start <ISS-NNN>`) from a SHA the ledger has anchored, and the agent's job is to land commits on the branch it is given. The agent cannot create the branch because doing so would let it decide *which base commit* to branch from — and that decision belongs to the ledger, not the agent.

## Mental Model

Picture the repository as a tree of worktrees, one per active issue, each rooted at a SHA the ledger has frozen. The agent runs inside a leaf it does not own; the CLI owns the topology.

```
operator's main checkout              issue worktrees (one per ISS-NNN)
┌────────────────────────────┐        ┌──────────────────────────────┐
│  main                      │        │ .worktrees/ISS-042/          │
│   └─ feature/ISS-007 ──────┼───────►│   branch: feature/ISS-042    │
│                            │        │   HEAD = ledger-anchored SHA │
│  (operator curates this)   │        │   (agent runs red→green here)│
└────────────────────────────┘        └──────────────────────────────┘
        ▲                                         │
        │ ledger-anchored base SHA                │ every git/gh subprocess
        │                                         │ runs with env=git_env()
        └─────────────────────────────────────────┘
```

The arrow from main to the worktree is `deviate feature start`, which reads the ledger's `anchored_sha` and runs `git worktree add` from there. The arrow back is `gt submit --stack` or a normal push — the agent never performs that arrow directly; the operator or the CLI does.

## Trade-Offs

Two alternatives were considered and rejected.

A **shared-checkout agent** — let the agent run on whatever branch the operator is sitting on — was rejected because every concurrent task becomes a fight for `HEAD`. Two agents cannot share a working tree without lock-step coordination; one agent's `git checkout` clobbers the other's edits, and the ledger that records "task T001-01 is green" lies because the commit it points to is no longer reachable from the operator's view. The isolation cost (one worktree per task) is paid for by the elimination of `HEAD` contention.

A **branch-mutating micro-agent** — let the agent create its own branch on demand — was rejected because the agent would then control its own base commit, and the ledger's "anchored at SHA X" guarantee becomes advisory. The append-only ledger protocol depends on branches being created at SHAs the system has *already decided*; if the agent can re-decide that SHA mid-loop, the ledger's invariants collapse. Centralising branch creation in `_create_feature_branch` keeps the SHA decision in code the ledger audits, not in code the agent can override.

The cost we accept is ceremony: every task requires `deviate feature start` before the micro-cycle can run, and a developer who skipped that step hits a recoverable failure instead of a silent success. We accept that ceremony because the silent-success failure mode is the one the Append-Only Ledger and Doc Rot defences both exist to catch.

## Implications

What becomes easier: a task loop is reproducible by replaying its ledger entries on a fresh worktree from the same anchored SHA, which is what makes `gt submit --stack` and the final merge audit tractable. The agent's environment is a hermetic leaf — no inherited `GIT_*`, no inherited remotes, no inherited auth — so the same micro-cycle produces the same commit graph on a contributor's laptop and in CI. What becomes harder: cross-worktree operations (rebasing, cherry-picking, stack submission) must be orchestrated by the operator or the CLI, never by the agent; and a developer who runs `git checkout -b` directly inside a worktree re-introduces the very coupling the principle forbids. The contract "micro-layer agents must never run branch-mutating git commands" is the load-bearing rule that keeps the ledger trustworthy.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — the cycle that opens its worktree via `deviate feature start` and runs red→green on it.
- [How-To → Recovery → Hotfix](/how-to/recovery/hotfix) — the recovery flow that refuses to interleave with an active micro-cycle.
- [Reference → CLI Index](/reference/cli/index) — the `deviate feature` subcommand table, the sanctioned entry point for branch creation.