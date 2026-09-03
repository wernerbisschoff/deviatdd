## Plan Summary
- **Issue**: ISS-ADH-020 — TDD JUDGE COMPLIANCE_PASS Requires Mechanical Diff Evidence
- **Implementation Strategy**: Add a first-class `HandoverManifest.evidence` list and a path-plus-substring gate in `_run_judge_phase` that rewrites unmatched TDD PASS into `revert_to_red`. Keep EXECUTE and IMMEDIATE judge paths unchanged.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/020-judge-compliance-pass-evidence.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable meso and micro phases to drive Pi or OMP through RPC and stream live progress into a compact TUI.
- **Architecture Components Touched**: C1

## Acceptance Contract

**Scenario AC-PLAN-001: Parse first-class evidence on HandoverManifest**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-01`, `FR-ADHOC-020`, `AC-ADHOC-020-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:HandoverManifest`
- **Given**: `HandoverManifest` allows extra keys and has no first-class `evidence` field the gate can read.
- **When**: YAML with `evidence` items (`ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`) plus an unknown extra key is parsed.
- **Then**: `HandoverManifest.evidence` round-trips those items and extra keys still parse.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Reject PASS that lacks matching citations**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-01`, `FR-ADHOC-020`, `AC-ADHOC-020-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: The injected plan contract lists `AC-PLAN-001` and `_run_judge_phase` already built `<diff>` from `git diff <red>^..HEAD` plus dirty `git diff HEAD` and untracked `--no-index` hunks.
- **When**: Judge YAML is `verdict: COMPLIANCE_PASS` with missing, empty, or partial `evidence`, a path absent from the diff headers, a quote that is empty, below the uniqueness floor, or not an exact substring of the named file hunk.
- **Then**: The runner does not COMPLETE; it forces `revert_to_red` with runner-authored feedback in the `JUDGE_AGENT_NO_FEEDBACK` family.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Accept PASS when quotes match the injected diff**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-02`, `FR-ADHOC-020`, `AC-ADHOC-020-03`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: The injected `<diff>` contains a test hunk and an impl hunk, and each evidence quote is an exact substring of the named path hunk with at least 12 non-whitespace characters or the full added line if that line is shorter.
- **When**: Judge YAML is `verdict: COMPLIANCE_PASS` with that `evidence` list covering every injected `AC-PLAN-NNN` token.
- **Then**: The runner keeps the PASS and follows the existing forward route.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Accept empty-GREEN PASS with a dirty-diff test quote**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-03`, `FR-ADHOC-020`, `AC-ADHOC-020-04`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: `next_action` is `proceed_to_refactor_no_diff` and the dirty or untracked diff contains the uncommitted RED test.
- **When**: Evidence cites that test with a matching `test_quote` and omits `impl_quote`.
- **Then**: The runner accepts the empty-GREEN PASS and does not require an impl quote.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Accept already-exists HEAD quotes and reject a missing test file**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-03`, `FR-ADHOC-020`, `AC-ADHOC-020-04`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_judge_phase`
- **Given**: `next_action` is `skip_refactor` on the already-exists path.
- **When**: The gate checks evidence quotes against HEAD contents of the named paths.
- **Then**: Matching HEAD test and impl quotes pass, and a named test file absent on disk fails closed without covering GH #63.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Allow empty evidence only when no AC-PLAN tokens exist and keep non-TDD judge ungated**
- **Source Outline**: `AO-020`
- **Upstream Traceability**: `US-020-03`, `FR-ADHOC-020`, `AC-ADHOC-020-04`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:constraints`
- **Given**: The injected plan contract has no `AC-PLAN-*` tokens, or the call is EXECUTE or IMMEDIATE judge.
- **When**: TDD judge YAML has empty `evidence`, or EXECUTE/IMMEDIATE judge runs.
- **Then**: Empty evidence is accepted for no-AC tasks; EXECUTE and IMMEDIATE judge stay ungated; auto and manual judge prompts require `evidence` and omit "Default to COMPLIANCE_PASS" and "When in doubt, pass."
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: Own first-class `evidence` on `HandoverManifest`.
  - **Current State**: `HandoverManifest` has `model_config = {"extra": "allow"}`. Extra keys parse into `model_extra`. There is no `evidence` field the gate can read.
  - **Changes Required**: Add nested citation items with `ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`. Keep `extra: allow`. Default `evidence` to empty or omitted so non-judge phases may skip it. `impl_path` and `impl_quote` may be empty on the empty-GREEN edge.
  - **Integration Surface**: `AgentBackend.parse_output`; `_run_judge_phase` reads `manifest.evidence`.
