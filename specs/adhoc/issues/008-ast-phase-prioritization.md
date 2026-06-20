---
title: "AST/Structural Analysis Phase Prioritization — Token/Cost Effectiveness Ranking"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-008
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/008-ast-phase-prioritization.md`
- **Primary Architectural Workstation**: `specs/adhoc/008-ast-phase-prioritization/analysis.md` (output recommendation document)
- **Upstream Evidence**: `specs/explore/ast-tree-sitter.md` (complete phase-by-phase integration potential table, sole AST usage reference at `src/deviate/cli/micro.py:2469-2539`)
- **Constitution Reference**: `specs/constitution.md` §`1_ARCHITECTURAL_PRINCIPLES` (model tiering: Flash=cheap, Pro=expensive, Qwen=premium)

## The Problem Contract
The explore.md at `specs/explore/ast-tree-sitter.md:200-213` catalogs 10 phase/AST integration potentials spanning HIGH to LOW, but does not factor in token/cost economics. Blindly integrating AST parsing everywhere would waste tokens on low-value phases (RED writes test stubs, MACRO operates on Markdown) while under-investing in high-ROI phases (JUDGE validates `git diff` against spec, REFACTOR replaces fragile return-type checker). The user needs a concrete, cost-aware prioritization document that ranks every phase by ROI, identifies the smallest set of structural checks that delivers the most value, and explicitly excludes phases where the token cost exceeds the benefit.

## Scope Boundaries
### Hard Inclusions
- Read `specs/explore/ast-tree-sitter.md` for the complete phase-by-phase integration potential table (HIGH: JUDGE, REFACTOR; MEDIUM: GREEN, PLAN, YELLOW, TamperGuard; LOW: RED, MACRO, TASKS)
- Read `specs/constitution.md` for model tiering cost structure (Flash < Pro < Qwen)
- Factor in: (a) code volume parsed per phase invocation, (b) structural complexity of output requiring validation, (c) existing non-AST alternatives and their effectiveness, (d) model cost tier for the consuming phase, (e) token savings achieved via structural analysis (preventing rework cycles)
- Map each phase to a concrete structural check with estimated token budget and cost justification
- Write the prioritization document to `specs/adhoc/008-ast-phase-prioritization/analysis.md`
- The document must contain: an ordered HIGH-ROI → SKIP ranking table, per-phase rationale with verbatim explore.md evidence, recommended checks, excluded phases with explicit rationale, and a decision heuristic for evaluating future phases

### Defensive Exclusions
- Do NOT implement any AST integration code — this is a decision document, not implementation
- Do NOT add `tree-sitter` or any AST dependency to `pyproject.toml`
- Do NOT modify any prompt templates (`src/deviate/prompts/`) — that belongs to a follow-up implementation issue
- Do NOT modify `src/deviate/cli/micro.py:_check_return_type_mismatch()` — only analyze its limitations for the ranking
- Do NOT evaluate languages other than Python (DeviaTDD is Python-only, per constitution §`2_1_BACKEND`)
- Do NOT produce separate explore/PRD artifacts — this is a single analysis output

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-008`
- **Acceptance Criteria Tokens**: `AC-ADHOC-008-01`, `AC-ADHOC-008-02`, `AC-ADHOC-008-03`, `AC-ADHOC-008-04`, `AC-ADHOC-008-05`
- **Data Model Entities**: None (analysis document, no state entities)

## User Stories Ledger
- **US-008-01**: As a DeviaTDD system architect, I want a concrete, token-cost-weighted ranking of all phases for AST integration so that I can budget implementation effort toward the highest-ROI phases and defensively exclude low-ROI phases. *(Ref: FR-ADHOC-008)*
- **US-008-02**: As a DeviaTDD operator, I want explicit go/no-go decisions per phase backed by explore.md evidence and cost analysis so that I can trust the prioritization without redoing the research.

