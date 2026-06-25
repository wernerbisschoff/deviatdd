---
name: deviate-tasks
description: Decompose a spec-enriched issue file (with embedded-first fallback to spec.md) into a granular task decomposition (tasks.md) consisting of autonomous Red-Green-Refactor units (vertical tasks, 30-90 min each). Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.
category: deviatdd-meso-layer
version: 1.0.0
layer: meso
aliases:
  - tasks
  - /deviate-tasks
  - spec:core:tasks
  - spec.core.tasks
  - /tasks
---

<universal_invariants>

The following rules apply across ALL phases — macro layer (explore, research, prd, shard), meso layer (plan, tasks), and micro layer (red, green, refactor, yellow, judge), whether implemented via DeviaTDD or another TDD workflow:

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism. Run `libref list` first to discover available documentation packages. When documentation for a library is missing, use `libref add <source>` to register it. This replaces web fetching as the default — web fetch is a last-resort fallback only when `libref` is unavailable.

</universal_invariants>

<kv_cache_preservation>

Static role definitions, behavioral constraints, and formatting parameters sit at the head of this prompt. Volatile runtime attributes (task IDs, file paths, timestamps) are appended via the `<user_input>` container or injected as `${PLACEHOLDER}` values after this framework block. This separation secures optimal KV cache reuse across invocations.

</kv_cache_preservation>


<meso_layer_model>

This phase operates inside the **MESO LAYER** — localized research, planning, and task decomposition per issue.

<shared_disciplines>

<item>
<title>Worktree Execution</title>
This phase runs inside a dedicated git worktree for a single issue. The pre-script resolves the worktree path and branch. All file operations are relative to the worktree root.
</item>

<item>
<title>Issue/Spec Loading</title>
Read the spec-enriched issue file at `spec_path`. The issue file contains user stories, Gherkin acceptance criteria, edge cases, performance constraints, and a system topology mapping section.
</item>

<item>
<title>Ledger State</title>
Issue state lives in `specs/issues.jsonl`. Task state lives in `tasks.jsonl`. Do NOT store task state in markdown files. `tasks.md` is a human-readable reference only.
</item>

<item>
<title>Post-Script Validation</title>
The post-script validates required sections, updates the ledger, commits, and advances the session state. If validation fails, fix the output and re-run.
</item>

<item>
<title>Branch Discipline</title>
All work happens on the dedicated issue branch. Do NOT switch branches or modify the main branch. Do NOT run `git checkout -b` or branch-switching commands — the worktree is pre-configured.
</item>

<item>
<title>Zero Speculative Scope</title>
Analyze only files directly mapped in the system topology mapping. Do not expand scope beyond the issue's declared workstation files.
</item>

<item>
<title>Deterministic Discovery</title>
Use only local, deterministic operations — `git log`, file reads, grep, glob. Zero network calls. If a scan would exceed the L_max budget for the phase, narrow the scope.
</item>

<item>
<title>Offline Documentation Requirement</title>
Use `libref query <library> <topic>` for understanding library APIs and framework conventions detected in the codebase. The `libref` CLI provides offline, deterministic documentation lookups without network overhead. Prefer it over training data or web fetching.
</item>

</shared_disciplines>

</meso_layer_model>

<step id="handover_emission">
After the post script completes, emit the YAML block from the `<handover_manifest>` section as your ONLY stdout output. Do NOT include any explanatory text, markdown formatting, or file contents before or after it.
</step>


<system_instructions>

This system operates strictly as an isolated, deterministic execution compilation pipeline for software implementation strategies and structured technical task decomposition. Your objective is to ingest a JSON contract emitted by the orchestrator script `deviate tasks pre` (which detects the existing worktree claim, locates the spec source, validates its required sections, and checks for optional research artifacts) and produce a granular task decomposition (`tasks.md`) consisting of autonomous Red-Green-Refactor units (vertical tasks, 30-90 min each). Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.

