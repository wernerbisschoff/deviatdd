# Guildwright Gap Register

This register separates current DeviaTDD defects and ambiguities from Guildwright requirements.

Every `Current` claim below is confirmed by the cited source. Entries without a current implementation claim are Guildwright design decisions, not defect assertions.

Related documents: [rewrite index](guildwright-rewrite.md), [current-system catalog](guildwright-current-system.md), [Git-backed state model](guildwright-git-state-model.md), and [Rust TUI requirements](guildwright-rust-tui-requirements.md).

## Critical State Gaps

### GAP-STATE-01: Gitignored session can disagree with Git

**Current:** `.deviate/session.json` stores active issue, phase, rollback SHA, feedback, and verdict data. Worktrees receive a one-time copy.

**Risk:** Checkout or revert can change tracked state while the runner retains newer session truth.

**Guildwright:** Derive workflow state from branch, tracked ledgers, and artifacts. Keep only process-resume data in the session cache.

**Evidence:** `src/deviate/state/config.py::SessionState`, `src/deviate/cli/meso.py`, `src/deviate/cli/micro.py`.

### GAP-STATE-02: Revert equivalence is not guaranteed

**Current:** COMPLETED is terminal in the issue reducer. Partial or external reverts can leave task and flow transitions inconsistent with code.

**Risk:** A reverted implementation can remain completed in the runner.

**Guildwright:** Define and test semantic state equivalence after commit reverts. Validate ledger-to-artifact consistency on startup.

**Evidence:** `src/deviate/state/ledger.py:204-260` treats COMPLETED as terminal and does not detect that a later Git revert removed the code or confirmation transaction it represented.

### GAP-STATE-03: Branch resolver is duplicated

**Current:** `_BRANCH_SLUG_RE` and resolution logic exist in shared CLI code and Micro.

**Risk:** Different commands can resolve different issues.

**Guildwright:** One pure branch parser and one issue resolver.

**Evidence:** `src/deviate/cli/_common.py:162-197` and `src/deviate/cli/micro.py:694,850-866` implement separate resolvers.

### GAP-STATE-04: Recovery evidence is split

**Current:** Runner rollback uses `tmp/deviate-agent-work/...`; commit failure uses `refs/deviate/recovery/...`; `.deviate/rollback.jsonl` adds another store.

**Risk:** Recovery discovery and cleanup are incomplete.

**Guildwright:** One recovery namespace and one typed recovery view.

**Evidence:** `src/deviate/cli/micro.py:1430-1583`, `:3532-3645`; `src/deviate/state/ledger.py:340-347`.

### GAP-STATE-05: Pre-squash history archive is optional

**Current:** Archive tagging occurs only during branch deletion. External or UI merges can lose the convenient history handle.

**Guildwright:** Archive the pre-squash tip as part of merge, independent of cleanup.

## Ledger Gaps


### GAP-LEDGER-01: Malformed-row policy differs

Some paths warn and skip malformed JSONL. Others fail strictly.

Guildwright must fail trusted reduction with exact row diagnostics. Inspection can offer a tolerant forensic mode.

**Evidence:** `src/deviate/state/ledger.py:41-58` warns and skips malformed rows; `:282-295` raises on the same condition.

### GAP-LEDGER-02: Flow reference event idempotency is unclear

`FLOW_REFERENCED_BY_ISSUE` lacks the stable sentinel used by merge confirmation.

Guildwright must define semantic keys per event type and test repeated synchronization.

### GAP-LEDGER-03: Union merge is not semantic conflict resolution

Union merge preserves lines but can retain incompatible claims or transitions.

Guildwright must run semantic validation after merges and before execution.

### GAP-LEDGER-04: Event schemas need an explicit version migration policy

Guildwright must version records and preserve unknown forward-version records without treating them as valid current state. This is a new design requirement, not a confirmed current parser defect.

## State-Machine Gaps

### GAP-FSM-01: Macro and Meso use descriptive session phases

Current phase validation is incomplete and automated paths use `force_transition_to()`.

Guildwright must encode legal Product, Macro, Meso, TDD, DIRECT, and E2E machines as separate enums.

### GAP-FSM-02: Failure classes span manifest and session schemas

`failure_kind` is duplicated across agent handover and session state.

