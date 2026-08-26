# Plan — ISS-ADH-031

## Plan Summary
- **Issue**: ISS-ADH-031 — Micro Judge already-exists COMPLIANCE_PASS must complete instead of hard-crashing with ROLLBACK_BOUNDARY_MISSING
- **Implementation Strategy**: Guard the mechanical evidence gate inside `_apply_judge_verdict` so a `failure_kind == "no_failing_test"` already-exists `COMPLIANCE_PASS` routes through `_NO_FAILING_TEST_FORWARD_ROUTES` to a graceful COMPLETED instead of being rewritten to `revert_to_red`, and relax the COMPLETED-write AC-token evidence check for that same route while keeping the declared-regression-files fail-closed gate.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Product Layer Anchors
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/031-judge-revert-boundary-no-failing-test.md` (frontmatter field: `flow_refs`)
- **Release Context**: The next release (`specs/_product/release-next.md`, Goal anchor FLOW-04) ships RPC subprocess transport and a Rich TUI for live agent progress; it is unrelated to this micro judge routing bug, which carries no `flow_refs` anchor.
- **Architecture Components Touched**: C1 (`deviate` CLI — micro orchestrator in `src/deviate/cli/micro.py`). The fix does not touch C2-C6 (RPC transport, JSONL framing, command sender, event adapter, TUI renderer).

**Invariant**: This issue has an empty `flow_refs` list and the requested change is application-level micro-orchestration behavior only. It does not authorize flow-catalog, release, DeviaTDD-setup, skill, or workflow-ledger work.

## Acceptance Contract

**Scenario AC-PLAN-001: A no_failing_test already-exists COMPLIANCE_PASS completes via skip_refactor without ROLLBACK_BOUNDARY_MISSING**
- **Source Outline**: `AO-031-01`
- **Upstream Traceability**: `US-031-01`, `FR-ADHOC-031`, `AC-ADHOC-031-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test` (line 1695), `src/deviate/cli/micro.py:_NO_FAILING_TEST_FORWARD_ROUTES` (line 1410)
- **Given**: `session.failure_kind == "no_failing_test"`, `session.red_commit_sha == ""`, and a RED no-failing-test task that declares a regression-pin `test_file` or `files` present in the worktree snapshot
- **When**: JUDGE emits `verdict: COMPLIANCE_PASS` with `next_action: skip_refactor` or a bare PASS verdict with no `next_action`
- **Then**: `_apply_judge_verdict` routes through `_NO_FAILING_TEST_FORWARD_ROUTES`, the task appends a COMPLETED transition, `pending_judge_action` is `skip_refactor`, the declared regression-pin test files remain on disk, and `ROLLBACK_BOUNDARY_MISSING` is never raised
- **Verification Mode**: automated

**Scenario AC-PLAN-002: A no_failing_test COMPLIANCE_PASS with partial evidence still completes instead of reverting to_red**
- **Source Outline**: `AO-031-01`
- **Upstream Traceability**: `US-031-01`, `FR-ADHOC-031`, `AC-ADHOC-031-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_apply_judge_verdict` (line 3226), `src/deviate/cli/micro.py:_rewrite_unmatched_tdd_pass` (line 3055), `src/deviate/core/judge_evidence.py:evaluate_judge_evidence` (line 56)
- **Given**: `session.failure_kind == "no_failing_test"`, `session.red_commit_sha == ""`, and a judge manifest with `verdict: COMPLIANCE_PASS`, `next_action: skip_refactor`, and evidence that cites all but one required `AC-PLAN-NNN` token
- **When**: `_apply_judge_verdict` runs the mechanical evidence gate
- **Then**: the gate does not rewrite the pass to `revert_to_red`, the task completes via `skip_refactor`, and the declared regression-pin tests remain on disk
- **Verification Mode**: automated

**Scenario AC-PLAN-003: A no_failing_test COMPLIANCE_PASS with no declared regression files fails closed**
- **Source Outline**: `AO-031-01`
- **Upstream Traceability**: `US-031-01`, `FR-ADHOC-031`, `AC-ADHOC-031-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_tdd_declared_regression_files` (line 1463), `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test` (line 1801)
- **Given**: `session.failure_kind == "no_failing_test"` and a judge `COMPLIANCE_PASS` with `skip_refactor` on a test-bearing TDD task whose manifest declares an empty `files` set and no `test_file`
- **When**: `_adjudicate_red_no_failing_test` takes the forward-route COMPLETE branch
- **Then**: `_require_tdd_declared_regression_files` raises `PhaseFailedError`, no COMPLETED transition is appended, and the task fails closed with no empty test deliverable
- **Verification Mode**: automated

**Scenario AC-PLAN-004: A genuine test-bearing RED with a real RED commit still routes to revert_to_red**
- **Source Outline**: `AO-031-01`
- **Upstream Traceability**: `US-031-01`, `FR-ADHOC-031`, `AC-ADHOC-031-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_to_red_boundary` (line 2492), `src/deviate/cli/micro.py:_rewrite_unmatched_tdd_pass` (line 3093)
- **Given**: a genuine test-bearing TDD task whose RED phase lands a failing test, records a non-empty `session.red_commit_sha`, and whose judge evidence omits a required `AC-PLAN-NNN` token
- **When**: `_apply_judge_verdict` runs the mechanical evidence gate
- **Then**: the unmatched pass rewrites to `revert_to_red`, `_require_revert_to_red_boundary` resolves the standing RED SHA, and the runner rolls back to RED without weakening the evidence gate
- **Verification Mode**: automated

**Scenario AC-PLAN-005: A no_failing_test COMPLIANCE_VIOLATION still routes to revert_before**
- **Source Outline**: `AO-031-02`
- **Upstream Traceability**: `US-031-02`, `FR-ADHOC-031`, `AC-ADHOC-031-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_coerce_judge_action` (line 2657), `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test` (line 1783)
- **Given**: `session.failure_kind == "no_failing_test"`, `session.red_commit_sha == ""`, and a judge `verdict: COMPLIANCE_VIOLATION` or `next_action: revert_before`
- **When**: `_apply_judge_verdict` coerces the action
- **Then**: `_coerce_judge_action` forces `revert_before`, the runner resets to the RED baseline, `pending_judge_action` is `revert_before`, and the TDD loop re-dispatches RED to re-author a genuinely failing test
- **Verification Mode**: automated

**Scenario AC-PLAN-006: The already-exists pass path never raises ROLLBACK_BOUNDARY_MISSING**
- **Source Outline**: `AO-031-02`
- **Upstream Traceability**: `US-031-02`, `FR-ADHOC-031`, `AC-ADHOC-031-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_require_revert_to_red_boundary` (line 2497), `src/deviate/cli/micro.py:_apply_judge_verdict` (line 3383)
- **Given**: the already-exists `no_failing_test` `COMPLIANCE_PASS` pass path with `session.red_commit_sha == ""`
- **When**: the runner completes the task through `_NO_FAILING_TEST_FORWARD_ROUTES`
- **Then**: `_require_revert_to_red_boundary` is never invoked on that path, so `ROLLBACK_BOUNDARY_MISSING` is not raised, and the boundary helper remains reachable only for a genuine `revert_to_red` with a real RED commit
- **Verification Mode**: automated

**Scenario AC-PLAN-007: The shared judge-verdict helper does not regress the manual judge post path**
- **Source Outline**: `AO-031-01, AO-031-02`
- **Upstream Traceability**: `US-031-01`, `FR-ADHOC-031`, `AC-ADHOC-031-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_apply_judge_verdict` (line 3193), `src/deviate/cli/micro.py:_run_judge_phase` (line 3096)
- **Given**: `_apply_judge_verdict` is invoked from the manual `judge post` path on a no_failing_test task
- **When**: the manual path applies the same post-verdict side effects
- **Then**: a `skip_refactor` pass still completes, a `revert_to_red` with a standing RED SHA still rolls back, and the shared helper does not regress the non-auto path
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Primary fix for the micro judge routing crash.
  - **Current State**: `_apply_judge_verdict` calls `_rewrite_unmatched_tdd_pass` unconditionally, which rewrites a `no_failing_test` `COMPLIANCE_PASS` to `revert_to_red` on partial evidence, then `_require_revert_to_red_boundary` raises `ROLLBACK_BOUNDARY_MISSING` because `session.red_commit_sha` is empty on the already-exists path.
  - **Changes Required**: Skip `_rewrite_unmatched_tdd_pass` when `session.failure_kind == "no_failing_test"` and the verdict is a forward-route PASS. Ensure the COMPLETED-write AC-token evidence check (`_require_tdd_completed_evidence` via `_append_status_transition`) does not raise `COMPLETED_EVIDENCE_MISSING` on partial evidence for the same route, while still enforcing declared-regression-path presence. Keep `revert_before` and genuine `revert_to_red` routes unchanged.
  - **Integration Surface**: `_coerce_judge_action`, `_rewrite_unmatched_tdd_pass`, `_NO_FAILING_TEST_FORWARD_ROUTES`, `_require_revert_to_red_boundary`, `_require_tdd_declared_regression_files`, `_append_status_transition`, and `SessionState.failure_kind` / `pending_judge_action` / `red_commit_sha`.
- **tests/test_micro/test_judge.py**: Unit sandbox for the fix.
  - **Current State**: `test_already_exists_head_quotes_pass` (line 3315) drives `_run_tdd_judge` with `next_action=skip_refactor` on a RED-boundary task.
  - **Changes Required**: Add a test that a `no_failing_test` `COMPLIANCE_PASS` with `red_commit_sha == ""` and partial evidence completes via `skip_refactor` instead of raising `ROLLBACK_BOUNDARY_MISSING`. Keep the genuine-test `revert_to_red` and `revert_before` assertions intact.
  - **Integration Surface**: `_run_judge_phase`, `_apply_judge_verdict`, `_adjudicate_red_no_failing_test`, `HandoverManifest`, `SessionState`.
- **tests/test_cli/test_micro.py**: Integration sandbox reproducing the `TSK-029-02` crash.
  - **Current State**: The `_run_pytest`-mocked CLI path covers judge routing and `ROLLBACK_BOUNDARY_MISSING` (lines 1760-1816).
  - **Changes Required**: Add a `_run_pytest`-mocked CLI test that drives a `no_failing_test` already-exists task end to end and asserts it COMPLETES with no `ROLLBACK_BOUNDARY_MISSING` traceback.
  - **Integration Surface**: `deviate micro run`, `_run_tdd_cycle`, `_run_red_phase`, `_run_judge_phase`.
- **specs/DeviaTDD-api.md**: Update the `no_failing_test` adjudication contract (line 595-604) to state that a `COMPLIANCE_PASS` already-exists pass completes via `skip_refactor` even with partial AC evidence, and that `ROLLBACK_BOUNDARY_MISSING` only applies to a genuine `revert_to_red` with a real RED commit.
- **specs/DeviaTDD-architecture.md**: Update §3 (line 288) to describe the guarded already-exists COMPLETE route and the retained fail-closed regression-files gate.
- **CHANGELOG.md**: Append a bullet under `[Unreleased]` `### Fixed` for the user-visible hard-crash fix.