**Embedded-First Spec Consumption**: The tasks pipeline reads spec content from the issue file itself when embedded sections are present — the issue file carries `## User Stories Ledger`, `## ATDD Acceptance Criteria`, and other spec sections directly. When these embedded sections are absent, tasks falls back to reading the adjacent `spec.md` file in the same issue directory. Embedded sections take precedence when both exist.

**The "Autonomous R-G-R" Mandate** (applies only to TDD-mode tasks):
- **Red**: Every TDD task starts by writing a failing test (Sociable/Integration).
- **Green**: Every TDD task implements the minimum code to pass the test.
- **Refactor**: Every task (TDD or IMMEDIATE) cleans up code to match idioms and `specs/constitution.md` invariants.
- **Verification-is-Done**: A task is ONLY finished when its `Verification` command passes. No "vibe" confirmation.
- **IMMEDIATE tasks**: Skip the Red/Green cycle. Execute directly then verify.

**The "Workstation" Mandate**:
- **Context Consolidation**: Files that share a logical capability MUST be in the same task.
- **Maximize Signal-to-Noise**: Group files so the agent has full "Workstation" context in a single Turn.

**Meso Workflow Position**: Shard+Specify → [HITL Gate 2] → Plan → Tasks → TDD (red-green-refactor)
- **Shard+Specify**: Precedes this phase. Produces spec-enriched issue files with embedded `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[EDGE_CASES_AND_BOUNDARIES]`, and `[PERFORMANCE_CONSTRAINTS]` sections.
- **Plan** (HITL Gate 2 → Plan): Optional per-issue localized research phase producing `plan.md`. When absent, tasks reads directly from the spec-enriched issue file.
- **Tasks** (this phase): Write `tasks.md` only. Commit it. STOP.
- **TDD**: Begins after the tasks artifact is committed.

Research artifacts (`design.md`, `data-model.md`) produced by the `deviate-research` skill may exist alongside the spec source and serve as supplementary input for workstation mapping and architectural context.

CRITICAL INFERENCE PHYSICS INVARIANTS:
1. **Context Reuse Rule**: This phase typically follows `/deviate-shard` or `/deviate-plan` in the same conversation. Reuse `BRANCH_NAME`, `WORKTREE_PATH`, `ISSUE_ID`, `EPIC_SLUG`, `ISSUE_SLUG` from the shard/plan contract in your context. Do NOT re-run the shard or plan pre-script.
2. **Cohesive Scope Invariant**: Every task line-item, target verification asset, or file node declared in this ledger must map directly onto a named entity or functional acceptance rule within the codebase repository tree.

</system_instructions>


<execution_sequence>
1. `cd` into the worktree (using the `worktree_full` path from your context) and run the pre-script to detect the worktree and emit a JSON contract:
   ```
   deviate tasks pre
   ```
   The pre-script detects the worktree via `Path.cwd()` — it must run from inside the worktree. It accepts the session in SHARD, PLAN, or TASKS phase (the shard/plan post-script may or may not have run yet). Use `--force` to bypass any phase validation. The contract on stdout contains: `branch_name`, `worktree_full`, `spec_path` (the primary spec source — either the issue file with embedded sections, or the spec.md fallback, resolved from the active issue ID), `tasks_target` (where to write tasks.md), `design_path` (optional), `data_model_path` (optional), `constitution_test_command`, `constitution_lint_command`.
   - If the pre-script emits `STATUS: SPEC_NOT_FOUND` or `STATUS: NO_ACTIVE_ISSUE`, surface the status. The `/deviate-shard` phase must produce a valid spec-enriched issue file for the active issue first.

2. Read the spec source from `spec_path` — this is the issue file itself when it contains embedded `## User Stories Ledger` and `## ATDD Acceptance Criteria` sections (primary path). If those embedded sections are absent, fall back to reading the adjacent `spec.md` file in the same issue directory (legacy path). If `design_path` or `data_model_path` are present in the contract, read those too for architectural context and data schema definitions. Embedded sections take precedence when both exist.

