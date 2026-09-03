## Plan Summary
- **Issue**: ISS-ADH-029 — Fold Ponytail Minimal-Code Pruning into the /deviate-review Gate and Keep /deviate-pr Squash-Merge Commit-Convention Compliant
- **Implementation Strategy**: Fold the ponytail pre-write ladder into the existing Pragmatism domain of `deviate-review.md` with prompt-text pins; verify and fix `_pr_title` prefix handling in `meso.py` with title/body pins.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Review scan prunes excess code through the ponytail ladder without a new command**
- **Source Outline**: `AO-029-01`
- **Upstream Traceability**: `US-029-01`, `FR-ADHOC-029`, `AC-ADHOC-029-01`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-review.md:82`
- **Given**: Gate 3 review runs on a diff with over-engineered code
- **When**: The reviewer scans the Pragmatism and Architectural Coherence domain
- **Then**: Findings cite the ponytail ladder and no `/deviate-ponytail` file or Minimality heading exists
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Pruning removes only real excess and keeps tested behavior green**
- **Source Outline**: `AO-029-02`
- **Upstream Traceability**: `US-029-01`, `FR-ADHOC-029`, `AC-ADHOC-029-02`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-review.md:82`
- **Given**: A diff with dead or over-abstracted code and green regression tests
- **When**: The review prescribes a minimal-code disposition
- **Then**: The disposition removes the excess, keeps all tests green, and suggests no shared-helper extraction
- **Verification Mode**: automated

**Scenario AC-PLAN-003: PR title and body squash-merge into a valid conventional commit**
- **Source Outline**: `AO-029-03`
- **Upstream Traceability**: `US-029-02`, `FR-ADHOC-029`, `AC-ADHOC-029-03`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_pr_title`
- **Given**: An adhoc issue record with a bracketed title prefix on either platform path
- **When**: The operator runs the PR flow on GitHub and on GitLab
- **Then**: The title matches conventional-commit form and the body serves as the squash-merge commit body
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/prompts/commands/deviate-review.md**: role is the fold target for the ponytail ladder inside the Pragmatism domain
  - **Current State**: Carries one over-engineering line and the no-helper rule; ladder text is absent
  - **Changes Required**: Add the explicit pre-write ladder to the drift line; keep heading set unchanged
  - **Integration Surface**: `src/deviate/cli/review.py` contract; `tests/unit/test_meso/test_auto_prompt_templates.py` pins
- **src/deviate/prompts/commands/deviate-pr.md**: role is the dual-purpose body contract reference
  - **Current State**: Defines `{SUMMARY}` / `{CHANGES}` / `{CLOSES}` body and title format
  - **Changes Required**: None expected; update only if verification exposes a contract gap
  - **Integration Surface**: `src/deviate/cli/meso.py` `_derive_pr_metadata` and `_pr_run`
- **src/deviate/cli/meso.py**: role is the title and push-path implementation under test
  - **Current State**: `_pr_title` strips simple prefixes; GitLab push options omit empty bodies
  - **Changes Required**: Fix prefix-strip gap for compound prefixes; keep transport paths unchanged
  - **Integration Surface**: `src/deviate/core/convention.py` helpers; `gh` and GitLab push options
- **src/deviate/core/convention.py**: role is the canonical scope and emoji helper
  - **Current State**: `commit_scope` strips legacy prefix; emoji detection returns False here
  - **Changes Required**: None expected; reference only
  - **Integration Surface**: `_pr_title` and `format_commit_message`
- **tests/unit/test_meso/test_auto_prompt_templates.py**: role is the prompt-text pin for the fold
  - **Current State**: Pins over-engineering presence and heading absence
  - **Changes Required**: Extend pins to assert ladder text and continued heading absence
  - **Integration Surface**: `deviate-review.md` content
- **tests/unit/test_meso/test_pr_platform.py / tests/unit/test_cli/test_meso.py**: role is the title and body pin for squash-merge compliance
  - **Current State**: Pin adhoc and numbered scopes on title paths
  - **Changes Required**: Add compound-prefix and body-format pins for both platform paths
  - **Integration Surface**: `_pr_title`, `_gitlab_push_options`, `_run_gh_pr_create`
- **specs/DeviaTDD-api.md / specs/DeviaTDD-architecture.md**: role is the spec mirror for user-visible changes
  - **Current State**: Describe review and PR behavior without the folded pruning
  - **Changes Required**: Document folded pruning and verified squash-convention behavior
  - **Integration Surface**: Review and PR command contracts
- **CHANGELOG.md**: role is the user-visible change record
  - **Current State**: Holds released entries plus `[Unreleased]`
  - **Changes Required**: Add one bullet for review pruning and any title fix
  - **Integration Surface**: None

## Implementation Strategy
- **Phase 1**: Fold ladder into review prompt and pin prompt text
  - **Files**: `src/deviate/prompts/commands/deviate-review.md`, `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Approach**: Extend the existing drift line with the ladder; assert ladder present and headings absent
  - **Verification**: Run `pytest tests/unit/test_meso/test_auto_prompt_templates.py -q`
