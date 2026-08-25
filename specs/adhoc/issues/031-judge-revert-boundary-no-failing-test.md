---
title: "Micro Judge already-exists COMPLIANCE_PASS must not hard-crash with ROLLBACK_BOUNDARY_MISSING"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-031
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/031-judge-revert-boundary-no-failing-test.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`

## The Problem Contract
On the RED `no_failing_test` already-exists path, `deviate micro run` hard-crashes with `ROLLBACK_BOUNDARY_MISSING` and never completes the task. The judge emits `COMPLIANCE_PASS` (behavior already exists at HEAD), but the mechanical evidence gate rewrites that pass to `revert_to_red`, and the revert requires a RED commit that never exists on the already-exists path. Every retry fails identically.

## Scope Boundaries
### Hard Inclusions
- Route a `no_failing_test` already-exists `COMPLIANCE_PASS` through a graceful COMPLETE path instead of `revert_to_red`.
- Keep the task's declared regression-pin test files on disk as the legitimate deliverable.
- Preserve fail-closed behavior for missing regression files and for real `COMPLIANCE_VIOLATION` verdicts.

### Defensive Exclusions
- Do not weaken the mechanical evidence gate for a genuine test-bearing RED with a failing test.
- Do not change the `revert_before` route for `no_failing_test` `COMPLIANCE_VIOLATION` (test-defect re-author).
- Do not fall back to `HEAD~1` or invent a RED boundary where none exists.
- Do not alter `flow_refs` mapping or Product-layer flow artifacts (`specs/_product/`).

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-031`
- **Acceptance Criteria Tokens**: `AC-ADHOC-031-01`, `AC-ADHOC-031-02`
- **Data Model Entities**: `SessionState` fields `failure_kind`, `red_commit_sha`, `pending_judge_action`, `last_judge_verdict`

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-031-01**: As a DeviaTDD operator, I want a judge `COMPLIANCE_PASS` on the already-exists path to complete the task and keep its regression-pin tests, so `deviate micro run` never hard-crashes with `ROLLBACK_BOUNDARY_MISSING`. *(Ref: FR-ADHOC-031)*
- **US-031-02**: As a DeviaTDD operator, I want a real `no_failing_test` violation (wrong test) to still route to `revert_before` for RED re-author, so the fail-closed contract stays intact. *(Ref: FR-ADHOC-031)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-031-01** *(Ref: AC-ADHOC-031-01, US-031-01)*: On `failure_kind == "no_failing_test"` with judge verdict `COMPLIANCE_PASS` (`next_action` null or `skip_refactor`), the runner completes the task through `_NO_FAILING_TEST_FORWARD_ROUTES` and keeps declared regression-pin test files on disk.
  - **Happy Path**: `deviate micro run` on `TSK-029-02`-style already-exists work completes the task; `pending_judge_action` is `skip_refactor`; the regression-pin tests remain present.
  - **Error Category**: A missing regression `test_file` / `files` still fails closed via `_require_tdd_declared_regression_files`; no task completes with an empty test deliverable.
  - **Boundary Category**: A genuine test-bearing RED with a failing test still routes to `revert_to_red` as today.
- **AO-031-02** *(Ref: AC-ADHOC-031-02, US-031-02)*: A `no_failing_test` `COMPLIANCE_VIOLATION` still routes to `revert_before` so RED re-authors the test.
  - **Happy Path**: Wrong or tautological test falls back to `next_action: revert_before` and RED re-authors a failing test.
  - **Error Category**: The runner never raises `ROLLBACK_BOUNDARY_MISSING` on the already-exists pass path; no destruction of regression-pin tests or code.
  - **Boundary Category**: `_require_revert_to_red_boundary` is only reached for a genuine `revert_to_red` with a real RED commit.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- Judge emits `COMPLIANCE_PASS` with `next_action` absent (legacy path): must coerce to `skip_refactor`, matching the existing line in `_adjudicate_red_no_failing_test`.
- Judge emits `COMPLIANCE_PASS` with `next_action: skip_refactor` but evidence omits one plan AC token: must still complete, not `revert_to_red`.
- Declared regression `test_file` names a path with no match in `_declared_regression_paths`: fails closed with the existing missing-regression-files error.
- A mid-plan task with a real failing test and a real RED commit: `revert_to_red` behavior unchanged.
- `_apply_judge_verdict` is shared by `judge post`; the fix must not regress the non-auto path.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- L_max: 500ms added to the existing JUDGE verdict application on the already-exists path.
- Throughput: No change; the fix adds a branch, not a new subprocess on the recovery path.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_micro/test_judge.py` — `test_already_exists_head_quotes_pass`, plus a new test that a `no_failing_test` `COMPLIANCE_PASS` with partial evidence completes instead of raising `ROLLBACK_BOUNDARY_MISSING`.
- **Integration Sandbox Targets**: `tests/test_cli/test_micro.py` — the `_run_pytest`-mocked CLI path that reproduces the `TSK-029-02` crash.

## Demonstration Path
```bash
# Unit-level reproduction harness (pytest path, judge verdict application).
# Regression target input:
#   session.failure_kind == "no_failing_test"
#   session.red_commit_sha == ""
#   judge verdict == COMPLIANCE_PASS (next_action null or skip_refactor)
deviate micro run --task TSK-029-02
# Expected after fix: task COMPLETES via skip_refactor;
# no ROLLBACK_BOUNDARY_MISSING traceback in .deviate/logs/*.log
```
