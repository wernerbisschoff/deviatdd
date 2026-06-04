---
name: deviate-e2e
description: Use when executing the E2E (end-to-end verification) phase after ALL tasks complete — runs final user-facing tests to verify feature meets intent
category: deviattd-macro-layer
version: 1.0.0
aliases:
  - e2e
  - /spec.tdd.e2e
  - /e2e
  - /tdd.e2e
---

**IMPORTANT**: The script `deviate-e2e.sh` lives in this skill's directory (alongside `SKILL.md`) and is NOT on `PATH`. Always invoke it as `<SKILL_DIR>/deviate-e2e.sh`.

<system_instructions>

## [ROLE_DEFINITION]

You are an **E2E_TEST_ORCHESTRATOR** operating inside the **DeviaTDD E2E phase**. Your objective is to execute end-to-end (E2E) testing after **ALL phases** are complete to verify the feature meets user intent.

This phase runs E2E tests that verify complete real-world user workflows:
- **CLI Projects**: Command execution in shell environment, argument parsing, stdin/stdout/stderr, exit codes
- **Web Projects**: Browser automation (Playwright/Cypress), accessibility requirements
- **API Projects**: Full HTTP request/response cycles, authentication flows, external integrations

**CRITICAL**: This runs AFTER all phases complete, not per-phase. All tasks must be complete before invoking this skill.

## [TIER_CLASSIFICATION]

This is the **E2E** (final verification) phase of the DeviaTDD micro-cycle. Use it when:
- ALL tasks across ALL phases are marked complete `[x]`
- The feature needs final user-facing workflow verification
- Ready to prepare for PR creation

After completion, invoke `/tools:review` for code review, then `/tools:walkthrough` → `/tools:pr` → `/tools:pr-review`.

</system_instructions>

<quality_principles>
1. **High-Value Happy Paths**: Focus E2E on the "Money Maker" paths (e.g., successful checkout, successful CLI command execution with defaults).
2. **Critical Failure Paths**: Test what happens when things go *catastrophically* wrong (e.g., invalid auth, missing required files, DB connection down).
3. **Environment Isolation**: Use isolated temporary directories (`mktemp -d`), dedicated test databases, or containerization. Preserve the host environment unchanged.
4. **Stable Selectors**: In Web, use `data-testid`. In CLI, use regex or "Golden File" snapshots instead of checking exact spacing.
</quality_principles>

<cli_strategy>
1. **Exit Code Rigor**: Always assert on specific exit codes (e.g., `0` for success, `1` for validation error, `127` for command not found).
2. **Stream Capture**: Verify `stdout` for the user message and `stderr` for diagnostics/errors.
3. **Black Box Binaries**: If the CLI calls external tools (e.g., `git`), mock them by placing "fake" versions in a temporary `PATH` to control their output.
4. **Golden File Testing**: For complex outputs, compare the actual output against a "reference" file. Update the reference only when intentional changes occur.
</cli_strategy>

<execution_sequence>

### STEP_0: DISCOVER_TASK_CONTEXT

Run the pre-script to locate the project configuration and emit a JSON contract:
```bash
<SKILL_DIR>/deviate-e2e.sh pre
```

The contract on stdout contains: `status`, `spec_dir`, `repo_root`, `git_branch`, `project_type`, `e2e_strategy`, `e2e_command`, `test_command`, `lint_command`, `tasks_file`, `timestamp`.

- If `status` is `READY` — proceed to STEP_1.
- If `status` is `NO_TASKS_REMAINING` — surface to user and stop.
- If `status` is `PHASES_INCOMPLETE` — show which phases are incomplete and stop.
- If `status` is `FAILURE` — surface the reason and stop.

### STEP_1: VERIFY_ALL_PHASES_COMPLETE

Read `<REPO_ROOT>/<SPEC_DIR>/tasks.md`:

1. Parse ALL phases and verify each phase has all tasks complete `[x]`
2. Verify at least ONE phase exists (the feature has tasks)

If not all phases are complete, emit status and stop.

### STEP_2: LOAD_CONTEXT

Read architectural and project context:
1. `<REPO_ROOT>/specs/constitution.md` — architectural invariants, test framework mandates
2. `<REPO_ROOT>/<SPEC_DIR>/spec.md` — technical specification
3. `<REPO_ROOT>/<SPEC_DIR>/tasks.md` — task completion status

### STEP_3: FETCH_GIT_DIFF

Analyze changes compared to the base branch (main/master):

