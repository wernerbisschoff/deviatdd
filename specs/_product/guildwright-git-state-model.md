# Guildwright Git-Backed State Model

Related documents: [rewrite index](guildwright-rewrite.md), [current-system catalog](guildwright-current-system.md), [Rust TUI requirements](guildwright-rust-tui-requirements.md), and [gap register](guildwright-gap-register.md).

## 1. Central Invariant

Guildwright treats the Git commit graph as the durable workflow clock.

For any checked-out commit $C$:

```text
WorkflowState(C) = reduce(tracked ledgers at C, tracked artifacts at C, branch identity)
```

A checkout or revert that changes tracked inputs must change derived workflow state. No gitignored session file can override that result.

## 2. State Categories

### Durable state

Durable state is tracked by Git:

- `specs/issues.jsonl`
- `specs/**/tasks.jsonl`
- `specs/_product/flows.jsonl`
- Product, Macro, Meso, and Micro artifacts
- Source and tests
- Configuration intended to affect reproducible behavior

### Derived state

Derived state is recalculated:

- Current issue from the branch and issue ledger
- Latest issue status
- Latest task status
- Runnable task queue
- Flow coverage and drift flags
- Current legal state-machine transitions
- Completion and release candidates

### Ephemeral state

Ephemeral state can be deleted without changing workflow truth:

- UI selection and layout
- Logs
- caches
- streaming buffers
- process IDs
- locks
- telemetry
- generated search indexes

## 3. Branch as Issue Claim

The canonical issue branch is:

```text
feat/<epic-or-bucket>/<issue-slug>
```

Resolution procedure:

1. Read the current branch.
2. Reject detached HEAD and non-feature branches for issue-scoped actions.
3. Parse bucket and issue slug.
4. Find a ledger record whose `source_file` ends with `specs/<bucket>/issues/<issue-slug>.md`.
5. Resolve the issue's canonical latest state.
6. Resolve the issue task ledger.
7. Limit all Meso, Micro, E2E, HTML, review, and walkthrough actions to that issue.

An explicit CLI issue argument can override branch discovery for read-only or claim setup operations. After a claim, branch identity wins over a stale runtime hint.

A remote branch is the distributed claim token. The first successful create-and-push wins. Local-only claims must display that they lack distributed exclusion.

## 4. Append-Only Ledgers

### Issue ledger

Each row contains a complete issue record or a transition that can be merged with its prior complete record. Current DeviaTDD makes COMPLETED terminal.

### Task ledger

Each task begins with PENDING. Phase results append RED, GREEN, JUDGE, REFACTOR, COMPLETED, or FAILED rows.

### Flow ledger

It contains flow identity and event rows. Events include discovered, documented, referenced by issue, confirmed implemented, and included in release.

### Reduction requirements

Every reducer must:

1. Read in file order.
2. validate every row;
3. preserve unknown future event types for forward compatibility;
4. report malformed rows instead of silently producing trusted state;
5. apply explicit terminal-state rules;
6. return provenance for each derived value;
7. remain deterministic for identical bytes.

### Idempotency

Writers use semantic event keys. A timestamp must not make an otherwise duplicate event unique.

Guildwright must define one idempotency key per event type.

## 5. Commit Transactions

A phase succeeds only when its artifact, ledger transition, and commit are one transaction.

```text
validate inputs
-> run phase
-> validate outputs
-> stage exact files
-> append ledger events
-> run required hooks
-> commit
-> publish success event
```

## 6. Revert Semantics

### Runner rollback

The TRAIN loop can discard an unaccepted local attempt with `git reset --hard <boundary>` and `git clean -fd`. This is safe only inside an isolated task branch with a captured recovery ref.

Runner rollback uses this strict order:

1. Verify the repository, branch, worktree isolation, and explicit boundary SHA.
2. Create a recovery ref for the current HEAD before destructive work.
3. Resolve the ref and verify that it points to the preserved commit.
4. Write ephemeral recovery metadata.
5. Reset tracked files and tracked ledger bytes to the boundary.
6. Run `git clean -fd` without `-x`, after the recovery ref is durable.
7. Reduce workflow state from the restored `HEAD`.
8. Emit a typed result with restore instructions.

