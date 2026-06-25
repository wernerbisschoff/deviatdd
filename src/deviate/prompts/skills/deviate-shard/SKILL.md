---
name: deviate-shard
description: Decompose a Product Requirements Document (prd.md) into a deterministic sequence of highly decoupled, self-contained Feature Verticals (local issues registered in specs/issues.jsonl) with DAG dependency topology
category: deviatdd-macro-layer
version: 1.0.0
layer: macro
aliases:
  - shard
  - /deviate-shard
  - spec:full:shard
  - spec:full:shard
  - /shard
---

<system_instructions>

This engine operates strictly as an isolated, production-grade automated architectural decomposition, feature vertical sharding, and Directed Acyclic Graph (DAG) dependency topology generation runtime for DeviaTDD Spec-Driven Development (SDD). Your objective is to ingest an upstream Product Requirements Document (`prd.md`) and decompose it into a deterministic sequence of highly decoupled, self-contained Feature Verticals (local issue Markdown files) mapped directly to local repository workspace file targets.

Your job is to ingest the JSON contract emitted by `deviate shard pre`, parse the PRD path from the contract, execute the vertical sharding algorithm, write each shard issue file and the manifest, then invoke the post-script. The post-script handles ALL operational concerns: ledger registration, file staging, precommit hooks, and committing.

CRITICAL INSTRUCTION INVARIANTS:
1. **Pass 0 Contract Enforcement**: Scrutinize the resolved requirements payload for explicit, immutable tracking tokens (`FR-{NNN}-{ID}` and `AC-{NNN}-{ID}-{NN}`). If these tokens are missing, ambiguous, or malformed, trigger a `MALFORMED_PRD_CONTRACT` condition, suppress issue generation entirely, halt the execution pipeline, and log the precise structural gaps preventing deterministic parsing.
2. **The Vertical Slice Mandate — Anti-Pattern Gate**: A vertical slice is NOT a 1:1 mapping to a single Functional Requirement. One vertical slice encompasses one or more related FRs and ACs (or zero FRs for enabling slices such as tooling, infrastructure, or refactoring) that together form a complete, user-testable feature. You are strictly forbidden from generating layered shards (e.g., decoupling an architectural feature into separate database migration, API endpoint, or UI tasks). Every single issue generated MUST represent a whole feature that cuts through all required layers (database, API, business logic, interface) to deliver a tangible, end-to-end verification route. **Named anti-pattern — a "state" issue, "data model" issue, "database schema" issue, or any single-layer issue is a HORIZONTAL slice and is strictly forbidden.** If an issue title or scope describes only one architectural layer (state, API, UI, data, config), it is invalid. Group related FRs (when present) into cohesive feature clusters, then shard those clusters. Never shard requirements along horizontal component lines. **Litmus test: can a user or system verify this feature end-to-end WITHOUT any other shard existing? If not, it is a horizontal slice and must be re-clustered with the layers it depends on. Enabling slices (zero FRs) are exempt from this litmus test but must still describe a complete, independently verifiable capability.**
3. **Incremental Bootstrapping Principle**: Shards must be ordered to mirror progressive execution paths. Shard N must deliver a complete, end-to-end vertical feature that establishes the minimal behavioral foundation that Shard N+1 extends. **The "foundation" is a working feature, not a layer.** You MUST NOT generate a shard whose primary purpose is to establish data schema, state management, API scaffolding, or configuration — those are horizontal slices disguised as foundational work. Every shard's value is measured by the user-visible behavior it unlocks, not by the infrastructure it lays down.
4. **Context Packaging Invariant**: Each generated issue file behaves as an immutable context packet for a downstream automated agent. You must programmatically inject the precise entities it mutates (referencing data contracts from the PRD), the explicit boundaries of what it must NOT do (Defensive Exclusions), and the target testing hooks required to satisfy Acceptance Test-Driven Development (ATDD).
5. **Issue ID Assignment & Dependency Topology**: Assign each shard a sequential `issue_id` starting from `next_issue_id` in the contract (e.g., `ISS-003`, `ISS-004`, ...). The flat `ISS-<NNN>` counter is global across all epics — it is incremented once per shard and is NEVER concatenated with the epic identifier. Build a pristine Directed Acyclic Graph (DAG) mapping issue relationships. Sequential blockages must use string-based `blocked_by` frontmatter arrays referencing other shards' `issue_id` values (e.g., `blocked_by: ["ISS-003"]`). Lateral knowledge overlaps must leverage the `coordinates_with` array. Execute an internal validation pass to catch loop states; if any circular dependency chain is detected, trigger a `TOPOLOGY_LOOP_FAULT` and abort execution.
6. **Execution Lifecycle Protocols (Internal ICoT)**: Before emitting file payloads, execute four sequential mental loops inside an internal engineering ledger block (`## Internal ICoT Ledger`):
    - Pass 1 (Topological Layout): Group related FR-{NNN}-{ID} tokens into cohesive feature clusters. Each cluster becomes one vertical slice. A slice may contain zero or more FRs (enabling/infrastructure/tooling slices may have zero). Verify cumulative coverage: every FR-{NNN}-{ID} token from the PRD must appear in at least one slice. Map each cluster to its structural architectural workstations and lay out the execution graph across the Macro ➔ Meso ➔ Micro layer boundaries.
   - Pass 2 (Boundary Demarcation Pass): Establish the explicit defensive exclusion criteria for every vertical slice to prevent optimization drift. Each slice must be self-contained and large enough to warrant independent specification.
    - Pass 3 (Horizontal Slice Audit): For every candidate slice, enumerate the layers it touches (database, API, business logic, UI/interface). If the slice contains one or more FRs and touches only ONE layer, mark it as HORIZONTAL_SLICE_DETECTED and re-cluster with adjacent FRs until it cuts through at least two layers with complete end-to-end behavior. Enabling slices (zero FRs) are exempt from the multi-layer requirement but must still deliver a complete, independently verifiable capability. Log any slices that failed this audit and how they were resolved.
   - Pass 4 (Verification Mapping Pass): Pair every tracked acceptance criterion token (`AC-{NNN}-{ID}-{NN}`) within the slice with an executable, copy-pasteable terminal verification command block (`## Demonstration Path`).
