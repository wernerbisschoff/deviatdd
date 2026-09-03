## Plan Summary
- **Issue**: ISS-ADH-035 — Rewrite Gate 3 walkthrough as a four-look map; review is comments by default with opt-in --apply CRITICAL
- **Implementation Strategy**: Remove the stray `/deviate-pr-review` reference from the e2e prompt, verify the walkthrough four-look map and review comments-default contracts hold, and pin all four behaviors with CLI-output tests plus spec and CHANGELOG updates.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-3 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Walkthrough emits the four-look map for this issue**
- **Source Outline**: `AO-035-01`
- **Upstream Traceability**: `US-035-01`, `FR-ADHOC-035`, `AC-ADHOC-035-01`
- **Current-Code Evidence**: `src/deviate/cli/walkthrough.py:classify_changed_files`
- **Given**: The walkthrough prompt and `deviate walkthrough pre` contract for this issue
- **When**: A human runs the walkthrough on this issue PR
- **Then**: The output shows the brief path plus plan AC lines, the test hunks, production hunks mapped to named checks, and the command that runs those checks, and empty diff exits with `SKIP: no changes since {base_branch}`
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Review posts comments by default and applies CRITICAL only with --apply**
- **Source Outline**: `AO-035-02`
- **Upstream Traceability**: `US-035-02`, `FR-ADHOC-035`, `AC-ADHOC-035-02`
- **Current-Code Evidence**: `src/deviate/cli/review.py:_apply_enabled`
- **Given**: The review prompt and `deviate review pre` contract for this issue
- **When**: A human runs review without flags and then with `--apply`
- **Then**: The default path prints or posts comments with no edits, no `git add`, no commit, never `REQUEST_CHANGES`, emits exactly `brief incomplete` when the brief has no named checks, and `--apply` lands CRITICAL findings with a concrete FIX only and commits only when such a fix landed
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Walkthrough and review stay optional packs with no new pack names**
- **Source Outline**: `AO-035-03`
- **Upstream Traceability**: `US-035-03`, `FR-ADHOC-035`, `AC-ADHOC-035-03`
- **Current-Code Evidence**: `src/deviate/core/commands.py:OPTIONAL_PACKS`
- **Given**: The pack registry and the e2e prompt chain reference
- **When**: Setup runs with default packs and a scan searches for new pack names
- **Then**: Default setup installs only macro, meso, and micro packs, `OPTIONAL_PACKS` still maps `review` and `walkthrough` with no `pr-review` entry, no `deviate-pr-review.md` file exists, and no prompt references `/deviate-pr-review`
- **Verification Mode**: automated

**Scenario AC-PLAN-004: CLI-output tests pin the rewrite without prompt-body greps**
- **Source Outline**: `AO-035-04`
- **Upstream Traceability**: `US-035-04`, `FR-ADHOC-035`, `AC-ADHOC-035-04`
- **Current-Code Evidence**: `tests/unit/test_cli/test_review.py:test_review_pre_default_apply_is_false`
- **Given**: The unit test suites for review and walkthrough CLI contracts
- **When**: The test suite runs for this slice
- **Then**: Tests assert on CLI output and files for default no-apply, `--apply` CRITICAL-only, `brief incomplete`, and the walkthrough four-look pre fields, and no test asserts on prompt-body substrings
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/prompts/commands/deviate-e2e.md**: Remove the `/deviate-pr-review` chain reference
  - **Current State**: Line 32 chains walkthrough into pr and a `/deviate-pr-review` command that must not exist
  - **Changes Required**: End the chain at an existing command and delete the `/deviate-pr-review` token
  - **Integration Surface**: `/deviate-review` and `/deviate-walkthrough` invocation order
- **src/deviate/prompts/commands/deviate-walkthrough.md**: Verify the four-look map holds
  - **Current State**: Four-look table, per-look `ask` pacing, and empty-diff `SKIP` already present
  - **Changes Required**: Edit only when verification finds a gap against `AO-035-01`
  - **Integration Surface**: `deviate walkthrough pre` JSON contract fields
- **src/deviate/prompts/commands/deviate-review.md**: Verify comments-default and opt-in apply hold
  - **Current State**: Comments-only default, `brief incomplete`, stable sort, and CRITICAL-only STEP 4 already present
  - **Changes Required**: Edit only when verification finds a gap against `AO-035-02`
  - **Integration Surface**: `deviate review pre` contract and `review_coverage.py` uncovered input
- **src/deviate/cli/review.py, src/deviate/cli/walkthrough.py, src/deviate/core/review_coverage.py**: Verify CLI contracts hold
  - **Current State**: `apply` defaults false with `apply_scope` CRITICAL on `--apply`; walkthrough pre emits brief, plan, and classified file lists
  - **Changes Required**: Edit only when verification finds a gap against `AO-035-01` or `AO-035-02`
  - **Integration Surface**: `pre` JSON contracts consumed by the slash commands