Guildwright must use one shared type.

### GAP-FSM-03: Gate documentation contains removed Gate 2 diagrams

The constitution removes Gate 2. Architecture still retains historical diagram lines before correcting them in prose.

Guildwright must render only Gate 1 and Gate 3. Historical documentation can mention Gate 2 only as removed.

### GAP-FSM-04: Product approvals are not formal runner state

Flows, architecture, and release prompts contain conversational approvals. They are not typed phase events.

Guildwright must decide whether to persist Product approval evidence or keep it as commit evidence.

### GAP-FSM-05: Macro and Meso failure recovery uses side channels

Current automated paths use `force_transition_to()` and represent failures through exceptions, session fields, and output tokens. Guildwright must encode legal phase-result transitions and refuse every unlisted transition.

**Evidence:** `src/deviate/state/config.py::SessionState.force_transition_to`, `src/deviate/cli/meso.py::_meso_run`, `src/deviate/cli/macro.py::_macro_run`.

### GAP-FSM-06: Claim health lacks a shared domain type

Current claim status is inferred separately from ledger rows, branches, remotes, and worktrees. Guildwright defines `Unclaimed`, `LocalOnly`, `RemoteClaimed`, `Stale`, `Conflicted`, and `ClaimInterrupted`.

## Prompt Gaps

### GAP-PROMPT-01: Consumer projects lack tracked prompt overlays

DeviaTDD maintainers can edit `src/deviate/prompts/`. Consumer projects receive gitignored generated copies without supported precedence.

Guildwright must implement tracked project layers, protected sections, effective prompt previews, and digests.

### GAP-PROMPT-02: Manual and automatic prompt bodies can drift

They share core layers but use separate command and auto phase templates.

Guildwright must identify which behavior contracts are shared and validate parity.

### GAP-PROMPT-03: Prompt truncation can remove required context

Head-and-tail truncation is deterministic but not contract-aware.

Guildwright should budget named prompt sections and fail when protected context cannot fit.

### GAP-PROMPT-04: Model-routing documentation conflicts

Architecture says routing is not programmatically enforced, then documents the implemented CLI and config priority chain. Guildwright must document implemented resolution, backend capability, and JUDGE override rules in one place.

**Evidence:** `specs/DeviaTDD-architecture.md:500-507` and `:713-726`; `src/deviate/state/config.py::resolve_phase_model`; `src/deviate/cli/micro.py::_resolve_model_for_phase`.

## Output and TUI Gaps

### GAP-OUTPUT-01: Human output contains contract information

Rich warnings, recovery instructions, gate summaries, and some rationale are not always represented as complete typed events.

Guildwright must promote them to typed payloads before rendering.

### GAP-OUTPUT-02: Event vocabularies are fragmented

The monitor has a small event set. Run logs use a larger string vocabulary. JSON contracts use separate shapes.

Guildwright must define one versioned event envelope with domain payload enums.

### GAP-OUTPUT-03: Agent output filtering hides information by text pattern

Current Micro output filters YAML fences, tool lines, headers, and status prose.

Guildwright must retain raw output for diagnostics and use structured frames for presentation.

### GAP-OUTPUT-04: HTML and Markdown can drift

HTML is hand-authored and Markdown remains canonical. Token mismatches are detected only in selected workflows.

Guildwright must show divergence and source provenance. It must not silently regenerate authored HTML.

### GAP-OUTPUT-05: Walkthrough post is a placeholder

It emits a JSON note but does not persist a useful audit artifact.

Guildwright must either make walkthrough ephemeral by design or persist a typed outcome.

## Runner and Recovery Gaps

### GAP-RUNNER-01: Reset and revert guidance conflicts

User guidance calls `git revert` the safe path. TRAIN uses `git reset --hard` and `git clean -fd`.

Guildwright must distinguish operator history undo from isolated-attempt discard.

### GAP-RUNNER-02: Rollback ordering needs one contract

Guildwright must execute runner rollback in this order:

1. verify isolated branch and clean preconditions;
2. validate the explicit boundary SHA;
3. create and verify the recovery ref;
4. record typed recovery metadata;
5. reset to the boundary;
6. clean untracked, non-ignored files;
7. reduce state again;
8. publish the rollback result.

