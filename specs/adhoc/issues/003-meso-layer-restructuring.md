---
title: "Meso-Layer Restructuring — Merge Specify into Shard, Introduce Plan Phase"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-003
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/003-meso-layer-restructuring.md`
- **Primary Architectural Workstation**:
  - `src/deviate/prompts/skills/deviate-shard/SKILL.md` — enhance to produce spec-level issue files
  - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` — enhance to produce spec-level issue files
  - `src/deviate/prompts/skills/deviate-plan/SKILL.md` — NEW skill for per-issue research/planning
  - `src/deviate/prompts/skills/deviate-specify/SKILL.md` — deprecate (redirect to new workflow)
  - `src/deviate/prompts/skills/deviate-tasks/SKILL.md` — update to consume spec-enriched issues
  - `specs/DeviaTDD-api.md` — update endpoint architecture and workflow descriptions
  - `specs/DeviaTDD-architecture.md` — update layer diagrams and phase descriptions
  - `specs/constitution.md` — update three-layer architecture and HITL gate descriptions

## [THE_PROBLEM_CONTRACT]
The current meso-layer has a redundant `/deviate-specify` step that merely reformats what `/deviate-shard` already produces. Meanwhile, by the time a developer reaches issue #5, the epic-level explore/research artifacts are stale. This restructuring merges specify into shard (issues are born as full specs), and introduces a per-issue `/deviate-plan` phase that performs fresh localized research before task decomposition.

## [SCOPE_BOUNDARIES]
### Hard Inclusions
- `/deviate-shard` skill must produce issue files with full spec-level detail: user stories (US-NNN), Gherkin acceptance criteria (Given/When/Then), edge cases, performance constraints, and scope boundaries
- `/deviate-adhoc` skill must produce issue files in the same spec-enriched format
- New `/deviate-plan` skill must perform per-issue localized codebase research and produce a planning document contextualizing the issue for current codebase state
- `/deviate-specify` skill must be marked deprecated with redirect documentation
- `/deviate-tasks` skill must be updated to consume spec-enriched issue format directly (no separate spec.md lookup)
- Architecture docs (`DeviaTDD-api.md`, `DeviaTDD-architecture.md`) must reflect the new workflow
- Constitution must update HITL Gate 2 position (moves to after shard, not after specify)

### Defensive Exclusions
- Do NOT modify any micro-layer skills (red, green, yellow, judge, refactor, prune, e2e)
- Do NOT modify CLI Python source code (`src/deviate/cli/`, `src/deviate/core/`) — this is a skill/prompt-only change
- Do NOT modify the macro-layer skills (explore, research, prd) — they remain unchanged
- Do NOT change the append-only ledger protocol or issue/task record schemas
- Do NOT create new CLI subcommands — this is purely a skill restructuring

## [UPSTREAM_REQUIREMENT_TRACING]
- **Requirements Tokens**: `FR-ADHOC-003`
- **Acceptance Criteria Tokens**: `AC-ADHOC-003-01`, `AC-ADHOC-003-02`, `AC-ADHOC-003-03`, `AC-ADHOC-003-04`, `AC-ADHOC-003-05`, `AC-ADHOC-003-06`
- **Data Model Entities**: N/A (skill/prompt restructuring, no data model changes)

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Sandbox Targets**: N/A (prompt/skill files, no Python unit tests)
- **Integration Sandbox Targets**: Manual verification that skill files parse correctly and workflow logic is internally consistent

## [DEMONSTRATION_PATH]
```bash
# Verify all skill files exist and are valid YAML/Markdown
ls -la src/deviate/prompts/skills/deviate-shard/SKILL.md
ls -la src/deviate/prompts/skills/deviate-adhoc/SKILL.md
ls -la src/deviate/prompts/skills/deviate-plan/SKILL.md
ls -la src/deviate/prompts/skills/deviate-specify/SKILL.md  # should show deprecation notice

# Verify architecture docs updated
grep -c "deviate-plan" specs/DeviaTDD-api.md
grep -c "deviate-plan" specs/DeviaTDD-architecture.md

# Verify constitution updated
grep -c "Plan" specs/constitution.md
```

## [WORKFLOW_RESTRUCTURING_DETAILS]

### Current Flow (Being Replaced)
```
Macro:  Explore → Research → PRD → Shard (produces thin issue stubs)
Meso:   Specify (produces spec.md from issue) → [HITL Gate 2] → Tasks
Micro:  RED → GREEN → JUDGE → REFACTOR
```

### New Flow (Target State)
```
Macro:  Explore → Research → PRD → Shard+Specify (issues ARE specs)
Meso:   [HITL Gate 2] → Plan (per-issue fresh research) → Tasks
Micro:  RED → GREEN → JUDGE → REFACTOR
```

### Key Changes
1. **Shard produces specs**: Issue files contain user stories, Gherkin AC, edge cases — not just high-level descriptions
2. **Adhoc produces specs**: Same format as shard for consistency
3. **Specify deprecated**: Redirects to new workflow (shard already produces specs)
4. **Plan introduced**: Per-issue localized research before tasks — reads current codebase state, understands what prior issues implemented, contextualizes the issue
5. **HITL Gate 2 repositioned**: Moves to after shard (review the specified issues) instead of after specify
6. **Tasks updated**: Consumes spec-enriched issue format directly, no separate spec.md lookup

### Shard Issue Format (Target)
Each issue file produced by shard must include:
- YAML frontmatter (title, labels, blocked_by, coordinates_with, issue_id)
- `## [SYSTEM_TOPOLOGY_MAPPING]` — epic domain, file paths, workstations
- `## [THE_PROBLEM_CONTRACT]` — user/system journey narrative
- `## [SCOPE_BOUNDARIES]` — Hard Inclusions and Defensive Exclusions
- `## [UPSTREAM_REQUIREMENT_TRACING]` — FR and AC tokens
- `## [USER_STORIES_LEDGER]` — US-NNN stories with FR traceability
- `## [ATDD_ACCEPTANCE_CRITERIA]` — Gherkin Given/When/Then scenarios
- `## [EDGE_CASES_AND_BOUNDARIES]` — edge cases, error states, boundary conditions
- `## [PERFORMANCE_CONSTRAINTS]` — latency, throughput, resource limits
- `## [MULTI_TIERED_VERIFICATION_TARGETS]` — unit and integration test paths
- `## [DEMONSTRATION_PATH]` — exact bash commands for verification

### Plan Skill Purpose
The `/deviate-plan` skill performs localized research on a specific issue:
- Reads the spec-enriched issue file
- Scans current codebase state (what exists NOW, not at epic-explore time)
- Analyzes what prior issues implemented (git log, completed issues)
- Identifies integration points, dependencies, potential conflicts
- Produces a planning document that contextualizes the issue for `/deviate-tasks`
- Output: `plan.md` in the issue workspace with implementation strategy, file mappings, risk assessment
