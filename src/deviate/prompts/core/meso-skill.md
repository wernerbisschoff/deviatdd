## Meso Layer Execution Model

This phase operates inside the **DeviaTDD MESO LAYER** — localized research, planning, and task decomposition per issue.

### Shared Meso Disciplines

1. **Worktree Execution**: This phase runs inside a dedicated git worktree for a single issue. The pre-script resolves the worktree path and branch. All file operations are relative to the worktree root.

2. **Issue/Spec Loading**: Read the spec-enriched issue file at `spec_path`. The issue file contains user stories, Gherkin acceptance criteria, edge cases, performance constraints, and a system topology mapping section.

3. **Ledger State**: Issue state lives in `specs/issues.jsonl`. Task state lives in `tasks.jsonl`. Do NOT store task state in markdown files. `tasks.md` is a human-readable reference only.

4. **Post-Script Validation**: The post-script validates required sections, updates the ledger, commits, and advances the session state. If validation fails, fix the output and re-run.

5. **Branch Discipline**: All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.

6. **Zero Speculative Scope**: Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.

7. **Deterministic Discovery**: Use only local, deterministic operations — `git log`, file reads, grep, glob. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.

<step id="handover_emission">
After the post script completes, emit the YAML block from the `<handover_manifest>` section as your ONLY stdout output. Do NOT include any explanatory text, markdown formatting, or file contents before or after it.
</step>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
