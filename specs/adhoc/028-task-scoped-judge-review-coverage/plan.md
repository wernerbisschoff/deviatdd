## Plan Summary
- **Issue**: ISS-ADH-028 — Scope TDD JUDGE evidence to this task and fail-close review on uncovered plan ACs
- **Implementation Strategy**: Resolve JUDGE required `AC-PLAN-NNN` tokens from this task first, then keep ISS-ADH-020 quote checks on that set. Add a runner-owned Gate 3 scan that fail-closes `deviate review` when any issue `plan.md` token lacks a COMPLETED claim.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/028-task-scoped-judge-review-coverage.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable meso and micro phases to drive Pi or OMP through RPC and stream live progress into a compact TUI.
- **Architecture Components Touched**: C1

## Acceptance Contract

**Scenario AC-PLAN-001: Scope JUDGE required tokens to this task**
- **Source Outline**: `AO-028-01`
- **Upstream Traceability**: `US-028-01`, `FR-ADHOC-028`, `AC-ADHOC-028-01`
- **Current-Code Evidence**: `src/deviate/core/judge_evidence.py:evaluate_judge_evidence`
- **Given**: The plan contract lists `AC-PLAN-001` and `AC-PLAN-002`, and this task owns only `AC-PLAN-001`.
- **When**: Evidence cites `AC-PLAN-001` with exact-substring quotes from the injected diff.
- **Then**: The gate returns no feedback and treats an omitted `AC-PLAN-002` as legal at JUDGE.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Resolve tokens by criteria, then card, then none**
- **Source Outline**: `AO-028-01`
- **Upstream Traceability**: `US-028-01`, `FR-ADHOC-028`, `AC-ADHOC-028-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_find_all_pending_tasks`
- **Given**: `TaskRecord.acceptance_criteria` may be non-empty, empty, or absent on a synthesized PENDING dict.
- **When**: The resolver computes this task's required `AC-PLAN-NNN` set.
- **Then**: Non-empty `criterion_id`s win; else the task card tokens win; else the set is empty.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Keep ISS-ADH-020 fail-closed on this-task tokens**
- **Source Outline**: `AO-028-02`
- **Upstream Traceability**: `US-028-02`, `FR-ADHOC-028`, `AC-ADHOC-028-02`
- **Current-Code Evidence**: `src/deviate/core/judge_evidence.py:_check_citation`
- **Given**: The resolved task token set includes `AC-PLAN-001` and the injected diff has matching hunks.
- **When**: Evidence omits that token, or supplies an empty quote, a path outside the diff or HEAD, a paraphrase quote, or a uniqueness-floor miss.
- **Then**: The runner rewrites PASS to `revert_to_red` with runner-authored feedback and does not COMPLETE the task.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Require evidence only for resolved tokens and leave non-TDD ungated**
- **Source Outline**: `AO-028-02`
- **Upstream Traceability**: `US-028-02`, `FR-ADHOC-028`, `AC-ADHOC-028-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:STEP_3`
- **Given**: Auto and manual judge prompts tell the agent to cite every injected plan `AC-PLAN-NNN`.
- **When**: The prompt templates and TDD gate routes update.
- **Then**: Prompts require `evidence` only for resolved task tokens, and EXECUTE, IMMEDIATE, and DIRECT stay ungated.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Fail-close review when a plan AC is unclaimed**
- **Source Outline**: `AO-028-03`
- **Upstream Traceability**: `US-028-03`, `FR-ADHOC-028`, `AC-ADHOC-028-03`
- **Current-Code Evidence**: `src/deviate/cli/review.py:pre`
- **Given**: This issue `plan.md` lists `AC-PLAN-001` and `AC-PLAN-002`, and no COMPLETED task on this issue claims `AC-PLAN-002`.
- **When**: The operator runs `deviate review pre` or `deviate review post`.
- **Then**: The runner exits non-zero or emits a non-PASS contract, and adequacy review cannot override the miss.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Pass review coverage when every plan token is claimed**
- **Source Outline**: `AO-028-03`
- **Upstream Traceability**: `US-028-03`, `FR-ADHOC-028`, `AC-ADHOC-028-03`
- **Current-Code Evidence**: `src/deviate/cli/review.py:pre`
- **Given**: Every `AC-PLAN-NNN` in this issue `plan.md` is claimed by a COMPLETED task on this issue, or a COMPLETED row already carries persisted evidence for that token.
- **When**: The operator runs `deviate review pre`.
- **Then**: Coverage is complete and the review contract may proceed or PASS.
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Treat missing plan tokens as complete and ignore non-COMPLETED claims**
- **Source Outline**: `AO-028-03`
- **Upstream Traceability**: `US-028-03`, `FR-ADHOC-028`, `AC-ADHOC-028-03`
- **Current-Code Evidence**: `src/deviate/cli/_common.py:resolve_issue_id_from_branch`
- **Given**: The issue has no `plan.md` or no `AC-PLAN-NNN` tokens, or only PENDING, FAILED, or sibling-issue rows name tokens.
- **When**: Review computes plan-AC coverage for the branch issue.
- **Then**: Missing plan tokens are vacuously complete, and only this-issue COMPLETED claims count.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/judge_evidence.py**: Own task-scoped token resolution and stop plan-wide fallback.
  - **Current State**: `evaluate_judge_evidence` extracts every `AC-PLAN-NNN` from `<authoritative_acceptance_contract source="plan.md">` via `_extract_ac_plan_tokens`. Quote, path, and uniqueness-floor checks already exist.
  - **Changes Required**: Accept an explicit `required_tokens` list. Do not fall back to the full plan set. Add `resolve_task_ac_tokens` with first-hit order: non-empty `acceptance_criteria` `criterion_id`s, else `AC-PLAN-NNN` tokens in this task's `tasks.md` card, else no AC tokens. Keep `_AC_TOKEN`, exact-substring, path-in-diff, uniqueness floor, empty-GREEN, and `skip_refactor` HEAD rules.
  - **Integration Surface**: `_rewrite_unmatched_tdd_pass`; review coverage helper; `tests/test_core/test_judge_evidence.py`.
