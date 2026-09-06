# Implementation Tasks: `feat/adhoc/049-judge-pass-violation-contradiction-hard-fail`

## Phase 1: Coerce contradiction and fix prompt schema
**Goal**: Contradicting JUDGE handovers route back to RED; schema examples pair verdicts with matching statuses

### Tasks

- TSK-049-01: Coerce known PASS plus COMPLIANCE_VIOLATION plus revert_red mix into revert_red route
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_handover_validation.py`
  - **Rationale**: `src/deviate/cli/micro.py:_invoke_agent` owns the handover validation branch that raises HANDOVER_INVALID for the known mix (`AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003` from `US-049-01`); `tests/unit/test_micro/test_handover_validation.py` pins that boundary and must assert coercion plus the still-invalid case.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_handover_validation.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Assert the exact PASS plus COMPLIANCE_VIOLATION plus revert_red manifest returns (not raises) with `next_action` revert_red and violation rationale copied into `train_feedback`; assert a still-invalid mix (e.g. PASS plus COMPLIANCE_VIOLATION plus a forward action) still raises PhaseFailedError with HANDOVER_INVALID.
    - **Green**: Implement the exact-triple coercion branch in `_invoke_agent` in `src/deviate/cli/micro.py`: match status PASS plus verdict COMPLIANCE_VIOLATION plus next_action revert_red only, log JUDGE_REJECTED, copy rationale into `train_feedback`, return the manifest so `_run_judge_phase` and `_apply_judge_verdict` take the revert_red path. GREEN cannot edit tests.
    - **Refactor**: Align the new branch with surrounding validation style; keep the strict rejection path unchanged for all other mixes.
    - **Edge Cases**: Handle missing rationale or train_feedback keys by coercing with an empty feedback string; handle repeat contradictions by routing every occurrence identically without exit 1.
    - **Acceptance**: Known mix re-runs RED without PhaseFailedError; malformed mixes still raise HANDOVER_INVALID; `mise run unit` passes.
  - **Dependency**: none

- TSK-049-02: Pair JUDGE prompt schema verdict examples with matching statuses
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Test Strategy**: unit
  - **Verification**: `mise run unit`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `src/deviate/prompts/auto/judge.md`
    - `tests/unit/test_micro/test_handover_validation.py`
  - **Rationale**: `src/deviate/prompts/auto/judge.md:186` pins status PASS on a schema block whose verdict admits COMPLIANCE_VIOLATION with revert_red (`AC-PLAN-004` from `US-049-01`); `tests/unit/test_micro/test_handover_validation.py` is the regression guard re-run to prove the prompt edit changes no runtime behavior.
  - **Details**:
    - **Implementation**: Change the violation example status in the schema block to a non-PASS value with COMPLIANCE_VIOLATION plus revert_red; keep the pass example COMPLIANT with a forward action; touch no other prompt text.
    - **Refactor**: Keep example formatting identical to surrounding schema lines.
    - **Edge Cases**: Handle no other verdict example drifting from its paired status; change only the violation example status token.
    - **Acceptance**: Violation example shows non-PASS status with COMPLIANCE_VIOLATION plus revert_red, pass example shows COMPLIANT plus forward action, `mise run unit` and `mise run check` stay green.
  - **Dependency**: `TSK-049-01`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 serial: TSK-049-01 -> TSK-049-02 (prompt edit lands after the coercion contract is pinned)

**Critical Dependency Chains**:
- TSK-049-01 must precede TSK-049-02

**Risk Hotspots**:
- Coercion matching wider than the exact three-field mix; mitigated by exact-match branch plus still-invalid test
- Violation rationale lost on coercion; mitigated by copying rationale into train_feedback before return

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_micro/test_handover_validation.py` (TSK-049-01 edits, TSK-049-02 re-runs only)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