- **tests/unit/test_cli/test_review.py, tests/unit/test_cli/test_walkthrough.py**: Pin the four behaviors through CLI output
  - **Current State**: Apply defaults, `brief incomplete`, no-`pr-review` pack, and four-look pre fields already pinned
  - **Changes Required**: Add the e2e prompt reference check and any missing pins for stable sort, empty-diff SKIP, and commit-only-on-CRITICAL
  - **Integration Surface**: CLI `pre` and `post` entry points under test
- **specs/DeviaTDD-api.md, specs/DeviaTDD-architecture.md, CHANGELOG.md**: Record the slice
  - **Current State**: API and architecture sections already describe comments-default review and the four-look walkthrough; CHANGELOG has no 035 entry
  - **Changes Required**: Touch up spec wording only where it drifts from the prompts; append one CHANGELOG bullet under `[Unreleased]`
  - **Integration Surface**: Gate 3 command contracts in the API spec

## Implementation Strategy
- **Phase 1**: Remove the forbidden reference and verify prompt and CLI contracts
  - **Files**: `src/deviate/prompts/commands/deviate-e2e.md`, `src/deviate/prompts/commands/deviate-walkthrough.md`, `src/deviate/prompts/commands/deviate-review.md`, `src/deviate/cli/review.py`, `src/deviate/cli/walkthrough.py`
  - **Approach**: Delete the `/deviate-pr-review` token from the e2e chain; read each Gate 3 prompt and CLI contract against `AO-035-01` and `AO-035-02` and change code only where the text drifts
  - **Verification**: Run the demonstration path command for review and walkthrough unit tests plus `ruff check` on the touched CLI files
- **Phase 2**: Pin the contracts with CLI-output tests and update specs plus CHANGELOG
  - **Files**: `tests/unit/test_cli/test_review.py`, `tests/unit/test_cli/test_walkthrough.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Add CLI-output assertions for the e2e reference removal, stable comment sort, empty-diff SKIP, and commit-only-on-CRITICAL; keep assertions off prompt-body substrings; append one CHANGELOG bullet
  - **Verification**: Run `pytest tests/unit/test_cli/test_review.py tests/unit/test_cli/test_walkthrough.py -v` and confirm full `mise run check` stays green

## Data Flow Analysis
- The e2e prompt chains into `/deviate-review` and `/deviate-walkthrough`; this slice only shortens that chain and changes no data flow. `deviate walkthrough pre` emits the brief path, plan path, diff, and classified test versus production file lists; the walkthrough skill maps those inputs into the four looks. `deviate review pre` emits the brief path, `apply` flag, `apply_scope`, and the `review_coverage.py` uncovered list; the review skill turns those inputs into sorted comments and, only with `--apply`, CRITICAL-only fixes.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Verification shows the prompts already satisfy the issue and the slice edits one line | Low | High | Keep the diff minimal and let the new tests carry the value |
| A new test asserts on prompt-body text instead of CLI output | Medium | Low | Review each added assertion for CLI output or file targets only |
| Spec touch-ups drift from the prompt wording | Low | Medium | Quote the prompt behavior verbatim and change specs only where they disagree |

## Security Profile
Risk surfaces: none touched (prompts, CLI output contracts, docs; no auth, secrets, PII, HTTP, deserialization, subprocess, file-path handling, SQL, or eval changes)
Negative tests: default review path performs no edits and no commit; `--apply` never lands SUGGESTION or OPPORTUNITY; incomplete brief stops with exactly `brief incomplete`
Constraints: GREEN changes stay inside the listed workstation files; JUDGE, `--profile fast`, and ISS-ADH-029 behavior stay untouched

## Integration Points
- **`deviate walkthrough pre` JSON contract**: Supplies `issue_brief_path`, `plan_path`, `test_files`, and `production_files` to the four-look map
- **`deviate review pre` JSON contract**: Supplies `issue_brief_path`, `apply`, `apply_scope`, and the uncovered plan-AC list to the comment engine
- **`/deviate-e2e` completion chain**: Calls review then walkthrough with no reference to a `pr-review` pack or command

## Constitutional Alignment
- **Architecture**: Meso plan authors the Gherkin contract for the Micro RED, GREEN, JUDGE, and REFACTOR loop; Gate 3 review and walkthrough stay post-micro audit tools with no new layer or catalog (constitution §1)
- **Testing**: pytest pins CLI output and files per `tests/unit/test_cli/test_review.py` and `tests/unit/test_cli/test_walkthrough.py`; `ruff check` guards the CLI files; coverage stays above 80 percent (constitution §3)
- **Git Isolation**: All work stays on the pre-configured issue worktree and branch; no branch switches and no main-branch edits (constitution §4)
- **User Scenarios**: `AC-PLAN-001` encodes `US-035-01`, `AC-PLAN-002` encodes `US-035-02`, `AC-PLAN-003` encodes `US-035-03`, and `AC-PLAN-004` encodes `US-035-04`; RED turns each automated scenario into a failing test before GREEN