- `revert_green` resets to the RED boundary.
- `revert_red` resets to the pre-RED boundary.
- EXECUTE resets to the pre-execute boundary.


### Operator revert

An operator uses `git revert <commit>` to undo accepted history while preserving the graph.

The revert commit must reverse code, artifacts, and ledger rows through normal Git patch semantics. After the revert, Guildwright recalculates state from `HEAD`.

Guildwright must never append a compensating state event merely because it saw a Git revert. Doing so would create state outside the reverted transaction.

## 7. Required Revert Property

For any commit $C_1$ and its revert commit $R$:

```text
tracked_state(HEAD after R) == tracked_state(parent of C_1)
```

The equality is semantic. Commit metadata and append order can differ, but derived issue, task, flow, and artifact state must match.

Guildwright must include property tests that generate event sequences, commit them, revert commits, and compare reduced state. Current failures are recorded in [Critical State Gaps](guildwright-gap-register.md#critical-state-gaps).

## 8. Session Model

Guildwright must not persist a mutable workflow phase as authority.

A runtime session can contain:

- schema version;
- repository and worktree identity;
- active process and agent session handles;
- pending input request;
- last rendered event offset;
- recovery reference under construction.

It must not override:

- active issue;
- task status;
- completed phase;
- ledger-derived queue;
- merge or release state.

On startup, resume works as follows:

1. Inspect repository and branch.
2. reduce all relevant tracked ledgers;
3. verify artifacts against derived transitions;
4. inspect worktree dirtiness;
5. inspect recovery refs;
6. classify the state as ready, resumable, conflicted, or corrupt;
7. offer only legal actions.

## 9. Recovery Evidence

Use one recovery namespace and one structured record:

```text
RecoveryRecord {
  issue_id,
  task_id,
  phase,
  attempt,
  kind: RunnerRollback | CommitFailure | InterruptedPhase,
  boundary_sha,
  preserved_head,
  recovery_ref,
  reason,
  created_at,
}
```

The record can be ephemeral because the Git ref preserves content. The TUI must show how to inspect, restore, or delete it.

## 10. Concurrency

- Use file locks for local ledger append transactions.
- Use atomic replace for ephemeral state files.
- Use remote branch creation for distributed issue claims.
- Refuse two live writers for the same worktree. A writer lease includes PID, process start identity, and heartbeat. Reclaim it only after verifying that the process is absent.
- Revalidate `HEAD`, index, branch, and reduced ledger state before every commit.
- Detect stale worktree metadata and provide repair commands.

Union merge drivers prevent text conflicts. They do not resolve semantic conflicts. Reducers must detect impossible transitions, duplicate identities, and conflicting claims.

## 11. Merge and Archive

Before squash merge, record the pre-squash tip independently of branch deletion. The record must survive remote UI merges and local cleanup.

Recommended representation:

- an archive tag or namespaced ref for the pre-squash tip;
- a Git note on the squash commit with issue ID and original tip;
- the COMPLETED issue event and flow confirmations in the squash commit.

Archive creation must not depend on `--delete-branch`.

## 12. Validation Errors

The reducer must distinguish:

- malformed JSON;
- schema mismatch;
- unknown event version;
- duplicate identity;
- duplicate transition;
- illegal transition;
- missing source artifact;
- branch-to-ledger mismatch;
- ledger-to-artifact mismatch;
- stale ephemeral session;
- interrupted commit transaction;
- orphan worktree;
- orphan recovery ref.

Each error must include evidence paths and safe next actions.

## Current Evidence

- `src/deviate/cli/_common.py::resolve_issue_id_from_branch`
- `src/deviate/state/ledger.py`
- `src/deviate/state/config.py::SessionState`
- `src/deviate/cli/meso.py::_try_claim_issue`
- `src/deviate/cli/micro.py::_execute_rollback`
- `src/deviate/cli/micro.py::_commit_phase_with_recovery`
- `specs/constitution.md` sections 1 and 5