## Implementation Strategy
- **Phase 1**: Guard the evidence gate in `src/deviate/cli/micro.py` — deliverable: `no_failing_test` already-exists `COMPLIANCE_PASS` no longer rewrites to `revert_to_red`.
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: In `_apply_judge_verdict`, run `_rewrite_unmatched_tdd_pass` only when `session.failure_kind != "no_failing_test"`. In the COMPLETED-write evidence check, skip the AC-token citation requirement for `failure_kind == "no_failing_test"` while retaining the declared-regression-path presence gate.
  - **Verification**: `pytest tests/test_micro/test_judge.py -v` passes; the new partial-evidence no_failing_test test completes with no `ROLLBACK_BOUNDARY_MISSING`.
- **Phase 2**: Add regression tests — deliverable: failing-then-passing RED coverage for the fix.
  - **Files**: `tests/test_micro/test_judge.py`, `tests/test_cli/test_micro.py`
  - **Approach**: Add a unit test driving `_adjudicate_red_no_failing_test` / `_run_judge_phase` with `red_commit_sha == ""` and partial evidence, and a `_run_pytest`-mocked CLI test for the `TSK-029-02` shape. Assert COMPLETED + `skip_refactor`, regression-pin tests on disk, no crash.
  - **Verification**: `pytest tests/ -v` (full suite under 30s with mocked `_run_pytest`); `ruff check .` clean.
