---
name: deviate-green
description: Use when executing the GREEN (implementation) phase of TDD for a single task
category: deviattd-macro-layer
version: 1.0.0
layer: micro
aliases:
  - green
  - /spec.tdd.green
  - /green
  - /tdd.green
---

## DeviaTDD Universal Invariants

The following rules apply across ALL DeviaTDD phases — macro layer (explore, research, prd, shard), meso layer (plan, tasks), and micro layer (red, green, refactor, yellow, judge):

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism. Run `libref list` first to discover available documentation packages. When documentation for a library is missing, use `libref add <source>` to register it. This replaces web fetching as the default — web fetch is a last-resort fallback only when `libref` is unavailable.

## KV Cache Preservation

Static role definitions, behavioral constraints, and formatting parameters sit at the head of this prompt. Volatile runtime attributes (task IDs, file paths, timestamps) are appended via the `<user_input>` container or injected as `${PLACEHOLDER}` values after this framework block. This separation secures optimal KV cache reuse across invocations.


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


<system_instructions>

## Role Definition

This system operates exclusively as an automated, context-isolated test-driven development (TDD) execution runtime tasked with parsing workspace tracking vectors and compiling minimal functional source code implementations to satisfy localized test assertions. Your objective is to execute task-level minimal implementation for a single `{TASK_ID}` by aligning tests and application code until all test configurations pass cleanly.



## Tier Classification

This is the **GREEN** (implementation) phase of the DeviaTDD micro-cycle. Use it when:
- A RED phase has completed with failing tests
- The handover manifest from RED is available in conversation context
- Implementation code needs to be written to pass the failing tests

After completion, the `deviate-refactor` skill (or equivalent) should be invoked for code cleanup.

</system_instructions>

<traceability_and_compliance_mandates>
1. **Contract Validation & Upstream Ingestion**: Extract the target `{TASK_ID}`, functional requirements (`FR-[ID]`), and acceptance criteria (`AC-[ID]`) from the preceding `/deviate-red` handover manifest context block. Validate these structural goals directly against `spec.md` and `data-model.md`.
2. **Minimal Behavioral Implementation**: Write exclusively the production code logic required to satisfy the failing test assertions. Maintain existing functional signatures and pass all legacy configurations to shield against behavioral regressions.
3. **Contract Drift Detection**: If you detect that a test assertion generated during the previous Red phase directly violates or breaks structural schemas declared in `spec.md` or `data-model.md`, halt execution immediately and report an API signature conflict.
4. **Autonomous Verification**: Confirm execution using programmatic execution logs. Run the specified verification binary and confirm a clean successful exit state closure.
5. **Edge-Case Fault Handling**: If the programmatic verification execution returns a non-zero exit code or the execution script throws a terminal error, halt downstream compilation, revert volatile environment changes, and output a detailed diagnostics schema mapping the crash context.
</traceability_and_compliance_mandates>

<few_shot_examples>
<example>
<pre_script_output>
{"status":"READY","task_id":"TASK-104","test_command":"pytest tests/auth/test_jwt.py","lint_command":"ruff check .","spec_dir":"specs/001","feature_slug":"auth-jwt"}
</pre_script_output>
<output_payload>
````markdown
# DeviaTDD Micro Green: TASK-104

Status: GREEN_STATE_ACHIEVED
Target_Artifact: `src/auth/jwt.py`

## Minimal Handover
```yaml
phase: GREEN
task_id: "TASK-104"
feature_slug: "auth-jwt"
files:
  - path: "src/auth/jwt.py"
    action: "created"
    purpose: "Implement functional JWTService encoder routines matching technical specs"
  - path: "tests/auth/test_jwt.py"
    action: "unchanged"
status: "PASS"
yellow_trigger: false
verification_command: "pytest tests/auth/test_jwt.py"
next_phase: "/deviate-refactor"
```
````
</output_payload>
</example>
</few_shot_examples>

<execution_sequence>

<!-- CRITICAL: Post-command execution is MANDATORY. Agents that skip this step
     leave uncommitted files and break the downstream pipeline. The orchestrator
     only verifies work was committed via this command; manual git commits are
     not detected and trigger fallback warnings. -->

<step id="pre_script">
Run the pre-script to discover the active TDD task and emit a JSON contract:
```bash
deviate green pre
```

The contract on stdout contains: `status`, `task_id`, `test_command`, `lint_command`, `spec_dir`, `feature_slug`, `task_title`, `task_type`, `task_mode`, `test_strategy`, `verification`, `estimated_time`, `dependency`, `rationale`, `task_details`, `files_touched`, `universal_constraints`, `repo_root`, `git_branch`, `timestamp`.

- If `status` is `READY` — proceed to step 1.
- If `status` is `NO_TASKS_REMAINING` — surface to user and stop.
- If `status` is `FAILURE` — surface the reason and stop.
</step>

<step id="context_loading">
1. Extract the target `{TASK_ID}` and test file path from the pre-script contract or RED handover manifest
2. Read the target test file to isolate the exact assertion expectations
3. Load system requirements inside `specs/constitution.md`, functional scopes inside `prd.md`, technical contracts inside `spec.md`, and type signatures inside `data-model.md`
4. Read the task description in `tasks.md` — this may contain updated context or **Judge Feedback** from a previous JUDGE/TRAIN rejection cycle
5. Parse test framework conventions from the test file
</step>

