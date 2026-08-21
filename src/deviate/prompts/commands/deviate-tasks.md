---
name: deviate-tasks
description: Decompose issue intent plus plan.md's authoritative acceptance contract into autonomous Red-Green-Refactor units.
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

<system_instructions>

This system operates strictly as an isolated, deterministic execution compilation pipeline for software implementation strategies and structured technical task decomposition. Your objective is to ingest a JSON contract emitted by the orchestrator script `deviate tasks pre` (which detects the existing worktree claim, locates the spec source, validates its required sections, and validates the plan.md prerequisite) and produce a granular task decomposition (`tasks.md`) consisting of autonomous Red-Green-Refactor units (vertical tasks; each task is one observable fail-to-pass contract, named 30-90 min). Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.

**Two-Source Contract Consumption**: Read macro intent from `spec_path`: topology, problem/scope boundaries, upstream FR/AC tokens, user stories, `AO-NNN` outlines, edge cases, performance constraints, verification targets, and `flow_refs`. Read finalized Gherkin only from `plan_path` → `## Acceptance Contract`. Plan `AC-PLAN-NNN` scenarios are authoritative when legacy issue/spec Gherkin also exists; never copy or fall back to stale macro Gherkin.

**The "Autonomous R-G-R" Mandate** (applies only to TDD-mode tasks):
- **Red**: Every TDD task starts by writing a failing test (Sociable/Integration).
- **Green**: Every TDD task implements the minimum code to pass the test.
- **Refactor**: Every task (TDD or IMMEDIATE) cleans up code to match idioms and `specs/constitution.md` invariants.
- **Verification-is-Done**: A task is ONLY finished when its `Verification` command passes. No "vibe" confirmation.
- **IMMEDIATE tasks**: Skip the Red/Green cycle. Execute directly then verify.

**The "Workstation" Mandate**:
- **Context Consolidation**: Files that share a logical capability MUST be in the same task.
- **Maximize Signal-to-Noise**: Group files so the agent has full "Workstation" context in a single Turn.

**Meso Workflow Position**: Shard/Adhoc → Plan → Tasks → TDD (Gate 2 removed — see constitution §1)
- **Shard/Adhoc**: Produces issue intent with user stories and acceptance outlines.
- **Plan**: Performs fresh research and writes the authoritative Gherkin Acceptance Contract.
- **Tasks**: Maps every `AC-PLAN-NNN` to executable work, then commits the task manifest. No human-approval gate sits between Tasks and Micro (Gate 2 was removed in constitution 0.8.0) — `deviate run` chains meso into micro end-to-end.
- **TDD**: Begins immediately after Tasks commits; the system auto-advances without human approval.

Research artifacts (`design.md`, `data-model.md`) produced by the `deviate-research` skill may exist alongside the spec source and serve as supplementary input for workstation mapping and architectural context.

CRITICAL INFERENCE PHYSICS INVARIANTS:
1. **Context Reuse Rule**: This phase follows `/deviate-plan` in the same conversation — plan.md has already been written. Reuse `BRANCH_NAME`, `WORKTREE_PATH`, `ISSUE_ID`, `EPIC_SLUG`, `ISSUE_SLUG` from the plan contract in your context. Do NOT re-run the plan or shard pre-script.
2. **Cohesive Scope Invariant**: Every task line-item, target verification asset, or file node declared in this ledger must map directly onto a named entity or functional acceptance rule within the codebase repository tree.

</system_instructions>

<consumer_repository_boundary>
Assume the consumer repository already has the DeviaTDD CLI, agent skills, and existing flow catalog. Every task must implement or verify requested application behavior and cite its issue story plus `AC-PLAN-NNN`. Existing `flow_refs` are read-only traceability. Do not emit tasks for DeviaTDD setup, agent skills or slash commands, flow authoring/index synchronization, release scaffolding, or workflow-ledger maintenance, and do not list those preconditions in generated `tasks.md`. Any meta-target task halts with `META_WORK_NOT_ALLOWED`.

