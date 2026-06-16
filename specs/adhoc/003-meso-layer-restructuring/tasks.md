# Implementation Tasks: feat/adhoc/003-meso-layer-restructuring

## Phase 1: Shard & Adhoc Spec Enrichment
**Goal**: Shard and adhoc skills produce spec-enriched issue files with full user stories, Gherkin AC, edge cases, and performance constraints

### Tasks

- TSK-003-01: Enhance shard skill to produce spec-enriched issue files
  - **Type**: Domain_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `ls -la src/deviate/prompts/skills/deviate-shard/SKILL.md && grep -c "USER_STORIES_LEDGER" src/deviate/prompts/skills/deviate-shard/SKILL.md`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-shard/SKILL.md`
  - **Rationale**: US-001 requires shard to generate issue files with embedded spec sections. This is the sole file that defines the shard skill's output format. Modifying its system instructions and output format schema to emit `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[EDGE_CASES_AND_BOUNDARIES]`, and `[PERFORMANCE_CONSTRAINTS]` sections per AC-ADHOC-003-01/02/03.
  - **Details**:
    - **Implementation**: Add `## [USER_STORIES_LEDGER]` section to the shard output format schema with `US-NNN` entries referencing `FR-NNN` from the PRD
    - **Implementation**: Add `## [ATDD_ACCEPTANCE_CRITERIA]` section with bold `**Given**`/`**When**`/`**Then**` Gherkin blocks
    - **Implementation**: Add `## [EDGE_CASES_AND_BOUNDARIES]` and `## [PERFORMANCE_CONSTRAINTS]` sections to the shard issue format template
    - **Implementation**: Update the `SHARD_GENERATION_MANIFEST` and `issue template` blocks in the execution sequence to produce these sections instead of thin stubs
    - **Refactor**: Align section header naming convention with downstream consumers (`[USER_STORIES_LEDGER]` not `[STORIES]`)
    - **Edge Cases**: When an issue has zero FRs (enabling slice), the `US-NNN` entries must still be generated describing the infrastructure value
    - **Acceptance**: Running `deviate shard post` on a mock PRD produces issue files containing all four required spec sections

