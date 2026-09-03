# Implementation Tasks: `feat/adhoc/020-judge-compliance-pass-evidence`

## Phase 1: First-class `HandoverManifest.evidence`
**Goal**: Judge YAML citations round-trip on `HandoverManifest.evidence` so the gate can read them. Extra keys still parse (constitution §1 Four-Layer Architecture; constitution §3 Testing Protocols).

### Tasks

- TSK-020-01: Parse first-class evidence items on `HandoverManifest`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_core/test_agent.py -q --tb=short`
  - **Estimated Time**: 45 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/unit/test_core/test_agent.py`
  - **Rationale**: US-020-01 / `AC-PLAN-001` need a first-class `evidence` list the gate can read. `HandoverManifest` today only allows extra keys into `model_extra`. `test_agent.py` already pins extra-allow and `files` round-trip. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: In `tests/unit/test_core/test_agent.py`, parse YAML with `evidence` items (`ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`) plus one unknown extra key. Assert `HandoverManifest.evidence` round-trips those items. Assert the extra key still parses. Assert omitted `evidence` still parses for non-judge phases.
    - **Green**: In `src/deviate/core/agent.py`, add a nested citation model (or typed dict) with `ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`. Add `evidence` on `HandoverManifest` defaulting to empty or omitted. Keep `model_config = {"extra": "allow"}`. Allow empty `impl_path` / `impl_quote` for the empty-GREEN edge.
    - **Refactor**: Keep one nested citation type. Do not require `evidence` on RED or GREEN YAML.
    - **Edge Cases**: Unknown extra keys stay legal. Empty `evidence: []` parses. Missing `evidence` key parses as default empty.
    - **Acceptance**: `HandoverManifest.evidence` is readable after parse. Extra-allow pin still passes. Constitution §3 pytest under `tests/` exits 0.

---

## Phase 2: Pure evidence helper
**Goal**: A path-plus-substring gate extracts `AC-PLAN-NNN` from the plan-contract block, maps injected-diff hunks, and returns runner-authored fail feedback with no agent and no extra git (constitution §3 Testing Protocols).

### Tasks

