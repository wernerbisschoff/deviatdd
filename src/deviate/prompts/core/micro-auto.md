<micro_layer_model>

NOTE: This differs from ``micro-skill.md`` — the ``-auto`` variants reference the CLI orchestrator,
while ``-skill`` variants reference the pre/post scripts directly, because skill prompts are invoked
by the agent directly (agent runs pre/post) while auto prompts are orchestrated by the CLI.

This phase operates inside the **MICRO LAYER** — the Red-Green-Refactor cycle for individual tasks.

<rgr_cycle>

Each task is a Logical Unit (30-90 min) that undergoes ONE complete R-G-R cycle:

<item>
**RED**: Write a failing test — verified to fail due to missing implementation, not syntax errors.
</item>

<item>
**GREEN**: Write the minimum production code to pass the test.
</item>

<item>
**REFACTOR**: Behavior-preserving structural cleanup without modifying tests.
</item>

</rgr_cycle>

<shared_disciplines>

<item>
<title>Test-First Discipline</title>
No production code is written before a failing test exists. Tests are the executable specification — the RED phase verifies the test fails before GREEN begins.
</item>

<item>
<title>Sociable Tests Over Solitary</title>
Prefer sociable (integration) tests that exercise real component orchestration. Restrict mocking exclusively to non-deterministic external networks, third-party transactional interfaces, or volatile system attributes (system epoch timers, cryptographic entropy paths).
</item>

<item>
<title>Verification-is-Done</title>
A task is ONLY finished when its `Verification` command passes. Verification is deterministic and scoped — run the specific test file, not the entire suite.
</item>

<item>
<title>Git Isolation</title>
Any test that invokes git operations MUST operate on an isolated temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real project repository. Use `create_temp_dir` → `git init` → copy fixtures → run test in that context.
</item>

<item>
<title>Orchestrator Lifecycle</title>
The CLI orchestrator handles all pre/post lifecycle — it injects context, stages files, runs pre-commit hooks, updates the task ledger, and commits. Do NOT run `deviate <phase> pre/post` or use `git add`/`git commit` directly.
</item>

<item>
<title>YAML Quoting Rule</title>
ALL string values in the handover manifest YAML MUST be wrapped in double quotes. A value containing a colon (`:`) will BREAK YAML parsing if unquoted.
</item>

</shared_disciplines>

<mandate>
STDOUT OUTPUT MANDATE: Your final stdout response must be EXACTLY the YAML block from the `<handover_manifest>` section. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.
</mandate>

</micro_layer_model>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
