---
name: deviate-red
description: Use when executing the RED (test-writing) phase of TDD for a single task
category: deviattd-macro-layer
version: 1.0.0
layer: micro
aliases:
  - red
  - /spec.tdd.red
  - /red
  - /tdd.red
---

<system_instructions>

## Role Definition

 This engine operates exclusively as an automated, context-isolated test-driven development execution runtime tasked with parsing workspace tracking vectors and compiling failing automated acceptance test suites. Your objective is to ingest an active task tracking vector and generate an absolute, deterministic suite of failing automated acceptance and unit tests. These tests serve as the executable specification and unyielding rulebook for subsequent implementation phases.

## Tier Classification

This is the **RED** (test-writing) phase of the DeviaTDD micro-cycle. Use it when:
- An active TDD task exists in `tasks.md`
- The task has a PENDING status in the `tasks.jsonl` ledger (or no ledger entry yet)
- Tests need to be written before implementation code

After completion, the `deviate-green` skill should be invoked for the implementation phase.

</system_instructions>

<traceability_mandates>
1. **Verbatim Objective Verification**: Extract the target `{TASK_ID}` defined inside the `tasks.md` state array. Trace this element directly back to its upstream declaration inside `specs/{FEATURE_SLUG}/spec.md`.
2. **Gherkin Acceptance Expansion**: The generated test architecture must translate the functional criteria (`FR-[ID]`) and acceptance bounds (`AC-[ID]`) of the requirement into explicit Given/When/Then scenario blocks within the test runner assertions.
3. **Execution Boundary Enforcement**: Test behavior, not implementation structure. Implement sociable component orchestration paths over solitary configurations. Restrict mocking structures exclusively to non-deterministic external networks, third-party transactional interfaces, or volatile system attributes (e.g., system epoch timers, cryptographic entropy paths).
4. **Environment Determinism**: Execute filesystem assertions utilizing in-memory directory wrappers or completely isolated ephemeral workspaces tracking clean teardown flags.
</traceability_mandates>

<few_shot_examples>
<example>
<pre_script_output>
{"status":"READY","task_id":"TASK-104","test_command":"pytest tests/","lint_command":"ruff check .","spec_dir":"specs/001","feature_slug":"auth-jwt"}
</pre_script_output>
<output_payload>
````markdown
# DeviaTDD Micro Red: TASK-104

Status: TEST_WRITTEN_FAILING
Target_Artifact: `tests/auth/test_jwt.py`

## Handover Manifest
```yaml
phase: RED
task_id: "TASK-104"
feature_slug: "auth-jwt"
status: "FAIL"
test_file: "tests/auth/test_jwt.py"
verification_command: "pytest tests/auth/test_jwt.py"
expected_failure_node: "NameError: name 'JWTService' is not defined"
traceability_anchors:
  requirement_id: "FR-A1"
  acceptance_criteria: "AC-03"
  scenarios_mapped:
    - "Given unexpired payload, When encoded, Then matching signature generated"
assertions_established:
  - "assert service.encode(payload) is not None"
next_phase: "/deviate-green"
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
deviate red pre
```

The contract on stdout contains: `status`, `task_id`, `test_command`, `lint_command`, `spec_dir`, `feature_slug`, `task_title`, `task_type`, `task_mode`, `test_strategy`, `verification`, `estimated_time`, `dependency`, `rationale`, `task_details`, `files_touched`, `universal_constraints`, `repo_root`, `git_branch`, `timestamp`.

- If `status` is `READY` — proceed to step 1.
- If `status` is `NO_TASKS_REMAINING` — surface to user and stop.
- If `status` is `FAILURE` — surface the reason and stop.
</step>

<step id="context_loading">
1. Extract the target `{TASK_ID}` from the pre-script contract
2. Resolve absolute paths for the feature workspace: `specs/{FEATURE_SLUG}/`
3. Read the active task description from `tasks.md`
4. Inspect `spec.md` to map data definitions, schemas, and API constraints
5. Read `specs/constitution.md` for global invariants and test framework conventions
</step>

<step id="test_writing">
1. Write the physical test file within the repository's native test structure using project-specific frameworks
2. Ensure all code interfaces required for the test compilation are structurally present; declare dummy interfaces or minimal stub structures if the target module does not yet exist
3. Run the `test_command` from the contract to verify the test fails:
   ```bash
   {test_command}
   ```
4. **Git Isolation**: If the test involves git operations (running git commands, testing git-based tools, fixture repos), the test MUST NOT run inside the project repository. Use `create_temp_dir` to create an isolated workspace, `cd` into it, `git init` a fresh repo there, copy test fixtures, and run the test against that isolated context. The LLM must create a test helper or fixture setup that handles this; the `test_command` must be scoped to the isolated directory, not `$REPO_ROOT`.
5. Validate that the execution crashes explicitly due to assertion failures or missing function components. If the suite passes immediately or crashes due to parsing syntax failures, abort execution and throw a micro error.
6. Run the `lint_command` from the contract to ensure lint compliance:
   ```bash
   {lint_command}
   ```
   If lint fails, fix the issues and re-run.
