---
title: "Scope TDD JUDGE evidence to this task and fail-close review on uncovered plan ACs"
labels: [enhancement, adhoc, vertical-slice, judge, review]
blocked_by: []
coordinates_with: [ISS-ADH-020]
issue_id: ISS-ADH-028
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/028-task-scoped-judge-review-coverage.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/judge_evidence.py::evaluate_judge_evidence` — TARGET: stop treating every `AC-PLAN-NNN` inside `<authoritative_acceptance_contract source="plan.md">` as required evidence. Accept an explicit task-scoped token list (or resolve it before the call). Do not fall back to the full plan set.
  - `src/deviate/core/judge_evidence.py` (new resolver, same module or a thin sibling) — TARGET: first non-empty `TaskRecord.acceptance_criteria` `criterion_id`s; else `AC-PLAN-NNN` tokens named in this task's `tasks.md` card (rationale / details / acceptance); else require no AC tokens. Keep `_AC_TOKEN` / exact-substring / path-in-diff / uniqueness floor unchanged.
  - `src/deviate/cli/micro.py::_rewrite_unmatched_tdd_pass` / `_run_judge_phase` — TARGET: pass the resolved task tokens into the gate. Synthesized PENDING dicts from `tasks.md` often omit `acceptance_criteria` (Campfire TSK-002-04 was null) — read the card, do not trust the in-memory dict alone. Inject the task card next to the plan contract in the JUDGE prompt.
  - `src/deviate/prompts/auto/judge.md` / `src/deviate/prompts/commands/deviate-judge.md` — TARGET: emit `evidence` only for the resolved task tokens. Quotes must be copied from the injected `<diff>` or allowed HEAD files. Drop any instruction that every plan scenario must appear in this verdict. Paraphrases, comments, and "later work" sentences stay illegal.
  - `src/deviate/cli/review.py` (`pre` / `post`) — TARGET: runner-owned fail-close when any `AC-PLAN-NNN` in the issue `plan.md` is unclaimed by a COMPLETED task (`acceptance_criteria` or task-card tokens; honor persisted #84 evidence rows only if already present). Not an LLM quote game. Review may still judge adequacy; it cannot PASS on a coverage miss.
  - Optional helper next to review / judge evidence — TARGET: unit-testable plan-vs-COMPLETED coverage without spawning an agent.
  - `tests/unit/test_core/test_judge_evidence.py` — TARGET: invert `test_partial_coverage_fails_for_omitted_token` when the omitted token is not this task's; keep #65 fail-closed pins for this-task tokens / paraphrase quotes.
  - `tests/unit/test_micro/test_judge.py` — TARGET: mid-plan COMPLETE with task-scoped evidence; prompt no longer requires every plan AC in the verdict.
  - `tests/unit/test_cli/test_review.py` — TARGET: review fail-closes on an unclaimed plan AC; PASS only when every plan token is claimed by a COMPLETED task.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document task-scoped JUDGE tokens and Gate 3 plan-AC coverage in the same implementation commit.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible JUDGE/review contract change.
- **Classification for plan/tasks**: production Python with observable fail-to-pass behavior. Prefer **TDD**. Meso may shard JUDGE vs review into 2+ tasks. Do not fatten GREEN.
- **Upstream Evidence**:
  - GitHub #85 (2026-08-22): Campfire `TSK-002-04` GREEN passed; JUDGE agent emitted `COMPLIANCE_PASS`; runner rejected paraphrase rows for later-shard ACs (`AC-PLAN-003` / `004` / `006` / `008`) then TRAIN_EXHAUSTED.
  - `evaluate_judge_evidence` docstring: tokens come only from the full plan contract (`src/deviate/core/judge_evidence.py`).
  - `_rewrite_unmatched_tdd_pass` passes `_resolve_spec_md(root, task)` as `plan_contract` (`src/deviate/cli/micro.py`).
  - `TaskRecord.acceptance_criteria` defaults to `None` (`src/deviate/state/ledger.py`). Card `**Acceptance Criteria**` is parsed only when generating JSONL (`src/deviate/core/tasks_ledger.py`).
  - Auto judge still says "Cite every injected `AC-PLAN-NNN` in `evidence`" (`src/deviate/prompts/auto/judge.md`).
  - `deviate review pre` always emits `status: READY` with no AC coverage field (`src/deviate/cli/review.py`).
  - ISS-ADH-020 / GitHub #65: keep exact-substring / path-in-diff. ISS-ADH-022 / #63: declared regression paths still apply. Do not implement #84.

## The Problem Contract

A mid-epic TDD task implements a subset of `plan.md`. Today JUDGE demands mechanical evidence for every plan AC, so honest GREEN work dies on paraphrase quotes for later shards. Operators need task-scoped evidence at JUDGE and a runner-owned Gate 3 check that every plan AC was claimed by some COMPLETED task.

## Scope Boundaries

### Hard Inclusions

- Resolve JUDGE required tokens, first hit wins:
  1. Non-empty `TaskRecord.acceptance_criteria` `criterion_id`s.
  2. Else `AC-PLAN-NNN` tokens named in this task's `tasks.md` card (rationale / details / acceptance).
  3. Else no AC tokens (enabling / infra edge). Still require declared regression paths when ISS-ADH-022 / #63 applies.
- Never fall back to "every token in `plan.md`".
- Keep ISS-ADH-020 mechanics on the **task** token set: missing this-task tokens, empty quotes, paths not in the injected diff/HEAD, non-substring quotes, and uniqueness-floor failures rewrite PASS to `revert_to_red` with runner-authored feedback (`JUDGE_AGENT_NO_FEEDBACK` family).
- Inject the task card next to the plan contract. Tell JUDGE to emit `evidence` only for the resolved task tokens. Drop "cite every plan scenario" wording. Quotes must be copied from `<diff>` or allowed HEAD files.
- `deviate review pre` / `post` (or the existing review runner that gathers the PR diff) fail-closes when any `AC-PLAN-NNN` in that issue's `plan.md` is uncovered. Uncovered means: no COMPLETED task on this issue named the token in `acceptance_criteria` or its `tasks.md` card, and (if #84 evidence is already present on a COMPLETED row) no persisted evidence row for that token.
- Review coverage is runner-owned. Review may still judge adequacy. It cannot PASS if a plan AC has no completed claim.
- E2E / merge stay as they are except a review coverage miss is not optional.
- EXECUTE / IMMEDIATE / DIRECT stay ungated.
- Update API + architecture in the same implementation commit; CHANGELOG `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for any git; mock `deviate.cli.micro._run_pytest` if a CLI path would spawn it.

