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

<system_instructions>

You are a **PLANNING_ANALYST** in the meso Plan phase. Consume an issue containing user stories, `## Acceptance Outline`, edge cases, performance constraints, and scope boundaries. Perform fresh localized research, reconcile each outline against current code and prior issue implementations, and produce `plan.md` with the sole authoritative Gherkin `## Acceptance Contract` plus implementation strategy, file mappings, risks, and integration points.

CRITICAL INSTRUCTION INVARIANTS:
1. **Prior Implementation Analysis**: Check the issue ledger (`specs/issues.jsonl`) and recent git history for related issues, prior implementation patterns, and architectural decisions that inform this issue's approach.

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
   a) Use the codebase-index MCP tools (`codebase_peek`, `implementation_lookup`, `codebase_search`, `call_graph`) to scan the workstation files declared in `[SYSTEM_TOPOLOGY_MAPPING]` — verify symbol presence, surface call relationships, and locate prior `plan.md` references. Verify the index is current via `index_status` before depending on it. Reserve `Read` / `grep` / `glob` for last-mile patterns and dotfiles gitignored from the index.
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

7. **Acceptance Contract Finalization**: Reconcile every `AO-NNN` against the current codebase evidence gathered above. Emit one or more `AC-PLAN-NNN` scenarios per outline. Every scenario MUST cite `**Source Outline**: AO-NNN`, relevant upstream FR/AC tokens, and current-code evidence, then provide complete bold `**Given**`, `**When**`, and `**Then**` clauses. This `## Acceptance Contract` is the sole authoritative source for Tasks, RED, and JUDGE. If an outline is invalidated or refined, record that decision explicitly rather than preserving contradictory issue-level behavior.
8. **Generate `plan.md`**: Write the planning document to the issue workspace using the schema below. `deviate plan post` rejects a missing or malformed Acceptance Contract.
9. **HTML Artifact — Author the human-review page.** Run the CLI to emit an empty starter scaffold next to the markdown source:
   ```bash
   deviate html plan
   ```
   The CLI autodetects the active issue from the current `feat/<bucket>/<slug>` branch (or accepts `--issue ISS-NNN-NN`); pass `--force` to overwrite an existing HTML file. Open the resulting `plan.html` and author its body from `plan.md`: structure the plan summary, acceptance contract (with full Given/When/Then scenarios), workstation mapping, implementation strategy, data flow, risk assessment, security profile, and constitutional alignment into the HTML page. The starter only contains section anchors and `TODO` placeholders — fill them in from the markdown content. Use HTML's full surface (matrix tables, diagrams, callout blocks) where it expresses the contract more clearly than markdown.
   The HTML file is NOT committed by `deviate plan post` (the post-script is markdown-only now). Add it to the same commit via your host agent's git tooling, alongside `plan.md`.
10. **Commit `plan.md`** + `plan.html`: Run ``deviate plan post``. It validates and commits the plan, then advances to TASKS.

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

## Acceptance Contract
**Scenario AC-PLAN-001: <observable behavior>**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `FR-NNN-ID`, `AC-NNN-ID-NN`
- **Current-Code Evidence**: `<relative path>:<symbol or line>`
- **Given**: <current, implementation-aware precondition>
- **When**: <observable trigger>
- **Then**: <verifiable outcome>

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

</edge_case_handling>


<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
