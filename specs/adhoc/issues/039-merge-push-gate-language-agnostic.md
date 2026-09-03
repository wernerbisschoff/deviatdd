---
title: "Make deviate-merge push gate language-agnostic via repo mise tasks"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-039
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/039-merge-push-gate-language-agnostic.md`
- **Primary Architectural Workstation**: `.githooks/pre-push`, `src/deviate/prompts/commands/deviate-merge.md`, `tests/unit/test_meso/test_auto_prompt_templates.py`

## The Problem Contract
The merge push gate filters on Python files and runs ruff plus testmon. It passes vacuously on repos with zero Python files. The gate must run repo checks on every push.

## Scope Boundaries
### Hard Inclusions
- Rewrite `.githooks/pre-push` to run repo `mise` tasks (format-check, lint, test or equivalent) without a Python file filter
- Update the inlined push gate body in `deviate-merge.md` to match the hook byte for byte
- Update `TestMergePromptPushGate` pins to the new body

### Defensive Exclusions
- No new hook framework or per-language plugin system
- No change to squash-merge flow, Gate 3 audit, or commit convention
- No change to `mise run test` as canonical full-suite command

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-039`
- **Acceptance Criteria Tokens**: `AC-ADHOC-039-01`, `AC-ADHOC-039-02`
- **Data Model Entities**: PushGateCheck
- **Remote Source**: `https://github.com/wernerbisschoff/deviatdd/issues/204` (gh issue 204, reported against 2.27.2, Elixir Phoenix repo MeepleInn)

## User Stories Ledger
- **US-039-01**: As a developer on a non-Python repo, I want the merge push gate to run my repo checks so a merge never reports a vacuous pass. *(Ref: FR-ADHOC-039)*

## Acceptance Outline
- **AO-039-01** *(Ref: AC-ADHOC-039-01, US-039-01)*: Push with zero Python changes runs repo checks and blocks on failure
  - **Happy Path**: Non-Python repo push runs format-check, lint, test tasks and passes when clean
  - **Error Category**: Failing check halts with `Failure_State: Push_Gate_Failed` plus tool stderr verbatim
  - **Boundary Category**: Freshly squashed branch with no upstream resolves base via `HEAD~1`
- **AO-039-02** *(Ref: AC-ADHOC-039-02, US-039-01)*: Python repos keep equivalent protection
  - **Happy Path**: Python repo push still runs lint, format check, affected or full tests
  - **Error Category**: Ruff or test failure blocks the push
  - **Boundary Category**: Missing `.testmondata` falls back to full suite, never silent pass

## Edge Cases and Boundaries
- Repo without the expected `mise` tasks errors with a plain message, never a silent pass
- Empty diff (no upstream, no parent) exits 0 unchanged
- Hook and prompt copies stay byte-equivalent; test pin updated in the same commit

## Performance Constraints
- L_max: 5000ms gate overhead beyond the checks themselves
- Throughput: single push evaluation, no retry loop

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_meso/test_auto_prompt_templates.py::TestMergePromptPushGate` (updated pin); hook shell tests if present
- **Integration Sandbox Targets**: `deviate merge` on a fixture repo with non-Python changes; `git push` hook path on same fixture

## Demonstration Path
```bash
mise run check
```
