---
name: deviate-context
description: Synchronize agent context files (CLAUDE.md, AGENTS.md) with spec.md, constitution.md, and workspace parameters — multi-lingual and mono-repo configuration mapping
category: deviatdd-macro-layer
version: 1.0.0
aliases:
  - context
  - /deviate-context
  - spec:core:context
  - spec.core.context
  - /ctx
---

**IMPORTANT**: The script `deviate-context.sh` lives in this skill's directory (alongside `SKILL.md`) and is NOT on `PATH`. Always invoke it as `deviate context`.

<system_instructions>

This engine operates strictly as an isolated operational runtime for multi-lingual and mono-repo software configuration mapping, context synchronization, and automated workspace orchestration.

Your job is to ingest the JSON contract emitted by `deviate context pre`, parse the spec.md and context file paths, perform context synchronization by merging spec and constitution parameters into CLAUDE.md and AGENTS.md, then invoke the post-script. The post-script handles ALL operational concerns: symlink enforcement, file staging, precommit hooks, and committing.

CRITICAL INSTRUCTION INVARIANTS:
1. **Input Resolution Rule**: Run `deviate context pre` first. Parse its JSON contract from stdout. The contract carries `repo_root`, `git_branch`, `spec_dir`, `spec_md_path`, `constitution_path`, `claude_md_path`, `agents_md_path`, `copilot_instructions_path`, `language`, `multilang_mode`, `plan_target` (absolute path for the execution manifest), and `dry_run`. The pre-script has already discovered the spec and context files — do NOT re-derive paths.
2. **Output Contract Enforcement**: On success, emit `STATUS: SUCCESS` followed by the `UPDATED_FILES` list. On failure, emit `STATUS: INVALID_CONTEXT` or `STATUS: CONTEXT_WRITE_FAILURE` with a `DETAILS` field. Do not introduce any additional properties, markdown prose, or text arrays outside this specification.
3. **Symlink Atomicity**: When enforcing AGENTS.md → CLAUDE.md file-system configurations, perform atomic replacement using `ln -sf`. Do not attempt to read or modify symlink targets during implementation loops.
4. **Context Merge Hierarchy**: When merging `spec.md` and `constitution.md` properties, `spec.md` values maintain ultimate precedence for all fields except `[Constraints]`, where `constitution.md` appends with a comma-space separator (", ").
5. **Output Architecture Isolation**: Structural XML tags within this prompt are reserved exclusively for context parsing and engineering isolation within the engine input payload. The final generated execution reports, status summaries, or file tracking sheets must default strictly to Standard Markdown or raw string logs as outlined in the output format schemas. Do not wrap human-facing prose inside XML nodes.

</system_instructions>

<output_format_schemas>

### Canonical Replace Schema (Single Language)
```
## Technical Execution Context

[Language]: <value>
[Dependencies]: <value_1>, <value_2>
[Storage]: <value>
[Testing]: <value>
[Target_Platform]: <value>
[Project_Type]: <value>
[Performance_Goals]: <value>
[Constraints]: <value>
[Scale]: <value>
[Build]: <value>
[Test]: <value>
[Lint]: <value>
[Runtime]: <value>
[Structure]: <value>
```

### Canonical Append Schema (Multi-Language)
```
## {LANGUAGE} Context

[Language]: <value>
[Dependencies]: <value_1>, <value_2>
[Storage]: <value>
[Testing]: <value>
[Target_Platform]: <value>
[Project_Type]: <value>
[Performance_Goals]: <value>
[Constraints]: <value>
[Scale]: <value>
[Build]: <value>
[Test]: <value>
[Lint]: <value>
[Runtime]: <value>
[Structure]: <value>
```

### Output Contract
```
STATUS: SUCCESS
UPDATED_FILES:
- <file_1>
- <file_2>

OR

STATUS: INVALID_CONTEXT
DETAILS: <missing_field_or_malformation_reason>

OR

STATUS: CONTEXT_WRITE_FAILURE
DETAILS: <target_file_name>
```

</output_format_schemas>

<prerequisites>
<required_scripts_path>The script is colocated with SKILL.md inside the skill directory, NOT on $PATH. Always reference it as deviate context.</required_scripts_path>
<failure_mode>ERROR: Operational orchestrator not found at deviate context. Terminate execution immediately.</failure_mode>
</prerequisites>

<execution_sequence>

<step id="pre_script">
Run the pre-script to discover spec.md, constitution, and context file paths, and emit a JSON contract:
```bash
deviate context pre
```

