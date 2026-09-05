## Plan Summary
- **Issue**: 005-005 — Prompt Template and Specification Alignment
- **Implementation Strategy**: Edit the four prompt templates to state the RED checkpoint and GREEN/REFACTOR gates, update the two spec documents with the verification-mode contract and gate semantics, and append the CHANGELOG bullet with template content tests pinning the text.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-3 hours

## Acceptance Contract
**Scenario AC-PLAN-001: RED templates state checkpoint completion with warning advisory**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-005-11`, `FR-005-06`, `AC-005-06-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/red.md:already_satisfied`
- **Given**: The RED runner completes on a passing suite with a warning advisory
- **When**: An agent reads the RED prompt templates
- **Then**: `src/deviate/prompts/commands/deviate-red.md` and `src/deviate/prompts/auto/red.md` state that RED completes with a warning advisory and carry no rejection statement
- **Verification Mode**: automated

**Scenario AC-PLAN-002: GREEN template states the blocking gate with JUDGE routing**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-005-11`, `FR-005-06`, `AC-005-06-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/green.md:train_feedback`
- **Given**: The GREEN runner blocks on a failing suite and routes to JUDGE via train feedback
- **When**: An agent reads the GREEN prompt template
- **Then**: `src/deviate/prompts/auto/green.md` describes the blocking gate and the RED warning advisory does not block start
- **Verification Mode**: automated

**Scenario AC-PLAN-003: REFACTOR template states the regression gate**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-005-11`, `FR-005-06`, `AC-005-06-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/refactor.md:Invariant`
- **Given**: The REFACTOR runner fails the phase on a non-zero post-polish test result
- **When**: An agent reads the REFACTOR prompt template
- **Then**: `src/deviate/prompts/auto/refactor.md` states that a post-polish test failure fails the phase
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Spec documents record contracts and gates without contradiction**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-005-12`, `FR-005-06`, `AC-005-06-01`
- **Current-Code Evidence**: `specs/DeviaTDD-api.md:validate_acceptance_contract`
- **Given**: The runner behavior for the RED checkpoint and GREEN/REFACTOR gates is fixed
- **When**: A reviewer reads the spec documents
- **Then**: `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` document the verification-mode contract line, the acceptance criteria traceability, the handoff advisory, and the gate semantics with no contradicting section
- **Verification Mode**: automated

**Scenario AC-PLAN-005: CHANGELOG records the gate behavior change**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-005-13`, `FR-005-06`, `AC-005-06-01`
- **Current-Code Evidence**: `CHANGELOG.md:[Unreleased]`
- **Given**: The gate behavior changes are user-visible
- **When**: A reader opens the changelog
- **Then**: `CHANGELOG.md` carries a bullet under `[Unreleased]` that describes the gate behavior changes
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/prompts/commands/deviate-red.md**: states the RED checkpoint completion with warning advisory
  - **Current State**: Mentions train feedback injection in manual mode; lacks checkpoint wording
  - **Changes Required**: Add completion-with-warning statement; remove any rejection statement
  - **Integration Surface**: Manual `/deviate-red` command consumed by agents
- **src/deviate/prompts/auto/red.md**: describes the checkpoint semantics and handoff advisory
  - **Current State**: Already emits `already_satisfied` with named files; wording needs alignment to checkpoint terms
  - **Changes Required**: State the phase completes and hands the advisory to GREEN
  - **Integration Surface**: `_run_red_phase` runner and `RedHandoffAdvisory` handoff
- **src/deviate/prompts/auto/green.md**: describes the blocking gate and JUDGE routing
  - **Current State**: Carries train feedback ingestion; gate wording needs alignment
  - **Changes Required**: State a failing suite routes to JUDGE via train feedback; the RED warning does not block start
  - **Integration Surface**: `_run_green_phase` runner and JUDGE verdict loop
- **src/deviate/prompts/auto/refactor.md**: describes the regression gate
  - **Current State**: Carries the test-modification invariant; gate wording needs alignment
  - **Changes Required**: State a non-zero post-polish test result fails the phase
  - **Integration Surface**: REFACTOR runner post-polish test run
- **specs/DeviaTDD-api.md**: records the verification-mode contract, acceptance criteria field, handoff, and gate semantics
  - **Current State**: Documents verification-mode auto-repair and train feedback; needs handoff and gate alignment
  - **Changes Required**: Document the contract line, the task record field, the handoff advisory, and GREEN/REFACTOR gates
  - **Integration Surface**: `src/deviate/core/validation.py::validate_acceptance_contract` and micro runners
- **specs/DeviaTDD-architecture.md**: records the phase state machine with checkpoint and gates
  - **Current State**: Documents the TDD cycle and JUDGE routing; needs checkpoint and regression-gate wording
  - **Changes Required**: Document the RED checkpoint, GREEN gate with JUDGE routing, and REFACTOR regression gate
  - **Integration Surface**: Micro-layer state machine in `src/deviate/cli/micro.py`
- **CHANGELOG.md**: gains the user-visible bullet under `[Unreleased]`
  - **Current State**: Has an `[Unreleased]` section without the gate entry
  - **Changes Required**: Append one bullet for the gate behavior changes
  - **Integration Surface**: Release notes readers
- **tests/unit/test_meso/test_auto_prompt_templates.py**: pins template content and rejects stale statements
  - **Current State**: Pins slim templates and merge push gate; no gate-semantics checks
  - **Changes Required**: Add checks that red/green/refactor templates carry new semantics and no stale rejection text
  - **Integration Surface**: `deviate.prompts.assembly::load_template`

## Implementation Strategy
- **Phase 1**: Align prompt templates and pin with tests
  - **Files**: `src/deviate/prompts/commands/deviate-red.md`, `src/deviate/prompts/auto/red.md`, `src/deviate/prompts/auto/green.md`, `src/deviate/prompts/auto/refactor.md`, `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Approach**: Edit the four templates to the checkpoint and gate wording, then add content checks that fail on stale rejection phrases or missing gate text
  - **Verification**: Run `uv run pytest tests/unit/test_meso/test_auto_prompt_templates.py -v` and the grep scans from the Demonstration Path