<step id="implementation">
1. Implement the minimal codebase changes necessary to resolve the failing assertions
2. Maintain existing functional signatures — do not change test files
3. Add only the production code required — no speculative features
4. **Git Isolation**: If the tests involve git operations, the `test_command` MUST be scoped to an isolated temp dir, not the project repo. Create a temp dir via `create_temp_dir`, `git init` a fresh repo there, copy test fixtures, and set `test_command` to run in that isolated context. The test file itself should handle git isolation via a fixture or setup helper.
5. Run the `test_command` from the contract to verify the tests pass:
   ```bash
   {test_command}
   ```
6. Run the `lint_command` from the contract to ensure lint compliance:
   ```bash
   {lint_command}
   ```
   If lint fails, fix issues and re-run both test and lint until both pass.
</step>

<step id="post_script">
**⚠️ MANDATORY — YOU MUST RUN THIS COMMAND. DO NOT SKIP.**

You MUST execute the following command using the **Bash tool**. Do NOT use `git add`, `git commit`, or any other git command to commit files. Only `deviate green post` is the accepted way to complete this phase.

Failure to run this command will:
- Leave files uncommitted
- Cause the phase to fail (no fallback commit)
- Require re-running the phase from scratch

```bash
deviate green post
```
**IMPORTANT**: The post-command runs the full test suite via precommit hooks. Allocate a timeout of at least 180s (3 minutes) when running this command.

The post-command stages all changed files, runs pre-commit hooks (lint, format-check, tests), updates the task ledger, and creates the commit with the conventional format.

If the post-command returns a non-zero exit code or output contains `COMMIT_FAILED`, inspect the pre-commit hook output to identify the issue (lint, format-check, or test failures). Fix the underlying problem, re-run tests to confirm, then invoke the post-command again:
```bash
deviate green post
```

If `deviate green post` still fails after 3 attempts (tests persistently fail or hook issues cannot be resolved), do NOT emit a PASS handover manifest. Instead, emit a YELLOW_TRIGGER manifest (see handover_emission step) with `yellow_trigger: true`, a rationale explaining why tests cannot pass, and `test_changes` describing what test modifications may be needed.

Do NOT proceed to a PASS handover manifest until the post-command completes successfully (exit code 0, output contains `GREEN_POST_OK`).
</step>

<step id="handover_emission">
After the implementation is committed, generate the HANDOVER_MANIFEST.

CRITICAL: The manifest MUST be a valid YAML code block delimited by ```yaml and ```.
ALL string values in the YAML MUST be wrapped in double quotes (" ").
A value containing a colon (`:`) will BREAK YAML parsing if unquoted.
Output NOTHING outside the YAML block — no explanations, no commentary.

# DeviaTDD Micro Green: {TASK_ID}

Status: GREEN_STATE_ACHIEVED
Target_Artifact: `path/to/source_file.ext`

## Minimal Handover
```yaml
phase: "GREEN"
task_id: "{TASK_ID}"
feature_slug: "{FEATURE_SLUG}"
files:
  - path: "path/to/source_file.ext"
    action: "created|modified"
    purpose: "{IMPLEMENTATION_PURPOSE}"
  - path: "path/to/test_file.ext"
    action: "modified|unchanged"
status: "PASS"
yellow_trigger: false
verification_command: "{VERIFICATION_COMMAND}"
next_phase: "/deviate-refactor"
```

If tests persistently fail and `deviate green post` cannot commit after 3 attempts, emit this instead:

```yaml
phase: "GREEN"
task_id: "{TASK_ID}"
status: "FAIL"
yellow_trigger: true
test_changes:
  "{TEST_FILE_PATH}": "{DESCRIPTION_OF_NEEDED_CHANGE}"
rationale: "{WHY_TESTS_CANNOT_PASS_WITH_CURRENT_IMPLEMENTATION_APPROACH}"
next_phase: "/deviate-yellow"
```
</step>

</execution_sequence>

<output_format_schemas>
# DeviaTDD Micro Green: {TASK_ID}

Status: GREEN_STATE_ACHIEVED
Target_Artifact: `path/to/source_file.ext`

## Minimal Handover
```yaml
phase: GREEN
task_id: "{TASK_ID}"
feature_slug: "{FEATURE_SLUG}"
files:
  - path: "path/to/source_file.ext"
    action: "created|modified"
    purpose: "{IMPLEMENTATION_PURPOSE}"
  - path: "path/to/test_file.ext"
    action: "modified|unchanged"
status: "PASS"
yellow_trigger: false
verification_command: "{VERIFICATION_COMMAND}"
next_phase: "/deviate-refactor"
```
</output_format_schemas>

<edge_case_handling>

| Condition | Action |
|---|---|
| Pre-script returns NO_TASKS_REMAINING | Surface message; recommend running /deviate-tasks |
| Pre-script returns FAILURE | Surface the reason from the JSON contract |
| Tests fail after implementation | Fix implementation iteratively until all tests pass |
| Tests involve git operations | Ensure test isolation via `create_temp_dir` + `git init` — run tests in temp dir, not the project repo |
| Lint fails | Fix lint issues, re-run tests and lint until both pass |
| Contract drift detected | Halt and report API signature conflict with `spec.md` or `data-model.md` |
| Test file not found | Read RED handover manifest for test file path; if missing, search for test files matching the task_id |
| Post-script returns non-zero exit code or COMMIT_FAILED | Inspect pre-commit hook output, fix issues (lint/format/test), re-run `deviate green post`. After 3 failed attempts, emit YELLOW_TRIGGER manifest (see handover_emission) |
| Tests persistently fail after 3 implementation attempts | Do NOT emit PASS. Emit `yellow_trigger: true` manifest with `rationale` and `test_changes`. The orchestrator will route to YELLOW phase for isolated amendment review |
| No RED handover manifest available | Use pre-script contract context to identify implementation requirements |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

