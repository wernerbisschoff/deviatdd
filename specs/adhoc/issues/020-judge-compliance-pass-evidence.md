---
title: "TDD JUDGE COMPLIANCE_PASS Requires Mechanical Diff Evidence"
labels: [enhancement, adhoc, vertical-slice, judge, tdd]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-020
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/020-judge-compliance-pass-evidence.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/agent.py::HandoverManifest` — TARGET: add a first-class `evidence` field (list of per-AC citations). Extra-allow stays. Nested item shape: `ac`, `test_path`, `test_quote`, `impl_path`, `impl_quote`.
  - `src/deviate/cli/micro.py::_run_judge_phase` — TARGET: after the agent returns, before accepting `COMPLIANCE_PASS` / forward routes, run a mechanical evidence gate against the same injected `<diff>` already built in this function (`git diff <red>^..HEAD` plus dirty `git diff HEAD` and untracked `--no-index` hunks). Fail-closed: missing/empty/partial evidence, hallucinated paths, empty or non-substring quotes, or quotes below the uniqueness floor rewrite PASS into `revert_to_red` with runner-authored feedback (same family as `JUDGE_AGENT_NO_FEEDBACK`).
  - Helper (prefer next to `_run_judge_phase` or a small sibling in `src/deviate/cli/micro.py` / `src/deviate/core/`) — TARGET: extract AC-PLAN tokens from the injected authoritative plan contract; map diff paths to hunk text; substring-check quotes. Keep it unit-testable without spawning an agent.
  - `src/deviate/prompts/auto/judge.md` — TARGET: require `evidence` in the YAML schema; drop "Default to COMPLIANCE_PASS" and "When in doubt, pass."; empty evidence is not a pass when AC-PLAN tokens exist.
  - `src/deviate/prompts/commands/deviate-judge.md` — TARGET: same schema and constraint edits on the manual skill.
  - `tests/test_core/test_agent.py` — TARGET: pin first-class `evidence` parse/round-trip.
  - `tests/test_micro/test_judge.py` — TARGET: pin gate fail-closed and pass-open; pin prompt schema/constraint text.
  - `tests/test_micro/test_green.py` — TARGET: update comments/assertions that currently treat the JUDGE edge table as bare `COMPLIANCE_PASS` + `NO_DIFF` for empty diffs, so they match the empty-GREEN `test_quote` rule.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document the evidence field and the TDD-only mechanical PASS gate in the same implementation commit.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible PASS contract change.
- **Classification for plan/tasks**: production Python with observable fail-to-pass behavior (a PASS YAML without matching quotes cannot COMPLETE). Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices; this gate is TDD judge only.
- **Upstream Evidence**:
  - `_run_judge_phase` already injects `<diff>` spanning RED parent to HEAD plus dirty/untracked (`src/deviate/cli/micro.py`).
  - `_resolve_spec_md` already wraps `plan.md` in `<authoritative_acceptance_contract source="plan.md">`.
  - `HandoverManifest.model_config = {"extra": "allow"}` — extra fields parse today but are not required or checked.
  - Auto judge constraints still say default PASS / when in doubt pass (`src/deviate/prompts/auto/judge.md`).
  - GH #63 (`already_satisfied` can COMPLETE with no tests on disk) is related but out of scope.

## The Problem Contract

JUDGE is the only phase that decides whether GREEN's code satisfies the plan. Tests running is already mechanical (RED fail / GREEN pass). Spec-vs-code is not: a judge that never looks at the injected tests or production hunks can still emit `COMPLIANCE_PASS` and COMPLETE the task. Operators need a runner-enforced citation gate so PASS is illegal unless the YAML points at real test and impl text from the injected diff.

## Scope Boundaries

### Hard Inclusions

- First-class `HandoverManifest.evidence` list. Per injected `AC-PLAN-NNN`:

  ```yaml
  evidence:
    - ac: AC-PLAN-001
      test_path: tests/example.py
      test_quote: "assert increment(2) == 3"
      impl_path: src/example.py
      impl_quote: "return n + 1"
  ```

- Mechanical gate in `_run_judge_phase` **before** accepting PASS / `continue_refactor` / `skip_refactor` / `proceed_to_refactor_no_diff`.
- Reject PASS (force `revert_to_red` with runner-authored feedback; do not COMPLETE) when:
  - the plan contract has `AC-PLAN-NNN` tokens and `evidence` is missing, empty, or missing a token;
  - `test_path` or `impl_path` is not a path that appears in the injected `<diff>` (except the documented already-exists HEAD-contents edge);
  - `test_quote` / `impl_quote` is empty, or is not an exact substring of that file's hunk in the injected diff (or HEAD contents on the already-exists edge);
  - quotes are below the uniqueness floor (≥ 12 non-whitespace characters, or the full added line if shorter).
- Hallucinated paths and invented snippets fail closed.
- Prompt schema requires `evidence`. Drop "Default to COMPLIANCE_PASS" and "When in doubt, pass." Empty evidence is not a pass when AC-PLAN tokens exist.
- Narrow edges:
  - `proceed_to_refactor_no_diff` / documented empty-GREEN mechanical path: no impl quote required; still require a `test_quote` from the uncommitted/RED test in the dirty diff.
  - `skip_refactor` + already-exists: quotes may come from HEAD file contents named in evidence, not only the diff. Still require both a test quote and an impl quote. No tests on disk still fails (do not paper over GH #63).
  - Enabling/infra tasks with no `AC-PLAN-*`: evidence may be empty; do not invent ACs.
- Gate is TDD judge only (`_run_judge_phase` on TDD). EXECUTE / IMMEDIATE / DIRECT judge paths are unchanged.
- Update API + architecture in the same implementation commit; CHANGELOG `[Unreleased]` bullet.
- Tests use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>` for any git; do not call un-mocked `_run_pytest`.