- TSK-003-02: Enhance adhoc skill to match shard spec-enriched format
  - **Type**: Domain_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `ls -la src/deviate/prompts/skills/deviate-adhoc/SKILL.md && grep -c "USER_STORIES_LEDGER" src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-003-01
  - **Files**:
    - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
  - **Rationale**: US-002 requires adhoc-produced issues to match shard's spec-enriched format (same section headers, same ordering). The adhoc skill must reference the same template structure established in TSK-003-01. AC-ADHOC-003-05/06 require consistency between the two generators.
  - **Details**:
    - **Implementation**: Update adhoc skill's output section instructions to emit the same `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`, `[EDGE_CASES_AND_BOUNDARIES]`, and `[PERFORMANCE_CONSTRAINTS]` sections as shard
    - **Implementation**: Align header ordering in adhoc output to match shard's exact section sequence
    - **Implementation**: Ensure US-NNN entries in adhoc reference `FR-ADHOC-NNN` tokens from `specs/adhoc/prd.md`
    - **Refactor**: Extract shared template reference between shard and adhoc (inline comment pointing to shard for canonical format)
    - **Acceptance**: Comparing an adhoc-produced issue and a shard-produced issue shows identical section header structures in the same order

---

## Phase 2: Specify Removal & Plan Introduction
**Goal**: Legacy specify skill removed, new plan skill created that absorbs its role

### Tasks

- TSK-003-03: Remove deviate-specify skill and stub its CLI entry points
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `test ! -f src/deviate/prompts/skills/deviate-specify/SKILL.md && uv run pytest tests/ -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-specify/SKILL.md`
    - `src/deviate/cli/meso.py`
    - `src/deviate/prompts/auto/specify.md`
  - **Rationale**: US-003 requires the specify SKILL.md file to not exist (Scenario 1) and the `def specify()` CLI entry removed or stubbed (Scenario 2). The auto prompt template must also be removed or preserved depending on whether the meso orchestration pipeline still references it. Tests that invoke `deviate specify` must be updated to reflect the new workflow.
  - **Details**:
    - **Implementation**: Delete `src/deviate/prompts/skills/deviate-specify/SKILL.md`
    - **Implementation**: Remove or stub the `def specify()` typer command in `src/deviate/cli/meso.py` — replace with a function that prints `"Specify phase is removed — use deviatte shard+plan workflow instead"` and exits
    - **Implementation**: Keep `_specify_pre`, `_specify_post` helper functions in meso.py (they may still be referenced by the meso orchestration pipeline `_meso_run`); add deprecation comments
    - **Implementation**: Update `_meso_run` in meso.py to skip the specify phase and go directly to plan → tasks
    - **Implementation**: Update tests in `tests/test_meso/test_specify.py` to expect the new stub behavior or removal
    - **Edge Cases**: Existing sessions in SPECIFY phase — the stub should print a clear migration message pointing to the new workflow
    - **Acceptance**: `ls src/deviate/prompts/skills/deviate-specify/SKILL.md` returns non-zero exit code; `deviate specify --help` shows deprecation notice; full test suite passes

- TSK-003-07: Restore `_specify_pre` worktree creation + issue claiming functionality
  - **Type**: Bug
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_meso/test_specify.py -v && uv run pytest tests/test_cli/test_meso.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: None
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_meso/test_specify.py`
  - **Rationale**: PR review thread C01 identified that `_specify_pre` was stubbed to a deprecation notice in TSK-003-03, removing the only caller of `_try_claim_issue`. This breaks the Meso-layer workflow: `_meso_run` no longer creates worktrees or claims issues, violating the Git Isolation Principle. The worktree+claim logic in `_try_claim_issue` (lines 318-441) is complete and functional — it just needs a surviving caller.
  - **Details**:
    - **Implementation**: Restore `_specify_pre` (line 445) to resolve the issue record from ledger and call `_try_claim_issue`, returning the worktree metadata dict (or failing gracefully). The flow: load record from `issue_id`, call `_try_claim_issue(record, repo_root=Path.cwd(), ledger_path=..., force=force, dry_run=dry_run)`, print worktree path on success, raise `typer.Exit(code=1)` on failure.
    - **Implementation**: Keep `_specify_post` as a no-op stub (post-phase no longer needed — setup is a single pre step).
    - **Implementation**: Update `_meso_run` to call the restored setup step before `_tasks_pre`. Insert the call between the dry-run check (line 905) and the worktree path resolution (line 907). Save the returned `worktree_path` and use it for the `chdir` context — do NOT derive the path a second time.
    - **Implementation**: Update the `deviate specify` Typer CLI entry (line 955) — change its docstring and help text from `"Deprecated: specify has been merged into shard"` to `"Setup: create worktree and claim issue for the given issue ID"`. The command remains `deviate specify` but now represents the worktree+claim step, not spec enrichment.
    - **Implementation**: Update `meso_run_command` docstring from `"Run the meso automated pipeline (specify → tasks)"` to `"Run the meso automated pipeline (setup → tasks)"`.
    - **Implementation**: In `_meso_run`, after the worktree setup call succeeds, transition the session to `"TASKS"` (retaining the existing session advancement logic at line 911-915). The worktree setup step implicitly transitions to `"SPECIFY"` — `_meso_run` should accept `"SPECIFY"` in the subsequent `_load_session_accept` call; or, more robustly, let `_meso_run` handle the session transition directly and not require a `_load_session` guard in the setup step.
    - **Edge Cases**: If `_try_claim_issue` returns `None` (branch on remote, worktree error, push race), `_meso_run` should abort with a clear error message and NOT proceed to tasks. If worktree already exists, `_try_claim_issue` returns the existing worktree path — `_meso_run` should use it normally.
    - **Acceptance**: `deviate specify pre ISS-ADH-003` creates a worktree and claims the issue; `deviate meso run --issue ISS-ADH-003` creates worktree, claims, transitions session, and proceeds to tasks phase; `deviate specify --help` shows setup description, not deprecation notice.
  - **Regression Notes**: TSK-003-03 stubbed `_specify_pre` which broke `_meso_run`'s isolation guarantee. Reverting the stub is intentional — the specify SKILL.md is still removed (TSK-003-03 deleted it), and the shard+plan workflow remains. The only change is that `deviate specify` now does what its pre-phase always did: create a worktree and claim the issue. The spec enrichment and agent invocation that used to happen in specify is absorbed by shard.

