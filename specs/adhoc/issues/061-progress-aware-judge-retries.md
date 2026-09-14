---
title: "Bound TRAIN retries by progress and return repeated blockers to the operator"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-061
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/061-progress-aware-judge-retries.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro/surface.py`, `src/deviate/state/config.py`, and `src/deviate/prompts/auto/judge.md`. Sources: S1–S4.

## The Problem Contract
Allow five task-wide candidate attempts: one initial attempt and four feedback-guided retries.
Return control when a blocking defect repeats after a corrective attempt without material progress.

This is a proposed operating policy, rather than an empirically established optimum.
The current nested budgets permit repeated work across RED restarts. Sources: S1–S3.

## Scope Boundaries
### Hard Inclusions
- Apply the policy to automatic `TDD` and `EXECUTE` corrective loops. Source: S1, S2, S5.
- Count each started `GREEN` or `EXECUTE` candidate once, including candidates that fail verification. Source: S2; `The Problem Contract`.
- Keep one five-attempt budget across `RED` restarts and session reloads. Source: S3; `The Problem Contract`.
- Stop on the second occurrence of an unchanged blocking defect after feedback reaches the corrective agent. Source: `AO-061-02`.
- Compare criterion or rule, affected behavior or symbol, defect, and current evidence. Source: S4; `AO-061-02`.
- Keep the initial `JUDGE` assessment independent; compare fresh findings against history afterward. Source: S6; `AO-061-05`.
- Persist attempt consumption, finding history, stop reason, and recovery references before another candidate starts. Source: S3; `AO-061-04`.
- Preserve the valid `RED` test when the task exhausts its candidate budget. Route confirmed test defects through existing `revert_red` handling. Source: S7.
- Treat an operator stop as an exceptional execution failure, distinct from the two mandatory approval gates. Source: S8.
- Update `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` with implementation. Source: S9.

### Defensive Exclusions
- Preserve model routing, session continuity, and the two mandatory approval gates. Source: S8.
- Keep manifest-format retries at their existing independent limit. Source: S5.
- Preserve rollback recovery, append-only task history, and existing test-defect escalation limits. Sources: S1, S3, S8.
- Keep advisory `REFACTOR NOTE` feedback on its existing passing route. Source: S7.
- Limit delivery to retry policy and directly required state, findings, and verification support. Source: `The Problem Contract`.
- Keep latency benchmarking, retry dashboards, additional model backends, and generic semantic-search infrastructure outside this issue. Source: `The Problem Contract`.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-060` in `specs/adhoc/prd.md`.
- **Acceptance Criteria Tokens**: `AC-ADHOC-060-01`, `AC-ADHOC-060-02`, `AC-ADHOC-060-03`, `AC-ADHOC-060-04`, `AC-ADHOC-060-05`.
- **Data Model Entities**: `SessionState`, current `JUDGE` violations, and task-scoped finding history. Sources: S3, S4.
- **Related Behavior**: Existing two-counter policy and stale-feedback protection provide compatibility context. Sources: S1, S6.

## User Stories Ledger
- **US-061-01**: As an operator, I want useful corrections to continue through five attempts so that actionable feedback can resolve the task. *(Ref: FR-ADHOC-060)*
- **US-061-02**: As an operator, I want repeated blockers to return control early so that I can resolve stalled corrections. *(Ref: FR-ADHOC-060)*

## Acceptance Outline
- **AO-061-01** *(Ref: AC-ADHOC-060-01, US-061-01)*: Progressive corrections complete within five task-wide candidate attempts.
  - **Happy Path**: A fourth or fifth candidate passes after earlier findings receive verified corrections.
  - **Error Category**: Rejection of the fifth candidate returns control with the attempt count and final feedback.
  - **Boundary Category**: Candidate six requires explicit operator continuation. A `RED` restart retains the consumed budget.
- **AO-061-02** *(Ref: AC-ADHOC-060-02, US-061-02)*: Repeated blocking defects return control after one corrective opportunity.
  - **Happy Path**: A repeated unresolved negative-quantity defect stops execution before candidate three.
  - **Error Category**: The stop report includes the earlier finding, current evidence, corrective attempt, and recovery details.
  - **Boundary Category**: Paraphrases, bullet order, line shifts, and commit hashes preserve defect identity. Distinct defects on one criterion remain distinct.
- **AO-061-03** *(Ref: AC-ADHOC-060-03, US-061-01, US-061-02)*: Evidence distinguishes progress from repeated failure.
  - **Happy Path**: Fixing negative values while zero remains invalid permits another bounded retry for the remaining defect.
  - **Error Category**: A resolved defect that returns after another correction produces an oscillation stop, including the A → B → A history.
  - **Boundary Category**: A new finding alongside an unchanged old blocker still triggers the repeated-blocker stop.
- **AO-061-04** *(Ref: AC-ADHOC-060-04, US-061-02)*: Resume preserves the budget and operator stop.
  - **Happy Path**: Reload continues an active task with its consumed attempts and finding history.
  - **Error Category**: Ordinary rerun and automatic drain retain a stopped task's operator-intervention state.
  - **Boundary Category**: Explicit operator continuation records authorization and its new bounded budget. Historical evidence remains available; a new task starts independently.
- **AO-061-05** *(Ref: AC-ADHOC-060-05, US-061-01)*: Retry policy composes with existing verdict and recovery behavior.
  - **Happy Path**: A passing verdict completes its normal route, including advisory refactor feedback.
  - **Error Category**: Manifest repair uses its own limit and preserves the candidate. Harness failures retain their existing immediate failure route.
  - **Boundary Category**: Budget exhaustion preserves a valid `RED` test. Confirmed test defects retain bounded `RED` escalation. Initial `JUDGE` assessment uses current evidence independently.

