---
title: "Align prompt schemas with post-script validators and cut filler-forcing checks"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-054
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/054-prompt-validator-alignment-no-filler.md`
- **Primary Architectural Workstation**: `src/deviate/core/validation.py`, `src/deviate/prompts/`

## The Problem Contract
Artifact prompts and post-script validators disagree, and validators force filler into generated artifacts. This issue aligns each prompt schema list with its validator required list and replaces filler-forcing checks with substance checks.

## Scope Boundaries
### Hard Inclusions
- One-to-one agreement between prompt schema lists and `ARTIFACT_VALIDATORS` required lists per phase
- Removal of Session State from `PRD_CONTRACT_SECTIONS` into manifest JSON
- Removal of Source Registry from required lists, folded into Document Control or dropped
- PRD FR sub-fields Preconditions, State Transition, and Exception made omit-if-N/A
- Plan Risk Assessment one-liner plus row-count warning caps, not more prompt prose
- Silent `repair_missing_verification_mode` replaced with a loud failure
- Shipped sample artifacts pass validators or carry an explicit grandfather note
- Spec plus CHANGELOG updated in the same commit

### Defensive Exclusions
- No new prompt prose beyond the schema alignment; caps arrive as warnings, not paragraphs
- No changes to unrelated validators or phase execution behavior
- No backfill of shipped artifacts beyond the explicit grandfather-or-fix decision

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-054`
- **Acceptance Criteria Tokens**: `AC-ADHOC-054-01`, `AC-ADHOC-054-02`
- **Data Model Entities**: Validator required lists, prompt schema lists, grandfather registry
- **Origin**: GitHub issue 214 (`Align prompt schemas with post-script validators; cut filler-forcing checks`)

## User Stories Ledger
- **US-054-01**: As a phase agent, I want prompts and validators to require the same sections so that my artifact never fails a check the prompt never named. *(Ref: FR-ADHOC-054)*
- **US-054-02**: As a maintainer, I want validators to reward substance over filler so that generated artifacts stay short and honest. *(Ref: FR-ADHOC-054)*

## Acceptance Outline
- **AO-054-01** *(Ref: AC-ADHOC-054-01, US-054-01)*: Prompt schema lists and validator required lists agree one-to-one per phase, Session State leaves the PRD contract for manifest JSON, and shipped sample artifacts pass or carry an explicit grandfather note.
  - **Happy Path**: Every mandated section appears in both the prompt and the validator, and sample artifacts validate clean.
  - **Error Category**: A section the validator demands but the prompt never names fails the alignment check with both sides cited.
  - **Boundary Category**: Grandfathered artifacts carry the explicit note and pass; unmarked legacy failures still fail.
- **AO-054-02** *(Ref: AC-ADHOC-054-02, US-054-02)*: Empty mandated sections fail substance checks, oversized registries warn at row-count caps, and a missing verification mode fails loudly instead of silent repair.
  - **Happy Path**: An empty mandated header fails with the section named; an oversized registry warns at the cap.
  - **Error Category**: A missing verification mode errors with the scenario id instead of inserting a default.
  - **Boundary Category**: FR sub-fields absent as N/A pass; present-but-empty sub-fields fail substance.

## Edge Cases and Boundaries
- Explore Sibling Flow Inventory and Scope Sizing plus PRD Non-Functional section: enforced only after the prompt names them.
- Source Registry folded into Document Control: existing references resolve to the new home.
- Row-count caps (File Registry 12, Risks 4): warnings only, never hard failures.
- Subagent detail report path cited in the origin issue: consulted at plan time, not vendored into the artifact.

## Performance Constraints
- L_max: 500ms issue registration; validator runs stay within the existing post-script budget.
- Throughput: one validator change ships with its failing test first; no batch validator edits without per-change tests.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` unit suite with one failing test per validator change (exact paths defined at plan time).
- **Integration Sandbox Targets**: Post-script validation run over shipped sample artifacts confirms pass or grandfather status.

## Demonstration Path
```bash
mise run test
```
