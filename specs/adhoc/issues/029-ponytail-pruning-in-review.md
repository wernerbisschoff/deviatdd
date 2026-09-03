---
title: "Fold Ponytail Minimal-Code Pruning into the /deviate-review Gate and Keep /deviate-pr Squash-Merge Commit-Convention Compliant"
labels: [enhancement, adhoc, vertical-slice, review, meso]
blocked_by: []
coordinates_with: [ISS-ADH-004]
issue_id: ISS-ADH-029
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/029-ponytail-pruning-in-review.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/commands/deviate-review.md` — TARGET: the Gate 3 scan adopts the ponytail minimal-code pruning discipline. Extend the Pragmatism & Architectural Coherence domain's over-engineering signal with the ponytail pre-write ladder (YAGNI → stdlib → platform feature → already-installed dep → one line → minimum that works). Fold into `/deviate-review`; do NOT create `/deviate-ponytail`. Do not add a `## Minimality` / `## Constraints` heading (GH-92 precedent).
  - `src/deviate/prompts/commands/deviate-pr.md` — TARGET: keep the dual-purpose PR body that is also a squash-merge commit body (`{SUMMARY}` / `{CHANGES}` / `{CLOSES}`).
  - `src/deviate/cli/meso.py` — TARGET: verify `_pr_title`, `_pr_body`/`_derive_pr_metadata` and the platform push path adhere to the commit convention on both GitHub (`_run_gh_pr_create`) and GitLab (`_gitlab_push_options`); fix any title/body gap so the squash-merge commit message is valid.
  - `src/deviate/core/convention.py` — TARGET: reference `commit_scope` and emoji detection as the canonical title helpers.
  - `src/deviate/cli/review.py` — TARGET: unchanged unless the review contract must expose the pruning dimension; keep HITL Gate 3 fail-close behavior intact.
  - `tests/unit/test_meso/test_auto_prompt_templates.py` — TARGET: pin the folded ponytail ladder text and the absent Minimality/Constraints heading; keep `test_review_keeps_overengineering_and_does_not_promote_helpers`.
  - `tests/unit/test_meso/test_pr_platform.py` / `tests/unit/test_cli/test_meso.py` — TARGET: extend title/body pins for the squash-merge commit-convention outcome.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document the folded review pruning and the verified `/deviate-pr` squash-convention behavior in the same implementation commit.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible review pruning and any PR title/body fix.
- **Classification for plan/tasks**: prompt-markdown + small production-verification with observable behavior. Prefer TDD for any `meso.py`/title-body fix; prompt-text pins are test-only.
- **Upstream Evidence**:
  - `specs/explore/ponytail-pruning.md` — Discovery consumed (pre-research staging). Scope sizing labels the ponytail concern Medium (2-5 files) and notes `/deviate-pr` is already implemented (verification or small fix).
  - `tests/unit/test_meso/test_auto_prompt_templates.py` — `TestSmallestChangeFoldedIntoExistingPrompts`: "GH-92 (rescoped): Ponytail smallest-change lives in existing GREEN / REFACTOR / review lines — no new Constraints or Minimality heading." `test_review_keeps_overengineering_and_does_not_promote_helpers`: asserts "Cross-task over-engineering", no "into a shared helper", no "## Constraints".
  - `src/deviate/prompts/commands/deviate-review.md` v3.1.0 — domain 3 "Pragmatism & Architectural Coherence" already lists "Cross-task over-engineering".
  - `src/deviate/prompts/commands/deviate-pr.md` v2.0.0 — the PR body MUST serve dual purpose: good PR description AND good squash-merge commit body (`{SUMMARY}` / `{CHANGES}` / `{CLOSES}`).
  - `src/deviate/cli/meso.py` — `_pr_title` builds `{commit_type}({commit_scope}): {desc}`; `_run_gh_pr_create` calls `gh pr create --title ... --body-file`; `_gitlab_push_options` uses `merge_request.title` / `merge_request.description` push options.
  - `src/deviate/core/convention.py` — `commit_scope` strips a legacy `ISS-` prefix; `detect_uses_emojis` returns False for this repo (`CONTRIBUTING.md` has no emoji).
  - `specs/constitution.md` §4 — Commit Convention: `<type>(<scope>): <description>`; types `feat|fix|test|refactor|docs|chore`; scope is task ID; body wraps at 72 chars.
  - DietrichGebert/ponytail (external) — pre-write ladder: 1. Does this need to exist? (YAGNI); 2. Stdlib does it?; 3. Native platform feature?; 4. Already-installed dep?; 5. Fits in one line?; 6. Else the minimum that works. Honest measured LOC reduction ≈ 54% (viral 80-94% claim based on a bare baseline).