## Edge Cases and Boundaries
- `TDD` attempts count at `GREEN` start; `EXECUTE` attempts count at implementation start. Source: S2; `AO-061-01`.
- `RED`-only failures retain the existing escalation cap, including the already-exists adjudication route. Source: S1; `AO-061-05`.
- A crash after attempt reservation retains consumption on reload. Source: `AO-061-04`.
- Legacy sessions receive conservative migration rules during `/plan`; stored counters remain evidence of consumed work. Source: S3; `AO-061-04`.
- Free-form feedback requires a documented fallback for defect identity during `/plan`. Evidence-backed matches authorize early repeated-blocker stops. Source: S4; `AO-061-02`.
- Ambiguous comparisons remain bounded by the five-attempt cap. Source: `AO-061-01`, `AO-061-02`.
- A budget stop preserves the valid `RED` contract; replacement requires a confirmed test defect. Source: S7; `AO-061-05`.

## Performance Constraints
- Keep the full test suite below 30 seconds. Source: `AGENTS.md`: `full test suite < 30s`.
- Mock agent calls and `_run_pytest` in runner tests. Source: `AGENTS.md`: `Tests calling CLI commands that hit this function MUST mock`.
- Bound comparison history by the task's five-attempt budget. Source: `AO-061-01`.
- Establish comparison latency during `/plan` from the selected existing mechanisms; this issue asserts a call-count bound rather than an unsupported millisecond target. Source: `AO-061-01`.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: Extend `tests/unit/test_micro/test_two_counter_retry.py` for fifth-attempt success, repeat stops, oscillation, and total-budget enforcement. Source: `AO-061-01`–`AO-061-03`.
- **State Targets**: Extend `tests/unit/test_state/test_config.py` for reload, legacy state, and explicit continuation. Source: `AO-061-04`.
- **Integration Sandbox Targets**: Extend mocked orchestration in `tests/unit/test_micro/test_orchestration.py` and `tests/unit/test_cli/test_micro.py`. Exercise real retry decisions across stubbed agent responses. Source: `AO-061-01`–`AO-061-05`.
- **Scope Warning**: This vertical slice spans more than five implementation, test, and mandatory documentation files. Keep all changes tied to the retry policy. Source: S9; `AO-061-01`–`AO-061-05`.

## Demonstration Path
Source: `mise.toml`: `description = "Run a single focused test (e.g. mise run test:one -- tests/test_x.py -k name)"`.

```bash
mise run test:one -- tests/unit/test_micro/test_two_counter_retry.py tests/unit/test_state/test_config.py tests/unit/test_micro/test_orchestration.py tests/unit/test_cli/test_micro.py
mise run check
```

## Discovery Audit
The existing explore paths contain no matching progress-aware retry brief.
Exact discovery uses `zg query --rg` after semantic discovery reports `INDEX_MISSING`.
The `adhoc pre` contract returns `status: READY` and `execution_mode: DIRECT`; this emission registers implementation work as `BACKLOG`.

### S1 — Existing nested limits
`src/deviate/cli/micro/surface.py`:
```python
_MAX_GREEN_ATTEMPTS = 3
_MAX_RED_ATTEMPTS = 3
```

### S2 — Candidate consumption
`src/deviate/cli/micro/surface.py`:
```python
    session.green_attempts += 1
```

### S3 — Persisted retry state
`src/deviate/state/config.py`:
```python
    train_feedback: str = ""
    green_attempts: int = 0
    red_attempts: int = 0
```

### S4 — Existing finding representation
`src/deviate/prompts/auto/judge.md`:
```yaml
violations:
  - category: "Spec Non-Compliance"
    file: "path/to/file.ext"
    detail: "Specific description of the violation, citing FR-NN / AC-PLAN-NNN"
    severity: "CRITICAL" | "HIGH" | "MEDIUM"
    recommendation: "How to resolve the violation (specific files, specific changes)"
```

### S5 — Independent JUDGE and EXECUTE limits
`src/deviate/cli/micro/surface.py`:
```python
_MAX_JUDGE_MANIFEST_ATTEMPTS = 3
```
```python
    max_judge_attempts = 3
```

### S6 — Stale-feedback precedent
`specs/adhoc/issues/032-judge-feedback-injection-fail-close.md`:
> the JUDGE prompt to receive the Judge-Feedback-stripped task card

This short phrase is a discovery pointer; `FR-ADHOC-032` in `specs/adhoc/prd.md` owns the existing feedback-isolation requirement.

### S7 — Existing test-integrity routing
`src/deviate/prompts/auto/judge.md`:
> **Test is honest; implementation/scope is wrong** → `next_action: revert_green` (discard GREEN, keep RED).

Source phrase within the route definition; the same section assigns test defects to `revert_red`.

### S8 — Constitutional boundary
`specs/constitution.md`:
> - **Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases. Model switching mid-task is prohibited.

`specs/constitution.md`, `Human-in-the-Loop (HITL)` field:
> Two remaining mandatory gates (Design Approval after research, Final Merge Audit after micro) prevent autonomous drift.

### S9 — Implementation documentation
`AGENTS.md`:
> CLI commands, phase workflows, model routing, file structure, and HITL gates MUST be reflected in both in the same commit as the implementation change.

`specs/constitution.md`, `Definition of Done` field:
> CHANGELOG.md updated under `[Unreleased]` for user-visible changes
