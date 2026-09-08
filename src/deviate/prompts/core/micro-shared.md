<micro_layer_model>


<rgr_cycle>

Each task undergoes ONE complete R-G-R cycle:

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
Exercise real in-process collaborators; restrict mocking to non-deterministic externals (external networks, third-party transactional interfaces, epoch timers, entropy paths). A sociable unit test must still run with the DB down under `mise unit`. Test Strategy remains `unit` | `integration` | `e2e`.
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
<title>YAML Quoting Rule</title>
ALL string values in the handover manifest YAML MUST be wrapped in double quotes.
</item>

<item>
<title>User-Scenario Encoding</title>
**red** MUST encode the parent issue's user scenarios (`## User Stories Ledger` plus ATDD / `## Acceptance Outline`, via the assigned `AC-PLAN-NNN` Given/When/Then) as failing tests before GREEN. After COMPLETED, those tests *are* the flow. **judge** scores Spec Compliance against that same user-visible behavior. **green**, **refactor**, and **execute** implement or polish only the workstation files required by those scenarios.
</item>

</shared_disciplines>

</micro_layer_model>