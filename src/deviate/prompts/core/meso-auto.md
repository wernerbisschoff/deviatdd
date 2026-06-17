## Meso Layer Execution Model

NOTE: This differs from ``meso-skill.md`` — the ``-auto`` variants reference the CLI orchestrator,
while ``-skill`` variants reference the pre/post scripts directly, because skill prompts are invoked
by the agent directly (agent runs pre/post) while auto prompts are orchestrated by the CLI.

This phase operates inside the **DeviaTDD MESO LAYER** — localized research, planning, and task decomposition per issue.

### Shared Meso Disciplines

1. **Worktree Execution**: This phase runs inside a dedicated git worktree for a single issue. The CLI orchestrator resolves the worktree path and branch. All file operations are relative to the worktree root.

2. **Issue/Spec Loading**: Read the spec-enriched issue file at `spec_path`. The issue file contains user stories, Gherkin acceptance criteria, edge cases, performance constraints, and a system topology mapping section.

3. **Ledger State**: Issue state lives in `specs/issues.jsonl`. Task state lives in `tasks.jsonl`. Do NOT store task state in markdown files. `tasks.md` is a human-readable reference only.

4. **Post-Script Validation**: The CLI orchestrator runs the post-script after your response to validate required sections, update the ledger, commit, and advance the session state.

5. **Branch Discipline**: All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.

6. **Zero Speculative Scope**: Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.

7. **Deterministic Discovery**: Use only local, deterministic operations — `git log`, file reads, grep, glob. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.

**STDOUT OUTPUT MANDATE**: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
