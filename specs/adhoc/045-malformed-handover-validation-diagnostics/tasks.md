# Implementation Tasks: `feat/adhoc/045-malformed-handover-validation-diagnostics`

## Phase 1: Consistency validation in the handover path
**Goal**: Malformed manifests fail with specific named defects; valid manifests pass through unchanged.

### Tasks

- TSK-045-01: Reject manifest with mismatched task id, pass valid manifest unchanged
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_handover_validation.py`
    - `src/deviate/core/agent.py`
  - **Rationale**: `US-045-01` plus `AC-PLAN-001` and `AC-PLAN-005` both live in the handover parse path. `src/deviate/core/agent.py:parse_output` is the workstation that owns manifest consistency. The new test file encodes the fail-to-pass contract for mismatch rejection and valid passthrough.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_handover_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert `parse_output` raises a `HANDOVER_INVALID`-style error naming expected versus received ids when the manifest task id differs from the active task, and returns the manifest unchanged when phase, task id, status, verdict, and next action are consistent. Mock the agent invoke boundary; mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture where the CLI path is touched.
    - **Green**: Implement the task-id consistency check in `parse_output` (`src/deviate/core/agent.py`) with `MalformedHandoverManifestError` carrying expected versus received ids; leave consistent manifests untouched. GREEN cannot edit tests.
    - **Refactor**: Align error naming and message shape with existing `parse_errors` conventions; keep checks to string compares.
    - **Edge Cases**: Handle missing task-id field by treating it as a mismatch with a specific defect name; allow unknown extra fields so legacy valid manifests still pass.
    - **Acceptance**: `mise unit` passes; mismatched ids fail with expected-versus-received naming; valid manifests flow unchanged.

- TSK-045-02: Reject PASS-with-violation contradiction and preserve diagnostics on failure
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_handover_validation.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `US-045-01` plus `AC-PLAN-002`, `AC-PLAN-003`, and `AC-PLAN-004` all concern how the phase runner records handover failures. `src/deviate/cli/micro.py:_invoke_agent` is the workstation that owns failure surfacing. The existing test file from `TSK-045-01` gains the new failing assertions; no new verification file is needed.
  - **Details**:
    - **Red**: Extend `tests/unit/test_micro/test_handover_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert a JUDGE manifest with `status: PASS` plus `verdict: COMPLIANCE_VIOLATION` and `next_action: revert_red` is rejected as a contradiction and never treated as a pass; an `ERROR` manifest with empty rationale records the failure with the preserved output tail and a `HANDOVER_INVALID`-style event instead of `unknown`; output with no parseable manifest but a plain `test_defect` diagnosis preserves that diagnosis. Add preservation assertions that existing verdict routing for consistent manifests is unchanged. Mock the agent invoke boundary and `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture.
    - **Green**: Implement contradiction rejection plus tail-carrying failure recording in `_invoke_agent` (`src/deviate/cli/micro.py`); preserve plain-output `test_defect` diagnoses when the manifest is missing. GREEN cannot edit tests.
    - **Refactor**: Keep the 50-line tail buffer as the single diagnostic source; reuse existing failure-event shapes.
    - **Edge Cases**: Handle `ERROR` with empty rationale and empty output by emitting the specific defect name with an empty-tail marker, never bare `unknown`; reject hostile YAML keys as inert data.
    - **Acceptance**: `mise unit` passes; contradictions never pass; failures carry tail plus specific event names; plain-output diagnoses survive.
  - **Dependency**: TSK-045-01

## Phase 2: One constrained format-correction retry
**Goal**: A single unparseable manifest gets exactly one format-only retry, then a specific failure.

### Tasks

- TSK-045-03: Recover through exactly one format-correction retry, fail specifically when it misses
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_micro/test_handover_validation.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `US-045-02` plus `AC-PLAN-006` and `AC-PLAN-007` define the single-retry behavior. `src/deviate/cli/micro.py:_invoke_agent` is the workstation that owns the correction-retry call. The existing test file from `TSK-045-01` gains the retry assertions.
  - **Details**:
    - **Red**: Extend `tests/unit/test_micro/test_handover_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert an unparseable first-attempt manifest triggers exactly one backend call with a format-only correction suffix and a valid retry manifest continues the phase; assert a retry that returns no valid manifest raises the specific correction failure and never emits bare `unknown`. Assert the backend invoke count equals 2 in the recovery case and that no third call occurs. Mock the agent invoke boundary and `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture.
    - **Green**: Implement the single format-correction retry in `_invoke_agent` (`src/deviate/cli/micro.py`): cap at one retry call with a format-only prompt suffix; re-run the same consistency check once; raise the specific correction failure on second miss. GREEN cannot edit tests.
    - **Refactor**: Keep the retry suffix format-only with no verdict-content changes; isolate retry counting to the invoke path.
    - **Edge Cases**: Handle retry output that is parseable but inconsistent by raising the specific failure, not a third retry; handle oversized output by truncating to the tail bound before the retry.
    - **Acceptance**: `mise unit` passes; recovery uses exactly one retry call; failed correction raises the specific error with no bare `unknown`.
  - **Dependency**: TSK-045-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (Phase 2 retry reuses the Phase 1 consistency check)

**Critical Dependency Chains**:
- TSK-045-01 must precede TSK-045-02
- TSK-045-02 must precede TSK-045-03

**Risk Hotspots**:
- Over-strict validation rejects legacy valid manifests; mitigated by allowing unknown extra fields and rejecting only named inconsistencies
- Contradiction check reroutes JUDGE semantics; mitigated by rejecting contradictions with no verdict-routing changes

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_micro/test_handover_validation.py`, `src/deviate/cli/micro.py`

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
