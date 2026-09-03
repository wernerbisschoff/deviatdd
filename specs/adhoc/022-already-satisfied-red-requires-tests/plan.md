## Plan Summary
- **Issue**: ISS-ADH-022 — already_satisfied RED cannot COMPLETE without declared regression tests
- **Implementation Strategy**: Gate test-bearing TDD `already_satisfied` and the no-failing-test COMPLETE route on a non-empty `files` and/or `test_file` set, then require those paths in the injected JUDGE snapshot or HEAD. Keep the tests on disk. Do not reopen ISS-ADH-020 quotes or ISS-ADH-021 GREEN-entry.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/022-already-satisfied-red-requires-tests.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it hardens C1 TDD already-exists COMPLETE, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase state and the TDD runner)

## Acceptance Contract

**Scenario AC-PLAN-001: Reject null or empty declared files on test-bearing already_satisfied**
- **Source Outline**: `AO-022-01`
- **Upstream Traceability**: `US-022-01`, `FR-ADHOC-022`, `AC-ADHOC-022-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`; `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test`; `src/deviate/core/agent.py:HandoverManifest`
- **Given**: A TDD task (`execution_mode` TDD) returns RED `failure_kind: already_satisfied` with `files` null or empty and `test_file` null, and the test command exits 0.
- **When**: `_run_red_phase` hands the manifest to `_adjudicate_red_no_failing_test`.
- **Then**: The runner raises `PhaseFailedError` or forces `test_defect` / `revert_before`, and the task ledger has no COMPLETED row.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Allow named files to reach JUDGE adjudication**
- **Source Outline**: `AO-022-01`
- **Upstream Traceability**: `US-022-01`, `FR-ADHOC-022`, `AC-ADHOC-022-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test`; `src/deviate/prompts/auto/red.md`
- **Given**: A TDD RED manifest sets `failure_kind: already_satisfied` and names `files: ["tests/test_gates.py"]` or a non-empty `test_file`.
- **When**: The test command exits 0 and the runner enters the no-failing-test route.
- **Then**: The runner calls `_run_judge_phase` and does not treat the empty-files defect as the reason to stop.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Leave EXECUTE IMMEDIATE and DIRECT ungated by the files rule**
- **Source Outline**: `AO-022-01`
- **Upstream Traceability**: `US-022-01`, `FR-ADHOC-022`, `AC-ADHOC-022-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_execute_phase`; `tests/unit/test_micro/test_judge.py:test_execute_judge_stays_ungated`
- **Given**: A task uses `execution_mode` EXECUTE, IMMEDIATE, or DIRECT.
- **When**: The phase completes without a non-empty `files` or `test_file` set.
- **Then**: This files gate does not raise and does not rewrite the route.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Accept JUDGE PASS when declared tests sit in the snapshot**
- **Source Outline**: `AO-022-02`
- **Upstream Traceability**: `US-022-02`, `FR-ADHOC-022`, `AC-ADHOC-022-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_assemble_judge_injected_diff`; `src/deviate/cli/micro.py:_evidence_head_contents`; `src/deviate/cli/micro.py:_rewrite_unmatched_tdd_pass`
- **Given**: Declared regression paths appear in the injected `<diff>` path set or in `_evidence_head_contents` HEAD text, and ISS-ADH-020 quotes still match.
- **When**: JUDGE emits `COMPLIANCE_PASS` with `next_action: skip_refactor` on an `already_satisfied` claim.
- **Then**: The runner may COMPLETE and those declared files remain on disk at HEAD or in the committed RED snapshot.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Rewrite PASS when declared tests are absent from the snapshot**
- **Source Outline**: `AO-022-02`
- **Upstream Traceability**: `US-022-02`, `FR-ADHOC-022`, `AC-ADHOC-022-02`
- **Current-Code Evidence**: `src/deviate/core/judge_evidence.py:evaluate_judge_evidence`; `src/deviate/cli/micro.py:_rewrite_unmatched_tdd_pass`
- **Given**: Declared `files` or `test_file` paths are missing from `_assemble_judge_injected_diff` and from `_evidence_head_contents`, or they appear only in `tasks.md` or agent rationale.
- **When**: JUDGE emits `skip_refactor` or a bare `COMPLIANCE_PASS` on the already-exists route.
- **Then**: The runner rewrites the action to `revert_before` or `revert_to_red` with runner-authored feedback and writes no COMPLETED row.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Refuse COMPLETE after restore wipes the only declared tests**
- **Source Outline**: `AO-022-03`
- **Upstream Traceability**: `US-022-01`, `FR-ADHOC-022`, `AC-ADHOC-022-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_restore_worktree_to_baseline`; `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test`
- **Given**: The only copy of the declared regression tests is the dirty or untracked RED write that JUDGE just saw.
- **When**: `_adjudicate_red_no_failing_test` would call `_restore_worktree_to_baseline` and then mark COMPLETED.
- **Then**: The runner keeps those files on disk (commit or skip the wipe) or refuses COMPLETE; it does not discard the only copy and then COMPLETE.
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Keep ISS-ADH-020 and ISS-ADH-021 pins and stay thin on GREEN**
- **Source Outline**: `AO-022-03`
- **Upstream Traceability**: `US-022-01`, `US-022-02`, `FR-ADHOC-022`, `AC-ADHOC-022-03`
- **Current-Code Evidence**: `tests/unit/test_micro/test_judge.py:test_already_exists_missing_test_file_fails`; `tests/unit/test_micro/test_judge.py:test_already_exists_head_quotes_pass`; `src/deviate/cli/micro.py:_run_green_phase`
- **Given**: Existing ISS-ADH-020 quote fixtures and ISS-ADH-021 GREEN-entry SHA fixtures run on this branch.
- **When**: The new files-membership gate lands in the same implementation commit as the API, architecture, and CHANGELOG edits.
- **Then**: Those fixtures stay green, GREEN is not invoked to invent missing tests, and `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` document that already-exists COMPLETE requires named present regression tests.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Own the RED files gate and the restore-then-COMPLETE hole.
  - **Current State**: `_run_red_phase` routes any exit-0 / no-tests result to `_adjudicate_red_no_failing_test` with no check of `manifest.files` or `manifest.test_file`. `_adjudicate_red_no_failing_test` sets `session.failure_kind = "no_failing_test"`, calls JUDGE, then on `skip_refactor` / bare `COMPLIANCE_PASS` runs `_restore_worktree_to_baseline` and returns so `_finish_tdd_cycle` writes COMPLETED. `_restore_worktree_to_baseline` deletes uncommitted RED tests. `_rewrite_unmatched_tdd_pass` checks ISS-ADH-020 quotes only. `_evidence_head_contents` reads paths from `manifest.evidence`, not from RED `files`.
  - **Changes Required**: After the RED agent returns, for a test-bearing TDD task that declares `already_satisfied` or that is about to enter the no-failing-test COMPLETE route, require a non-null non-empty `files` set and/or `test_file`. Null or empty is a RED defect (`PhaseFailedError` or force `test_defect` / `revert_before`). On `skip_refactor`, cross-check every declared path against the injected-diff path set and HEAD. If a declared path is missing, rewrite to `revert_before` / `revert_to_red` with runner-authored feedback. Do not call `_restore_worktree_to_baseline` in a way that discards the only copy of those tests and then COMPLETE. If the tests exist only as dirty RED writes, keep them (commit the RED snapshot or skip the wipe of those paths). Do not invoke GREEN. Do not apply the gate to EXECUTE / IMMEDIATE / DIRECT. Do not change `red_commit_sha` GREEN-entry or `ROLLBACK_BOUNDARY_MISSING`.
  - **Integration Surface**: `HandoverManifest.files`, `HandoverManifest.test_file`, `HandoverManifest.failure_kind`; `_run_judge_phase`; `_assemble_judge_injected_diff`; `_evidence_head_contents`; `_rewrite_unmatched_tdd_pass`; `evaluate_judge_evidence`; `_finish_tdd_cycle`.

