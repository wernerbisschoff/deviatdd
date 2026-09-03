---
title: "CWE Mapping on JUDGE Security Findings — `SecurityProfile.cwe_id` + CWE-tagged flat security scan"
labels: [enhancement, adhoc, vertical-slice, security]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-014
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/014-cwe-mapping-security-findings.md`
- **Primary Architectural Workstations**:
  - `src/deviate/state/ledger.py:61-78` — MODIFY: add one optional `cwe_id: str | None = None` field to the existing `SecurityProfile` Pydantic model, preserving `model_config = {"extra": "forbid"}`.
  - `src/deviate/state/ledger.py:81-98` — REFERENCE: `TaskRecord` carries `security_profile: SecurityProfile | None = None` at line 97; unchanged.
  - `src/deviate/prompts/auto/judge.md:78` — MODIFY: the "Security Checks" `security_checks: pass | fail | warn` manifest-field directive gains a deterministic CWE-ID token on each finding.
  - `src/deviate/prompts/auto/judge.md:101` — MODIFY: the flat security scan line enumerates each probe with a CWE-ID token (hardcoded secrets `CWE-798`, injection `CWE-79`, unsafe deserialization `CWE-502`, path traversal `CWE-22`, log leakage `CWE-532`).
  - `src/deviate/prompts/commands/deviate-plan.md:165-172` — MODIFY: the `## Security Profile` prose template instructs the planner to optionally record the applicable `CWE-ID` for each risk surface and the negative tests that exercise it.
  - `src/deviate/prompts/commands/deviate-review.md` — MODIFY: Gate 3 cross-task Security aggregation domain surfaces CWE-ID tokens per finding so composed-vulnerability review can aggregate by CWE.
  - `src/deviate/cli/review.py:18` — REFERENCE: `review_app` runs at HITL Gate 3; consumes the review prompt (no signature change required).
  - `tests/unit/test_state/test_security_profile.py` — TARGET: extend the existing `SecurityProfile` contract tests (5 tests) with a `cwe_id` round-trip test.
  - `tests/unit/test_micro/test_judge.py` — TARGET: extend the `TestJudgeSecurityChecksField` class (line 1557) with one test pinning the CWE vocabulary in the rendered Judge prompt.
  - `specs/constitution.md` — REFERENCE: §5 Definition of Done "No governance violations (constitution rules upheld)". No tooling change; the CWE tag is a prompt/data-model change, not the adoption of a new declared SAST/type-check tool.
  - `specs/DeviaTDD-api.md` — MODIFY: document the `SecurityProfile.cwe_id` field and the CWE-tagged `security_checks` verdict vocabulary (spec-alignment mandate).
  - `specs/DeviaTDD-architecture.md` — MODIFY: document the CWE mapping in the JUDGE manifest contract (spec-alignment mandate).
- **Upstream Evidence**:
  - `specs/explore/security-hardening-cwe.md:9` — Problem statement: determine where CWE mapping belongs.
  - `specs/explore/security-hardening-cwe.md:111-115` — Standard tooling and best-practices findings: CWE is the standard weakness taxonomy and the mapping target for SAST and OWASP findings.
  - `specs/explore/security-hardening-cwe.md:141-146` — Scope sizing: Medium complexity; files modified 2-4; CWE is a bounded addition rather than a rewrite.
  - `specs/explore/security-hardening-cwe.md:154` — `NEXT_ACTION`: run `/deviate-adhoc` with the same problem statement; `explore.md` on disk is auto-consumed.

## The Problem Contract
The DeviaTDD security control is expressed as a prose flat security scan inside the JUDGE phase (`src/deviate/prompts/auto/judge.md:101`) and a prose-only `SecurityProfile.body` ledger field (`src/deviate/state/ledger.py:61-78`), with a mandatory `security_checks: pass | fail | warn` manifest field pinned by `tests/unit/test_micro/test_judge.py:1557`. None of these findings carry a CWE identifier, so a security finding emitted by one Judge verdict cannot be aggregated, grepped, or compared with the same finding class emitted by another task, and the Gate 3 cross-task Security aggregation at `src/deviate/cli/review.py` must match on prose labels instead of a stable token taxonomy. This slice maps the existing flat scan probes and the `SecurityProfile` model to deterministic CWE identifiers (`CWE-798`, `CWE-79`, `CWE-502`, `CWE-22`, `CWE-532`), so findings are stable, greppable, and cross-task-aggregable.