3. **Workstation Mapping**: Map all files touched by each user story from the spec source's `SYSTEM_TOPOLOGY_MAPPING` and `PROJECT_STRUCTURE` sections (whether from embedded `[USER_STORIES_LEDGER]` in the issue file or from `spec.md`). Group related files (e.g., a service and its test file, a handler and its route registration) into workstation clusters. Derive phases from logical groupings of related user stories.

4. **Task Construction**:
    - **4a. Group Items**: Group workstation clusters into **Batched Logical Units** (vertical slices), each delivering one or more related acceptance criteria.
     - **4b. Assign Execution_Mode**: Decide **per task** using this decision tree. Run it fresh for every task:

        1. Does this task modify **only config, docs, constants, schemas, or trivial boilerplate**? → **IMMEDIATE**
        2. Does this task **refactor existing code without changing behavior** and have **existing test coverage**? → **IMMEDIATE**
        3. Does this task introduce **new business logic, state mutations, API endpoints, or integration boundaries**? → **TDD**
        4. Does this task fix a **bug**? → **TDD** (write regression test first)
        5. Does this task have **non-trivial acceptance criteria** that aren't trivially verifiable? → **TDD**
        6. Otherwise → **IMMEDIATE** (when in doubt, prefer IMMEDIATE over speculative TDD)
        7. Does this task **connect/wire already-tested components** via subprocess, API, or message passing? → **TDD** with system-edge mock boundary (mock `subprocess.Popen`, assert CLI args/env/stdin)

        A single phase can contain both modes. Do NOT default to TDD — TDD carries cost; use it where it earns its keep.
    - **4c. Assign Verification**: Assign each slice a `Verification` command based on the test strategy implied by the acceptance criteria.
    - **4d. Validate Structure**: Ensure no "Testing-only" tasks — tests are the mandatory **Red** phase of every TDD task.
    - **4e. File Rationale Assignment**: For each task, add `[File_Rationale]` explaining WHY each file is touched.

5. **Traceability Audit**:
    - Read the spec source's `SCOPE_BOUNDARIES > Defensive Exclusions` section and verify no task touches files related to anti-goals
    - Read `design.md` `RISK_REGISTER` or `CONSTRAINTS` sections (if available) and incorporate into task generation
    - Verify phase-to-story mapping
    - Flag orphaned files

6. Apply granularity rules:
    - **Slice over Step**: Tasks are defined by **What they add to the feature**, not the technical step.
    - **30-90 Minute Rule**: If a task takes < 30 min, merge it. If > 90 min, split it only while maintaining verticality.
    - **Ambiguity Resolution**: If a plan item spans multiple capabilities, create separate tasks per capability with explicit `Dependency` links.

7. Transpile the final task decomposition into format-compliant Markdown per `<output_format_schemas>` and write it directly to `<tasks_target>` (the relative path from the contract). Write exactly the tasks content — no preamble, no postamble, no XML wrapper tags.

8. Run the post-script to validate and commit (still inside the worktree from step 1):
   ```
   deviate tasks post
   ```
   The post-script validates required sections and task ID format (`T{NNN}`), then commits and advances the session to IDLE. The post-script runs precommit hooks which include the full test suite — allocate a timeout of at least 180s (3 minutes) when running this command. If validation fails, it prints a diagnostic. Fix the file and re-run. Use `--force` only with documented justification.

**TERMINATE HERE. Do NOT proceed to implementation. Hand off to the TDD phase.**
</execution_sequence>

<output_format_schemas>
<format_contract>
Render output to `<tasks_target>` using the following format. No XML wrapper tags — the file content is the ledger body.

**CRITICAL FORMAT RULES:**
- `**Files**` MUST be followed by indented file paths on separate lines (not inline)
- `**Details**` MUST be followed by indented bullet points on separate lines (not inline)
- `**Dependency**` MUST be inline: `TSK-001-01` not on separate line

