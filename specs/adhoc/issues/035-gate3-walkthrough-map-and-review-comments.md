---
title: "Rewrite Gate 3 walkthrough as a four-look map and review as comments-only"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: ["ISS-ADH-004", "ISS-ADH-028"]
issue_id: ISS-ADH-035
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/035-gate3-walkthrough-map-and-review-comments.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/commands/deviate-walkthrough.md`, `src/deviate/prompts/commands/deviate-review.md`, `src/deviate/cli/walkthrough.py`, `src/deviate/cli/review.py`, `src/deviate/core/review_coverage.py`

## The Problem Contract

The coworker path is one issue = one PR, often `--profile fast` (JUDGE skipped). Humans need a four-look map of this issue's brief, tests, named checks, and the command that runs those checks. Automation may comment but must not edit or commit (La Review burned the operator). `/deviate-review` today auto-applies CRITICAL+SUGGESTION and assumes JUDGE already ran. `/deviate-walkthrough` is a curator of raw diff, not a map of brief/tests/named checks. These two existing Gate-3 commands belong together. Do not add a new `pr-review` pack or `/deviate-pr-review` command.

## Scope Boundaries
### Hard Inclusions
- `/deviate-walkthrough` is the four-look map for THIS issue/PR. It MUST emit: (a) where the brief is (issue file path + this issue’s plan AC lines if `plan.md` exists); (b) which hunks are the test diff; (c) which production hunks claim which named check; (d) the command to run those checks. MUST NOT: reimplement, approve, hide hunks, tell the human to skip a look, auto-edit, or apply fixes. Reads: this issue’s brief + named checks + this diff. MUST NOT read epic explore, leftover research, other plans, Product/flows, constitution unless this brief names those paths.
- `/deviate-review` is comments-only and specs-aware. MUST: comments only; no apply; no `git add`/`git commit`; not a merge gate (no REQUEST_CHANGES, no merge). Same inputs → same comments (structured checklist keyed by named-check tokens + test-weakening + cross-task drift, stable sort by token then path then line; no style nits / “consider”). MUST read: this issue’s brief; this issue’s `plan.md` AC-PLAN lines if present; `behavioral`/`ac` tests in the diff; production delta vs those checks; test diff for deleted/skipped/weakened tests. Cross-task drift **on this issue** is in scope (unique job vs per-task JUDGE). MUST NOT: auto-apply CRITICAL/SUGGESTION (delete STEP 4 apply+commit from `deviate-review.md`); hunt Explore if the brief has no named checks (emit exactly `brief incomplete` and stop); treat leftover flows/research as the spec; assume JUDGE already ran (coworker path is `--profile fast` — do not “light-sniff because JUDGE validated”). Non-DeviaTDD: if a brief with named checks is provided, comments only; if not, stop with `brief incomplete`.
- Both remain optional packs (`walkthrough`, `review`). Default setup still does not install them. No new pack names.
- Tests pin: review prompt/CLI has no apply/commit/REQUEST_CHANGES path; incomplete brief → `brief incomplete`; walkthrough prompt requires the four emit fields and forbids approve/hide/skip-a-look/auto-edit; existing auto-apply tests are rewritten to comments-only.
- `deviate walkthrough pre` may gain issue-brief path + plan path (null if absent) + classified test vs production changed files; do not pull constitution/prd unless the brief names them.
- `deviate review pre` includes issue brief path; `review_coverage.py` plan-AC uncovered list is an input to comments, not a reason to auto-fix; do not require coverage_complete to apply anything (there is no apply).
- Update `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md` `[Unreleased]`.

### Defensive Exclusions
- Do not add a new `pr-review` pack or `/deviate-pr-review` command.
- Do not implement ISS-ADH-029 ponytail-in-review.
- Do not change JUDGE.
- Do not change `--profile fast` flags.
- Do not merge. Do not cut a release.
- Do not author or modify Product-layer flows; `flow_refs: []`.
- Do not put this in a FiveWest pitch doc.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-035`
- **Acceptance Criteria Tokens**: `AC-ADHOC-035-01`, `AC-ADHOC-035-02`, `AC-ADHOC-035-03`, `AC-ADHOC-035-04`
- **Data Model Entities**: `IssueBrief`, `NamedCheck`, `FourLookMap`, `ReviewComment`

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-035-01**: As a human reviewing a coworker one-issue PR (often `--profile fast`), I want `/deviate-walkthrough` to emit a four-look map of this brief, this test diff, which production hunks claim which named check, and the command to run those checks so I know what to look at. *(Ref: FR-ADHOC-035)*
- **US-035-02**: As a human who was burned when La Review auto-applied edits, I want `/deviate-review` to post comments only — never apply, never `git add`/`git commit`, never REQUEST_CHANGES — so automation cannot mutate the branch. *(Ref: FR-ADHOC-035)*
- **US-035-03**: As a consumer-project operator, I want `walkthrough` and `review` to stay optional packs with no new pack names so default setup (macro/meso/micro) does not install them. *(Ref: FR-ADHOC-035)*
- **US-035-04**: As a DeviaTDD maintainer, I want tests to pin comments-only review, `brief incomplete` when named checks are missing, and the walkthrough four-look emit/forbid rules so STEP 4 auto-apply cannot return. *(Ref: FR-ADHOC-035)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-035-01** *(Ref: AC-ADHOC-035-01, US-035-01)*: Walkthrough is the four-look map for THIS issue/PR.
  - **Happy Path**: Prompt + `deviate walkthrough pre` emit (a) issue brief path + this issue’s plan AC lines if `plan.md` exists; (b) classified test hunks/files; (c) production hunks mapped to named checks; (d) the command to run those checks. HITL `ask` pacing may remain. Pre includes `issue_brief_path`, `plan_path` (null if absent), and test vs production file lists. Constitution/prd are omitted unless this brief names those paths.
  - **Error Category**: Empty diff still exits with `SKIP: no changes since {base_branch}`.
  - **Boundary Category**: MUST NOT reimplement, approve, hide hunks, tell the human to skip a look, auto-edit, or apply fixes. MUST NOT read epic explore, leftover research, other plans, Product/flows, or constitution unless this brief names those paths.