- **src/deviate/core/judge_evidence.py**: Fail closed when declared regression paths are missing from diff or HEAD.
  - **Current State**: `evaluate_judge_evidence` returns `None` when the plan contract has no `AC-PLAN-*` tokens. Path checks run only for evidence `test_path` / `impl_path` inside the citation loop. Quote uniqueness and AC coverage already exist.
  - **Changes Required**: Extend only enough to reject when declared regression paths are absent from the injected-diff map and from `head_contents`. Run this membership check even when no `AC-PLAN-*` tokens exist. Do not change quote uniqueness, AC token coverage, or EXECUTE ungating. Reuse `_map_diff_hunks` / `_UNKNOWN_PATH` style feedback.
  - **Integration Surface**: `_rewrite_unmatched_tdd_pass` passes declared paths plus existing `evidence`, `injected_diff`, and `head_contents`.

- **src/deviate/core/agent.py**: Reference only.
  - **Current State**: `HandoverManifest` already has `files`, `test_file`, and `failure_kind: already_satisfied`.
  - **Changes Required**: Do not add a second discriminator. Do not rename `already_satisfied`.
  - **Integration Surface**: RED and JUDGE YAML parse.

- **src/deviate/prompts/auto/red.md**: Require named tests on `already_satisfied`.
  - **Current State**: The prompt tells the agent to keep the test and emit `failure_kind: already_satisfied`. The handover schema comments do not require `files` or `test_file`.
  - **Changes Required**: State that `already_satisfied` must name `files` and/or `test_file`. A passing suite with no named test files is not a COMPLETE.
  - **Integration Surface**: `_build_auto_prompt("red", ...)`.

