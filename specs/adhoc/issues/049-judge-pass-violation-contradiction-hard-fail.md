---
title: "Fix JUDGE PASS plus COMPLIANCE_VIOLATION contradiction that hard-fails the micro run"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-049
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/049-judge-pass-violation-contradiction-hard-fail.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/judge.md`

## The Problem Contract
The JUDGE agent emits status PASS with verdict COMPLIANCE_VIOLATION and next_action revert_red. Handover validation rejects this mix and the micro run exits 1. The run cannot advance past JUDGE.

## Scope Boundaries
### Hard Inclusions
- Coerce the known PASS plus COMPLIANCE_VIOLATION plus revert_red mix into the normal revert_red rejection route in `src/deviate/cli/micro.py`
- Fix the JUDGE prompt schema in `src/deviate/prompts/auto/judge.md` so the violation example no longer shows `status: "PASS"`
- Cover the coercion with a unit test at the handover validation boundary

### Defensive Exclusions
- No change to RED, GREEN, or REFACTOR agent behavior
- No change to the append-only ledger protocol or phase commit flow
- No new model routing or backend support

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-049`
- **Acceptance Criteria Tokens**: `AC-ADHOC-049-01`, `AC-ADHOC-049-02`
- **Data Model Entities**: Agent handover manifest (status, verdict, next_action)

## User Stories Ledger
- **US-049-01**: As an operator running `deviate micro run`, I want a self-contradicting JUDGE handover to route back to RED so my run keeps moving instead of exiting 1. *(Ref: FR-ADHOC-049)*

## Acceptance Outline
- **AO-049-01** *(Ref: AC-ADHOC-049-01, US-049-01)*: A JUDGE manifest with status PASS plus verdict COMPLIANCE_VIOLATION plus next_action revert_red routes to the revert_red path and the run continues.
  - **Happy Path**: Contradicting handover logs JUDGE_REJECTED and RED re-runs with the violation feedback.
  - **Error Category**: Genuinely malformed handovers outside this known mix still raise HANDOVER_INVALID.
  - **Boundary Category**: Repeat contradictions on consecutive runs keep routing to RED without exiting 1.
- **AO-049-02** *(Ref: AC-ADHOC-049-02, US-049-01)*: The JUDGE prompt schema pairs each verdict with its matching status, and the suite stays green.
  - **Happy Path**: Violation example shows a non-PASS status; pass example shows COMPLIANT plus a forward action.
  - **Error Category**: Full unit suite or `mise run check` fails.
  - **Boundary Category**: Source anchor `src/deviate/cli/micro.py:765` contradiction branch and `src/deviate/prompts/auto/judge.md:186` schema block both change in the same commit.

## Edge Cases and Boundaries
- Other PASS plus violation verdict mixes outside revert_red keep current strict behavior unless the fix explicitly widens the coercion set.
- The coercion must preserve the violation rationale into `train_feedback` so the next RED attempt carries the reason.
- Related closed work on malformed handovers stays intact; this fix only adds the one known-contradiction coercion.

## Performance Constraints
- L_max: 200ms per handover validation path
- Throughput: no new subprocess or network call on the validation path

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` handover validation tests covering the PASS plus COMPLIANCE_VIOLATION plus revert_red mix and one still-invalid mix
- **Integration Sandbox Targets**: `deviate micro run` on the failing task reaches RED re-run instead of PhaseFailedError

## Demonstration Path
```bash
mise run test
mise run check
```

## Source Anchors
- `src/deviate/cli/micro.py:765`: `status_norm == "PASS"` plus `verdict_str == "COMPLIANCE_VIOLATION"` plus `next_action_str == "revert_red"` builds `HANDOVER_INVALID contradiction` and raises `PhaseFailedError`.
- `src/deviate/prompts/auto/judge.md:186`: schema example pins `status: "PASS"` while the verdict enum admits `COMPLIANCE_VIOLATION` with `next_action: revert_red`.
- GH #209 log: `AGENT_RESULT phase JUDGE status PASS verdict COMPLIANCE_VIOLATION next_action revert_red` → `HANDOVER_INVALID contradiction` → `PhaseFailedError` at `micro.py:784 _invoke_agent`.