- **Phase 2**: Verify and fix PR title and body compliance on both platform paths
  - **Files**: `src/deviate/cli/meso.py`, `tests/unit/test_cli/test_meso.py`, `tests/unit/test_meso/test_pr_platform.py`
  - **Approach**: Widen prefix-strip coverage; pin title form and body push options per platform
  - **Verification**: Run `pytest tests/unit/test_cli/test_meso.py tests/unit/test_meso/test_pr_platform.py -q`
- **Phase 3**: Mirror specs and changelog in the same commit
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Record folded pruning and verified squash behavior; add `[Unreleased]` bullet
  - **Verification**: Run `mise run check`

## Data Flow Analysis
- Inputs are the issue brief, the review diff, and the issue record title and type. The review prompt transforms the diff into keyed comments through the ladder check. The PR path transforms the record into a conventional title plus a file-based body. Outputs are review comments and platform push payloads. Storage is the append-only issue ledger plus the pushed branch state.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Ladder text drifts into a new heading | Medium | Medium | Pin heading absence in the template test |
| Title fix breaks existing scope pins | Medium | Low | Keep existing scope tests green while adding compound-prefix cases |
| Body contract change ripples to agent skill | Low | Low | Keep body format stable; change CLI prefix handling only |

## Security Profile
Risk surfaces: none touched (prompt text, commit-title strings, push-option strings; no auth, secrets, PII, HTTP, deserialization, subprocess, file-path, SQL, or eval changes).
Negative tests: new command file absent; Minimality and Constraints headings absent; helper-promotion phrases absent; malformed title rejected by pins.
Constraints: prompt-text changes only outside `src/deviate/cli/meso.py` fix; no new dependencies; no hardcoded secrets; mock `deviate.cli.micro._run_pytest` on CLI paths that spawn it.

## Integration Points
- **`deviate review pre` contract**: review prompt reads diff, brief, and plan AC lines; ladder is additive and fail-close stays intact
- **GitHub `gh pr create` path**: receives the conventional title plus the body file unchanged
- **GitLab push-option path**: receives title and description options; empty body omits the description option
- **`commit_scope` helper**: supplies the canonical scope for titles and ledger commits

## Constitutional Alignment
- **Architecture**: Implements the three-layer model: meso plan authors the contract, micro RED encodes user stories as failing tests, Gate 3 reviews the result (constitution §1)
- **Testing**: Uses pytest per §3; prompt-text pins plus TDD for any `meso.py` fix; full suite stays under 30s via `_run_pytest` mocking
- **Git Isolation**: Runs on the dedicated issue worktree branch; commits reference the task ID in conventional form per §4
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `US-029-01` pruning; `AC-PLAN-003` encodes `US-029-02` squash-merge; RED turns each automated scenario into failing tests