- **src/deviate/core/judge_evidence.py**: Pure mechanical gate (new sibling).
  - **Current State**: File does not exist. Diff assembly and plan injection live in `_run_judge_phase` / `_resolve_spec_md`.
  - **Changes Required**: Extract `AC-PLAN-NNN` tokens only from the injected `<authoritative_acceptance_contract source="plan.md">` block. Map injected-diff paths from `diff --git a/... b/...` and `+++ b/...` headers to hunk text. Substring-check quotes. Enforce the uniqueness floor (≥ 12 non-whitespace characters, or the full added line if shorter). Return runner-authored feedback on fail. No AST, no extra git, no agent call.
  - **Integration Surface**: `_run_judge_phase` after `_invoke_agent` and `_coerce_judge_action`, before forward PASS routes.
- **src/deviate/cli/micro.py**: Run the gate on TDD `_run_judge_phase` only.
  - **Current State**: `_run_judge_phase` builds `<diff>` from RED parent to HEAD plus dirty and untracked hunks, then accepts `COMPLIANCE_PASS` / `continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff` with no citation check. `_run_execute_phase` has a separate judge path.
  - **Changes Required**: After the agent returns, if the coerced action is a forward PASS route, run the evidence helper against the same injected diff and the plan contract from `_resolve_spec_md`. On fail, rewrite the action to `revert_to_red` and inject runner-authored feedback (same family as `JUDGE_AGENT_NO_FEEDBACK`). Skip the gate on `COMPLIANCE_VIOLATION` / `revert_to_red` / `revert_before`. Do not call the gate from EXECUTE. `proceed_to_refactor_no_diff` requires `test_quote` only. `skip_refactor` already-exists may quote HEAD file contents; a missing named test file fails. No `AC-PLAN-*` tokens allows empty evidence.
  - **Integration Surface**: `_coerce_judge_action`; `_judge_feedback_from_manifest`; `_git_env()`; `_run_execute_phase` stays ungated.
- **src/deviate/prompts/auto/judge.md**: Require `evidence` in the YAML schema and drop default-pass language.
  - **Current State**: STEP_3 and `<constraints>` say "Default to COMPLIANCE_PASS" and "When in doubt, pass." Empty-diff edge emits `COMPLIANCE_PASS` with note `NO_DIFF`. Schema has no `evidence` key.
  - **Changes Required**: Add the `evidence` list to both YAML schema blocks. Instruct the agent to cite every injected `AC-PLAN-NNN`. Empty evidence is not a pass when AC-PLAN tokens exist. Remove "Default to COMPLIANCE_PASS" and "When in doubt, pass." Update the empty-diff row to the empty-GREEN `test_quote` rule.
  - **Integration Surface**: `_build_auto_prompt("judge", ...)`.
- **src/deviate/prompts/commands/deviate-judge.md**: Same schema and constraint edits on the manual skill.
  - **Current State**: Approval YAML has no `evidence`. Default-pass wording is present in the approval path.
  - **Changes Required**: Mirror the auto schema and the no-default-pass constraint. Keep EXECUTE out of this skill.
  - **Integration Surface**: `deviate setup` install mirror of the manual skill.