## Scope Boundaries
### Hard Inclusions
- Add one optional `cwe_id: str | None = None` field to `SecurityProfile` at `src/deviate/state/ledger.py:61-78`. Keep the existing `body: str | None = None` field and `model_config = {"extra": "forbid"}`. This is metadata, not a structured risk model — no new `risk_surfaces` / `negative_tests` / `green_constraints` models are introduced in this issue (deferred per the existing model docstring at `src/deviate/state/ledger.py:69-73`).
- Extend the flat security scan directive in `src/deviate/prompts/auto/judge.md:101` so each probe carries a deterministic CWE-ID token: hardcoded secrets `CWE-798`, injection (`subprocess.run` / `os.system` / `eval`) `CWE-79`, unsafe deserialization (`pickle.loads` / `yaml.load`) `CWE-502`, path traversal (path from user input) `CWE-22`, log leakage (secrets in log/print) `CWE-532`.
- Extend the mandatory `security_checks` manifest-field directive at `src/deviate/prompts/auto/judge.md:78` so a `fail` verdict names the CWE-ID token(s) of the blocking finding. Keep the vocabulary locked to `pass | fail | warn`.
- Extend the `## Security Profile` template at `src/deviate/prompts/commands/deviate-plan.md:165-172` to instruct the planner to optionally record the applicable `CWE-ID` for each risk surface and the negative tests that exercise it.
- Extend the Gate 3 Security aggregation domain in `src/deviate/prompts/commands/deviate-review.md` to surface each finding's CWE-ID token for cross-task aggregation.
- Add tests:
  - `tests/unit/test_state/test_security_profile.py::test_security_profile_cwe_id_round_trip` — parse `SecurityProfile(cwe_id="CWE-798")`, re-emit via `model_dump_json`, parse back, assert byte-equal and field preserved; assert `SecurityProfile(cwe_id="not-a-cwe")` is NOT rejected (lenient string field) but unknown extra fields still raise `ValidationError` (`extra=forbid`).
  - `tests/unit/test_state/test_security_profile.py::test_security_profile_default_cwe_id_none` — `SecurityProfile()` yields `cwe_id is None` (parallel to the existing `test_security_profile_default_construction`).
  - `tests/unit/test_micro/test_judge.py::TestJudgeSecurityChecksField::test_judge_prompt_declares_cwe_vocabulary` — load the judge prompt via `_build_auto_prompt("judge", task, tmp_path)` and assert each of `CWE-798`, `CWE-79`, `CWE-502`, `CWE-22`, `CWE-532` appears in the rendered prompt beside its probe.
- Spec alignment (`specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`): document the new `SecurityProfile.cwe_id` field and the CWE-tagged `security_checks` verdict vocabulary in the same commit.
- **CHANGELOG.md `[Unreleased] → Added` bullet in this same commit**: the CWE mapping changes user-visible verdict behavior (AGENTS.md §CHANGELOG Discipline). Bullet summarizes the `SecurityProfile.cwe_id` field, the CWE-tagged flat scan, and the Gate 3 CWE aggregation.

