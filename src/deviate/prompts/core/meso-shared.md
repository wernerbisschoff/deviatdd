<meso_layer_model>


<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. All file operations are relative to the worktree root.
</item>

<item>
<title>Issue Intent and Plan Contract Loading</title>
Read macro intent from the issue at `spec_path`: user stories, AO/ATDD outlines, scope, edge cases, performance, and topology. Plan reads these inputs and authors the Gherkin `## Acceptance Contract`; Tasks treats that plan contract as authoritative and never falls back to issue/spec Gherkin.
</item>

<item>
<title>Ledger State</title>
Issue state lives in `specs/issues.jsonl`. Task state lives in `tasks.jsonl`. Do NOT store task state in markdown files. `tasks.md` is a human-readable reference only.
</item>

<item>
<title>Branch Discipline</title>
All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.
</item>

<item>
<title>Application-Only Scope</title>
Analyze only files directly mapped in the system topology mapping. `Workstation Mapping`, `Implementation Strategy`, and task `Files` list only application files required by the issue; they never include DeviaTDD setup, agent skills, catalog files, release scaffolding, or workflow ledgers.
</item>

<item>
<title>Deterministic Discovery</title>
Use only local, deterministic discovery (see core Code Discovery Mandate). Supplement with `git log` for prior-commit context. Zero network calls.
</item>


</shared_disciplines>

</meso_layer_model>