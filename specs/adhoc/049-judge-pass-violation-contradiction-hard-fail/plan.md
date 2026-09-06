## Plan Summary
- **Issue**: ISS-ADH-049 — Fix JUDGE PASS plus COMPLIANCE_VIOLATION contradiction that hard-fails the micro run
- **Implementation Strategy**: Coerce the known PASS plus COMPLIANCE_VIOLATION plus revert_red mix into the normal revert_red path in `_invoke_agent`, and fix the JUDGE prompt schema example so violation pairs with a non-PASS status.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Route contradicting JUDGE handover back to RED**
- **Source Outline**: `AO-049-01`
- **Upstream Traceability**: `US-049-01`, `FR-ADHOC-049`, `AC-ADHOC-049-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: A JUDGE manifest carries status PASS plus verdict COMPLIANCE_VIOLATION plus next_action revert_red
- **When**: The runner validates the handover in `_invoke_agent`
- **Then**: The runner logs JUDGE_REJECTED, preserves violation rationale as train_feedback, and re-runs RED without raising PhaseFailedError
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Reject genuinely malformed handovers with HANDOVER_INVALID**
- **Source Outline**: `AO-049-01`
- **Upstream Traceability**: `US-049-01`, `FR-ADHOC-049`, `AC-ADHOC-049-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: A JUDGE manifest carries a malformed mix outside the known PASS plus COMPLIANCE_VIOLATION plus revert_red mix
- **When**: The runner validates the handover in `_invoke_agent`
- **Then**: The runner logs HANDOVER_INVALID and raises PhaseFailedError
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Route repeat contradictions to RED without exiting**
- **Source Outline**: `AO-049-01`
- **Upstream Traceability**: `US-049-01`, `FR-ADHOC-049`, `AC-ADHOC-049-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_apply_judge_verdict`
- **Given**: Consecutive runs emit the known contradicting JUDGE mix
- **When**: Each handover reaches validation and verdict application
- **Then**: Each routes to the revert_red path and the run continues without exit 1
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Pair JUDGE schema verdicts with matching statuses**
- **Source Outline**: `AO-049-02`
- **Upstream Traceability**: `US-049-01`, `FR-ADHOC-049`, `AC-ADHOC-049-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:186`
- **Given**: The JUDGE prompt schema block shows a verdict example
- **When**: The author reads the violation and pass examples
- **Then**: The violation example shows a non-PASS status with COMPLIANCE_VIOLATION plus revert_red, the pass example shows COMPLIANT plus a forward action, and the unit suite plus check stay green
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Coerce the known contradiction into the revert_red route instead of raising HANDOVER_INVALID
  - **Current State**: `_invoke_agent` builds HANDOVER_INVALID contradiction and raises PhaseFailedError for the mix
  - **Changes Required**: Return the manifest with JUDGE_REJECTED log and violation rationale in train_feedback so `_run_judge_phase` and `_apply_judge_verdict` take the revert_red path
  - **Integration Surface**: `_run_judge_phase`, `_apply_judge_verdict`, `_coerce_judge_action`, session train_feedback
- **src/deviate/prompts/auto/judge.md**: Fix schema example pairing
  - **Current State**: Schema block at line 186 pins status PASS while verdict admits COMPLIANCE_VIOLATION with revert_red
  - **Changes Required**: Show violation example with non-PASS status; keep pass example COMPLIANT with forward action
  - **Integration Surface**: JUDGE agent handover manifest shape consumed by `_invoke_agent` validation
- **tests/unit/test_micro/test_handover_validation.py**: Pin the coercion and the still-invalid boundary
  - **Current State**: One test asserts the known mix raises contradiction PhaseFailedError
  - **Changes Required**: Update that test to assert coercion to revert_red route; add one still-invalid mix test
  - **Integration Surface**: `_invoke_agent` handover validation boundary

## Implementation Strategy
- **Phase 1**: Coerce known contradiction and fix prompt schema
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/judge.md`, `tests/unit/test_micro/test_handover_validation.py`
  - **Approach**: Replace the raise branch for the exact PASS plus COMPLIANCE_VIOLATION plus revert_red mix with a JUDGE_REJECTED log plus manifest return carrying train_feedback; change the judge.md violation example status to a non-PASS value; update plus add unit tests at the validation boundary
  - **Verification**: Targeted pytest on handover validation tests, then full `mise run test` and `mise run check`

## Data Flow Analysis
- JUDGE agent emits handover manifest (status, verdict, next_action, rationale or train_feedback). `_invoke_agent` validates it. The known contradicting mix now logs JUDGE_REJECTED and returns the manifest instead of raising. `_run_judge_phase` plus `_apply_judge_verdict` read next_action revert_red, store feedback in session train_feedback, reset to RED, and the loop re-runs RED. Genuinely malformed mixes keep the HANDOVER_INVALID plus PhaseFailedError path.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Coercion widens to mixes outside the known triple | Medium | Low | Match the exact three-field mix only; keep strict rejection otherwise |
| Violation rationale lost on coercion | Medium | Low | Copy rationale or train_feedback into train_feedback before return |
| Existing contradiction test contradicts fix | Low | High | Update that test to the new coercion expectation in the same commit |

## Security Profile
Risk surfaces: none (handover routing, prompt text; no auth, secrets, PII, HTTP, deserialization, subprocess, file paths, SQL, eval)
Negative tests: still-invalid mix still raises HANDOVER_INVALID; PASS plus violation outside revert_red keeps strict behavior
Constraints: no new dependencies; change only the exact known-mix branch and the prompt example

## Integration Points
- **`_invoke_agent` handover validation**: known mix returns manifest with JUDGE_REJECTED instead of raising
- **`_apply_judge_verdict` revert_red route**: receives the coerced manifest and resets task to RED with feedback
- **JUDGE prompt schema**: violation example guides the agent to emit consistent status plus verdict pairs

## Constitutional Alignment
- **Architecture**: Micro-layer fix inside RED-GREEN-JUDGE-REFACTOR; no layer skipped; no new HITL bypass; auto-advance meso into micro unchanged
- **Testing**: pytest at `tests/unit/test_micro/test_handover_validation.py`; RED encodes user scenarios as failing tests; GREEN cannot edit tests; suite target stays green
- **Git Isolation**: Work happens on the dedicated issue branch in its worktree; commits at phase boundaries via orchestrator
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-003` encode `US-049-01` run-keeps-moving behavior; `AC-PLAN-004` encodes the schema pairing; RED turns the automated scenarios into failing-then-passing tests