**App-verification E2E is NOT meta-work**: A closing `[E2E]` task whose only target is the consumer's own application E2E surface (`tests/e2e/`, `e2e/`, or the consumer's configured E2E command) is application *verification*, not a DeviaTDD-maintenance task. It is always allowed. `META_WORK_NOT_ALLOWED` applies only when a task targets DeviaTDD itself (setup, agent skills, slash commands, flow catalog, release scaffolding, workflow ledgers).
</consumer_repository_boundary>


<execution_sequence>
1. `cd` into the worktree (using the `worktree_full` path from your context) and run the pre-script to detect the worktree and emit a JSON contract:
   ```
   deviate tasks pre
   ```
   The contract contains `spec_path`, authoritative `plan_path`, and `tasks_target`. Halt on `PLAN_NOT_FOUND`, `PLAN_ACCEPTANCE_CONTRACT_MISSING`, or `PLAN_ACCEPTANCE_CONTRACT_INVALID`; `--force` MUST NOT cause fallback to issue-level Gherkin.

2. Read `spec_path` for macro intent sections only. Read `plan_path` for implementation strategy, workstation mapping, risks, integration points, and the complete `## Acceptance Contract`. If both artifacts contain Gherkin, ignore issue/spec Gherkin and use `AC-PLAN-NNN` exclusively.

3. **Workstation Mapping**: Map all files touched by each user story from the spec source's `SYSTEM_TOPOLOGY_MAPPING` and `PROJECT_STRUCTURE` sections (whether from embedded `[USER_STORIES_LEDGER]` in the issue file or from `spec.md`). Group related files (e.g., a service and its test file, a handler and its route registration) into workstation clusters. Derive phases from logical groupings of related user stories.

4. **Task Construction**:
    - **4a. Group Items**: Group workstation clusters into **Batched Logical Units** (vertical slices), each delivering one or more related acceptance criteria.
     - **4b. Assign Execution_Mode**: Decide **per task** using this decision tree. Run it fresh for every task:

        0. Is this task **Type**: `Verification_Batch`? → **IMMEDIATE** (hard type→mode lock — never TDD; verification batches are not a Red-Green-Refactor cycle)
        1. Does this task modify **only config, docs, constants, schemas, or trivial boilerplate**? → **IMMEDIATE**
        2. Does this task **refactor existing code without changing behavior** and have **existing test coverage**? → **IMMEDIATE**
        3. Does this task introduce **new business logic, state mutations, API endpoints, or integration boundaries**? → **TDD**
        4. Does this task fix a **bug**? → **TDD** (write regression test first)
        5. Does this task have **non-trivial acceptance criteria** that aren't trivially verifiable? → **TDD**
        6. Otherwise → **IMMEDIATE** (when in doubt, prefer IMMEDIATE over speculative TDD)
        7. Does this task **connect/wire already-tested components** via subprocess, API, or message passing? → **TDD** with system-edge mock boundary (mock `subprocess.Popen`, assert CLI args/env/stdin)

        A single phase can contain both modes. Do NOT default to TDD — TDD carries cost; use it where it earns its keep. Never emit `Mode: TDD` for `Verification_Batch`.
    - **4c. Assign Verification**: Assign each slice a `Verification` command based on the test strategy implied by the acceptance criteria.
    - **4d. Validate Structure**: Ensure no "Testing-only" tasks — tests are the mandatory **Red** phase of every TDD task.
    - **4e. File Rationale Assignment**: For each task, add `[File_Rationale]` explaining WHY each file is touched.
    - **4f. Closing E2E Task**: If the issue's `spec_path`/`plan_path` carries user-facing `flow_refs` (Product layer), or the design implies a real user-facing workflow (CLI command execution, Web browser flow, API request/response cycle), emit a **final closing `[E2E]` task** that authors the consumer's application E2E surface. It MUST:
        - Use **Type**: `Verification_Batch`, **Mode**: **IMMEDIATE** (E2E authoring is not a Red-Green-Refactor cycle), **Test Strategy**: `Integration`, and a `[E2E]` marker in its description line so the ``deviate e2e`` phase (`STEP_6`) discovers it.
        - Set **Verification** to the consumer's E2E command, resolved from the same source as the E2E phase contract's `e2e_command` (constitution ``E2E command`` key, else repo convention: ``bats tests/e2e/``, Playwright, pytest-based OAS/HTTP, etc.).
        - List **Files** under the consumer's E2E dir only (e.g. ``tests/e2e/e2e_<slug>.bats``, ``tests/e2e/<slug>.spec.ts``). Do NOT touch ``src/`` or pytest unit test files.
        - In **Details**, give **Implementation + Edge Cases** bullets naming the concrete user-facing scenarios: the happy path (the "money maker") and at least one critical-failure path, driven by the resolved ``flow_refs``. Use an **Acceptance** bullet: ``<E2E command> exits 0``.
        - Be emitted **last** in the ledger with no forward ``Dependency``, so the micro runner consumes it last and the ``deviate e2e`` post-phase's "all tasks terminal" precondition stays valid.
    - **Skip the closing E2E task** (no bullet for it) when the issue touches only library/config/schema internals with no user-facing workflow — do not manufacture empty E2E files.
    - **Consumer Implementation Audit**: Every task has an application implementation or application verification target tied to a named story and acceptance criterion. A task whose primary target is DeviaTDD setup, an agent skill, a slash command, a flow file/index, release scaffolding, or a workflow ledger is invalid; halt with `META_WORK_NOT_ALLOWED`.

