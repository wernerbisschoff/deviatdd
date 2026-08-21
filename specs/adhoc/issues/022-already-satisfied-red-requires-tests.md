---
title: "already_satisfied RED cannot COMPLETE without declared regression tests"
labels: [bugfix, adhoc, vertical-slice, micro, red, judge]
blocked_by: []
coordinates_with: [ISS-ADH-020, ISS-ADH-021]
issue_id: ISS-ADH-022
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/022-already-satisfied-red-requires-tests.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py::_run_red_phase` — TARGET: after the RED agent returns, a test-bearing TDD task (`execution_mode` TDD / not EXECUTE-IMMEDIATE-DIRECT) that declares `failure_kind: already_satisfied` (or that is about to enter the no-failing-test COMPLETE route) must present a non-null, non-empty `files` set and/or `test_file`. Null/empty is a RED defect (`PhaseFailedError` or force the `test_defect` / `revert_before` path), not a path to COMPLETED.
  - `src/deviate/cli/micro.py::_adjudicate_red_no_failing_test` — TARGET: do not treat `skip_refactor` / bare `COMPLIANCE_PASS` as COMPLETED when the RED manifest named no regression files, or when those files are absent from the snapshot JUDGE just saw. `_restore_worktree_to_baseline` must not be the mechanism that both discards the mandated tests and then COMPLETEs the task.
  - `src/deviate/cli/micro.py::_run_judge_phase` / `_rewrite_unmatched_tdd_pass` — TARGET: compose with the ISS-ADH-020 evidence gate. On an `already_satisfied` / already-exists claim, refuse PASS unless declared `files` / `test_file` / evidence `test_path` exist in the injected `<diff>` path set (`_assemble_judge_injected_diff`) or the documented HEAD already-exists snapshot (`_evidence_head_contents`). Cross-check declared files against that snapshot (the `diff_summary` / injected-diff path set), not against agent rationale.
  - `src/deviate/core/judge_evidence.py::evaluate_judge_evidence` — TARGET: extend only as needed to fail closed when declared regression paths are missing from diff/HEAD; do not reopen quote uniqueness, AC token coverage, or EXECUTE ungating.
  - `src/deviate/core/agent.py::HandoverManifest` — REFERENCE: `files`, `test_file`, and `failure_kind: already_satisfied` already exist. Do not invent a second discriminator.
  - `src/deviate/prompts/auto/red.md` — TARGET: require `files` / `test_file` on `already_satisfied`; a passing suite without named test files is not a COMPLETE.
  - `tests/test_micro/test_orchestration.py` — TARGET: pin that `already_satisfied` + null/empty `files` does not COMPLETE (extends `test_micro_red_no_failing_test_routes_to_judge_skip_refactor`).
  - `tests/test_micro/test_judge.py` — TARGET: pin that JUDGE PASS on already-exists still requires the declared test path in the injected diff or HEAD (`test_already_exists_missing_test_file_fails` already covers missing HEAD test; add the RED-declared-`files` vs snapshot pin).
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document that already-exists COMPLETE requires named, present regression tests; the current “discard uncommitted passing test and COMPLETE” wording is the hole.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible COMPLETE contract change.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - TSK-005-02 / TSK-005-03 on issue 005-003: RED `failure_kind: already_satisfied` with `test_file: null` / `files: null`; JUDGE `COMPLIANCE_PASS`; ledger COMPLETED.
  - Grep found `TestGreenAdvisoryGate`, `TestGreenLedgerAudit`, `TestLedgerAudit` only in `tasks.md`, never in `tests/`.
  - RED rationale claimed tests were added and passed immediately; on-disk those classes do not exist.
  - GH #63 is this hole. GH #65 (ISS-ADH-020) already said `skip_refactor` + already-exists still requires test+impl quotes and no tests on disk still fails. GH #74 (ISS-ADH-021) is the SHA / GREEN-entry gate. Compose; do not reopen.

## The Problem Contract

`deviate micro` can COMPLETE a test-bearing TDD task when RED claims `already_satisfied` without naming or landing any regression tests. JUDGE then PASSes and the ledger is COMPLETED even though the classes mandated in `tasks.md` never appear under `tests/`. Operators need the runner to treat empty/null `files` as a RED defect and to refuse JUDGE PASS unless the declared test paths exist in the committed or injected snapshot.

## Scope Boundaries

### Hard Inclusions

- For a test-bearing TDD task, `_run_red_phase` / the already_satisfied route requires a non-null, non-empty `files` set (and/or `test_file`). Empty or null is a RED defect, not COMPLETED.
- JUDGE must not accept `COMPLIANCE_PASS` / `skip_refactor` on an `already_satisfied` claim unless every declared regression-test path exists in the injected `<diff>` or the documented already-exists HEAD snapshot. Cross-check `files` against that path set (`diff_summary` / `_assemble_judge_injected_diff` / `_evidence_head_contents`).
- A valid already_satisfied COMPLETE leaves those regression tests on disk (HEAD or committed RED snapshot). Completing after `_restore_worktree_to_baseline` wiped the only copy of the declared tests is a defect.
- Compose with ISS-ADH-020: keep evidence quotes, uniqueness floor, and `test_already_exists_missing_test_file_fails`. Add the declared-`files` membership check; do not redesign the evidence schema.
- Compose with ISS-ADH-021: do not invoke GREEN to invent missing tests; do not weaken `red_commit_sha` / GREEN-entry / `ROLLBACK_BOUNDARY_MISSING`.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for any git; mock `deviate.cli.micro._run_pytest` when a CLI path would spawn it.

### Defensive Exclusions

- Do **not** fatten GREEN (no “implement anyway” production files when the suite already passed).
- Do **not** reopen GH #65 (ISS-ADH-020 evidence quote/AC schema) or GH #74 (ISS-ADH-021 SHA / GREEN-entry) except to call them.
- Do **not** rename `failure_kind: already_satisfied` or add a second discriminator.
- Do **not** apply this gate to EXECUTE / IMMEDIATE / DIRECT tasks (non-test-bearing).
- Do **not** change how adhoc/plan picks TDD vs IMMEDIATE.
- Do **not** author or synchronize Product-layer flows; `flow_refs: []`.
- Do **not** revert operator-local `.deviate/config.toml` (backend=pi, transport=cli, pi_rpc=false, timeout=1800, models.default=grok-4.6).
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** treat a missing Product-layer flow as work.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-022`
- **Acceptance Criteria Tokens**: `AC-ADHOC-022-01`, `AC-ADHOC-022-02`, `AC-ADHOC-022-03`
- **Data Model Entities**: `HandoverManifest.files`, `HandoverManifest.test_file`, `HandoverManifest.failure_kind` (`already_satisfied`) — no new ledger rows
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` `_run_red_phase` / `_adjudicate_red_no_failing_test`
  - `src/deviate/cli/micro.py` `_run_judge_phase` / `_rewrite_unmatched_tdd_pass` / `_assemble_judge_injected_diff`
  - `src/deviate/core/judge_evidence.py::evaluate_judge_evidence`
  - `src/deviate/core/agent.py::HandoverManifest`
  - `specs/constitution.md` §3 Testing Protocols and §5 Definition of Done (tests exist; Judge phase passed)

## User Stories Ledger

- **US-022-01**: As a DeviaTDD operator, I want `already_satisfied` with null/empty `files` on a test-bearing TDD task treated as a RED defect so the ledger cannot COMPLETE without naming the regression tests. *(Ref: FR-ADHOC-022)*
- **US-022-02**: As a DeviaTDD operator, I want JUDGE to refuse PASS on an `already_satisfied` claim unless the declared test paths exist in the committed/injected snapshot so rationale-only COMPLETEs cannot ship. *(Ref: FR-ADHOC-022)*

## Acceptance Outline

- **AO-022-01** *(Ref: AC-ADHOC-022-01, US-022-01)*: Null/empty files on test-bearing `already_satisfied` cannot COMPLETE.
  - **Happy Path**: RED `failure_kind: already_satisfied` with `files: ["tests/test_gates.py"]` (or a non-empty `test_file`) may proceed to JUDGE adjudication.
  - **Error Category**: `files: null`, `files: []`, and `test_file: null` together on a TDD task yield `PhaseFailedError` or JUDGE `revert_before`; the task ledger has no COMPLETED row.
  - **Boundary Category**: EXECUTE / IMMEDIATE / DIRECT tasks stay ungated by this files requirement.

- **AO-022-02** *(Ref: AC-ADHOC-022-02, US-022-02)*: JUDGE PASS requires declared tests in the snapshot.
  - **Happy Path**: Declared test paths appear in the injected `<diff>` (dirty/untracked RED write) or in the HEAD already-exists snapshot; `COMPLIANCE_PASS` + `skip_refactor` may COMPLETE and those files remain on disk.
  - **Error Category**: Declared path absent from diff and HEAD (or named only in `tasks.md` / rationale) rewrites PASS to `revert_before` / `revert_to_red` with runner-authored feedback; no COMPLETED row.
  - **Boundary Category**: Cross-check is path membership against `_assemble_judge_injected_diff` / `_evidence_head_contents`, not semantic reading of class names.

- **AO-022-03** *(Ref: AC-ADHOC-022-03, US-022-01)*: Composition and GREEN stay thin.
  - **Happy Path**: ISS-ADH-020 quote checks and ISS-ADH-021 GREEN-entry SHA rules still fire on their existing fixtures.
  - **Error Category**: Completing after `_restore_worktree_to_baseline` deleted the only copy of the declared tests fails the pin.
  - **Boundary Category**: No extra GREEN production files; API / architecture / CHANGELOG update in the same implementation commit.

## Edge Cases and Boundaries

- A passing RED suite that is a *wrong* test remains `failure_kind: test_defect` → `revert_before` (ISS-ADH-021); this issue does not reclassify that as already-exists.
- `--no-judge` on a no-failing-test RED remains a hard `PhaseFailedError`.
- Already-exists citing a real HEAD test file that covers the behavior is still legal when `files` / `test_file` names that path and ISS-ADH-020 quotes succeed.
- Newly written passing regression tests that RED actually landed must not be discarded as the price of COMPLETE.
- Tasks with no `AC-PLAN-*` still need named test files if they are TDD test-bearing; do not invent ACs.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: ≤ 500ms CLI init; the files-vs-snapshot check is an in-process path-set membership test against the diff/HEAD snapshot already built for ISS-ADH-020, ≤ 50ms on the hot TDD loop (no extra agent call).
- Throughput: no additional agent calls versus today’s RED → JUDGE adjudication. Full test suite remains < 30s; tests that would drive `_run_pytest` must mock `deviate.cli.micro._run_pytest`.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_micro/test_orchestration.py` — `test_already_satisfied_null_files_does_not_complete` (name may vary): RED manifest `failure_kind: already_satisfied` with `files=None` / `test_file=None` and pytest exit 0 does not write COMPLETED.
  - `tests/test_micro/test_judge.py` — `test_already_satisfied_declared_files_missing_from_diff_fails`: JUDGE `skip_refactor` + declared `files` absent from injected diff and HEAD does not COMPLETE.
  - `tests/test_micro/test_judge.py` — existing `test_already_exists_missing_test_file_fails` and `test_already_exists_head_quotes_pass` stay green (compose, do not regress #65).
  - `tests/test_micro/test_green.py` / `tests/test_micro/test_two_counter_retry.py` — GREEN is not invoked to paper over the hole; #74 SHA pins stay green.
- **Integration Sandbox Targets**:
  - Stub-agent `_run_tdd_cycle` with mocked `_run_pytest` / `_run_test_cmd`: RED `already_satisfied` + empty files + JUDGE willing PASS → assert no COMPLETED and no GREEN invoke; RED `already_satisfied` + real test path in dirty/HEAD snapshot + matching #65 evidence → COMPLETE without GREEN.

## Demonstration Path

```bash
# Mocked TDD-loop pins (no live agent, no un-mocked pytest)
uv run pytest tests/test_micro/test_orchestration.py tests/test_micro/test_judge.py tests/test_micro/test_green.py tests/test_micro/test_two_counter_retry.py -q -k "already_satisfied or already_exists or no_failing_test"
```