- TSK-003-04: Create deviate-plan skill for per-issue localized research
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `ls -la src/deviate/prompts/skills/deviate-plan/SKILL.md && grep -c "plan.md" src/deviate/prompts/skills/deviate-plan/SKILL.md`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-003-03
  - **Files**:
    - `src/deviate/prompts/skills/deviate-plan/SKILL.md`
  - **Rationale**: US-004 requires a new `/deviate-plan` skill that performs per-issue localized codebase research (Scenario 1), produces `plan.md` (Scenario 2), and completes within 200ms (Scenario 3). This is a brand-new skill file following the existing skill template conventions (frontmatter, system instructions, output format, execution sequence).
  - **Details**:
    - **Implementation**: Create `deviate-plan/SKILL.md` with frontmatter: `name: deviate-plan`, `category: deviatdd-meso-layer`, `aliases: [plan, /deviate-plan]`
    - **Implementation**: Write system instructions defining the plan phase: reads spec-enriched issue file (embedded `[USER_STORIES_LEDGER]`, `[ATDD_ACCEPTANCE_CRITERIA]`), scans current codebase state via `git log` and issue ledger, analyses prior issue implementations
    - **Implementation**: Define output format: `plan.md` with implementation strategy, file mappings, risk assessment, and integration point analysis
    - **Implementation**: Define performance constraint: research scan must complete in L_max <= 200ms, zero network calls
    - **Implementation**: Reference existing skill conventions: pointer normalization, markdown backticks for XML elements, output format constraint matching other meso-layer skills
    - **Acceptance**: Skill file exists with all required sections; manual inspection confirms it follows the same structural conventions as other meso-layer skills

---

## Phase 3: Tasks Skill Embedded-First Fallback
**Goal**: Tasks skill consumes spec-enriched issue files directly with fallback to spec.md

### Tasks

- TSK-003-05: Update tasks skill for embedded-first spec consumption
  - **Type**: Domain_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `grep -c "embedded" src/deviate/prompts/skills/deviate-tasks/SKILL.md`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-003-01
  - **Files**:
    - `src/deviate/prompts/skills/deviate-tasks/SKILL.md`
  - **Rationale**: US-005 requires tasks to read embedded spec from issue files (Scenario 1) and fall back to `spec.md` when absent (Scenario 2). The tasks skill's system instructions must be updated to describe this two-tier lookup strategy. AC-ADHOC-003-07/08/09 define the fallback behavior and performance constraint.
  - **Details**:
    - **Implementation**: Update the tasks skill's input resolution instructions to first check the issue file for `## [USER_STORIES_LEDGER]` and `## [ATDD_ACCEPTANCE_CRITERIA]` sections
    - **Implementation**: Add fallback logic description: if embedded sections absent, read from adjacent `spec.md` file in the same issue directory
    - **Implementation**: Update the `spec_path` reference in the skill instructions to accept either the issue file (embedded mode) or spec.md (fallback mode)
    - **Implementation**: Update the execution sequence to note that the issue file itself is now the primary spec source; spec.md lookup is the secondary path
    - **Edge Cases**: What if BOTH issue file embedded sections AND spec.md exist? Embedded takes precedence per spec AC-ADHOC-003-07
    - **Acceptance**: Tasks skill instructions describe the embedded-first lookup; fallback to spec.md is documented as the legacy path

---

## Phase 4: Architecture Documentation Update
**Goal**: All architecture docs reflect the new Shard+Specify → Plan → Tasks workflow

### Tasks