- **src/deviate/cli/micro.py**: Pass resolved task tokens into the gate and inject the task card.
  - **Current State**: `_rewrite_unmatched_tdd_pass` passes `_resolve_spec_md(root, task)` as `plan_contract`. Synthesized PENDING dicts omit `acceptance_criteria`. `_build_auto_prompt` dumps `json.dumps(task)` only.
  - **Changes Required**: Resolve tokens from the live task dict plus the `tasks.md` card before `evaluate_judge_evidence`. Read the card when the in-memory dict omits `acceptance_criteria`. Inject the card next to the plan contract in the JUDGE prompt. Keep EXECUTE, IMMEDIATE, and DIRECT ungated. Keep ISS-ADH-022 `declared_paths` checks.
  - **Integration Surface**: `_run_judge_phase`; `_find_tasks_md_for_issue`; `_TDD_EVIDENCE_GATE_ROUTES`.
- **src/deviate/prompts/auto/judge.md**: Tell JUDGE to cite only resolved task tokens.
  - **Current State**: STEP_3 and `<constraints>` say "Cite every injected `AC-PLAN-NNN` in `evidence`".
  - **Changes Required**: Require `evidence` only for the resolved task tokens. Quotes must copy from `<diff>` or allowed HEAD files. Drop any instruction that every plan scenario must appear in this verdict. Keep paraphrase and later-work quotes illegal.
  - **Integration Surface**: `_build_auto_prompt("judge", ...)`.
- **src/deviate/prompts/commands/deviate-judge.md**: Mirror the auto prompt token-width change.
  - **Current State**: STEP 3 also says "Cite every injected `AC-PLAN-NNN`".
  - **Changes Required**: Same task-scoped evidence rule as the auto template. Keep EXECUTE out of this skill.
  - **Integration Surface**: Installed `/deviate-judge` skill body.
- **src/deviate/cli/review.py**: Fail-close Gate 3 when a plan AC is unclaimed.
  - **Current State**: `pre` always emits `status: READY` with no coverage field. `post` writes any supplied report.
  - **Changes Required**: Resolve the branch issue, scan `plan.md` for `AC-PLAN-NNN`, and claim tokens from this-issue COMPLETED rows via the same first-hit resolver. Honor a persisted evidence row only when a COMPLETED raw JSONL object already carries one. On a miss, exit non-zero and emit a non-PASS contract. `post` must not persist a PASS report over a miss. Vacuous complete when `plan.md` or tokens are absent.
  - **Integration Surface**: `resolve_issue_id_from_branch`; coverage helper; `tests/test_cli/test_review.py`.