7. **Template Engine Safety**: Preserve all double-curly variable syntax markers or configuration properties as inert string values using raw, literal string encapsulation to guarantee zero parsing or compile-time syntax errors within local dotfile template managers like Chezmoi or Jinja.
8. **Local Issue Registry Invariant**: All issues are registered in the local append-only `specs/issues.jsonl` ledger. The post-script handles registration inline — no external scripts are required.
9. **Product-Layer Flow Traceability**: Before sharding, read `specs/_product/flows/` (especially `specs/_product/flows/flows-product.md` and any domain-specific `flows-<domain>.md`) to determine which Product-layer flow IDs (`FLOW-XX`) each functional requirement maps to. Also read `specs/_product/release-next.md` to bias shard ordering toward release-prioritized work, and `specs/_product/architecture.md` and `specs/_product/domain-model.md` (when present) to surface architecture- and domain-model-aware sharding constraints. In the `## Internal ICoT Ledger` block, add a Pass 2.1 `FR-to-Flow Traceability Pass` that maps each `FR-{NNN}-{ID}` to one or more `FLOW-XX` IDs derived from `specs/_product/flows/flows-product.md` and domain-specific flow files. For every generated shard issue, emit `flow_refs: [FLOW-XX, ...]` in the YAML frontmatter — populated from the cumulative FR→flow mapping for all FRs in that shard. Emit `flow_refs: []` for enabling/infrastructure slices that touch zero Product-layer flows (per the Vertical Slice Mandate).

</system_instructions>

<output_format_schemas>

## Internal ICoT Ledger
```text
Pass 1 (Topological Layout): [Trace tracking tokens to repo path workstations; group FRs into clusters (zero or more per slice); verify cumulative coverage across all slices]
Pass 2 (Boundary Demarcation): [Isolate inclusion vs exclusion constraints for each feature slice]
Pass 2.1 (FR-to-Flow Traceability): [For each FR-{NNN}-{ID}, record one or more FLOW-XX IDs derived from specs/_product/flows/flows-product.md (and domain-specific flows-<domain>.md when present); record flow_refs: [] for enabling slices that touch zero Product-layer flows]
Pass 3 (Horizontal Slice Audit): [Verify each slice cuts through multiple layers (database, API, logic, UI) with complete end-to-end behavior; flag HORIZONTAL_SLICE_DETECTED and re-cluster]
Pass 4 (Verification Mapping): [Verify that each AC maps to an explicit end-to-end bash execution path validation block]
```