- **AO-035-02** *(Ref: AC-ADHOC-035-02, US-035-02)*: `/deviate-review` is comments-only and specs-aware.
  - **Happy Path**: Comments only (stdout and/or GitHub PR review event COMMENT if a PR exists). Structured checklist keyed by named-check tokens + test-weakening + cross-task drift; stable sort by token then path then line. Same inputs → same comments. `review_coverage.py` uncovered list is comment input. `deviate review pre` includes the issue brief path.
  - **Error Category**: Brief with no named checks emits exactly `brief incomplete` and stops. Do not hunt Explore. Non-DeviaTDD without a named-check brief stops the same way.
  - **Boundary Category**: No apply; no `git add`/`git commit`; no REQUEST_CHANGES; no merge. STEP 4 apply+commit is deleted. Do not assume JUDGE already ran. Do not treat leftover flows/research as the spec. Do not require `coverage_complete` to apply anything (there is no apply).
- **AO-035-03** *(Ref: AC-ADHOC-035-03, US-035-03)*: Both remain optional packs (`walkthrough`, `review`). Default setup still does not install them. No new pack names.
  - **Happy Path**: `OPTIONAL_PACKS` still maps `review` → `deviate-review` and `walkthrough` → `deviate-walkthrough`. Default packs stay macro/meso/micro.
  - **Error Category**: A new `pr-review` pack name or `/deviate-pr-review` command must not appear.
  - **Boundary Category**: Pack membership is unchanged by this slice.
- **AO-035-04** *(Ref: AC-ADHOC-035-04, US-035-04)*: Tests pin the rewrite.
  - **Happy Path**: Review prompt/CLI has no apply/commit/REQUEST_CHANGES path. Incomplete brief → `brief incomplete`. Walkthrough prompt requires the four emit fields and forbids approve/hide/skip-a-look/auto-edit.
  - **Error Category**: Existing auto-apply tests are rewritten to comments-only rather than kept green by leaving auto-apply in place.
  - **Boundary Category**: JUDGE, `--profile fast`, and ISS-ADH-029 ponytail-in-review are untouched.
<!-- `**Given**` / `**When**` / `**Then**` are forbidden here. -->

## Edge Cases and Boundaries
- Coworker path is `--profile fast`: JUDGE may not have run. Review must not “light-sniff because JUDGE validated”.
- Cross-task drift **on this issue** is in scope; leftover epic research and Product/flows are not the spec unless this brief names those paths.
- `review_coverage.py` uncovered plan-AC tokens stay in the pre contract as comment input. They are not a reason to auto-fix.
- Non-DeviaTDD repos: comments only when a brief with named checks is provided; otherwise `brief incomplete`.
- La Review / STEP 4 apply+commit must not remain as a fallback path.

## Performance Constraints
- L_max: `deviate review pre` / `deviate walkthrough pre` add less than 50 ms beyond the existing diff + coverage scan.
- Throughput: named-check extraction and test/production file classification stay O(changed files + brief size).

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_cli/test_review.py` — comments-only, `brief incomplete`, issue brief path, no apply/commit/REQUEST_CHANGES; `tests/test_cli/test_walkthrough.py` — four-look pre contract (brief/plan paths, test vs production files, no default constitution/prd); prompt-template tests that previously asserted apply/commit.
- **Integration Sandbox Targets**: Existing optional-pack tests still classify `review` and `walkthrough` as optional. E2E coverage bats keep the uncovered list as comment input and do not require apply.

## Demonstration Path
```bash
# optional packs still off by default
TMP=$(mktemp -d) && cd "$TMP"
deviate setup --agent opencode --packs none
test ! -f .opencode/commands/deviate-review.md
test ! -f .opencode/commands/deviate-walkthrough.md

# comments-only + four-look map (in this repo, with packs installed)
pytest tests/test_cli/test_review.py tests/test_cli/test_walkthrough.py tests/test_meso/test_auto_prompt_templates.py -v && ruff check src/deviate/cli/review.py src/deviate/cli/walkthrough.py
```
