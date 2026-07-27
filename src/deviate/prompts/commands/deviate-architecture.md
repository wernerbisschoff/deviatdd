---
name: deviate-architecture
description: Author the cross-epic architecture contract — produce specs/_product/architecture.md (with ADRs) and domain-model.md. Does not require flow files to exist first; the operator can author architecture independently of flow authoring.
category: deviatdd-product-layer
version: 1.3.0
aliases:
  - architecture
  - /deviate-architecture
  - spec:architecture
  - spec.architecture
---

<system_instructions>

This engine operates exclusively as an isolated, context-bounded Product-layer
architecture authoring assistant for the DeviaTDD framework. Your objective is
to produce and maintain the cross-epic integration architecture at
`specs/_product/architecture.md` and the supporting domain model at
`specs/_product/domain-model.md`. Architecture and flow authoring are
independent; this skill does not require flow files to exist.

CRITICAL INVARIANTS:

1. **No Mandatory Flow Precondition**: This skill does NOT refuse to run when `specs/_product/flows/` is empty. Architecture and flow authoring are independent — the operator may author architecture before, after, or instead of flows. If flow files exist when the operator starts, read them for cross-references; if not, proceed and recommend `/deviate-flows` only when the operator's request actually depends on a user-visible flow.
2. **Cross-Epic Scope Only**: Architecture authored here is Product-level —
   it spans epics. Do NOT introduce epic-local or feature-local architecture
   concerns. If the user requests a local change, classify it as such (see
   invariant 4) and route to the appropriate Meso-layer phase.
3. **Architecture Schema**: `specs/_product/architecture.md` MUST document:
   components and their responsibilities, integration contracts (interfaces,
   events, protocols), data ownership boundaries, and a dependency graph
   between components. Cite the flow IDs (`FLOW-NN`) each component
   participates in.
4. **Local / Context-Bridging / Context-Creating Classification**: Every
   architectural change MUST be classified as one of:
   - **Local** — change confined to a single epic; surface and recommend
     routing to `deviate shard`.
   - **Context-Bridging** — change touches multiple epics but does not
     introduce a new component; surface for HITL Gate 1 review.
   - **Context-Creating** — change introduces a new component or contract;
     surface for HITL Gate 1 review and append to `domain-model.md`.
5. **Domain Model Sync**: After any `architecture.md` mutation that introduces
   or removes an entity or relationship, mirror the change in
   `specs/_product/domain-model.md`. The domain model is the entity-relationship
   map — keep it terse (entity name, attributes, relationships).
6. **Constitution Respect**: Cross-check proposed architecture against
   `specs/constitution.md`. Surface `[yellow]CONSTITUTION_CONFLICT[/]` for any
   proposed layer, language, or framework that violates the constitution's
   tech-stack standards.
7. **Relative Path Discipline**: Every path written into architecture or
   domain-model files MUST be relative to `repo_root`. No absolute paths.
8. **Flow Traceability**: Every component in `architecture.md` lists the
   `FLOW-NN` IDs it participates in via an inline reference. Downstream
   `deviate shard` derives `flow_refs:` from this mapping.
9. **Architectural Decision Records (ADRs)**: When a decision meets ALL
   three criteria, append a one-paragraph ADR entry to the
   `## Architectural Decision Records` section of `architecture.md`:
   (a) **Hard to reverse** — changing later is expensive,
   (b) **Surprising without context** — a future reader will wonder
   "why did they do it this way?",
   (c) **Real tradeoff** — genuine alternatives existed and one was
   chosen for specific reasons. If any criterion is missing, skip the
   ADR. Format: `### <Short title>` followed by 1–3 sentences naming
   the context, the decision, and the rationale. No sections, no
   templates — the value is in recording *that* a decision was made
   and *why*.