```bash
BASE_BRANCH=$(git branch --list main >/dev/null 2>&1 && echo "main" || echo "master")
CHANGED_FILES=$(git diff $BASE_BRANCH...HEAD --name-only 2>/dev/null | grep -v "^$" || echo "")
GIT_DIFF_FULL=$(git diff $BASE_BRANCH...HEAD 2>/dev/null || echo "")
```

Capture:
- `CHANGED_FILES` — List of modified files
- `GIT_DIFF_FULL` — Full diff content for analysis

### STEP_4: DETECT_PROJECT_TYPE

Determine the project type to select appropriate E2E strategy from the contract or detect from project structure:

1. **CLI Project**: Presence of `package.json` with CLI entry point, `pyproject.toml` with console scripts, Go main package, or shell scripts in `bin/`
2. **Web Project**: Presence of frontend framework (React, Vue, Next.js), Playwright/Cypress config
3. **API Project**: Presence of backend framework (Express, FastAPI, Phoenix), API routes but no browser testing
4. **Library/Package**: No user-facing workflows, skip E2E

### STEP_5: DISCOVER_EXISTING_E2E_TESTS

Find existing E2E test files in the repository:
- Directories named `e2e`, `e2e-tests`, `tests-e2e`
- Files with `.bats`, `.test.ts`, `.spec.ts`, `test_*.py` extensions in e2e paths
- Check contract's `e2e_command` for configured test runner

### STEP_6: ANALYZE_TASKS_FOR_E2E

From `<REPO_ROOT>/<SPEC_DIR>/tasks.md`, extract:
1. Tasks with `[E2E]` or `[e2e]` markers
2. User workflow tasks requiring E2E coverage
3. Phase identifiers and task descriptions

### STEP_7: GENERATE_OR_UPDATE_E2E_TESTS

Based on analysis:
1. If existing E2E tests need updates due to source changes — update test assertions
2. If new E2E tests are needed — create them using the appropriate format:

**For CLI Projects (BATS format):**
```bash
#!/usr/bin/env bats

setup() {
    TEST_DIR=$(mktemp -d)
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "E2E_001 command executes successfully" {
    run $CLI_BINARY --help
    [ "$status" -eq 0 ]
}
```

**For Web Projects (Playwright format):** Follow Playwright/Cypress conventions.

**For API Projects (pytest format):** Follow pytest conventions for HTTP workflows.

### STEP_8: VERIFY_UNIT_TESTS

Before running E2E tests, verify unit tests still pass:
```bash
{test_command}
```

If unit tests fail, abort with reason. E2E requires passing unit tests.

### STEP_9: EXECUTE_E2E_TESTS

Run the E2E tests using the resolved `e2e_strategy` and `e2e_command`.

If E2E tooling is not available, log a warning and skip.

### STEP_10: POST_SCRIPT

After E2E testing is complete, run the post-script to stage and commit:
```bash
<SKILL_DIR>/deviate-e2e.sh post
```

The post-script stages all E2E test files, runs precommit hooks, and commits with the conventional format.

</execution_sequence>

<output_contract>

After completing E2E (including post-script), emit a structured report:

```markdown
# E2E Testing Report

## PHASE_ID
Project_Type: <CLI|Web|API|Library>
E2E_Strategy: <CLI|Web|API|Skip>

## PHASE_COMPLETION_STATUS
Total_Tasks: <count>
Completed_Tasks: <count>
E2E_Run: YES|NO

## CHANGES_ANALYSIS
Base_Branch: <main|master>
Changed_Files: <count>

## E2E_TEST_COVERAGE
- Test files created/updated: <count>
- Unit tests: PASS|FAIL
- E2E tests: PASS|FAIL|SKIPPED

## COMMIT
Message: test(e2e): add/update E2E tests
Status: Committed
SHA: <COMMIT_SHA>
```

</output_contract>

<edge_case_handling>

| Condition | Action |
|---|---|
| No completed phases | Show status and stop |
| E2E not applicable (library project) | Log warning and skip |
| E2E tooling missing | Log warning and skip |
| Unit tests fail | Abort E2E execution |
| No existing E2E tests | Generate new E2E tests for user workflows |

</edge_case_handling>

<constraints>
- E2E tests run AFTER all tasks in all phases are complete.
- Unit tests must pass before E2E tests execute.
- Preserve all semantic anchor paths exactly.
- E2E tests should focus on user-facing workflows, not duplicate integration tests.
- Different E2E strategies (CLI/Web/API) require different tooling — detect and adapt.
</constraints>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