- **tests/unit/test_core/test_agent.py**: Pin first-class `evidence` parse and round-trip.
  - **Current State**: `TestHandoverManifestModel` pins extra-allow and `files` round-trip. No `evidence` pin.
  - **Changes Required**: YAML with citation items round-trips on `HandoverManifest.evidence`. Unknown extra keys still parse. Omitted `evidence` stays valid for non-judge phases.
  - **Integration Surface**: `HandoverManifest`.
- **tests/unit/test_micro/test_judge.py**: Pin gate fail-closed and pass-open plus prompt text.
  - **Current State**: Many `_run_judge_phase` tests mock `_invoke_agent` with bare `COMPLIANCE_PASS` and mock `_build_auto_prompt` to `"test prompt"` (no AC-PLAN tokens). Prompt tests require `COMPLIANCE_PASS` vocabulary, not default-pass strings.
  - **Changes Required**: With a plan contract that lists `AC-PLAN-001`, PASS with empty/missing/partial evidence, hallucinated paths, empty quotes, short quotes, or quotes from the wrong file hunk does not COMPLETE and forces `revert_to_red`. Matching quotes pass. `proceed_to_refactor_no_diff` requires `test_quote` only. `skip_refactor` already-exists accepts HEAD quotes and fails when the test file is missing. No-AC-PLAN empty evidence is allowed. Auto judge prompt contains an `evidence` schema key and does not contain "Default to COMPLIANCE_PASS" or "When in doubt, pass." Use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for git. Mock `_invoke_agent`. Do not call un-mocked `_run_pytest`. Keep existing mocked no-AC-PLAN PASS tests green.
  - **Integration Surface**: `_run_judge_phase`; `_build_auto_prompt`; `src/deviate/core/judge_evidence.py`.
- **tests/unit/test_core/test_judge_evidence.py**: Unit-test the helper without an agent.
  - **Current State**: File does not exist.
  - **Changes Required**: Feed plan-contract text, injected-diff text, evidence list, `next_action`, and optional HEAD contents. Pin token extract, path map, substring match, uniqueness floor, empty-GREEN impl-quote skip, and already-exists HEAD fallback.
  - **Integration Surface**: `src/deviate/core/judge_evidence.py`.
- **tests/unit/test_micro/test_green.py**: Align empty-GREEN comments with the `test_quote` rule.
  - **Current State**: Class and test docstrings say the JUDGE edge table emits `COMPLIANCE_PASS` with note `NO_DIFF` for empty diffs.
  - **Changes Required**: Update comments and any assertion that treats empty-GREEN as bare `COMPLIANCE_PASS` + `NO_DIFF` so they match the dirty-diff `test_quote` rule. Do not change GREEN routing.
  - **Integration Surface**: JUDGE prompt edge table; `_run_green_phase` still hands empty PASS to JUDGE.
- **specs/DeviaTDD-api.md**: Document `HandoverManifest.evidence` and the TDD-only PASS gate.
  - **Current State**: JUDGE `next_action` routing table describes forward PASS routes with no citation gate.
  - **Changes Required**: Document the nested `evidence` field. Document the mechanical gate in `_run_judge_phase` before forward PASS routes. State EXECUTE/IMMEDIATE stay ungated. Same commit as the implementation.
  - **Integration Surface**: `specs/DeviaTDD-architecture.md` Judge bullet.
- **specs/DeviaTDD-architecture.md**: Record the TDD-only mechanical PASS gate.
  - **Current State**: "The Judge" evaluates the RED-parent-to-HEAD diff with no runner citation check.
  - **Changes Required**: State that TDD `_run_judge_phase` rejects `COMPLIANCE_PASS` unless evidence quotes match the injected diff (or HEAD on the already-exists edge). Same commit as the API doc.
  - **Integration Surface**: `specs/DeviaTDD-api.md` routing table.