- **Phase 3**: Align specs and changelog — deliverable: documentation reflects the final behavior.
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Update the `no_failing_test` adjudication descriptions and add a `[Unreleased]` Fixed bullet.
  - **Verification**: `mise run check` exits 0.

## Data Flow Analysis
- RED phase calls `_run_red_phase`, which routes a no-failing-test outcome to `_adjudicate_red_no_failing_test`.
- `_adjudicate_red_no_failing_test` sets `session.failure_kind = "no_failing_test"` and dispatches `_run_judge_phase`.
- `_run_judge_phase` builds the JUDGE prompt with a `<failure_kind>no_failing_test</failure_kind>` block and the uncommitted RED test diff, then calls `_apply_judge_verdict`.
- `_apply_judge_verdict` coerces `next_action` via `_coerce_judge_action`, then applies the evidence gate. On the fixed route it keeps `skip_refactor`, stashes validated evidence, appends a COMPLETED transition, and parks the session at IDLE.
- `_adjudicate_red_no_failing_test` enforces `_require_tdd_declared_regression_files`, restores the worktree to the RED baseline while keeping declared regression paths, and clears the session for the next task.
- On `COMPLIANCE_VIOLATION`, `_coerce_judge_action` forces `revert_before`; the runner resets to the RED baseline and re-dispatches RED. Storage: append-only `specs/**/tasks.jsonl` COMPLETED row plus `.deviate/session.json` transient state.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Guarding on `failure_kind == "no_failing_test"` accidentally also skips the evidence gate for `test_defect` or `mechanical` routes | Medium | Low | Restrict the guard strictly to `no_failing_test`; keep the AC-token evidence gate for all other failure kinds and for the genuine test-bearing RED path. |
| Relaxing the COMPLETED-write evidence check weakens fail-closed on missing regression files | Medium | Low | Keep `_require_tdd_declared_regression_files` and the declared-path presence gate intact for the no_failing_test route; only the AC-token citation check is relaxed. |
| The shared `_apply_judge_verdict` regresses the manual `judge post` path | Medium | Low | The guard keys on `session.failure_kind`, which both auto and manual paths already set; add a judge-post regression scenario (AC-PLAN-007). |
| Double COMPLETED append on the no_failing_test forward route | Medium | Medium | The relaxed evidence check must tolerate the second `_append_status_transition`; verify the ledger keeps a single COMPLETED transition per task in tests. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve the empty `flow_refs` and plan the application behavior without creating flow or DeviaTDD-setup work. |