## ATDD Acceptance Criteria
**Scenario 008**: Phase ranking document is generated and traceable
**Given** `specs/explore/ast-tree-sitter.md` contains a phase-by-phase integration potential table (lines 200-213) and `specs/constitution.md` defines model tiering (lines 15-16)
**When** the analysis document at `specs/adhoc/008-ast-phase-prioritization/analysis.md` is produced
**Then** every DeviaTDD phase (JUDGE, REFACTOR, GREEN, PLAN, TASKS, RED, explore, research, PRD, shard, YELLOW, TamperGuard) receives an explicit HIGH-ROI, MEDIUM-ROI, LOW-ROI, or SKIP ranking with token-cost justification traceable to explore.md verbatim snippets or constitution clauses.

**Scenario 008-02**: Model cost tier is factored into ROI calculus
**Given** the constitution assigns V4 Flash (cheap) to high-frequency phases (RED, GREEN, REFACTOR, explore) and V4 Pro (expensive) to compliance phases (JUDGE, YELLOW, plan)
**When** ranking phases by ROI
**Then** structural analysis that prevents costly Pro-phase rework scores higher than Flash-phase optimization, and this weighting is documented per phase.

**Scenario 008-03**: At least one concrete structural check identified per ranked phase
**Given** a phase ranked HIGH-ROI or MEDIUM-ROI
**When** the analysis document describes integration value
**Then** it identifies at least one concrete structural check (e.g., "diff signature validation against spec" for JUDGE, "dead code detection" for REFACTOR) with estimated token budget for the check.

**Scenario 008-04**: Excluded phases carry explicit rationale
**Given** a phase ranked LOW-ROI or SKIP
**When** the document lists it
**Then** the rationale references a specific constraint (e.g., "RED produces test stubs, no production code to parse", "MACRO operates on Markdown, tree-sitter is Python-only") and a decision heuristic for evaluating similar future phases.

**Scenario 008-05**: Source anchoring verification
**Given** the analysis document is complete
**When** validated against explore.md and constitution.md
**Then** every cost claim or integration-potential claim is traceable to a verbatim snippet (≤10 lines) or section in the source documents.

## Edge Cases and Boundaries
- The constitution's model tiering is configurable via `.deviate/config.toml` `[models]` section — the analysis must note that overrides can change cost calculus and the ranking assumes the documented defaults.
- `py-tree-sitter` incremental parsing (`parser.parse(new_src, old_tree)`) reduces per-use cost on repeated parses of the same file — the analysis should note this if recommending checks that run multiple times on the same file (e.g., JUDGE diff analysis).
- Stdlib `ast` (zero-dependency, zero-overhead) may be sufficient for LOW-ROI phases where structural analysis is nice-to-have — the analysis must not recommend tree-sitter where stdlib `ast` suffices.
- The sole existing AST usage (`_check_return_type_mismatch` at `src/deviate/cli/micro.py:2469-2539`) walks every `FunctionDef` node looking for return-type mismatches — the analysis should note whether this check is token-efficient or replaceable.

## Performance Constraints
- The analysis document should be generated in a single pass — no multi-agent coordination required
- Output document should be ≤ 500 lines (concise, scannable)
- Every verbatim source reference must be ≤ 10 lines

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: N/A (analysis document, no code)
- **Integration Sandbox Targets**: N/A

## Demonstration Path
```bash
# Verify the analysis document exists and contains the required sections
ls specs/adhoc/008-ast-phase-prioritization/analysis.md

# Verify all phases are covered (grep for each phase name)
grep -c "JUDGE\|REFACTOR\|GREEN\|PLAN\|TASKS\|RED\|YELLOW\|TamperGuard\|explore\|research\|PRD\|shard" \
  specs/adhoc/008-ast-phase-prioritization/analysis.md

# Verify the ranking categories are present
grep -c "HIGH-ROI\|MEDIUM-ROI\|LOW-ROI\|SKIP" \
  specs/adhoc/008-ast-phase-prioritization/analysis.md

# Verify verbatim source anchoring (explore.md and constitution.md references)
grep -c "explore/ast-tree-sitter.md\|constitution.md" \
  specs/adhoc/008-ast-phase-prioritization/analysis.md
```
