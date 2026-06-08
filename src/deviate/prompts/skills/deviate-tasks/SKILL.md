---
name: deviate-tasks
description: Decompose spec.md into a granular task decomposition (tasks.md) consisting of autonomous Red-Green-Refactor units (vertical tasks, 30-90 min each). Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.
category: deviatdd-meso-layer
version: 1.0.0
aliases:
  - tasks
  - /deviate-tasks
  - spec:core:tasks
  - spec.core.tasks
  - /tasks
---

**IMPORTANT**: The script `deviate-tasks.sh` lives in this skill's directory (alongside `SKILL.md`) and is NOT on `PATH`. Always invoke it as `deviate tasks`.

<system_instructions>

This system operates strictly as an isolated, deterministic execution compilation pipeline for software implementation strategies and structured technical task decomposition. Your objective is to ingest a JSON contract emitted by the orchestrator script `deviate tasks pre` (which detects the existing worktree claim from `/deviate-specify`, locates `spec.md`, validates its required sections, and checks for optional research artifacts) and produce a granular task decomposition (`tasks.md`) consisting of autonomous Red-Green-Refactor units (vertical tasks, 30-90 min each). Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.

**The "Autonomous R-G-R" Mandate** (applies only to TDD-mode tasks):
- **Red**: Every TDD task starts by writing a failing test (Sociable/Integration).
- **Green**: Every TDD task implements the minimum code to pass the test.
- **Refactor**: Every task (TDD or IMMEDIATE) cleans up code to match idioms and `specs/constitution.md` invariants.
- **Verification-is-Done**: A task is ONLY finished when its `Verification` command passes. No "vibe" confirmation.
- **IMMEDIATE tasks**: Skip the Red/Green cycle. Execute directly then verify.

**The "Workstation" Mandate**:
- **Context Consolidation**: Files that share a logical capability MUST be in the same task.
- **Maximize Signal-to-Noise**: Group files so the agent has full "Workstation" context in a single Turn.

**Meso Workflow Position**: Specify → Tasks → TDD (red-green-refactor)
- **Specify**: Precedes this phase. Created `spec.md`.
- **Tasks** (this phase): Write `tasks.md` only. Commit it. STOP.
- **TDD**: Begins after the tasks artifact is committed.

Research artifacts (`design.md`, `data-model.md`) produced by the `deviate-research` skill may exist alongside `spec.md` and serve as supplementary input for workstation mapping and architectural context.

CRITICAL INFERENCE PHYSICS INVARIANTS:
1. **Context Reuse Rule**: This phase typically follows `/deviate-specify` in the same conversation. Reuse `BRANCH_NAME`, `WORKTREE_PATH`, `ISSUE_ID`, `EPIC_SLUG`, `ISSUE_SLUG` from the specify contract in your context. Do NOT re-run the specify pre-script.
2. **Input Resolution Rule**: The tasks pre-script emits a JSON contract on stdout. Parse `spec_path`, `tasks_target`, `design_path` (optional), `data_model_path` (optional) from that contract directly. Do NOT re-derive.
3. **Prefix Invariance Placement Rule**: All systematic definitions, roles, execution sequences, and parsing schemas sit statically at the absolute head. Volatile parameters (target plan text, code repository file maps) occupy the trailing edge inside `<context>`.
4. **Context-Instruction Isolation (The Markov Blanket)**: Never mix operational instructions or framework requirements inside data payload nodes.
5. **Cohesive Scope Invariant**: Every task line-item, target verification asset, or file node declared in this ledger must map directly onto a named entity or functional acceptance rule within the codebase repository tree.
6. **Transition Status Architecture**: Initialize tasks strictly with empty completion brackets `- [ ] `. You must NEVER emit `- [x]` (completed) or `- [/]` (in-progress) markers.
7. **Output Schema Constraint**: Write the task ledger content directly to `<tasks_target>` using the Standard Markdown format defined in `<output_format_schemas>`. The file content is exactly the ledger body — no preamble, no postamble, no XML wrapper tags. The post-script will read the file, validate, and commit.

</system_instructions>

<prerequisites>
<required_scripts_path>The script is colocated with SKILL.md inside the skill directory, NOT on $PATH. Always reference it as deviate tasks.</required_scripts_path>
<failure_mode>ERROR: Operational orchestrator not found at deviate tasks. Stop execution immediately and notify the host user.</failure_mode>
</prerequisites>

<execution_sequence>
1. `cd` into the worktree (using the `worktree_full` path from your context) and run the pre-script to validate `spec.md` has required sections and emit a JSON contract:
   ```
   deviate tasks pre
   ```
   The pre-script detects the worktree via `git rev-parse` — it must run from inside the worktree. The contract on stdout contains: `branch_name`, `worktree_full`, `spec_path` (the spec.md you must read), `tasks_target` (where the post-script will write tasks.md), `design_path` (optional, from research skill), `data_model_path` (optional, from research skill), `reuse_from_specify: true`.
   - If the pre-script emits `STATUS: NOT_IN_WORKTREE`, `STATUS: INVALID_BRANCH`, `STATUS: SPEC_NOT_FOUND`, or `STATUS: TASKS_FAILED`, terminate immediately and surface the status.

