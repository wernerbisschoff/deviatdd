<micro_layer_model>

This phase operates inside the **MICRO LAYER** — the Red-Green-Refactor cycle for individual tasks.

<rgr_cycle>

Each task is a Logical Unit (30-90 min) — one fail-to-pass contract, not a duration floor — that undergoes ONE complete R-G-R cycle:

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
<title>YAML Quoting Rule</title>
ALL string values in the handover manifest YAML MUST be wrapped in double quotes. A value containing a colon (`:`) will BREAK YAML parsing if unquoted.
</item>

<item>
<title>User-Scenario Encoding</title>
**red** MUST encode the parent issue's user scenarios (`## User Stories Ledger` plus ATDD / `## Acceptance Outline`, via the assigned `AC-PLAN-NNN` Given/When/Then) as failing tests before GREEN. GREEN still cannot edit tests. After COMPLETED, those tests *are* the flow — do not invent a catalog or `flow_refs` field. **judge** scores Spec Compliance against that same user-visible behavior. **green**, **refactor**, and **execute** implement or polish only the workstation files required by those scenarios.
</item>

</shared_disciplines>

</micro_layer_model>