- **tests/unit/test_micro/test_orchestration.py**: Pin the RED empty-files defect.
  - **Current State**: `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` COMPLETEs on `skip_refactor` with no RED `files` / `test_file` and with a seeded passing test that restore may discard.
  - **Changes Required**: Add `test_already_satisfied_null_files_does_not_complete` (name may vary): RED `failure_kind: already_satisfied`, `files=None`, `test_file=None`, pytest exit 0, mocked `_run_pytest` / `_run_test_cmd`, no COMPLETED row. Keep the existing skip_refactor happy path only when files are named and present. Use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>`.
  - **Integration Surface**: `_run_red_phase`; `_adjudicate_red_no_failing_test`; `_invoke_agent` mock.

- **tests/unit/test_micro/test_judge.py**: Pin declared-files membership on already-exists.
  - **Current State**: `test_already_exists_missing_test_file_fails` covers a missing HEAD test on evidence `test_path`. `test_already_exists_head_quotes_pass` COMPLETEs when HEAD quotes match. There is no pin that RED-declared `files` must appear in the injected-diff / HEAD path set.
  - **Changes Required**: Add `test_already_satisfied_declared_files_missing_from_diff_fails`: JUDGE `skip_refactor` plus declared `files` absent from injected diff and HEAD does not COMPLETE. Keep `test_already_exists_missing_test_file_fails` and `test_already_exists_head_quotes_pass` green. Keep `test_execute_judge_stays_ungated` green.
  - **Integration Surface**: `_run_judge_phase`; `_rewrite_unmatched_tdd_pass`; `evaluate_judge_evidence`.

- **tests/unit/test_micro/test_green.py** / **tests/unit/test_micro/test_two_counter_retry.py**: Composition only.
  - **Current State**: ISS-ADH-021 SHA / GREEN-entry pins live here.
  - **Changes Required**: Do not invoke GREEN to invent missing tests. Leave the SHA pins green. Add no extra GREEN production-file writes.
  - **Integration Surface**: `_run_green_phase`; `_run_tdd_cycle`.

- **specs/DeviaTDD-api.md**: Close the discard-and-COMPLETE wording.
  - **Current State**: `deviate red post` says JUDGE may COMPLETE and discard the uncommitted passing test. The TDD evidence-gate paragraph requires quotes but not named present `files` on already-exists COMPLETE.
  - **Changes Required**: Document that a test-bearing TDD already-exists COMPLETE requires named, present regression tests in the injected diff or HEAD. Empty `files` / `test_file` is a RED defect. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` RED no-failing-test bullet.