### Defensive Exclusions
- Do NOT adopt, declare, or configure any SAST tool (`bandit`, `semgrep`, `safety`, `pip-audit`) or type checker (`mypy`, `pyright`). The security gate question (a mandated mechanical linter/type-check gate) is deferred research-track work per `specs/explore/security-hardening-cwe.md:60-63` (`Manifest-Constitution Divergence`). This slice only maps the existing LLM scan to CWE tokens — it does not add a tool channel.
- Do NOT add a dedicated `/deviate-security` CLI phase or command. `specs/explore/security-hardening-cwe.md:145` confirms no such command exists today; introducing one is a new command surface + constitution step, scoped as adjacent work downstream of this issue, not part of this slice.
- Do NOT change `specs/constitution.md` §2 Tooling. The flat scan stays LLM-driven; no new declared tool is added. The `mypy` `.mypy_cache/` ghost-dependency divergence (`specs/explore/security-hardening-cwe.md:59-63`) is explicitly out of scope.
- Do NOT replace `SecurityProfile.body` or remove the prose field. The `body` field is the verbatim plan-section carrier consumed by the Judge prompt; `cwe_id` is additive and parallel.
- Do NOT modify `IssueRecord`, `TaskRecord`, `FlowRecord`, `FlowEvent`, or `FlowCoverage` Pydantic models. Only `SecurityProfile` gains the `cwe_id` field.
- Do NOT change the `security_checks: pass | fail | warn` vocabulary or its mandatory semantics. The pinned test `TestJudgeSecurityChecksField` must continue to pass unchanged and green.
- Do NOT rewrite the authorize flow mapping: `flow_refs` remains `[]`. The security-hardening capability is not represented by any existing Product-layer flow in `specs/_product/flows/index.md` (only `FLOW-04` Live-Stream Agent Progress via RPC exists). A flow is authored only if the operator explicitly does so.
- Do NOT modify `specs/_product/` flow artifacts or the `flows.jsonl` ledger.
- Do NOT add tests that invoke `_run_pytest` without mocking `deviate.cli.micro._run_pytest` (AGENTS.md test-performance mandate).

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-014`
- **Acceptance Criteria Tokens**: `AC-ADHOC-014-01` through `AC-ADHOC-014-05`
- **Data Model Entities**:
  - `SecurityProfile` — gains one optional `cwe_id` string field (Pydantic, `extra=forbid`)
- **Spec Source Anchors**:
  - `specs/explore/security-hardening-cwe.md:9` — Problem statement
  - `specs/explore/security-hardening-cwe.md:111-115` — CWE standard taxonomy
  - `src/deviate/state/ledger.py:61-78` — `SecurityProfile` model (MODIFY)
  - `src/deviate/prompts/auto/judge.md:78, 101` — `security_checks` field + flat security scan (MODIFY)
  - `src/deviate/prompts/commands/deviate-plan.md:165-172` — `## Security Profile` template (MODIFY)
  - `src/deviate/prompts/commands/deviate-review.md` — Gate 3 Security aggregation domain (MODIFY)

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- **US-014-01**: As a security auditor triaging a Judge verdict, I want each flat security-scan finding to carry a CWE identifier (secrets, injection, deserialization, path traversal, log leakage) so I can route findings to CWE-trained mitigations, grep the verdict, and compare findings across tasks in `deviate review`. *(Ref: FR-ADHOC-014)*
- **US-014-02**: As a planner authoring the `## Security Profile` section in `plan.md`, I want `SecurityProfile` to accept an optional `cwe_id` field so the risk surface a task touches is tagged with a stable identifier that the Judge reads as supplementary context. *(Ref: FR-ADHOC-014)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- **AO-014-01** *(Ref: AC-ADHOC-014-01, US-014-01)*: The flat security scan in `src/deviate/prompts/auto/judge.md:101` attaches a CWE-ID token to each probe, and a blocking violation forces `security_checks == "fail"`.
  - **Happy Path**: A GREEN diff containing a hardcoded credential is reported with `CWE-798`; the manifest carries `security_checks: fail`.
  - **Error Category**: No CWE token for the probe — the rendered prompt omits the token and the CWE pin test fails.
  - **Boundary Category**: Non-blocking warnings may still carry a CWE token while `security_checks == "warn"`.
- **AO-014-02** *(Ref: AC-ADHOC-014-02, US-014-02)*: `SecurityProfile.cwe_id` round-trips through JSONL serialization and is read by the Judge as supplementary context.
  - **Happy Path**: `SecurityProfile(cwe_id="CWE-798")` serializes, deserializes, and re-emits byte-equal.
  - **Error Category**: An unknown extra field on `SecurityProfile` still raises `ValidationError` (`extra=forbid` stays enforced).
  - **Boundary Category**: `SecurityProfile()` defaults `cwe_id` to `None` (backward-compatible).
- **AO-014-03** *(Ref: AC-ADHOC-014-03, US-014-02)*: The `## Security Profile` planner template at `src/deviate/prompts/commands/deviate-plan.md:165-172` instructs the planner to optionally record the applicable CWE-ID and the negative tests.
  - **Happy Path**: The template text includes a placeholder for `CWE-ID` alongside each risk surface.
  - **Error Category**: Template drift is caught by a prompt-content assertion if the repo pins it.
  - **Boundary Category**: CWE-ID is optional; a planner who does not supply it produces a valid `SecurityProfile` with `cwe_id=None`.
- **AO-014-04** *(Ref: AC-ADHOC-014-04)*: The `security_checks: pass | fail | warn` vocabulary and its mandatory semantics are unchanged.
  - **Happy Path**: `tests/unit/test_micro/test_judge.py::TestJudgeSecurityChecksField` passes without modification.
  - **Error Category**: Any vocabulary rename or softening is a deliberate design decision and is rejected by the pinned test.
  - **Boundary Category**: CWE tokens augment, never replace, the three-value verdict.
- **AO-014-05** *(Ref: AC-ADHOC-014-05, US-014-01)*: A new pinned test asserts the CWE vocabulary is present in the rendered Judge prompt.
  - **Happy Path**: `_build_auto_prompt("judge", task, tmp_path)` output contains `CWE-798`, `CWE-79`, `CWE-502`, `CWE-22`, `CWE-532`.
  - **Error Category**: A probe without its CWE token fails the pin, surfacing prompt drift.
  - **Boundary Category**: The test asserts token presence, not token ordering.