### Defensive Exclusions

- Do **not** loosen ISS-ADH-020 exact-substring / path-in-diff / uniqueness-floor matching.
- Do **not** implement GitHub #84 (persist validated evidence). Honor a persisted evidence row only if one already exists.
- Do **not** change Campfire 001-002 or its running micro.
- Do **not** reopen GitHub #63 / #74 / ISS-ADH-022 except to compose declared-path checks.
- Do **not** add verification profiles or `deviate evidence audit`.
- Do **not** apply the evidence gate to EXECUTE / IMMEDIATE / DIRECT.
- Do **not** author, repair, or index Product-layer flows (`flow_refs: []`). FLOW-04 is RPC TUI live-stream, not JUDGE token width.
- Do **not** delete branches, mutate operator-local `.deviate/config.toml` (`backend=pi`, `transport=cli`, `pi_rpc=false`, `timeout=1800`, `models.default=grok-4.6`, `timeout_seconds=1800`), or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** invent a second issue-id series. This issue is ISS-ADH-028.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-028`
- **Acceptance Criteria Tokens**: `AC-ADHOC-028-01`, `AC-ADHOC-028-02`, `AC-ADHOC-028-03`
- **Data Model Entities**: `TaskRecord.acceptance_criteria` (`CriterionLink.criterion_id`), `HandoverManifest.evidence` (existing; no new persistence), issue `plan.md` `AC-PLAN-NNN` set. No new ledger row types. Do not add #84 evidence fields.
- **Spec Source Anchors**:
  - `src/deviate/core/judge_evidence.py` `evaluate_judge_evidence` / `_extract_ac_plan_tokens`
  - `src/deviate/cli/micro.py` `_rewrite_unmatched_tdd_pass` / `_run_judge_phase` / `_resolve_spec_md`
  - `src/deviate/state/ledger.py` `TaskRecord` / `CriterionLink`
  - `src/deviate/core/tasks_ledger.py` card `**Acceptance Criteria**` parse
  - `src/deviate/cli/review.py` `pre` / `post`
  - `src/deviate/prompts/auto/judge.md` / `src/deviate/prompts/commands/deviate-judge.md`
  - `specs/constitution.md` §1 HITL Gate 3; §3 Testing Protocols (JUDGE verifies GREEN); §5 Definition of Done (assigned `AC-PLAN-NNN`, CHANGELOG)

## User Stories Ledger

- **US-028-01**: As a DeviaTDD operator, I want a mid-plan TDD task to COMPLETE when evidence covers only that task's AC tokens with real diff quotes so later shards do not burn the two-counter budget. *(Ref: FR-ADHOC-028)*
- **US-028-02**: As a DeviaTDD operator, I want paraphrase or missing citations for this task's tokens to still fail JUDGE so ISS-ADH-020 stays fail-closed. *(Ref: FR-ADHOC-028)*
- **US-028-03**: As a DeviaTDD operator, I want `deviate review` to refuse PASS when any `plan.md` AC-PLAN token was never claimed by a COMPLETED task so issue-level completeness lives at Gate 3. *(Ref: FR-ADHOC-028)*

## Acceptance Outline

- **AO-028-01** *(Ref: AC-ADHOC-028-01, US-028-01)*: JUDGE evidence is task-scoped.
  - **Happy Path**: Plan lists AC-PLAN-001 and AC-PLAN-002. Task owns only 001 via non-empty `acceptance_criteria` or card-named tokens. Evidence cites 001 with exact-substring quotes from the injected diff. Task COMPLETEs. Omitting 002 is legal at JUDGE.
  - **Error Category**: Falling back to every plan.md token, or requiring evidence for a later-shard AC, fails the pin.
  - **Boundary Category**: Empty `acceptance_criteria` plus card tokens uses the card. Card names none: require no AC tokens (infra / enabling). Synthesized PENDING dicts without the field still resolve from the card.

- **AO-028-02** *(Ref: AC-ADHOC-028-02, US-028-02)*: ISS-ADH-020 stays fail-closed on this task's tokens.
  - **Happy Path**: Matching this-task quotes still PASS on existing forward routes.
  - **Error Category**: Missing this-task token, empty quote, path not in diff/HEAD, paraphrase / non-substring quote, or uniqueness-floor miss rewrites PASS to `revert_to_red` with runner-authored feedback. Task does not COMPLETE.
  - **Boundary Category**: EXECUTE / IMMEDIATE / DIRECT stay ungated. Declared regression paths still fail closed when ISS-ADH-022 / #63 applies. Prompt no longer tells JUDGE every plan scenario must appear in this verdict.

- **AO-028-03** *(Ref: AC-ADHOC-028-03, US-028-03)*: Gate 3 owns plan-wide AC coverage.
  - **Happy Path**: Every `AC-PLAN-NNN` in the issue `plan.md` is claimed by at least one COMPLETED task (`acceptance_criteria` or task-card tokens). Review may proceed / PASS on coverage.
  - **Error Category**: Any plan AC with no COMPLETED claim makes `deviate review` fail-close (non-zero exit and/or non-PASS contract). Adequacy review cannot override the miss.
  - **Boundary Category**: If a COMPLETED row already carries persisted #84 evidence for a token, that token counts as claimed. This issue does not persist evidence. E2E / merge do not treat a coverage miss as optional. API / architecture / CHANGELOG land with the implementation.

## Edge Cases and Boundaries

- Mid-epic card names AC-PLAN-001 and half of AC-PLAN-005 (Campfire TSK-002-04 shape): require those named tokens only; later-shard ACs are review's problem.
- `acceptance_criteria` non-empty wins even if the card also names other AC-PLAN tokens.
- Enabling / infra task with no AC-PLAN tokens: empty evidence remains legal; do not invent ACs.
- Already-exists `skip_refactor`: quotes may still come from HEAD for this-task tokens only.
- Empty-GREEN `proceed_to_refactor_no_diff`: still require a dirty-diff `test_quote` for this-task tokens; omit `impl_quote`.
- Review with no `plan.md` or no `AC-PLAN-NNN`: coverage is vacuously complete (do not invent plan ACs).
- PENDING / FAILED tasks do not claim tokens; only COMPLETED rows count at review.
- Sibling issue COMPLETED rows do not claim this issue's plan ACs.

## Performance Constraints

- L_max: `evaluate_judge_evidence` and review coverage scan ≤ 200ms on a typical issue (`plan.md` + one `tasks.md` + `tasks.jsonl`).
- Throughput: no extra LLM call for coverage; runner-owned parse only. Full test suite stays under 30s; mock `_run_pytest` on CLI paths that would spawn it.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_core/test_judge_evidence.py` — task-scoped omit of AC-PLAN-002 passes; this-task paraphrase / missing token still fails; resolver precedence (criteria, then card, then none).
  - `tests/unit/test_cli/test_review.py` — uncovered plan AC fail-closes; full COMPLETED claims pass coverage.
- **Integration Sandbox Targets**:
  - `tests/unit/test_micro/test_judge.py` — `_run_judge_phase` COMPLETEs a GREEN-passing task whose evidence covers only the task tokens; prompt text no longer requires every plan AC.

## Demonstration Path

```bash
pytest tests/unit/test_core/test_judge_evidence.py tests/unit/test_cli/test_review.py tests/unit/test_micro/test_judge.py -q
```
