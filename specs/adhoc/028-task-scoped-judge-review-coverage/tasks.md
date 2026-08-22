# Implementation Tasks: `feat/adhoc/028-task-scoped-judge-review-coverage`

## Phase 1: Task-Scoped Evidence Tokens
**Goal**: `evaluate_judge_evidence` checks only this task's `AC-PLAN-NNN` set. `resolve_task_ac_tokens` picks criteria, then the card, then none.

### Tasks

- TSK-028-01: Scope JUDGE tokens to this task via first-hit resolver
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `uv run pytest tests/test_core/test_judge_evidence.py -q --tb=short`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/judge_evidence.py`
    - `tests/test_core/test_judge_evidence.py`
  - **Rationale**: US-028-01 and `AC-PLAN-001` require the gate to treat an omitted later-shard token as legal when this task owns only `AC-PLAN-001`. US-028-01 and `AC-PLAN-002` require first-hit order: non-empty `acceptance_criteria` `criterion_id`s, else `AC-PLAN-NNN` tokens in this task's `tasks.md` card, else no AC tokens. `src/deviate/core/judge_evidence.py` owns `evaluate_judge_evidence` and `_extract_ac_plan_tokens`. `tests/test_core/test_judge_evidence.py` owns `test_partial_coverage_fails_for_omitted_token` and the ISS-ADH-020 quote pins. Constitution §3 Testing Protocols: pytest under `tests/`; no agent; no git. Constitution §1 Micro-Layer Scope: JUDGE stays the per-task compliance gate.
  - **Details**:
    - **Red**: In `tests/test_core/test_judge_evidence.py`, invert `test_partial_coverage_fails_for_omitted_token` so evidence that cites only `AC-PLAN-001` with matching quotes returns `None` when `required_tokens` is `["AC-PLAN-001"]` and the plan contract still lists `AC-PLAN-002` (`AC-PLAN-001`). Add `test_resolve_task_ac_tokens_criteria_then_card_then_none`: non-empty `criterion_id`s win even when the card names other tokens; empty or absent `acceptance_criteria` uses card tokens; a card with no `AC-PLAN-NNN` yields `[]` (`AC-PLAN-002`). Keep empty quote, hallucinated path, paraphrase, and uniqueness-floor failures when the omitted or bad citation is this task's token. Do not spawn an agent. Do not run git.
    - **Green**: Add `resolve_task_ac_tokens` on `src/deviate/core/judge_evidence.py`. Read non-empty `acceptance_criteria` `criterion_id`s first. Else scan this task's card text with `_AC_TOKEN`. Else return `[]`. Change `evaluate_judge_evidence` to require an explicit `required_tokens` list. Do not fall back to `_extract_ac_plan_tokens` on the plan contract. Keep exact-substring, path-in-diff, uniqueness floor, empty-GREEN `test_quote`, `skip_refactor` HEAD, and `declared_paths` checks.
    - **Refactor**: Keep `_AC_TOKEN` as the only token regex. Keep one resolver used later by review coverage.
    - **Edge Cases**: A synthesized PENDING dict with no `acceptance_criteria` key still resolves from the card. Empty `acceptance_criteria` does not win over the card. Criteria that name `AC-PLAN-001` ignore extra card tokens. Empty `required_tokens` still runs `declared_paths` checks.
    - **Acceptance**: Omitted `AC-PLAN-002` is legal when it is not in `required_tokens`. Resolver precedence matches criteria, then card, then none. ISS-ADH-020 this-task quote pins stay fail-closed.

---

## Phase 2: Wire JUDGE and Prompt Token Width
**Goal**: `_rewrite_unmatched_tdd_pass` gates only resolved task tokens. Prompts ask for those tokens. EXECUTE, IMMEDIATE, and DIRECT stay ungated.

### Tasks

  - **Judge Feedback**: JUDGE evidence is missing, empty, or partial for injected acceptance tokens: AC-PLAN-003, AC-PLAN-005, AC-PLAN-004, AC-PLAN-006, AC-PLAN-007
- TSK-028-02: Gate TDD JUDGE on resolved task tokens and drop cite-every-plan wording
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_micro/test_judge.py -q --tb=short`
  - **Estimated Time**: 90 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/commands/deviate-judge.md`
    - `tests/test_micro/test_judge.py`
  - **Rationale**: US-028-02 and `AC-PLAN-003` require unmatched this-task citations to rewrite PASS to `revert_to_red` with runner-authored feedback and no COMPLETED row. US-028-01 and `AC-PLAN-004` require the auto and manual judge prompts to ask for evidence only for resolved task tokens. EXECUTE, IMMEDIATE, and DIRECT stay ungated. `src/deviate/cli/micro.py` owns `_rewrite_unmatched_tdd_pass`, `_run_judge_phase`, `_build_auto_prompt`, and `_find_tasks_md_for_issue`. Prompt files own STEP_3 wording. `tests/test_micro/test_judge.py` owns `_seed_gate_issue` and `test_partial_evidence_does_not_complete`. Constitution §3: mock `deviate.cli.micro._run_pytest`. Constitution §1 Git Isolation: `tmp_git_repo` plus `_git_env()`.
  - **Details**:
    - **Red**: In `tests/test_micro/test_judge.py`, seed this-task `AC-PLAN-001` on the `tasks.md` card or `acceptance_criteria` so ISS-ADH-020 fail-closed pins stay red-then-green (`AC-PLAN-003`). Keep missing this-task token, empty quote, path miss, paraphrase, and uniqueness-floor cases on `revert_to_red` with no COMPLETED row. Invert `test_partial_evidence_does_not_complete` into a mid-plan COMPLETE: plan lists `AC-PLAN-001` and `AC-PLAN-002`, this task owns only `AC-PLAN-001`, matching this-task quotes COMPLETE (`AC-PLAN-001`, `AC-PLAN-004`). Assert `_build_auto_prompt("judge", ...)` no longer says cite every injected plan `AC-PLAN-NNN`. Assert EXECUTE, IMMEDIATE, and DIRECT still skip `_TDD_EVIDENCE_GATE_ROUTES`. Use `tmp_git_repo` plus `_git_env()`. Mock `_run_pytest`.
    - **Green**: In `_rewrite_unmatched_tdd_pass`, resolve tokens with `resolve_task_ac_tokens` from the live task dict plus the `_find_tasks_md_for_issue` card when `acceptance_criteria` is empty or absent. Pass that list as `required_tokens` into `evaluate_judge_evidence`. In `_run_judge_phase` / `_build_auto_prompt`, inject the task card next to the plan contract. In `src/deviate/prompts/auto/judge.md` and `src/deviate/prompts/commands/deviate-judge.md`, require `evidence` only for resolved task tokens. Quotes must copy from `<diff>` or allowed HEAD files. Drop cite-every-plan wording. Keep paraphrase and later-work quotes illegal. Keep EXECUTE out of the manual skill. Keep ISS-ADH-022 `declared_paths` checks.
    - **Refactor**: Read the card in the runner, not only the in-memory dict. Reuse one resolver. Do not rebuild the injected diff.
    - **Edge Cases**: Synthesized PENDING dicts without `acceptance_criteria` still resolve from the card. Empty-token infra tasks still COMPLETE with empty evidence. `skip_refactor` HEAD quotes stay legal for this-task tokens only. Do not apply the gate to EXECUTE, IMMEDIATE, or DIRECT.
    - **Acceptance**: Mid-plan this-task evidence COMPLETEs. This-task quote failures stay `revert_to_red`. Prompts name resolved task tokens only. Non-TDD routes stay ungated.
  - **Dependency**: TSK-028-01

---

## Phase 3: Gate 3 Plan-AC Coverage
**Goal**: `deviate review` fail-closes when any issue `plan.md` `AC-PLAN-NNN` lacks a this-issue COMPLETED claim. No-plan repos stay vacuously READY.

### Tasks

  - **Judge Feedback**: JUDGE evidence is missing, empty, or partial for injected acceptance tokens: AC-PLAN-005
  - **Judge Feedback**: JUDGE evidence is missing, empty, or partial for injected acceptance tokens: AC-PLAN-002, AC-PLAN-005
- TSK-028-03: Fail-close review when a plan AC has no COMPLETED claim
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_cli/test_review.py -q --tb=short`
  - **Estimated Time**: 75 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/review_coverage.py`
    - `src/deviate/cli/review.py`
    - `tests/test_cli/test_review.py`
  - **Rationale**: US-028-03 and `AC-PLAN-005` require `deviate review pre` and `deviate review post` to exit non-zero or emit a non-PASS contract when any this-issue `plan.md` token lacks a COMPLETED claim. `AC-PLAN-006` requires READY or PASS when every token is claimed by a this-issue COMPLETED row or by persisted evidence already on that COMPLETED raw JSONL object. `AC-PLAN-007` requires vacuous complete when `plan.md` or tokens are absent, and ignores PENDING, FAILED, and sibling-issue rows. `src/deviate/core/review_coverage.py` is the unit-testable scan. `src/deviate/cli/review.py` owns `pre` and `post`. `tests/test_cli/test_review.py` owns `test_review_pre_emits_contract`. Constitution §1 HITL Gate 3: review owns issue-level completeness. Constitution §1 Append-Only Ledger: parse latest `tasks.jsonl` rows; add no #84 field. Constitution §3: `tmp_git_repo` plus `_git_env()`.
  - **Details**:
    - **Red**: Keep `test_review_pre_emits_contract` READY and exit 0 on a repo with no `plan.md` (`AC-PLAN-007`). Add a fixture where this issue `plan.md` lists `AC-PLAN-001` and `AC-PLAN-002` and no this-issue COMPLETED task claims `AC-PLAN-002`; `review pre` and `review post` exit non-zero or emit a non-PASS contract (`AC-PLAN-005`). Add a fixture where COMPLETED claims cover every plan token, or a COMPLETED raw row already carries persisted evidence for the miss; `review pre` may proceed or PASS (`AC-PLAN-006`). Assert PENDING, FAILED, and sibling-issue COMPLETED rows do not claim. Use `tmp_git_repo` plus `_git_env()`. Do not spawn an agent.
    - **Green**: Add `src/deviate/core/review_coverage.py`. Scan `plan.md` with `_AC_TOKEN` / `_extract_ac_plan_tokens`. Claim tokens from this-issue COMPLETED rows via `resolve_task_ac_tokens` (criteria, then card, then none). Honor persisted evidence only when a COMPLETED raw JSONL object already carries it. Return uncovered tokens. In `review.pre`, resolve the branch issue, run the scan, and fail-close on a non-empty uncovered set. In `review.post`, refuse to persist a PASS report over a miss. Vacuous complete when `plan.md` or tokens are absent.
    - **Refactor**: Reuse `resolve_task_ac_tokens`. Do not add a second resolver or a #84 persistence field. Do not add an LLM call.
    - **Edge Cases**: Adequacy review cannot override a coverage miss. Sibling-issue COMPLETED rows do not claim this issue's tokens. No `plan.md` stays READY. Coverage scan stays under 200ms on a typical issue.
    - **Acceptance**: Unclaimed plan AC fail-closes `pre` and `post`. Full this-issue COMPLETED claims pass coverage. No-plan and no-token repos stay vacuously complete.
  - **Dependency**: TSK-028-01

---

## Phase 4: Specs and Changelog
**Goal**: API and architecture name task-scoped JUDGE tokens and Gate 3 plan-AC coverage. CHANGELOG records the user-visible contract.

### Tasks

- TSK-028-04: Document task-scoped JUDGE evidence and review coverage
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/test_core/test_judge_evidence.py tests/test_micro/test_judge.py tests/test_cli/test_review.py -q --tb=short`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: `AC-PLAN-001` through `AC-PLAN-007` plus constitution §5 Definition of Done require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same change as the JUDGE and review contract. AGENTS.md Spec Alignment requires both spec files. US-028-01 is task-scoped JUDGE. US-028-03 is Gate 3 coverage. Constitution §1 Four-Layer Architecture: Gate 2 stays removed. HITL Gate 3 owns plan-wide completeness. `flow_refs` stays `[]`.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, state that TDD JUDGE required tokens come from `resolve_task_ac_tokens`, not the full plan set. State ISS-ADH-020 quote checks still apply to that set. State `deviate review` fail-closes on an unclaimed plan AC.
    - **Implementation**: In `specs/DeviaTDD-architecture.md`, state JUDGE evidence is task-scoped. State Gate 3 review owns plan-wide AC coverage. Keep EXECUTE, IMMEDIATE, and DIRECT ungated.
    - **Implementation**: Append one `[Unreleased]` bullet in `CHANGELOG.md`: JUDGE evidence is task-scoped; `deviate review` fail-closes on an unclaimed plan AC.
    - **Implementation**: Re-run the Phase 1 through Phase 3 pins. Do not author or sync Product-layer flows. Do not persist #84 evidence fields.
    - **Refactor**: Reuse the existing mechanical evidence gate and `deviate review pre` sections. Do not add a second coverage algorithm in the docs.
    - **Edge Cases**: Docs still say missing plan tokens are vacuously complete. Docs still say PENDING, FAILED, and sibling-issue rows do not claim. `flow_refs` stays `[]`.
    - **Acceptance**: API and architecture name task-scoped JUDGE tokens and Gate 3 coverage. CHANGELOG `[Unreleased]` has the ISS-ADH-028 bullet. Helper, JUDGE, and review pins stay green.
  - **Dependency**: TSK-028-03

