---
name: deviate-shard
description: Decompose a Product Requirements Document (prd.md) into a deterministic sequence of highly decoupled, self-contained Feature Verticals (GitHub Issues) with DAG dependency topology
category: deviatdd-macro-layer
version: 1.0.0
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
1. **Input Resolution Rule**: Run `deviate shard pre` first. Parse its JSON contract from stdout. The contract carries `prd_path`, `constitution_path`, `repo_root`, `git_branch`, `epic_slug`, `feature_dir`, `issues_dir` (where to write shard files), `issues_ledger`, `next_issue_id` (the next ISS-NNN to assign), `plan_target` (absolute path for the execution manifest), and `dry_run`. The pre-script has already discovered the feature workspace — do NOT re-derive paths.
2. **Constitutional Validation Gate**: Prior to synthesizing or sharding any components, verify the presence and technical requirements defined in `specs/constitution.md` (from the contract's `constitution_path`). Every functional requirement mapping, test boundary limit, and data layer interaction must inherit compliance from the core rules of the project constitution.
3. **Pass 0 Contract Enforcement**: Scrutinize the resolved requirements payload for explicit, immutable tracking tokens (`FR-{NNN}-{ID}` and `AC-{NNN}-{ID}-{NN}`). If these tokens are missing, ambiguous, or malformed, trigger a `MALFORMED_PRD_CONTRACT` condition, suppress issue generation entirely, halt the execution pipeline, and log the precise structural gaps preventing deterministic parsing.
4. **The Vertical Slice Mandate — Anti-Pattern Gate**: A vertical slice is NOT a 1:1 mapping to a single Functional Requirement. One vertical slice encompasses one or more related FRs and ACs (or zero FRs for enabling slices such as tooling, infrastructure, or refactoring) that together form a complete, user-testable feature. You are strictly forbidden from generating layered shards (e.g., decoupling an architectural feature into separate database migration, API endpoint, or UI tasks). Every single issue generated MUST represent a whole feature that cuts through all required layers (database, API, business logic, interface) to deliver a tangible, end-to-end verification route. **Named anti-pattern — a "state" issue, "data model" issue, "database schema" issue, or any single-layer issue is a HORIZONTAL slice and is strictly forbidden.** If an issue title or scope describes only one architectural layer (state, API, UI, data, config), it is invalid. Group related FRs (when present) into cohesive feature clusters, then shard those clusters. Never shard requirements along horizontal component lines. **Litmus test: can a user or system verify this feature end-to-end WITHOUT any other shard existing? If not, it is a horizontal slice and must be re-clustered with the layers it depends on. Enabling slices (zero FRs) are exempt from this litmus test but must still describe a complete, independently verifiable capability.**
5. **Incremental Bootstrapping Principle**: Shards must be ordered to mirror progressive execution paths. Shard N must deliver a complete, end-to-end vertical feature that establishes the minimal behavioral foundation that Shard N+1 extends. **The "foundation" is a working feature, not a layer.** You MUST NOT generate a shard whose primary purpose is to establish data schema, state management, API scaffolding, or configuration — those are horizontal slices disguised as foundational work. Every shard's value is measured by the user-visible behavior it unlocks, not by the infrastructure it lays down.
6. **Context Packaging Invariant**: Each generated issue file behaves as an immutable context packet for a downstream automated agent. You must programmatically inject the precise entities it mutates (referencing data contracts from the PRD), the explicit boundaries of what it must NOT do (Defensive Exclusions), and the target testing hooks required to satisfy Acceptance Test-Driven Development (ATDD).
7. **Feature Slug & Relative Path Normalization**: Resolve the feature folder path index from the execution context matching the layout pattern `specs/{NNN}-{FEATURE_SLUG}/`. Every single path output, file target, test workspace module, or script reference written into the issue bodies must be strictly written as a relative path calculated from the workspace root directory (e.g., `src/core/runner.py`). Absolute local machine structures are completely forbidden.
8. **Issue ID Assignment & Dependency Topology**: Assign each shard a sequential `issue_id` starting from `next_issue_id` in the contract (e.g., `ISS-004`, `ISS-005`, ...). Build a pristine Directed Acyclic Graph (DAG) mapping issue relationships. Sequential blockages must use string-based `blocked_by` frontmatter arrays referencing other shards' `issue_id` values (e.g., `blocked_by: ["ISS-004"]`). Lateral knowledge overlaps must leverage the `coordinates_with` array. Execute an internal validation pass to catch loop states; if any circular dependency chain is detected, trigger a `TOPOLOGY_LOOP_FAULT` and abort execution.
9. **Execution Lifecycle Protocols (Internal ICoT)**: Before emitting file payloads, execute four sequential mental loops inside an internal engineering ledger block (`## [INTERNAL_ICOT_LEDGER]`):
    - Pass 1 (Topological Layout): Group related FR-{NNN}-{ID} tokens into cohesive feature clusters. Each cluster becomes one vertical slice. A slice may contain zero or more FRs (enabling/infrastructure/tooling slices may have zero). Verify cumulative coverage: every FR-{NNN}-{ID} token from the PRD must appear in at least one slice. Map each cluster to its structural architectural workstations and lay out the execution graph across the Macro ➔ Meso ➔ Micro layer boundaries.
   - Pass 2 (Boundary Demarcation Pass): Establish the explicit defensive exclusion criteria for every vertical slice to prevent optimization drift. Each slice must be self-contained and large enough to warrant independent specification.
    - Pass 3 (Horizontal Slice Audit): For every candidate slice, enumerate the layers it touches (database, API, business logic, UI/interface). If the slice contains one or more FRs and touches only ONE layer, mark it as HORIZONTAL_SLICE_DETECTED and re-cluster with adjacent FRs until it cuts through at least two layers with complete end-to-end behavior. Enabling slices (zero FRs) are exempt from the multi-layer requirement but must still deliver a complete, independently verifiable capability. Log any slices that failed this audit and how they were resolved.
   - Pass 4 (Verification Mapping Pass): Pair every tracked acceptance criterion token (`AC-{NNN}-{ID}-{NN}`) within the slice with an executable, copy-pasteable terminal verification command block (`## [DEMONSTRATION_PATH]`).
10. **Template Engine Safety**: Preserve all double-curly variable syntax markers or configuration properties as inert string values using raw, literal string encapsulation to guarantee zero parsing or compile-time syntax errors within local dotfile template managers like Chezmoi or Jinja.
11. **Output Format Constraint**: Present the final response exclusively using human-readable Markdown syntax headers, bullet configurations, and text patterns. Do not encapsulate or wrap output blocks within XML structural boundaries. Ensure frontmatter blocks generated within inner file schema emissions utilize explicit line-level escaping or safe literal formatting so they do not interrupt or prematurely terminate parent formatting lines.
12. **Local Issue Registry Invariant**: All issues are registered in the local append-only `specs/issues.jsonl` ledger. The post-script handles registration inline — no external scripts are required.

</system_instructions>

<output_format_schemas>

## [INTERNAL_ICOT_LEDGER]
```text
Pass 1 (Topological Layout): [Trace tracking tokens to repo path workstations; group FRs into clusters (zero or more per slice); verify cumulative coverage across all slices]
Pass 2 (Boundary Demarcation): [Isolate inclusion vs exclusion constraints for each feature slice]
Pass 3 (Verification Mapping): [Verify that each AC maps to an explicit end-to-end bash execution path validation block]
```

## [SHARD_GENERATION_MANIFEST]
### [COMPILATION_METADATA]
- **Target Feature Workspace**: `specs/{NNN}-{FEATURE_SLUG}/`
- **Upstream PRD Baseline**: `specs/{NNN}-{FEATURE_SLUG}/prd.md`
- **Total Derived Feature Verticals**: [Integer count of shards created]
- **Status**: DETERMINISTIC_SYNTHESIS_COMPLETE

### [SUMMARY_TOPOLOGY_TABLE]
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
Execute the Internal ICoT (Pass 1-4) to cluster related FRs into vertical slices (zero or more FRs per slice; enabling slices may carry zero). Verify cumulative FR coverage across all slices — every FR from the PRD must appear in at least one slice. Write the ICoT ledger as `## [INTERNAL_ICOT_LEDGER]` in the output.

For each vertical slice:
1. Group one or more related FRs (or zero for enabling slices such as tooling, infrastructure, or refactoring) into a cohesive, independently verifiable feature
2. Ensure the slice cuts through ALL layers (database, API, logic, UI) — enabling slices with zero FRs are exempt from this requirement
3. Verify the slice is non-trivial — it must warrant its own spec + plan phase
4. Map blocked_by and coordinates_with dependencies across slices
</step>

<step id="issue_generation">
For each vertical slice, generate a shard issue markdown file. Each file must include:
- YAML frontmatter with `title`, `labels`, `source_file`, `blocked_by`, `coordinates_with`, `issue_id`
- `## [SYSTEM_TOPOLOGY_MAPPING]` — epic domain, local file path, workstation paths
- `## [THE_PROBLEM_CONTRACT]` — narrative of the user/system journey
- `## [SCOPE_BOUNDARIES]` — Hard Inclusions and Defensive Exclusions
- `## [UPSTREAM_REQUIREMENT_TRACING]` — FR and AC tokens
- `## [MULTI_TIERED_VERIFICATION_TARGETS]` — unit and integration test paths
- `## [DEMONSTRATION_PATH]` — exact bash commands for end-to-end verification

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
Write the execution manifest JSON to `plan_target` (absolute path from the contract). The manifest must include:
```json
{
  "task_id": "shard",
  "files_modified": [
    {
      "path": "<issues_dir>/000-<slug>.md",
      "action": "created",
      "purpose": "Vertical slice issue for <title>"
    }
  ],
  "commit_subject": "docs(<epic_id>): shard vertical slices",
  "commit_body": "Generated <N> vertical shards from PRD with DAG dependency topology",
  "validation": {
    "lint": "SKIP",
    "typecheck": "SKIP",
    "tests": "SKIP",
    "summary": "Shard generation complete — <N> issues created"
  },
  "reasoning": {
    "approach": "FR clustering into vertical slices with DAG topology",
    "key_decisions": [
      {"decision": "slice grouping strategy", "rationale": "vertical slices per user-testable feature"}
    ]
  }
}
```
</step>

<step id="post_script">
Run the post-script to register issues in the ledger, stage files, and commit:
```bash
deviate shard post "$PLAN_TARGET"
```

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

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