## Edge Cases and Boundaries
- **`cwe_id` with an invalid CWE string**: `SecurityProfile(cwe_id="not-a-cwe")` is accepted (the field is a lenient string), because CWE validity is a review-time concern, not a model-parse concern. Unknown extra fields remain rejected via `extra=forbid`.
- **Legacy tasks without `cwe_id`**: `SecurityProfile()` and any previously-persisted `SecurityProfile(body=...)` rows read back with `cwe_id=None`; the JSONL ledger is append-only and old rows are not rewritten.
- **Probe present, CWE mapping absent**: If the Judge prompt ever carries a probe without its CWE token, the CWE pin test fails first — this is prompt drift, not silent behavior change.
- **A single diff spanning multiple CWE classes**: The Judge may surface more than one CWE-ID token in one verdict; `security_checks` remains a single `pass | fail | warn` value driven by the most severe blocking class.
- **Non-blocking warnings**: A `warn` verdict can still carry a CWE token (informational finding); only a blocking violation forces `fail`.
- **`deviate review` aggregation with sparse CWE tags**: Until all tasks carry the new token vocabulary, cross-task aggregation matches on `CWE-XX` tokens where present and falls back to prose labels for legacy tasks; no hard failure on missing tokens.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- **L_max (SecurityProfile parse)**: ≤ 200ms per task export (adds one optional string field; a no-op cost below the AGENTS.md ≤ 200ms per-agent-export gate).
- **L_max (init)**: ≤ 500ms — unchanged; no new import-time cost beyond the existing `SecurityProfile` model.
- **Throughput**: No new ledger writes are introduced by this issue. `SecurityProfile.cwe_id` round-trip is O(1); full test suite stays < 30s (AGENTS.md mandate). New tests: 2 in `tests/unit/test_state/test_security_profile.py` + 1 in `tests/unit/test_micro/test_judge.py`, each ≤ 200ms (mocked loader, no subprocess).
- **Test performance**: The new judge CWE test MUST mock `deviate.cli.micro._run_pytest` (or avoid invoking it) so the suite stays under 30s, per AGENTS.md test-performance mandate.
- **Lint budget**: `mise run lint` (ruff check) and `mise run format-check` report zero violations on the one new model field and the three new tests.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/unit/test_state/test_security_profile.py::test_security_profile_cwe_id_round_trip` — CWE-ID JSONL round-trip byte-equal; extra=forbid still enforced.
  - `tests/unit/test_state/test_security_profile.py::test_security_profile_default_cwe_id_none` — `SecurityProfile()` yields `cwe_id is None`.
  - `tests/unit/test_micro/test_judge.py::TestJudgeSecurityChecksField::test_judge_prompt_declares_cwe_vocabulary` — rendered judge prompt contains the five `CWE-XX` tokens.
- **Integration Sandbox Targets**:
  - `tests/unit/test_micro/test_judge.py::TestJudgeSecurityChecksField::test_judge_prompt_declares_security_checks_as_required_field` — must remain green unchanged (vocabulary lock).
  - Manual smoke: `uv run python -c "from deviate.state.ledger import SecurityProfile; p=SecurityProfile(cwe_id='CWE-798', body='x'); print(p.model_dump_json())"` round-trips.

## Demonstration Path
```bash
# 1. Verify SecurityProfile.cwe_id round-trips through JSONL
uv run python -c "
from deviate.state.ledger import SecurityProfile
p = SecurityProfile(cwe_id='CWE-798', body='secrets risk')
js = p.model_dump_json()
q = SecurityProfile.model_validate_json(js)
assert p == q and q.cwe_id == 'CWE-798', 'round-trip failed'
print('round-trip OK:', q.model_dump_json())
# extra=forbid still enforced
from pydantic import ValidationError
try:
    SecurityProfile(nope=1)
    raise SystemExit('expected ValidationError')
except ValidationError:
    print('extra=forbid OK')
"

# 2. Confirm the Judge prompt renders the CWE vocabulary
uv run python -c "
from pathlib import Path
from deviate.cli.micro import _build_auto_prompt
task = {'id': 'TSK-014-01', 'issue_id': 'ISS-ADH-014', 'description': 'CWE scan', 'status': 'PENDING', 'execution_mode': 'TDD'}
prompt = _build_auto_prompt('judge', task, Path('.'))
for tok in ['CWE-798', 'CWE-79', 'CWE-502', 'CWE-22', 'CWE-532']:
    assert tok in prompt, f'missing {tok}'
print('judge CWE vocabulary OK')
"

# 3. Run the new + locked tests
mise run test tests/unit/test_state/test_security_profile.py -v
mise run test tests/unit/test_micro/test_judge.py::TestJudgeSecurityChecksField -v

# 4. Lint and format
mise run lint
mise run format-check
```
