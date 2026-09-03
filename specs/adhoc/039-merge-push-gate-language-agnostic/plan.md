## Plan Summary
- **Issue**: ISS-ADH-039 — Make deviate-merge push gate language-agnostic via repo mise tasks
- **Implementation Strategy**: Rewrite `.githooks/pre-push` to drop the Python file filter and run repo `mise` checks on every non-empty push, then mirror the body byte for byte into `deviate-merge.md` and update the `TestMergePromptPushGate` pins.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-3 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Push with zero Python changes runs repo checks and blocks on failure**
- **Source Outline**: `AO-039-01`
- **Upstream Traceability**: `US-039-01`, `FR-ADHOC-039`, `AC-ADHOC-039-01`
- **Current-Code Evidence**: `.githooks/pre-push:_gate_block_lines`
- **Given**: A repo push whose diff contains no Python files
- **When**: The operator pushes or `deviate merge` runs the inline push gate
- **Then**: The gate runs `mise run format-check`, `mise run lint`, and the test task, and halts with `Failure_State: Push_Gate_Failed` plus tool stderr verbatim on any failure
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Freshly squashed branch with no upstream resolves base via HEAD~1**
- **Source Outline**: `AO-039-01`
- **Upstream Traceability**: `US-039-01`, `FR-ADHOC-039`, `AC-ADHOC-039-01`
- **Current-Code Evidence**: `.githooks/pre-push:upstream`
- **Given**: A freshly squashed branch with no `@{u}` upstream
- **When**: The push gate resolves its comparison base
- **Then**: The gate uses `HEAD~1` as the base, and exits 0 only when the diff is empty or no parent exists
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Python repos keep equivalent protection**
- **Source Outline**: `AO-039-02`
- **Upstream Traceability**: `US-039-01`, `FR-ADHOC-039`, `AC-ADHOC-039-02`
- **Current-Code Evidence**: `tests/unit/test_meso/test_auto_prompt_templates.py:TestMergePromptPushGate`
- **Given**: A Python repo push with Python changes
- **When**: The push gate runs
- **Then**: Lint, format check, and affected or full tests run, ruff or test failure blocks the push, and a missing or empty `.testmondata` falls back to `mise run test` never a silent pass
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Hook and prompt copies stay byte-equivalent with updated pins**
- **Source Outline**: `AO-039-02`
- **Upstream Traceability**: `US-039-01`, `FR-ADHOC-039`, `AC-ADHOC-039-02`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-merge.md:Run the push gate`
- **Given**: The rewritten hook and its inline prompt copy
- **When**: `TestMergePromptPushGate` runs
- **Then**: The prompt gate body matches `.githooks/pre-push` on non-blank non-comment lines, pins assert the new mise-task behavior not the old `*.py` filter, and a repo without the expected `mise` tasks errors plainly never silently passes
- **Verification Mode**: automated

## Workstation Mapping
- **.githooks/pre-push**: Core change — drop the `*.py` filter and vacuous pass, run mise checks on every non-empty push
  - **Current State**: Filters diff on `*.py`, exits 0 when no Python files change, runs ruff on changed files plus testmon
  - **Changes Required**: Remove the Python filter and early exit, keep base resolution plus empty-diff exit 0, run `mise run format-check`, `mise run lint`, then testmon-or-full-suite; error plainly when a required mise task is missing
  - **Integration Surface**: `mise.toml` task names, `deviate-merge.md` inline copy, `TestMergePromptPushGate`
- **src/deviate/prompts/commands/deviate-merge.md**: Mirror copy of the hook body
  - **Current State**: Inlines the old Python-filtered gate body verbatim
  - **Changes Required**: Replace the fenced gate block byte for byte with the new hook body, update surrounding prose that names Python-only behavior
  - **Integration Surface**: `.githooks/pre-push`, `TestMergePromptPushGate` drift test
- **tests/unit/test_meso/test_auto_prompt_templates.py**: Pin updates for the new gate
  - **Current State**: `TestMergePromptPushGate` pins `*.py` filter, testmon fallback, hook/prompt line-set equality
  - **Changes Required**: Update pins to the new body, keep the line-set equality invariant, add a pin that the old vacuous-pass filter is gone
  - **Integration Surface**: `.githooks/pre-push`, `deviate-merge.md`

## Implementation Strategy
- **Phase 1**: Rewrite hook, mirror into prompt, update test pins
  - **Files**: `.githooks/pre-push`, `src/deviate/prompts/commands/deviate-merge.md`, `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Approach**: Edit the hook first, copy its body verbatim into the prompt fence, then update the pin assertions to the new strings
  - **Verification**: `mise run test` for the pin class plus `mise run lint` and `mise run format-check`

## Data Flow Analysis
- Input: push ref range resolved to a base (`@{u}` merge-base else `HEAD~1`, exit 0 with neither). Transform: empty-diff check exits 0, else sequential `mise run format-check`, `mise run lint`, test task (`mise run test-affected` when `.testmondata` is non-empty else `mise run test`). Output: exit 0 on clean, non-zero exit surfaces as `Failure_State: Push_Gate_Failed` with tool stderr verbatim in the merge flow. Missing mise task produces a plain error, never exit 0.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hook/prompt drift | Medium | Medium | Keep the line-set equality test, update both bodies in one commit |
| Non-Python repos lack test-affected task | Medium | High | Probe task presence with `mise tasks ls`, fall back to `mise run test` with a plain notice |
| Gate slows pushes on large repos | Low | Low | Keep single-pass sequential checks, no retry loop, L_max 5000ms overhead beyond checks |

## Security Profile
Risk surfaces: subprocess, file paths
Negative tests: failing check blocks push with stderr verbatim, missing mise task errors never silently passes, empty diff exits 0
Constraints: no new dependencies, no hook framework, no change to squash-merge flow or commit convention

## Integration Points
- **mise task catalog**: Gate calls `format-check`, `lint`, `test-affected`/`test` by name; contract is task presence in consumer `mise.toml`
- **deviate merge push gate step**: Inline body in `deviate-merge.md` mirrors the hook; `Failure_State: Push_Gate_Failed` contract unchanged

## Constitutional Alignment
- **Architecture**: Meso plan for a Micro TDD slice; no layer skipped, Gate 2 stays removed per constitution 0.11.0
- **Testing**: pytest via `mise run test`, updated `TestMergePromptPushGate` pins plus hook shell coverage where present
- **Git Isolation**: Work happens on the issue worktree branch only, commits at phase boundaries
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `US-039-01` via `AO-039-01`, `AC-PLAN-003` and `AC-PLAN-004` via `AO-039-02`; RED turns them into failing tests
