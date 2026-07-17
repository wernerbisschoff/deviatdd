<meso_layer_model>

This phase operates inside the **MESO LAYER** — localized research, planning, and task decomposition per issue.

<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. The lifecycle entry step resolves the worktree path and branch. All file operations are relative to the worktree root.
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
<title>Branch Discipline</title>
All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.
</item>

<item>
<title>Zero Speculative Scope</title>
Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.
</item>

<item>
<title>Deterministic Discovery</title>
Use only local, deterministic operations. The codebase-index MCP tools (`codebase_peek`, `implementation_lookup`, `codebase_search`, `call_graph`) are the primary discovery path — verify the index is current via `index_status` before depending on it. Supplement with `git log`, `Read`, `grep`, and `glob` for prior-commit context, raw text reads, and last-mile regex patterns or dotfiles gitignored from the index. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.
</item>

<item>
<title>Flow Reference Propagation</title>
Meso phases are the Product-layer propagation channel. The `flow_refs` field on the parent issue's YAML frontmatter is the authoritative source — once shard emits it, every subsequent artifact MUST carry it forward verbatim. **plan** MUST extract `flow_refs` from the issue at `spec_path` and emit a `## Product Layer Anchors` section in `plan.md` containing `**Flow References**`, `**Source**` (the issue file path), `**Release Context**` (one-line summary from `specs/_product/release-next.md` Goal if present, else `N/A`), and `**Architecture Components Touched**` (Component IDs from `specs/_product/architecture.md` §3 that this issue modifies). **tasks** MUST read `flow_refs` from `plan.md`'s `## Product Layer Anchors` and copy them onto every emitted task as `**Flow References**: [FLOW-XX, ...]` so downstream micro phases inherit flow context per-task. If `specs/_product/` is absent, emit `**Flow References**: []` and continue — do NOT halt. This is the structural fix that prevents context loss between macro and micro layers.
</item>

</shared_disciplines>

</meso_layer_model>

<mandate>
STDOUT OUTPUT MANDATE: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.
</mandate>