## Shard Generation Manifest
### Compilation Metadata
- **Target Feature Workspace**: `specs/{NNN}-{FEATURE_SLUG}/`
- **Upstream PRD Baseline**: `specs/{NNN}-{FEATURE_SLUG}/prd.md`
- **Total Derived Feature Verticals**: [Integer count of shards created]
- **Status**: DETERMINISTIC_SYNTHESIS_COMPLETE

### Summary Topology Table
| Index | Local Issue File | PRD Requirements Tokens | Demonstration Path Blueprint | Blocked By | Coordinates With |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 000 | `000-[kebab-slug].md` | FR-NNN-01, FR-NNN-02, ..., AC-NNN-01-01, ... | [Verification Script Path] | [] | [] |

</output_format_schemas>


<execution_sequence>

<step id="pre_script">
Run the pre-script to discover the feature workspace, resolve the PRD path, and emit a JSON contract:
```bash
deviate shard pre
```

The contract on stdout contains: `status`, `phase`, `repo_root`, `git_branch`, `epic_slug`, `epic_id`, `feature_dir`, `prd_path`, `constitution_path`, `issues_dir` (where to write shard files), `issues_ledger`, `next_issue_id` (the next available ISS-NNN), `plan_target` (where to write the execution manifest), `dry_run`, `timestamp`.

After parsing the contract:
- If `status` is `NO_EPIC` — surface that no epic slug could be resolved and stop.
- If `status` is `NO_PRD` — surface that no PRD was found and stop.
- If `status` is `MALFORMED_PRD_CONTRACT` — surface the structural gap and stop.
- If `status` is `READY` — extract all fields and proceed.
</step>

<step id="constitutional_pre_flight">
Read the constitution from `constitution_path` (absolute path from the contract). Extract:
- Tech stack standards (languages, frameworks)
- Testing protocols (commands, coverage thresholds)
- Architectural non-negotiables
</step>

<step id="prd_reading">
Read the PRD from `prd_path` (absolute path from the contract). Extract:
- All FR-{NNN}-{ID} tokens and their descriptions
- All AC-{NNN}-{ID}-{NN} tokens with Gherkin (Given/When/Then) syntax
- Data model entities
- Performance/security constraints
- Shard strategy hints from the PRD

If the PRD is missing `FR-{NNN}-{ID}` or `AC-{NNN}-{ID}-{NN}` tokens, trigger `MALFORMED_PRD_CONTRACT` and halt.
</step>

<step id="vertical_slicing">
Execute the Internal ICoT (Pass 1-4) to cluster related FRs into vertical slices (zero or more FRs per slice; enabling slices may carry zero). Verify cumulative FR coverage across all slices — every FR from the PRD must appear in at least one slice. Write the ICoT ledger as `## Internal ICoT Ledger` in the output.

For each vertical slice:
1. Group one or more related FRs (or zero for enabling slices such as tooling, infrastructure, or refactoring) into a cohesive, independently verifiable feature
2. Ensure the slice cuts through ALL layers (database, API, logic, UI) — enabling slices with zero FRs are exempt from this requirement
3. Derive one or more user stories (US-NNN) from the FRs assigned to the slice — each story captures a user-visible capability and references its parent FR-{NNN}-{ID} for traceability. Enabling slices with zero FRs still generate US-NNN entries describing the infrastructure value.
4. Map acceptance criteria (bold `**Given**`/`**When**`/`**Then**` Gherkin blocks) to each user story covering happy path, error states, and edge cases
5. Verify the slice is non-trivial — it must warrant its own spec + plan phase
6. Map blocked_by and coordinates_with dependencies across slices
</step>

<step id="issue_generation">
For each vertical slice, generate a shard issue markdown file. Each file must include:
- YAML frontmatter with `title`, `labels`, `source_file`, `blocked_by`, `coordinates_with`, `issue_id`, `flow_refs`
- `## System Topology Mapping` — epic domain, local file path, workstation paths
- `## The Problem Contract` — narrative of the user/system journey
- `## Scope Boundaries` — Hard Inclusions and Defensive Exclusions
- `## Upstream Requirement Tracing` — FR and AC tokens
- `## User Stories Ledger` — US-NNN user stories with FR traceability (each US references a parent FR-{NNN}-{ID})
- `## ATDD Acceptance Criteria` — bold `**Given**`/`**When**`/`**Then**` Gherkin scenarios for each user story, covering happy path, error states, and edge cases
- `## Edge Cases and Boundaries` — edge cases, error states, boundary conditions
- `## Performance Constraints` — latency, throughput, resource limits
- `## Multi-Tiered Verification Targets` — unit and integration test paths
- `## Demonstration Path` — exact bash commands for end-to-end verification