- **src/deviate/core/review_coverage.py**: Unit-testable plan-versus-COMPLETED coverage helper.
  - **Current State**: File does not exist. Review has no AC coverage scan.
  - **Changes Required**: Parse plan tokens, latest this-issue task rows, and `tasks.md` cards. Return uncovered tokens with no agent call. Reuse `resolve_task_ac_tokens`. Do not add a #84 persistence field.
  - **Integration Surface**: `review.pre` / `review.post`; `tests/test_cli/test_review.py`.
- **tests/test_core/test_judge_evidence.py**: Invert plan-wide omit and keep this-task fail-closed pins.
  - **Current State**: `test_partial_coverage_fails_for_omitted_token` fails when plan lists `AC-PLAN-002` and evidence omits it.
  - **Changes Required**: Pass when the omitted token is not this task's required set. Keep missing this-task token, empty quote, path miss, paraphrase, and uniqueness-floor failures. Pin resolver precedence.
  - **Integration Surface**: `evaluate_judge_evidence`; `resolve_task_ac_tokens`.
- **tests/test_micro/test_judge.py**: Pin mid-plan COMPLETE and prompt wording.
  - **Current State**: `_seed_gate_issue` writes a `tasks.md` card with no AC tokens. `_run_tdd_judge` task dict omits `acceptance_criteria`. `test_partial_evidence_does_not_complete` treats a second plan token as required.
  - **Changes Required**: Seed this-task tokens so ISS-ADH-020 pins stay fail-closed. COMPLETE a GREEN-passing task whose evidence covers only the task tokens while the plan lists more. Assert the auto prompt no longer requires every plan AC. Mock `_run_pytest`. Use `tmp_git_repo` plus `_git_env()`.
  - **Integration Surface**: `_run_judge_phase`; `_build_auto_prompt`.
- **tests/test_cli/test_review.py**: Pin coverage fail-close and full-claim PASS.
  - **Current State**: `test_review_pre_emits_contract` asserts `status == READY` and exit 0 on a repo with no `plan.md`.
  - **Changes Required**: Keep the no-plan repo vacuously READY. Add fixtures where an unclaimed plan AC fail-closes, and where COMPLETED claims cover every plan token. PENDING, FAILED, and sibling-issue rows must not claim. Use `tmp_git_repo` plus `_git_env()`.
  - **Integration Surface**: `deviate review pre` / `post`.
- **specs/DeviaTDD-api.md**: Document task-scoped JUDGE tokens and Gate 3 coverage.
  - **Current State**: The TDD mechanical evidence gate checks every token from the plan contract block.
  - **Changes Required**: State that required tokens come from the task resolver, not the full plan set. State that `deviate review` fail-closes on an unclaimed plan AC. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` Judge and review bullets.
- **specs/DeviaTDD-architecture.md**: Record task-scoped JUDGE and Gate 3 coverage.
  - **Current State**: "The Judge" rejects unmatched PASS against every plan token in the injected contract.
  - **Changes Required**: JUDGE evidence is task-scoped. Gate 3 review owns plan-wide AC coverage. Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` review and evidence sections.
- **CHANGELOG.md**: Record the user-visible JUDGE and review contract change.
  - **Current State**: `[Unreleased]` has no task-scoped JUDGE or review-coverage bullet.
  - **Changes Required**: Append one `[Unreleased]` bullet: JUDGE evidence is task-scoped; `deviate review` fail-closes on an unclaimed plan AC.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: Task-scoped evidence helper
  - **Files**: `src/deviate/core/judge_evidence.py`, `tests/test_core/test_judge_evidence.py`
  - **Approach**: Add `resolve_task_ac_tokens` with first-hit order. Change `evaluate_judge_evidence` to require that explicit list. Invert `test_partial_coverage_fails_for_omitted_token` when the omitted token is not this task's. Keep ISS-ADH-020 quote pins.
  - **Verification**: `pytest tests/test_core/test_judge_evidence.py -q --tb=short`