- **Phase 2**: Align specs and changelog
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Document the verification-mode contract, acceptance criteria traceability, handoff advisory, and gate semantics in both specs in the same commit; append the changelog bullet
  - **Verification**: Grep for the contract line in the API spec, run the changelog awk check, and run `mise run check`

## Data Flow Analysis
- Inputs: runner behavior from issues `005-001` through `005-004` plus the issue AO outlines. Transformations: template wording edits, spec section edits, changelog bullet, template content tests. Outputs: aligned prompts, specs, changelog entry, passing tests. Storage: prompt files under `src/deviate/prompts/`, specs under `specs/`, changelog at repo root, tests under `tests/`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Stale rejection phrase survives in a template | High | Medium | Grep scans plus content tests fail on forbidden phrases |
| Spec wording contradicts runner behavior | High | Low | Review compares each spec claim against the micro runner code |
| Changelog bullet misses the `[Unreleased]` section | Medium | Low | Awk presence check in the Demonstration Path |
| Install mirror touched by accident | Medium | Low | `git status` check limits writes to allowed paths |

## Security Profile
Risk surfaces: file paths (prompt and spec text edits only)
Negative tests: stale rejection statement fails review, template without gate text fails review, install mirror writes fail the status check
Constraints: edit prompt templates in `src/deviate/prompts/` only, never touch `~/.config/opencode/skills/`, no runner behavior changes, no new dependencies

## Integration Points
- **Micro runners in `src/deviate/cli/micro.py`**: templates must describe the runner behavior exactly; no runner change in this issue
- **Validation in `src/deviate/core/validation.py::validate_acceptance_contract`**: API spec must describe the verification-mode contract the validator enforces
- **Tasks ledger and `TaskRecord.acceptance_criteria`**: API spec must describe the traceability Tasks and JUDGE use

## Constitutional Alignment
- **Architecture**: Follows the three-layer model; plan authors the authoritative contract for Tasks, RED, and JUDGE with no layer skipped
- **Testing**: Uses pytest with content checks on templates plus grep scans; keeps the full suite under 30 seconds
- **Git Isolation**: Runs on the dedicated issue branch inside the pre-configured worktree; no branch switches
- **User Scenarios**: Each `AC-PLAN-NNN` maps to `US-005-11` through `US-005-13` and `FR-005-06`; RED turns the template and gate scenarios into failing-then-passing content tests