- TSK-020-02: Enforce citation path, quote, and AC coverage in `judge_evidence`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `pytest tests/unit/test_core/test_judge_evidence.py -q --tb=short`
  - **Estimated Time**: 75 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/core/judge_evidence.py`
    - `tests/unit/test_core/test_judge_evidence.py`
  - **Rationale**: US-020-01 through US-020-03 / `AC-PLAN-002` through `AC-PLAN-006` need a unit-testable gate before `_run_judge_phase` wiring. Tokens come only from `<authoritative_acceptance_contract source="plan.md">`, not from `judge.md`. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: In `tests/unit/test_core/test_judge_evidence.py`, feed plan-contract text, injected-diff text, evidence list, `next_action`, and optional HEAD contents. Pin fail-closed for missing, empty, or partial `evidence`; path absent from `diff --git a/... b/...` and `+++ b/...` headers; empty quote; quote below the uniqueness floor; quote that is not an exact substring of the named file hunk (`AC-PLAN-002`). Pin pass-open when every injected `AC-PLAN-NNN` has matching test and impl quotes (`AC-PLAN-003`). Pin `proceed_to_refactor_no_diff` requiring `test_quote` only (`AC-PLAN-004`). Pin `skip_refactor` HEAD quotes pass and a missing named test file fails (`AC-PLAN-005`). Pin empty evidence legal when no `AC-PLAN-*` tokens exist (`AC-PLAN-006`). Do not spawn an agent. Do not run git.
    - **Green**: Add `src/deviate/core/judge_evidence.py` that extracts `AC-PLAN-\d{3}` only from the plan-contract block, maps injected-diff paths to hunk text, substring-checks quotes, and enforces ≥ 12 non-whitespace characters or the full added line if shorter. Return runner-authored feedback on fail. Skip impl quote when `next_action` is `proceed_to_refactor_no_diff`. On `skip_refactor`, check quotes against supplied HEAD contents; fail if the named test file is missing. Accept empty evidence when no tokens exist.
    - **Refactor**: Keep path plus exact substring only. No AST. No extra git. No agent call.
    - **Edge Cases**: `AC-PLAN-NNN` text in a prompt template is not a required token. Generic `assert True` fails the uniqueness floor. Quote present only in a different file hunk fails. Hallucinated paths fail.
    - **Acceptance**: Helper tests cover fail-closed, pass-open, empty-GREEN, already-exists, and no-AC-PLAN. No network. No agent.
  - **Dependency**: TSK-020-01

---

## Phase 3: TDD `_run_judge_phase` evidence gate
**Goal**: Forward `COMPLIANCE_PASS` routes run the helper against the already-built `<diff>`. Unmatched PASS rewrites to `revert_to_red` and does not COMPLETE. EXECUTE stays ungated (constitution §1 Micro-Layer Scope; constitution §3 JUDGE verifies GREEN).

### Tasks

- TSK-020-03: Rewrite unmatched TDD PASS to `revert_to_red` in `_run_judge_phase`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/unit/test_micro/test_judge.py -q --tb=short`
  - **Estimated Time**: 90 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_judge.py`
  - **Rationale**: US-020-01 / `AC-PLAN-002` require unmatched PASS cannot COMPLETE. US-020-02 / `AC-PLAN-003` require matching quotes keep the forward route. US-020-03 / `AC-PLAN-004` through `AC-PLAN-006` require empty-GREEN, already-exists, no-AC-PLAN, and ungated EXECUTE. `_run_judge_phase` already builds `<diff>` from `git diff <red>^..HEAD` plus dirty `git diff HEAD` and untracked `--no-index`. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_judge.py`, seed RED plus GREEN commits in `tmp_git_repo` with `cwd=<tmp_git_repo>` and `env=_git_env()`. Mock `_invoke_agent`. Do not call un-mocked `deviate.cli.micro._run_pytest`. With a plan contract that lists `AC-PLAN-001`, assert `verdict: COMPLIANCE_PASS` with missing, empty, or partial `evidence`, a hallucinated path, an empty quote, a short quote, or a wrong-file quote does not COMPLETE and forces `revert_to_red` with runner-authored feedback in the `JUDGE_AGENT_NO_FEEDBACK` family (`AC-PLAN-002`). Assert matching quotes keep PASS on the existing forward route (`AC-PLAN-003`). Assert `proceed_to_refactor_no_diff` accepts a dirty-diff `test_quote` and omits `impl_quote` (`AC-PLAN-004`). Assert `skip_refactor` already-exists accepts HEAD quotes and fails when the named test file is absent (`AC-PLAN-005`). Assert no-AC-PLAN empty evidence still COMPLETEs so existing `"test prompt"` mocks stay green (`AC-PLAN-006`). Assert `_run_execute_phase` is not gated (`AC-PLAN-006`).
    - **Green**: In `_run_judge_phase`, after `_invoke_agent` and `_coerce_judge_action`, if the action is a forward PASS route, call the Phase 2 helper with the already-built `diff`, `_resolve_spec_md` text, `manifest.evidence`, and `next_action`. On fail, set action to `revert_to_red`, attach runner-authored feedback via `_judge_feedback_from_manifest` family, and take the existing rejection path. Skip the gate on `COMPLIANCE_VIOLATION` / `revert_to_red` / `revert_before`. Do not call the helper from `_run_execute_phase`. On `skip_refactor`, read HEAD contents only for paths named in evidence.
    - **Refactor**: Consume the injected `<diff>` string. Do not rebuild it. Do not add a second agent call.
    - **Edge Cases**: Keep existing mocked no-AC-PLAN PASS tests green. Do not paper over GH #63 with HEAD fallback when the test file is missing. Do not revert operator-local `.deviate/config.toml`. Production git uses `_git_env()`.
    - **Acceptance**: Unmatched TDD PASS cannot COMPLETE. Matching quotes follow the existing forward route. EXECUTE judge stays ungated.
  - **Dependency**: TSK-020-02

---

## Phase 4: Judge prompts, GREEN comments, specs, changelog
**Goal**: Auto and manual judge schemas require `evidence` and drop default-pass language. API, architecture, and `CHANGELOG.md` `[Unreleased]` record the TDD-only gate in the same change set (constitution §5 Definition of Done; AGENTS.md Spec Alignment).

### Tasks

