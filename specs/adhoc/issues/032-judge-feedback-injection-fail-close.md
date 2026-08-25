---
title: "Judge prompt must inject the Judge-Feedback-stripped task card so prior feedback cannot mislead the judge into a COMPLETED evidence fail-close loop"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: ["ISS-ADH-020", "ISS-ADH-028"]
issue_id: ISS-ADH-032
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/032-judge-feedback-injection-fail-close.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/core/judge_evidence.py`

## The Problem Contract
`deviate micro run` on a TDD task repeatedly fail-closes at the COMPLETED evidence gate with `COMPLETED_EVIDENCE_MISSING` for owned AC tokens, even when the judge emits `COMPLIANCE_PASS` and GREEN folded the requested change. The harness injects runner-appended Judge-Feedback prose into the JUDGE prompt via the raw task card; a prior round's prose can assert a false ownership claim that a later judge trusts, causing it to omit evidence for a token it owns. This is the prompt-injection mirror of issue #89 (which fixed only token resolution, never the injection path).

## Scope Boundaries
### Hard Inclusions
- Inject the Judge-Feedback-stripped task card (`_strip_judge_feedback`) when building the JUDGE prompt, so a prior round's feedback can neither assert false ownership nor bias the current judge.
- Reuse the same stripped card the token-resolution path (`resolve_task_ac_tokens`) already uses, so resolution and injection read the same source.
- Preserve the fail-closed `COMPLETED_EVIDENCE_MISSING` gate for genuinely missing evidence.

### Defensive Exclusions
- Do not weaken the mechanical evidence gate or the judge's own evidence requirements.
- Do not change `_append_judge_feedback`'s bounded, deduplicated feedback retention in `tasks.md`.
- Do not alter `flow_refs` mapping or Product-layer flow artifacts (`specs/_product/`).
- Do not change model tiering or phase routing.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-032`
- **Acceptance Criteria Tokens**: `AC-ADHOC-032-01`, `AC-ADHOC-032-02`
- **Data Model Entities**: task card text in `tasks.md`; Judge-Feedback bullets under a task card

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-032-01**: As a DeviaTDD operator, I want the JUDGE prompt to receive the Judge-Feedback-stripped task card so a prior retry's prose cannot mislead the judge into omitting evidence for an owned token. *(Ref: FR-ADHOC-032)*
- **US-032-02**: As a DeviaTDD operator, I want a genuine evidence gap to still fail closed at `COMPLETED_EVIDENCE_MISSING`, so the fail-closed contract stays intact. *(Ref: FR-ADHOC-032)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-032-01** *(Ref: AC-ADHOC-032-01, US-032-01)*: For phase == `judge`, the `<task_card source="tasks.md">` injected into the prompt contains no `**Judge Feedback**` bullet lines and no continuation lines from prior rounds; it matches the stripped card used by `resolve_task_ac_tokens`.
  - **Happy Path**: `deviate micro run` completes a task whose judge cites evidence for all owned AC tokens; no spurious false-ownership prose reaches the judge.
  - **Error Category**: A genuine missing-evidence case still fails closed with `COMPLETED_EVIDENCE_MISSING` naming the omitted tokens.
  - **Boundary Category**: A task card that never had Judge-Feedback bullets is injected unchanged (stripping is a no-op).
- **AO-032-02** *(Ref: AC-ADHOC-032-02, US-032-02)*: A task retried after a prior failed COMPLETED gate does not carry prior feedback prose into the next JUDGE prompt.
  - **Happy Path**: After a fail-close, the next retry's judge sees only the task's real ownership tokens, not earlier "belongs to a later task" claims.
  - **Error Category**: No injected card ever re-asserts a token ownership claim that contradicts the task card's own Rationale.
  - **Boundary Category**: Multi-line Judge-Feedback bullets and their continuation lines are fully removed, not partially stripped.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- A task card with duplicate Judge-Feedback bullets above the Phase heading must be fully stripped before injection.
- A card whose only content is Judge-Feedback must not be injected with stale prose; stripping yields the token-bearing rationale or an empty non-misleading card.
- The fix must not regress the already-exists `COMPLIANCE_PASS` skip-refactor path (ISS-ADH-031) or the task-scoped judge evidence gate (ISS-ADH-028).
- `_task_card_text` is shared by RED/JUDGE/COMPLETED paths (call sites at lines 5948, 6366, 3078); stripping must apply to the JUDGE injection path without altering the other callers' raw card use unless intended.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- L_max: 500ms added to JUDGE prompt construction (a single regex-strip pass over the card).
- Throughput: No change; stripping is in-process string work, no new subprocess.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_core/test_judge_evidence.py` — extend `TestResolveTaskAcTokens` to assert the stripped card; `tests/test_micro/test_judge.py` — a new test that the JUDGE prompt injection uses the Judge-Feedback-stripped card.
- **Integration Sandbox Targets**: `tests/test_cli/test_micro.py` — a `_run_pytest`-mocked path that reproduces a `TSK-029-01`-style fail-close loop and asserts the retry's judge sees no stale feedback.

## Demonstration Path
```bash
# Unit-level reproduction: build a task card with a "**Judge Feedback**" bullet
# asserting "AC-PLAN-003 belongs to a later task", then build the judge prompt.
# Expected after fix: the injected <task_card> omits the bullet and its continuation.
deviate micro run --task TSK-029-01
# Expected after fix: judge cites evidence for all owned tokens; no COMPLETED_EVIDENCE_MISSING
# loop in .deviate/logs/*.log.
```
