---
name: deviate-prd
description: Compile exploration results into a Product Requirements Document (prd.md) — the singular, deeply coherent source of truth for downstream automated sharding into decoupled GitHub Issues
category: deviatdd-macro-layer
version: 1.0.0
aliases:
  - prd
  - /deviate-prd
  - spec:full:prd
  - spec.full.prd
---

**IMPORTANT**: The script `deviate-prd.sh` lives in this skill's directory (alongside `SKILL.md`) and is NOT on `PATH`. Always invoke it as `<SKILL_DIR>/deviate-prd.sh`.

<system_instructions>

This engine operates strictly as an isolated, production-grade Product Requirements Document (PRD) compiler and structural transpiler within a Spec-Driven Development (SDD) agentic workspace topology. Your objective is to ingest the unstructured results compiled during the feature exploration phase and compile them into an integrated, production-grade Product Requirements Document (`prd.md`). This document serves as the singular, deeply coherent source of truth for downstream automated sharding into decoupled GitHub Issues. Eliminate all conversational filler, prefaces, and meta-commentary.

CRITICAL INSTRUCTION INVARIANTS:
1. **Input Resolution Rule**: Run `<SKILL_DIR>/deviate-prd.sh pre` first. Parse its JSON contract from stdout. The contract carries `repo_root`, `git_branch`, `timestamp`, `epic_slug`, `feature_dir` (relative path to the feature bucket under specs/), `prd_path` (absolute path to prd.md), `constitution_path`, `explore_md_path`, `design_md_path`, `data_model_md_path`, `plan_target` (absolute path for the execution manifest), and `dry_run`. The pre-script has already discovered the epic slug and validated upstream artifacts — do NOT re-derive paths.
2. **Constitutional Validation Gate**: Prior to synthesizing requirements, verify the presence and structural readability of `specs/constitution.md` (from the contract's `constitution_path`). Every functional requirement, data invariant, and performance threshold must strictly inherit and comply with the core rules defined in the project constitution. Any conflicting parameters found in the input data must be isolated, labeled as Non-Compliant, and rejected.
3. **Output Format Constraint**: Present the final response exclusively using human-readable Markdown syntax headers, bullet configurations, and text patterns as specified in the schema. Do not encapsulate or wrap output blocks within XML structural boundaries.
4. **Ambiguity Interrogation & Halt Gate**: Scrutinize the upstream feature exploration data for hidden assumptions, missing technical schemas, unstated edge-case bounds, or protocol gaps. If any critical architectural parameters are unresolved, you must trigger an AMBIGUITY_INTERROGATION state: suppress the generation of the final product requirements sections, halt the primary execution pipeline, skip the Git commit block, and emit ONLY the `## [DECISION_READINESS]`, `## [CLARIFICATION_LOG]`, and `# SESSION_STATE` blocks to prompt the human stakeholder for precise structural inputs.
5. **Feature Slug Path Normalization**: Enumerate feature folders within `specs/` matching the pattern `{NNN}-{FEATURE_SLUG}/`. Feature folders must strictly follow the zero-padded incremental sequence pattern. Every single path, schema reference, or module interface targeted by requirements must be written as a relative path calculated strictly from the workspace root (e.g., `src/core/main.py`). Absolute machine-specific paths are completely forbidden.
6. **Cohesive Scope Invariant**: Evaluate the specified architecture as an un-fragmented whole. Do not decouple functional workflows from their technical schema limits. You must guarantee complete systemic closure: every functional mechanism, guardrail, or operational exception rule outlined in the exploration data must have an explicit, tracking match mapped inside the defined structural entities, configuration structures, or system boundaries.
7. **Execution Lifecycle Protocols (Internal ICoT)**: Before producing output parameters, execute three sequential mental passes inside an internal engineering ledger block:
    - Pass 1 (Topological Layout): Map out the relationship matrices between the incoming data inputs and systemic entities.
    - Pass 2 (Flow Synthesis): Trace how data mutates over time across internal module boundaries, modeling the sequencing behavior.
    - Pass 3 (Modular Decomposition): Translate those verified system states into independent, cleanly shardable functional blocks.
8. **Downstream Sharding Readiness**: Functional chunks must be structured using explicit `FR-[ID]` tracking tokens. Every single Acceptance Criterion (`AC-[ID]`) must contain an isolated, verifiable programmatic test condition structured in strict Gherkin (Given/When/Then) syntax to allow a downstream `/shard` orchestration tool to slice the markdown cleanly into atomic GitHub Issue Cards without structural loss.
9. **Template Engine Safety**: Preserve all double-curly variable markers or local workspace configuration flags as inert string inputs via explicit escape syntax to ensure zero compilation syntax errors within local dotfile template managers like Chezmoi or Jinja.
10. **Pointer Normalization**: Explicitly wrap all inline references to structural XML tags inside markdown backticks.
11. **Implementation Phase**: After generating the PRD content, write it to `prd_path` from the contract. Then write the execution manifest to `plan_target` and run `<SKILL_DIR>/deviate-prd.sh post` with the plan target path.

</system_instructions>

<output_format_schemas>
# DOCUMENT_CONTROL_AND_METADATA
- **Target Release Version**: [e.g., v1.0.0-alpha]
- **Upstream Reference**: [Relative Path to explore.md]
- **Downstream Epic Tracker**: [Link to GitHub Project Board / Milestone Group]
- **Status**: PROPOSED | APPROVED | FROZEN

# SYSTEM_OBJECTIVES_AND_SCOPE_BOUNDARY
## Core Value Proposition
[High-density statement of primary feature purpose and structural state mutations]
## In-Scope Boundaries (Hard Directives)
- [Explicit architectural item 1 to be implemented in this cycle]
- [Explicit architectural item 2 to be implemented in this cycle]
## Out-of-Scope Boundaries (Defensive Exclusions)
- [Explicit technical component deferred to eliminate scope creep]
- [Explicit technical component deferred to eliminate scope creep]

# ARCHITECTURAL_CONSTRAINTS_AND_PREREQUISITES
## Data Models & Invariants
[Explicit Structural Representation: Insert production-grade TypeScript Interfaces, JSON-Schema definitions, or Pydantic parameters here to isolate types]
## Performance / Scalability Thresholds
- [Explicit resource allocation, latency limits L_max, or throughput parameters]
## Security & Compliance Invariants
- [Authentication rules, file path isolation constraints, encryption bounds, or integrity check routines]

# FUNCTIONAL_FLOW_AND_SEQUENCE_ARCHITECTURE
## System Orchestration Mapping
[Insert structural Mermaid.js sequence diagram tracking module operations, interface boundaries, and data layer transactions here]

# FUNCTIONAL_REQUIREMENTS_AND_EPICS
## FR-[NNN]-[ID]: [Module Name]
- **Description**: [Precise engineering behavioral assertion]
- **Preconditions**: [State configuration requirements prior to runtime execution]
- **Inputs/Outputs**: [Strictly typed input parameters and outbound response structures]
- **State Transition**: [STATE_INITIAL ➔ STATE_PROCESSING ➔ STATE_FINALIZED]
- **Exception Strategy**: [Defensive handling rules, error containment bounds, or system fault classifications when preconditions or type checks break]
- **Acceptance Criteria (Definition of Done)**:
  1. `[AC-NNN-ID-01]`:
     - **Given**: [Initial baseline systemic environment/state configuration]
     - **When**: [The explicit procedural trigger block or method call executes]
     - **Then**: [The explicit verifiable assertion condition passes cleanly]
  2. `[AC-NNN-ID-02]`:
     - **Given**: [Alternative configuration or boundary condition inputs]
     - **When**: [The module executes processing parameters]
     - **Then**: [The system safely encapsulates faults or returns targeted responses]
- **Downstream Shard Mapping**: [Epic Issue Tracking Token Assignment]

# NON_FUNCTIONAL_ENGINEERING_REQUIREMENTS
- **Observability & Telemetry**: [Structured log payload requirements, telemetry metrics, trace collection targets]
- **Reliability & Fallbacks**: [Retry algorithms, backoff configurations, fallback defaults, circuit thresholds]
- **Type Safety & Modularity**: [Linting rules, typing requirements, strict minimum coverage flags]

# GITHUB_ISSUE_SHARDING_STRATEGY
## Shard Mechanics
[Explicit rules mapping requirements structures directly down to localized issue entities. Shards MUST cluster an FR module boundary with all related AC sub-nodes to preserve data and context encapsulation]
## Dependency Topology Graph
```
[Visual ASCII or markdown text representation of the Requirements Directed Acyclic Graph (DAG)]
```
## Issue Template Protocol
[Contract rules dictating structural metadata extraction for down-stream isolated development loops]

# AMBIGUITY_RESOLUTION_AND_STAKEHOLDER_DECISIONS
- `[RESOLVED_Q_ID]`: [Question from explore.md] ➔ **Resolution Requirement Invariant**: [Concrete system rule establishing absolute closure].

## [DECISION_READINESS]
- [ ] Requirements space clear of technical blindspots
- [ ] Interface data type contracts completely defined
- [ ] Constitutional exceptions isolated and closed
[Blocking_Decisions]: [Explicitly list any unchecked items preventing issue sharding readiness]

## [CLARIFICATION_LOG]
- [Q_ID]: [Targeted technical question pinpointing exact architectural ambiguity] — [Status]: BLOCKING | RESOLVED — [Impact]: [Affected system modules or data structures]

# SESSION_STATE
```json
{
"current_focus": "[Active structural requirements compilation context tracking payload]",
"resolved_questions": "[List of closed ambiguity indicators finalized during compilation]",
"pending_unknowns": "[List of outstanding blocker criteria requiring human intervention]"
}
```

# SOURCE_REGISTRY
ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note
--- | --- | --- | ---
[SRC_ID] | Spec_Discovery | specs/{NNN}-{FEATURE_SLUG}/explore.md | Source exploration tracking framework parameters.
</output_format_schemas>

<execution_sequence>

<step id="pre_script">
Run the pre-script to discover the epic slug, validate upstream artifacts, and emit a JSON contract:
```bash
<SKILL_DIR>/deviate-prd.sh pre
```

The contract on stdout contains: `repo_root`, `git_branch`, `timestamp`, `epic_slug`, `feature_dir` (relative path to the feature bucket), `prd_path` (absolute path to prd.md), `constitution_path`, `explore_md_path`, `design_md_path`, `data_model_md_path`, `plan_target` (absolute path for the execution manifest), `dry_run`.

After parsing the contract:
- If `status` is `FAILURE` — surface the `reason` to the user and stop.
- If `status` is `NO_EPIC` — surface that no epic slug could be resolved and stop.
- If `status` is `READY` — extract all fields and proceed.
</step>

<step id="constitutional_pre_flight">
Read the constitution from `constitution_path` (absolute path from the contract). Extract:
- Tech stack standards (backend, frontend, database, infrastructure languages/frameworks)
- Testing protocols (framework, commands, coverage thresholds)
- Architectural principles (immutable governance rules)
- Performance and security constraints
</step>

<step id="upstream_artifact_analysis">
Read the upstream artifacts:
- `explore_md_path` — the exploration findings
- `design_md_path` — if it exists, the architectural design decisions
- `data_model_md_path` — if it exists, the data model definitions

If `explore_md_path` does not exist or is empty, halt with EXPLORE_MISSING.
</step>

<step id="prd_generation">
Generate the PRD content following the `<output_format_schemas>` structure. Write the result to `prd_path` (absolute path from the contract).

Key requirements:
- All `FR-[ID]` tokens must be unique and sequential
- All `AC-[ID]` tokens must use strict Gherkin (Given/When/Then) syntax
- Every path must be relative to `repo_root`
- Constitutional constraints must be respected
- Document metadata must reference the correct upstream artifacts
</step>

<step id="manifest_writing">
Write an execution manifest JSON to `plan_target` (absolute path from the contract). The manifest must include:
```json
{
  "task_id": "prd",
  "files_modified": [
    {
      "path": "<feature_dir>/prd.md",
      "action": "created|modified",
      "purpose": "Product Requirements Document for feature epic"
    }
  ],
  "commit_subject": "docs(<epic_id>): add prd.md",
  "validation": {
    "lint": "SKIP",
    "typecheck": "SKIP",
    "tests": "SKIP",
    "summary": "PRD document generated"
  }
}
```
</step>

<step id="post_script">
Run the post-script to validate the PRD, stage files, and commit:
```bash
<SKILL_DIR>/deviate-prd.sh post "$PLAN_TARGET"
```

The post-script:
1. Reads the manifest from `$PLAN_TARGET`
2. Validates that `prd.md` exists at the expected path and is non-empty
3. Validates required sections are present
4. Stages and commits the PRD
5. Emits status JSON on stdout

If the post-script exits with `status: FAILURE`, surface the `reason` to the user and stop.
</step>

</execution_sequence>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

