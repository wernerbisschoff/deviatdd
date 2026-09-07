## Plan Summary
- **Issue**: ISS-ADH-050 — Make JUDGE rejection feedback describe a clean-slate retry
- **Implementation Strategy**: Update the canonical JUDGE prompt to state rollback state before rejection feedback rules. Add prompt contract tests for `revert_green` and `revert_red` clean-slate instructions.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Describe `revert_green` feedback from the retained RED baseline**
- **Source Outline**: `AO-050-01`
- **Upstream Traceability**: `US-050-01`, `FR-ADHOC-050`, `AC-ADHOC-050-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:CRITICAL — train_feedback on a COMPLIANCE_VIOLATION`
- **Given**: JUDGE selects `revert_green` after the runner removes the rejected GREEN commit set and retains RED
- **When**: JUDGE writes `train_feedback` for the next GREEN attempt
- **Then**: The feedback states the required behavior and proof from the retained RED test and restored implementation baseline
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep `revert_green` feedback free from discarded GREEN dependencies**
- **Source Outline**: `AO-050-01`
- **Upstream Traceability**: `US-050-01`, `FR-ADHOC-050`, `AC-ADHOC-050-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:On `next_action: revert_red` or `revert_green``
- **Given**: JUDGE observes paths or behavior in the rejected GREEN diff
- **When**: JUDGE formats `revert_green` instructions
- **Then**: The feedback uses durable behavior, interface, file, and proof requirements without asking GREEN to modify or inspect discarded artifacts
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Describe `revert_red` feedback from the pre-RED baseline**
- **Source Outline**: `AO-050-02`
- **Upstream Traceability**: `US-050-01`, `FR-ADHOC-050`, `AC-ADHOC-050-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:revert_red discards RED+GREEN`
- **Given**: JUDGE selects `revert_red` after the runner removes both rejected RED and GREEN commits
- **When**: JUDGE writes `train_feedback` for the next RED attempt
- **Then**: The feedback states the required test behavior and proof from the pre-RED baseline
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep `revert_red` feedback free from discarded RED and GREEN dependencies**
- **Source Outline**: `AO-050-02`
- **Upstream Traceability**: `US-050-01`, `FR-ADHOC-050`, `AC-ADHOC-050-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:Format Requirements for Rejection train_feedback`
- **Given**: JUDGE has diagnostic facts from rejected RED and GREEN artifacts
- **When**: JUDGE formats `revert_red` instructions
- **Then**: The feedback gives durable replacement-state instructions and keeps discarded artifact references as diagnostic context only
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/prompts/auto/judge.md**: Defines JUDGE rollback semantics and rejection feedback requirements
  - **Current State**: The prompt names which commits rollback removes and requires durable feedback, but it does not fully define the restored baseline for each route
  - **Changes Required**: State that the runner removes the rejected commit set before the next agent; define retained RED plus restored implementation baseline for `revert_green`; define pre-RED baseline for `revert_red`; require durable replacement-state instructions
  - **Integration Surface**: JUDGE verdict `next_action`, `train_feedback`, rollback runner, and next RED/GREEN prompt injection
- **tests/unit/test_micro/test_orchestration.py**: Owns prompt contract coverage for JUDGE orchestration
  - **Current State**: `test_judge_auto_prompt_names_next_action_and_revert_meanings` checks route meanings and feedback framing
  - **Changes Required**: Add focused assertions for clean-slate `revert_green` and `revert_red` instructions and discarded-artifact restrictions
  - **Integration Surface**: `_build_auto_prompt`, packaged `judge.md`, and the JUDGE prompt assembly path

## Implementation Strategy
- **Phase 1**: Define route-specific clean-slate feedback rules
  - **Files**: `src/deviate/prompts/auto/judge.md`
  - **Approach**: Extend the rollback semantics and rejection feedback sections with explicit restored baselines. Keep rollback boundaries, commands, retry budgets, routing, and verdict handling unchanged.
  - **Verification**: Inspect the rendered prompt and run focused orchestration tests.
- **Phase 2**: Verify both rejection routes
  - **Files**: `tests/unit/test_micro/test_orchestration.py`
  - **Approach**: Assert the prompt names retained RED for `revert_green`, pre-RED for `revert_red`, and durable replacement-state instructions for both routes.
  - **Verification**: Run `uv run pytest tests/unit/test_micro/test_orchestration.py -q` and `mise run check`.

## Data Flow Analysis
- JUDGE receives the task card, diff, and current phase context. It selects a verdict and `next_action`. The prompt directs `train_feedback` to describe the state that exists after rollback. The runner removes the rejected commits, persists the feedback, and injects it into the next RED or GREEN prompt. Forward-route feedback keeps the current REFACTOR behavior.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| JUDGE still references discarded paths | High | Medium | Add route-specific prompt assertions for artifact absence and durable requirements |
| Prompt changes alter forward-route behavior | Medium | Low | Limit edits to rejection guidance and assert existing route meanings remain |
| Feedback guidance becomes ambiguous after rollback | High | Low | Name the exact retained or pre-RED baseline in each route |

## Security Profile
Risk surfaces: prompt handling, context construction, output handling
Negative tests: `revert_green` feedback excludes discarded GREEN instructions; `revert_red` feedback excludes discarded RED and GREEN instructions
Constraints: keep prompt assembly bounded; add no subprocess, network call, dependency, or secret; preserve diagnostic context without using discarded artifacts as required state

## Integration Points
- **JUDGE prompt assembly**: `src/deviate/cli/micro.py:_build_auto_prompt` loads the canonical template and injects task context.
- **Rollback transition**: `src/deviate/cli/micro.py:_commit_judge_feedback_and_advance` persists feedback after reset, as stated by the issue source anchor.
- **Retry prompts**: `_run_green_phase` and the RED prompt consume `session.train_feedback` for the next attempt.

## Constitutional Alignment
- **Architecture**: This change stays within the Micro RED → GREEN → JUDGE retry flow required by `specs/constitution.md` §1: “Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).”
- **Testing**: Pytest covers the canonical prompt contract. The checks use the repository test command and preserve the 80% coverage target from §3.
- **Git Isolation**: The runner removes rejected commits before the next agent, matching §1: “Every task loop executes on a clean git branch or worktree.”
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `AO-050-01`; `AC-PLAN-003` and `AC-PLAN-004` encode `AO-050-02`. RED turns these scenarios into failing prompt contract tests before GREEN.