- **specs/DeviaTDD-architecture.md**: Same contract in the RED → JUDGE bullet.
  - **Current State**: The RED No-Failing-Test bullet says the runner discards the uncommitted passing test via `_restore_worktree_to_baseline` and marks COMPLETED.
  - **Changes Required**: Replace that hole. Already-exists COMPLETE keeps declared tests on disk. Empty declared files cannot COMPLETE. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` red-post and evidence-gate paragraphs.

- **CHANGELOG.md**: Record the user-visible COMPLETE contract change.
  - **Current State**: `[Unreleased]` still describes discard-uncommitted-test COMPLETE.
  - **Changes Required**: Append one `[Unreleased]` bullet: already-exists COMPLETE on a test-bearing TDD task requires named present regression tests; empty `files` cannot COMPLETE.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: RED declared-files gate
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/red.md`, `tests/unit/test_micro/test_orchestration.py`
  - **Approach**: After `_invoke_agent` in `_run_red_phase` / at the start of `_adjudicate_red_no_failing_test`, detect a test-bearing TDD task (`execution_mode` TDD, not EXECUTE / IMMEDIATE / DIRECT). If `failure_kind` is `already_satisfied` or the route is about to COMPLETE with no failing test, require `files` non-empty or `test_file` non-empty. Otherwise raise `PhaseFailedError` or force `test_defect` / `revert_before`. Update `red.md` so the agent names those fields. Mock `_run_pytest` and `_run_test_cmd`.
  - **Verification**: `uv run pytest tests/unit/test_micro/test_orchestration.py -q -k "already_satisfied or no_failing_test" --tb=short`

- **Phase 2**: Snapshot membership and restore-safe COMPLETE
  - **Files**: `src/deviate/core/judge_evidence.py`, `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_judge.py`, `tests/unit/test_core/test_judge_evidence.py`
  - **Approach**: Collect declared paths from RED `files` / `test_file` and from JUDGE evidence `test_path`. Cross-check membership against `_map_diff_hunks(_assemble_judge_injected_diff(...))` and `_evidence_head_contents` (include declared paths, not only evidence paths). Missing path rewrites PASS to `revert_before` / `revert_to_red` with runner-authored feedback. When the path exists only in the dirty snapshot, do not let `_restore_worktree_to_baseline` delete it and then COMPLETE; commit those tests or skip the wipe of those paths. Do not reopen quote uniqueness or AC coverage. Do not call GREEN.
  - **Verification**: `uv run pytest tests/unit/test_micro/test_judge.py tests/unit/test_core/test_judge_evidence.py -q -k "already_satisfied or already_exists" --tb=short`

