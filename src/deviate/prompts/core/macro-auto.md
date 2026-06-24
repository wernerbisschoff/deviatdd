<macro_layer_model>

NOTE: This differs from ``macro-skill.md`` — the ``-auto`` variants reference the CLI orchestrator,
while ``-skill`` variants reference the pre/post scripts directly, because skill prompts are invoked
by the agent directly (agent runs pre/post) while auto prompts are orchestrated by the CLI.

This phase operates inside the **MACRO LAYER** — feature scoping, architectural analysis, and requirement definition.

<shared_disciplines>

<item>
<title>Feature Bucket Allocation</title>
Each macro phase operates within a pre-allocated feature bucket. For **research**, **PRD**, and **shard**, the bucket is `specs/{NNN}-{FEATURE_SLUG}/` (a numbered epic directory created by `allocate_feature_bucket()`). For **explore**, the bucket is `specs/explore/` (a staging directory, NOT a numbered epic — the CLI orchestrator creates it via `deviate explore pre`). Do NOT re-derive paths from the problem statement.
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
<title>Contract Context</title>
The CLI orchestrator has run the pre-script and resolved the contract. Available context includes: `repo_root`, `git_branch`, `feature_slug`, `feature_dir`, `specs_directory`, `spec_target`, `constitution_path`, `test_command`, `lint_command`, `type_check_command`, `epic_id`, `is_greenfield`. The orchestrator runs the post-script after your response to validate and commit.
</item>

<item>
<title>HITL Gate Handoff</title>
After the orchestrator validates your output, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.
</item>

<item>
<title>Subagent Delegation</title>
For non-trivial features (>20 source files or mixed-language manifests), spawn 2-3 parallel read-only discovery/reasoning subagents. Each returns text fragments only — no file writes. For trivial repos, collapse to a single linear pass.
</item>

<item>
<title>Zero Implementation Code</title>
Macro phases MUST NOT write, modify, or generate any implementation code (source files, tests, configs, scripts, migrations). Only specification/design/PRD documents are written.
</item>

</shared_disciplines>

</macro_layer_model>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
