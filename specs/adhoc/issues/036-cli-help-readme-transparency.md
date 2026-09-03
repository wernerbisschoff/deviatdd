---
title: "Make deviate --help and README phase-transparent"
labels: [enhancement, adhoc, docs]
blocked_by: []
coordinates_with: ["ISS-ADH-035"]
issue_id: ISS-ADH-036
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/036-cli-help-readme-transparency.md`
- **Primary Architectural Workstation**: `README.md`, `src/deviate/cli/__init__.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/micro.py`, `tests/unit/test_cli/test_help.py`

## The Problem Contract

The harness is opinionated. Prompts call a lot of `pre`/`post`. Coworkers cannot tell from `--help` or the README which commands commit, spawn an agent, or fail closed. Source of truth for *what* to say is the operator transparency note (not prose to paste). README and Typer help must make commits, Codex spawn, fail-closed exits, `pre`/`post`, `--profile fast`, and the `--review` vs `/deviate-review` distinction obvious — without dumping the full note and without fighting ISS-ADH-035 / PR #135.

## Scope Boundaries
### Hard Inclusions
- File this adhoc issue, `FR-ADHOC-036` on `specs/adhoc/prd.md`, and one BACKLOG ledger row (`flow_refs: []`).
- README: a short per-phase table or tight sections for setup, adhoc, meso, micro, review, walkthrough. Each row: what it does, what it commits, how to debug a fail.
- Facts that must be obvious: which commands commit (including RED `git commit --no-verify`); which spawn Codex (`codex exec --sandbox workspace-write --ask-for-approval never`); nested spawn inside `meso run` / `micro run`; fail-closed exits (`NO_AGENT_SELECTED`, `COVERAGE_INCOMPLETE` on `review pre`, unknown `--packs`); `pre` injects a JSON contract and `post` validates/writes/commits; slash prompts tell the agent to run `pre`/`post` and auto prompts tell the agent not to; `--profile fast` skips JUDGE **and** REFACTOR; `deviate micro run --review` is a TTY pause before phase commit, not `/deviate-review`; skill argument `review` is an agent loop policy (never pass `--review` from the skill); default setup on current main (#134) installs macro+meso+micro only; optional packs are product, merge, pr, review, walkthrough, html, hotfix, triage, prune, e2e; shared `deviatdd` skill still installs; do not document PyPI 2.23.1 as current main; meso default uses a worktree; `--no-setup --local` stays in this clone and skips the remote lock (Path A coworker flow); `claim_remote` default false; `/deviate-review` comments-only default (align ISS-ADH-035); opt-in `--apply` CRITICAL-only if apply is mentioned; not a merge gate; `/deviate-walkthrough` is the four-look map (optional pack).
- Typer `--help` on `deviate setup`, `deviate meso run`, `deviate micro run` (`--profile`, `--review`, `--all`), and any other command whose help currently hides commits/spawns. Keep help to a few lines.
- Tests only if help strings are already pinned; otherwise a small test that `--help` mentions the pause-vs-slash distinction for `--review` and that `fast` mentions skipping JUDGE.
- `CHANGELOG.md` `[Unreleased]` in the same commit.

### Defensive Exclusions
- Do not commit onto PR #135 / `cursor/gate3-walkthrough-review-bf34`. Do not merge #135 into this PR.
- Do not edit `src/deviate/prompts/commands/deviate-review.md` or `deviate-walkthrough.md` or `src/deviate/cli/review.py` / `walkthrough.py` unless a one-line `--help` string is the only way and you would otherwise lie. Prefer README + Typer help on other commands.
- Do not change pack membership, JUDGE, profile flags, or Gate 3 prompt bodies.
- Do not dump the full transparency note into the README. Do not turn this into a FiveWest pitch.
- Do not cut a release. Do not merge this PR.
- Do not author or modify Product-layer flows; `flow_refs: []`.
- No Gherkin in this issue file.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-036`
- **Acceptance Criteria Tokens**: `AC-ADHOC-036-01`, `AC-ADHOC-036-02`, `AC-ADHOC-036-03`
- **Data Model Entities**: none (docs + Typer help strings)

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-036-01**: As a coworker on a consumer repo, I want `deviate --help` and the README to say which phases commit, spawn an agent, or fail closed so I can run Path A without reading prompts. *(Ref: FR-ADHOC-036)*
- **US-036-02**: As a coworker, I want `--profile fast` and `--review` help to name what they skip or pause so I do not confuse them with JUDGE or `/deviate-review`. *(Ref: FR-ADHOC-036)*
- **US-036-03**: As a coworker, I want default packs, `claim_remote` false, `--no-setup --local`, and comments-only `/deviate-review` documented as current main — not PyPI 2.23.1. *(Ref: FR-ADHOC-036)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-036-01** *(Ref: AC-ADHOC-036-01, US-036-01)*: README has a short per-phase table (setup, adhoc, meso, micro, review, walkthrough) covering does / commits / debug a fail, including RED `--no-verify`, Codex spawn argv, nested spawn, `pre`/`post`, fail-closed tokens, default vs optional packs, worktree vs `--no-setup --local`, and `claim_remote` default false.
  - **Happy Path**: A coworker reading README + `deviate setup --help` / `meso run --help` / `micro run --help` can answer "does this commit?" and "does this spawn?" without opening a prompt file.
  - **Error Category**: Unknown `--packs` and `NO_AGENT_SELECTED` are named as fail-closed.
  - **Boundary Category**: The README does not paste the full troubleshooting note and is not a product pitch.
