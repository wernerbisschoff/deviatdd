<meso_layer_model>

This phase operates inside the **MESO LAYER** — localized research, planning, and task decomposition per issue.

<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. The lifecycle entry step resolves the worktree path and branch. All file operations are relative to the worktree root.
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
<title>Zero Speculative Scope</title>
Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.
</item>

<item>
<title>Deterministic Discovery</title>
Use only local, deterministic operations. The codebase-index tools (`codebase_peek`, `implementation_lookup`, `codebase_search`, `call_graph`) are the primary discovery path — verify the index is current via `index_status` before depending on it. Supplement with `git log`, `Read`, `grep`, and `glob` for prior-commit context, raw text reads, and last-mile regex patterns or dotfiles gitignored from the index. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.
</item>

<item>
<title>Application-Only Workstations</title>
Meso phases plan and decompose the issue's user stories and ATDD. `Workstation Mapping`, `Implementation Strategy`, and task `Files` list only application files required by the issue; they never include DeviaTDD setup, agent skills, catalog files, release scaffolding, or workflow ledgers.
</item>

</shared_disciplines>

</meso_layer_model>

<mandate>
STDOUT OUTPUT MANDATE: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.
</mandate>