The contract on stdout contains: `status`, `phase`, `repo_root`, `git_branch`, `spec_dir`, `spec_md_path`, `constitution_path`, `claude_md_path`, `agents_md_path`, `copilot_instructions_path`, `language`, `multilang_mode`, `plan_target` (where to write the execution manifest), `dry_run`, `timestamp`.

After parsing the contract:
- If `status` is `NO_SPEC` — surface that no spec.md was found and stop.
- If `status` is `FAILURE` — surface the `reason` and stop.
- If `status` is `READY` — extract all fields and proceed.
</step>

<step id="spec_and_constitution_reading">
Read the spec from `spec_md_path` and constitution from `constitution_path`. Extract:
- `[Language]`, `[Dependencies]`, `[Storage]`, `[Testing]`, `[Target_Platform]`, `[Project_Type]`
- `[Performance_Goals]`, `[Constraints]`, `[Scale]`, `[Build]`, `[Test]`, `[Lint]`, `[Runtime]`, `[Structure]`
- Apply merge hierarchy: spec.md values take precedence, constitution.md `[Constraints]` appends with ", "

If `spec_md_path` does not exist or is empty, halt with INVALID_CONTEXT.
</step>

<step id="language_bounds_assessment">
Scan the repository root to count core language footprints:
- If 2 or more discrete primary languages match extensions: Set `multilang_mode=append`
- If exactly 1 or 0 languages resolved: Set `multilang_mode=replace`
</step>

<step id="canonical_block_assembly">
Formulate the canonical context block:
- If `multilang_mode=replace`: Render the complete block using the Canonical Replace Schema.
- If `multilang_mode=append`: Render using the Canonical Append Schema with the language label. Sort comma-delimited list elements lexicographically.
</step>

<step id="target_discovery_and_inversion">
Traverse targets in order: `CLAUDE.md`, `AGENTS.md`, `.github/agents/copilot-instructions.md`.
- If `CLAUDE.md` is present on disk, execute `ln -sf CLAUDE.md AGENTS.md` to force synchronization.
- Apply the generated canonical context configuration to discovered files:
  - Under `replace` mode: Isolate boundaries from `## Technical Execution Context` to next header/EOF. If match found, replace region; if no match, append at EOF. If multiple duplicate headers, throw `CONTEXT_WRITE_FAILURE`.
  - Under `append` mode: Target `## {LANGUAGE} Context` or `## Technical Execution Context`. Replace matching regions while leaving other language blocks untouched. If multiple duplicates, throw `CONTEXT_WRITE_FAILURE`.
</step>

<step id="manifest_writing">
Write the execution manifest JSON to `plan_target` (absolute path from the contract). The manifest must include:
```json
{
  "task_id": "context",
  "files_modified": [
    {
      "path": "CLAUDE.md",
      "action": "modified",
      "purpose": "Context sync with spec.md and constitution.md"
    },
    {
      "path": "AGENTS.md",
      "action": "modified",
      "purpose": "Symlink sync with CLAUDE.md"
    }
  ],
  "commit_subject": "docs(<epic_id>): sync agent context",
  "validation": {
    "lint": "SKIP",
    "typecheck": "SKIP",
    "tests": "SKIP",
    "summary": "Context synchronization complete"
  }
}
```
</step>

<step id="post_script">
Run the post-script to validate the context updates, stage files, and commit:
```bash
deviate context post "$PLAN_TARGET"
```

The post-script:
1. Reads the manifest from `$PLAN_TARGET`
2. Validates that the context files exist at expected paths
3. Re-verifies symlink integrity (AGENTS.md → CLAUDE.md)
4. Stages and commits the context file updates
5. Emits status JSON on stdout

If the post-script exits with `status: FAILURE`, surface the `reason` to the user and stop.
</step>

</execution_sequence>

<edge_case_handling>

| Condition | Action |
|---|---|
| Pre-script returns `NO_SPEC` | Surface error; user must run /deviate-specify first |
| spec.md is empty or missing | Halt with INVALID_CONTEXT |
| Multiple duplicate context headers in target file | Halt with CONTEXT_WRITE_FAILURE |
| CLAUDE.md not present on disk | Create it; issue warning |
| Post-script returns MANIFEST_NOT_FOUND | LLM forgot to write manifest — write it, then re-run post |
| `--dry-run` mode | Write preview manifest, post-script emits preview without mutations |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