- **CHANGELOG.md**: Record the user-visible PASS contract change.
  - **Current State**: `[Unreleased]` has no evidence-gate bullet.
  - **Changes Required**: Append one `[Unreleased]` bullet: TDD JUDGE `COMPLIANCE_PASS` requires mechanical diff evidence; unmatched PASS cannot COMPLETE.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: First-class `evidence` field
  - **Files**: `src/deviate/core/agent.py`, `tests/unit/test_core/test_agent.py`
  - **Approach**: Add a nested model (or typed dict) with `ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`. Default `evidence` so RED/GREEN YAML without the key still parses. Keep `extra: allow`.
  - **Verification**: `uv run pytest tests/unit/test_core/test_agent.py -q --tb=short` — round-trip plus extra-key pin.
- **Phase 2**: Pure evidence helper
  - **Files**: `src/deviate/core/judge_evidence.py`, `tests/unit/test_core/test_judge_evidence.py`
  - **Approach**: Parse `AC-PLAN-\d{3}` only from the plan-contract block, not from `judge.md`. Split the injected diff by file headers. Require every token to have a citation. Path must appear in those headers unless `next_action == skip_refactor` and HEAD contents are supplied. Quote must be an exact substring of that file's hunk (or HEAD text on that edge). Uniqueness floor: ≥ 12 non-whitespace characters, or the full added line if shorter. `proceed_to_refactor_no_diff` skips impl quote. Missing named test file fails.
  - **Verification**: `uv run pytest tests/unit/test_core/test_judge_evidence.py -q --tb=short` — no agent, no git network.
- **Phase 3**: Wire the gate into TDD `_run_judge_phase`
  - **Files**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_judge.py`
  - **Approach**: After `_invoke_agent` and `_coerce_judge_action`, if the action is a forward PASS route, call the helper with the already-built `diff`, `_resolve_spec_md` text, `manifest.evidence`, and `next_action`. On fail, set action to `revert_to_red`, attach runner-authored feedback, and take the existing rejection path so the task does not COMPLETE. Do not gate `COMPLIANCE_VIOLATION`. Do not call the helper from `_run_execute_phase`. Seed RED+GREEN commits in `tmp_git_repo` with `_git_env()`. Mock `_invoke_agent`. Do not call un-mocked `_run_pytest`.
  - **Verification**: `uv run pytest tests/unit/test_micro/test_judge.py -q --tb=short` — fail-closed, pass-open, empty-GREEN, already-exists, no-AC-PLAN.
- **Phase 4**: Prompts, green comments, specs, changelog
  - **Files**: `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/commands/deviate-judge.md`, `tests/unit/test_micro/test_green.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Add `evidence` to the YAML schema. Remove "Default to COMPLIANCE_PASS" and "When in doubt, pass." Replace the empty-diff `NO_DIFF` pass row with the dirty-diff `test_quote` rule. Update GREEN docstrings that cite that row. Document the TDD-only gate in API and architecture in the same implementation commit. Append the `[Unreleased]` bullet.
  - **Verification**: Prompt pins in `tests/unit/test_micro/test_judge.py`. Same-commit spec and changelog review against constitution §5 and AGENTS.md Spec Alignment.

