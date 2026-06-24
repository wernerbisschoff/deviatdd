## Micro Layer Execution Model — TDD Sandbox

NOTE: This differs from ``micro-skill.md`` — the ``-auto`` variants reference the CLI orchestrator,
while ``-skill`` variants reference the pre/post scripts directly, because skill prompts are invoked
by the agent directly (agent runs pre/post) while auto prompts are orchestrated by the CLI.

This phase operates inside the **MICRO LAYER** — the Red-Green-Refactor cycle for individual tasks.

### The R-G-R Cycle

Each task is a Logical Unit (30-90 min) that undergoes ONE complete R-G-R cycle:

1. **RED**: Write a failing test — verified to fail due to missing implementation, not syntax errors.
2. **GREEN**: Write the minimum production code to pass the test.
3. **REFACTOR**: Behavior-preserving structural cleanup without modifying tests.

### Shared Micro Disciplines

1. **Test-First Discipline**: No production code is written before a failing test exists. Tests are the executable specification — the RED phase verifies the test fails before GREEN begins.

2. **Sociable Tests Over Solitary**: Prefer sociable (integration) tests that exercise real component orchestration. Restrict mocking exclusively to non-deterministic external networks, third-party transactional interfaces, or volatile system attributes (system epoch timers, cryptographic entropy paths).

3. **Verification-is-Done**: A task is ONLY finished when its `Verification` command passes. Verification is deterministic and scoped — run the specific test file, not the entire suite.

4. **Git Isolation**: Any test that invokes git operations MUST operate on an isolated temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real project repository. Use `create_temp_dir` → `git init` → copy fixtures → run test in that context.

5. **Orchestrator Lifecycle**: The CLI orchestrator handles all pre/post lifecycle — it injects context, stages files, runs pre-commit hooks, updates the task ledger, and commits. Do NOT run `deviate <phase> pre/post` or use `git add`/`git commit` directly.

**STDOUT OUTPUT MANDATE**: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.

6. **YAML Quoting Rule**: ALL string values in the handover manifest YAML MUST be wrapped in double quotes. A value containing a colon (`:`) will BREAK YAML parsing if unquoted.

## <context>
<user_input>
$ARGUMENTS
</user_input>
</context>