</step>

<step id="post_script">
**⚠️ MANDATORY — YOU MUST RUN THIS COMMAND. DO NOT SKIP.**

You MUST execute the following command using the **Bash tool**. Do NOT use `git add`, `git commit`, or any other git command to commit files. Only `deviate red post` is the accepted way to complete this phase.

Failure to run this command will:
- Leave files uncommitted
- Cause the phase to fail (no fallback commit)
- Require re-running the phase from scratch

```bash
deviate red post
```

The post-command stages all changed files, verifies tests are still failing (expected for RED), updates the task ledger, and commits with `--no-verify` (pre-commit hooks are bypassed because RED-phase tests are intentionally failing).

If the post-command returns a non-zero exit code, inspect the error output, fix the underlying issue, then re-run:
```bash
deviate red post
```

Do NOT proceed to the handover manifest until this command completes successfully.
</step>

<step id="handover_emission">
Emit the structured handover manifest. The manifest must be emitted as a distinct, self-contained YAML block suitable for downstream parsing.

CRITICAL: The manifest MUST be a valid YAML code block delimited by ```yaml and ```.
ALL string values in the YAML MUST be wrapped in double quotes (" ").
A value containing a colon (`:`) will BREAK YAML parsing if unquoted.
Output NOTHING outside the YAML block — no explanations, no commentary.

# DeviaTDD Micro Red: {TASK_ID}

Status: TEST_WRITTEN_FAILING
Target_Artifact: `path/to/test_file.ext`

## Handover Manifest
```yaml
phase: "RED"
task_id: "{TASK_ID}"
feature_slug: "{FEATURE_SLUG}"
status: "FAIL"
test_file: "path/to/test_file.ext"
verification_command: "{VERIFICATION_BINARY} path/to/test_file.ext"
expected_failure_node: |
  {EXACT_ASSERTION_ERROR_OR_COMPILER_STUB_MISSING}
traceability_anchors:
  requirement_id: "FR-{ID}"
  acceptance_criteria: "AC-{ID}"
  scenarios_mapped:
    - "Given {PRECONDITION}, When {ACTION}, Then {EXPECTED_BEHAVIOR}"
assertions_established:
  - "{ASSERTION_CRITERIA_1}"
  - "{ASSERTION_CRITERIA_2}"
next_phase: "/deviate-green"
```

</step>

</execution_sequence>

<output_format_schemas>
Emit exclusively the finalized human-readable Markdown blueprint document satisfying the structural constraints of the output layout specification. Do not output operational XML tags, conversational preambles, or post-execution explanations outside the required Markdown block schema.

# DeviaTDD Micro Red: {TASK_ID}

Status: TEST_WRITTEN_FAILING
Target_Artifact: `path/to/test_file.ext`

## Handover Manifest
```yaml
phase: RED
task_id: "{TASK_ID}"
feature_slug: "{FEATURE_SLUG}"
status: "FAIL"
test_file: "path/to/test_file.ext"
verification_command: "{VERIFICATION_BINARY} path/to/test_file.ext"
expected_failure_node: |
  {EXACT_ASSERTION_ERROR_OR_COMPILER_STUB_MISSING}
traceability_anchors:
  requirement_id: "FR-{ID}"
  acceptance_criteria: "AC-{ID}"
  scenarios_mapped:
    - "Given {PRECONDITION}, When {ACTION}, Then {EXPECTED_BEHAVIOR}"
assertions_established:
  - "{ASSERTION_CRITERIA_1}"
  - "{ASSERTION_CRITERIA_2}"
next_phase: "/deviate-green"
```


## Handover Persistence (FLOW-11)

After emitting the YAML manifest, call the Write tool to persist it at `.deviate/feat/<epic>/<issue>/[<task>/]<phase>.yaml` via `deviate.core.handover.handover_path()` (FLOW-11 capture).

</output_format_schemas>

<edge_case_handling>

| Condition | Action |
|---|---|
| Pre-script returns NO_TASKS_REMAINING | Surface message; recommend running /deviate-tasks to generate tasks |
| Pre-script returns FAILURE | Surface the reason from the JSON contract |
| Test passes immediately | Abort — test must fail first. Check for pre-existing implementation |
| Test crashes with syntax error | Fix syntax, re-run, verify FAIL status |
| Tests involve git operations | Create isolated temp dir via `create_temp_dir`, `git init` a fresh repo, copy test fixtures there, run tests in that isolated context — NEVER inside the project repository |
| Lint fails | Fix lint issues before proceeding |
| No matching spec.md found | Proceed with minimal test structure based on task description |
| Test file already exists | Read it, understand current state, add new failing tests |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

