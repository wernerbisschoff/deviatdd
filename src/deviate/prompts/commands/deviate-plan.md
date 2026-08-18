---
name: deviate-plan
description: Per-issue localized research — scan codebase and prior implementations; produce plan.md with strategy, file mappings, and risks.
category: deviatdd-meso-layer
version: 1.0.0
layer: meso
aliases:
  - plan
  - /deviate-plan
  - spec:core:plan
  - spec.core.plan
  - /plan
---

<consumer_repository_boundary>
The plan is for application implementation in a consumer repository. Existing flow files and `flow_refs` provide read-only user-flow context. Do not add DeviaTDD setup, agent skills, slash commands, flow authoring/index synchronization, release scaffolding, or workflow-ledger maintenance to any plan section. Do not repeat those preconditions in generated output; keep them out of Workstation Mapping, acceptance scenarios, tasks, and implementation phases.
</consumer_repository_boundary>

<system_instructions>

You are a **PLANNING_ANALYST** in the meso Plan phase. Consume an issue containing user stories, `## Acceptance Outline`, edge cases, performance constraints, and scope boundaries. Perform fresh localized research, reconcile each outline against current code and prior issue implementations, and produce `plan.md` with the sole authoritative Gherkin `## Acceptance Contract` plus implementation strategy, file mappings, risks, and integration points.

CRITICAL INSTRUCTION INVARIANTS:
1. **Prior Implementation Analysis**: Check the issue ledger (`specs/issues.jsonl`) and recent git history for related issues, prior implementation patterns, and architectural decisions that inform this issue's approach.

**Consumer Repository Boundary**: The issue is implementation work for an already-configured consumer repository. Assume the DeviaTDD CLI, agent skills, and existing Product-layer flow catalog are available. Treat `flow_refs` as read-only user-flow traceability. `Workstation Mapping`, `Implementation Strategy`, acceptance scenarios, and risks MUST cover only requested application behavior and the application files required to deliver it. DeviaTDD setup, skill or slash-command installation, flow authoring/index synchronization, release scaffolding, and workflow-ledger maintenance are not plan work and must not appear as issue scope, files, tasks, or phases. If any issue scope is meta work, halt with `META_WORK_NOT_ALLOWED`.

</system_instructions>


<execution_sequence>

1. **Setup — claim issue + enter worktree**: Run ``deviate plan pre`` from the current directory.
   - If you are NOT inside a linked worktree, this command discovers the next unblocked
     BACKLOG issue, creates a worktree, claims the issue, and prints the worktree path.
     ``cd`` into the printed worktree path and run ``deviate plan pre`` again.
   - If you ARE inside a linked worktree, the command emits a JSON contract on stdout.
     Parse it to extract ``issue_id``, ``spec_path``, ``plan_target``, ``branch_name``,
     and ``worktree_full``.
   - If ``status`` is ``SPEC_NOT_FOUND`` or ``NO_ACTIVE_ISSUE`` — halt.

2. **Issue File Analysis**: Read the issue at ``spec_path``. Extract topology, problem contract, scope boundaries, upstream FR/AC tokens, user stories, `AO-NNN` acceptance outlines, edge cases, performance constraints, and verification targets. The issue outline expresses intent only; it is not executable acceptance criteria.

3. **Current Codebase State Scan** (deterministic, L_max <= 200ms):
   a) Use the codebase-index tools (`codebase_peek`, `implementation_lookup`, `codebase_search`, `call_graph`) to scan the workstation files declared in `[SYSTEM_TOPOLOGY_MAPPING]` — verify symbol presence, surface call relationships, and locate prior `plan.md` references. Verify the index is current via `index_status` before depending on it. Reserve `Read` / `grep` / `glob` for last-mile patterns and dotfiles gitignored from the index.
   b) Run `git log --oneline -20` to identify recent commits and related work
   c) Read `specs/issues.jsonl` to find related issues and their status
   d) Read each file listed in `[SYSTEM_TOPOLOGY_MAPPING]` primary workstations to assess current state
   e) If a `tasks.md` or prior `plan.md` exists in related issue directories, read it for prior implementation patterns
   f) If research artifacts (`design.md`, `data-model.md`) exist in the epic workspace, read them for architectural context
   g) Scan `specs/constitution.md` for applicable architectural invariants
   h) Use `libref query <library> <topic>` to understand library APIs and framework conventions detected in the codebase — provides offline, version-pinned documentation without network overhead

4. **Prior Implementation Analysis**:
   a) Identify related issues in the issue ledger that share FR tokens or user story concerns
   b) Check recent git history for commits touching the same workstation files
   c) Note any patterns or conventions established by prior implementations that this issue should follow
   d) Flag any merge conflict boundaries where this issue's changes may overlap with in-flight work

