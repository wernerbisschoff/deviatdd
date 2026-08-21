# Implementation Tasks: `feat/adhoc/018-one-behavior-rgr-granularity`

## Phase 1: One-Behavior Shard and Fail-to-Pass Task
**Goal**: Pass 1.5 allows one user-visible shard. Each TDD task is one fail-to-pass contract. Specs match that policy in the same change set (constitution §1 Four-Layer Architecture; constitution §5 CHANGELOG discipline).

### Tasks

- TSK-018-01: Recast shard Pass 1.5 and tasks 30-90 to one fail-to-pass contract
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `test -z "$(rg -n "Target range: 4" src/deviate/prompts/commands/deviate-shard.md src/deviate/prompts/auto/shard.md || true)" && rg -n "SLICE_CAP_EXCEEDED|Hard ceiling: 10|1 is legal" src/deviate/prompts/commands/deviate-shard.md src/deviate/prompts/auto/shard.md && test -z "$(rg -n "If a task takes < 30 min" src/deviate/prompts/commands/deviate-tasks.md src/deviate/prompts/auto/tasks.md || true)" && rg -n "fail-to-pass|one observable behavior" src/deviate/prompts/commands/deviate-tasks.md src/deviate/prompts/auto/tasks.md && test -z "$(rg -n "Target: 4-8 issues|Target 4-8 issues|Target 4-8 tasks" specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md || true)" && rg -n "fail-to-pass" CHANGELOG.md`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/prompts/commands/deviate-shard.md`
    - `src/deviate/prompts/auto/shard.md`
    - `src/deviate/prompts/commands/deviate-tasks.md`
    - `src/deviate/prompts/auto/tasks.md`
    - `src/deviate/prompts/core/micro-shared.md`
    - `src/deviate/prompts/auto/refactor.md`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: US-018-01 / `AC-PLAN-001` need Pass 1.5 in `deviate-shard.md` and `auto/shard.md` to drop the `Target range: 4` floor while `SLICE_CAP_EXCEEDED` and hard ceiling 10 stay. US-018-02 / `AC-PLAN-002` need the tasks pair plus `micro-shared.md` and `auto/refactor.md` to name one fail-to-pass contract instead of `If a task takes < 30 min, merge it`. US-018-03 / `AC-PLAN-003` keep Pass 3 / Pass 3.5 / Pass 5 and still split a mixed 10-file / >400 LOC GREEN packet; JUDGE default stays ≲2 files / ≲3 hunks / ≲30 production LOC with review ceiling <200 LOC typical / 400 max. `AC-PLAN-004` requires `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same implementation commit as the prompt edits (AGENTS.md Spec Alignment; constitution §5). `**Flow References**: []` matches plan.md `## Product Layer Anchors`; this task still maps US-018-01 through US-018-03 onto `AC-PLAN-001` through `AC-PLAN-004`.
  - **Details**:
    - **Implementation**: In `src/deviate/prompts/commands/deviate-shard.md` Pass 1.5 (invariants ~line 30 and ICoT ~line 52) and `src/deviate/prompts/auto/shard.md` Pass 1.5 (~line 44), replace `Target range: 4–8` / `Target range: 4-8` with as-few-as-needed wording that states `1 is legal`, keeps `Hard ceiling: 10`, and still halts with `SLICE_CAP_EXCEEDED` when draft count exceeds 10 then re-clusters until count ≤ 10. Leave Pass 3, Pass 3.5, and Pass 5 verbatim (`AC-PLAN-001`, `AC-PLAN-003`).
    - **Implementation**: In `src/deviate/prompts/commands/deviate-shard.md` `vertical_slicing` step 5 (~line 122), replace `it must warrant its own spec + plan phase` so one user-visible behavior is enough. Do not invent extra slices to look non-trivial (`AC-PLAN-001`, US-018-01).
    - **Implementation**: In `src/deviate/prompts/commands/deviate-tasks.md` (~lines 17 and 97) and `src/deviate/prompts/auto/tasks.md` (~lines 5 and 39), recast `vertical tasks, 30-90 min each` and the **30-90 Minute Rule**. Delete `If a task takes < 30 min, merge it`. Name one observable fail-to-pass contract. Forbid fake splits of the same `AC-PLAN-NNN` (test-skeleton vs implement vs add-the-route). Keep the TASK STRUCTURE CONSTRAINTS Details 4–8 bullet quota and the Estimated Time field format. In `src/deviate/prompts/core/micro-shared.md` (~line 7) and `src/deviate/prompts/auto/refactor.md` (~line 10), keep one R-G-R cycle per task and state that the Logical Unit is one fail-to-pass contract, not a duration floor. Restate that an oversized mixed 10-file / >400 LOC GREEN packet still splits and that JUDGE still sees ≲2 files / ≲3 hunks / ≲30 production LOC with review ceiling <200 LOC typical / 400 max (`AC-PLAN-002`, `AC-PLAN-003`, US-018-02, US-018-03).
    - **Implementation**: In `specs/DeviaTDD-api.md` Granularity Guidelines (~lines 254–260), replace `Target: 4-8 issues per feature shard` and `Pass 1.5 (Slice Cap Gate) hard-enforces the 4–8 / max-10 cap` with as-few-as-needed, min 1, max 10, and `SLICE_CAP_EXCEEDED` as the over-10 halt. In `specs/DeviaTDD-architecture.md` Macro Shard (~line 92) drop `Target 4-8 issues per feature shard` and keep minimum 1 issue / maximum 10 issues. In Meso Granularity (~line 142) drop `Target 4-8 tasks per issue` and recast the unit as one fail-to-pass contract per task with min 1 / max 10. Append a `CHANGELOG.md` `[Unreleased]` Changed bullet that records the Pass 1.5 floor drop and the tasks fail-to-pass recast. Leave ISS-ADH-017 retry wording untouched (`AC-PLAN-004`).
    - **Refactor**: Keep each auto/command pair aligned (ISS-ADH-016 identical-middle). Use the same Pass 1.5 tokens in both shard files. Use the same fail-to-pass tokens in both tasks files.
    - **Edge Cases**: `rg` still finds `SLICE_CAP_EXCEEDED` and `Hard ceiling: 10`. Details 4–8 quota remains. `src/deviate/prompts/core/style-ste.md` still contains the STE example `30-90 minutes`. `src/deviate/cli/micro.py` is unmodified. No test invokes un-mocked `deviate.cli.micro._run_pytest`. Eight independent user-visible verticals still emit eight issues.
    - **Acceptance**: Demonstration-path `rg` pins pass. Shard prompts omit `Target range: 4`. Tasks prompts omit `If a task takes < 30 min`. API and architecture omit `Target: 4-8 issues`, `Target 4-8 issues`, and `Target 4-8 tasks`. `CHANGELOG.md` `[Unreleased]` carries the policy bullet.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (`TSK-018-01`) — one IMMEDIATE wording change set

**Critical Dependency Chains**:
- None. `TSK-018-01` is the only task.

**Risk Hotspots**:
- Auto/command shard or tasks pair drift if one file of a pair is skipped (ISS-ADH-016 identical-middle).
- Accidental removal of cap 10 or `SLICE_CAP_EXCEEDED`.
- Accidental removal of the Details 4–8 bullet quota while dropping the shard 4–8 floor.
- Leftover `Target 4-8` wording in `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md`.

**Merge Conflict Boundaries**:
- Single-task file set: `src/deviate/prompts/commands/deviate-shard.md`, `src/deviate/prompts/auto/shard.md`, `src/deviate/prompts/commands/deviate-tasks.md`, `src/deviate/prompts/auto/tasks.md`, `src/deviate/prompts/core/micro-shared.md`, `src/deviate/prompts/auto/refactor.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/018-one-behavior-rgr-granularity.md` (frontmatter field: `flow_refs`)
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