2. Read `spec_path` (the full file on disk) for user stories, acceptance criteria, and project structure. If `design_path` or `data_model_path` are present in the contract, read those too for architectural context and data schema definitions.

3. **Workstation Mapping**: Map all files touched by each user story from `spec.md`'s `SYSTEM_TOPOLOGY_MAPPING` and `PROJECT_STRUCTURE` sections. Group related files (e.g., a service and its test file, a handler and its route registration) into workstation clusters. Derive phases from logical groupings of related user stories.

4. **Task Construction**:
    - **4a. Group Items**: Group workstation clusters into **Batched Logical Units** (vertical slices), each delivering one or more related acceptance criteria.
    - **4b. Assign Execution_Mode**: Decide **per task** based on the nature of the work. A single phase can contain both TDD and IMMEDIATE tasks.
    - **4c. Assign Verification**: Assign each slice a `Verification` command based on the test strategy implied by the acceptance criteria.
    - **4d. Validate Structure**: Ensure no "Testing-only" tasks — tests are the mandatory **Red** phase of every TDD task.
    - **4e. File Rationale Assignment**: For each task, add `[File_Rationale]` explaining WHY each file is touched.

5. **Traceability Audit**:
    - Read spec.md ANTI_GOALS section and verify no task touches files related to anti-goals
    - Read design.md RISK_REGISTER or CONSTRAINTS sections (if available) and incorporate into task generation
    - Verify phase-to-story mapping
    - Flag orphaned files

6. Apply granularity rules:
    - **Slice over Step**: Tasks are defined by **What they add to the feature**, not the technical step.
    - **30-90 Minute Rule**: If a task takes < 30 min, merge it. If > 90 min, split it only while maintaining verticality.
    - **Ambiguity Resolution**: If a plan item spans multiple capabilities, create separate tasks per capability with explicit `Dependency` links.

7. Transpile the final task decomposition into format-compliant Markdown per `<output_format_schemas>` and write it directly to `<tasks_target>` (the relative path from the contract). Write exactly the tasks content — no preamble, no postamble, no XML wrapper tags.

8. Run the post-script to validate, commit (still inside the worktree from step 1):
   ```
   deviate tasks post
   ```
   The post-script reads the file, validates required sections, task ID format (`T{NNN}`), locked checkboxes (`- [ ] `, never `- [x]`), and file traceability tags, then commits. If validation fails, it prints a diagnostic. Fix the file and re-run. Re-run with `--force` only with documented justification.

**TERMINATE HERE. Do NOT proceed to implementation. Hand off to the TDD phase.**
</execution_sequence>

<output_format_schemas>
<format_contract>
Render output to `<tasks_target>` using the following format. No XML wrapper tags — the file content is the ledger body.

**CRITICAL FORMAT RULES:**
- `[Files_Touched]` MUST be followed by indented file paths on separate lines (not inline)
- `[Task_Details]` MUST be followed by indented bullet points on separate lines (not inline)
- `[Dependency]` MUST be inline: `T001` not on separate line

**CRITICAL TASK ID CONSTRAINT:**
- Task IDs MUST follow the format `T{NNN}` where `NNN` is exactly 3 zero-padded digits, starting from `T001`.
- Examples of VALID task IDs: `T001`, `T002`, `T003`, `T010`, `T099`
- Examples of INVALID task IDs (DO NOT use): `TSK-001-01`, `TASK_1`, `T1`, `T-001`, `Task1`, `TSK001`
- The post-script validator enforces this exact pattern: `T` followed by exactly 3 digits (no dashes, no prefixes, no suffixes).

**TASK STRUCTURE CONSTRAINTS** — every task MUST contain:
- **Task_ID**: `T{NNN}` (zero-padded, sequential)
- **Task_Type**: `Feature_Batch | Infra_Batch | Domain_Batch | Bugfix | Migration | Config`
- **Execution_Mode**: `TDD | IMMEDIATE` (default: `TDD`)
  - `TDD`: Full Red-Green-Refactor cycle (write failing test first)
  - `IMMEDIATE`: Execute directly without test-first (skip [RED] in Task_Details)
- **Test_Strategy**: `Sociable_Unit | Integration | Solitary_Unit` (required if Execution_Mode is TDD)
- **Description**: High-density objective (e.g., "Implement S3 multipart upload with error boundaries").
- **Verification**: A **Deterministic CLI Command** (e.g., `pytest tests/unit/test_s3.py`).
- **Estimated_Time**: Time estimate in format `30-90 minutes` or `60 minutes`.
- **Files_Touched**: List of absolute or project-relative paths (multi-line, indented, minimum 2 files).
- **Task_Details**: **CRITICAL** — Must contain 4-8 detailed bullet points with explicit R-G-R breakdown:
  - **[RED]**: Specific test file, test cases to write, and assertions
  - **[GREEN]**: Exact functions/methods to implement, signatures, and logic
  - **[REFACTOR]**: Code quality improvements, pattern alignment
  - **[EDGE_CASES]**: Error handling, boundary conditions
  - **[ACCEPTANCE]**: Concrete "done" criteria beyond test passing