- TSK-003-06: Update DeviaTDD-api.md, DeviaTDD-architecture.md, and constitution for new workflow
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `grep -c "deviate-plan" specs/DeviaTDD-api.md && grep -c "Plan" specs/constitution.md`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-003-03
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `specs/constitution.md`
  - **Rationale**: US-006 requires all three architecture documents to reflect the new workflow. The api doc must describe `Shard+Specify → [HITL Gate 2] → Plan → Tasks → Micro` flow and remove specify as a separate phase (Scenario 1). The architecture doc must show Plan phase and merged Shard+Specify in layer diagrams (Scenario 2). The constitution must update HITL Gate 2 position and add Plan phase to meso-layer section (Scenario 3).
  - **Details**:
    - **Implementation**: In `DeviaTDD-api.md`: Replace the `deviate specify pre/post` section with a note that specify functionality is absorbed into shard; update the meso layer command list to include plan pre/post (even if CLI not yet created, note it as planned)
    - **Implementation**: In `DeviaTDD-architecture.md`: Update layer diagram to show `Shard+Specify` merged block; add `Plan` phase between Gate 2 and Tasks; remove specify as standalone phase in meso-layer description
    - **Implementation**: In `constitution.md`: Update `[1_ARCHITECTURAL_PRINCIPLES]` three-layer description to reference Plan phase; update HITL Gate 2 description to say "after shard, before plan" instead of "after specify"
    - **Implementation**: Replace all references to `/deviate-specify` as a current phase with historical/deprecation references
    - **Edge Cases**: External references to the old workflow (e.g., in AGENTS.md, README, or issue templates) should be checked but are out of scope per spec defensive exclusions
    - **Acceptance**: `grep "deviate-plan" specs/DeviaTDD-api.md` returns at least 1 match; `grep "Plan" specs/constitution.md` finds the phase described; `specs/DeviaTDD-architecture.md` ASCII art diagram shows updated flow

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Shard + Adhoc enrichment) → Phase 2 (Specify removal + Plan creation) → Phase 3 (Tasks fallback) → Phase 4 (Docs)
2. Phase 1 must complete first because Phases 2 and 3 reference the new section format established there
3. Phase 2 (specify removal) gates Phase 4 (docs must reflect removal)

**Critical Dependency Chains**:
- TSK-003-01 (Shard enrichment) → TSK-003-02 (Adhoc format match)
- TSK-003-01 (Shard enrichment) → TSK-003-05 (Tasks fallback — needs to know embedded format)
- TSK-003-03 (Specify removal) → TSK-003-04 (Plan creation — execution order)
- TSK-003-03 (Specify removal) → TSK-003-06 (Docs — must describe removal)
- TSK-003-07 (Worktree+claim restore) — no dependency, can be done in parallel with other tasks

**Risk Hotspots**:
- Tests in `tests/test_meso/test_specify.py` will fail after TSK-003-03 removes the specify CLI entry — this is expected and handled within that task
- TSK-003-07 re-enables `_specify_pre` to call `_try_claim_issue`, reverting the stub from TSK-003-03. This is intentional — the SKILL.md is still removed; the CLI command now does setup (worktree+claim) instead of spec enrichment. The `_meso_run` integration tests must be updated to expect worktree creation as part of the pipeline.

**Merge Conflict Boundaries**:
- `src/deviate/prompts/skills/deviate-shard/SKILL.md` — touched only by TSK-003-01
- `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` — touched only by TSK-003-02
- `src/deviate/cli/meso.py` — touched by TSK-003-03 (specify entry stub) AND TSK-003-07 (restore worktree+claim)
- `src/deviate/prompts/skills/deviate-specify/SKILL.md` — deleted in TSK-003-03
- `src/deviate/prompts/skills/deviate-plan/SKILL.md` — created in TSK-003-04
- `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — touched only by TSK-003-05
- `specs/DeviaTDD-api.md` — touched only by TSK-003-06
- `specs/DeviaTDD-architecture.md` — touched only by TSK-003-06
- `specs/constitution.md` — touched only by TSK-003-06

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
