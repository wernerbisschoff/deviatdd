## Micro Layer Execution Model — TDD Sandbox

This phase operates inside the **DeviaTDD MICRO LAYER** — the Red-Green-Refactor cycle for individual tasks.

### The R-G-R Cycle

Each task is a Logical Unit (30-90 min) that undergoes ONE complete R-G-R cycle:

1. **RED**: Write a failing test — verified to fail due to missing implementation, not syntax errors.
2. **GREEN**: Write the minimum production code to pass the test.
3. **REFACTOR**: Behavior-preserving structural cleanup without modifying tests.

### Shared Micro Disciplines

1. **Test-First Discipline**: No production code is written before a failing test exists. Tests are the executable specification — the RED phase verifies the test fails before GREEN begins.

2. **Sociable Tests Over Solitary**: Prefer sociable (integration) tests that exercise real component orchestration. Restrict mocking exclusively to non-deterministic external networks, third-party transactional interfaces, or volatile system attributes (system epoch timers, cryptographic entropy paths).

3. **Verification-is-Done**: A task is ONLY finished when its `Verification` command passes and the post-script commits successfully. Verification is deterministic and scoped — run the specific test file, not the entire suite.

4. **Git Isolation**: Any test that invokes git operations MUST operate on an isolated temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real project repository. Use `create_temp_dir` → `git init` → copy fixtures → run test in that context.

5. **Post-Script Protocol**: Every micro phase ends with `deviate <phase> post`. This is MANDATORY — do NOT use `git add` / `git commit` directly. The post-script stages files, runs pre-commit hooks (lint, format-check, tests), updates the task ledger, and commits. Allocate a timeout of at least 180s (3 minutes) for post-script execution.

6. **Handover Manifest YAML**: After post-script success, emit a handover manifest as a YAML code block. ALL string values MUST be wrapped in double quotes. A value containing a colon (`:`) will BREAK YAML parsing if unquoted. Output NOTHING outside the YAML block — no explanations, no commentary.

7. **Offline Documentation Guidance**: When implementing, use `libref query <library> <topic>` to look up library APIs and framework conventions. The `libref` CLI provides offline, version-pinned documentation — prefer it over web fetching. If `libref` is unavailable, fall back to training data or web fetch.