## The Problem Contract

The operator wants the "ponytail" coding discipline to prune excessive code and wants the PR/MR step to produce a title and body that, after squashing, yield a valid conventional commit message. This vertical slice folds the ponytail pruning into the existing `/deviate-review` Gate (no new command, per GH-92) and verifies `/deviate-pr` emits commit-convention-compliant PR/MR metadata for a clean squash-merge.

## Scope Boundaries

### Hard Inclusions

- Fold the ponytail pre-write ladder into `/deviate-review` v3.1.0 as an explicit pruning check inside the Pragmatism & Architectural Coherence domain. No `/deviate-ponytail` command.
- Do not add a separate `## Minimality` or `## Constraints` heading; keep `Cross-task over-engineering` text and the "do not promote helper extraction" rule.
- Verify `/deviate-pr` title (`_pr_title`) and body (`_derive_pr_metadata` / `{SUMMARY}`/`{CHANGES}`/`{CLOSES}`) adhere to `specs/constitution.md` §4 and `CONTRIBUTING.md` on both the GitHub (`gh`) and GitLab (push-option) paths.
- Fix any title/body gap found so the squash-merge commit message is a valid conventional commit; pin with tests.
- Keep the two-counter / RED-GREEN-JUDGE-REFACTOR micro contract intact. Green-phase scope stays limited to `src/` plus permitted implementation paths.
- Update API + architecture in the same implementation commit for any user-visible change; add a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests that touch git use `tmp_git_repo` + `_git_env()` / `cwd=<tmp_git_repo>`; mock `deviate.cli.micro._run_pytest` for any CLI path that would spawn it.

### Defensive Exclusions

- Do **not** create a new `/deviate-ponytail` slash command or a new prompt heading. The fold default comes from the GH-92 precedent and the pinned test.
- Do **not** promote systematic helper extraction or "into a shared helper" refactors. Ponytail pruning removes real, removable excess only.
- Do **not** change `deviate review` HITL Gate 3 fail-close semantics; the pruning dimension is additive to the existing review scan.
- Do **not** change emoji detection / the commit-convention template (both already consistent with `CONTRIBUTING.md`).
- Do **not** re-architect the GitHub `gh` / GitLab push-option transport; only verify and fix title/body compliance on the existing paths.
- Do **not** author, repair, or index Product-layer flows. `flow_refs: []`; FLOW-04 is RPC TUI live-stream, unrelated to review pruning or PR metadata.
- Do **not** delete branches, mutate operator-local `.deviate/config.toml`, or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** invent a second issue-id series. This issue is ISS-ADH-029.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-029`
- **Acceptance Criteria Tokens**: `AC-ADHOC-029-01`, `AC-ADHOC-029-02`, `AC-ADHOC-029-03`
- **Data Model Entities**: `FlowRecord`/`FlowEvent` (unrelated; unchanged), issue `IssueRecord`, PR/MR title and body strings. No new ledger row types.
- **Spec Source Anchors**:
  - `specs/explore/ponytail-pruning.md` (File Registry: `deviate-review.md`, `deviate-pr.md`, `deviate-prune.md`, `src/deviate/cli/meso.py`, `src/deviate/core/convention.py`, `tests/unit/test_meso/test_auto_prompt_templates.py`, `tests/unit/test_meso/test_pr_platform.py`, `tests/unit/test_cli/test_meso.py`)
  - `src/deviate/prompts/commands/deviate-review.md` v3.1.0
  - `src/deviate/prompts/commands/deviate-pr.md` v2.0.0
  - `src/deviate/cli/meso.py` (`_pr_title`, `_derive_pr_metadata`, `_run_gh_pr_create`, `_gitlab_push_options`)
  - `src/deviate/core/convention.py` (`commit_scope`, `detect_uses_emojis`)
  - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - `specs/constitution.md` §4 Commit Convention; §5 Definition of Done
  - `CONTRIBUTING.md` Commit convention + "Squash or rebase before merge" + HITL Gate 3

## User Stories Ledger

- **US-029-01**: As a DeviaTDD operator, I want the Gate 3 review to surface over-engineered and excessive code and dispose of it through the ponytail pre-write ladder so minimal code ships, without a new command. *(Ref: FR-ADHOC-029)*
- **US-029-02**: As a DeviaTDD operator, I want `/deviate-pr` to emit a PR/MR title and body that, when squash-merged into `main`, form a valid conventional commit message matching the repo convention. *(Ref: FR-ADHOC-029)*

## Acceptance Outline

- **AO-029-01** *(Ref: AC-ADHOC-029-01, US-029-01)*: `/deviate-review` folds the ponytail pruning discipline.
  - **Happy Path**: The review scan checks over-engineered and excessive code through the ponytail pre-write ladder (YAGNI → stdlib → platform feature → already-installed dep → one line → minimum that works). Pruning lives in `/deviate-review`; no `/deviate-ponytail` command exists.
  - **Error Category**: Introducing a new command or a `## Minimality` / `## Constraints` heading fails the pinned test (`TestSmallestChangeFoldedIntoExistingPrompts`).
  - **Boundary Category**: The existing "Cross-task over-engineering" signal and the "do not promote helper extraction" rule stay present (`test_review_keeps_overengineering_and_does_not_promote_helpers`).