### Defensive Exclusions

- Do **not** add semantic scanners, AST "understanding," or LLM self-check loops. The gate is path + exact-substring only.
- Do **not** fatten GREEN or change task grain / shard rules.
- Do **not** change how adhoc/plan picks TDD vs IMMEDIATE.
- Do **not** apply this gate to EXECUTE / IMMEDIATE / DIRECT.
- Do **not** use the already-exists HEAD-contents edge to COMPLETE when no tests exist on disk (GH #63 stays separate).
- Do **not** keep "Default to COMPLIANCE_PASS" / "When in doubt, pass" in auto or manual judge prompts.
- Do **not** treat empty evidence as PASS when the injected plan lists `AC-PLAN-*` tokens.
- Do **not** revert operator-local `.deviate/config.toml` (backend=pi, transport=cli, pi_rpc=false, timeout=1800, models.default=grok-4.6).
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** author or synchronize Product-layer flows; `flow_refs: []`.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-020`
- **Acceptance Criteria Tokens**: `AC-ADHOC-020-01`, `AC-ADHOC-020-02`, `AC-ADHOC-020-03`, `AC-ADHOC-020-04`
- **Data Model Entities**: `HandoverManifest.evidence` (new first-class field; nested citation items). No ledger schema change.
- **Spec Source Anchors**:
  - `src/deviate/core/agent.py::HandoverManifest`
  - `src/deviate/cli/micro.py::_run_judge_phase`
  - `src/deviate/cli/micro.py::_resolve_spec_md`
  - `src/deviate/prompts/auto/judge.md`
  - `src/deviate/prompts/commands/deviate-judge.md`
  - `specs/constitution.md` §3 Testing Protocols (JUDGE verifies GREEN) and §5 Definition of Done (Judge phase passed)

## User Stories Ledger

- **US-020-01**: As a DeviaTDD operator, I want `COMPLIANCE_PASS` rejected when the judge YAML has no matching quotes from the injected RED+GREEN diff so a toy GREEN cannot COMPLETE. *(Ref: FR-ADHOC-020)*
- **US-020-02**: As a DeviaTDD operator, I want a judge that cites the real RED test line and the real impl line in `evidence` to PASS so honest compliance still ships. *(Ref: FR-ADHOC-020)*
- **US-020-03**: As a DeviaTDD operator, I want the documented empty-GREEN and already-exists edges to stay legal without papering over missing tests on disk. *(Ref: FR-ADHOC-020)*

## Acceptance Outline

- **AO-020** *(Ref: AC-ADHOC-020-01, US-020-01)*: Manifest parses first-class evidence.
  - **Happy Path**: YAML `evidence` with `ac` / `test_path` / `test_quote` / `impl_path` / `impl_quote` round-trips on `HandoverManifest`; unknown extra keys still parse.
  - **Error Category**: Dropping evidence into `model_extra` only, without a first-class field the gate can read, fails the pin.
  - **Boundary Category**: `extra: allow` remains; non-judge phases may omit `evidence`.

- **AO-020** *(Ref: AC-ADHOC-020-02, US-020-01)*: PASS without matching citations cannot COMPLETE.
  - **Happy Path**: Plan lists `AC-PLAN-001`; judge YAML is `verdict: COMPLIANCE_PASS` with empty/missing `evidence`, or a quote that does not appear in the injected `<diff>`: runner does not COMPLETE; it forces `revert_to_red` with runner-authored feedback (same abort family as `JUDGE_AGENT_NO_FEEDBACK`).
  - **Error Category**: Hallucinated `test_path` / `impl_path` not present in the diff, empty quotes, or quotes shorter than the uniqueness floor fail closed even if tests already passed.
  - **Boundary Category**: Partial coverage (one AC cited, another omitted) is a fail, not a partial pass.

- **AO-020** *(Ref: AC-ADHOC-020-03, US-020-02)*: Matching quotes allow PASS.
  - **Happy Path**: Evidence `test_quote` is an exact substring of the named test file's hunk in the injected diff and `impl_quote` is an exact substring of the named impl hunk; `COMPLIANCE_PASS` proceeds on existing forward routes.
  - **Error Category**: Quote present in a *different* file's hunk than the named path fails.
  - **Boundary Category**: Uniqueness floor: ≥ 12 non-whitespace chars, or the full added line if that line is shorter.

- **AO-020** *(Ref: AC-ADHOC-020-04, US-020-03)*: Narrow edges, prompt, docs.
  - **Happy Path**: `proceed_to_refactor_no_diff` accepts evidence with a dirty/RED `test_quote` and no impl quote. `skip_refactor` + already-exists accepts quotes copied from HEAD file contents for both test and impl. Tasks whose injected plan has no `AC-PLAN-*` accept empty evidence. Auto/manual judge prompts require `evidence` and no longer instruct default-pass / when-in-doubt-pass.
  - **Error Category**: Using the already-exists edge to PASS when the named test file is absent on disk fails. EXECUTE/IMMEDIATE judge is not gated by this change.
  - **Boundary Category**: API/architecture docs and CHANGELOG `[Unreleased]` record the TDD-only mechanical PASS gate in the same commit.

## Edge Cases and Boundaries

- **Empty injected diff with AC-PLAN tokens**: not a PASS. Empty-GREEN must still cite the uncommitted/RED test via dirty-diff `test_quote` (`proceed_to_refactor_no_diff`).
- **Quote uniqueness**: `assert True` is too short/generic; require ≥ 12 non-whitespace chars or the entire added line.
- **Path matching**: compare against paths that appear in the injected diff headers (`diff --git a/... b/...`, `+++ b/...`), not an unbounded filesystem walk.
- **Already-exists HEAD fallback**: only when `next_action` is `skip_refactor` (already-exists / no-failing-test PASS). Quotes must exist as exact substrings of the named files at HEAD. Missing files fail.
- **COMPLIANCE_VIOLATION**: evidence gate does not apply; existing feedback cascade (`JUDGE_AGENT_NO_FEEDBACK`) stays.
- **Git isolation**: every test git call `cwd=<tmp_git_repo>` and `env=_git_env()`; production uses `git_env()`.
- **Micro pytest**: do not call un-mocked `_run_pytest`.
- **Prompt pins**: invert any test that currently requires the strings "Default to COMPLIANCE_PASS" or "When in doubt, pass."

## Performance Constraints

- **L_max**: init remains ≤ 500ms (AGENTS.md). The gate is string matching over the already-built diff; no extra git network, no extra agent call.
- **Per-agent export**: ≤ 200ms. No new export path.
- **Full test suite**: `mise run test` remains < 30s. New tests mock `_invoke_agent` / `_run_pytest`; do not spawn real judge agents.
- **Gate latency**: substring checks over a typical RED+GREEN diff should stay well under 200ms in tests.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/test_core/test_agent.py` — `HandoverManifest` parses and round-trips `evidence`.
  - `tests/test_micro/test_judge.py` — PASS with empty evidence and AC-PLAN tokens is rejected; hallucinated path/quote is rejected; matching quotes pass; `proceed_to_refactor_no_diff` requires test_quote only; `skip_refactor` already-exists accepts HEAD quotes and fails when the test file is missing; no-AC-PLAN empty evidence is allowed.
  - `tests/test_micro/test_judge.py` — auto judge prompt contains an `evidence` schema key and does not contain "Default to COMPLIANCE_PASS" or "When in doubt, pass."
- **Integration Sandbox Targets**:
  - `_run_judge_phase` with mocked `_invoke_agent` on a `tmp_git_repo` that has a RED test commit + GREEN impl commit: PASS YAML without quotes does not COMPLETE; PASS YAML with matching quotes proceeds.

## Demonstration Path

```bash
uv run pytest tests/test_core/test_agent.py tests/test_micro/test_judge.py -q --tb=short
```
