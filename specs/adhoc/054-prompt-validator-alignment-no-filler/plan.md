## Plan Summary
- **Issue**: ISS-ADH-054 — Align prompt schemas with post-script validators and cut filler-forcing checks
- **Implementation Strategy**: Align each prompt schema list with its validator required list, replace filler-forcing checks with substance checks and loud failures, then fix or grandfather shipped sample artifacts.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Prompt schema lists agree one-to-one with validator required lists**
- **Source Outline**: `AO-054-01`
- **Upstream Traceability**: `US-054-01`, `FR-ADHOC-054`, `AC-ADHOC-054-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:ARTIFACT_VALIDATORS`
- **Given**: Prompt schema lists in `src/deviate/prompts/auto/explore.md`, `research.md`, and `prd.md` name sections the validators never require
- **When**: The agent aligns each prompt schema list with its `ARTIFACT_VALIDATORS` required list per phase
- **Then**: Every mandated section appears in both the prompt and the validator with neither side citing an extra section
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Session State leaves the PRD contract for manifest JSON**
- **Source Outline**: `AO-054-01`
- **Upstream Traceability**: `US-054-01`, `FR-ADHOC-054`, `AC-ADHOC-054-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:PRD_CONTRACT_SECTIONS`
- **Given**: `PRD_CONTRACT_SECTIONS` in `src/deviate/core/validation.py` requires `Session State`
- **When**: The agent removes `Session State` from `PRD_CONTRACT_SECTIONS` and routes it to manifest JSON
- **Then**: PRD validation passes without a `Session State` section and the manifest carries the session state
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Source Registry leaves required lists for Document Control**
- **Source Outline**: `AO-054-01`
- **Upstream Traceability**: `US-054-01`, `FR-ADHOC-054`, `AC-ADHOC-054-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:ARTIFACT_VALIDATORS`
- **Given**: `design` and `data_model` validator lists require `Source Registry` while prompts never mandate it consistently
- **When**: The agent removes `Source Registry` from required lists and folds it into Document Control
- **Then**: Design and data-model validation passes without `Source Registry` and existing references resolve to the new home
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Shipped sample artifacts pass or carry a grandfather note**
- **Source Outline**: `AO-054-01`
- **Upstream Traceability**: `US-054-01`, `FR-ADHOC-054`, `AC-ADHOC-054-01`
- **Current-Code Evidence**: `src/deviate/core/validation.py:validate_artifact`
- **Given**: Shipped sample artifacts under `specs/` predate the aligned validators
- **When**: The agent runs post-script validation over the shipped sample artifacts
- **Then**: Each sample artifact passes validation or carries an explicit grandfather note, and unmarked legacy failures still fail
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Empty sections fail substance checks and oversized registries warn at caps**
- **Source Outline**: `AO-054-02`
- **Upstream Traceability**: `US-054-02`, `FR-ADHOC-054`, `AC-ADHOC-054-02`
- **Current-Code Evidence**: `src/deviate/core/validation.py:extract_section_body`
- **Given**: Validators check only section presence while prompts demand Sibling Flow Inventory, Scope Sizing, and Non-Functional content
- **When**: The agent adds substance checks for empty mandated sections and row-count warning caps for File Registry and Risks
- **Then**: An empty mandated header fails with the section named, oversized registries warn at the cap without failing, and FR sub-fields absent as N/A pass while present-but-empty sub-fields fail
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Missing verification mode fails loudly instead of silent repair**
- **Source Outline**: `AO-054-02`
- **Upstream Traceability**: `US-054-02`, `FR-ADHOC-054`, `AC-ADHOC-054-02`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:_validate_or_repair_plan`
- **Given**: `_validate_or_repair_plan` in `src/deviate/cli/meso.py` silently inserts a default verification mode
- **When**: The agent removes `repair_missing_verification_mode` from the plan post path
- **Then**: A plan scenario missing its verification mode errors with the scenario id and no default is inserted
- **Verification Mode**: automated

**Scenario AC-PLAN-007: PRD FR sub-fields become omit-if-N/A and plan risk stays a one-liner**
- **Source Outline**: `AO-054-02`
- **Upstream Traceability**: `US-054-02`, `FR-ADHOC-054`, `AC-ADHOC-054-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/prd.md:FR-{NNN}-{ID}`
- **Given**: The PRD prompt mandates Preconditions, State Transition, and Exception sub-fields on every FR and the plan prompt invites risk prose
- **When**: The agent marks the three FR sub-fields omit-if-N/A and caps plan Risk Assessment to a one-liner plus row-count warnings
- **Then**: FRs without applicable sub-fields validate clean, present-but-empty sub-fields fail substance, and no new prompt prose ships beyond the schema alignment
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/validation.py**: owns `ARTIFACT_VALIDATORS`, `PRD_CONTRACT_SECTIONS`, substance checks, warning caps, and repair removal target
  - **Current State**: Presence-only section checks; `Session State` in PRD contract; `Source Registry` required; silent `repair_missing_verification_mode` exists
  - **Changes Required**: Align required lists, drop `Session State` and `Source Registry`, add substance and cap warnings, delete or fail-loud the repair path
  - **Integration Surface**: `validate_artifact`, `validate_macro_contract`, `validate_sections` consumed by `src/deviate/cli/macro.py` and `src/deviate/cli/meso.py`
- **src/deviate/prompts/auto/explore.md**: owns explore prompt schema including Sibling Flow Inventory, Scope Sizing, File Registry
  - **Current State**: Names sections the explore validator list does not require
  - **Changes Required**: Align schema list one-to-one with the explore validator list
  - **Integration Surface**: `src/deviate/prompts/assembly.py` layer routing for explore
- **src/deviate/prompts/auto/research.md**: owns design and data-model prompt schemas including Source Registry
  - **Current State**: Emits Source Registry and sections diverging from validator lists
  - **Changes Required**: Align schema lists, drop Source Registry requirement, fold into Document Control reference
  - **Integration Surface**: Design and data-model artifacts consumed by `deviate prd pre`
- **src/deviate/prompts/auto/prd.md**: owns PRD prompt schema including FR sub-fields and Session State
  - **Current State**: Mandates Session State and all FR sub-fields unconditionally
  - **Changes Required**: Drop Session State, mark Preconditions, State Transition, Exception omit-if-N/A
  - **Integration Surface**: PRD artifact validated by `validate_macro_contract`
- **src/deviate/prompts/auto/plan.md**: owns plan prompt schema including Risk Assessment
  - **Current State**: No cap language on Risk Assessment prose
  - **Changes Required**: Cap Risk Assessment to one-liner plus row-count warning reference
  - **Integration Surface**: `plan.md` validated by `validate_acceptance_contract` via `src/deviate/cli/meso.py`
- **src/deviate/cli/meso.py**: owns plan post validation and silent repair call site
  - **Current State**: `_validate_or_repair_plan` auto-fills missing verification modes
  - **Changes Required**: Replace silent repair with loud failure citing the scenario id
  - **Integration Surface**: `repair_missing_verification_mode` import from `src/deviate/core/validation.py`
- **tests/unit/test_core/test_validation.py**: owns validator unit tests
  - **Current State**: Tests cover presence checks and repair behavior
  - **Changes Required**: One failing test per validator change; update repair tests to expect loud failure
  - **Integration Surface**: `mise run test` unit sandbox gate
- **specs/DeviaTDD-api.md, specs/DeviaTDD-architecture.md, CHANGELOG.md**: own spec alignment and release notes
  - **Current State**: Reflect current validator and contract behavior
  - **Changes Required**: Update spec sections and append `[Unreleased]` bullet in the same commit
  - **Integration Surface**: Constitution §5 Definition of Done and AGENTS.md spec-alignment rule

## Implementation Strategy
- **Phase 1**: Align prompt schemas with validator required lists and relocate Session State and Source Registry
  - **Files**: `src/deviate/core/validation.py`, `src/deviate/prompts/auto/explore.md`, `src/deviate/prompts/auto/research.md`, `src/deviate/prompts/auto/prd.md`
  - **Approach**: Change validators first with one failing test per change, then edit prompt schemas to match one-to-one
  - **Verification**: Unit tests pass; sample diff shows prompt and validator lists identical per phase
- **Phase 2**: Replace filler-forcing checks with substance checks, caps, and loud verification-mode failure
  - **Files**: `src/deviate/core/validation.py`, `src/deviate/cli/meso.py`, `src/deviate/prompts/auto/prd.md`, `src/deviate/prompts/auto/plan.md`, `tests/unit/test_core/test_validation.py`
  - **Approach**: Add empty-section substance errors, row-count warnings, omit-if-N/A FR sub-fields, and delete the silent repair call
  - **Verification**: New failing-then-passing tests for each check; missing mode errors with scenario id
- **Phase 3**: Fix or grandfather shipped sample artifacts and update specs plus CHANGELOG
  - **Files**: `specs/` sample artifacts, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Run post-script validation over samples; fix cheap failures, add explicit grandfather notes elsewhere
  - **Verification**: Validation run over samples shows pass or grandfather status; `mise run check` clean

## Data Flow Analysis
- Inputs arrive as prompt schema lists and validator required lists plus shipped sample artifacts. The agent compares each pair, edits the validator lists and prompt schemas to match, and routes Session State to manifest JSON. Substance checks read section bodies via `extract_section_body`, emit errors for empty mandated sections and warnings at row-count caps, and reject missing verification modes loudly. Outputs land as passing unit tests, clean sample validation runs, and updated spec plus CHANGELOG entries.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Validator tightening breaks shipped artifacts beyond grandfather scope | Medium | Medium | Fix cheap failures, grandfather the rest with explicit notes |
| Prompt edits drift from validator lists again | Medium | Low | Keep lists adjacent in review; one test pins each pair |
| Silent-repair removal breaks existing plans in flight | Low | Low | Loud error cites scenario id so authors fix in one edit |

## Security Profile
Risk surfaces: file paths, deserialization
Negative tests: missing section body does not crash substance check, malformed frontmatter still rejected, repair removal never writes default modes into plans
Constraints: no new dependencies, no writes outside `src/`, `specs/`, `tests/`, `CHANGELOG.md`

## Integration Points
- **Post-script validators in `src/deviate/cli/macro.py` and `src/deviate/cli/meso.py`**: consume `validate_artifact` and `validate_macro_contract`; contract is aligned required lists plus substance errors and cap warnings
- **`deviate plan post` via `_validate_or_repair_plan`**: consumes `validate_acceptance_contract`; contract is loud missing-mode failure with scenario id, no silent insert
- **Prompt assembly in `src/deviate/prompts/assembly.py`**: serves edited prompt schemas; contract is one-to-one section agreement with validators

## Constitutional Alignment
- **Architecture**: Implements the three-layer model: macro prompts and validators agree, meso plan owns the authoritative contract, micro RED encodes these AC-PLAN scenarios as failing tests
- **Testing**: pytest via `mise run test` with one failing test per validator change; `mise run check` gates lint, format, and types
- **Git Isolation**: All work stays on the dedicated issue branch inside the pre-configured worktree; commits happen only via the orchestrator post step
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-004` encode `US-054-01` prompt-validator agreement; `AC-PLAN-005` through `AC-PLAN-007` encode `US-054-02` substance over filler; RED turns each into failing tests