**CRITICAL TASK ID CONSTRAINT:**
- Task IDs MUST follow the format `TSK-{NNN}-{NN}:` where `NNN` is the 3-digit issue number and `NN` is the 2-digit task index within the issue, starting from `TSK-001-01:`.
- Examples of VALID task IDs: `TSK-001-01:`, `TSK-001-02:`, `TSK-002-01:`, `TSK-010-01:`, `TSK-099-01:`
- Examples of INVALID task IDs (DO NOT use): `T001:`, `TASK_1:`, `T1:`, `T-001:`, `Task1:`, `TSK001:`
- The post-script validator enforces this exact pattern: `TSK-` followed by exactly 3 digits, `-`, exactly 2 digits, and a colon.

**TASK STRUCTURE CONSTRAINTS** — every task MUST contain:
- **Type**: `Feature_Batch | Infra_Batch | Domain_Batch | Bugfix | Migration | Config`
- **Mode**: `TDD | IMMEDIATE` (no default — apply the decision tree at step 4b)
  - `TDD`: Full Red-Green-Refactor cycle. **Use for**: New business logic, state mutations, integration boundaries, or non-trivial acceptance criteria.
  - `IMMEDIATE`: Execute directly without test-first. **Use for**: Trivial updates (config, docs, constants), pure refactoring with existing test coverage, or low-risk boilerplate where testing cost outweighs regression risk.
- **Test Strategy**: `Sociable_Unit | Integration | Solitary_Unit` (required if Mode is TDD)
- **Verification**: A **Deterministic CLI Command** (e.g., `pytest tests/unit/test_s3.py`).
- **Estimated Time**: Time estimate in format `30-90 minutes` or `60 minutes`.
- **Files**: List of absolute or project-relative paths (multi-line, indented, minimum 2 files).
- **Details**: **CRITICAL** — Must contain 4-8 detailed bullet points with explicit R-G-R breakdown:
  - **Red**: Specific test file, test cases to write, and assertions
  - **Green**: Exact functions/methods to implement, signatures, and logic
  - **Refactor**: Code quality improvements, pattern alignment
  - **Edge Cases**: Error handling, boundary conditions
  - **Acceptance**: Concrete "done" criteria beyond test passing
- **Dependency**: (Optional) `T{NNN}` if this task requires another task to complete first (inline value).

**DETAILS QUALITY RULES:**
- Minimum 4 bullet points, maximum 8
- For TDD tasks: MUST include at least one **Red** bullet with specific test case name and assertion
- For TDD tasks: MUST include at least one **Green** bullet with function signature and logic
- For IMMEDIATE tasks: Use **Implementation** instead of **Red**/**Green**
- SHOULD include **Edge Cases** for error handling scenarios
- SHOULD include **Acceptance** with concrete "done" criteria

**FILE TRACEABILITY RULES:**
- **Rationale** is REQUIRED on every task (prevents misaligned scope)
- Must explain WHY each file in **Files** is being modified
- Must tie each file to specific story identifiers and acceptance criteria from spec.md
- Every file in **Files** MUST be justified in **Rationale**
- Files without justification are flagged as potential scope creep

**DETERMINISM RULES:**
- **No Vibe Coding**: Any task without a `Verification` command is invalid.
- **No Layered Tasks**: Reject any task that doesn't produce a testable outcome.
- **No Vague Details**: Reject any task with fewer than 4 `Details` bullets. TDD tasks must have **Red**/**Green** markers; IMMEDIATE tasks must have **Implementation** markers.
- **Path Integrity**: Use absolute paths for all cross-references.
- **Test-First Enforcement**: Every TDD task's **Green** bullet MUST have a corresponding **Red** bullet that defines the test it passes. IMMEDIATE tasks are exempt (use **Implementation** instead).

**OUTPUT TEMPLATE** — the complete file should follow this structure:
```markdown
# Implementation Tasks: {BRANCH_NAME}

## Phase 1: <Feature Slice Name>
**Goal**: <what capability this slice delivers>

### Tasks

- T001: <Description of Vertical Slice>
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_s3.py`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `path/to/file1.ts`
    - `path/to/file2.ts`
  - **Rationale**: <Why these files? Tie to specific story US_### and AC>
  - **Details**:
    - **Red**: Write failing test: `<test_name>()` with assertion that <expected>
    - **Green**: Implement `<function>(<params>): <return>` with <logic>
    - **Refactor**: <code quality improvement>
    - **Edge Cases**: Handle <error scenario> by <action>
    - **Acceptance**: <concrete done criteria>

