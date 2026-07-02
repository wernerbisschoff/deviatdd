---
title: "Why Append-Only Ledgers"
description: "Why DeviaTDD records every state transition as a new JSONL line instead of mutating state in place — and what that protocol costs the system."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues:
  - ISS-001-002
prev: false
next: explanation/data-and-governance/sha-anchored-verification.md
---

Why does a CLI that runs TDD cycles need a write protocol at all? Because the Git Isolation Principle turns the ledger into the single shared memory across parallel feature branches, and shared mutable state across branches is the failure mode every distributed system eventually meets. DeviaTDD's answer is to refuse the mutation: every state transition is a new line appended to `specs/issues.jsonl` or `specs/**/tasks.jsonl`, and the canonical state is the *projection* of all lines onto the present.

## Context

The macro layer decomposes a feature into issues; the meso layer decomposes an issue into tasks; the micro layer runs each task through a phase machine. Every one of these transitions is a fact the system needs to remember, and the same fact may be reached from multiple concurrent branches (two workers creating different issues from the same epic, two phases claiming the same task in a clean worktree, two agents appending to a shared ledger from parallel `git worktree` directories). The traditional fix — a central database with row-level locks — would solve the problem and break DeviaTDD's "no persistent database runtime" clause (`specs/constitution.md` §2). The append-only ledger is the no-database answer: writes are commutative, reads are sequential, and the system never has to lock.

The protocol is two lines long in the constitution. "All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing." That last clause is the load-bearing one — it means the protocol is not just "don't edit by hand" but "the system derives state by walking the file forward." If a record lies, the system does not correct it; the system appends a corrective transition and lets the parser pick the latest fact.

## Rationale

The decision is to treat the ledger as an event log, not a state table. The CLI is the only writer (`src/deviate/core/issues.py::append_issue_record` and `src/deviate/cli/micro.py::append_task_transition` are the canonical entry points); agents and contributors never edit the file directly. Every transition is guarded by a compound idempotency key — `(id, status)` for tasks, `(issue_id, status)` for issues — so the same transition recorded twice dedupes on read. The Pydantic `IssueRecord` and `TaskRecord` models in `src/deviate/state/ledger.py` enforce the schema on each new line, which means a malformed append is rejected at write time rather than poisoning downstream state derivation. Cross-branch concurrency is handled by `.gitattributes` declaring `merge=union` for both ledgers, so two branches appending the same file at merge time get *both* sets of new lines (line-level union, not block-level three-way merge) and the parser picks the consistent projection.

## Mental Model

Picture the ledger as a journal where every entry is dated and immutable. The system's view of "what is task T001-01 doing right now?" is the answer to "what is the *latest* entry mentioning T001-01?"

```
specs/issues.jsonl  (events)         derived state
┌──────────────────────────┐         ┌──────────────────┐
│ ISS-001-002  REGISTERED  │ ──▶     │ ISS-001-002:     │
│ ISS-001-002  IN_PROGRESS │         │   status=COMPLETE│
│ ISS-001-002  COMPLETED   │         │   ts=2026-06-07  │
│ T001-01      PENDING     │         └──────────────────┘
│ T001-01      RED         │         (parse → walk →   │
│ T001-01      GREEN       │          last-write-wins) │
└──────────────────────────┘
```

The journal grows forever; the projection is cheap because the parser only needs the *last* transition per entity.

## Trade-Offs

We rejected three alternatives before settling on the append-only protocol.

- **Mutable JSON state files** — the natural shape for a CLI that needs to remember "what's the status?" Rejected because mutable files do not survive two feature branches both creating issues: one branch's `git checkout` clobbers the other's, and a manual merge step becomes a corruption vector. Mutable state also makes the audit trail a lie (the system can no longer answer "when did this change?" because the change is overwritten).
- **SQLite database with row locks** — the distributed-systems-correct answer. Rejected because DeviaTDD's tech stack is "no persistent database runtime" (`specs/constitution.md` §2), a SQLite file would still be a binary blob subject to the same branch-merge corruption, and contributors would need a SQL tool to inspect canonical state. The ledger is a plain text file readable in `cat`.
- **Per-branch state with merge-time conflict resolution** — give each branch its own ledger file and reconcile at merge. Rejected because canonical state would be ambiguous (which branch is the source of truth?) and because the reconciliation step would have to re-implement the same sequential-parse logic that the append-only protocol already encodes.

The cost we accept: canonical-state derivation reads the whole file. At DeviaTDD's per-issue scale (hundreds of records per epic) the parse is sub-10ms; at a million-record scale the protocol would need an index. The system also refuses in-place correction — a misrecorded transition can only be fixed by appending a *new* transition that supersedes it, and tooling must be able to replay the history to spot retracted facts. We accept that the discipline is a contributor cost; we gain a protocol that survives any branch topology without coordination.

## Implications

The append-only protocol is what makes the Green → Judge → Green loop (`specs/DeviaTDD-architecture.md` §2.3) auditable: when `_execute_rollback()` runs `git reset --hard <red_sha>`, the ledger still records the GREEN attempt, the JUDGE violation, the rollback snapshot, and the next GREEN — the *system* is rolled back, the *history* is preserved. It is also what makes HITL Gate 3 (Final Merge Audit) tractable: the human reviews a journal of events, not a current state they must reconstruct. v0.4.0 of the constitution added the `merge=union` rule precisely because the protocol was correct but unmergeable — once concurrent branches could append without conflict, the append-only choice stopped costing branch-management overhead and started paying for itself.

The protocol's sharpest edge is the assumption that appends are *commutative*: `A then B` must equal `B then A` under projection. That holds as long as two branches never both transition the same `(id, status)` pair, which is exactly what the compound idempotency key guarantees. It is also why the CLI — not the agent — is the only writer: a free-form edit can break commutativity in ways the parser cannot detect.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — see the ledger receive its first `PENDING` and end in `COMPLETED`.
- [How-To → Issue Execution → Run Tasks](/how-to/issue-execution/execute) — the operator recipe that drives the task ledger through RED/GREEN/JUDGE.
- [Reference → State & Ledger → Issues JSONL Schema](/reference/state-and-ledger/issues-jsonl) — the `IssueRecord` schema, idempotency keys, and the `append_issue_record()` helper.
