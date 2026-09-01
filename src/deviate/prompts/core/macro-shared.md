<macro_layer_model>

This phase operates inside the **MACRO LAYER** — feature scoping, architectural analysis, and requirement definition.

<shared_disciplines>

<item>
<title>Feature Bucket Allocation</title>
Each macro phase operates within a pre-allocated feature bucket. For **research**, **PRD**, and **shard**, the bucket is `specs/{NNN}-{FEATURE_SLUG}/` (a numbered epic directory). For **explore**, the bucket is `specs/explore/` (a staging directory, NOT a numbered epic). The bucket is allocated by the lifecycle entry step — either the CLI orchestrator's `deviate <phase> pre` (auto mode) or the operator running `deviate <phase> pre "<problem-statement>" --slug "<slug>"` directly (manual mode). Either path calls `allocate_feature_bucket()`; do NOT re-derive paths from the problem statement.
</item>

<item>
<title>Constitutional Validation Gate</title>
Prior to any synthesis, read and verify the constitution from `constitution_path`. Every decision, requirement, and output must comply with the constitution's core rules (tech stack, architectural principles, testing protocols, definition of done).
</item>

<item>
<title>Output File Mandate</title>
Each macro phase writes only its declared output artifacts. Explore and PRD write 1 file; research writes 2 files (`design.md` and `data-model.md`). SHARD writes one issue file per vertical slice plus its required execution manifest. No unlisted artifact files, temporary files, summary files, or implementation files are written by the agent or its subagents.
</item>

<item>
<title>Subagent Delegation</title>
Sub-agents are for parallel work. **explore** may spawn 2-3 parallel read-only discovery subagents; each returns text fragments only — no file writes. **research** is ordered: one agent, two sequential jobs in the same prompt — do not spawn research sub-agents or forward context between two research processes. **prd** and **shard** collapse to a single linear pass. For trivial repos, every phase collapses to a single linear pass.
</item>

<item>
<title>Zero Implementation Code</title>
Macro phases MUST NOT write, modify, or generate any implementation code (source files, tests, configs, scripts, migrations). Only specification/design/PRD documents are written.
</item>

<item>
<title>User Scenarios Belong on the Issue</title>
Macro phases author application behavior, not a product catalog. **shard** and **adhoc** MUST write `## User Stories Ledger` plus ATDD (`## Acceptance Outline` with `AO-NNN`) on every issued vertical. Those scenarios are the user-visible job. Do not invent `flow_refs`, a `_product/` folder, or FR-to-flow catalog mapping. DeviaTDD skills and agent command directories are never implementation workstations or generated issue/task targets.
</item>

</shared_disciplines>

</macro_layer_model>
