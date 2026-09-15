## Plan Summary
- **Issue**: 010-002 — Make JUDGE evaluate current diff and stop contradiction loops
- **Implementation Strategy**: Keep JUDGE evaluation anchored to the active task contract and the injected RED-to-HEAD diff. Preserve existing contradiction detection and make repeated incompatible requirements produce one stable terminal outcome.

## Acceptance Contract

**Scenario AC-PLAN-001: Judge the active contract against the current GREEN diff**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-010-02`, `FR-004-JUDGE`, `AC-010-002-04`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_assemble_judge_injected_diff`
- **Given**: The active task contract requires changed behavior and the current GREEN diff contains the implementation and RED test changes
- **When**: JUDGE evaluates the task
- **Then**: JUDGE returns a pass or actionable retry verdict from the active contract and current diff without rejecting absent behavior that the contract does not require preserving
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Preserve required behavior only when the active contract requires it**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-010-02`, `FR-004-JUDGE`, `AC-010-002-04`
- **Current-Code Evidence**: `src/deviate/cli/micro/surface.py:_rewrite_unmatched_tdd_pass`
- **Given**: The active task contract explicitly requires preservation of existing behavior
- **When**: JUDGE evaluates the current GREEN diff
- **Then**: JUDGE rejects the task only when the required preservation behavior is absent or contradicted
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Return a stable result after incompatible JUDGE interpretations recur**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-010-02`, `FR-005-CONTRADICTION`, `AC-010-002-05`
- **Current-Code Evidence**: `src/deviate/core/judge_contradiction.py:detect_judge_requirement_contradiction`
- **Given**: JUDGE feedback contains repeated incompatible interpretations for the same task
- **When**: The runner evaluates the next JUDGE feedback
- **Then**: The runner returns `JUDGE_REQUIREMENT_CONTRADICTION` and stops selecting another retry interpretation
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro/surface.py**: Build the current RED-to-HEAD and dirty working-tree diff, inject the active task contract, and apply current-diff JUDGE verdicts: `_assemble_judge_injected_diff`, `_run_judge_phase`, `_apply_judge_verdict` + Integrates: `src/deviate/core/judge_contradiction.py`, `SessionState`
- **src/deviate/core/judge_contradiction.py**: Detect explicit incompatible requirements and A→B→A oscillation without treating compatible refinements as contradictions: `detect_judge_requirement_contradiction` + Integrates: `src/deviate/cli/micro/surface.py`
- **src/deviate/prompts/auto/judge.md**: State that JUDGE checks changed behavior against the active contract and current diff: `STEP_1`, `STEP_3` + Integrates: `_build_auto_prompt`
- **tests/unit/test_core/test_judge_contradiction.py**: Verify explicit conflict, ABA oscillation, compatible refinement, and empty-history behavior: `test_aba_oscillation_is_a_contradiction` + Integrates: `src/deviate/core/judge_contradiction.py`
- **tests/unit/test_micro/test_judge.py**: Verify current-diff verdicts, preservation-only rejection, and stable contradiction routing: `_run_judge_phase` tests + Integrates: `src/deviate/cli/micro/surface.py`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| JUDGE evaluates only GREEN implementation and misses RED evidence | High | Medium | Keep the RED-parent-to-HEAD diff assembly and test it with a failing-test boundary |
| Existing behavior becomes an implicit preservation requirement | High | High | Require preservation evidence from the active contract before rejecting absent behavior |
| Compatible feedback is misclassified as contradiction | Medium | Medium | Keep identity and polarity checks plus compatible-refinement regression tests |
| Repeated contradiction feedback continues retry routing | High | Medium | Route the detected contradiction to the stable `JUDGE_REQUIREMENT_CONTRADICTION` halt |

## Security Profile
Risk surfaces: task contract injection, git diff selection, retry routing
Negative tests: absent unrequired behavior passes; required preservation absence rejects; compatible feedback continues; repeated incompatible feedback halts
Constraints: preserve relative paths, use current diff only, add no dependencies, keep append-only task transitions
## Constitutional Alignment
- **Constitution**: §1, §3, §4, §5 — current-contract JUDGE evaluation, automated pytest verification, phase isolation, and mandatory JUDGE compliance
