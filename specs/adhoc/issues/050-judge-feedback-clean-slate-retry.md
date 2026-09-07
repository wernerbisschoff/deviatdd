---
title: "Make JUDGE rejection feedback describe a clean-slate retry"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-050
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/050-judge-feedback-clean-slate-retry.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/auto/judge.md`, `tests/unit/test_micro/test_orchestration.py`

## The Problem Contract
JUDGE sees the rejected RED and GREEN diff when it writes feedback. The retry receives that feedback after rollback removes the rejected commits.

JUDGE must describe the required replacement state. The feedback must avoid instructions that depend on discarded code or tests.

## Scope Boundaries
### Hard Inclusions
- Tell JUDGE that the runner removes the rejected commit set before the next agent runs.
- Require `revert_green` feedback to build from the retained RED test and restored implementation baseline.
- Require `revert_red` feedback to build from the pre-RED baseline because the runner removes both RED and GREEN.
- Require durable behavior, interface, file, and proof instructions that stay valid after rollback.
- Add prompt contract tests for both rejection routes.

### Defensive Exclusions
- Keep rollback boundaries and Git commands unchanged.
- Keep retry budgets, session continuity, model routing, and verdict coercion unchanged.
- Keep JUDGE findings and operator summaries unchanged.
- Keep REFACTOR notes outside rejection feedback.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-050`
- **Acceptance Criteria Tokens**: `AC-ADHOC-050-01`, `AC-ADHOC-050-02`
- **Data Model Entities**: JUDGE handover fields `next_action`, `train_feedback`, `summary`

## User Stories Ledger
- **US-050-01**: As a retry agent, I want JUDGE feedback to describe the required result from the restored baseline so that I avoid rebuilding the rejected state. *(Ref: FR-ADHOC-050)*

## Acceptance Outline
- **AO-050-01** *(Ref: AC-ADHOC-050-01, US-050-01)*: A `revert_green` rejection produces feedback for a new GREEN implementation against the retained RED test.
  - **Happy Path**: The feedback names the required behavior and proof from the restored implementation baseline.
  - **Error Category**: The feedback never asks GREEN to modify, preserve, or inspect a discarded GREEN artifact.
  - **Boundary Category**: The retained RED test remains the only rejected-attempt artifact that feedback can reference as present.
- **AO-050-02** *(Ref: AC-ADHOC-050-02, US-050-01)*: A `revert_red` rejection produces feedback for a new RED test against the pre-RED baseline.
  - **Happy Path**: The feedback names the required test behavior and proof without relying on the rejected test or implementation.
  - **Error Category**: The feedback never asks RED to fix, edit, preserve, or inspect discarded RED or GREEN artifacts.
  - **Boundary Category**: Diagnostic facts can explain the defect, but all instructions describe work from the restored baseline.

## Edge Cases and Boundaries
- JUDGE can name paths and interfaces that must exist in the replacement state.
- JUDGE can describe observed behavior as diagnostic context after the required action.
- JUDGE must avoid discarded `path:line` locations and discarded artifact assumptions.
- Forward-route feedback keeps its current REFACTOR behavior.

## Performance Constraints
- L_max: 200ms per prompt assembly
- Throughput: no new subprocess, network call, or model call

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_orchestration.py::test_judge_auto_prompt_names_next_action_and_revert_meanings` plus focused clean-slate feedback assertions
- **Integration Sandbox Targets**: `deviate micro run` retries one `revert_green` and one `revert_red` verdict with feedback that remains valid after rollback

## Demonstration Path
```bash
uv run pytest tests/unit/test_micro/test_orchestration.py -q
mise run check
```

## Constitution Compliance
This issue implements `specs/constitution.md` §1 **Three-Layer Architecture** and **Git Isolation Principle**.

> “Every task loop executes on a clean git branch or worktree.”

The change preserves `specs/constitution.md` §1 **Session Continuity**.

> “Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases.”

## Source Anchors
`src/deviate/prompts/auto/judge.md` defines the rollback result:

> “`revert_green` discards GREEN and keeps RED — `train_feedback` is the next GREEN's memory.”
>
> “`revert_red` discards RED+GREEN — `train_feedback` is the next RED's memory.”

`src/deviate/prompts/auto/judge.md` already requires durable feedback:

> “Write a durable rewrite contract (behavior + required proof).”
>
> “The runner also strips leftover `file:line` tokens on these routes.”

`src/deviate/cli/micro.py::_commit_judge_feedback_and_advance` confirms operation order:

> “Writes `tasks.jsonl` (`judge_action` / `judge_feedback`) and `tasks.md` only after the caller has already reset to the blast-radius SHA.”

`src/deviate/cli/micro.py::_run_green_phase` confirms current GREEN rollback context:

> “Treat this as a clean-slate GREEN attempt: verify every referenced artifact exists on disk and recreate anything missing before reporting success.”