- TSK-020-04: Require `evidence` in judge prompts and document the TDD-only PASS gate
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/unit/test_micro/test_judge.py tests/unit/test_micro/test_green.py -q --tb=short`
  - **Estimated Time**: 45 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/commands/deviate-judge.md`
    - `tests/unit/test_micro/test_judge.py`
    - `tests/unit/test_micro/test_green.py`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: US-020-03 / `AC-PLAN-006` require auto and manual judge prompts to list `evidence` and omit "Default to COMPLIANCE_PASS" and "When in doubt, pass." Empty-GREEN comments in `test_green.py` must match the dirty-diff `test_quote` rule. Constitution §5 and AGENTS.md Spec Alignment require API, architecture, and CHANGELOG in the same implementation commit. `**Flow References**: []` matches plan.md `## Product Layer Anchors`.
  - **Details**:
    - **Implementation**: In `src/deviate/prompts/auto/judge.md` and `src/deviate/prompts/commands/deviate-judge.md`, add the `evidence` list to both YAML schema blocks. Instruct the agent to cite every injected `AC-PLAN-NNN`. State that empty evidence is not a pass when AC-PLAN tokens exist. Remove "Default to COMPLIANCE_PASS" and "When in doubt, pass." Replace the empty-diff `NO_DIFF` pass row with the dirty-diff `test_quote` / `proceed_to_refactor_no_diff` rule. Keep EXECUTE out of the manual skill.
    - **Implementation**: In `tests/unit/test_micro/test_judge.py`, pin that the auto judge prompt contains an `evidence` schema key and does not contain "Default to COMPLIANCE_PASS" or "When in doubt, pass." Invert any existing pin that required those strings.
    - **Implementation**: In `tests/unit/test_micro/test_green.py`, update class and test comments that say the JUDGE edge table emits `COMPLIANCE_PASS` with note `NO_DIFF` for empty diffs so they match the dirty-diff `test_quote` rule. Do not change GREEN routing.
    - **Implementation**: In `specs/DeviaTDD-api.md`, document nested `HandoverManifest.evidence` and the mechanical gate in `_run_judge_phase` before forward PASS routes. State EXECUTE/IMMEDIATE stay ungated. In `specs/DeviaTDD-architecture.md`, state that TDD `_run_judge_phase` rejects `COMPLIANCE_PASS` unless evidence quotes match the injected diff or HEAD on the already-exists edge.
    - **Implementation**: Append one `CHANGELOG.md` `[Unreleased]` bullet: TDD JUDGE `COMPLIANCE_PASS` requires mechanical diff evidence; unmatched PASS cannot COMPLETE.
    - **Refactor**: Keep auto and manual schema wording aligned. Do not fatten GREEN.
    - **Edge Cases**: Do not author or sync Product-layer flows. Do not apply the gate to EXECUTE in docs. Do not revert operator-local `.deviate/config.toml`.
    - **Acceptance**: Prompt pins pass. GREEN comments match the `test_quote` rule. API, architecture, and CHANGELOG describe the TDD-only gate.
  - **Dependency**: TSK-020-03

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (`TSK-020-01`) -> Phase 2 (`TSK-020-02`) -> Phase 3 (`TSK-020-03`) -> Phase 4 (`TSK-020-04`)

**Critical Dependency Chains**:
- TSK-020-01 must precede TSK-020-02 (`HandoverManifest.evidence` is the citation input type)
- TSK-020-02 must precede TSK-020-03 (`_run_judge_phase` calls the helper)
- TSK-020-03 must precede TSK-020-04 (docs and prompts describe the shipped gate)

**Risk Hotspots**:
- `AC-PLAN-NNN` in `judge.md` treated as a required token.
- Existing mocked PASS tests break because `"test prompt"` has no evidence.
- Empty-GREEN `NO_DIFF` PASS still COMPLETEs with no `test_quote`.
- Already-exists HEAD fallback COMPLETEs with no tests on disk (GH #63).
- Gate applied to EXECUTE / IMMEDIATE.
- Un-mocked `deviate.cli.micro._run_pytest` blowing the 30s suite budget.
- Tests inherit parent git config instead of `cwd=<tmp_git_repo>` + `env=_git_env()`.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_micro/test_judge.py` (Phase 3 gate pins, Phase 4 prompt pins). `src/deviate/cli/micro.py` stays Phase 3 only. `src/deviate/core/agent.py` stays Phase 1 only. `src/deviate/core/judge_evidence.py` stays Phase 2 only.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/020-judge-compliance-pass-evidence.md` (frontmatter field: `flow_refs`)
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
