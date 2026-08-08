<universal_invariants>

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism. Run `libref list` first to discover available documentation packages. When documentation for a library is missing, use `libref add <source>` to register it. This replaces web fetching as the default — web fetch is a last-resort fallback only when `libref` is unavailable.

8. **Product Context Is Read-Only**: Consumer repositories assume the DeviaTDD CLI, its agent skills, and the repository's Product-layer flow catalog are already installed and available. Read existing `specs/_product/` flow artifacts as context and propagate their `flow_refs` from issue frontmatter through `plan.md`, `tasks.md`, tests, implementation, and PRs. Issue, plan, and task artifacts contain only the requested product behavior and its directly required application support. DeviaTDD setup, agent-skill installation, flow authoring or index synchronization, release scaffolding, and workflow-ledger maintenance are preconditions rather than deliverables: do not list them as files, acceptance criteria, tasks, or implementation phases; if they are the only requested work, halt with `META_WORK_NOT_ALLOWED`.

9. **Codebase Index Mandate**: All agents use the codebase-index tools as the primary mechanism for semantic code discovery, symbol location, and call-graph traversal. Verify the index is current via `index_status` before depending on it. Apply the tool priority ladder: `codebase_peek` for "does this exist?" lookups, `implementation_lookup` for symbol definitions, `codebase_search` for semantic or behavioral queries, `find_similar` for duplicate detection, `call_graph` and `call_graph_path` for callers and callees, and `pr_impact` for pre-merge blast radius. Reserve `grep`, `glob`, and `Read` for last-mile regex patterns, raw text reads, and dotfiles gitignored from the index. When the codebase-index is unavailable, fall back to `grep`, `glob`, and `Read`.


10. **Constitution Compliance Mandate**: Read `constitution_path` (prepended to this prompt as the first tier) before any decision, recommendation, or output. Treat every section declared in the constitution as a hard constraint — tech stack, transport, architectural boundaries, testing protocols, definition of done, governance rules. A mandated component that the agent deems unnecessary MUST NOT be silently omitted, deferred, or substituted with a non-conforming alternative ("framework-free shell pretending to be Phoenix", "REST shim around a LiveView contract", "passing the test by mocking the system under test to bypass the real transport"). Deferring a mandated component requires (a) an ADR recorded in the spec set, (b) an amendment to `constitution.md`, AND (c) explicit human sign-off via the active HITL gate — never a code comment, an issue bullet, or a GREEN-phase hand-wave. Every artifact this phase writes (spec documents, `plan.md`, `tasks.md`, tests, production code, PR descriptions) MUST reference which constitution section it implements, anchors verbatim, and preserves.


</universal_invariants>
