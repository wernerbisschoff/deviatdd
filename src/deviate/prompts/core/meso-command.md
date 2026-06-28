<meso_layer_model>

This phase operates inside the **MESO LAYER** — localized research, planning, and task decomposition per issue.

<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. The pre-script resolves the worktree path and branch. All file operations are relative to the worktree root.
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
The post-script validates required sections, updates the ledger, commits, and advances the session state. If validation fails, fix the output and re-run.
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

<item>
<title>Offline Documentation Requirement</title>
Use `libref query <library> <topic>` for understanding library APIs and framework conventions detected in the codebase. The `libref` CLI provides offline, deterministic documentation lookups without network overhead. Prefer it over training data or web fetching.
</item>

<item>
<title>Flow Reference Propagation</title>
Meso phases are the Product-layer propagation channel. The `flow_refs` field on the parent issue's YAML frontmatter is the authoritative source — once shard emits it, every subsequent artifact MUST carry it forward verbatim. **plan** MUST extract `flow_refs` from the issue at `spec_path` and emit a `## Product Layer Anchors` section in `plan.md` containing `**Flow References**`, `**Source**` (the issue file path), `**Release Context**` (one-line summary from `specs/_product/release-next.md` Goal if present, else `N/A`), and `**Architecture Components Touched**` (Component IDs from `specs/_product/architecture.md` §3 that this issue modifies). **tasks** MUST read `flow_refs` from `plan.md`'s `## Product Layer Anchors` and copy them onto every emitted task as `**Flow References**: [FLOW-XX, ...]` so downstream micro phases inherit flow context per-task. If `specs/_product/` is absent, emit `**Flow References**: []` and continue — do NOT halt. This is the structural fix that prevents context loss between macro and micro layers.
</item>

</shared_disciplines>

</meso_layer_model>

<step id="handover_emission">
After the post script completes, emit the YAML block from the `<handover_manifest>` section as your ONLY stdout output. Do NOT include any explanatory text, markdown formatting, or file contents before or after it.
</step>