- **AO-036-02** *(Ref: AC-ADHOC-036-02, US-036-02)*: `deviate micro run --help` states that `fast` skips JUDGE and REFACTOR, and that `--review` is a TTY pause before phase commit, not `/deviate-review`.
  - **Happy Path**: `--profile` help keeps the pinned `Execution profile: full, fast` substring and adds the skip.
  - **Error Category**: `--review` without a TTY still fail-closes (`REVIEW_REQUIRES_TTY`); help does not claim it is `/deviate-review`.
  - **Boundary Category**: Skill argument `review` is documented as an agent loop policy that must not pass `--review` into the runner.
- **AO-036-03** *(Ref: AC-ADHOC-036-03, US-036-03)*: `/deviate-review` is documented as comments-only default (not a merge gate; opt-in `--apply` CRITICAL-only if apply is mentioned). `/deviate-walkthrough` is the four-look map. PyPI 2.23.1 is not taught as current main. ISS-ADH-035 prompt bodies are not edited.
  - **Happy Path**: README review/walkthrough rows match ISS-ADH-035 product language without merging #135.
  - **Error Category**: `COVERAGE_INCOMPLETE` is named as the `review pre` fail-closed token.
  - **Boundary Category**: One-line Typer help on `review` / `walkthrough` may be updated in `__init__.py` so help does not lie; `review.py` / `walkthrough.py` / Gate 3 prompt bodies stay untouched.
<!-- `**Given**` / `**When**` / `**Then**` are forbidden here. -->

## Edge Cases and Boundaries
- ISS-ADH-035 / PR #135 stays a sibling PR. This issue coordinates and does not implement walkthrough four-look or review `--apply` runtime.
- Existing `--help` pins (`Use \`deviate meso run\``, `Bootstrap`, `Prepare`, `Execution profile: full, fast`, user-panel membership) must keep passing.
- `deviate micro run --review` vs skill argument `review` vs `/deviate-review` are three different things and must stay distinct in prose.
- Do not document 2.23.1's install-all-slash-files or auto-apply CRITICAL+SUGGESTION as current.

## Performance Constraints
- L_max: help-string and README edits add no runtime cost beyond Typer rendering.
- Throughput: no new subprocesses, ledgers, or agent invocations in production code.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_cli/test_help.py` — `--review` pause-vs-slash; `fast` mentions skipping JUDGE; existing panel pins. `tests/unit/test_core/test_profile.py::test_help_lists_only_full_and_fast` — pinned `Execution profile: full, fast`. `tests/unit/test_cli/test_setup.py::TestReadmeNewUserPath` — Quickstart still names setup then `/deviate-init`.
- **Integration Sandbox Targets**: none (docs + help only).

## Demonstration Path
```bash
deviate setup --help
deviate meso run --help
deviate micro run --help
# --profile help names full, fast and that fast skips JUDGE
# --review help says TTY pause, not /deviate-review
pytest tests/unit/test_cli/test_help.py tests/unit/test_core/test_profile.py tests/unit/test_cli/test_setup.py::TestReadmeNewUserPath -v
```