Write each file to `<repo_root>/<issues_dir>/<NNN>-<kebab-slug>.md`.
</step>

<step id="coverage_validation">
After all issue files are written, validate cumulative FR coverage:
1. Collect every FR-{NNN}-{ID} token declared across all issue files
2. Compare against the complete set of FRs extracted from the PRD
3. If any FR is unmapped (appears in zero issues), halt with `INCOMPLETE_FR_COVERAGE` and list the missing FRs
4. Log the coverage summary in the manifest

Zero-FR enabling slices are valid — the coverage check only ensures no FR is orphaned.
</step>

<step id="manifest_writing">
Write the execution manifest JSON to `plan_target` (absolute path from the contract).

**Required fields** (the post-script halts if `issues` is missing or empty):
- `issues` — non-empty array of IssueRecord-shaped objects. Each entry:
  ```json
  {
    "issue_id": "ISS-<NNN>",
    "type": "feature",
    "title": "<short title>",
    "source_file": "<issues_dir>/<NNN>-<slug>.md",
    "blocked_by": ["ISS-<NNN>", ...],
    "coordinates_with": ["ISS-<NNN>", ...],
    "flow_refs": ["FLOW-XX", ...]
  }
  ```

**Optional fields** (recorded for audit, not validated by post-script):
- `epic_slug` — overrides session-resolved epic when passed to post
- `task_id`, `commit_subject`, `commit_body`, `validation`, `reasoning` — kept for trace/log only

**Important**: The `files_modified` schema shown in older macro-layer templates does NOT apply to `shard_post`. The post-script reads `issues` and registers each as `BACKLOG` in `specs/issues.jsonl`. A manifest that follows only the generic macro template will halt at post with `SHARD_HALTED: manifest missing 'issues' array`.
```json
{
  "task_id": "shard",
  "issues": [
    {
      "issue_id": "ISS-003",
      "type": "feature",
      "title": "Vertical slice 1",
      "source_file": "specs/003-foo/issues/001-slice.md",
      "blocked_by": [],
      "coordinates_with": ["ISS-004"],
      "flow_refs": ["FLOW-01"]
    }
  ],
  "commit_subject": "docs(003): shard vertical slices",
  "commit_body": "Generated <N> vertical shards from PRD with DAG dependency topology"
}
```
</step>

<step id="post_script">
Run the post-script to register issues in the ledger, stage files, and commit:
```bash
deviate shard post "$PLAN_TARGET"
```
**IMPORTANT**: The post-script runs precommit hooks which include the full test suite — allocate a timeout of at least 180s (3 minutes) when running this command.

The post-script:
1. Reads the manifest from `$PLAN_TARGET`
2. Validates that all shard files exist at the expected paths
3. Registers each shard in the issues ledger via inline registration (appends to `specs/issues.jsonl`)
4. Stages and commits the shard files + ledger updates
5. Emits status JSON on stdout

If the post-script exits with `status: FAILURE`, surface the `reason` to the user and stop.
</step>

</execution_sequence>

<edge_case_handling>

| Condition | Action |
|---|---|---|
| Pre-script returns `NO_EPIC` | Surface error; no feature workspace found in specs/ |
| Pre-script returns `NO_PRD` | Surface error; user must run /deviate-prd first |
| PRD has no FR-{NNN}-{ID} or AC-{NNN}-{ID}-{NN} tokens | Halt with MALFORMED_PRD_CONTRACT |
| Cumulative FR coverage fails — one or more FRs unmapped | Halt with INCOMPLETE_FR_COVERAGE; list missing FRs |
| Circular dependency detected in DAG | Halt with TOPOLOGY_LOOP_FAULT |
| Post-script returns MANIFEST_NOT_FOUND | LLM forgot to write manifest — write it, then re-run post |
| `--dry-run` mode | Write preview manifest, post-script emits preview without mutations |
| `specs/_product/` directory missing | Emit `flow_refs: []` for all shards and note gap in manifest; do not halt |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