- T002: <Description>
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `npm run lint`
  - **Estimated Time**: 30 minutes
  - **Dependency**: T001
  - **Files**:
    - `path/to/file3.ts`
  - **Rationale**: <Why these files?>
  - **Details**:
    - **Implementation**: Implement `<function>()` with <logic>
    - **Refactor**: <improvement>
    - **Acceptance**: <criteria>

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (Logical dependency order)

**Critical Dependency Chains**:
- T001 (Schema) must precede T002 (API)

**Risk Hotspots**:
- High coupling in `user.service.ts`

**Merge Conflict Boundaries**:
- Files touched by multiple phases: [list_files]

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, check=True)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.
```

**Write the entire content directly to `<tasks_target>`** as the file's full content. No wrapping tags, no preamble, no postamble. The post-script reads the file and commits it.
</format_contract>
</output_format_schemas>

<edge_case_handling>
<case condition="Pre-script emits STATUS: NOT_IN_WORKTREE or STATUS: SPEC_NOT_FOUND">
<action>Stop. The /deviate-shard phase must produce a valid spec-enriched issue file (or a spec.md must exist as fallback) before tasks can run. Surface the status to the human operator.</action>
</case>
<case condition="Task count exceeds 10 tasks for a single issue">
<action>Halt with OUT_OF_BOUNDS_TASK_COUNT_ABOVE_MAX. Directive: split the issue's scope into a new sibling issue via `/deviate-adhoc` for the overflow; OR extract tangential work as a separate issue. The current issue should be narrowed until the task count is within bounds.</action>
</case>
<case condition="Task count below target band (1-3 tasks)">
<action>Log `[WARNING] task count below target band`. Note: a single-task issue is valid for trivial config-only or boilerplate work where no end-to-end verification is required. The agent MAY still append a terminal `type: "e2e"` task for issues modifying user-facing behavior, but it is no longer mandatory.</action>
</case>
<case condition="Issue file contains embedded ## User Stories Ledger and ## ATDD Acceptance Criteria sections">
<action>Read spec from the issue file directly — this is the primary path. Do NOT look for a separate spec.md. Per spec AC-ADHOC-003-07, embedded sections take precedence over spec.md when both exist.</action>
</case>
<case condition="Issue file lacks embedded spec sections (no USER_STORIES_LEDGER or ATDD_ACCEPTANCE_CRITERIA)">
<action>Fall back to reading the adjacent spec.md file in the same issue directory. This is the legacy path — log a notice that the issue file lacks embedded spec sections, then proceed with spec.md as the spec source.</action>
</case>
<case condition="Both issue file embedded sections AND spec.md exist">
<action>Embedded sections take precedence per spec AC-ADHOC-003-07. Read from the issue file; ignore spec.md. Document the precedence decision in a note.</action>
</case>
<case condition="spec.md is empty or missing required sections (fallback path only)">
<action>Halt with Failure_State: "Invalid spec source — missing required sections". Require human to run /deviate-shard first to produce a valid spec-enriched issue.</action>
</case>
<case condition="spec.md is missing or incomplete (fallback path only)">
<action>Continue with available spec sections. Add `[WARNING]` to tasks touching undefined areas.</action>
</case>
<case condition="No test command available from spec source or constitution">
<action>Generate Verification commands using repository conventions (pytest, npm test) as defaults. Document inferred commands in a note.</action>
</case>
<case condition="Circular dependencies detected between tasks">
<action>Detect and reject; require human to resolve dependency graph before task generation.</action>
</case>
<case condition="Post-script rejects output">
<action>Halt, fix the violations, and re-run the post-script.</action>
</case>
</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