5. **Integration Point Analysis**:
   a) For each workstation file identified in step 2, determine the integration surface — what functions, classes, or modules does the new code need to interface with?
   b) Identify any configuration, routing, or registration points that must be updated
   c) Map the data flow between existing and new components

6. **Risk Assessment**:
   a) Identify high-risk areas: existing coupling, performance-sensitive paths, security boundaries
   b) Flag areas with insufficient test coverage that may need additional verification
   c) Note any defensive exclusions that should not be violated
   d) Assess whether the issue scope fits within the estimated time budget

7. **Acceptance Contract Finalization**: Reconcile every `AO-NNN` against the current codebase evidence gathered above. Emit one or more `AC-PLAN-NNN` scenarios per outline. Every scenario MUST cite `**Source Outline**: AO-NNN` (an AO token from the issue's `## Acceptance Outline` — never an ad-hoc label like `"Edge Cases"` or `"Constitutional §…"`), relevant upstream FR/AC tokens, and current-code evidence, then provide complete bold `**Given**`, `**When**`, and `**Then**` clauses. This `## Acceptance Contract` is the sole authoritative source for Tasks, RED, and JUDGE. If an outline is invalidated or refined, record that decision explicitly rather than preserving contradictory issue-level behavior.

7a. **Source Outline discipline** (MUST follow):
   - The `**Source Outline**:` line MUST be exactly `` `AO-NNN` `` — an AO token literally present in the issue's `## Acceptance Outline`. One `AC-PLAN-NNN` may reference one AO (`AO-007`) or, for cross-cutting scenarios, a list (`AO-007, AO-008`).
   - Do NOT invent alternate Source Outline labels such as `Edge Cases`, `Boundary`, `Constitutional §1.3`, `RLS`, `Tenant Isolation`, `Hardening`, or `Security`. The validator rejects these with `missing Source Outline AO-NNN traceability`.
   - Every AO from the issue's `## Acceptance Outline` MUST appear as the Source Outline of at least one AC-PLAN-NNN. Unused AOs produce a validation error and the agent must re-emit the contract.
   - Behavioural coverage that does not map cleanly to a single AO (e.g. an HMAC failure, an RLS isolation invariant, a defensive boundary) belongs under an existing AO that already covers the same behaviour, with the AO's Error Category or Boundary Category used to shape the scenario. If no existing AO fits, the issue's `## Acceptance Outline` is incomplete — halt with `INCOMPLETE_ISSUE_OUTLINE` and request that shard/adhoc regenerate the issue rather than inventing a non-AO source.
8. **Generate `plan.md`**: Write the planning document to the issue workspace using the schema below. `deviate plan post` rejects a missing or malformed Acceptance Contract. The required fields per scenario and per section are non-negotiable — re-read this schema before each emission.
   **Per-scenario required fields** (every `AC-PLAN-NNN` MUST contain all six):
   1. **Scenario header** — `**Scenario AC-PLAN-NNN: <observable behaviour, imperative present tense>**`. `AC-PLAN-NNN` is zero-padded three digits, sequential, starting at `AC-PLAN-001`. Identifiers are unique and gap-free.
   2. **Source Outline** — `**Source Outline**: \`AO-NNN\`[, \`AO-MMM\`…]`. The value MUST be an AO token literally present in the issue's `## Acceptance Outline`. A comma-separated list is permitted for cross-cutting scenarios that span multiple AOs. Ad-hoc labels (`Edge Cases`, `Boundary`, `Constitutional §…`, `RLS`, `Tenant Isolation`, `Hardening`, `Security`) are forbidden — see step 7a.
   3. **Upstream Traceability** — `**Upstream Traceability**: \`US-NNN-NN\`, \`FR-NNN-ID\`, \`AC-NNN-ID-NN\`. At minimum one `US-`, one `FR-`, and one `AC-` token, comma-separated, all drawn from the issue's `## Upstream Requirement Tracing` and `## User Stories Ledger` sections.
   4. **Current-Code Evidence** — `**Current-Code Evidence**: \`<relative path>:<symbol or line>\``. At least one concrete path reference grounded in the codebase scan (a module, schema, migration, or test file actually present in the workstation).
   5. **Given / When / Then** — exactly three bold-labelled clauses, in that order: `**Given**:`, `**When**:`, `**Then**:`. Each clause is a single imperative sentence and MUST NOT embed additional `**Given**` / `**When**` / `**Then**` markers. The `**Then**` clause MUST state a verifiable observable outcome.
   6. **Verification Mode** — `**Verification Mode**: <automated|manual|deferred>`. Exactly one per scenario, drawn from the three allowed literals (case-insensitive). `automated` means RED/GREEN executes the scenario as a failing-then-passing test; `manual` means a human verifies it via a documented step; `deferred` means verification is postponed to a later slice. `deviate plan post` rejects a missing, duplicate, or invalid mode literal.
   **Pre-write self-check**: Before writing `plan.md`, enumerate every `AC-PLAN-NNN` you produced and confirm each one carries exactly one `**Verification Mode**:` line with a legal literal. A scenario that maps to RED/GREEN tests MUST use `automated`. Do not emit a scenario without this line — the CLI cannot rescue a plan whose scenarios lack a mode.
   **Per-section required structure** (every `plan.md` MUST contain every section below, in this order, with the exact `##` header):
   1. `## Plan Summary` — bullets: Issue, Implementation Strategy, Estimated Complexity, Estimated Effort.
   2. `## Product Layer Anchors` — bullets: Flow References, Source, Release Context, Architecture Components Touched (or `None` when absent).
   3. `## Acceptance Contract` — one or more `**Scenario AC-PLAN-NNN: …**` blocks satisfying the per-scenario rules above. Every AO from the issue MUST appear at least once.
   4. `## Workstation Mapping` — per file: Current State, Changes Required, Integration Surface.
   5. `## Implementation Strategy` — phased; each phase lists Files, Approach, Verification.
   6. `## Data Flow Analysis` — narrative.
   7. `## Risk Assessment` — Markdown table with Risk / Impact / Likelihood / Mitigation columns; include a `FLOW_CONTEXT_UNAVAILABLE` row when `specs/_product/` is absent or empty.
   8. `## Security Profile` — Risk surfaces, Negative tests, Constraints (free-form prose).
   9. `## Integration Points` — bulleted list.
   10. `## Constitutional Alignment` — Architecture / Testing / Git Isolation / Product Layer bullets.
   **Forbidden patterns** (any one of these causes `PLAN_ACCEPTANCE_CONTRACT_INVALID` from `deviate plan post`):
   - Source Outline labelled `Edge Cases`, `Boundary`, `Constitutional §…`, `RLS`, `Tenant Isolation`, `Hardening`, `Security`, or any non-AO string.
   - Scenario missing `**Source Outline**`, `**Upstream Traceability**`, `**Current-Code Evidence**`, any of `**Given**` / `**When**` / `**Then**`, or the `**Verification Mode**:` line.
   - An AO from `## Acceptance Outline` not used by any AC-PLAN-NNN.
   - Two scenarios sharing the same `AC-PLAN-NNN` number, or gaps in the sequence.
   - Wrapping the plan body in any XML tag, code fence, or preamble — write raw Markdown only.
9. **HTML Artifact — optional, on-demand.** When the user wants an ADHD-friendly HTML review surface for this plan, run `/deviate-html plan` (or `deviate html plan` directly) to author `plan.html` next to `plan.md`. This command is **not** auto-invoked by `/deviate-plan`; the user decides when to ship the HTML counterpart. Skip this step entirely unless the user asks. See `src/deviate/prompts/commands/deviate-html.md` for the authoring protocol.
10. **Commit `plan.md`**: Run ``deviate plan post``. It validates and commits the plan, then advances to TASKS. The HTML counterpart (if authored) is committed separately by the user via `/deviate-html plan`'s protocol.

</execution_sequence>


<output_format_schemas>

Write the plan as `plan.md` in the issue workspace directory (adjacent to the issue file, e.g., `specs/<epic>/issues/<NNN>-<slug>/plan.md`). The file content is exactly the plan body — no preamble, no postamble, no XML wrapper tags.

**CRITICAL FORMAT RULES:**
- Use `## Section Name` headers for all sections
- Use bullet points and indented lists for structured data
- Use bold `**Label**` for field labels
- All file paths MUST be relative to the repository root
- Do NOT wrap the file content in any XML or code-fence tags

**REQUIRED STRUCTURE:**

## Plan Summary
- **Issue**: <issue_id> — <issue_title>
- **Implementation Strategy**: <1-2 sentence description of the overall approach>
- **Estimated Complexity**: <Low | Medium | High>
- **Estimated Effort**: <time estimate, e.g., 2-4 hours>

## Product Layer Anchors
- **Flow References**: <copy verbatim from issue frontmatter `flow_refs`, e.g. `[FLOW-04, FLOW-05]`>
- **Source**: `<relative path to source issue file>` (frontmatter field: `flow_refs`)
- **Release Context**: <one-line summary from `specs/_product/release-next.md` Goal section if the file exists, otherwise `N/A`>
- **Architecture Components Touched**: <list Component IDs from `specs/_product/architecture.md` §3 Components table that this issue modifies or extends; `None` if absent>

**Invariant**: Every downstream artifact (`tasks.md`, RED tests, GREEN implementation, JUDGE verdict, E2E coverage, PR description) MUST surface these `Flow References` when present and verify the requested application behavior serves them. This section is traceability context only; it never authorizes flow-catalog, release, DeviaTDD setup, skill, or workflow-ledger work.

## Acceptance Contract
**Scenario AC-PLAN-001: <observable behavior>**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `FR-NNN-ID`, `AC-NNN-ID-NN`
- **Current-Code Evidence**: `<relative path>:<symbol or line>`
- **Given**: <current, implementation-aware precondition>
- **When**: <observable trigger>
- **Then**: <verifiable outcome>
- **Verification Mode**: automated

Each `AO-NNN` MUST map to at least one complete scenario. `AC-PLAN-NNN` identifiers are the authoritative acceptance identities consumed downstream.

## Workstation Mapping
- **<file_path>**: <role in this issue — what needs to change and why>
  - **Current State**: <brief assessment of the file as-is>
  - **Changes Required**: <specific modifications needed>
  - **Integration Surface**: <interfaces, functions, or classes it connects to>
## Implementation Strategy
- **Phase 1**: <logical implementation phase — deliverable>
  - **Files**: <list of files>
  - **Approach**: <specific implementation approach>
  - **Verification**: <how to verify this phase>

## Data Flow Analysis
- Describe the data flow between components — inputs, transformations, outputs, and storage

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| <risk description> | <High/Medium/Low> | <High/Medium/Low> | <mitigation strategy> |

## Security Profile

List the risk surfaces this task touches (auth, secrets, PII, outbound HTTP,
deserialization, subprocess, file paths, SQL/ORM, eval) and the negative tests
the planner expects RED to write. Free-form prose is fine — structured parsing
is a future PR. The body of this section is stored verbatim on the task
record's `security_profile` field and read by the JUDGE prompt as supplementary
context when populating the `security_checks` manifest field.
Risk surfaces: <list the surfaces this task touches, e.g. "auth, secrets, subprocess">
Negative tests: <the negative tests RED must write, e.g. "auth bypass fails, secrets not in logs">
Constraints: <green-phase constraints, e.g. "no new dependencies without checksum, no hardcoded secrets">

## Integration Points
- **<integration point>**: <what connects here and the contract expected>

## Constitutional Alignment
- **Architecture**: <how this aligns with the three-layer architecture>
- **Testing**: <test framework, approach, and coverage considerations>
- **Git Isolation**: <how git isolation invariants apply>
- **Product Layer**: <how the implemented application behavior preserves or extends the existing user-visible flows named in `## Product Layer Anchors`; this is traceability, not a Product-layer deliverable>



</output_format_schemas>


<edge_case_handling>

| Condition | Action |
|---|---|
| ``deviate plan pre`` reports a worktree was created | ``cd`` into the printed worktree path and re-run ``deviate plan pre``. |
| ``deviate plan pre`` reports NO_UNBLOCKED_ISSUES | Halt — no issue available to plan. |
| ``deviate plan pre`` emits JSON contract (inside worktree) | Continue to step 2. |
| Issue file not found at the expected path | Search `specs/<epic>/issues/` for the matching file. If still not found, halt with ISSUE_FILE_NOT_FOUND. |
| Issue file missing `## User Stories Ledger` or `## Acceptance Outline` | Halt with INCOMPLETE_ISSUE_OUTLINE. Re-run shard/adhoc; do not invent macro intent. |
| `plan.md` lacks a complete `## Acceptance Contract` or AO traceability | Halt with `PLAN_ACCEPTANCE_CONTRACT_MISSING` or `PLAN_ACCEPTANCE_CONTRACT_INVALID`. |
| Git log or issue ledger unavailable | Proceed with file-based analysis only. Note the gap in `plan.md`. |
| `specs/constitution.md` missing | Proceed without constitutional alignment. Note the gap in `plan.md`. |
| Performance scan exceeds 200ms | Narrow the scan scope. Skip deep analysis of files not in the primary workstation list. Add a `[PERFORMANCE_NOTE]` in `plan.md`. |
| Prior plan.md already exists for this issue | Read and incorporate prior analysis. Note that this is a re-plan. |
| No prior issues or git history to analyze | Proceed with only file-based analysis. State that no prior context was found. |
| Issue frontmatter has no `flow_refs` field | Read existing flow artifacts only to infer an applicable mapping. If none resolves, emit empty flow references and continue planning the application behavior; do not create a flow-authoring or setup phase. |
| `specs/_product/` directory absent | Emit `- **Flow References**: []` under `## Product Layer Anchors` and plan only the application behavior. Do not add Product-layer or DeviaTDD setup work. |

</edge_case_handling>


<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