- **AO-029-02** *(Ref: AC-ADHOC-029-02, US-029-01)*: Pruning removes only real, removable excess.
  - **Happy Path**: Review flags dead, over-abstracted, or redundant code and prescribes a minimal-code disposition that keeps passing tested behavior intact.
  - **Error Category**: Systematic helper promotion or "into a shared helper" refactor suggestions are absent from the review output.
  - **Boundary Category**: A behaviour-preserving change is still subject to the normal Gate 3 review; pruning does not weaken any REGRESSION / two-counter pin.

- **AO-029-03** *(Ref: AC-ADHOC-029-03, US-029-02)*: `/deviate-pr` metadata squash-merges into a valid conventional commit.
  - **Happy Path**: `_pr_title` yields `<type>(<scope>): <desc>` and the body (`{SUMMARY}` / `{CHANGES}` / `{CLOSES}`) is a valid squash-merge commit body on both GitHub (`gh pr create`) and GitLab (push options). Squash-merge into `main` reproduces the conventional title.
  - **Error Category**: A title/body that violates `specs/constitution.md` §4 or `CONTRIBUTING.md` fails the verification pin, and the gap is fixed in `src/deviate/cli/meso.py` (+ tests) in this slice.
  - **Boundary Category**: Emoji state stays a no-op (`detect_uses_emojis` False); the repo convention template is unchanged.

## Edge Cases and Boundaries

- Review strategy `targeted` (large diff) still applies the pruning ladder from the structured diff; no governance reads required for the pruning dimension.
- A new `/deviate-ponytail.md` file or any `## Minimality` / `## Constraints` heading appears → the GH-92 pin fails; this is a regression, not a feature.
- PR/MR body with an empty `body` on GitLab omits `merge_request.description` push option; the title push option still applies.
- `commit_scope` strips the legacy `ISS-` prefix and keeps the `ADH-` scope for adhoc ids; both title forms must remain valid.
- A review over a diff with no changes (`deviate review pre` → empty `diff`) emits the existing `SKIP` and exits; pruning checks do not run.
- Pruning never deletes a passing tested behavior; any deletion must keep all regression tests green.

## Performance Constraints

- L_max: prompt-text changes add no runtime latency; `_pr_title` / title-body generation stays ≤ 50ms on a typical record.
- Throughput: no extra LLM call for the pruning ladder (prompt-level only). Full test suite stays under 30s; mock `_run_pytest` on CLI paths that would spawn it.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_meso/test_auto_prompt_templates.py` — `TestSmallestChangeFoldedIntoExistingPrompts` (ladder folded, no new Minimality/Constraints heading); `test_review_keeps_overengineering_and_does_not_promote_helpers` (still green).
  - `tests/unit/test_cli/test_meso.py` — extended `_pr_title` / body pins assert the squash-merge conventional-commit outcome.
  - `tests/unit/test_meso/test_pr_platform.py` — GitHub / GitLab title and body push-path pins stay green.
- **Integration Sandbox Targets**:
  - `tests/test_integration/test_meso_layer.py::TestPrRun` — `deviate pr` end-to-end PR/MR metadata still yields a conventional title and dual-purpose body; no squash-merge regression.

## Demonstration Path

```bash
mise run check && pytest tests/unit/test_meso/test_auto_prompt_templates.py tests/unit/test_cli/test_meso.py tests/unit/test_meso/test_pr_platform.py -q
```
