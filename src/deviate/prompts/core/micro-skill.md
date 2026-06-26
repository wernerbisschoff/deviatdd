<micro_layer_model>

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
A task is ONLY finished when its `Verification` command passes and the post-script commits successfully. Verification is deterministic and scoped — run the specific test file, not the entire suite.
</item>

<item>
<title>Git Isolation</title>
Any test that invokes git operations MUST operate on an isolated temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real project repository. Use `create_temp_dir` → `git init` → copy fixtures → run test in that context.
</item>

<item>
<title>Post-Script Protocol</title>
Every micro phase ends with `deviate <phase> post`. This is MANDATORY — do NOT use `git add` / `git commit` directly. The post-script stages files, runs pre-commit hooks (lint, format-check, tests), updates the task ledger, and commits. Allocate a timeout of at least 180s (3 minutes) for post-script execution.
</item>

<item>
<title>Handover Manifest YAML</title>
After post-script success, emit a handover manifest as a YAML code block. ALL string values MUST be wrapped in double quotes. A value containing a colon (`:`) will BREAK YAML parsing if unquoted. Output NOTHING outside the YAML block — no explanations, no commentary.
</item>

<item>
<title>Offline Documentation Guidance</title>
When implementing, use `libref query <library> <topic>` to look up library APIs and framework conventions. The `libref` CLI provides offline, version-pinned documentation — prefer it over web fetching. If `libref` is unavailable, fall back to training data or web fetch.
</item>

<item>
<title>Flow-Anchored Implementation</title>
Micro phases are where Product-layer context is at the highest risk of being lost. Every micro phase MUST (a) read the active task's `**Flow References**` field from `tasks.md` before writing any code, (b) restate the user-visible flow(s) the task serves in the handover manifest under `flow_refs`, and (c) verify the test or implementation exercises behavior derivable from those flows — not implementation details detached from user intent. **judge** MUST add a `flow_alignment` rubric dimension alongside Spec Compliance: does the diff preserve or extend the flows named in the task's `**Flow References**`? A change that silently abandons or breaks a named flow MUST fail JUDGE with severity HIGH and a `train_feedback` block instructing the next GREEN attempt to re-anchor to the flow. **red** MUST write tests that describe user-visible behavior derivable from the parent flow's Trigger and Happy Path, not internal function signatures. **green** MUST implement the minimum production code to satisfy those flow-anchored tests, restricting scope to workstation files explicitly tied to the named flow. **refactor**, **yellow**, and **execute** inherit the same flow context and MUST NOT extend scope beyond what the named flow requires. If `tasks.md` carries `**Flow References**: []`, treat the task as enabling/infrastructure (no flow anchor required) but still surface the empty list in the handover manifest.
</item>

</shared_disciplines>

</micro_layer_model>
