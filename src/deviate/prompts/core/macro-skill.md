<macro_layer_model>

This phase operates inside the **MACRO LAYER** — feature scoping, architectural analysis, and requirement definition.

<shared_disciplines>

<item>
<title>Feature Bucket Allocation</title>
Each macro phase operates within a pre-allocated feature bucket. For **research**, **PRD**, and **shard**, the bucket is `specs/{NNN}-{FEATURE_SLUG}/` (a numbered epic directory). For **explore**, the bucket is `specs/explore/` (a staging directory, NOT a numbered epic). The explore bucket is created by `deviate explore pre`; numbered epic buckets are created by `deviate research pre` via `allocate_feature_bucket()` — do NOT re-derive paths from the problem statement.
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
<title>Pre/Post Script Lifecycle</title>
Every macro phase begins with `deviate <phase> pre` (allocates bucket, emits JSON contract on stdout). Parse the JSON contract to extract runtime attributes — the contract carries `repo_root`, `git_branch`, `feature_slug`, `feature_dir`, `specs_directory`, `spec_target`, `constitution_path`, `test_command`, `lint_command`, `type_check_command`, `epic_id`, `is_greenfield`. Do NOT re-derive paths from the problem statement. Every macro phase ends with `deviate <phase> post` (validates artifacts, commits, returns status).
</item>

<item>
<title>HITL Gate Handoff</title>
After the post-script completes successfully, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.
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
<title>Offline Documentation Requirement</title>
All macro-layer phases MUST use `libref query <library> <topic>` when evaluating library APIs, framework conventions, or dependency-specific decisions. The `libref` CLI provides offline, version-pinned documentation — prefer it over web fetching. Web fetch is a last-resort fallback.
</item>

</shared_disciplines>

</macro_layer_model>
