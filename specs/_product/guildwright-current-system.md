# Guildwright Current-System Flow Catalog

## Purpose

This document records the DeviaTDD behavior that Guildwright must preserve unless the gap register approves a change.

Related documents: [rewrite index](guildwright-rewrite.md), [Git-backed state model](guildwright-git-state-model.md), [Rust TUI requirements](guildwright-rust-tui-requirements.md), and [gap register](guildwright-gap-register.md).

## 1. Bootstrap and Setup

### `deviate setup`

1. Detect or accept the selected agent backend.
2. Create `.deviate/config.toml`, `.deviate/session.json`, `.deviate/.gitignore`, and runtime directories.
3. Link `CLAUDE.md` and `AGENTS.md` to one governance source when possible.
4. Install commands into `.claude/commands`, `.opencode/commands`, `.factory/commands`, `.pi/prompts`, and `.omp/prompts`.
5. Install the `deviatdd` skill into each agent skill directory.
6. Add root `.gitignore` rules for installed command and skill copies.
7. Add `.gitattributes` union-merge rules for all JSONL ledgers.
8. Save the selected backend in `[agent].backend`.

Setup does not create `specs/constitution.md`. A greenfield project remains greenfield until Research.

`deviate init pre/post` is a separate pre/post scaffold path. Existing documentation sometimes treats it as equivalent to setup. Guildwright must not preserve that ambiguity.

### Configuration

Current configuration includes the agent backend, execution profile, timeout, Graphite, libref, transport, and per-phase models.

Model resolution is:

1. Phase-specific `[models].<phase>`.
2. CLI `--model`, except for JUDGE.
3. `[models].default`.
4. Backend default.

## 2. Prompt System

DeviaTDD has two prompt modes.

### Automated mode

`load_template()` composes:

1. `specs/constitution.md`, when present.
2. `prompts/core/core.md`.
3. `prompts/core/<layer>-shared.md`.
4. `prompts/core/lifecycle-auto.md`.
5. `prompts/core/style-ste.md`.
6. `prompts/auto/<phase>.md`.
7. Runtime contract placeholder values.

### Manual slash-command mode

`compose_command_body()` composes:

1. Source frontmatter.
2. `core.md`.
3. `<layer>-shared.md`.
4. `lifecycle-manual.md`.
5. `style-ste.md`.
6. The command body from `prompts/commands/<name>.md`.

Setup strips internal frontmatter and writes platform-specific copies.

### Current customization limitation

Current DeviaTDD maintainers customize canonical prompts in `src/deviate/prompts/`. Consumer projects have no supported tracked prompt overlay with explicit precedence or schema validation. Installed copies are generated and gitignored.