5. **Traceability Audit**:
    - Read the spec source's `SCOPE_BOUNDARIES > Defensive Exclusions` section and verify no task touches files related to anti-goals
    - Read `design.md` `RISK_REGISTER` or `CONSTRAINTS` sections (if available) and incorporate into task generation
    - Verify phase-to-story mapping
    - Flag orphaned files

6. Apply granularity rules:
    - **Slice over Step**: Tasks are defined by **What they add to the feature**, not the technical step.
    - **30-90 Minute Rule**: 30–90 names one observable fail-to-pass contract (Beck: exactly one item on the test list), not a wall-clock splitter. One TDD task equals one fail-to-pass contract — not one assert, not one feature file, not a whole epic. Merge fake splits of the same AC (test-skeleton vs implement vs add-the-route). Split only when a GREEN packet would bury the contract (mixed 10-file / >400 LOC); JUDGE still sees one behavior (safe default ≲2 files / ≲3 hunks / ≲30 production LOC; review ceiling <200 LOC typical / 400 max).
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
- **Type**: `Feature_Batch | Infra_Batch | Domain_Batch | Bugfix | Migration | Config | Verification_Batch`
- **Mode**: `TDD | IMMEDIATE` (no default — apply the decision tree at step 4b). **Type→Mode lock**: `Verification_Batch` MUST be `IMMEDIATE` — never emit `Mode: TDD` for that type.
  - `TDD`: Full Red-Green-Refactor cycle. **Use for**: New business logic, state mutations, integration boundaries, or non-trivial acceptance criteria. Never for `Verification_Batch`.
  - `IMMEDIATE`: Execute directly without test-first. **Use for**: every `Verification_Batch` (hard lock — not only the closing E2E task), trivial updates (config, docs, constants), pure refactoring with existing test coverage, or low-risk boilerplate where testing cost outweighs regression risk.
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
<action>Stop. `/deviate-shard` or `/deviate-adhoc` must produce an issue containing user stories and `## Acceptance Outline`.</action>
</case>
<case condition="Pre-script emits STATUS: PLAN_NOT_FOUND">
<action>Halt. `/deviate-plan` must produce plan.md before tasks can run.</action>
</case>
<case condition="Pre-script emits STATUS: PLAN_ACCEPTANCE_CONTRACT_MISSING or PLAN_ACCEPTANCE_CONTRACT_INVALID">
<action>Halt. Never fall back to issue-embedded or legacy spec.md Gherkin; re-run Plan.</action>
</case>
<case condition="Issue and plan both contain Gherkin">
<action>Use plan.md `## Acceptance Contract` exclusively. Treat issue/spec Gherkin as stale legacy content.</action>
</case>
<case condition="Issue source lacks User Stories Ledger or Acceptance Outline">
<action>Halt with INCOMPLETE_ISSUE_OUTLINE and regenerate the shard/adhoc issue.</action>
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
<case condition="Task targets only DeviaTDD setup, agent skills, flow catalog maintenance, release scaffolding, or workflow-ledger maintenance">
<action>Halt with `META_WORK_NOT_ALLOWED`; do not write the task set.</action>
</case>
</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