---

## Phase 5: CLI E2E
**Goal**: Installed `deviate review` fail-closes on an unclaimed plan AC and stays READY when every this-issue COMPLETED claim covers the plan.

### Tasks

- TSK-028-05: [E2E] Verify installed review coverage fail-close and full-claim READY
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_review_plan_ac_coverage.bats`
    - `tests/e2e/test_macro_workflow.bats`
  - **Rationale**: US-028-03 and `AC-PLAN-005` are the user-visible critical-failure path: `deviate review pre` refuses PASS when a this-issue `plan.md` token has no COMPLETED claim. `AC-PLAN-006` is the happy path: full this-issue COMPLETED claims let review proceed. `AC-PLAN-007` keeps a no-plan repo READY. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_review_plan_ac_coverage.bats`. Happy path: seed a tmp git repo whose this-issue COMPLETED task claims every `plan.md` `AC-PLAN-NNN`. Run installed `deviate review pre`. Assert exit 0 and a READY or PASS contract (`AC-PLAN-006`). Also assert a no-plan repo stays READY (`AC-PLAN-007`).
    - **Implementation**: Critical-failure path in the same bats file: seed `AC-PLAN-001` and `AC-PLAN-002` with no COMPLETED claim for `AC-PLAN-002`. Run `deviate review pre`. Assert non-zero exit or a non-PASS contract (`AC-PLAN-005`). Do not spawn an agent. Do not call un-mocked `_run_pytest`.
    - **Implementation**: Keep `tests/e2e/test_macro_workflow.bats` as the existing CLI compose suite. Do not change it unless a pin breaks.
    - **Refactor**: Reuse bats tmpdir setup and the installed-package helper from existing e2e files.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` is unused. Do not delete branches in the host repo. PENDING rows must not make the miss look claimed.
    - **Acceptance**: `bats tests/e2e/` exits 0. Installed `deviate review pre` fail-closes on an unclaimed plan AC and stays READY when coverage is complete or vacuous.
  - **Dependency**: TSK-028-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2
2. Phase 1 -> Phase 3
3. Phase 3 -> Phase 4 -> Phase 5

**Critical Dependency Chains**:
- TSK-028-01 must precede TSK-028-02 (`resolve_task_ac_tokens` and `required_tokens` feed the JUDGE runner)
- TSK-028-01 must precede TSK-028-03 (review coverage reuses the same resolver)
- TSK-028-03 must precede TSK-028-04 (docs describe the shipped review contract)
- TSK-028-04 must precede TSK-028-05

**Risk Hotspots**:
- Gate fixtures omit card tokens, so ISS-ADH-020 fail-closed tests become empty-token passes
- Synthesized PENDING dicts omit `acceptance_criteria` and skip the `tasks.md` card
- Review unions card tokens with criteria and over-claims later-shard ACs
- `test_review_pre_emits_contract` loses READY on no-plan repos
- Merge conflict with ISS-ADH-020 quote pins or ISS-ADH-022 `declared_paths`
- Un-mocked `deviate.cli.micro._run_pytest` blows the 30s suite budget

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/judge_evidence.py` is Phase 1 only; Phase 3 imports `resolve_task_ac_tokens`. `src/deviate/cli/micro.py` and judge prompts stay Phase 2. `src/deviate/cli/review.py` stays Phase 3. Specs and CHANGELOG stay Phase 4. `tests/e2e/` stays Phase 5.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/028-task-scoped-judge-review-coverage.md` (frontmatter field: `flow_refs`)
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