Guildwright must add a tracked project override layer. See [Prompt Customization](guildwright-rust-tui-requirements.md#7-prompt-customization).

## 3. Product Layer

The Product layer is optional.

### Flows

`/deviate-flows` gathers actor, domain, job, trigger, and success state. It writes `specs/_product/flows/flows-<domain>.md` and updates `flows/index.md`.

`deviate flows sync` converts the index into `flows.jsonl`. It appends identity, discovered, and documented events.

### Architecture

`/deviate-architecture` requires at least one flow. It writes `architecture.md` and `domain-model.md`. Local changes route to Meso. Cross-epic changes remain at Product scope.

### Release

`/deviate-release` requires flows and architecture. It writes `release-next.md` with included flows, work, and acceptance criteria.

### Downstream traceability

Shard and Adhoc read Product artifacts. Each issue records `flow_refs`. Merge appends `FLOW_CONFIRMED_IMPLEMENTED`. Release inspection selects confirmed flows not yet included in a release.

## 4. Macro Layer


### Macro phase and result model

```text
IDLE -> EXPLORE -> RESEARCH -> AWAITING_GATE_1 -> PRD -> SHARD -> IDLE
```

Each active phase can produce SUCCESS, FAILURE, INTERRUPTED, or NEEDS_HUMAN. FAILURE stays at the same phase for correction. INTERRUPTED resumes after artifact and Git reconciliation. NEEDS_HUMAN is legal at Gate 1 or an explicit contract-drift escalation. SHARD success appends BACKLOG issue records; SHARD failure appends nothing and keeps the phase resumable.
- Research creates the epic directory, moves `explore.md`, and writes `design.md` plus `data-model.md`.
- Gate 1 requires human design approval before PRD.
- PRD writes requirements and `AO-NNN` acceptance outlines. It must not write Gherkin.
- Shard creates 1–10 vertical issues. It registers BACKLOG issue rows in `issues.jsonl`.

`deviate macro run` automates pre, agent invocation, post, validation, commits, and resume selection.

### Adhoc path

Adhoc compresses Explore, Research, PRD, and Shard for bounded work. A complexity gate rejects broad or architectural work. It appends to `specs/adhoc/prd.md`, writes one issue, and registers it in `issues.jsonl`.

## 5. Issue Claim and Meso Layer

### Branch claim

A claim uses `feat/<epic>/<issue-slug>`.

1. Select an unblocked BACKLOG issue.
2. Check the remote branch claim.
3. Create the branch and linked worktree.
4. Copy agent assets and local environment support.
5. Run project setup.
6. Append a SPECIFIED issue transition.
7. Commit the claim.
8. Push the branch. The first successful remote push wins a concurrent claim.

### Branch-to-issue resolution

The runner parses `feat/<bucket>/<slug>`. It matches `specs/<bucket>/issues/<slug>.md` against `source_file` rows in `issues.jsonl`.

Branch resolution is the durable scope signal. `.deviate/session.json::active_issue_id` is only a runtime hint.

### Plan

Plan performs fresh issue-local research. It writes `plan.md`. The `## Acceptance Contract` is authoritative.

Every `AC-PLAN-NNN` maps to a real `AO-NNN`, upstream requirement tokens, current-code evidence, and one Given/When/Then scenario. Every AO must have coverage.

### Tasks

Tasks reads issue intent and the Plan contract. It writes `tasks.md` and registers task records in the issue task ledger. Plan wins over legacy Gherkin.

Task execution modes are TDD, DIRECT, EXECUTE, E2E, and legacy IMMEDIATE aliases. User-facing changes receive a final E2E verification task.

### Automatic handoff

Tasks advances directly into Micro. Gate 2 does not exist. This is a constitutional rule from `specs/constitution.md` section 1 and version 0.8.0.

### Meso state model

```text
BACKLOG --claim--> SPECIFIED --plan--> TASKS --task registration--> IMPLEMENTING
IMPLEMENTING --all tasks complete--> AWAITING_GATE_3 --merge--> COMPLETED
```

Unmet dependencies produce a derived BLOCKED condition while the durable issue status remains BACKLOG. A phase failure keeps the issue at its last committed state. A terminal task failure keeps the issue IMPLEMENTING and requires recovery or an explicit abandonment event. There is no pause between TASKS and IMPLEMENTING.

### PR, review, walkthrough, and merge

- PR builds metadata from branch commits and issue artifacts.
- Review performs the final structured audit for Gate 3.
- Walkthrough provides a human-guided architectural tour.
- Merge squash-merges the branch, appends COMPLETED, confirms flow events, and commits code plus ledgers atomically.
- Optional cleanup archives the pre-squash tip, removes worktrees, and deletes branches.

## 6. Micro Layer

### TDD state machine

```text
PENDING
  -> RED
  -> GREEN
  -> JUDGE
     -> revert_red -> RED
     -> revert_green -> GREEN
     -> continue_refactor -> REFACTOR
     -> proceed_to_refactor_no_diff -> REFACTOR
     -> skip_refactor -> COMPLETED
  -> REFACTOR
  -> COMPLETED
```

RED writes tests and must produce an assertion failure, not a pass, syntax error, import error, or crash.

GREEN writes production code. It runs the configured test command. Mechanical failures and test defects route to JUDGE with typed evidence.

JUDGE runs in an isolated agent session. It evaluates the complete diff against Plan, issue scope, security, governance, and flow references.

REFACTOR runs after compliance approval. It reruns regression checks. A regression discards the refactor and preserves verified GREEN.

### JUDGE routing

- `revert_red`: discard RED and GREEN. A test defect forces this route.
- `revert_green`: preserve RED and discard GREEN.
- `continue_refactor`: approve a substantive diff.
- `proceed_to_refactor_no_diff`: approve a valid zero-production-diff slice.
- `skip_refactor`: complete without refactor.

The TRAIN loop permits three JUDGE-directed attempts. The task runner permits two outer task attempts. The queue stops after the first terminal task failure.

### Direct and E2E work

DIRECT and EXECUTE bypass RED. They run implementation and JUDGE against a pre-execute Git boundary.

E2E verifies an issue-level consumer flow. It resolves the issue from the branch and checks only that issue's tasks.

## 7. Runner and Agent Backends

Supported agent surfaces include Claude, OpenCode, Factory Droid, Pi, and OMP. Pi can use CLI or RPC transport.

The runner:

- caps prompts at 80,000 characters;
- streams output;
- detects a 60-second output stall;
- retries timeouts once after backoff;
- retries malformed or empty manifests once with parse context;
- parses a YAML handover manifest;
- rejects schema-recovered manifests as successful results;
- logs per-run and per-task events.

Tests run through a safe command boundary with allow-list validation and a process-group deadline. Timeout returns code 124 after TERM and KILL escalation.

## 8. Output Surfaces

Guildwright must distinguish four output classes.

### Machine contracts

Pre commands emit JSON contracts. Pipeline JSON mode emits JSONL events such as task start, phase change, task completion, failure, halt, and completion.

### Agent handovers

Agents emit structured YAML manifests. Key fields include phase, status, verdict, rationale, files, failure kind, feedback, and JUDGE next action.

### Durable artifacts

Markdown, HTML, source changes, tests, and JSONL ledgers are tracked in Git. Markdown remains canonical. HTML is an agent-authored sibling, not an automatic Markdown translation.

### Human presentation

Rich renders pipeline banners, summaries, progress, agent streams, warnings, recovery instructions, and exit status. Review reports and run logs are gitignored diagnostic output.

The Guildwright TUI must render typed domain events. It must not parse its own human-readable text. Current Rich-only gate summaries, warnings, rationale, and recovery instructions therefore require typed equivalents before the port can preserve them.

## 9. Inspection and Diagnostics

Inspection includes issue list/show, task list/show, flow coverage, release candidates, review, walkthrough, logs, and HTML authoring.

Flow coverage derives a view from `flows/index.md`, `flows.jsonl`, and issue `flow_refs`. Derived drift status is not persisted.

## Evidence

Primary evidence:

- `specs/constitution.md`
- `specs/DeviaTDD-api.md`
- `specs/DeviaTDD-architecture.md`
- `src/deviate/cli/`
- `src/deviate/state/ledger.py`
- `src/deviate/state/config.py`
- `src/deviate/core/agent.py`
- `src/deviate/prompts/`
