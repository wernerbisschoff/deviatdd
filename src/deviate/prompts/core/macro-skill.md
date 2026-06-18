## Macro Layer Execution Model

This phase operates inside the **DeviaTDD MACRO LAYER** — feature scoping, architectural analysis, and requirement definition.

### Shared Macro Disciplines

1. **Feature Bucket Allocation**: Each macro phase operates within a pre-allocated feature bucket at `specs/{NNN}-{FEATURE_SLUG}/`. The bucket is created by the pre-script — do NOT re-derive paths from the problem statement.

2. **Constitutional Validation Gate**: Prior to any synthesis, read and verify the constitution from `constitution_path`. Every decision, requirement, and output must comply with the constitution's core rules (tech stack, architectural principles, testing protocols, definition of done).

3. **Output File Mandate**: Each macro phase writes a fixed number of output artifacts — 1 file (explore, prd, shard) or 2 files (research: design.md + data-model.md). No artifact files, temporary files, summary files, or implementation files are written by the agent or its subagents.

4. **Pre/Post Script Lifecycle**: Every macro phase begins with `deviate <phase> pre` (allocates bucket, emits JSON contract on stdout). Parse the JSON contract to extract runtime attributes — the contract carries `repo_root`, `git_branch`, `feature_slug`, `feature_dir`, `specs_directory`, `spec_target`, `constitution_path`, `test_command`, `lint_command`, `type_check_command`, `epic_id`, `is_greenfield`. Do NOT re-derive paths from the problem statement. Every macro phase ends with `deviate <phase> post` (validates artifacts, commits, returns status).

5. **HITL Gate Handoff**: After the post-script completes successfully, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.

6. **Subagent Delegation**: For non-trivial features (>20 source files or mixed-language manifests), spawn 2-3 parallel read-only discovery/reasoning subagents. Each returns text fragments only — no file writes. For trivial repos, collapse to a single linear pass.

7. **Zero Implementation Code**: Macro phases MUST NOT write, modify, or generate any implementation code (source files, tests, configs, scripts, migrations). Only specification/design/PRD documents are written.

8. **Context Consultation Requirement**: All macro-layer phases MUST use `context query <library> <topic>` when evaluating library APIs, framework conventions, or dependency-specific decisions. The `context` CLI provides offline, version-pinned documentation — prefer it over web fetching. Web fetch is a last-resort fallback.

## <context>
<user_input>
$ARGUMENTS
</user_input>