- **Phase 2**: Wire JUDGE and update prompts
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/commands/deviate-judge.md`, `tests/test_micro/test_judge.py`
  - **Approach**: Resolve tokens from the task dict and the `tasks.md` card inside `_rewrite_unmatched_tdd_pass`. Inject the card next to the plan contract. Seed this-task tokens in gate fixtures so existing fail-closed tests stay red-then-green. Add a mid-plan COMPLETE case. Remove cite-every-plan wording.
  - **Verification**: `pytest tests/test_micro/test_judge.py -q --tb=short`
- **Phase 3**: Gate 3 plan-AC coverage
  - **Files**: `src/deviate/core/review_coverage.py`, `src/deviate/cli/review.py`, `tests/test_cli/test_review.py`
  - **Approach**: Scan `plan.md` tokens against this-issue COMPLETED claims. Fail-close `pre` and `post` on a miss. Honor persisted evidence only when a COMPLETED raw row already has it. Keep no-plan repos vacuously READY.
  - **Verification**: `pytest tests/test_cli/test_review.py -q --tb=short`
- **Phase 4**: Specs and changelog
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Update the mechanical evidence gate and `deviate review pre` contracts in the same implementation commit. Append one `[Unreleased]` bullet.
  - **Verification**: Diff the named sections against AC-PLAN-001 through AC-PLAN-007.

## Data Flow Analysis
- JUDGE inputs are the live task dict, the `tasks.md` card, `plan.md` inside `_resolve_spec_md`, `HandoverManifest.evidence`, and the already-built injected diff.
- `resolve_task_ac_tokens` turns those inputs into the required token list. `evaluate_judge_evidence` checks quotes only for that list and returns runner-authored feedback or `None`.
- `_rewrite_unmatched_tdd_pass` rewrites a forward PASS to `revert_to_red` when feedback is present. The JUDGE prompt receives the task card beside the plan contract so the agent emits only those tokens.
- Review inputs are the branch issue, `plan.md` `AC-PLAN-NNN` set, latest `tasks.jsonl` rows, `tasks.md` cards, and optional persisted evidence on COMPLETED rows.
- The coverage helper outputs uncovered tokens. `review pre` and `review post` fail-close on a non-empty uncovered set. No extra LLM call runs for coverage.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Gate fixtures omit card tokens, so ISS-ADH-020 fail-closed tests become empty-token passes | High | High | Seed this-task `AC-PLAN-001` on the card or `acceptance_criteria` before changing the helper |
| Review uses union-of-card-and-criteria and over-claims later-shard tokens | High | Medium | Reuse first-hit `resolve_task_ac_tokens` for COMPLETED claims |
| Synthesized PENDING dicts omit `acceptance_criteria` and skip the card | High | High | Read the `tasks.md` card in the runner, not only the in-memory dict |
| Existing `test_review_pre_emits_contract` breaks if no-plan repos lose READY | Medium | Medium | Vacuous complete when `plan.md` or tokens are absent |
| Merge conflict with ISS-ADH-020 quote pins or ISS-ADH-022 declared paths | High | Low | Keep substring, path-in-diff, uniqueness floor, and `declared_paths` unchanged |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths
Negative tests: paraphrase quotes fail; sibling-issue COMPLETED rows do not claim this issue's plan ACs; PENDING and FAILED rows do not claim tokens; hallucinated evidence paths still fail
Constraints: no new dependencies; no hardcoded secrets; no extra LLM call for coverage; do not persist #84 evidence fields; mock `deviate.cli.micro._run_pytest` on CLI paths that would spawn it

## Integration Points
- **`evaluate_judge_evidence`**: Caller supplies `required_tokens`. The helper does not extract the full plan set.
- **`_rewrite_unmatched_tdd_pass`**: Resolves tokens, then calls the helper with the existing injected diff and HEAD snapshot.
- **`_run_judge_phase`**: Injects the task card next to the plan contract. EXECUTE, IMMEDIATE, and DIRECT do not call the gate.
- **`deviate review pre` / `post`**: Runner-owned coverage. Adequacy review may still run after a complete claim set.
- **`TaskRecord.acceptance_criteria`**: First-hit source of `criterion_id`s. No new ledger row type.

## Constitutional Alignment
- **Architecture**: Micro JUDGE stays the per-task compliance gate. HITL Gate 3 (`deviate review`) owns issue-level plan-AC completeness. Gate 2 stays removed.
- **Testing**: pytest under `tests/` with constitution §3. RED writes failing pins first. GREEN implements only `src/` plus the listed prompts, specs, and changelog. Full suite stays under 30s by mocking `_run_pytest`.
- **Git Isolation**: Tests use `tmp_git_repo` plus `_git_env()` and `cwd=<tmp_git_repo>`. This worktree stays on `feat/adhoc/028-task-scoped-judge-review-coverage`.
- **Product Layer**: `flow_refs` is `[]`. This issue does not author or index flows. FLOW-04 stays RPC TUI live-stream, not JUDGE token width.