No ledger row is staged during an attempt discard. The reset restores the tracked ledger bytes at the boundary.

### GAP-RUNNER-03: Queue always halts after the first terminal failure

Guildwright should preserve this safe default and add an explicit continue-on-failure policy for independent tasks.

### GAP-RUNNER-04: Writer locks need crash recovery

A writer registration must include repository identity, worktree identity, PID, process start token, and heartbeat. Guildwright can reclaim a stale lock only after verifying the process is absent.

### GAP-RUNNER-05: Claim bypasses mandatory hooks

Current issue claim and completion commits invoke `git commit --no-verify`. Claim push invokes `git push --no-verify`.

This violates the repository Commit Authority contract. It is a current must-fix defect, not a Guildwright design option. Guildwright must never silently bypass repository policy.

**Evidence:** `src/deviate/cli/meso.py:554-560`, `:576-579`, and `:1310-1313`.

### GAP-RUNNER-06: Recovery between RED boundary clear and commit is weak

A process death can leave no rollback boundary.

Guildwright must derive boundaries from verified commit metadata and interrupted transaction records.

### GAP-RUNNER-07: YAML manifest recovery policy is mixed

Schema recovery fills missing fields but marks the result unsuccessful. Logs still expose recovered fields.

Guildwright must emit one parse outcome enum and never confuse recovered diagnostics with an accepted handover.

## Setup and Configuration Gaps

### GAP-SETUP-01: Setup and init contracts overlap

Documentation calls them equivalent while constitution creation differs.

Guildwright needs one setup command with explicit modes and one migration command.

### GAP-SETUP-02: Environment copying is unsafe by default

Current worktree setup copies `.env` when present.

Guildwright must use explicit environment forwarding policy and secret redaction.

### GAP-SETUP-03: Installed prompt copies can drift

Generated agent files are gitignored and can diverge from package sources.

Guildwright must display installed digest versus effective source digest and repair safely.

### GAP-SETUP-04: Runtime directory has no schema version

Guildwright must version `.guildwright/` and migrate caches independently from tracked workflow data.

## Missing Product Decisions

### DECISION-01: TUI ownership

Decide whether Guildwright owns agent execution or can attach to external runs. Recommendation: support both through the same event protocol.

### DECISION-02: Git library

Choose `git2`, `gix`, or controlled Git CLI execution. Recommendation: use the Git CLI for behavior parity first, behind a typed adapter. Revisit after compatibility tests pass.

### DECISION-03: Ledger format evolution

Keep JSONL for compatibility or introduce a new event encoding. Recommendation: keep versioned JSONL. It remains mergeable, inspectable, and revert-friendly.

### DECISION-04: Product approval persistence

Recommendation: use signed or attributed commit evidence plus optional ledger events. Do not add mutable approval files.

### DECISION-05: Prompt replacement authority

Recommendation: allow named-section replacement. Protect governance, safety, HITL, and output schema sections.

### DECISION-06: Compatibility command names

Recommendation: `guildwright` is the canonical binary. An optional `deviate` shim maps commands for one migration release, then is removed.

### DECISION-07: Task scheduling

Recommendation: execute sequentially in one issue by default. Parallelize only tasks with proven dependency and file-scope independence.

### DECISION-08: Remote provider scope

Current flows assume GitHub and optionally Graphite. Decide whether the first release supports GitHub only or a provider trait.

## Additional Required First-Release Coverage

- Safe command policy and shell injection resistance.
- Configuration provenance and schema migration.
- Crash recovery and stale writer detection.
- Worktree lifecycle and orphan repair.
- PR, merge, archive, and remote push behavior.
- Gate 3 review and walkthrough.
- Flow coverage and release-candidate inspection.
- HTML artifact provenance and divergence.
- Agent transport capability negotiation.
- Manifest versioning and parse failures.
- Timeouts, cancellation, process-tree cleanup, and partial output.
- Secrets, environment forwarding, redaction, and logs.
- Migration from `.deviate/` without rewriting tracked specs.
- Accessibility, keyboard navigation, reduced motion, color independence, and non-TUI JSON mode.
- Performance budgets and telemetry policy.
- Property tests for reducer and Git revert behavior.
