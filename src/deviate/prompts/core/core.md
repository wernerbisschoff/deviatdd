<universal_invariants>

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Documentation Lookup**: Prefer version-pinned project docs and local references. Use web fetch only when those sources do not answer the question.

8. **Application Scope Only**: Consumer repositories assume the DeviaTDD CLI and its agent skills are already installed and available. Issue, plan, and task artifacts contain only the requested application behavior and its directly required application support. User scenarios live on the shard issue (`## User Stories Ledger` + ATDD / `## Acceptance Outline`); RED encodes those scenarios as failing tests, and after COMPLETED the tests *are* the flow. DeviaTDD setup, agent-skill installation, catalog authoring, release scaffolding, and workflow-ledger maintenance are preconditions rather than deliverables: do not list them as files, acceptance criteria, tasks, or implementation phases; if they are the only requested work, halt with `META_WORK_NOT_ALLOWED`.

9. **Code Discovery Mandate**: Use zvec-grep for semantic code discovery. Use the `zvec_grep_search` MCP tool when available, or `zg query` via the CLI. Use `grep`, `glob`, and `Read` for exact matches, raw text reads, and dotfiles.


10. **Constitution Compliance Mandate**: Read `constitution_path` — resolved as `<workdir>/specs/constitution.md` when this prompt is a shared/global install, or the file prepended as the first tier of this prompt when the install embedded it — before any decision, recommendation, or output. Treat every section declared in the constitution as a hard constraint — tech stack, transport, architectural boundaries, testing protocols, definition of done, governance rules. A mandated component that the agent deems unnecessary MUST NOT be silently omitted, deferred, or substituted with a non-conforming alternative ("framework-free shell pretending to be Phoenix", "REST shim around a LiveView contract", "passing the test by mocking the system under test to bypass the real transport"). Deferring a mandated component requires (a) an ADR recorded in the spec set, (b) an amendment to `constitution.md`, AND (c) explicit human sign-off via the active HITL gate — never a code comment, an issue bullet, or a GREEN-phase hand-wave. Every artifact this phase writes (spec documents, `plan.md`, `tasks.md`, tests, production code, PR descriptions) MUST reference which constitution section it implements, anchors verbatim, and preserves.


</universal_invariants>