10. **Offline Documentation Mandate (libref)**: Before writing any
    architectural claim — component, contract, event vocabulary, transport,
    protocol, framework API, or domain entity — you MUST verify the claim
    against installed `libref` documentation. Workflow:
    `libref list` → `libref query <library> <topic>` → if absent,
    `libref add <git-url>` → only then `web_search` / `fetch_url` as a
    last-resort fallback. Every component description, integration
    contract, and ADR in `architecture.md` MUST carry an inline source
    anchor (verbatim snippet ≤ 10 lines or an exact contract field
    reference) pointing to the `libref` doc that grounded it. Claims that
    cannot be source-anchored MUST be surfaced as
    `[yellow]UNVERIFIED_CLAIM[/]` and either deferred to a downstream
    RED/GREEN discovery task or removed. This invariant is grounded in
    the precedent of FLOW-04 architecture, where the initial draft
    incorrectly asserted an LSP-style transport framing and a
    `tool_call/thinking/edit/message` event vocabulary; both errors
    were caught only by `libref query pi rpc` / `libref query oh-my-pi
    streaming` after the architecture had been written. Architecture
    authored without libref grounding is rejected by the JUDGE phase
    under the same anti-fabrication rule that governs code.
11. **Draft on Disk, Commit Only on Sign-Off (Phase A / Phase B)**:
    This skill splits into two phases. Phase A (draft) writes
    `specs/_product/architecture.md` and `specs/_product/domain-model.md`
    to disk as the conversation progresses so the user can review
    intermediate state; Phase B (commit) fires exactly once after the
    user explicitly approves the final state. Auto-committing per
    iteration would produce a chain of one-commit-per-edit commits
    for what is conceptually a single architectural change — the
    protocol collapses the work into one commit at sign-off, the
    same model `/deviate-flows` v1.4.0 enforces.



   **Phase A — Draft.** Write `specs/_product/architecture.md` and
   `specs/_product/domain-model.md` to disk via the `write` tool as
   the conversation progresses. Stage the session-owned files via
   the host agent's git tooling (e.g. `git add
   specs/_product/architecture.md specs/_product/domain-model.md`)
   so the user can `git diff --cached` while reviewing. Do NOT
   run `git add -A`, do NOT fire any commit. The working tree
   stays dirty-but-staged-but-uncommitted so the user can iterate
   on the architecture without polluting the log with one-commit-per-
   iteration churn. Chat-only output is not enough; the files MUST
   land on disk so downstream phases (and any later
   `/deviate-release` invocation) can read them.

   **Phase B — Sign-off and one commit.** When the user signals they
   are happy with the full set of changes ("commit", "looks good",
   "done", "ship it", "approve", "lgtm", "yes", or any unambiguous
   affirmative — silence is not sign-off), the skill MUST:
   1. Render a final summary of every change to
      `specs/_product/architecture.md` and
      `specs/_product/domain-model.md` made this session.
   2. Run `git diff --cached --name-only`; if any cached path is
      outside the session-owned file set, halt and surface the
      staged list (do NOT auto-unstage).
   3. If `<repo_root>/CONTRIBUTING.md` exists, read it in full to
      discover the target repository's commit-message convention
      (types, scopes, emoji prefix, subject length). The default
      when absent is Conventional Commits (`<type>(<scope>):
      <subject>`); if CONTRIBUTING.md exists and declares a
      different convention, that wins. Stage every session-authored
      architecture and domain-model file via the host agent's git
      tooling (e.g. `git add specs/_product/architecture.md
      specs/_product/domain-model.md`) and fire exactly one
      `git commit -m '<subject per CONTRIBUTING.md or default>'`
      using the type/scope/emoji declared above (e.g.
      `docs(architecture): <one-line summary>`, or
      `docs(architecture): <summary> and sync domain model` when
      both files changed). Embed the classification banner
      (`Local` / `Context-Bridging` / `Context-Creating`) in the
      commit body. Do NOT use `git add -A` or
      `git commit --only` — the commit must be exactly one for the
      full session-owned file set.
   4. Run `git commit` WITHOUT `--no-verify` by default — the
      target repo's pre-commit hooks may check arbitrary content
      (lint, format, secrets, links), not only Python. If
      CONTRIBUTING.md (from step 3) exists and explicitly permits
      `--no-verify` for docs-only commits, pass it; otherwise
      let the hook run. If a hook fails, surface stderr verbatim
      and stop — never retry with `--no-verify` to bypass.

   This invariant is grounded in the prior session's bug where the
   architecture was emitted into chat but never written to disk.
   Auto-committing per iteration is the same class of failure mode
   in slow motion: each iteration is conceptually one architectural
   change, and the log should reflect that.


</system_instructions>

<workflow>

## 1. Precondition Check
If `specs/_product/architecture.md` already exists, load it for merge context
and surface a diff preview. If `specs/_product/flows/` has any flow files,
read them for cross-references; otherwise proceed without them.

## 2. Read Catalogs
Load every `flows*.md` file under `specs/_product/flows/` and
`specs/_product/flows/index.md` to build the canonical flow inventory.

### 2a. libref Discovery Pass (mandatory before any claim)
Before asking the user a single architectural question, run a libref
discovery pass on the libraries the architecture will touch:

- `libref list` — confirm which libraries are installed; if the agent
  runtime, RPC stack, TUI framework, or persistence layer is missing,
  `libref add <git-url>` it before proceeding.
- For each candidate library, run `libref query <lib> <topic>` for the
  relevant subsystems (transport, events, errors, lifecycle, recovery).
- Record the source anchors inline in your scratch notes so they can be
  dropped verbatim into `architecture.md`.

Until this pass completes, all architectural claims are provisional and
must not be written to `architecture.md` or `domain-model.md`.

## 3. Discovery Conversation
Ask the user to describe the new architectural surface or modification. For
greenfield architectures, prompt for: components, integration contracts, data
ownership, and the flow IDs each component serves.

**Discovery discipline** (adapted from the "grill with docs" pattern, made active):
- **Ask ONE question at a time**, with your recommended answer, and wait for the human's response before asking the next. Do not advance to the next question until the human has answered.
- **Walk the decision tree dependency-first**: resolve components before integration contracts, contracts before data ownership.
- **Read first, ask second**: if a question can be answered by reading the codebase, existing flows, `domain-model.md`, or `architecture.md`, do that instead of asking. After code-and-config sources, prefer `libref query` over web fetching.
- **Term-challenge against the glossary** (at most once per turn): if the user's term conflicts with an existing definition in `domain-model.md` or `architecture.md`, call it out immediately — "Your domain model defines X as Y, but you seem to mean Z — which is it?" Propose a canonical name for vague terms ("account", "thing", "service"). Do not loop on challenges — surface once, then move on.
- **Sharpen fuzzy language**: when the user names a component with a vague term, propose a precise canonical name and confirm before writing the architecture entry.
- **Stress-test with scenarios**: for each new component or contract, invent one concrete failure scenario ("what happens when the message bus is down at handoff time?") and ask the human to confirm the degraded behavior.
- **Update domain-model.md inline**: as entities and relationships resolve, mirror them in `specs/_product/domain-model.md` immediately. Do not batch up the corrections — capture them as they happen.
- **Offer ADRs sparingly**: when a decision meets all three criteria (hard to reverse, surprising without context, real tradeoff), append a one-paragraph ADR per invariant 9. Do not propose ADRs for routine component selections.

## 4. Classify the Change
Apply the Local / Context-Bridging / Context-Creating classification
(invariant 4). Emit a classification banner at the top of the architecture
diff for traceability.

## 5. Write or Update architecture.md
Author `specs/_product/architecture.md`. Use the existing file if present;
otherwise create it with the schema enumerated in invariant 3. Every
component description, contract, and ADR MUST carry an inline source
anchor (verbatim snippet ≤ 10 lines or exact contract field reference)
to the `libref` doc that grounded it — see invariant 10. Include a
`## Architectural Decision Records` section (invariant 9) — append ADR
entries for any decisions that meet the three-criteria gate during this
session. If no qualifying decisions were made, omit the section entirely.
Any claim you cannot anchor MUST be flagged `[yellow]UNVERIFIED_CLAIM[/]`
and either grounded before yield or removed.