## Security Profile

Risk surfaces: subprocess (git reset / clean / restore during rollback), file paths (declared regression-test paths, `_evidence_head_contents`), ledger writes (append-only `tasks.jsonl`).

Negative tests: The `no_failing_test` already-exists COMPLIANCE_PASS never invokes `_require_revert_to_red_boundary`, so no git reset to an invented `HEAD~1` boundary occurs; a partial-evidence pass does not silently destroy the declared regression-pin tests; a `COMPLIANCE_VIOLATION` still fails closed to `revert_before` and never completes with an empty test deliverable.

Constraints: No new dependencies; no hardcoded secrets; no invented RED boundary or `HEAD~1` fallback; no changes to `flow_refs` or Product-layer flow artifacts; no file-path path traversal beyond the existing relative-path guard in `_evidence_head_contents`.

## Integration Points
- **`_adjudicate_red_no_failing_test`**: Routes the RED no-failing-test outcome; owns the forward-route COMPLETE and the `revert_before` re-author contract.
- **`_apply_judge_verdict`**: Shared by auto `_run_judge_phase` and manual `judge post`; owns `next_action` coercion, the evidence gate, and the violation/forward side effects.
- **`_require_revert_to_red_boundary`**: Fatal `ROLLBACK_BOUNDARY_MISSING` for a genuine `revert_to_red` with no RED SHA; must stay reachable only for real revert routes.
- **`_require_tdd_declared_regression_files` / `_require_tdd_completed_evidence`**: The fail-closed files gate and the AC-token completed-evidence gate.
- **`SessionState` fields `failure_kind`, `red_commit_sha`, `pending_judge_action`, `last_judge_verdict`**: Discriminators that drive the guarded routing.

## Constitutional Alignment
- **Architecture**: Aligns with the Micro layer (RED → GREEN → JUDGE → REFACTOR) and the Git Isolation Principle (§1) — the fix refuses to invent a RED boundary and completes the already-exists task without a destructive rollback.
- **Testing**: pytest under `tests/`; GREEN passes all tests and JUDGE verifies GREEN modified only allowed files; the full suite stays under 30s by mocking `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture.
- **Git Isolation**: The fix runs on the dedicated issue branch/worktree; the already-exists pass writes no RED commit and does not mutate git history, and `_require_revert_to_red_boundary` stays reserved for genuine revert routes with a real RED commit.
- **Product Layer**: This issue carries an empty `flow_refs` and touches only application micro-orchestration behavior in C1; it preserves the existing user-visible flows and does not author or synchronize any Product-layer flow catalog.
