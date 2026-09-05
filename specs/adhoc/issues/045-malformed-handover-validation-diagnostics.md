---
title: "Malformed phase handovers fail with specific diagnostics and one correction retry"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-045
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/045-malformed-handover-validation-diagnostics.md`
- **Primary Architectural Workstation**: `src/deviate/core/agent.py`, `src/deviate/cli/micro.py`, `tests/unit/test_micro/`

## The Problem Contract
Micro phase agents emit malformed or contradictory handover manifests and the runner raises opaque `PhaseFailedError` failures (`unknown`, `agent returned no manifest`). This issue adds consistency validation, one correction retry, and diagnostic-preserving failures.

## Scope Boundaries
### Hard Inclusions
- Validate phase, task id, status, verdict, and next action as one consistent result in the handover path (`parse_output` in `src/deviate/core/agent.py` plus phase runners in `src/deviate/cli/micro.py`)
- Reject a mismatched task id with an explicit error naming expected versus received ids
- Retry once with a constrained format-correction prompt on unparseable manifests
- Preserve available rationale or output tail in the failure; emit a specific `HANDOVER_INVALID`-style event instead of `unknown`

### Defensive Exclusions
- No change to RED/GREEN/JUDGE prompt content beyond the correction-retry suffix
- No change to agent backends, RPC transport, timeout, or retry budgets
- No change to JUDGE verdict routing semantics; contradictory PASS plus violation verdicts are rejected, not rerouted

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-045`
- **Acceptance Criteria Tokens**: `AC-ADHOC-045-01`, `AC-ADHOC-045-02`
- **Data Model Entities**: HandoverManifest (phase, status, task_id, verdict, next_action, rationale)

## User Stories Ledger
- **US-045-01**: As a developer watching a micro run, I want a malformed handover to name the exact inconsistency so I fix the prompt or task instead of decoding `unknown`. *(Ref: FR-ADHOC-045)*
- **US-045-02**: As an operator, I want one format-correction retry to recover a malformed manifest so a single bad emission does not kill the task. *(Ref: FR-ADHOC-045)*

## Acceptance Outline
- **AO-045-01** *(Ref: AC-ADHOC-045-01, US-045-01)*: Manifest with a mismatched task id, contradictory verdict/next_action, or ERROR status without rationale fails with a specific error naming the defect
  - **Happy Path**: Valid consistent manifest flows through the phase unchanged
  - **Error Category**: Mismatched task id is rejected explicitly; contradictory PASS plus `COMPLIANCE_VIOLATION` plus `revert_red` fails with the contradiction named; ERROR without rationale carries the preserved output tail
  - **Boundary Category**: Missing manifest preserves the useful `test_defect` diagnosis from plain output instead of discarding it
- **AO-045-02** *(Ref: AC-ADHOC-045-02, US-045-02)*: Unparseable manifest triggers exactly one constrained format-correction retry before failing
  - **Happy Path**: Retry recovers a valid manifest and the phase continues
  - **Error Category**: Failed retry raises the specific correction failure, never bare `unknown`
  - **Boundary Category**: Exactly one retry; no retry loop

## Edge Cases and Boundaries
- RED emitting `task_id: AC-PLAN-001` for active task `TSK-001-01` is rejected with expected versus received ids
- GREEN prose claiming success with `status: ERROR` and no rationale fails with the output tail attached
- JUDGE `status: PASS` with `verdict: COMPLIANCE_VIOLATION` and `next_action: revert_red` is a contradiction, not a pass
- Remote source: gh issue 199 (malformed phase handovers, TSK-001-01, deviate 2.27.1); sibling gh 206 covers the RPC no-`agent_end` transport gap and stays out of scope

## Performance Constraints
- L_max: 200ms per added validation gate excluding the single correction-retry agent call
- Throughput: full test suite under 30s (mock agent invoke and `_run_pytest` subprocess in new tests per AGENTS.md)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_handover_validation.py` — task-id mismatch rejected; contradictory verdict rejected; ERROR-without-rationale carries tail; one correction retry then specific failure; missing manifest preserves plain-output rationale
- **Integration Sandbox Targets**: Micro run on a fixture task with an injected malformed handover exits with the specific `HANDOVER_INVALID`-style message and never `unknown`

## Demonstration Path
```bash
mise run test -- tests/unit/test_micro/test_handover_validation.py
```
