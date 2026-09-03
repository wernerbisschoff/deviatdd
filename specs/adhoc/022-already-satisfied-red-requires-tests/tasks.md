# Implementation Tasks: `feat/adhoc/022-already-satisfied-red-requires-tests`

## Phase 1: RED Declared-Files Gate
**Goal**: A test-bearing TDD `already_satisfied` or no-failing-test COMPLETE route requires a non-empty `files` set or `test_file`. Empty declared files cannot COMPLETE. EXECUTE, IMMEDIATE, and DIRECT stay ungated.

### Tasks

- TSK-022-01: Reject empty declared files on TDD already_satisfied
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_judge.py -q -k "already_satisfied or no_failing_test or execute_judge_stays_ungated" --tb=short`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/red.md`
    - `tests/unit/test_micro/test_orchestration.py`
    - `tests/unit/test_micro/test_judge.py`
  - **Rationale**: US-022-01 and `AC-PLAN-001` treat null or empty `files` plus null `test_file` as a RED defect on TDD. `AC-PLAN-002` lets a named path reach `_run_judge_phase`. `AC-PLAN-003` keeps EXECUTE, IMMEDIATE, and DIRECT ungated. `_run_red_phase` and `_adjudicate_red_no_failing_test` in `src/deviate/cli/micro.py` own the route. `src/deviate/prompts/auto/red.md` must name `files` or `test_file` on `already_satisfied`. Tests in `tests/unit/test_micro/test_orchestration.py` pin the defect and the named-files path. `tests/unit/test_micro/test_judge.py` keeps `test_execute_judge_stays_ungated` green. Constitution §1 Micro-Layer Scope: RED owns the failing-test contract. Constitution §3 requires pytest under `tests/` with mocked `_run_pytest`.
  - **Details**:
    - **Red**: Add `test_already_satisfied_null_files_does_not_complete` in `tests/unit/test_micro/test_orchestration.py`. Stub RED `failure_kind: already_satisfied` with `files=None` and `test_file=None`. Return pytest exit 0. Mock `deviate.cli.micro._run_pytest` and `_run_test_cmd`. Use `tmp_git_repo` plus `_git_env()` and `cwd=<tmp_git_repo>`. Assert no COMPLETED ledger row. Assert GREEN is never invoked. Add the same pin for `files=[]`. Add `test_already_satisfied_named_files_reaches_judge`: `files: ["tests/test_gates.py"]` or a non-empty `test_file` must call `_run_judge_phase`. Update `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` so it names a present test path. Keep `test_execute_judge_stays_ungated` passing.
    - **Green**: After `_invoke_agent` in `_run_red_phase`, or at the start of `_adjudicate_red_no_failing_test`, detect `execution_mode` TDD. If `failure_kind` is `already_satisfied` or the no-failing-test COMPLETE route is about to run, require a non-empty `files` set or a non-empty `test_file`. On empty declared files raise `PhaseFailedError` or force `test_defect` / `revert_before`. Do not write COMPLETED. Reuse `HandoverManifest.files`, `test_file`, and `failure_kind: already_satisfied`. Do not add a second discriminator. In `src/deviate/prompts/auto/red.md` require `files` and/or `test_file` on `already_satisfied`. State that a passing suite with no named test files is not a COMPLETE.
    - **Refactor**: Keep one ownership site for the files check. Prefer `_adjudicate_red_no_failing_test` so every no-failing-test COMPLETE route shares the gate.
    - **Edge Cases**: APPLY the gate only to TDD. EXECUTE, IMMEDIATE, and DIRECT complete without a non-empty `files` set. `--no-judge` on a no-failing-test RED stays a hard `PhaseFailedError`. Do not invoke GREEN to invent tests. Do not call un-mocked `_run_pytest`. Do not change `red_commit_sha` or `ROLLBACK_BOUNDARY_MISSING`.
    - **Acceptance**: Null or empty declared files on TDD `already_satisfied` yield no COMPLETED row. Named `files` or `test_file` reach JUDGE. `test_execute_judge_stays_ungated` stays green.