- **Dependency**: (Optional) `T{NNN}` if this task requires another task to complete first (inline value).

**TASK_DETAILS QUALITY RULES:**
- Minimum 4 bullet points, maximum 8
- For TDD tasks: MUST include at least one `[RED]` bullet with specific test case name and assertion
- For TDD tasks: MUST include at least one `[GREEN]` bullet with function signature and logic
- For IMMEDIATE tasks: Use `[IMPLEMENT]` instead of `[RED]`/`[GREEN]`
- SHOULD include `[EDGE_CASES]` for error handling scenarios
- SHOULD include `[ACCEPTANCE]` with concrete "done" criteria

**FILE_TRACEABILITY RULES:**
- `[File_Rationale]` is REQUIRED on every task (prevents misaligned scope)
- Must explain WHY each file in `[Files_Touched]` is being modified
- Must tie each file to specific story identifiers and acceptance criteria from spec.md
- Every file in `[Files_Touched]` MUST be justified in `[File_Rationale]`
- Files without justification are flagged as potential scope creep

**DETERMINISM RULES:**
- **No Vibe Coding**: Any task without a `Verification` command is invalid.
- **No Layered Tasks**: Reject any task that doesn't produce a testable outcome.
- **No Vague Details**: Reject any task with fewer than 4 `Task_Details` bullets. TDD tasks must have `[RED]`/`[GREEN]` markers; IMMEDIATE tasks must have `[IMPLEMENT]` markers.
- **Path Integrity**: Use absolute paths for all cross-references.
- **Test-First Enforcement**: Every TDD task's `[GREEN]` bullet MUST have a corresponding `[RED]` bullet that defines the test it passes. IMMEDIATE tasks are exempt (use `[IMPLEMENT]` instead).

**OUTPUT TEMPLATE** — the complete file should follow this structure:
```markdown
# Implementation Tasks: {BRANCH_NAME}

## [PHASE_1]: <Feature Slice Name>
[Phase_Goal]: <what capability this slice delivers>

### [TASKS]
- [ ] [T001] <Description of Vertical Slice>
  - [Task_Type]: Feature_Batch
  - [Execution_Mode]: TDD
  - [Test_Strategy]: Sociable_Unit
  - [Verification]: <Deterministic command>
  - [Estimated_Time]: 60 minutes
  - [Files_Touched]:
    - path/to/file1.ts
    - path/to/file2.ts
  - [File_Rationale]: <Why these files? Tie to specific story US_### and AC>
  - [Task_Details]:
    - [RED] Write failing test: `<test_name>()` with assertion that <expected>
    - [GREEN] Implement `<function>(<params>): <return>` with <logic>
    - [REFACTOR] <code quality improvement>
    - [EDGE_CASES] Handle <error scenario> by <action>
    - [ACCEPTANCE] <concrete done criteria>

- [ ] [T002] <Description>
  - [Task_Type]: Feature_Batch
  - [Execution_Mode]: IMMEDIATE
  - [Verification]: <command>
  - [Estimated_Time]: 60 minutes
  - [Dependency]: T001
  - [Files_Touched]:
    - path/to/file3.ts
  - [File_Rationale]: <Why these files?>
  - [Task_Details]:
    - [IMPLEMENT] Implement `<function>()` with <logic>
    - [REFACTOR] <improvement>
    - [ACCEPTANCE] <criteria>

---

## [IMPLEMENTATION_STRATEGY]
[Execution_Order]:
1. Phase 1 -> Phase 2 (Logical dependency order)

[Critical_Dependency_Chains]:
- T001 (Schema) must precede T002 (API)

[Risk_Hotspots]:
- [RISK_01]: High coupling in `user.service.ts`

[Merge_Conflict_Boundaries]:
- Files touched by multiple phases: [list_files]
```

**Write the entire content directly to `<tasks_target>`** as the file's full content. No wrapping tags, no preamble, no postamble. The post-script reads the file and commits it.
</format_contract>
</output_format_schemas>

<edge_case_handling>
<case condition="Pre-script emits STATUS: NOT_IN_WORKTREE or STATUS: SPEC_NOT_FOUND">
<action>Stop. The /deviate-specify phase must complete (and commit spec.md) before tasks can run. Surface the status to the human operator.</action>
</case>
<case condition="spec.md is empty or missing required sections">
<action>Halt with Failure_State: "Invalid spec.md — missing required sections". Require human to run /deviate-specify first.</action>
</case>
<case condition="spec.md is missing or incomplete">
<action>Continue with available spec sections. Add `[WARNING]` to tasks touching undefined areas.</action>
</case>
<case condition="No test command available from spec.md or constitution">
<action>Generate Verification commands using repository conventions (pytest, npm test) as defaults. Document inferred commands in a note.</action>
</case>
<case condition="Circular dependencies detected between tasks">
<action>Detect and reject; require human to resolve dependency graph before task generation.</action>
</case>
<case condition="Post-script rejects output">
<action>Halt, fix the violations, and re-run the post-script. Task check-boxes are programmatically locked; never emit `- [x]`.</action>
</case>
</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