- **Phase 3**: Composition pins, specs, changelog
  - **Files**: `tests/unit/test_micro/test_green.py`, `tests/unit/test_micro/test_two_counter_retry.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Re-run the ISS-ADH-020 already-exists fixtures and the ISS-ADH-021 GREEN-entry / `ROLLBACK_BOUNDARY_MISSING` pins. Edit API and architecture in the same implementation commit. Append the `[Unreleased]` bullet. Do not add GREEN production files.
  - **Verification**: `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_judge.py tests/unit/test_micro/test_green.py tests/unit/test_micro/test_two_counter_retry.py -q -k "already_satisfied or already_exists or no_failing_test"`

## Data Flow Analysis
- **Inputs**: RED `HandoverManifest.failure_kind`, `files`, `test_file`; task `execution_mode`; test-command exit code; JUDGE `next_action` / `verdict` / `evidence`; injected `<diff>` from `_assemble_judge_injected_diff`; HEAD bytes from `_git_show_head`.
- **Transform**: For TDD, empty declared files on `already_satisfied` or the COMPLETE route become a RED defect. Declared paths are checked for membership in the injected-diff path set or HEAD. Quote checks from ISS-ADH-020 still run. Restore cannot delete the only copy of a declared path on a COMPLETE route.
- **Pass output**: Named present tests plus matching quotes allow `skip_refactor` COMPLETE. Files remain on disk. GREEN is not called.
- **Fail output**: Empty files raise or force `revert_before`. Missing snapshot membership rewrites PASS. No COMPLETED row.
- **Storage**: No new ledger row schema. No new `failure_kind` value. Session still uses `no_failing_test` for the JUDGE discriminator.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `test_micro_red_no_failing_test_routes_to_judge_skip_refactor` still COMPLETEs with null files | High | High | Update that fixture to name a present test path, or keep it as the defect pin and add a named-files happy path. |
| Membership check lives only inside the AC-token loop and no-AC tasks still COMPLETE | High | High | Run declared-path membership even when `evaluate_judge_evidence` extracts no `AC-PLAN-*` tokens. |
| `_restore_worktree_to_baseline` still wipes dirty declared tests after a valid JUDGE PASS | High | High | Skip restore of declared paths or commit them before COMPLETE; pin that the files remain on disk. |
| Gate applied to EXECUTE / IMMEDIATE / DIRECT | High | Low | Branch on `execution_mode` TDD only. Keep `test_execute_judge_stays_ungated` green. |
| ISS-ADH-020 quote / uniqueness pins regress | High | Medium | Do not change `_check_quote` or AC coverage. Keep `test_already_exists_head_quotes_pass` and `test_already_exists_missing_test_file_fails`. |
| ISS-ADH-021 GREEN-entry / empty SHA pins regress | High | Low | Do not call GREEN to invent tests. Do not weaken `red_commit_sha` or `ROLLBACK_BOUNDARY_MISSING`. |
| Second discriminator invented beside `already_satisfied` | Medium | Low | Reuse `HandoverManifest.files`, `test_file`, and `failure_kind: already_satisfied`. |
| Extra agent call or extra git network blows L_max | Medium | Low | Path-set membership on the snapshot already built for ISS-ADH-020. No extra agent call. Budget ≤ 50ms. |
| Tests call un-mocked `_run_pytest` or inherit parent git | Medium | Medium | Mock `deviate.cli.micro._run_pytest`. Every test git call uses `cwd=<tmp_git_repo>` and `env=_git_env()`. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (existing git status / restore / show / diff in `_run_red_phase` and `_run_judge_phase`), file paths (declared `files` / `test_file` / evidence `test_path` vs injected-diff headers and HEAD reads).
Negative tests: `already_satisfied` with `files=None` / `files=[]` / `test_file=None` does not COMPLETE; declared path absent from diff and HEAD does not COMPLETE; path named only in `tasks.md` or rationale does not COMPLETE; restore-then-wipe of the only declared tests does not COMPLETE; EXECUTE / IMMEDIATE / DIRECT stay ungated; GREEN is not invoked to invent tests.
Constraints: no new dependencies; no hardcoded secrets; path checks use the already-built snapshot, not an unbounded filesystem walk; HEAD read stays limited to declared and evidence paths; do not revert operator-local `.deviate/config.toml`; do not fatten GREEN; do not call un-mocked `_run_pytest`; do not rename `already_satisfied`.

## Integration Points
- **`HandoverManifest.files` / `test_file` / `failure_kind`**: Existing fields. `already_satisfied` plus empty files is a RED defect on TDD. Do not add a second discriminator.
- **`_adjudicate_red_no_failing_test`**: Owns the COMPLETE-route files gate and the restore-safe keep of declared tests.
- **`_assemble_judge_injected_diff` / `_evidence_head_contents`**: Source of the path set for membership. Extend HEAD reads to declared files, not only evidence items.
- **`evaluate_judge_evidence` / `_rewrite_unmatched_tdd_pass`**: Add declared-path membership. Keep quote uniqueness and AC coverage. Unmatched already-exists PASS cannot COMPLETE.
- **`_run_green_phase` / ISS-ADH-021**: GREEN stays refused without a RED-phase SHA. This issue does not call GREEN to fill missing tests.
- **`_run_execute_phase`**: Stays ungated.
- **`src/deviate/prompts/auto/red.md`**: Agent must name `files` / `test_file` on `already_satisfied`.
- **API / architecture / CHANGELOG**: Same implementation commit. Close the “discard uncommitted passing test and COMPLETE” hole.

## Constitutional Alignment
- **Architecture**: Micro RED and JUDGE stay the TDD sandbox and compliance gate in the four-layer model (constitution §1). This plan does not skip a layer. Gate 2 stays absent. Product-layer work is out of scope.
- **Testing**: pytest under `tests/` with `tmp_git_repo` and `_git_env()` (constitution §3). GREEN must pass the suite. JUDGE checks declared tests against the plan contract and the snapshot. Coverage target ≥ 80%. Full suite stays under 30s. No un-mocked `_run_pytest`.
- **Git Isolation**: Work stays on `feat/adhoc/022-already-satisfied-red-requires-tests`. Production git uses `_git_env()`. This issue does not delete branches.
- **Product Layer**: Issue `flow_refs` is `[]`. Downstream artifacts keep empty flow references. This plan does not author or sync Product-layer flows.
