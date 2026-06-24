<meso_layer_model>

NOTE: This differs from ``meso-skill.md`` — the ``-auto`` variants reference the CLI orchestrator,
while ``-skill`` variants reference the pre/post scripts directly, because skill prompts are invoked
by the agent directly (agent runs pre/post) while auto prompts are orchestrated by the CLI.

This phase operates inside the **MESO LAYER** — localized research, planning, and task decomposition per issue.

<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. The CLI orchestrator resolves the worktree path and branch. All file operations are relative to the worktree root.
</item>

<item>
<title>Issue/Spec Loading</title>
Read the spec-enriched issue file at `spec_path`. The issue file contains user stories, Gherkin acceptance criteria, edge cases, performance constraints, and a system topology mapping section.
</item>

<item>
<title>Ledger State</title>
Issue state lives in `specs/issues.jsonl`. Task state lives in `tasks.jsonl`. Do NOT store task state in markdown files. `tasks.md` is a human-readable reference only.
</item>

<item>
<title>Post-Script Validation</title>
The CLI orchestrator runs the post-script after your response to validate required sections, update the ledger, commit, and advance the session state.
</item>

<item>
<title>Branch Discipline</title>
All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.
</item>

<item>
<title>Zero Speculative Scope</title>
Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.
</item>

<item>
<title>Deterministic Discovery</title>
Use only local, deterministic operations — `git log`, file reads, grep, glob. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.
</item>

</shared_disciplines>

<mandate>
STDOUT OUTPUT MANDATE: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.
</mandate>

</meso_layer_model>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