## Data Flow Analysis
- **Inputs**: Judge YAML (`verdict`, `next_action`, `evidence`), injected `<diff>` already built in `_run_judge_phase`, plan contract from `_resolve_spec_md`, optional HEAD file bytes on `skip_refactor`.
- **Transform**: Helper extracts `AC-PLAN-NNN` tokens from the plan-contract block. It maps diff headers to hunk text. It checks each citation path and exact-substring quote against that map (or HEAD on the already-exists edge). Uniqueness floor is character count on the quote, or the full added line when that line is shorter than 12 non-whitespace characters.
- **Pass output**: Forward routes stay as coerced: `continue_refactor`, `skip_refactor`, `proceed_to_refactor_no_diff`, or legacy PASS.
- **Fail output**: Action becomes `revert_to_red`. Runner-authored feedback names the missing token, bad path, or failed quote. Existing rollback plus GREEN train path runs. The task does not COMPLETE.
- **Storage**: No ledger schema change. `HandoverManifest.evidence` is request-scoped YAML only.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `AC-PLAN-NNN` in `judge.md` is treated as a required token | High | High | Extract tokens only from `<authoritative_acceptance_contract source="plan.md">`, not from the prompt template. |
| Existing mocked PASS tests break because `"test prompt"` has no evidence | Medium | High | No-AC-PLAN empty evidence stays legal. Keep `_build_auto_prompt` mocks without a plan contract. |
| Empty-GREEN `NO_DIFF` PASS still COMPLETEs with no test quote | High | Medium | Gate `proceed_to_refactor_no_diff` on dirty-diff `test_quote`. Update prompt edge table and `test_green.py` comments. |
| Already-exists HEAD fallback COMPLETEs with no tests on disk (GH #63) | High | Medium | Missing named test file fails closed. Do not use HEAD fallback to paper over GH #63. |
| Quote uniqueness floor rejects a short but unique added line | Medium | Medium | Accept the full added line when it is shorter than 12 non-whitespace characters. Reject generic `assert True`. |
| Gate applied to EXECUTE / IMMEDIATE | High | Low | Call the helper only from TDD `_run_judge_phase`. Leave `_run_execute_phase` unchanged. |
| Gate uses AST or a second agent call and blows L_max | Medium | Low | Path plus exact substring only on the already-built diff. No extra git network. No extra agent call. |
| Tests inherit parent git config or call un-mocked `_run_pytest` | Medium | Medium | Every test git call uses `cwd=<tmp_git_repo>` and `env=_git_env()`. Production uses `git_env()` / `_git_env()`. Mock `_invoke_agent` and `_run_pytest`. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: subprocess (existing git diff in `_run_judge_phase`), file paths (diff headers and optional HEAD reads of named evidence paths), YAML parse (`HandoverManifest`).
Negative tests: hallucinated `test_path` / `impl_path` fail; empty quotes fail; quotes below the uniqueness floor fail; quote present only in a different file hunk fails; partial AC coverage fails; named test file absent on disk fails on `skip_refactor`; EXECUTE judge is not gated.
Constraints: no new dependencies; no hardcoded secrets; path matching uses injected-diff headers, not an unbounded filesystem walk; HEAD read is limited to paths named in evidence; do not revert operator-local `.deviate/config.toml`; do not fatten GREEN; do not call un-mocked `_run_pytest`.

## Integration Points
- **`HandoverManifest.evidence`**: First-class citation list. Nested keys `ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`. Extra keys remain allowed.
- **`_run_judge_phase` injected `<diff>`**: `git diff <red>^..HEAD` plus dirty `git diff HEAD` plus untracked `--no-index`. The gate consumes this string; it does not rebuild it.
- **`_resolve_spec_md`**: Source of `<authoritative_acceptance_contract source="plan.md">` for `AC-PLAN-NNN` tokens.
- **`_coerce_judge_action`**: Gate runs after coerce on forward PASS routes only. Violation routes skip the gate.
- **`JUDGE_AGENT_NO_FEEDBACK` family**: Evidence failure uses runner-authored feedback and `revert_to_red` so the task cannot COMPLETE.
- **`_run_execute_phase`**: Separate judge path. This issue does not add the gate there.
- **Auto/manual judge prompts**: Schema requires `evidence`. Default-pass and when-in-doubt-pass lines are removed.

## Constitutional Alignment
- **Architecture**: Micro JUDGE stays the compliance gate in the four-layer model (constitution §1). The runner now enforces GREEN-vs-plan citations mechanically. This plan does not skip a layer and does not add Product-layer work.
- **Testing**: pytest under `tests/` with `tmp_git_repo` and `_git_env()` (constitution §3). JUDGE verifies GREEN against the plan contract. Coverage target ≥ 80%. Full suite stays under 30s. No un-mocked `_run_pytest`.
- **Git Isolation**: Work stays on `feat/adhoc/020-judge-compliance-pass-evidence`. Production git uses `_git_env()`. This issue does not delete branches.
- **Product Layer**: Issue `flow_refs` is `[]`. Downstream artifacts keep empty flow references. This plan does not author or sync Product-layer flows.
