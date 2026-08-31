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
Each macro phase writes a fixed number of output artifacts — 1 file (explore, prd, shard) or 2 files (research: design.md + data-model.md). No artifact files, temporary files, summary files, or implementation files are written by the agent or its subagents.
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
<title>Product-Layer Context Inheritance</title>
Macro phases consume existing Product-layer context; they do not create the tooling that makes DeviaTDD or that catalog available. **explore** MAY read `specs/_product/release-next.md` if it exists and surface its Goal and Included Epics as context. **research** MAY read existing `specs/_product/architecture.md` and `specs/_product/domain-model.md` for integration constraints. **prd** MAY tag each `FR-NNN-NN` with `FLOW-XX` IDs from the existing flow catalog. **shard** and **adhoc** use those existing flow definitions only to derive traceability. Flow files, flow indexes, release documents, DeviaTDD skills, and agent command directories are read-only context and are never implementation workstations or generated issue/task targets.
</item>

</shared_disciplines>

</macro_layer_model>
