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
For non-trivial features (>20 source files or mixed-language manifests), spawn 2-3 parallel read-only discovery/reasoning subagents. Each returns text fragments only — no file writes. For trivial repos, collapse to a single linear pass.
</item>

<item>
<title>Zero Implementation Code</title>
Macro phases MUST NOT write, modify, or generate any implementation code (source files, tests, configs, scripts, migrations). Only specification/design/PRD documents are written.
</item>

<item>
<title>Product-Layer Context Inheritance</title>
Macro phases are the Product-layer intake valve. **explore** MUST read `specs/_product/release-next.md` if it exists and surface its `## Goal` + `## Included Epics` in the explore output's `## Problem Definition` section as the "Release Compass". **research** MUST read `specs/_product/architecture.md` and `specs/_product/domain-model.md` if they exist; classify the epic as `Local`, `Context-Bridging`, or `Context-Creating` per the architecture's own classification rule, and surface the classification in `design.md` under `## Cross-Epic Architecture Alignment`. **prd** MUST pre-tag every `FR-NNN-NN` token with one or more `FLOW-XX` IDs derived from `specs/_product/flows/index.md` and any domain-specific `flows-<domain>.md`; the PRD is the canonical source for shard's Pass 2.1 FR-to-Flow mapping. **shard** MUST emit `flow_refs: [FLOW-XX, ...]` in every issue's YAML frontmatter (already enforced; verify). If `specs/_product/` is absent, emit empty flow lists and continue.
</item>

</shared_disciplines>

</macro_layer_model>