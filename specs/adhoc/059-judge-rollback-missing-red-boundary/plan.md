## Plan Summary
- **Issue**: ISS-ADH-059 — Preserve rollback evidence when the RED boundary is missing
- **Implementation Strategy**: Make the TDD `revert_green` missing-boundary path preserve rollback evidence and fail as `DEVIATDD_BUG`. Keep the branch unchanged, avoid inferred boundaries, and recommend `/deviate-green` after reporting `head_sha` and `recovery_ref`.

## Acceptance Contract
**Scenario AC-PLAN-001: Report a distinct harness failure with available rollback evidence**
- **Source Outline**: `AO-059-01`
- **Upstream Traceability**: `US-059-01`, `FR-ADHOC-059`, `AC-ADHOC-059-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase` and `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: JUDGE selects TDD `revert_green` while `session.red_commit_sha` is empty and rollback evidence includes `head_sha` or `recovery_ref`
- **When**: The runner validates the rollback boundary
- **Then**: The runner reports `DEVIATDD_BUG` with explicit `head_sha` and `recovery_ref` fields, preserves both values, and leaves the branch unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Keep empty rollback evidence explicit and reject inferred boundaries**
- **Source Outline**: `AO-059-01`, `AO-059-02`
- **Upstream Traceability**: `US-059-01`, `FR-ADHOC-059`, `AC-ADHOC-059-01`, `AC-ADHOC-059-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_green_boundary`; `src/deviate/state/ledger.py:TaskRecord.head_sha`
- **Given**: JUDGE selects TDD `revert_green` while `session.red_commit_sha`, `head_sha`, and `recovery_ref` are empty
- **When**: The runner handles the missing rollback boundary
- **Then**: The runner emits `DEVIATDD_BUG` with empty evidence fields, does not use `HEAD~1`, does not retry silently, and recommends `/deviate-green`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Preserve the safe operator recovery route after boundary failure**
- **Source Outline**: `AO-059-02`
- **Upstream Traceability**: `US-059-01`, `FR-ADHOC-059`, `AC-ADHOC-059-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_is_fatal_missing_revert_green_boundary`; `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: TDD `revert_green` raises `ROLLBACK_BOUNDARY_MISSING` before any reset
- **When**: The JUDGE error handler classifies the failure
- **Then**: The handler records a harness failure, skips `_commit_judge_feedback_and_advance`, performs no retry, and recommends `/deviate-green`
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Extend the TDD `revert_green` boundary-failure handling to retain rollback evidence and classify `DEVIATDD_BUG`; use `_require_revert_green_boundary`, `_execute_rollback`, `_is_fatal_missing_revert_green_boundary`, and `_run_judge_phase` evidence: `src/deviate/cli/micro.py:2775` contains `ROLLBACK_BOUNDARY_MISSING`; Integrates: `TaskRecord` rollback fields and JUDGE verdict handling.
- **src/deviate/state/ledger.py**: Reuse `TaskRecord.head_sha` and `TaskRecord.recovery_ref` as nullable rollback evidence; evidence: `src/deviate/state/ledger.py:head_sha: str | None = None`; Integrates: task ledger serialization.
- **tests/unit/test_micro/test_rollback_safety.py**: Add unit coverage for missing-boundary evidence preservation, empty evidence, and rejection of implicit Git fallback; evidence: `tests/unit/test_micro/test_rollback_safety.py:TestExecuteRollbackBoundaryContract`.
- **tests/unit/test_micro/test_run.py**: Add integration coverage for `deviate micro run` reporting `DEVIATDD_BUG`, preserving evidence, and recommending `/deviate-green`; evidence: `tests/unit/test_micro/test_run.py:TestSessionResume`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Error handling overwrites or drops available rollback evidence | High | Medium | Capture `head_sha` and `recovery_ref` before classification and assert both in unit and integration tests |
| Missing-boundary handling resumes training after an unsafe failure | High | Medium | Keep `ROLLBACK_BOUNDARY_MISSING` fatal, skip feedback commit, and assert no retry |
| A fallback resets to an inferred Git boundary | High | Low | Reject empty boundaries before reset and assert no `HEAD~1` command or HEAD change |
| Existing valid `revert_green` behavior changes | Medium | Low | Limit changes to the missing-boundary branch and run focused rollback and run tests |

## Security Profile
Risk surfaces: subprocess (git reset and git clean), rollback evidence, session JSON, task ledger
Negative tests: missing boundary keeps HEAD unchanged; empty evidence stays explicit; no `HEAD~1`; no silent retry; no feedback commit
Constraints: no new dependencies; no hardcoded secrets; preserve append-only ledgers; keep evidence paths relative; do not alter valid rollback or model routing

## Constitutional Alignment
- **Constitution**: §1 Micro-Layer Scope, §1 Git Isolation Principle, §1 User Scenarios Are the Flow, §3 Testing Protocols, §5 Definition of Done
