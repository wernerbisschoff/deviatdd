# Guildwright Rust TUI Requirements

## 1. Product Goal

Guildwright is a Rust TUI that executes the DeviaTDD method. It preserves contracts and improves state correctness, recovery, visibility, and project customization.

Related documents: [rewrite index](guildwright-rewrite.md), [current-system catalog](guildwright-current-system.md), [Git-backed state model](guildwright-git-state-model.md), and [gap register](guildwright-gap-register.md).

## 2. Architectural Boundaries

Use an Actions, Calculations, and Data split.

### Calculations

Pure code must implement:

- ledger parsing and reduction;
- state-machine transition validation;
- branch-name parsing;
- issue and task selection;
- prompt-layer resolution;
- contract validation;
- output-event reduction into a view model;
- recovery classification;
- flow coverage;
- exit-status selection.

These functions accept explicit values. They must not read files, Git, time, environment variables, or terminal state.

### Actions

Effect adapters perform:

- Git commands;
- filesystem reads and writes;
- process execution;
- agent RPC and CLI transport;
- terminal input and rendering;
- clocks and timers;
- locks;
- network push and pull;
- logging.

### Data

Versioned schemas define ledgers, artifacts, prompts, configuration, phase contracts, agent handovers, output events, and recovery records.

## 3. Suggested Crates

```text
guildwright-domain      Pure IDs, records, events, reducers, state machines
guildwright-git         Git repository, branch, worktree, commit, ref adapters
guildwright-ledger      JSONL codecs, locks, append transactions, validation
guildwright-prompt      Prompt discovery, layering, rendering, validation
guildwright-agent       Backend interface, CLI and RPC transports, manifests
guildwright-runner      Product, Macro, Meso, and Micro orchestration
guildwright-events      Typed event protocol and durable diagnostics
guildwright-tui         Ratatui view model, screens, keyboard input
guildwright-cli         Non-interactive and compatibility command surface
guildwright-config      Layered config and migrations
```

A workspace is optional. These are dependency boundaries, not a requirement for nine published packages.

`guildwright-events` owns event schemas and emission interfaces. TUI, JSONL, log, and CLI-text sinks subscribe through one-way dependencies.

## 4. State Machines

This section is the Rust implementation source for legal states and transitions. The [current-system catalog](guildwright-current-system.md) supplies current-flow evidence, not new states.

### Product

```text
NoProduct
-> FlowsDraft
-> FlowsApproved
-> ArchitectureDraft
-> ArchitectureApproved
-> ReleaseDraft
-> ReleaseApproved
```

The Product layer remains optional. Product approvals are conversational gates, not substitutes for Gate 1 or Gate 3.

### Macro

```text
Idle
-> Explore
-> Research
-> AwaitingDesignApproval
-> Prd
-> Shard
-> Idle
```

Each Macro phase returns `Succeeded`, `Failed`, `Interrupted`, or `NeedsHuman`. `Failed` remains at the committed phase for correction. `Interrupted` requires Git and artifact reconciliation before resume. `NeedsHuman` is legal at Gate 1 or typed contract drift. Automatic retry is allowed only for declared transient agent or transport errors.

| Phase result | Legal next action |
|---|---|
| Explore failed | Stay in Explore; correct or retry Explore. |
| Research failed | Stay in Research; correct or retry Research. |
| Research needs human | Enter AwaitingDesignApproval; approve, revise Research, or abandon. |
| PRD failed | Stay in PRD; correct or retry PRD. |
| Shard failed | Stay in Shard; correct or retry Shard. No issue rows append. |
| Any phase interrupted | Reconcile Git and artifacts; resume the same phase or restore its last committed predecessor. |

### Meso

```text
BACKLOG --claim transaction--> SPECIFIED --plan commit--> TASKS
TASKS --task registration--> IMPLEMENTING
IMPLEMENTING --all tasks complete--> AWAITING_GATE_3
AWAITING_GATE_3 --approved merge--> COMPLETED
```

BLOCKED is derived from unmet dependencies while durable status remains BACKLOG. A failed claim remains BACKLOG. Branch or worktree presence without a SPECIFIED row derives `ClaimInterrupted`; recovery completes or removes the partial claim. A Plan or Tasks failure remains SPECIFIED at the last valid commit. A terminal task failure remains IMPLEMENTING. There is no durable `ReadyForMicro` pause and no separate `Claimed` status. Merge evidence accompanies COMPLETED.

There is no Gate 2. This follows `specs/constitution.md` version 0.8.0 and section 1.

### Micro TDD