---

## Phase 2: Snapshot Membership and Restore-Safe COMPLETE
**Goal**: JUDGE PASS on already-exists requires every declared regression path in the injected `<diff>` or HEAD. COMPLETE keeps those files on disk.

### Tasks

- TSK-022-02: Require declared tests in the JUDGE snapshot and keep them on COMPLETE
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_judge.py tests/unit/test_core/test_judge_evidence.py -q -k "already_satisfied or already_exists" --tb=short`
  - **Estimated Time**: 90 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/judge_evidence.py`
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_judge.py`
    - `tests/unit/test_core/test_judge_evidence.py`
  - **Rationale**: US-022-02 and `AC-PLAN-005` refuse PASS when declared `files` or `test_file` are absent from `_assemble_judge_injected_diff` and `_evidence_head_contents`. `AC-PLAN-004` allows COMPLETE when those paths sit in the snapshot and ISS-ADH-020 quotes match. `AC-PLAN-006` forbids COMPLETE after `_restore_worktree_to_baseline` deletes the only copy. `evaluate_judge_evidence` in `src/deviate/core/judge_evidence.py` must run path membership even when no `AC-PLAN-*` tokens exist. `_rewrite_unmatched_tdd_pass` and `_adjudicate_red_no_failing_test` in `src/deviate/cli/micro.py` rewrite unmatched PASS and keep dirty RED tests. Tests in `tests/unit/test_micro/test_judge.py` and `tests/unit/test_core/test_judge_evidence.py` pin both outcomes. Constitution §3: JUDGE verifies the plan contract against the snapshot. Constitution §5: Judge phase passed requires tests on disk.
  - **Details**:
    - **Red**: Add `test_already_satisfied_declared_files_missing_from_diff_fails` in `tests/unit/test_micro/test_judge.py`. Seed a TDD already-exists route. Name `files` or `test_file` that are absent from the injected `<diff>` and from HEAD. Stub JUDGE `COMPLIANCE_PASS` with `next_action: skip_refactor`. Mock `deviate.cli.micro._run_pytest`. Assert the runner rewrites to `revert_before` or `revert_to_red` with runner-authored feedback. Assert no COMPLETED row. Add a pin that a path named only in `tasks.md` or agent rationale does not COMPLETE. Add a happy-path pin for `AC-PLAN-004`: declared path present in dirty `<diff>` or `_evidence_head_contents`, quotes still match, COMPLETE is allowed, and the file remains on disk. Add a restore pin for `AC-PLAN-006`: the only copy is a dirty or untracked RED write; after adjudication the file remains or COMPLETE is refused. Keep `test_already_exists_head_quotes_pass` and `test_already_exists_missing_test_file_fails` green. In `tests/unit/test_core/test_judge_evidence.py` pin declared-path membership with no `AC-PLAN-*` tokens.
    - **Green**: Collect declared paths from RED `files`, `test_file`, and JUDGE evidence `test_path`. Cross-check membership against `_map_diff_hunks(_assemble_judge_injected_diff(...))` and `_evidence_head_contents`. Extend `_evidence_head_contents` to read declared paths, not only evidence items. If a declared path is missing, rewrite PASS to `revert_before` or `revert_to_red` and attach runner-authored feedback. Run this check even when `evaluate_judge_evidence` extracts no `AC-PLAN-*` tokens. Keep quote uniqueness and AC coverage unchanged. On a valid `skip_refactor`, do not call `_restore_worktree_to_baseline` in a way that deletes the only copy and then COMPLETE. Commit the RED snapshot or skip the wipe of those paths. Do not invoke GREEN. Do not reopen ISS-ADH-020 quote rules.
    - **Refactor**: Reuse `_UNKNOWN_PATH` style feedback. Keep path-set membership on the snapshot already built for ISS-ADH-020. Add no extra agent call. Stay within the 50ms membership budget.
    - **Edge Cases**: Tasks with no `AC-PLAN-*` still need named present tests on TDD. A path that exists only as dirty RED text must survive COMPLETE. EXECUTE stays ungated. Do not fatten GREEN. Do not rename `already_satisfied`. Production git uses `_git_env()`.
    - **Acceptance**: Missing snapshot membership cannot COMPLETE. Present declared tests plus matching quotes may COMPLETE and remain on disk. ISS-ADH-020 already-exists fixtures stay green.
  - **Dependency**: TSK-022-01

---

## Phase 3: Composition Pins, Specs, and Changelog
**Goal**: Keep ISS-ADH-020 quote pins and ISS-ADH-021 GREEN-entry pins green. Document that already-exists COMPLETE requires named present regression tests.

### Tasks

- TSK-022-03: Align API, architecture, and CHANGELOG with the files gate
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_judge.py tests/unit/test_micro/test_green.py tests/unit/test_micro/test_two_counter_retry.py -q -k "already_satisfied or already_exists or no_failing_test"`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-007` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same change as the runner contract. US-022-01 and US-022-02 are the user-visible COMPLETE rule: named present regression tests. AGENTS.md Spec Alignment requires both spec files. ISS-ADH-020 fixtures in `tests/unit/test_micro/test_judge.py` and ISS-ADH-021 SHA pins in `tests/unit/test_micro/test_green.py` and `tests/unit/test_micro/test_two_counter_retry.py` must stay green. Constitution §1 Four-Layer Architecture: this slice does not skip a layer and does not restore Gate 2.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, replace the discard-uncommitted-passing-test COMPLETE wording. State that a test-bearing TDD already-exists COMPLETE requires named present regression tests in the injected `<diff>` or HEAD. State that empty `files` / `test_file` is a RED defect. State that EXECUTE, IMMEDIATE, and DIRECT stay ungated.
    - **Implementation**: In `specs/DeviaTDD-architecture.md`, update the RED No-Failing-Test bullet on C1. State that already-exists COMPLETE keeps declared tests on disk. State that `_restore_worktree_to_baseline` must not discard the only copy and then COMPLETE.
    - **Implementation**: Append one bullet under `CHANGELOG.md` `[Unreleased]`: already-exists COMPLETE on a test-bearing TDD task requires named present regression tests; empty `files` cannot COMPLETE.
    - **Implementation**: Re-run `test_already_exists_head_quotes_pass`, `test_already_exists_missing_test_file_fails`, and the ISS-ADH-021 GREEN-entry / `ROLLBACK_BOUNDARY_MISSING` pins. Do not edit GREEN production files. Do not weaken `red_commit_sha` or `ROLLBACK_BOUNDARY_MISSING`.
    - **Refactor**: Reuse existing Micro-layer already-exists wording. Do not add a second `failure_kind`. Do not author or sync Product-layer flows.
    - **Edge Cases**: Do not reopen ISS-ADH-020 quote uniqueness. Do not invoke GREEN to invent missing tests. `flow_refs` stays `[]`. Do not revert operator-local `.deviate/config.toml`.
    - **Acceptance**: API and architecture state the named-present-tests COMPLETE rule. CHANGELOG `[Unreleased]` has the user-visible bullet. ISS-ADH-020 and ISS-ADH-021 pins stay green.
  - **Dependency**: TSK-022-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3

**Critical Dependency Chains**:
- TSK-022-01 must precede TSK-022-02
- TSK-022-02 must precede TSK-022-03

**Risk Hotspots**:
- `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` still COMPLETEs with null files
- Membership check lives only inside the AC-token loop and no-AC tasks still COMPLETE
- `_restore_worktree_to_baseline` still wipes dirty declared tests after a valid JUDGE PASS
- Gate applied to EXECUTE / IMMEDIATE / DIRECT
- ISS-ADH-020 quote / uniqueness pins regress
- ISS-ADH-021 GREEN-entry / empty SHA pins regress
- Un-mocked `_run_pytest` blows the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/022-already-satisfied-red-requires-tests/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
