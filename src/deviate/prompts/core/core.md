<universal_invariants>

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism. Run `libref list` first to discover available documentation packages. When documentation for a library is missing, use `libref add <source>` to register it. This replaces web fetching as the default — web fetch is a last-resort fallback only when `libref` is unavailable.

8. **Product-Layer Flow Traceability**: The Product layer under `specs/_product/` holds cross-epic context that prevents context loss as work moves down the layers. `flows/index.md` and any domain-specific `flows-<domain>.md` define user-visible `FLOW-XX` IDs; `release-next.md` defines the in-flight release goal; `architecture.md` and `domain-model.md` define cross-epic integration contracts. Every phase MUST (a) read the relevant Product-layer artifacts at the start of execution, (b) propagate `flow_refs` from the parent artifact (issue frontmatter → `plan.md` → `tasks.md` → tests → implementation → PR), and (c) verify the artifact it emits preserves or extends the named flows. Macro phases read `release-next.md` as the guiding compass and use the canonical flow index for FR-to-Flow mapping; meso phases copy `flow_refs` from the issue into `plan.md` under `## Product Layer Anchors` and from `plan.md` into each task's `**Flow References**` field; micro phases restate the user-visible flow before writing code and assert implementation serves it; HITL gates (review, PR) surface flow coverage as a first-class review dimension. If `specs/_product/` is absent, emit `flow_refs: []` and continue — do NOT halt.

9. **Codebase Index Mandate**: All agents use the codebase-index MCP tools as the primary mechanism for semantic code discovery, symbol location, and call-graph traversal. Verify the index is current via `index_status` before depending on it. Apply the tool priority ladder: `codebase_peek` for "does this exist?" lookups, `implementation_lookup` for symbol definitions, `codebase_search` for semantic or behavioral queries, `find_similar` for duplicate detection, `call_graph` and `call_graph_path` for callers and callees, and `pr_impact` for pre-merge blast radius. Reserve `grep`, `glob`, and `Read` for last-mile regex patterns, raw text reads, and dotfiles gitignored from the index. When the codebase-index MCP is unavailable, fall back to `grep`, `glob`, and `Read` in that same order.

</universal_invariants>