Use the [Micro state machine](guildwright-current-system.md#6-micro-layer). Encode JUDGE next actions as a Rust enum. Do not dispatch on strings.

DIRECT and E2E use separate smaller state machines. Do not add sentinel states to the TDD enum.

## 5. TUI Screens

### Home

Show repository, branch, resolved issue, claim health, current release, blocked work, and safe next action. Claim health is `Unclaimed`, `LocalOnly`, `RemoteClaimed`, `Stale`, or `Conflicted`, derived from the ledger, local branch, remote branch, and worktree.

### Product

Show flows, architecture links, release inclusion, implementation confirmation, and drift flags.

### Macro

Show phase timeline, artifacts, Gate 1 status, validation errors, and resume action.

### Issue

Show issue intent, dependencies, branch claim, Plan contract coverage, tasks, worktree, and PR state.

### Task Runner

Show task queue, current phase, attempts, test output, agent output, JUDGE rationale, changed files, and recovery boundary.

### Diff and Judge

Show Plan scenarios, diff hunks, security profile, flow references, verdict, next action, and evidence.

### Logs and Recovery

Show structured events, raw subprocess output, recovery refs, interrupted transactions, and safe recovery actions.

### Prompt Studio

Show effective prompt layers, source paths, diffs from defaults, unresolved variables, size, and a rendered preview.

## 6. Typed Output Protocol

Every operation emits typed events before presentation.

Minimum event groups:

- repository and claim events;
- phase lifecycle events;
- artifact validation events;
- ledger append events;
- Git transaction events;
- agent stream and handover events;
- test command events;
- JUDGE decision events;
- recovery events;
- HITL request and decision events;
- pipeline completion events.

Each event has schema version, timestamp, run ID, repository ID, optional issue ID, optional task ID, severity, and payload.

The TUI, JSONL mode, logs, and CLI text all consume the same event stream. Human-readable text is never parsed to drive behavior.

Port precondition: define typed equivalents for current Rich-only recovery instructions, warnings, gate summaries, and rationale. The Rust renderer must not re-derive these contracts from text logs.

## 7. Prompt Customization

Guildwright must support project-specific prompt changes without editing installed package files.

### Layers

Use this precedence, lowest to highest:

1. Built-in Guildwright core prompt.
2. Built-in layer prompt.
3. Built-in phase prompt.
4. Tracked project core additions under `.guildwright/prompts/core/`.
5. Tracked project layer additions under `.guildwright/prompts/layers/`.
6. Tracked project phase override under `.guildwright/prompts/phases/`.
7. Optional user-global additions under the user config directory.
8. Explicit one-run prompt additions from CLI or TUI.
9. Runtime contract data.

Project layers must override user-global layers for reproducible team behavior. One-run additions must be visible and recorded in run diagnostics.

### Modes

Each override declares one mode:

- `append`: add instructions after the built-in section;
- `prepend`: add before the built-in section;
- `replace`: replace one named section;
- `disable`: disable one optional named section.

Do not permit unconstrained full-prompt replacement by default. Governance, safety boundaries, manifest schema, and HITL requirements are protected sections.

### Prompt lock

A run records:

- effective prompt digest;
- each layer path and digest;
- template version;
- rendered size;
- protected-section validation result.

This makes agent behavior reproducible and reviewable.

### Project overlay contract

Consumer projects MUST maintain tracked prompt overlays under `.guildwright/prompts/{core,layers,phases}/` with the precedence and modes defined above.
## 8. Configuration

Use `.guildwright/config.toml` for tracked project behavior. Keep machine-local values in the platform config directory.

Configuration groups:

- repository and default branch;
- issue branch pattern;
- agent backends and transports;
- phase models;
- execution profiles;
- test, lint, format, type, and E2E commands;
- timeouts and retry limits;
- allowed write scopes;
- prompt layers;
- Graphite and remote claim behavior;
- output and logging;
- TUI preferences;
- security policy.

Print the effective configuration with provenance for every value.

## 9. Runner Requirements

- Run phases in process where safe.
- Run external commands without a shell by default.
- Validate configured commands against explicit policy.
- Kill the full process group on timeout.
- preserve partial stdout and stderr;
- support backpressure on agent streams;
- detect stalls separately from total timeout;
- use bounded prompts and output buffers;
- persist structured logs incrementally;
- resume after process interruption;
- halt on first terminal failure by default;
- allow an explicit continue-on-failure queue policy;
- revalidate Git state before every write transaction.

## 10. Agent Interface

Define one async backend trait with capabilities:

- one-shot invocation;
- continuous session;
- isolated session;
- streaming output;
- structured handover;
- model selection;
- cancellation;
- timeout;
- tool capability declaration.

RED, GREEN, and REFACTOR share a task session when the backend supports it. JUDGE always uses an isolated session.

## 11. HITL

Guildwright enforces:

- Gate 1 after Research and before PRD;
- Gate 3 after Micro and before final merge.

It must not implement Gate 2. `specs/constitution.md` version 0.8.0 explicitly removed that gate.

Every HITL request is a typed event with context, options, recommendation, decision, actor, and evidence digest. A non-interactive run fails closed when a mandatory decision is unavailable.

## 12. Security

- No shell interpolation for Git or test commands.
- Treat repository content and agent output as untrusted.
- Validate paths remain inside allowed roots.
- reject symlink escapes;
- redact configured secrets from output and logs;
- never copy `.env` by default;
- expose an explicit project policy for environment forwarding;
- require confirmation for branch deletion, worktree deletion, destructive reset, and force operations;
- never bypass hooks unless the repository policy explicitly declares a safe internal phase commit exception.

## 13. Performance

Preserve current targets unless benchmarks justify a change:

- setup under 500 ms without agent invocation;
- prompt export under 200 ms per agent;
- responsive TUI input during streaming work;
- bounded event memory;
- incremental ledger reduction;
- no repeated full-repository scan for each frame.

## 14. Compatibility and Migration

Guildwright must import current DeviaTDD repositories without rewriting ledgers.

Migration steps:

1. Detect `.deviate/` and existing specs.
2. Validate all ledgers and artifacts.
3. Map current config into Guildwright config.
4. Ignore legacy `.tdd-session.json` if present. Current workflow state comes from tracked Git data, not either legacy session file.
5. Derive state from Git rather than import `.deviate/session.json` phase data.
6. install Guildwright prompt launchers without deleting DeviaTDD copies;
7. provide a dry-run report;
8. require explicit cutover;
9. preserve old commands during a bounded compatibility period only if requested.

Do not rename tracked `specs/` artifacts merely to match the new product name.

## 15. Verification

Required verification includes:

- reducer unit and property tests;
- commit/revert state-equivalence tests;
- branch claim race tests;
- worktree interruption tests;
- prompt precedence and protected-section tests;
- state-machine model tests;
- malformed and forward-version ledger tests;
- timeout and process-tree tests;
- backend contract tests;
- golden event-schema tests;
- TUI view-model tests;
- real smoke runs against a disposable Git repository.