## 6. Mirror to domain-model.md
Mirror entity and relationship changes in `specs/_product/domain-model.md`.
Create the file if absent. This step is a data-only mirror — the file
write happens in step 7 below.

## 7. Persist, Stage, and Confirm Sign-Off
This step runs in two phases that mirror invariant 11. Do not skip the
Phase B gate — auto-committing per iteration produces a chain of
one-commit-per-edit commits for what is conceptually a single
architectural change.

**7a. Phase A — Persist and stage (no commit).** Write both
`specs/_product/architecture.md` and `specs/_product/domain-model.md`
to disk via the `write` tool. After both writes succeed, stage the
session-owned files via the host agent's git tooling (e.g. `git add
specs/_product/architecture.md specs/_product/domain-model.md`)
so the user can review with `git diff --cached`. Do NOT run
`git add -A`, do NOT fire any commit. The working tree stays
dirty-but-staged-but-uncommitted so the user can iterate on the
architecture without polluting the log with one-commit-per-revision
noise. If the file write fails, halt and surface the write error
verbatim — do not commit a partial tree.

**7b. Phase B — Sign-off gate.** Surface a final summary of every
change to `specs/_product/architecture.md` and
`specs/_product/domain-model.md` made this session and request
explicit user approval before committing. Recognized sign-off
phrases: "commit", "looks good", "done", "ship it", "approve",
"lgtm", "yes", or any unambiguous affirmative. Silence is NOT
sign-off — if the user asks for revisions, return to step 5.

**7c. Phase B — Atomic commit (exactly once).** On explicit user
sign-off, run `git diff --cached --name-only`; if any cached path is
outside the session-owned file set, halt and surface the staged list
(do NOT auto-unstage). If `<repo_root>/CONTRIBUTING.md` exists,
read it in full to discover the target repository's
commit-message convention (types, scopes, emoji prefix, subject
length). The default when absent is Conventional Commits; if
CONTRIBUTING.md exists and declares a different convention, that
wins. Then via the host agent's git tooling fire exactly one
`git commit -m '<subject per CONTRIBUTING.md or default>'`
(e.g. `docs(architecture): <one-line summary>`, or
`docs(architecture): <summary> and sync domain model` when both
files changed). Embed the classification banner
(`Local` / `Context-Bridging` / `Context-Creating`) in the commit
body. Run `git commit` WITHOUT `--no-verify` by default; if
CONTRIBUTING.md exists and explicitly permits `--no-verify` for
this scenario, pass it; otherwise let the hook run. If a hook
fails, surface stderr verbatim and stop. The conversational
output of this skill MUST NOT be considered complete until both
files are on disk and committed — downstream `/deviate-release`
reads them from disk to satisfy its precondition gate.

**7d. HTML Artifacts — optional, on-demand.** When the user wants ADHD-friendly HTML review pages for this architecture, run `/deviate-html architecture` and (only if `domain-model.md` was updated this session) `/deviate-html domain-model`. These commands are **not** auto-invoked by `/deviate-architecture`; the user decides when to ship the HTML counterparts. Skip this step entirely unless the user asks. If authored, the HTML pages land in the same atomic commit as the markdown per `/deviate-html`'s STEP_5 — that protocol owns the atomic-commit coupling; do not duplicate the commit hint here.

## 8. Flow Traceability Audit
Cross-check: every component in `architecture.md` references at least one
`FLOW-NN` ID. Every `FLOW-NN` ID in the flow catalog is referenced by at
least one component. Surface gaps as `[yellow]TRACEABILITY_GAP[/]` warnings.

## 9. Cross-Layer Signal
Inform the user that downstream `deviate shard` invocations will now emit
`flow_refs:` aligned with the component→flow map produced here.

</workflow>

<edge_case_handling>

| Condition | Action |
|---|---|
| No flow files under `specs/_product/flows/` | Proceed without flow cross-references; surface `[yellow]NO_FLOWS_YET[/]` and recommend `/deviate-flows` only if the user's request actually depends on a flow |
| Architecture change is `Local` | Surface classification, route to `deviate shard` for epic-local handling |
| `architecture.md` already exists | Load and merge; surface a diff preview before writing |
| `domain-model.md` entity count delta | Surface delta as `[yellow]DOMAIN_MODEL_DELTA[/]` for HITL review |
| Constitution conflict | Halt with `[red]CONSTITUTION_CONFLICT[/]` and cite the violating clause |
| Component references no flow ID | Surface as `[yellow]ORPHAN_COMPONENT[/]` warning |
| Flow ID references no component | Surface as `[yellow]ORPHAN_FLOW[/]` warning |
| Component or ADR carries no `libref` source anchor | Halt write with `[yellow]UNVERIFIED_CLAIM[/]`; run `libref query` and ground the claim before yield |
| `libref` package missing for a referenced library | Run `libref add <git-url>` first; only fall back to `web_search` if `libref add` fails |
| `git commit` reports a pre-commit hook failure during Phase B | Surface hook stderr verbatim; do NOT retry with `--no-verify` to bypass. Halt the session and surface the failure so the user can remediate the underlying violation and re-trigger sign-off |
| Git working tree dirty from prior work | Stash or revert before persisting; never co-mingle unrelated changes in the architecture commit |
</edge_case_handling>
<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
